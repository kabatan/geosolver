"""Frozen refiner + final verification, followed by full worker with a warm proposal."""
from common import *
import resource
import time
from mpmath import mp
from warm_worker import proposal, near_point
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.runtime.deadline import runtime_session
from geosolver.runtime.worker import _json_value

def local(cid, sign):
    bundle = load_problem_bundle(problem(cid).engine_document())
    evaluator = build_ir_evaluator(bundle)
    c = proposal(evaluator, sign)
    started = time.monotonic()
    deadline = started + 180
    with mp.workdps(180), runtime_session(deadline) as timings:
        refined = MpmathRefiner().refine_candidates(bundle=bundle,evaluator=evaluator,
            candidates=(c,),deadline_monotonic=deadline-30)
        phase_c = assemble_exact_results(refined_candidates=refined.candidates,evaluator=evaluator,
            input_precision_dps=120,deadline_monotonic=deadline)
    elapsed = time.monotonic()-started
    data = _json_value(dict(experiment="posthoc_original_DSL_near_local_B_C", id=cid,
        sign=sign, perturbation="x_i + sign * 0.01 * (-1)^i; every variable including integer witnesses",
        input_candidate=c, refiner=refined, completion=phase_c, elapsed_seconds=elapsed,
        time_limit_seconds=180, timings=dict(timings), counters=timings.counters))
    save(HERE / "local" / f"{cid}-sign-{sign}.json", data)
    print(cid,'local',sign,'answers',phase_c.answer_values,'seconds',round(elapsed,3),flush=True)

def warm(cid):
    from geosolver.application.service import solve
    from geosolver.engine.runner import EngineRunner
    os.environ['PYTHONPATH'] = os.pathsep.join([str(HERE),str(ROOT / 'src'),str(ROOT)])
    result = solve(problem(cid),dict(seed=2901,time_limit_seconds=180,cores=1),
        runner=EngineRunner(worker_module="warm_worker",memory_limit_bytes=2*1024**3))
    data = result.model_dump(mode="json")
    save(HERE / "warm-full" / f"{cid}.json",dict(experiment="posthoc_warm_full_worker",
        intervention="Only discovery replaced with one analytic witness perturbed by +/-0.01; see warm_worker.py",
        original_DSL=True, solver_src=FROZEN, time_limit_seconds=180, cpu=3,
        near_point=near_point(cid,problem(cid).variables), solver_result=data))
    print(cid,'warm_full',data['status'],data['answers'],'seconds',round(data['elapsed_seconds'],3),flush=True)

if __name__ == "__main__":
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_FSIZE,(4_900_000,4_900_000))
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    identity()
    for cid in IDS:
        for sign in (1,-1):
            local(cid,sign)
        warm(cid)
