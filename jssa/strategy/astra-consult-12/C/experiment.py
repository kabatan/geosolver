"""Reproducible astra-C diagnostics and paired local experiments. All writes stay here."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))
from expand_k import eligible, expand
from expand_z import expand_offset
from probe_basins import ANS_RTOL, RES_TOL, answer_float, construction_coordinates, load_case, reference_values
from probe_common import build, local_solve, infer_problem_bounds, ExternalPipelineConfig, smb, WIDE

DSL = ROOT / "jssa/difficulty/holdout-1023/dsl"
OLD = ROOT / "jssa/difficulty/holdout-1023/out"


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, np.ndarray)):
        return [clean(x) for x in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def save(name, value):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(value), ensure_ascii=False, indent=1) + "\n")


def save_csv(name, rows):
    if not rows:
        return
    with (HERE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(clean(rows))


def jac(fn, x):
    x = np.asarray(x, dtype=float)
    cols = []
    for i in range(len(x)):
        h = 1e-5 * max(1.0, abs(x[i]))
        v = np.zeros_like(x)
        v[i] = h
        cols.append((np.asarray(fn(x + v)) - np.asarray(fn(x - v))) / (2 * h))
    return np.column_stack(cols)


def eq(ev, x):
    return np.array(ev.evaluate_float_residual(list(x)).residual_vector, dtype=float)


class Case:
    def __init__(self, cid):
        self.cid = cid
        self.e, self.eb, self.ee = build(DSL / f"{cid}.k0.json")
        self.y, self.yb, self.ye = build(DSL / f"{cid}.k2.json")
        self.base = list(self.eb.var_names)
        self.extra = sorted({n[2:] for n in self.yb.var_names if n[:2] in ("x_", "y_") and n not in self.base})
        self.hvars = [f"{a}_{p}" for p in self.extra for a in "xy"]
        self.hc = construction_coordinates(self.e, self.extra)
        self.box = np.array(infer_problem_bounds(self.eb), dtype=float)
        self.width = self.box[:, 1] - self.box[:, 0]
        self.ybox = dict(zip(self.yb.var_names, infer_problem_bounds(self.yb)))
        self.me = len(self.eb.spec.constraints)
        # Incidence lowering can append original rows after newly added rows.
        # Match compiled residual labels as a multiset; do not assume a prefix.
        remaining = list(range(len(self.yb.spec.constraints)))
        self.original_rows = []
        for expr in self.eb.spec.constraints:
            ix = next(i for i in remaining if self.yb.spec.constraints[i] == expr)
            self.original_rows.append(ix)
            remaining.remove(ix)
        self.new_rows = remaining
        # Lowering may also introduce an incidence row that vanished identically in E.
        assert len(self.new_rows) >= 4, (cid, self.new_rows)
        self.refs = reference_values(load_case(cid)["answer"])

    def h(self, u):
        values = dict(zip(self.base, u))
        out = []
        for v in self.hvars:
            names, ev = self.hc[v]
            value = answer_float(ev, [values[n] for n in names])
            out.append(float("nan") if value is None else value)
        return np.array(out, dtype=float)

    def ypoint(self, u, h):
        values = dict(zip(self.base, u)) | dict(zip(self.hvars, h))
        return np.array([values[n] for n in self.yb.var_names], dtype=float)

    def region(self, u, h):
        return bool(np.all(u >= self.box[:, 0]) and np.all(u <= self.box[:, 1]) and
                    all(math.isfinite(v) and self.ybox[n][0] <= v <= self.ybox[n][1]
                        for n, v in zip(self.hvars, h)))


def features(case_ids=None):
    start = time.monotonic()
    results = [] if not case_ids else [r for r in json.loads((HERE / "features.json").read_text()) if r["case_id"] not in case_ids]
    for path in sorted(DSL.glob("*.k0.json")):
        cid = path.name[:-8]
        if case_ids and cid not in case_ids:
            continue
        try:
            c = Case(cid)
            rows = []
            for k in range(16):
                rng = np.random.default_rng([102300, k])
                u = c.box[:, 0] + rng.random(len(c.base)) * c.width
                try:
                    h = c.h(u)
                    H = jac(c.h, u)
                    f = eq(c.ee, u)
                    J = jac(lambda x: eq(c.ee, x), u)
                    y = c.ypoint(u, h)
                    JY = jac(lambda x: eq(c.ye, x), y)
                    if not all(np.all(np.isfinite(x)) for x in [h, H, f, J, JY]):
                        raise ValueError("nonfinite")
                    de = np.maximum(np.linalg.norm(J, axis=0), 1e-12)
                    du = np.linalg.lstsq(J / de, -f, rcond=1e-10)[0] / de
                    dy = c.ypoint(du, H @ du)
                    sy = np.linalg.norm(JY, axis=0)
                    base_ix = [list(c.yb.var_names).index(n) for n in c.base]
                    inf = np.median(sy[base_ix] / de)
                    ratio = np.linalg.norm(sy * dy) / max(np.linalg.norm(de * du), 1e-12)
                    dn = np.linalg.norm(du / c.width)
                    alpha = min(1.0, 0.25 / max(dn, 1e-12))
                    ft = eq(c.ye, c.ypoint(u + alpha * du, h + alpha * (H @ du)))
                    if not np.all(np.isfinite(ft)):
                        raise ValueError("nonfinite tangent trial")
                    defect = np.linalg.norm(ft[c.new_rows]) / max(np.linalg.norm(f), 1e-12)
                    expected = np.zeros(len(ft))
                    expected[c.original_rows] = J @ du
                    rows.append(dict(k=k, escape=bool(np.any(u + du < c.box[:, 0]) or np.any(u + du > c.box[:, 1])),
                                     metric=float(ratio), defect=float(defect), inflation=float(inf),
                                     step_box=float(dn), initial_res=float(np.linalg.norm(f)),
                                     tangent_error=float(np.linalg.norm(JY @ dy - expected) /
                                                         max(np.linalg.norm(J @ du), 1e-12))))
                except Exception as exc:
                    rows.append(dict(k=k, error=type(exc).__name__))
            valid = [r for r in rows if "escape" in r]
            vals = dict(case_id=cid, n_vars=len(c.base), picks=" ".join(c.extra), n_valid=len(valid))
            for field in ["escape", "metric", "defect", "inflation", "step_box", "initial_res", "tangent_error"]:
                vals[field] = float(np.mean([r[field] for r in valid])) if field == "escape" else float(np.median([r[field] for r in valid]))
            vals["rule_R"] = bool(vals["escape"] >= .5 and vals["metric"] >= 2 and vals["defect"] <= .1)
            results.append(vals)
            save(f"diagnostics/{cid}.json", dict(features=vals, starts=rows))
            print(json.dumps(clean(vals)), flush=True)
        except Exception as exc:
            print(cid, "FAILED", repr(exc), flush=True)
    save_csv("features.csv", results)
    save("features.json", results)
    save("diagnostics_meta.json", dict(elapsed_this_invocation=time.monotonic()-start, total_cases_in_file=len(results),
         cases_this_invocation=case_ids or [r["case_id"] for r in results], numpy=np.__version__, scipy=scipy.__version__))


def make_variants(cid):
    c = Case(cid)
    picks = eligible(c.e)
    z = expand_offset(c.e, 2, picks)
    newrows = c.y["conditions"][len(c.e["conditions"]):]
    zg = copy.deepcopy(z)
    zg["conditions"] = copy.deepcopy(c.e["conditions"]) + copy.deepcopy(newrows)
    zg["id"] += ".zg"
    save(f"dsl/{cid}.z2.json", z)
    save(f"dsl/{cid}.zg2.json", zg)
    if cid == "AIME-2020-II-15":
        yn = copy.deepcopy(c.y)
        for idx, row in enumerate(yn["conditions"][len(c.e["conditions"]):]):
            row["left"] = f"({row['left']}) / Distance(A, {'B' if idx < 2 else 'C'})"
        yn["id"] += ".norm"
        save(f"dsl/{cid}.ynorm.json", yn)
    return c


def run(cid, systems, n, seed, tag, boxfactor=1.0):
    c = make_variants(cid)
    built = {"E": (c.eb, c.ee), "Y": (c.yb, c.ye)}
    for s in systems:
        if s == "Eunit":
            built[s] = (c.eb, c.ee)
        elif s in ("Z", "ZG", "Ynorm"):
            suffix = {"Z": "z2", "ZG": "zg2", "Ynorm": "ynorm"}[s]
            _, b, ev = build(HERE / f"dsl/{cid}.{suffix}.json")
            built[s] = (b, ev)
    config = ExternalPipelineConfig.production_baseline_tier(seed=seed, total_time_budget_sec=180).search
    allrows = []
    start_time = time.monotonic()
    for k in range(n):
        rng = np.random.default_rng([seed, k])
        # Scaling around 0 preserves the positive lower bound in this case.
        u0 = (c.box[:, 0] + rng.random(len(c.base)) * c.width) * boxfactor
        h0 = c.h(u0)
        row = dict(k=k, u0=u0.tolist(), start_in_region=c.region(u0, h0))
        if not np.all(np.isfinite(h0)):
            row["start_undefined"] = True
            allrows.append(row)
            continue
        for s in systems:
            b, ev = built[s]
            values = dict(zip(c.base, u0)) | dict(zip(c.hvars, h0))
            x0 = np.array([0.0 if name.startswith("ofs") else values[name] for name in b.var_names])
            tel = smb._SearchTelemetry()
            t0 = time.monotonic()
            if s == "Eunit":
                fn = smb._AugmentedResidualVectorFn(bundle=b, evaluator=ev, n_constraints=len(b.spec.constraints),
                                                    deadline_monotonic=None, telemetry=tel, constraint_scales=None)
                try:
                    res = least_squares(fn, x0, method="lm", max_nfev=smb._LM_MAX_NFEV,
                                        ftol=1e-14, xtol=1e-14, gtol=1e-14, x_scale=1.0)
                    status = "cap" if res.status == 0 else "conv"
                    cand = smb._build_candidate(evaluator=ev, config=config, bounds=[(-WIDE,WIDE)]*len(x0),
                                               values=res.x, origin_seed=seed, family_code=smb._LM_FAMILY_CODE,
                                               origin_start_point_index=k, telemetry=tel)
                except Exception as exc:
                    cand, status = None, f"exception:{type(exc).__name__}"
            else:
                cand, status = local_solve(b, ev, x0, config, tel, k)
            rec = dict(sec=time.monotonic()-t0, nfev=tel.evaluation_count, stop=status)
            if cand is None or not math.isfinite(cand.residual_norm_float):
                rec["cls"] = "undefined"
            else:
                v = dict(zip(b.var_names, cand.x_float))
                u = np.array([v[name] for name in c.base])
                if s.startswith("Y"):
                    h = np.array([v[name] for name in c.hvars])
                else:
                    h = c.h(u)
                    if s in ("Z", "ZG"):
                        h = h + np.array([v["ofs" + name] for name in c.hvars])
                rec.update(x=list(cand.x_float), u=u.tolist(), h=h.tolist(), res=cand.residual_norm_float,
                           region=c.region(u,h), guard_ok=bool(cand.guard_ok), hard_feasible=cand.hard_feasible)
                if not rec["region"]:
                    rec["cls"] = "left_region"
                elif rec["res"] > RES_TOL:
                    rec["cls"] = "stuck_cap" if status in ("cap", "powell_cap") else "stuck"
                elif not (rec["guard_ok"] and cand.hard_feasible is not False):
                    rec["cls"] = "wrong_branch"
                else:
                    value = answer_float(ev, cand.x_float)
                    rec["answer"] = value
                    rec["cls"] = "hit" if value is not None and any(abs(value-r) <= ANS_RTOL*max(1,abs(r)) for r in c.refs) else "wrong_answer"
            row[s] = rec
        allrows.append(row)
        if (k+1) % 10 == 0 or k+1 == n:
            print(cid, tag, k+1, {s:sum(r.get(s,{}).get("cls")=="hit" for r in allrows) for s in systems}, flush=True)
            save(f"runs/{cid}.{tag}.json", dict(case_id=cid, systems=systems, seed=seed, requested=n,
                 completed=k+1, boxfactor=boxfactor, elapsed=time.monotonic()-start_time,
                 base=c.base, extra=c.extra, box=c.box, rows=allrows, numpy=np.__version__, scipy=scipy.__version__))


def paired(rows, a, b):
    rows = [r for r in rows if a in r and b in r]
    av = np.array([r[a]["cls"]=="hit" for r in rows], dtype=int)
    bv = np.array([r[b]["cls"]=="hit" for r in rows], dtype=int)
    diff = bv-av
    n = len(diff)
    gain, loss = int(np.sum(diff==1)), int(np.sum(diff==-1))
    rng = np.random.default_rng(102302)
    boot = diff[rng.integers(0,n,size=(20000,n))].mean(axis=1) if n else np.array([np.nan])
    return dict(n=n, pA=float(av.mean()), pB=float(bv.mean()), delta=float(diff.mean()),
                B_only=gain, A_only=loss, ci_low=float(np.quantile(boot,.025)), ci_high=float(np.quantile(boot,.975)),
                mcnemar_p=binomtest(gain,gain+loss).pvalue if gain+loss else 1.0)


def summarize():
    table = []
    for path in sorted((HERE / "runs").glob("*.json")):
        d = json.loads(path.read_text())
        systems = d["systems"]
        ref = "E" if "E" in systems else systems[0]
        for s in systems:
            if s == ref: continue
            p = paired(d["rows"],ref,s)
            table.append(dict(file=path.name, case_id=d["case_id"], seed=d["seed"], A=ref, B=s, **p))
    save_csv("paired_results.csv", table)
    save("paired_results.json", table)
    for r in table: print(r, flush=True)
    if (HERE / "features.json").exists():
        scored = []
        for r in json.loads((HERE / "features.json").read_text()):
            path=OLD / f"{r['case_id']}.json"
            if path.exists():
                d=json.loads(path.read_text())
                scored.append(r | paired(d["rows"], "E", "Y"))
        save_csv("retrospective.csv", scored)
        tp=sum(r["rule_R"] and r["delta"] >= .1-1e-12 for r in scored)
        fp=sum(r["rule_R"] and r["delta"] < .1-1e-12 for r in scored)
        fn=sum(not r["rule_R"] and r["delta"] >= .1-1e-12 for r in scored)
        tn=len(scored)-tp-fp-fn
        save("rule_score.json",dict(tp=tp,fp=fp,fn=fn,tn=tn,n=len(scored)))
        print('Rule R retrospective', dict(tp=tp,fp=fp,fn=fn,tn=tn),flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    fp = sub.add_parser("features")
    fp.add_argument("--cases", nargs="+")
    sub.add_parser("summarize")
    p = sub.add_parser("run")
    p.add_argument("case_id")
    p.add_argument("--systems", nargs="+", default=["E","Y"])
    p.add_argument("--starts", type=int, default=60)
    p.add_argument("--seed", type=int, default=102301)
    p.add_argument("--tag", default="fresh")
    p.add_argument("--boxfactor", type=float, default=1.0)
    args = ap.parse_args()
    if args.mode == "features": features(args.cases)
    elif args.mode == "summarize": summarize()
    else: run(args.case_id,args.systems,args.starts,args.seed,args.tag,args.boxfactor)


if __name__ == "__main__":
    main()
