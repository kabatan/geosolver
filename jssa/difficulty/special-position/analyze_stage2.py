"""Prespecified Q42 rank/OLS/bootstrap/permutation analysis of saved numbers."""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import scipy
from scipy.stats import rankdata

from stage2_inputs import HERE, TOLS, build, digest, finite, write_csv, write_json

BOOTSTRAPS = 5000
PERMUTATIONS = 9999
CONTINUOUS = ("year", "n_eq", "n_ineq", "n_pts", "n_circ", "construction_depth", "dsl_len", "n_refs")
CATEGORICAL = ("n_vars", "contest", "has_angle", "has_tangent")
MODELS = {
    "P1": {"x": "G", "ys": ("S",)},
    "P2": {"x": "S", "ys": ("D",), "group": True, "cost": True},
    "P34": {"x": "G", "ys": ("D", "H"), "group": True},
}
CACHE = {}


def basis(x):
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    rank = int(np.sum(s > s[0]*1e-10)) if len(s) else 0
    return u[:, :rank], rank


def residual(y, q):
    return y - q @ (q.T @ y)


def correlation(a, b):
    a, b = a - np.mean(a), b - np.mean(b)
    aa, bb = float(a @ a), float(b @ b)
    if aa <= 1e-18 or bb <= 1e-18:
        return None
    return float(np.clip((a @ b)/math.sqrt(aa*bb), -1, 1))


class Dataset:
    def __init__(self, rows, model):
        self.rows, self.model = rows, model
        self.ids = [r["id"] for r in rows]
        self.n = len(rows)
        self.contest_names = [r["contest"] for r in rows]
        self.contests = np.array(self.contest_names)
        self.continuous = np.array([[r[k] for k in CONTINUOUS] for r in rows], dtype=float).reshape(self.n, len(CONTINUOUS))
        self.categories = {k: np.array([r[k] for r in rows]) for k in CATEGORICAL}
        self.x = np.array([r[model["x"]] for r in rows], dtype=float)
        self.y = {k: np.array([(1 - r["p"]) if k == "D" else r[k] for r in rows], dtype=float) for k in model["ys"]}
        self.p = np.array([r.get("p", np.nan) if r.get("p") is not None else np.nan for r in rows], dtype=float)
        self.cost = {k: np.array([r.get(f"{k}_median0", np.nan) for r in rows], dtype=float) for k in ("nfev", "sec")}
        self.recorded = {k: np.array([r.get(f"{k}_recorded0", 0) for r in rows], dtype=float) for k in ("nfev", "sec")}
        self.planned = np.array([r.get("starts_requested0", 0) for r in rows], dtype=float)
        self.strata = [np.where(self.contests == c)[0] for c in sorted(set(self.contest_names))]

    def design(self, ix):
        columns = [np.ones(len(ix))]
        if len(ix):
            ranks = rankdata(self.continuous[ix], method="average", axis=0)
            columns.extend(ranks[:, j] for j in range(ranks.shape[1]) if np.ptp(ranks[:, j]) > 0)
            for k in CATEGORICAL:
                values = self.categories[k][ix]
                for level in sorted(set(values.tolist())):
                    dummy = (values == level).astype(float)
                    if np.ptp(dummy) > 0:
                        columns.append(dummy)
        return np.column_stack(columns)

    def response_rank(self, key, ix):
        values = self.y[key][ix]
        if key != "H":
            return rankdata(values, method="average")
        out = np.empty(len(ix), dtype=float)
        for c in sorted(set(self.contests[ix].tolist())):
            mask = self.contests[ix] == c
            out[mask] = rankdata(values[mask], method="average")
        return out

    def metrics(self, ix=None, detail=False):
        ix = np.arange(self.n) if ix is None else ix
        xmat = self.design(ix)
        q, rank = basis(xmat)
        info = dict(n=len(ix), rank_X=rank, residual_df=len(ix) - rank, status="ok")
        if len(ix) < 80 or len(ix) - rank < 40:
            info["status"] = "n_below_80" if len(ix) < 80 else "residual_df_below_40"
            return {}, info
        xrank = rankdata(self.x[ix], method="average")
        xr = residual(xrank, q)
        # Suppress only numerical projection remnants of exactly explained ranks.
        if np.linalg.norm(xr) <= 1e-10*max(1., np.linalg.norm(xrank)):
            info["status"] = "zero_explanatory_residual_variance"
            return {}, info
        vals = {}
        for key in self.model["ys"]:
            yrank = self.response_rank(key, ix)
            yr = residual(yrank, q)
            vals[f"rho_{key}"] = (None if np.linalg.norm(yr) <= 1e-10*max(1., np.linalg.norm(yrank))
                                  else correlation(xr, yr))
        if "H" in self.model["ys"]:
            vals["rho_D_minus_H"] = vals["rho_D"] - vals["rho_H"] if vals["rho_D"] is not None and vals["rho_H"] is not None else None
        if self.model.get("cost"):
            for key in ("nfev", "sec"):
                cov = float(np.sum(self.recorded[key][ix])/np.sum(self.planned[ix]))
                info[f"{key}_planned_coverage"] = cov
                val = self.cost[key][ix]
                ok = cov >= .9 and np.isfinite(val).all()
                vals[f"rho_{key}"] = correlation(xr, residual(rankdata(val, method="average"), q)) if ok else None
        if self.model.get("group"):
            lo, hi = np.quantile(xr, [1/3, 2/3], method="linear")
            lower, upper = xr <= lo, xr >= hi
            info.update(lower_n=int(sum(lower)), upper_n=int(sum(upper)), cut_lower=float(lo), cut_upper=float(hi))
            info["group_status"] = "ok"
            if lo == hi:
                info["group_status"] = "equal_tertile_boundaries"
            elif sum(lower) < 20 or sum(upper) < 20:
                info["group_status"] = "group_n_below_20"
            keep = lower | upper
            if info["group_status"] == "ok":
                group = upper[keep].astype(float)
                xgroup = xmat[keep]
                qg, rg = basis(xgroup)
                _, aug_rank = basis(np.column_stack([xgroup, group]))
                gr = residual(group, qg)
                if aug_rank != rg + 1 or np.linalg.norm(gr) <= 1e-10*max(1., np.linalg.norm(group)):
                    info["group_status"] = "group_coefficient_not_identifiable"
                else:
                    # FWL coefficient for original, unranked p on group + the same X.
                    vals["p_diff"] = float((gr @ self.p[ix][keep])/(gr @ gr))
                    if self.model.get("cost"):
                        val = self.cost["nfev"][ix]
                        group_cov = float(np.sum(self.recorded["nfev"][ix][keep])/np.sum(self.planned[ix][keep]))
                        info["nfev_extremes_planned_coverage"] = group_cov
                        if info["nfev_planned_coverage"] >= .9 and group_cov >= .9 and np.isfinite(val).all():
                            coef = float((gr @ np.log1p(val[keep]))/(gr @ gr))
                            vals["nfev_ratio"] = float(np.exp(coef)) if coef < 700 else None
                        else:
                            vals["nfev_ratio"] = None
            if detail and info["group_status"] == "ok":
                info["lower_ids"] = [self.ids[ix[j]] for j in np.where(lower)[0]]
                info["upper_ids"] = [self.ids[ix[j]] for j in np.where(upper)[0]]
        return vals, info

    def signature(self):
        # Cache only genuinely identical numeric analyses (including ID order/costs).
        obj = dict(model=self.model, ids=self.ids, continuous=self.continuous.tolist(),
                   categories={k: v.tolist() for k, v in self.categories.items()}, x=self.x.tolist(),
                   y={k: v.tolist() for k, v in self.y.items()}, p=self.p.tolist(),
                   cost={k: v.tolist() for k, v in self.cost.items()},
                   recorded={k: v.tolist() for k, v in self.recorded.items()}, planned=self.planned.tolist())
        return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def bootstrap(dataset, point):
    if not point:
        return {}
    rng = np.random.default_rng(424200)
    samples = {k: [] for k in point}
    for _ in range(BOOTSTRAPS):
        ix = np.concatenate([rng.choice(s, size=len(s), replace=True) for s in dataset.strata])
        vals, _ = dataset.metrics(ix)
        for key in point:
            value = vals.get(key)
            if value is not None and math.isfinite(value):
                samples[key].append(value)
    out = {}
    for key, values in samples.items():
        invalid = BOOTSTRAPS - len(values)
        ok = point[key] is not None and invalid <= .05*BOOTSTRAPS
        out[key] = dict(value=point[key], ci95=np.quantile(values, [.025, .975], method="linear").tolist() if ok else None,
                        bootstrap_valid=len(values), bootstrap_invalid=invalid,
                        interval_status="ok" if ok else ("point_unavailable" if point[key] is None else "invalid_bootstraps_over_5_percent"))
    return out


def freedman_lane(dataset, response, sign):
    values, info = dataset.metrics()
    observed = values.get(f"rho_{response}")
    if observed is None:
        return dict(p_one_sided=None, status=info["status"], movable_n=0)
    ix = np.arange(dataset.n)
    xmat = dataset.design(ix)
    q, _ = basis(xmat)
    xr = residual(rankdata(dataset.x, method="average"), q)
    yrank = dataset.response_rank(response, ix)
    fitted = q @ (q.T @ yrank)
    yr = yrank - fitted
    groups = {}
    for j, r in enumerate(dataset.rows):
        groups.setdefault((r["contest"], r["n_vars"]), []).append(j)
    movable = sum(len(g) for g in groups.values() if len(g) >= 2)
    if movable < 40:
        return dict(p_one_sided=None, status="movable_n_below_40", movable_n=movable)
    rng = np.random.default_rng(424201)
    ge = 0
    invalid = 0
    groups = [np.array(groups[g]) for g in sorted(groups)]
    for _ in range(PERMUTATIONS):
        shuffled = np.empty(dataset.n)
        for group in groups:
            shuffled[group] = yr[rng.permutation(group)]
        # Deliberately no re-ranking of fitted + permuted residuals.
        test = correlation(xr, residual(fitted + shuffled, q))
        if test is None:
            invalid += 1
        elif sign*test >= sign*observed:
            ge += 1
    return dict(p_one_sided=(ge + 1)/(PERMUTATIONS + 1) if invalid == 0 else None,
                status="ok" if invalid == 0 else "invalid_permutation", movable_n=movable,
                permutations=PERMUTATIONS, invalid_permutations=invalid, tail_count=ge,
                seed=424201, direction="positive" if sign == 1 else "negative")


def cohort(rows, kind, population_ids):
    required = {"P1": ("S", "G"), "P2": ("S", "p"), "P34": ("S", "G", "p", "H")}[kind]
    eligible, reasons = [], Counter()
    reasons["scenario_filter"] = len(population_ids) - len(rows)
    for r in rows:
        if not r["X_complete"]:
            reasons["required_confound_missing"] += 1
            continue
        missing = next((k for k in required if not finite(r.get(k))), None)
        if missing:
            detail = r.get({"S": "S_reason0", "G": "G_reason", "p": "p_reason0", "H": "H_reason"}[missing], "missing")
            reasons[f"{missing}:{detail}"] += 1
        else:
            eligible.append(r)
    return eligible, {k: v for k, v in reasons.items() if v}


def analyze_scenario(name, rows, population_ids, permutation=False):
    result = dict(name=name, models={})
    datasets = {}
    for kind, spec in MODELS.items():
        rr, reasons = cohort(rows, kind, population_ids)
        data = Dataset(rr, spec)
        datasets[kind] = data
        key = data.signature()
        if key not in CACHE:
            point, info = data.metrics(detail=True)
            estimates = bootstrap(data, point)
            CACHE[key] = dict(info=info, estimates=estimates)
        core = CACHE[key]
        entry = dict(**core, used_n=len(rr), used_out_of_323=f"{len(rr)}/323", excluded_n=323-len(rr),
                     excluded_out_of_323=f"{323-len(rr)}/323", exclusion_reasons=reasons,
                     contests=dict(Counter(r["contest"] for r in rr)), ids=[r["id"] for r in rr])
        if permutation:
            entry["direction_tests"] = {y: freedman_lane(data, y, -1 if y == "H" else 1) for y in spec["ys"]}
        result["models"][kind] = entry
    print(json.dumps({"scenario": name, "models": {k: dict(n=v["used_n"], status=v["info"]["status"],
          estimates={a: b["value"] for a, b in v["estimates"].items()}) for k, v in result["models"].items()}}), flush=True)
    return result


def holm(main):
    names = [("P1", "S"), ("P2", "D"), ("P34", "D"), ("P34", "H")]
    tests = [main["models"][m]["direction_tests"][y] for m, y in names]
    # Keep the preregistered family of four, even when tests are unavailable.
    p = np.array([t["p_one_sided"] if t["p_one_sided"] is not None else 1. for t in tests])
    order = np.argsort(p, kind="stable")
    adjusted = np.maximum.accumulate((4 - np.arange(4))*p[order]).clip(max=1)
    for idx, val in zip(order, adjusted):
        tests[idx]["p_holm_4"] = float(val) if tests[idx]["p_one_sided"] is not None else None
        tests[idx]["holm_unavailable_slots"] = "conservative p=1 placeholders; not reported as performed tests"


def verdict(main):
    out = {}
    definitions = {
        "P1": ("P1", "S", [("rho_S", ">=", .20)]),
        "P2": ("P2", "D", [("rho_D", ">=", .20), ("p_diff", "<=", -.10)]),
        "P3": ("P34", "D", [("rho_D", ">=", .20), ("p_diff", "<=", -.10)]),
        "P4": ("P34", "H", [("rho_H", "<=", -.20), ("rho_D_minus_H", ">=", .40)]),
    }
    for name, (group, response, rules) in definitions.items():
        result = main["models"][group]
        if result["info"]["status"] != "ok":
            out[name] = dict(status="判定不可", n=result["used_n"], reason=result["info"]["status"])
            continue
        all_met, refuted, available = True, [], True
        for key, direction, threshold in rules:
            metric = result["estimates"].get(key, {})
            value, ci = metric.get("value"), metric.get("ci95")
            if value is None or ci is None:
                available = False
                all_met = False
                continue
            all_met &= value >= threshold if direction == ">=" else value <= threshold
            if (direction == ">=" and ci[1] < threshold) or (direction == "<=" and ci[0] > threshold):
                refuted.append(key)
        pval = result["direction_tests"][response].get("p_holm_4")
        status = ("数値つき予言を反証" if refuted else "判定不可" if not available or pval is None
                  else "支持候補" if all_met and pval < .05 else "未支持・未決着")
        rho = result["estimates"].get(f"rho_{response}", {}).get("value")
        sign = -1 if response == "H" else 1
        out[name] = dict(status=status, n=result["used_n"], refuted_metrics=refuted,
                         point_direction_reversed=rho is not None and sign*rho < 0)
    out["P5"] = dict(status="未検証", n=0, reason="No refinement-only time or iteration records in fixed inputs")
    ratio = main["models"]["P2"]["estimates"].get("nfev_ratio", {})
    ci = ratio.get("ci95")
    out["local_nfev_auxiliary"] = dict(status="判定不可" if not ci else "数値つき予言を反証" if ci[1] < 1.5
                                     else "点推定基準達成（補助）" if ratio["value"] >= 1.5 else "未支持・未決着",
                                     n=main["models"]["P2"]["used_n"])
    return out


def main():
    rows, audit = build()
    if audit["errors"]:
        raise SystemExit("Input inconsistency; analysis held")
    population = {r["id"] for r in rows}
    started = datetime.now(timezone.utc).isoformat()
    result = analyze_scenario("main", rows, population, permutation=True)
    holm(result)
    write_json("primary-results.json", dict(main=result, verdicts=verdict(result)))
    scenarios = []

    def run(name, changed):
        scenarios.append(analyze_scenario(name, changed, population))
        write_json("sensitivity-results.json", scenarios)

    paired = [r for r in rows if finite(r.get("p0")) and finite(r.get("p1"))]
    run("seed0_common_ids", paired)
    run("seed1_p_fixed_seed0_G_S", [dict(r, p=r["p1"]) for r in paired])
    for tol in ("1e-08", "1e-06"):
        run("geometry_hidden_" + tol, [dict(r, G=r.get(f"G_hidden_{tol}")) for r in rows])
    run("geometry_raw_1e-07", [dict(r, G=r.get("G_raw_1e-07")) for r in rows])
    run("p_completed", [dict(r, p=r.get("p_completed0")) for r in rows])
    run("p_existing_basins", [dict(r, p=r.get("p_basins")) for r in rows])
    for label, field in (("S_raw_sigma_min", "S_raw0"), ("S_min_branch", "S_branch_min0"), ("S_max_branch", "S_branch_max0")):
        run(label, [dict(r, S=r.get(field) if r.get("S") is not None else None) for r in rows])
    run("S_exclude_all_zero_J", [r for r in rows if not r.get("any_zero_J0", False)])
    run("S_all_references_saved", [r for r in rows if r.get("all_refs_saved0", False)])
    # Definition sensitivity, not a replacement for missing primary seed0 S.
    run("S_seed1_saved", [dict(r, S=r.get("S1"), S_reason0=r.get("S_reason1")) for r in rows])
    for c in sorted({r["contest"] for r in rows}):
        run("contest_" + c, [r for r in rows if r["contest"] == c])
    for year in sorted({r["year"] for r in rows}):
        run(f"leave_year_{year}_out", [r for r in rows if r["year"] != year])
    missing_info = []
    for s_fill in (0., 12.):
        for g_fill in (0., math.log(1001)):
            eligible = [r for r in rows if r["known_dimension_eligible"] and r["X_complete"] and finite(r.get("p"))]
            name = f"missing_S_{int(s_fill)}_G_{'0' if g_fill == 0 else 'log1001'}"
            missing_info.append(dict(scenario=name, eligible_n=len(eligible), eligible_out_of_323=f"{len(eligible)}/323",
                                     imputed_S_n=sum(r["S"] is None for r in eligible),
                                     imputed_G_n=sum(r["G"] is None for r in eligible),
                                     missing_m_not_imputed_n=sum(r.get("S_reason0") == "no_first_hit_m_unknown" for r in rows)))
            run(name, [dict(r, S=s_fill if r["S"] is None else r["S"], G=g_fill if r["G"] is None else r["G"]) for r in eligible])
    for tol in TOLS:
        for kind in ("right_angle", "tangent_hidden", "tangent_raw"):
            run(f"aux_{kind}_{tol}", [dict(r, G=r.get(f"{kind}_{tol}")) for r in rows])
    metadata = dict(started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                    numpy=np.__version__, scipy=scipy.__version__, python=sys.version,
                    bootstraps=BOOTSTRAPS, bootstrap_seed=424200, permutations=PERMUTATIONS, permutation_seed=424201,
                    bootstrap_unit="problem; original n per contest; rank, adjust, and split anew",
                    minimum_n=80, minimum_residual_df=40, minimum_group_n=20, svd_relative_cutoff=1e-10,
                    missing_sensitivity=missing_info, unique_computations=len(CACHE),
                    human_provenance="Existing E/J source-join audit; no new labels or human data imported",
                    source_sha256={p.name: digest(p) for p in (HERE / "stage2_inputs.py", HERE / "analyze_stage2.py")})
    write_json("analysis-run.json", metadata)
    flat = []
    for scenario in [result] + scenarios:
        for model, entry in scenario["models"].items():
            base = dict(scenario=scenario["name"], model=model, n=entry["used_n"], n_over_323=entry["used_out_of_323"],
                        excluded_n=entry["excluded_n"], excluded_over_323=entry["excluded_out_of_323"],
                        reasons=json.dumps(entry["exclusion_reasons"], ensure_ascii=False),
                        status=entry["info"]["status"], rank_X=entry["info"]["rank_X"], residual_df=entry["info"]["residual_df"])
            if not entry["estimates"]:
                flat.append(base)
            for key, estimate in entry["estimates"].items():
                flat.append(dict(base, metric=key, value=estimate["value"],
                                 ci_low=estimate["ci95"][0] if estimate["ci95"] else None,
                                 ci_high=estimate["ci95"][1] if estimate["ci95"] else None,
                                 bootstrap_valid=estimate["bootstrap_valid"], bootstrap_invalid=estimate["bootstrap_invalid"],
                                 interval_status=estimate["interval_status"]))
    write_csv("estimates.csv", flat)
    print(json.dumps(verdict(result), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
