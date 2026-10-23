"""Verify completed Q42 artifacts using saved numbers; never run a solver.

Original results, prediction, and locks are read-only. Only completion-audit.json
is written. Confidence intervals and permutations are checked, not rerun.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def close(actual, expected):
    assert math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-10), (actual, expected)


def independent_p2(rows, p_column="p0"):
    """Separate least-squares implementation of the preregistered point estimates."""
    continuous = ("year", "n_eq", "n_ineq", "n_pts", "n_circ", "construction_depth", "dsl_len", "n_refs")
    categorical = ("n_vars", "contest", "has_angle", "has_tangent")
    cols = [np.ones(len(rows))]
    for key in continuous:
        v = rankdata([float(r[key]) for r in rows], method="average")
        if np.ptp(v):
            cols.append(v)
    for key in categorical:
        values = np.array([r[key] for r in rows])
        for level in sorted(set(values)):
            v = (values == level).astype(float)
            if np.ptp(v):
                cols.append(v)
    x = np.column_stack(cols)

    def resid(v):
        beta, _, rank, _ = np.linalg.lstsq(x, v, rcond=1e-10)
        return v - x @ beta, int(rank)

    sr, rank = resid(rankdata([float(r["S0"]) for r in rows], method="average"))
    p = np.array([float(r[p_column]) for r in rows])
    lo, hi = np.quantile(sr, [1 / 3, 2 / 3], method="linear")
    lower, upper = sr <= lo, sr >= hi
    keep = lower | upper
    group_x = np.column_stack([x[keep], upper[keep].astype(float)])
    p_fit, _, _, _ = np.linalg.lstsq(group_x, p[keep], rcond=1e-10)
    nfev = np.array([float(r["nfev_median0"]) for r in rows])
    nfev_fit, _, _, _ = np.linalg.lstsq(group_x, np.log1p(nfev[keep]), rcond=1e-10)
    values = {"p_diff": float(p_fit[-1]), "nfev_ratio": float(np.exp(nfev_fit[-1]))}
    for key, v in (("D", 1 - p), ("nfev", nfev), ("sec", [float(r["sec_median0"]) for r in rows])):
        yr, _ = resid(rankdata(v, method="average"))
        values["rho_" + key] = float(np.corrcoef(sr, yr)[0, 1])
    return dict(rank_X=rank, lower_n=int(sum(lower)), upper_n=int(sum(upper)), values=values)


def main():
    sealed = subprocess.run([sys.executable, "-B", str(HERE / "seal_prediction.py"), "--verify"],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    run = read_json(HERE / "analysis-run.json")
    for name, expected in run["source_sha256"].items():
        assert sha(HERE / name) == expected, name
    rows = read_csv(HERE / "ledger.csv")
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 323
    basins = read_csv(ROOT / "jssa/difficulty/minima/basins-323.csv")
    assert ids == [r["id"] for r in basins]
    assert all(r["X_complete"] == "True" and not r["X_missing"] for r in rows)
    totals = {}
    for seed, directory in ((0, "raw-323"), (1, "raw-323-seed1")):
        z = str(seed)
        summary = Counter()
        for row, basin in zip(rows, basins):
            raw = read_json(ROOT / "jssa/difficulty/minima" / directory / (row["id"] + ".json"))
            assert raw["case_id"] == row["id"] and raw["seed"] == seed
            assert raw["n_vars"] == int(row["n_vars"])
            if raw["n_vars"] == 0:
                assert row["p" + z] == row["S" + z] == ""
                summary["no_search_problems"] += 1
                continue
            records, planned = raw["records"], raw["starts_requested"]
            hits = sum(r["cls"] == "hit" for r in records)
            assert raw["starts_done"] == len(records) <= planned
            assert len({r["k"] for r in records}) == len(records)
            assert all(0 <= r["k"] < planned for r in records)
            close(row["p" + z], hits / planned)
            close(row["p_completed" + z], hits / len(records))
            if seed == 0:
                close(basin["p"], hits / len(records))
                assert int(basin["n_starts"]) == len(records)
            for field in ("nfev", "sec"):
                values = [float(r[field]) for r in records if r.get(field) is not None
                          and math.isfinite(float(r[field])) and float(r[field]) >= 0]
                close(row[field + "_median" + z], median(values))
                assert int(row[field + "_recorded" + z]) == len(values)
            if row["S" + z]:
                ss = []
                for b in raw["first_hit"].values():
                    n, m, sv = raw["n_vars"], b["n_residuals"], b["svals"]
                    assert n >= 2 and m >= n and len(sv) == min(m, n)
                    assert all(math.isfinite(v) and v >= 0 for v in sv)
                    ss.append(12. if max(sv) == 0 else -math.log10(max(min(sv) / max(sv), 1e-12)))
                close(row["S" + z], median(ss))
            summary.update(search_problems=1, requested=planned, recorded=len(records), hits=hits,
                           non_success=planned - hits, unrecorded=planned - len(records),
                           incomplete_problems=int(len(records) < planned))
            summary.update({"class_" + k: v for k, v in Counter(r["cls"] for r in records).items()})
        totals[z] = dict(summary)
    for r in rows:
        if not r["G"]:
            continue
        q = int(r["measured_points"])
        candidates = dict(equal_length=math.comb(math.comb(q, 2), 2),
                          collinear=math.comb(q, 3), concyclic=math.comb(q, 4))
        for tol in ("1e-08", "1e-07", "1e-06"):
            for prefix in ("hidden", "raw"):
                terms = []
                for kind, count in candidates.items():
                    c = int(r[f"{prefix}_{kind}_{tol}"])
                    assert 0 <= c <= count
                    terms.append(math.log1p(1000 * c / max(1, count)))
                close(r[f"G_{prefix}_{tol}"], sum(terms) / 3)
        close(r["G"], r["G_hidden_1e-07"])
    primary = read_json(HERE / "primary-results.json")
    sensitivities = read_json(HERE / "sensitivity-results.json")
    names = [s["name"] for s in sensitivities]
    expected = ["seed0_common_ids", "seed1_p_fixed_seed0_G_S", "geometry_hidden_1e-08",
                "geometry_hidden_1e-06", "geometry_raw_1e-07", "p_completed", "p_existing_basins",
                "S_raw_sigma_min", "S_min_branch", "S_max_branch", "S_exclude_all_zero_J",
                "S_all_references_saved", "S_seed1_saved"]
    expected += ["contest_" + c for c in sorted({r["contest"] for r in rows})]
    expected += [f"leave_year_{y}_out" for y in sorted({int(r["year"]) for r in rows})]
    expected += [f"missing_S_{s}_G_{g}" for s in (0, 12) for g in ("0", "log1001")]
    expected += [f"aux_{k}_{t}" for t in ("1e-08", "1e-07", "1e-06")
                 for k in ("right_angle", "tangent_hidden", "tangent_raw")]
    assert names == expected and len(names) == 55
    flat = {(r["scenario"], r["model"], r["metric"]): r for r in read_csv(HERE / "estimates.csv")}
    entries, intervals = 0, 0
    for scenario in [primary["main"], *sensitivities]:
        assert set(scenario["models"]) == {"P1", "P2", "P34"}
        for model, result in scenario["models"].items():
            assert result["used_n"] == len(result["ids"]) == len(set(result["ids"]))
            assert set(result["ids"]) <= set(ids)
            assert result["used_n"] + result["excluded_n"] == 323
            assert sum(result["exclusion_reasons"].values()) == result["excluded_n"]
            for metric, estimate in result["estimates"].items():
                assert estimate["bootstrap_valid"] + estimate["bootstrap_invalid"] == 5000
                assert estimate["bootstrap_invalid"] == 0 and estimate["interval_status"] == "ok"
                assert all(math.isfinite(v) for v in estimate["ci95"])
                record = flat[(scenario["name"], model, metric)]
                close(record["value"], estimate["value"])
                close(record["ci_low"], estimate["ci95"][0])
                close(record["ci_high"], estimate["ci95"][1])
                intervals += 1
            entries += max(1, len(result["estimates"]))
    assert entries == len(flat) == 384
    observed = primary["main"]["models"]["P2"]
    selected = [r for r in rows if r["id"] in set(observed["ids"])]
    independent = {}
    paired = next(s for s in sensitivities if s["name"] == "seed1_p_fixed_seed0_G_S")["models"]["P2"]
    assert paired["ids"] == observed["ids"]
    for name, p_column, result in (("main", "p0", observed), ("seed1_p_fixed_seed0_G_S", "p1", paired)):
        point = independent_p2(selected, p_column)
        for key in ("rank_X", "lower_n", "upper_n"):
            assert point[key] == result["info"][key]
        for key, value in point["values"].items():
            close(value, result["estimates"][key]["value"])
        independent[name] = point
    test = observed["direction_tests"]["D"]
    close(test["p_one_sided"], (test["tail_count"] + 1) / (9999 + 1))
    close(test["p_holm_4"], min(1, 4 * test["p_one_sided"]))
    files = ["prediction.md", "prediction.lock.json", "input-manifest.json", "stage2_inputs.py",
             "analyze_stage2.py", "input-audit.json", "analysis-run.json", "ledger.csv", "branches.csv",
             "primary-results.json", "sensitivity-results.json", "estimates.csv"]
    audit = dict(utc=datetime.now(timezone.utc).isoformat(), status="passed",
                 seal_verification_stdout=sealed.stdout.strip(), fixed_input_count=1038,
                 population=323, completed_sensitivity_scenarios=len(sensitivities),
                 checked_estimate_rows=entries, checked_intervals=intervals,
                 new_solver_runs=0, new_searches=0, new_refinements=0, new_jacobian_evaluations=0,
                 bootstrap_or_permutation_reruns=0, raw_arithmetic_totals=totals,
                 independently_recomputed_p2=independent, original_run=run,
                 files_sha256={name: sha(HERE / name) for name in files}, verifier_sha256=sha(Path(__file__)),
                 limits="Read-only hash/consistency audit and independent point estimates; stored resampling intervals adopted without rerun. ps only sees the current sandbox process namespace.")
    (HERE / "completion-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: audit[k] for k in ("status", "population", "completed_sensitivity_scenarios", "checked_estimate_rows", "checked_intervals", "new_solver_runs")}))


if __name__ == "__main__":
    main()
