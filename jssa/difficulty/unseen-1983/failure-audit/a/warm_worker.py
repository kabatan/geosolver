"""Diagnostic-only worker: replace discovery with ONE perturbed analytic witness.

No answer is supplied. The original production refinement, exact identification,
verification, output handling, and 180s deadline run unchanged. The four replaced
proposal functions are explicit below; this is NOT an ordinary frozen-score run.
"""
from common import *
from mpmath import mp
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
import importlib

def near_point(cid, var_names, sign=1):
    with mp.workdps(100):
        values = witness(cid)
        # Absolute perturbation avoids moving the large integer witnesses by whole integers.
        return tuple(float(values[n] + sign*mp.mpf("0.01")*(-1 if i % 2 else 1))
                     for i,n in enumerate(var_names))

def proposal(evaluator, sign=1):
    x = near_point(evaluator.bundle.problem_id, evaluator.bundle.var_names, sign)
    residual = evaluator.evaluate_float_residual(x)
    hard = evaluator.evaluate_float_hard_feasibility(x)
    guard, tags = evaluator.evaluate_guard(x)
    return FloatCandidate(x_float=x, score=residual.residual_norm_float,
        residual_norm_float=residual.residual_norm_float, guard_ok=guard,
        evaluation_status=residual.evaluation_status, origin_seed=2901,
        origin_start_point_index=0, candidate_id=0, hard_feasible=hard.hard_feasible,
        hard_violation_tags=hard.failure_tags, origin_phase="Q29a_warm_start",
        origin_backend="analytic_witness_plus_absolute_0.01")

def probe(*, evaluator, **kwargs):
    return InitialProbeResult(candidates=(proposal(evaluator),), metrics={"oracle_near_start":True})

def search(*, initial_probe_result, **kwargs):
    cs = initial_probe_result.candidates
    return SearchBatchResult(candidates=cs, evaluation_count=1, failure_ratio=0,
        all_records=cs, guard_feasible_ledger=tuple(c for c in cs if c.guard_ok),
        search_diagnostics={"oracle_near_start":True,"discovery_replaced":True})

def install():
    pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")
    algebraic = importlib.import_module("geosolver.engine.standard.search.algebraic_branches")
    algebraic.search_algebraic_branches = lambda **kwargs: None
    pipeline.run_initial_probe = probe
    pipeline.augment_initial_probe_with_exact_distance_samples = lambda **kwargs: kwargs['initial_probe_result']
    pipeline.run_search = search

if __name__ == "__main__":
    install()
    from geosolver.runtime.worker import main
    main()
