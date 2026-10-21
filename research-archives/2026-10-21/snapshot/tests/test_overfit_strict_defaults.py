"""Removing development-tuned samplers must preserve ordinary search evidence."""

import importlib
from types import SimpleNamespace

import pytest
from mpmath import mp
from test_integer_segment_branches import make_problem

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.discrete.lattice_segments import integer_segment_branches
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.sampling.manifold import DEFAULT_MANIFOLD_SAMPLE_STRATEGIES
from geosolver.problem.adapter import to_engine_document


def test_default_portfolio_does_not_run_positive_radius_projection_or_brackets():
    identifiers = {strategy.strategy_id for strategy in DEFAULT_MANIFOLD_SAMPLE_STRATEGIES}
    assert "positive_radius_contact_manifold" not in identifiers
    assert "affine_guard_interior" in identifiers


@pytest.mark.parametrize("vector", [(2, 3), (3, 4), (2, 5)])
def test_each_finite_displacement_gets_at_most_one_canonical_unit_witness(vector):
    problem = make_problem(vector, (0, 0), 0)
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    plan = integer_segment_branches(bundle)
    assert plan is not None and plan.total_displacements > 0
    assert len(plan.branches) + plan.excluded_displacements == plan.total_displacements
    assert all(len(branch) <= 1 for branch in plan.branches)


def test_guard_rejecting_unit_witness_keeps_far_ordinary_candidate_and_all_evidence(monkeypatch):
    module = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    problem = make_problem((2, 3), (0, 0), 0)
    problem["conditions"].append({"left": "Distance(P,Q)", "operator": ">", "right": "10000"})
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    # BC=(3,2), so AD-BC=(-1,1); this far witness lies on the same
    # integer line while every canonical unit witness fails the length guard.
    point = (-10001.0, 10001.0, -9998.0, 10003.0)
    verification = verify_final_candidate(evaluator=evaluator, values=tuple(map(mp.mpf, point)))
    assert verification.verified
    original = FloatCandidate(point, 0, 0, True, EvaluationStatus.OK, 0, 0, 123, hard_feasible=True)
    baseline = SearchBatchResult(
        candidates=(original,),
        all_records=(original,),
        guard_feasible_ledger=(original,),
        evaluation_count=7,
        evaluation_failure_count=2,
        failure_ratio=2 / 7,
        search_diagnostics={"ordinary": "retained"},
    )
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return baseline

    monkeypatch.setattr(
        module, "_build_search_backend", lambda **kwargs: SimpleNamespace(run_search=run)
    )
    result = module._run_search_baseline(
        bundle=bundle,
        evaluator=evaluator,
        bounds=[(-1000000.0, 1000000.0)] * 4,
        initial_probe_result=InitialProbeResult((original,), {}),
        config=NomadConfig(max_bb_eval=1000, seed_values=(0,)),
    )
    assert len(calls) == 1
    assert original in result.candidates
    assert original in result.all_records
    assert original in result.guard_feasible_ledger
    assert result.search_diagnostics["ordinary"] == "retained"
    assert result.failed_evaluations >= baseline.failed_evaluations
    assert not result.search_diagnostics["integer_segment_displacements"][
        "all_displacements_covered"
    ]


@pytest.mark.parametrize("allow_integer_shortcuts", [False, True])
@pytest.mark.parametrize("search_mode", ["disco_mads", "scipy_multistart", "hybrid_legacy_nomad"])
def test_production_search_cannot_reach_experimental_segment_helper(
    monkeypatch, allow_integer_shortcuts, search_mode
):
    from geosolver.engine.standard.search import scale_chart
    from geosolver.engine.standard.search.discrete import lattice_segments

    module = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    problem = make_problem((2, 3), (0, 0), 0)
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    point = (-10001.0, 10001.0, -9998.0, 10003.0)
    original = FloatCandidate(point, 0, 0, True, EvaluationStatus.OK, 0, 0, 123, hard_feasible=True)
    baseline = SearchBatchResult((original,), 1, 0, (original,), (original,))
    calls = []

    def forbidden(**kwargs):
        pytest.fail("production reached excluded integer-segment helper")

    def run(**kwargs):
        calls.append(kwargs)
        return baseline

    monkeypatch.setattr(lattice_segments, "scan_integer_segments", forbidden)
    monkeypatch.setattr(scale_chart, "search_positive_scale_chart", lambda **kwargs: None)
    monkeypatch.setattr(
        module, "_build_search_backend", lambda **kwargs: SimpleNamespace(run_search=run)
    )
    monkeypatch.setattr(module, "NomadBackend", lambda **kwargs: SimpleNamespace(run_search=run))
    monkeypatch.setattr(
        module,
        "_run_supplemental_search_pass",
        lambda **kwargs: module._empty_search_batch_result(),
    )
    result = module.run_search(
        bundle=bundle,
        evaluator=evaluator,
        bounds=[(-1000000.0, 1000000.0)] * 4,
        initial_probe_result=InitialProbeResult((original,), {}),
        config=NomadConfig(max_bb_eval=1000, seed_values=(0,)),
        search_mode=search_mode,
        allow_integer_shortcuts=allow_integer_shortcuts,
    )
    assert len(calls) == 1
    assert original in result.candidates
    assert original in result.all_records
    assert original in result.guard_feasible_ledger
