"""Measure, per problem, how often one local search start lands on a correct figure.

For each case the script draws N uniform random starts inside the solver's own
search box and runs the solver's own single-start local solver
(``_collect_local_start_record``: Levenberg-Marquardt on the residual vector
augmented with the guard and hard-feasibility penalties, or Powell when the
system is underdetermined).  Each end point is classified as

- ``hit``: residual small, guards and hard checks pass, answer matches a
  reference answer (which one is recorded);
- ``wrong_answer``: residual small and feasible but the answer is not a
  reference answer;
- ``wrong_branch``: equalities satisfied but a guard or hard check fails;
- ``stuck``: the residual did not go to zero (local minimum or no convergence);
- ``error``: evaluation failed.

At the first hit of each reference answer the Jacobian of the equality
residuals is estimated by central differences; its singular values measure
how degenerate (tangent / double-root-like) the correct configuration is.

The solver source is not modified (frozen 60db4b6); private helpers are
imported read-only.

With ``--init-from BASE.json`` (the k=0 DSL of an extra-variables variant),
the extra point variables x_N, y_N are not drawn at random: they start at the
position the original construction gives for the random base variables, so
the start lies on the extra equations and only the search space is larger.

Usage: python probe_basins.py CASE_ID OUT.json [--starts 200] [--seed 0] [--budget 120]
       [--dsl VARIANT.json [--init-from BASE.json]]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import sympy as sp
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig

ROOT = Path(__file__).resolve().parents[2]
RES_TOL = 1e-8
ANS_RTOL = 1e-6


def load_case(case_id: str, cases_path: str | Path | None = None) -> dict:
    for line in Path(cases_path or ROOT / "benchmarks" / "cases.jsonl").open():
        case = json.loads(line)
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def _ascii_expr(text: str) -> str:
    """Turn reference answers such as '9√15' or '64(2-√3)' into SymPy syntax."""
    s = str(text).replace("−", "-").replace("×", "*").replace("π", "pi")
    s = re.sub(r"\\sqrt\{([^}]*)\}", r"sqrt(\1)", s)
    s = re.sub(r"∛\s*(\d+|\([^)]*\))", r"cbrt(\1)", s)
    s = re.sub(r"√\s*\(", "sqrt(", s)
    s = re.sub(r"√\s*(\d+(?:\.\d+)?|[A-Za-z_]\w*)", r"sqrt(\1)", s)
    s = re.sub(r"(\d|\))\s*(sqrt|pi|\()", r"\1*\2", s)
    return s


def reference_values(answer) -> list[float]:
    items = answer if isinstance(answer, list) else [answer]
    flat = []
    for item in items:
        text = re.sub(r"\(\d+個\)", "", str(item))
        flat.extend(part for part in (text.split(",") if "CRootOf" not in text else [text]) if part.strip())
    items = flat
    return [float(sp.N(sp.sympify(_ascii_expr(item), locals={"cbrt": sp.cbrt, "CRootOf": sp.CRootOf}), 30)) for item in items]


def answer_float(evaluator, x) -> float | None:
    try:
        with mp.workdps(30), high_precision_mode():
            r = evaluator.evaluate_answer_hp([mp.mpf(repr(float(v))) for v in x], precision=30)
        value = getattr(r, "answer_hp", None)
        return None if value is None else float(mp.re(value))
    except Exception:
        return None


def equality_jacobian_svals(evaluator, x, h=1e-6):
    x = np.array(x, dtype=float)
    base = np.array(evaluator.evaluate_float_residual(list(x)).residual_vector, dtype=float)
    cols = []
    for i in range(x.size):
        step = h * max(1.0, abs(x[i]))
        xp = x.copy(); xp[i] += step
        xm = x.copy(); xm[i] -= step
        fp = np.array(evaluator.evaluate_float_residual(list(xp)).residual_vector, dtype=float)
        fm = np.array(evaluator.evaluate_float_residual(list(xm)).residual_vector, dtype=float)
        cols.append((fp - fm) / (2 * step))
    J = np.column_stack(cols) if cols else np.zeros((base.size, 0))
    s = np.linalg.svd(J, compute_uv=False) if J.size else np.array([])
    return [float(v) for v in s], int(base.size)


def construction_coordinates(base_dsl: dict, names: list[str]):
    """Evaluators giving the constructed position of each point in ``names`` from the base variables."""
    out = {}
    for name in names:
        for axis in ("x", "y"):
            dsl = json.loads(json.dumps(base_dsl))
            dsl["constructions"] = [{"name": "ORIGINZ", "expression": "Point(0, 0)"}] + dsl["constructions"]
            dsl["target"] = f"Vector(ORIGINZ, {name}).{axis}"
            dsl["conditions"] = [c for c in dsl["conditions"] if c.get("operator") == "="][:1] or dsl["conditions"][:1]
            bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
            out[f"{axis}_{name}"] = (list(bundle.var_names), build_ir_evaluator(bundle))
    return out


def _hard_feasible(evaluator, x) -> bool:
    try:
        return bool(evaluator.evaluate_float_hard_feasibility(list(x), include_margins=False).hard_feasible)
    except Exception:  # noqa: BLE001
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("out")
    ap.add_argument("--starts", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=float, default=120.0)
    ap.add_argument("--cases", type=Path, help="case JSONL (default: benchmarks/cases.jsonl)")
    ap.add_argument("--defer-summary", action="store_true",
                    help="save individual records without aggregating hits or p (preregistration)")
    ap.add_argument("--dsl", help="use this DSL JSON instead of the case's own")
    ap.add_argument("--init-from", help="k=0 DSL: start extra point variables at their constructed position")
    ap.add_argument("--zero-prefix", help="start variables whose name begins with this prefix at 0 (offset variants)")
    ap.add_argument("--feasible-starts", action="store_true",
                    help="redraw each start (own RNG [seed, 99, k], up to 2000 tries) until it passes hard feasibility")
    args = ap.parse_args()

    case = load_case(args.case_id, args.cases)
    dsl = json.loads(Path(args.dsl).read_text()) if args.dsl else case["dsl"]
    refs = reference_values(case["answer"])
    doc = GeometryProblem.model_validate(dsl).engine_document()
    bundle = load_problem_bundle(doc)
    evaluator = build_ir_evaluator(bundle)
    out = {
        "case_id": args.case_id,
        "dsl_override": args.dsl,
        "n_vars": len(bundle.var_names),
        "n_constraints": len(bundle.spec.constraints),
        "references": refs,
        "starts_requested": args.starts,
        "seed": args.seed,
        "init_from": args.init_from,
        "zero_prefix": args.zero_prefix,
        "feasible_starts": args.feasible_starts,
    }
    if not bundle.var_names:
        out["status"] = "no_variables"
        Path(args.out).write_text(json.dumps(out))
        return
    bounds = infer_problem_bounds(bundle)
    lower = np.array([b[0] for b in bounds], dtype=float)
    upper = np.array([b[1] for b in bounds], dtype=float)
    out["box"] = [list(map(float, b)) for b in bounds]
    config = ExternalPipelineConfig.production_baseline_tier(seed=args.seed, total_time_budget_sec=180.0).search
    telemetry = smb._SearchTelemetry()
    rng = np.random.default_rng(args.seed)
    names = list(bundle.var_names)
    init = {}
    if args.init_from:
        base_dsl = json.loads(Path(args.init_from).read_text())
        extra = sorted({v[2:] for v in names if re.match(r"^[xy]_", v) and v not in base_dsl["variables"]})
        init = construction_coordinates(base_dsl, extra)
    t_start = time.monotonic()
    deadline = t_start + args.budget
    records = []
    first_hit = {}
    for k in range(args.starts):
        if time.monotonic() > deadline:
            break
        start = lower + rng.random(lower.size) * (upper - lower)
        if init:
            value_of = dict(zip(names, start))
            for var, (base_names, ev) in init.items():
                v = answer_float(ev, [value_of[n] for n in base_names])
                if v is not None and math.isfinite(v):
                    start[names.index(var)] = v
        if args.zero_prefix:
            for j, n in enumerate(names):
                if n.startswith(args.zero_prefix):
                    start[j] = 0.0
        redraws = 0
        if args.feasible_starts:
            rr = np.random.default_rng([args.seed, 99, k])
            while redraws < 2000 and not _hard_feasible(evaluator, start):
                start = lower + rr.random(lower.size) * (upper - lower)
                redraws += 1
        t0 = time.monotonic()
        n0 = telemetry.evaluation_count
        try:
            cand = smb._collect_local_start_record(
                bundle=bundle, evaluator=evaluator, bounds=bounds, config=config,
                seed=args.seed, start_index=k, start=start,
                deadline_monotonic=deadline, telemetry=telemetry,
            )
        except smb._SearchDeadlineExceeded:
            break
        except Exception as error:  # noqa: BLE001
            cand = None
            err = type(error).__name__
        else:
            err = None
        dt = time.monotonic() - t0
        rec = {"k": k, "sec": dt, "nfev": telemetry.evaluation_count - n0}
        if args.defer_summary:
            rec["start"] = [float(v) for v in start]
        if args.feasible_starts:
            rec["redraws"] = redraws
        rec["start_feasible"] = _hard_feasible(evaluator, start)
        if cand is not None:
            rec["x"] = [float(v) for v in cand.x_float]
            rec["start"] = [float(v) for v in start]
        if cand is None:
            rec["cls"] = "error"
            rec["err"] = err
        elif "out_of_bounds" in tuple(cand.hard_violation_tags):
            rec["cls"] = "left_box"
        elif not math.isfinite(cand.residual_norm_float):
            rec["cls"] = "error"
            rec["err"] = "nonfinite"

        else:
            rec["res"] = cand.residual_norm_float
            feasible = bool(cand.guard_ok) and cand.hard_feasible is not False
            if cand.residual_norm_float > RES_TOL:
                rec["cls"] = "stuck"
            elif not feasible:
                rec["cls"] = "wrong_branch"
            else:
                value = answer_float(evaluator, cand.x_float)
                rec["ans"] = value
                match = None
                if value is not None:
                    for j, ref in enumerate(refs):
                        if abs(value - ref) <= ANS_RTOL * max(1.0, abs(ref)):
                            match = j
                            break
                if match is None:
                    rec["cls"] = "wrong_answer"
                else:
                    rec["cls"] = "hit"
                    rec["ref"] = match
                    if match not in first_hit:
                        svals, n_eq = equality_jacobian_svals(evaluator, cand.x_float)
                        first_hit[match] = {"k": k, "x": list(cand.x_float), "svals": svals, "n_residuals": n_eq}
        records.append(rec)
    out["status"] = "ok"
    out["elapsed"] = time.monotonic() - t_start
    out["starts_done"] = len(records)
    if args.defer_summary:
        out["summary_deferred"] = True
        out["records"] = records
        Path(args.out).write_text(json.dumps(out))
        print(args.case_id, "starts_done=", len(records), "summary deferred",
              "elapsed=%.1f" % out["elapsed"])
        return
    counts = {}
    for r in records:
        counts[r["cls"]] = counts.get(r["cls"], 0) + 1
    out["counts"] = counts
    hits_by_ref = [sum(1 for r in records if r.get("ref") == j) for j in range(len(refs))]
    out["hits_by_ref"] = hits_by_ref
    n = max(1, len(records))
    out["p_any"] = counts.get("hit", 0) / n
    out["p_min_ref"] = min(hits_by_ref) / n if refs else None
    out["sec_per_start_median"] = float(np.median([r["sec"] for r in records])) if records else None
    out["nfev_per_start_median"] = float(np.median([r["nfev"] for r in records])) if records else None
    out["first_hit"] = {str(k): v for k, v in first_hit.items()}
    out["records"] = records
    Path(args.out).write_text(json.dumps(out))
    print(args.case_id, out["n_vars"], counts, "p_any=%.3f" % out["p_any"], "elapsed=%.1f" % out["elapsed"])


if __name__ == "__main__":
    sys.exit(main())
