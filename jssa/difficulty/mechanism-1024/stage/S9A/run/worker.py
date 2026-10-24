"""S1 stage worker; imports only the source selected by driver PYTHONPATH."""
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
resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
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
assert SOURCE == M["base_source_hash" if MODE == "search" else "source_hash" if MODE == "refine" else "frozen_source_hash"]
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
    return dict(pid=os.getpid(),affinity=sorted(os.sched_getaffinity(0)),threads=int(next(line.split(':')[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('Threads:'))),environment={k:v for k,v in os.environ.items() if k.startswith(('GEOSOLVER_ABLATE_','GEOSOLVER_S3_','GEOSOLVER_S7_'))},source_hash=SOURCE)
save(MODE + ('.'+ARM if ARM else '')+'.runtime-start.json',runtime_receipt())
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

elif MODE == "refine":
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
    from geosolver.runtime.deadline import runtime_session
    candidates, config = load("initial.pkl")
    bundle, evaluator = ordinary()
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
    save(ARM + ".refinement.json", {"source_hash": SOURCE, "arm": ARM,
        "initial_sha256": hashlib.sha256((D / "initial.pkl").read_bytes()).hexdigest(),
        "seconds": seconds, "deadline_hit": seconds >= 90,
        "attempted": result.attempted_count, "returned": len(result.candidates),
        "converged": result.converged_count, "hard_feasible": result.hard_feasible_count,
        "unattempted": len(candidates) - result.attempted_count, "candidate_seconds": timings})

elif MODE == "initial":
    from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf, BoundaryOrigin
    candidates,config=load("initial.pkl")
    bundle,evaluator=ordinary()
    rows=[]
    with mp.workdps(180):
        for i,c in enumerate(candidates):
            row=dict(rank=i,candidate_uid=c.candidate_uid,candidate_id=c.candidate_id)
            try:
                point=tuple(boundary_float_to_mpf(v,origin=BoundaryOrigin.INITIAL_POINT) for v in c.x_float)
                ev=evaluator.evaluate_hp_residual(point,precision=180)
                row['residual_norm']=textnum(ev.residual_norm_hp)
            except Exception as e:row['error']=repr(e)
            rows.append(row)
        values=[mp.mpf(r['residual_norm']) for r in rows if 'residual_norm' in r]
        values=[v if mp.isfinite(v) else mp.inf for v in values]
        values.sort()
        median=(values[len(values)//2] if len(values)%2 else (values[len(values)//2-1]+values[len(values)//2])/2) if values and len(values)==len(rows) else None
        save('initial-metrics.json',dict(source_hash=SOURCE,count=len(rows),config_repr=repr(config),median_residual=textnum(median),rows=rows))

elif MODE == "measure":
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
    _,evaluator=ordinary()
    started=time.monotonic()
    rows=[]
    with mp.workdps(700):
        refs=[_eval_exact_to_mpf(r,700) for r in TASK['reference_expressions']]
        assert refs and all(r is not None and mp.isfinite(r) for r in refs), 'reference evaluation unavailable'
    candidates=load(ARM+'.refined.pkl')
    with mp.workdps(700),high_precision_mode():
        for i,c in enumerate(candidates):
            row=dict(case_id=CASE,seed=0,arm=ARM,rank=i,candidate_id=c.candidate_id,candidate_uid=c.candidate_uid,source_uid=c.source.candidate_uid if c.source else None,status=c.refinement_status,hard_feasible=c.hard_feasible,immediate_pass=c.refinement_status=='target_reached' and c.hard_feasible is True,solver_residual=textnum(c.residual_norm_hp),coordinate_dps=c.coordinate_precision_dps)
            try:
                answer=evaluator.evaluate_answer_hp(c.x_hp,precision=700).answer_hp
                if answer is None or not mp.isfinite(answer):raise ValueError('nonfinite or unavailable answer')
                errors=[abs(answer-ref) for ref in refs];error=min(errors)
                digits=min(mp.mpf(600),-mp.log10(error)) if error else mp.mpf(600)
                row.update(answer=textnum(answer),absolute_error=textnum(error),error_digits=float(str(digits)),error_digits_exact=textnum(digits),nearest_reference=errors.index(error))
            except Exception as e:row['answer_error']=repr(e)
            rows.append(row)
            save(ARM+'.measure.json',dict(source_hash=SOURCE,seconds=time.monotonic()-started,complete=len(rows)==len(candidates),rows=rows))
    if not candidates:save(ARM+'.measure.json',dict(source_hash=SOURCE,seconds=time.monotonic()-started,complete=True,rows=[]))

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

save(MODE+("."+ARM if ARM else "")+".runtime-end.json",runtime_receipt())
