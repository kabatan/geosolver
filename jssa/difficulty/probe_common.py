"""Same-start, same-region comparison of three coordinate systems for one problem.

E: the original DSL (constructed points eliminated), variables u.
Y: k constructions rewritten as free points y with y = h(u) (expand_k), started at y = h(u0).
Z: the same constructions written as y = h(u) + z with z = 0 (expand_z), started at z = 0.

Every start k uses the same base point u0 (drawn from E's box with a per-start RNG), so the
three systems start from the same figure. The local solve is the solver's own LM / Powell call
with no box; each endpoint is then classified with one common region: base variables in E's box
and the physical position of each rewritten point inside Y's box for that point.

Usage: probe_common.py CASE OUT.json --e E.json --y Y.json --z Z.json [--starts 100] [--seed 0]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares, minimize

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_basins import ANS_RTOL, RES_TOL, answer_float, construction_coordinates, load_case, reference_values  # noqa: E402

WIDE = 1e12


def build(path):
    dsl = json.loads(Path(path).read_text())
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    return dsl, bundle, build_ir_evaluator(bundle)


def local_solve(bundle, evaluator, start, config, telemetry, k):
    n = len(bundle.var_names)
    m = len(bundle.spec.constraints)
    bounds = [(-WIDE, WIDE)] * n
    vector_fn = smb._AugmentedResidualVectorFn(
        bundle=bundle, evaluator=evaluator, n_constraints=m,
        deadline_monotonic=None, telemetry=telemetry, constraint_scales=None,
    )
    status = None
    try:
        if n > m:
            res = minimize(smb._ResidualObjectiveFn(vector_fn=vector_fn), start, method="Powell",
                           options={"maxiter": smb._UNDERDETERMINED_POWELL_MAXITER, "ftol": 1e-16})
            status = "powell_cap" if res.status == 2 else "powell"
        else:
            res = least_squares(vector_fn, start, method="lm", max_nfev=smb._LM_MAX_NFEV,
                                ftol=1e-14, xtol=1e-14, gtol=1e-14)
            status = "cap" if res.status == 0 else "conv"
    except Exception as error:  # noqa: BLE001
        return None, f"exception:{type(error).__name__}"
    cand = smb._build_candidate(evaluator=evaluator, config=config, bounds=bounds,
                                values=np.array(res.x, dtype=float), origin_seed=0, family_code=smb._LM_FAMILY_CODE,
                                origin_start_point_index=k, telemetry=telemetry)
    return cand, status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("out")
    ap.add_argument("--e", required=True)
    ap.add_argument("--y", required=True)
    ap.add_argument("--z", required=True)
    ap.add_argument("--starts", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=1500.0, help="stop starting new rows after this many seconds")
    ap.add_argument("--near", type=float, default=None,
                    help="start at u* + near * (box width) * U(-1/2, 1/2), u* = an endpoint where E hits")
    args = ap.parse_args()

    refs = reference_values(load_case(args.case_id)["answer"])
    e_dsl, e_b, e_ev = build(args.e)
    _, y_b, y_ev = build(args.y)
    _, z_b, z_ev = build(args.z)
    base = list(e_b.var_names)
    e_box = np.array(infer_problem_bounds(e_b), dtype=float)
    y_box = dict(zip(y_b.var_names, map(tuple, np.array(infer_problem_bounds(y_b), dtype=float))))
    extra = sorted({v[2:] for v in y_b.var_names if v[:2] in ("x_", "y_") and v not in base})
    assert all(f"ofsx_{p}" in z_b.var_names for p in extra), extra
    hcoord = construction_coordinates(e_dsl, extra)
    config = ExternalPipelineConfig.production_baseline_tier(seed=args.seed, total_time_budget_sec=180.0).search
    telemetry = smb._SearchTelemetry()

    def h_of(u):
        vals = dict(zip(base, u))
        out = {}
        for var, (names, ev) in hcoord.items():
            v = answer_float(ev, [vals[n] for n in names])
            out[var] = v if v is not None and math.isfinite(v) else float("nan")
        return out

    def physical(system, x):
        vals = dict(zip({"E": e_b, "Y": y_b, "Z": z_b}[system].var_names, x))
        u = [vals[n] for n in base]
        if system == "Y":
            pts = {f"{a}_{p}": vals[f"{a}_{p}"] for p in extra for a in "xy"}
        else:
            h = h_of(u)
            pts = {f"{a}_{p}": h[f"{a}_{p}"] + (vals[f"ofs{a}_{p}"] if system == "Z" else 0.0) for p in extra for a in "xy"}
        return u, pts

    def in_region(u, pts):
        if not all(lo <= v <= hi for v, (lo, hi) in zip(u, e_box)):
            return False
        return all(math.isfinite(v) and y_box[n][0] <= v <= y_box[n][1] for n, v in pts.items())

    systems = {"E": (e_b, e_ev), "Y": (y_b, y_ev), "Z": (z_b, z_ev)}
    rows = []
    t_start = time.monotonic()
    u_star = None
    if args.near is not None:
        rng = np.random.default_rng([args.seed, 10**6])
        for _ in range(400):
            u0 = e_box[:, 0] + rng.random(len(base)) * (e_box[:, 1] - e_box[:, 0])
            cand, _ = local_solve(e_b, e_ev, u0, config, telemetry, 0)
            if cand is None or not math.isfinite(cand.residual_norm_float) or cand.residual_norm_float > RES_TOL:
                continue
            if not (bool(cand.guard_ok) and cand.hard_feasible is not False):
                continue
            value = answer_float(e_ev, cand.x_float)
            if value is not None and any(abs(value - r) <= ANS_RTOL * max(1.0, abs(r)) for r in refs) \
                    and in_region(list(cand.x_float), h_of(list(cand.x_float))):
                u_star = np.array(cand.x_float, dtype=float)
                break
        if u_star is None:
            Path(args.out).write_text(json.dumps({"case_id": args.case_id, "near": args.near, "no_u_star": True}))
            return
    for k in range(args.starts):
        if time.monotonic() - t_start > args.budget:
            break
        rng = np.random.default_rng([args.seed, k])
        u0 = e_box[:, 0] + rng.random(len(base)) * (e_box[:, 1] - e_box[:, 0])
        if u_star is not None:
            u0 = u_star + args.near * (e_box[:, 1] - e_box[:, 0]) * (rng.random(len(base)) - 0.5)
        h0 = h_of(u0)
        if not all(math.isfinite(v) for v in h0.values()):
            rows.append({"k": k, "start_undefined": True})
            continue
        u0d = dict(zip(base, u0))
        row = {"k": k, "start_in_region": in_region(list(u0), h0)}
        for s, (b, ev) in systems.items():
            start = []
            for n in b.var_names:
                if n in u0d:
                    start.append(u0d[n])
                elif n.startswith("ofs"):
                    start.append(0.0)
                else:
                    start.append(h0[n])
            t0 = time.monotonic()
            n0 = telemetry.evaluation_count
            cand, status = local_solve(b, ev, np.array(start, dtype=float), config, telemetry, k)
            rec = {"sec": time.monotonic() - t0, "nfev": telemetry.evaluation_count - n0, "stop": status}
            if cand is None or not math.isfinite(cand.residual_norm_float):
                rec["cls"] = "undefined"
            else:
                u, pts = physical(s, cand.x_float)
                rec["region"] = in_region(u, pts)
                rec["res"] = cand.residual_norm_float
                if not rec["region"]:
                    rec["cls"] = "left_region"
                elif cand.residual_norm_float > RES_TOL:
                    rec["cls"] = "stuck_cap" if status in ("cap", "powell_cap") else "stuck"
                elif not (bool(cand.guard_ok) and cand.hard_feasible is not False):
                    rec["cls"] = "wrong_branch"
                else:
                    value = answer_float(ev, cand.x_float)
                    ok = value is not None and any(abs(value - r) <= ANS_RTOL * max(1.0, abs(r)) for r in refs)
                    rec["cls"] = "hit" if ok else "wrong_answer"
            row[s] = rec
        rows.append(row)
    summary = {}
    done = [r for r in rows if "E" in r]
    for s in systems:
        c = {}
        for r in done:
            c[r[s]["cls"]] = c.get(r[s]["cls"], 0) + 1
        summary[s] = {"counts": c, "p": c.get("hit", 0) / max(1, len(done)),
                      "sec_median": float(np.median([r[s]["sec"] for r in done])) if done else None}
    out = {"case_id": args.case_id, "near": args.near, "u_star": None if u_star is None else list(u_star), "extra": extra, "n_base": len(base), "starts": len(done),
           "start_undefined": len(rows) - len(done), "elapsed": time.monotonic() - t_start,
           "summary": summary, "rows": rows}
    Path(args.out).write_text(json.dumps(out))
    print(args.case_id, {s: round(v["p"], 3) for s, v in summary.items()}, "elapsed=%.0f" % out["elapsed"])


if __name__ == "__main__":
    sys.exit(main())
