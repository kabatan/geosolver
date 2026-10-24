"""Adapted S1 worker: fixed S7 references, raw/T1 arm, no final verification."""
import hashlib
import json
import math
import os
import pickle
import sys
import time
from dataclasses import asdict
from pathlib import Path

import resource
resource.setrlimit(resource.RLIMIT_FSIZE, (2_999_999, 2_999_999))

from mpmath import mp
from geosolver.runtime.integrity import source_tree_hash

ROOT = Path(sys.argv[1])
MODE, CASE = sys.argv[2:4]
ARM = sys.argv[4] if len(sys.argv) > 4 else None
M = json.loads((ROOT / "manifest.json").read_text())
TASK = next(t for t in M["inputs"] if t["case_id"] == CASE)
D = ROOT / "runs" / CASE
D.mkdir(parents=True, exist_ok=True)
SOURCE = source_tree_hash()
assert SOURCE == M["frozen_source_hash" if MODE == "verify" else "source_hash"]
assert hashlib.sha256(Path(TASK["input_copy"]).read_bytes()).hexdigest() == TASK["sha256"]


def save(name, obj):
    def clean(value):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [clean(v) for v in value]
        return value
    path = D / name
    temp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(data.encode()) < 3_000_000
    temp.write_text(data)
    temp.replace(path)


def dump(name, obj):
    with (D / name).open("wb") as f:
        pickle.dump(obj, f, protocol=5)


def load(name):
    with (D / name).open("rb") as f:
        return pickle.load(f)


def textnum(x):
    return None if x is None else mp.nstr(x, 710, min_fixed=0, max_fixed=0)


def doc():
    from geosolver.problem.models import GeometryProblem
    return GeometryProblem.model_validate_json(Path(TASK["input_copy"]).read_text()).engine_document()


def ordinary():
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    bundle = load_problem_bundle(doc())
    return bundle, build_ir_evaluator(bundle)


def runtime_receipt():
    return {"pid": os.getpid(), "affinity": sorted(os.sched_getaffinity(0)),
        "threads": int(next(line.split(':')[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('Threads:'))),
        "environment": {k:v for k,v in os.environ.items() if k.startswith(('GEOSOLVER_ABLATE_', 'GEOSOLVER_S3_', 'GEOSOLVER_S7_'))},
        "source_hash": SOURCE}

save(("measure-corrected" if MODE == "measure" else MODE) + ("." + ARM if ARM else "") + ".runtime-start.json", runtime_receipt())

if MODE == "search":
    import geosolver.engine.standard.orchestration.run_external_pipeline as pipeline
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.contracts.candidate_record import candidate_record
    from geosolver.runtime.deadline import runtime_session

    class Captured(BaseException):
        pass

    started = time.monotonic()

    def capture(**kw):
        candidates = kw["search_result"].candidates
        dump("initial.pkl", (candidates, kw["refiner"].config))
        save("initial.json", {"source_hash": SOURCE, "seed": 0,
             "var_names": kw["bundle"].var_names, "candidates": [candidate_record(c) for c in candidates],
             "search_seconds": time.monotonic() - started,
             "search_evaluations": kw["search_result"].evaluation_count,
             "search_diagnostics": kw["search_result"].search_diagnostics})
        raise Captured()

    pipeline.run_refinement = capture
    deadline = started + 178
    try:
        with mp.workdps(180), runtime_session(deadline):
            pipeline.run_external_pipeline(doc(), seed=0,
                pipeline_config=ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=178),
                deadline_monotonic=deadline)
    except Captured:
        pass
    else:
        raise RuntimeError("primary refinement handoff not reached")

elif MODE == "scales":
    from geosolver.problem.ir.parser import load_ir
    from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision, evaluate_target_high_precision
    from geosolver.engine.standard.evaluation.snapshots import evaluate_scalar_expression
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf, BoundaryOrigin
    spec = load_ir(doc())
    bundle, _ = ordinary()
    targets = tuple(spec.v) if spec.v is not None else (0,) * len(spec.constraints)
    raw = ProblemBundle(spec, bundle.var_names, targets, bundle.base_context, CASE)
    scales = [mp.mpf(1) for _ in targets]
    finite_counts = [0 for _ in targets]
    candidates, _ = load("initial.pkl")
    with mp.workdps(700):
        points = [tuple(boundary_float_to_mpf(v, origin=BoundaryOrigin.INITIAL_POINT) for v in c.x_float) for c in candidates]
    with mp.workdps(700), high_precision_mode():
        for point in points:
            try:
                ctx = build_solution_context_high_precision(spec, list(raw.var_names), list(point), raw.base_context, 700,
                    expressions=[*spec.constraints, *(t for t in targets if isinstance(t, str))])
                for i, expression in enumerate(spec.constraints):
                    try:
                        lhs = mp.mpf(evaluate_scalar_expression(expression, ctx, constants_only=True))
                        rhs = evaluate_target_high_precision(targets[i], ctx, precision=700, index=i)
                        if mp.isfinite(lhs) and mp.isfinite(rhs):
                            scales[i] = max(scales[i], abs(lhs), abs(rhs))
                            finite_counts[i] += 1
                    except Exception:
                        pass
            except Exception:
                pass
        save("scales.json", {"constraints": spec.constraints, "targets": list(targets),
             "scales": [textnum(x) for x in scales], "finite_counts": finite_counts})

elif MODE == "refine":
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
    from geosolver.runtime.deadline import runtime_session
    candidates, config = load("initial.pkl")
    bundle, evaluator = ordinary()
    raw_receipt = None
    if ARM == "RAW":
        from raw_switch import install
        item = json.loads(Path(TASK["stage1_input"]).read_text())
        tangencies = json.loads(Path(TASK["sigma_details"]).read_text())["tangencies"]
        raw_receipt = install(bundle, item, tangencies)
    timings = {}
    original_single = MpmathRefiner._refine_single_candidate

    def timed_single(self, **kwargs):
        t0 = time.monotonic()
        try:
            return original_single(self, **kwargs)
        finally:
            timings[kwargs["candidate"].candidate_uid] = time.monotonic()-t0

    MpmathRefiner._refine_single_candidate = timed_single
    started = time.monotonic()
    with mp.workdps(180), runtime_session(started + 90):
        result = MpmathRefiner(config).refine_candidates(bundle=bundle, evaluator=evaluator,
            candidates=candidates, deadline_monotonic=started + 90)
    seconds = time.monotonic() - started
    dump(ARM + ".refined.pkl", result.candidates)
    save(ARM + ".refinement.json", {"source_hash": SOURCE, "arm": ARM, "raw_receipt": raw_receipt,
        "initial_sha256": hashlib.sha256((D / "initial.pkl").read_bytes()).hexdigest(),
        "scales_sha256": hashlib.sha256((D / "scales.json").read_bytes()).hexdigest() if (D / "scales.json").exists() else None,
        "seconds": seconds, "deadline_hit": seconds >= 90,
        "attempted": result.attempted_count, "returned": len(result.candidates),
        "converged": result.converged_count, "hard_feasible": result.hard_feasible_count,
        "unattempted": len(candidates) - result.attempted_count, "candidate_seconds": timings})

elif MODE == "measure":
    from geosolver.problem.ir.parser import load_ir
    from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
    spec = load_ir(doc())
    bundle, _ = ordinary()
    targets = tuple(spec.v) if spec.v is not None else (0,) * len(spec.constraints)
    evaluator = build_ir_evaluator(ProblemBundle(spec, bundle.var_names, targets, bundle.base_context, CASE))
    started = time.monotonic()
    rows = []
    with mp.workdps(700):
        refs = [mp.mpf(TASK["reference_answer"])]
        scales = [mp.mpf(x) for x in json.loads((D / "scales.json").read_text())["scales"]] if (D / "scales.json").exists() else None
        for i, c in enumerate(load(ARM + ".refined.pkl")):
            row = {"case_id": CASE, "seed": 0, "arm": ARM, "rank": i,
                "candidate_id": c.candidate_id, "candidate_uid": c.candidate_uid,
                "source_uid": c.source.candidate_uid if c.source else None,
                "status": c.refinement_status, "hard_feasible": c.hard_feasible,
                "immediate_pass": c.refinement_status == "target_reached" and c.hard_feasible is True,
                "solver_residual": textnum(c.residual_norm_hp), "coordinate_dps": c.coordinate_precision_dps}
            try:
                with high_precision_mode():
                    evaluation = evaluator.evaluate_hp_residual(c.x_hp, precision=700)
                if scales is None:
                    raise ValueError("fixed scales unavailable")
                normalized = [r/s for r, s in zip(evaluation.residual_vector, scales, strict=True)]
                norm = mp.sqrt(mp.fsum(r*r for r in normalized)) if all(mp.isfinite(r) for r in normalized) else mp.inf
                row.update(original_residual_norm=textnum(evaluation.residual_norm_hp), normalized_l2=textnum(norm),
                    normalized_max=textnum(max(map(abs, normalized), default=mp.mpf(0))))
            except Exception as e:
                row["residual_error"] = repr(e)
            try:
                with high_precision_mode():
                    answer = evaluator.evaluate_answer_hp(c.x_hp, precision=700).answer_hp
                if answer is None or not mp.isfinite(answer):
                    raise ValueError("nonfinite or unavailable answer")
                errors = [abs(answer-ref) for ref in refs]
                error = min(errors)
                digits = min(mp.mpf(600), -mp.log10(error)) if error else mp.mpf(600)
                row.update(answer=textnum(answer), absolute_error=textnum(error), error_digits=float(digits), error_digits_exact=textnum(digits),
                    nearest_reference=errors.index(error), p1_base_threshold=error <= mp.mpf("1e-100"),
                    p1_without_threshold=error > mp.mpf("1e-60"))
            except Exception as e:
                row["answer_error"] = repr(e)
            rows.append(row)
    save(ARM + ".measure.json", {"source_hash": SOURCE, "seconds": time.monotonic()-started, "rows": rows})

else:
    raise ValueError(MODE)

save(("measure-corrected" if MODE == "measure" else MODE) + ("." + ARM if ARM else "") + ".runtime-end.json", runtime_receipt())
