"""S5: S3 worker plus unchanged S1 first-search capture and fixed-scale stages."""
import hashlib
import json
import math
import os
import pickle
import sys
import time
from dataclasses import asdict
from pathlib import Path

from mpmath import mp
from geosolver.runtime.integrity import source_tree_hash

ROOT = Path(sys.argv[1])
MODE, CASE = sys.argv[2:4]
ARM = sys.argv[4] if len(sys.argv) > 4 else None
M = json.loads((ROOT / "manifest.json").read_text())
TASK = next(t for t in M["inputs"] if t["case_id"] == CASE)
D = ROOT / "runs" / CASE
D.mkdir(parents=True, exist_ok=True)
import resource
resource.setrlimit(resource.RLIMIT_FSIZE, (2_999_999, 2_999_999))
SOURCE = source_tree_hash()
assert SOURCE == M["frozen_source_hash" if MODE in ("verify", "references") else "source_hash"]
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
    temp.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def dump(name, obj):
    with (D / name).open("wb") as f:
        pickle.dump(obj, f, protocol=5)


def load(name):
    with (D / name).open("rb") as f:
        return pickle.load(f)


def textnum(x):
    return None if x is None else mp.nstr(x, 710)


def doc():
    from geosolver.problem.models import GeometryProblem
    return GeometryProblem.model_validate_json(Path(TASK["input_copy"]).read_text()).engine_document()


def ordinary():
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    bundle = load_problem_bundle(doc())
    return bundle, build_ir_evaluator(bundle)


with (D / (MODE + ("." + ARM if ARM else "") + ".execution.json")).open("x") as f:
    json.dump(dict(pid=os.getpid(), mode=MODE, arm=ARM, seed=0, affinity=sorted(os.sched_getaffinity(0)),
        source_hash=SOURCE, threads={k:os.environ.get(k) for k in M["thread_environment"]},
        switches={k:v for k,v in os.environ.items() if k.startswith("GEOSOLVER_ABLATE_") or k=="GEOSOLVER_S3_TANGENCY_MODE"}), f)

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
             "config_repr": repr(kw["refiner"].config),
             "candidate_uids": [c.candidate_uid for c in candidates],
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
    import random
    import numpy as np
    random.seed(0)
    np.random.seed(0)
    candidates, config = load("initial.pkl")
    bundle, evaluator = ordinary()
    timings = {}
    original_single = MpmathRefiner._refine_single_candidate
    observer = None
    if CASE == "AIME-2018-II-14":
        from observe_iterations import Observer
        observer = Observer()
        observer.install()

    def timed_single(self, **kwargs):
        t0 = time.monotonic()
        if observer:
            observer.begin(kwargs["candidate"])
        try:
            returned = original_single(self, **kwargs)
            if observer:
                observer.finish(returned)
            return returned
        finally:
            timings[kwargs["candidate"].candidate_uid] = time.monotonic()-t0

    MpmathRefiner._refine_single_candidate = timed_single
    started = time.monotonic()
    with mp.workdps(180), runtime_session(started + 90):
        result = MpmathRefiner(config).refine_candidates(bundle=bundle, evaluator=evaluator,
            candidates=candidates, deadline_monotonic=started + 90)
    seconds = time.monotonic() - started
    dump(ARM + ".refined.pkl", result.candidates)
    if observer:
        dump(ARM + ".iterations.pkl", observer.rows)
    save(ARM + ".refinement.json", {"source_hash": SOURCE, "arm": ARM,
        "initial_sha256": hashlib.sha256((D / "initial.pkl").read_bytes()).hexdigest(),
        "scales_sha256": hashlib.sha256((D / "scales.json").read_bytes()).hexdigest(),
        "seconds": seconds, "deadline_hit": seconds >= 90,
        "attempted": result.attempted_count, "returned": len(result.candidates),
        "converged": result.converged_count, "hard_feasible": result.hard_feasible_count,
        "unattempted": len(candidates) - result.attempted_count, "candidate_seconds": timings})

elif MODE in ("measure", "iterations"):
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
    reference_record = json.loads((D / "references.json").read_text())
    with mp.workdps(700):
        refs = [mp.mpf(r) for r in reference_record["values"]] if reference_record["available"] else []
    with mp.workdps(700), high_precision_mode():
        scales = [mp.mpf(x) for x in json.loads((D / "scales.json").read_text())["scales"]]
        for i, c in enumerate(load(ARM + ".refined.pkl") if MODE == "measure" else []):
            row = {"case_id": CASE, "seed": 0, "arm": ARM, "rank": i,
                "candidate_id": c.candidate_id, "candidate_uid": c.candidate_uid,
                "source_uid": c.source.candidate_uid if c.source else None,
                "status": c.refinement_status, "hard_feasible": c.hard_feasible,
                "immediate_pass": c.refinement_status == "target_reached" and c.hard_feasible is True,
                "solver_residual": textnum(c.residual_norm_hp), "coordinate_dps": c.coordinate_precision_dps}
            try:
                evaluation = evaluator.evaluate_hp_residual(c.x_hp, precision=700)
                normalized = [r/s for r, s in zip(evaluation.residual_vector, scales, strict=True)]
                norm = mp.sqrt(mp.fsum(r*r for r in normalized)) if all(mp.isfinite(r) for r in normalized) else mp.inf
                row.update(original_residual_norm=textnum(evaluation.residual_norm_hp), normalized_l2=textnum(norm),
                    normalized_max=textnum(max(map(abs, normalized), default=mp.mpf(0))))
            except Exception as e:
                row["residual_error"] = repr(e)
            try:
                answer = evaluator.evaluate_answer_hp(c.x_hp, precision=700).answer_hp
                if answer is None or not mp.isfinite(answer):
                    raise ValueError("nonfinite or unavailable answer")
                row["answer"] = textnum(answer)
                if not refs:
                    raise ValueError("reference_missing: " + str(reference_record.get("error")))
                errors = [abs(answer-ref) for ref in refs]
                error = min(errors)
                digits = min(mp.mpf(600), -mp.log10(error)) if error else mp.mpf(600)
                row.update(answer=textnum(answer), absolute_error=textnum(error), error_digits=float(str(digits)),
                    nearest_reference=errors.index(error), p1_base_threshold=error <= mp.mpf("1e-100"),
                    p1_without_threshold=error > mp.mpf("1e-60"))
            except Exception as e:
                row["answer_error"] = repr(e)
            rows.append(row)
    if MODE == "measure":
        save(ARM + ".measure.json", {"source_hash": SOURCE, "seconds": time.monotonic()-started,
             "reference_available": reference_record["available"], "reference_error": reference_record.get("error"), "rows": rows})
    else:
        from observe_iterations import measure_trace
        measure_trace(D, ARM, evaluator, refs, save, textnum)

elif MODE == "references":
    from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
    started = time.monotonic()
    try:
        with mp.workdps(700):
            refs = [_eval_exact_to_mpf(r, 700) for r in TASK["reference_expressions"]]
            if not refs or not all(r is not None and mp.isfinite(r) for r in refs):
                raise ValueError("reference expression returned None/nonfinite")
            record = {"available": True, "values": [textnum(r) for r in refs]}
    except Exception as e:
        record = {"available": False, "values": [], "error": repr(e)}
    save("references.json", {**record, "source_hash": SOURCE,
         "expressions": TASK["reference_expressions"], "seconds": time.monotonic()-started})

elif MODE == "verify":
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.runtime.deadline import runtime_session
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    _, evaluator = ordinary()
    candidates = load(ARM + ".refined.pkl")
    started = time.monotonic()
    rows = []
    for i, c in enumerate(candidates):
        row = {"rank": i, "candidate_uid": c.candidate_uid, "final_pass": False}
        t0 = time.monotonic()
        if t0 >= started + 90:
            row["status"] = "unattempted_deadline"
        else:
            try:
                with mp.workdps(180), high_precision_mode(), runtime_session(started + 90):
                    result = verify_final_candidate(evaluator=evaluator, values=c.x_hp)
                row.update(final_pass=result.verified, status=result.status,
                    normalized_residual=textnum(result.normalized_residual), precision_dps=result.precision_dps,
                    hard_feasible=result.hard_feasible, hard_failure_tags=result.hard_failure_tags,
                    answer=textnum(result.answer_hp))
            except TimeoutError:
                row["status"] = "deadline_reached"
            except Exception as e:
                row.update(status="error", error=repr(e))
        row["seconds"] = time.monotonic() - t0
        rows.append(row)
        save(ARM + ".verification.json", {"source_hash": SOURCE,
            "seconds": time.monotonic()-started, "complete": len(rows) == len(candidates), "rows": rows})
    if not candidates:
        save(ARM + ".verification.json", {"source_hash": SOURCE, "seconds": time.monotonic()-started, "complete": True, "rows": []})
else:
    raise ValueError(MODE)
