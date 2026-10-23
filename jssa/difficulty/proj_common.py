"""Projected local search: points fixed by two equations are re-solved inside every evaluation.

The mechanism of section 5.3: when a construction y = h(u) is written as a free point y plus two
equations G(u, y) = 0, a trial step keeps G only to first order, the second-order error q_G pushes
the residual up and the step is cut. If every evaluation first moves y back onto G(u, y) = 0, the
outer search sees R(u, y(u)) = the eliminated system E, so Proposition 1 predicts E's behaviour.

Detection uses only the residual vector (no labels, no DSL text): a point P (variables x_P, y_P)
is taken as dependent with rows i, j when both rows depend on P, the 2x2 Jacobian of (r_i, r_j) in
(x_P, y_P) is well conditioned at sample points, and the dependency graph stays acyclic. Among the
candidates, rows that are affine in P and touch few variables come first. Every evaluation solves
the dependent points in topological order by Newton's method from the last solution.

Usage: proj_common.py CASE OUT.json --e E.json --y Y.json [--starts 40] [--budget 600]
Arms: E, Y as in probe_common.py; PY = projected search on Y; PE = projected search on E.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares, minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_common as pc  # noqa: E402
from probe_common import smb  # noqa: E402
from probe_basins import ANS_RTOL, RES_TOL, answer_float, construction_coordinates, load_case, reference_values  # noqa: E402

PEN = smb._NONFINITE_RESIDUAL_PENALTY
FD = 1.4901161193847656e-08


def _raw(evaluator, values):
    try:
        res = evaluator.evaluate_float_residual(list(values))
        v = np.array(res.residual_vector, dtype=float)
        return v if res.is_finite and np.all(np.isfinite(v)) else None
    except Exception:  # noqa: BLE001
        return None


def detect(bundle, evaluator, box, rng, samples=3):
    """Return [(point, (ix, iy), (row_i, row_j))] in solve order, and a log."""
    names = list(bundle.var_names)
    n = len(names)
    pts = {}
    for k, v in enumerate(names):
        m = re.fullmatch(r"x_(.+)", v)
        if m and f"y_{m.group(1)}" in names:
            pts[m.group(1)] = (k, names.index(f"y_{m.group(1)}"))
    xs, Js, curv = [], [], []
    tries = 0
    while len(xs) < samples and tries < 200:
        tries += 1
        x = box[:, 0] + rng.random(n) * (box[:, 1] - box[:, 0])
        r = _raw(evaluator, x)
        if r is None:
            continue
        J = np.empty((r.size, n))
        C = np.zeros((r.size, n))
        ok = True
        for j in range(n):
            h = 1e-3 * max(1.0, abs(x[j]))
            xp = x.copy(); xp[j] += h
            xm = x.copy(); xm[j] -= h
            rp, rm = _raw(evaluator, xp), _raw(evaluator, xm)
            if rp is None or rm is None:
                ok = False
                break
            J[:, j] = (rp - rm) / (2 * h)
            C[:, j] = np.abs(rp - 2 * r + rm) / h**2 / (1.0 + np.abs(J[:, j]))
        if ok:
            xs.append(x); Js.append(J); curv.append(C)
    if not xs:
        return [], {"error": "no finite sample"}
    S = np.max([np.abs(J) for J in Js], axis=0) > 1e-9
    nonlin = np.max(curv, axis=0) > 1e-4
    m = S.shape[0]
    dep_of = {}
    chosen = []
    used = set()

    def acyclic(extra_p, rows):
        deps = {p: {q for q in pts if q != p and any(S[i, pts[q][0]] or S[i, pts[q][1]] for i in rr)}
                for p, rr in list(dep_of.items()) + [(extra_p, rows)]}
        seen, stack = set(), set()

        def visit(p):
            if p in stack:
                return False
            if p in seen:
                return True
            stack.add(p)
            okv = all(visit(q) for q in deps[p] if q in deps)
            stack.discard(p)
            seen.add(p)
            return okv
        return all(visit(p) for p in deps)

    while True:
        best = None
        for p, (ix, iy) in pts.items():
            if p in dep_of:
                continue
            rows = [i for i in range(m) if i not in used and (S[i, ix] or S[i, iy])]
            for i, j in itertools.combinations(rows, 2):
                conds = []
                for J in Js:
                    B = J[np.ix_([i, j], [ix, iy])]
                    s = np.linalg.svd(B, compute_uv=False)
                    conds.append(s[0] / s[1] if s[1] > 1e-12 else math.inf)
                if max(conds) > 1e8:
                    continue
                lin = int(nonlin[i, ix] or nonlin[i, iy]) + int(nonlin[j, ix] or nonlin[j, iy])
                width = int(S[i].sum() + S[j].sum())
                key = (lin, width, i, j)
                if best is None or key < best[0]:
                    if acyclic(p, (i, j)):
                        best = (key, p, (i, j))
        if best is None:
            break
        _, p, rows = best
        dep_of[p] = rows
        used.update(rows)
        chosen.append(p)
    # topological order
    order, done = [], set()

    def place(p):
        if p in done:
            return
        for q in dep_of:
            if q != p and any(S[i, pts[q][0]] or S[i, pts[q][1]] for i in dep_of[p]):
                place(q)
        done.add(p)
        order.append(p)
    for p in chosen:
        place(p)
    plan = [(p, pts[p], dep_of[p]) for p in order]
    log = {"points": order, "rows": {p: list(map(int, dep_of[p])) for p in order},
           "affine_rows": {p: [not (nonlin[i, pts[p][0]] or nonlin[i, pts[p][1]]) for i in dep_of[p]] for p in order}}
    return plan, log


class Projector:
    def __init__(self, bundle, evaluator, plan):
        self.bundle, self.ev, self.plan = bundle, evaluator, plan
        n = len(bundle.var_names)
        dep = {k for _, ij, _ in plan for k in ij}
        self.free = [k for k in range(n) if k not in dep]
        self.drop = {r for _, _, rows in plan for r in rows}
        self.n = n
        self.last = None
        self.fails = 0

    def full(self, u, y0):
        x = y0.copy()
        x[self.free] = u
        for _, (ix, iy), (ri, rj) in self.plan:
            for _ in range(40):
                r = _raw(self.ev, x)
                if r is None:
                    return None
                g = r[[ri, rj]]
                if np.max(np.abs(g)) < 1e-15 * (1.0 + abs(x[ix]) + abs(x[iy])):
                    break
                B = np.empty((2, 2))
                for c, k in enumerate((ix, iy)):
                    h = FD * max(1.0, abs(x[k]))
                    xp = x.copy(); xp[k] += h
                    rp = _raw(self.ev, xp)
                    if rp is None:
                        return None
                    B[:, c] = (rp[[ri, rj]] - g) / h
                try:
                    d = np.linalg.solve(B, -g)
                except np.linalg.LinAlgError:
                    return None
                if not np.all(np.isfinite(d)):
                    return None
                x[ix] += d[0]; x[iy] += d[1]
                if np.max(np.abs(d)) < 1e-15 * (1.0 + abs(x[ix]) + abs(x[iy])):
                    break
            else:
                return None
            r = _raw(self.ev, x)
            if r is None or np.max(np.abs(r[[ri, rj]])) > 1e-9:
                return None
        return x


def proj_local_solve(bundle, evaluator, start, config, telemetry, k, plan):
    if not plan:
        return pc.local_solve(bundle, evaluator, start, config, telemetry, k)
    P = Projector(bundle, evaluator, plan)
    m = len(bundle.spec.constraints)
    keep = [i for i in range(m + 2) if i not in P.drop]
    vector_fn = smb._AugmentedResidualVectorFn(
        bundle=bundle, evaluator=evaluator, n_constraints=m,
        deadline_monotonic=None, telemetry=telemetry, constraint_scales=None,
    )
    state = {"y": np.array(start, dtype=float)}
    anchor = np.array(start, dtype=float)
    x0 = P.full(np.array(start, dtype=float)[P.free], anchor)
    if x0 is None:
        return None, "proj_start_fail"
    state["y"] = x0

    def f(u):
        x = P.full(np.asarray(u, dtype=float), state["y"])
        if x is None:
            x = P.full(np.asarray(u, dtype=float), x0)
        if x is None:
            P.fails += 1
            return np.full(len(keep), PEN)
        state["y"] = x
        return np.asarray(vector_fn(x), dtype=float)[keep]

    u0 = x0[P.free]
    nf, mk = len(P.free), len(keep) - 2
    try:
        if nf > mk:
            res = minimize(lambda u: float(np.dot(f(u), f(u))), u0, method="Powell",
                           options={"maxiter": smb._UNDERDETERMINED_POWELL_MAXITER, "ftol": 1e-16})
            status = "powell_cap" if res.status == 2 else "powell"
        elif nf == 0:
            res = type("R", (), {"x": u0})()
            status = "conv"
        else:
            res = least_squares(f, u0, method="lm", max_nfev=smb._LM_MAX_NFEV,
                                ftol=1e-14, xtol=1e-14, gtol=1e-14)
            status = "cap" if res.status == 0 else "conv"
    except Exception as error:  # noqa: BLE001
        return None, f"exception:{type(error).__name__}"
    x = P.full(np.asarray(res.x, dtype=float), state["y"])
    if x is None:
        x = P.full(np.asarray(res.x, dtype=float), x0)
    if x is None:
        return None, "proj_end_fail"
    cand = smb._build_candidate(evaluator=evaluator, config=config, bounds=[(-pc.WIDE, pc.WIDE)] * P.n,
                                values=np.array(x, dtype=float), origin_seed=0, family_code=smb._LM_FAMILY_CODE,
                                origin_start_point_index=k, telemetry=telemetry)
    return cand, status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("out")
    ap.add_argument("--e", required=True)
    ap.add_argument("--y", required=True)
    ap.add_argument("--starts", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=600.0)
    ap.add_argument("--arms", default="E,Y,PY,PE")
    args = ap.parse_args()

    refs = reference_values(load_case(args.case_id)["answer"])
    e_dsl, e_b, e_ev = pc.build(args.e)
    y_dsl, y_b, y_ev = pc.build(args.y)
    base = list(e_b.var_names)
    e_box = np.array(pc.infer_problem_bounds(e_b), dtype=float)
    y_boxa = np.array(pc.infer_problem_bounds(y_b), dtype=float)
    y_box = dict(zip(y_b.var_names, map(tuple, y_boxa)))
    extra = sorted({v[2:] for v in y_b.var_names if v[:2] in ("x_", "y_") and v not in base})
    hcoord = construction_coordinates(e_dsl, extra)
    config = pc.ExternalPipelineConfig.production_baseline_tier(seed=args.seed, total_time_budget_sec=180.0).search
    telemetry = smb._SearchTelemetry()

    drng = np.random.default_rng([args.seed, 777])
    plan_y, log_y = detect(y_b, y_ev, y_boxa, drng)
    plan_e, log_e = detect(e_b, e_ev, e_box, drng)
    # which Y rows are the construction rows added by the rewrite (for reporting only)
    e_rows = [str(c) for c in e_b.spec.constraints]
    y_rows = [str(c) for c in y_b.spec.constraints]
    added = [i for i, s in enumerate(y_rows) if s not in e_rows]
    log_y["added_rows"] = added
    log_y["points_extra"] = extra

    def h_of(u):
        vals = dict(zip(base, u))
        out = {}
        for var, (names, ev) in hcoord.items():
            v = answer_float(ev, [vals[n] for n in names])
            out[var] = v if v is not None and math.isfinite(v) else float("nan")
        return out

    def physical(system, x):
        vals = dict(zip((y_b if system in ("Y", "PY") else e_b).var_names, x))
        u = [vals[n] for n in base]
        if system in ("Y", "PY"):
            pts = {f"{a}_{p}": vals[f"{a}_{p}"] for p in extra for a in "xy"}
        else:
            h = h_of(u)
            pts = {f"{a}_{p}": h[f"{a}_{p}"] for p in extra for a in "xy"}
        return u, pts

    def in_region(u, pts):
        if not all(lo <= v <= hi for v, (lo, hi) in zip(u, e_box)):
            return False
        return all(math.isfinite(v) and y_box[n][0] <= v <= y_box[n][1] for n, v in pts.items())

    arms = args.arms.split(",")
    systems = {"E": (e_b, e_ev, None), "Y": (y_b, y_ev, None), "PY": (y_b, y_ev, plan_y), "PE": (e_b, e_ev, plan_e)}
    rows = []
    t_start = time.monotonic()
    for k in range(args.starts):
        if time.monotonic() - t_start > args.budget:
            break
        rng = np.random.default_rng([args.seed, k])
        u0 = e_box[:, 0] + rng.random(len(base)) * (e_box[:, 1] - e_box[:, 0])
        h0 = h_of(u0)
        if not all(math.isfinite(v) for v in h0.values()):
            rows.append({"k": k, "start_undefined": True})
            continue
        u0d = dict(zip(base, u0))
        row = {"k": k}
        for s in arms:
            b, ev, plan = systems[s]
            start = np.array([u0d[n] if n in u0d else h0[n] for n in b.var_names], dtype=float)
            t0 = time.monotonic()
            n0 = telemetry.evaluation_count
            if plan is None:
                cand, status = pc.local_solve(b, ev, start, config, telemetry, k)
            else:
                cand, status = proj_local_solve(b, ev, start, config, telemetry, k, plan)
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
    done = [r for r in rows if "start_undefined" not in r]
    summary = {}
    for s in arms:
        c = {}
        for r in done:
            c[r[s]["cls"]] = c.get(r[s]["cls"], 0) + 1
        summary[s] = {"counts": c, "p": c.get("hit", 0) / max(1, len(done)),
                      "sec_median": float(np.median([r[s]["sec"] for r in done])) if done else None,
                      "nfev_median": float(np.median([r[s]["nfev"] for r in done])) if done else None}
    out = {"case_id": args.case_id, "n_base": len(base), "n_y": len(y_b.var_names), "extra": extra,
           "detect_y": log_y, "detect_e": log_e, "starts": len(done), "start_undefined": len(rows) - len(done),
           "elapsed": time.monotonic() - t_start, "summary": summary, "rows": rows}
    Path(args.out).write_text(json.dumps(out))
    print(args.case_id, {s: round(v["p"], 3) for s, v in summary.items()},
          "PYpts=", log_y.get("points"), "PEpts=", log_e.get("points"), "elapsed=%.0f" % out["elapsed"])


if __name__ == "__main__":
    sys.exit(main())
