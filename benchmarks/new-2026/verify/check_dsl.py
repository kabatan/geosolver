# ruff: noqa: E501, SIM115
"""Independent consistency check for a hand-written DSL (no GeoSolver search).

Uses only the DSL evaluation layer (constructions, residuals, guards, target)
and an independent multi-start SciPy least-squares + mpmath Gauss-Newton
polish. Reports every distinct target value reached by feasible configurations
and compares it with the official answer set.

usage: check_dsl.py DSL.json --answer EXPR [--answer EXPR ...]
                    [--box LO HI | --var NAME LO HI ...] [--starts N] [--seed S]
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings

import mpmath
import numpy as np
import sympy
from scipy.optimize import least_squares

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    high_precision_mode,
)
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import validate

warnings.filterwarnings("ignore")
DPS = 60


def load(path):
    return load_dict(json.load(open(path, encoding="utf-8")))


def load_dict(dsl):
    problem = GeometryProblem.model_validate(dsl)
    report = validate(problem)
    issues = [f"{i.path}: {i.message}" for i in report.issues]
    bundle = load_problem_bundle(to_engine_document(problem))
    return dsl, issues, bundle, build_ir_evaluator(bundle)


def float_residual(ev, x):
    r = ev.evaluate_float_residual([float(v) for v in x])
    if not r.is_finite:
        return None
    return np.array([float(v) for v in r.residual_vector])


def hp_residual(ev, x):
    mpmath.mp.dps = DPS
    vals = [v if isinstance(v, mpmath.mpf) else mpmath.mpf(repr(float(v))) for v in x]
    with high_precision_mode():
        r = ev.evaluate_hp_residual(vals, precision=DPS)
    if not getattr(r, "is_finite", True):
        return None
    vec = getattr(r, "residual_vector", None)
    return None if vec is None else [mpmath.mpf(v) for v in vec]


def hp_target(ev, x):
    mpmath.mp.dps = DPS
    vals = [v if isinstance(v, mpmath.mpf) else mpmath.mpf(repr(float(v))) for v in x]
    with high_precision_mode():
        a = ev.evaluate_answer_hp(vals, precision=DPS)
    return a.answer_hp


def polish(ev, x0, iters=40):
    """Minimum-norm Gauss-Newton at DPS digits with forward differences."""
    mpmath.mp.dps = DPS
    x = mpmath.matrix([mpmath.mpf(repr(float(v))) for v in x0])
    n = len(x)
    h = mpmath.mpf(10) ** (-DPS // 2)
    for _ in range(iters):
        r0 = hp_residual(ev, list(x))
        if r0 is None:
            return None, None
        norm = mpmath.sqrt(sum(v * v for v in r0)) if r0 else mpmath.mpf(0)
        if norm < mpmath.mpf(10) ** (-(DPS - 12)):
            return list(x), norm
        m = len(r0)
        J = mpmath.matrix(m, n)
        for j in range(n):
            xp = x.copy()
            xp[j] += h
            rp = hp_residual(ev, list(xp))
            if rp is None:
                return None, None
            for i in range(m):
                J[i, j] = (rp[i] - r0[i]) / h
        r = mpmath.matrix(r0)
        try:
            if m >= n:
                step = mpmath.lu_solve(J.T * J, J.T * r)
            else:
                step = J.T * mpmath.lu_solve(J * J.T, r)
        except ZeroDivisionError:
            return list(x), norm
        x = x - step
    r0 = hp_residual(ev, list(x))
    norm = mpmath.sqrt(sum(v * v for v in r0)) if r0 else None
    return list(x), norm


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dsl")
    p.add_argument("--answer", action="append", default=[])
    p.add_argument("--box", nargs=2, type=float, default=[-20, 20])
    p.add_argument("--var", nargs=3, action="append", default=[])
    p.add_argument("--starts", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--polish-max", type=int, default=6, help="HP polishes per cluster")
    p.add_argument("--point", nargs="*", type=float, help="evaluate a given point only")
    args = p.parse_args()

    dsl, issues, bundle, ev = load(args.dsl)
    names = list(bundle.var_names)
    print(f"# {dsl['id']}  vars={names}  residuals={len(bundle.targets)}")
    print(f"  validate issues: {issues or 'none'}")
    official = [sympy.sympify(a.replace("√", "sqrt")) for a in args.answer]
    mpmath.mp.dps = DPS
    official_num = [mpmath.mpf(str(sympy.N(a, DPS + 10))) for a in official]

    if args.point is not None:
        x = args.point
        print("  residual", float_residual(ev, x))
        print("  guard", ev.evaluate_guard(x))
        print("  hard", ev.evaluate_float_hard_feasibility(x))
        print("  target", hp_target(ev, x))
        return

    lo = np.full(len(names), args.box[0])
    hi = np.full(len(names), args.box[1])
    for name, a, b in args.var:
        k = names.index(name)
        lo[k], hi[k] = float(a), float(b)
    rng = np.random.default_rng(args.seed)
    clusters = {}
    converged = feasible = 0
    for _ in range(args.starts):
        x0 = lo + (hi - lo) * rng.random(len(names))

        def fun(x):
            r = float_residual(ev, x)
            if r is None:
                return np.full(len(bundle.targets), 1e6)
            return r

        if len(bundle.targets) == 0:
            sol = x0
        else:
            try:
                res = least_squares(fun, x0, method="trf", xtol=1e-15, ftol=1e-15, gtol=1e-15,
                                    max_nfev=400 * len(names))
            except Exception:
                continue
            sol = res.x
            r = float_residual(ev, sol)
            if r is None or np.linalg.norm(r) > 1e-8:
                continue
        converged += 1
        ok, _ = ev.evaluate_guard(list(sol))
        hard = ev.evaluate_float_hard_feasibility(list(sol))
        if not (ok and hard.hard_feasible):
            continue
        feasible += 1
        mpmath.mp.dps = DPS
        t = float(hp_target(ev, list(sol)))
        key = round(t, 6)
        clusters.setdefault(key, []).append(sol)
    print(f"  starts={args.starts} converged={converged} feasible={feasible}")
    found = []
    for key in sorted(clusters):
        pts = clusters[key]
        best = None
        for sol in pts[: args.polish_max]:
            xp, norm = polish(ev, sol)
            if xp is None or norm is None:
                continue
            ok, _ = ev.evaluate_guard([float(v) for v in xp])
            hard = ev.evaluate_float_hard_feasibility([float(v) for v in xp])
            if not (ok and hard.hard_feasible):
                continue
            t = hp_target(ev, xp)
            if best is None or norm < best[1]:
                best = (xp, norm, t)
        if best is None:
            print(f"  value~{key}: {len(pts)} hits, HP polish failed/infeasible")
            continue
        xp, norm, t = best
        match = [k for k, v in enumerate(official_num) if abs(t - v) < mpmath.mpf(10) ** (-30)]
        found.extend(match)
        match = [args.answer[k] for k in match]
        print(f"  value={mpmath.nstr(t, 35)}  hits={len(pts)}  |res|={mpmath.nstr(norm, 3)}  "
              f"official_match={match or 'NO'}")
        print("     at " + ", ".join(f"{n}={mpmath.nstr(v, 12)}" for n, v in zip(names, xp, strict=False)))
    missing = [args.answer[k] for k in range(len(official)) if k not in found]
    extra = [k for k in clusters if not any(abs(k - float(v)) < 1e-5 for v in official_num)]
    verdict = "PASS" if not missing and not extra and not issues else "CHECK"
    print(f"  missing_official={missing or 'none'}  extra_values={extra or 'none'}  => {verdict}")


if __name__ == "__main__":
    sys.exit(main())
