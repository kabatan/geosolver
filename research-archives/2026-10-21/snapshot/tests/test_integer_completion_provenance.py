"""Finite integer proposals need original verification for each root identity."""

import importlib
from dataclasses import replace
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.orchestration.assemble_exact_results import ExactAssemblyResult
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
from geosolver.engine.standard.search.nomad_config import NomadConfig

pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")
search = importlib.import_module("geosolver.engine.standard.orchestration.run_search")


def proposal(index, backend, attempt=0):
    return FloatCandidate(
        (float(index),),
        0,
        0,
        True,
        EvaluationStatus.OK,
        0,
        index,
        candidate_id=index,
        origin_backend=backend,
        origin_attempt=attempt,
        originating_branch_box=((str(index - 0.25), str(index + 0.25)),),
    )


def accepted(origin, coordinate=None):
    return RefinedCandidate(
        (mp.mpf(origin.x_float[0] if coordinate is None else coordinate),),
        mp.mpf(0),
        mp.mpf(7),
        "target_reached",
        (),
        source=origin,
        candidate_id=origin.candidate_id,
        hard_feasible=True,
        revision=2,
        coordinate_uncertainty=(mp.mpf("1e-60"),),
    )


def outcome(attempt, proposals, verified):
    values = tuple("7" for _ in verified)
    assembly = ExactAssemblyResult(
        verified,
        verified,
        values,
        tuple(SimpleNamespace(candidate=c) for c in verified),
        values,
        0,
        (),
        tuple({"candidate_uid": c.candidate_uid, "verified": True} for c in verified),
    )
    stage = pipeline._CompletedPipelineStageState(
        initial_probe_result=None,
        search_result=SearchBatchResult(proposals, len(proposals), 0, all_records=proposals),
        refinement_result=RefinementBatchResult(verified, len(verified), len(verified)),
        exact_assembly_result=assembly,
        rescue_search_summary={},
        integer_fallback_summary={},
    )
    return pipeline._OrderedSearchAttemptOutcome(attempt, stage)


@pytest.mark.parametrize("backend", ["integer_square_difference", "integer_segment_displacements"])
@pytest.mark.parametrize("verification", ["missing", "drifted", "complete"])
def test_integer_roots_only_skip_fallback_after_every_origin_is_independently_verified(
    monkeypatch, backend, verification
):
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    fallback = pipeline._OrderedSearchAttemptDescriptor("hybrid_fallback", "fallback", None, None)
    a, b = proposal(1, backend), proposal(2, backend)
    verified = (accepted(a),)
    if verification != "missing":
        verified += (accepted(b, 1 if verification == "drifted" else 2),)
    first = outcome(primary, (a, b), verified)
    c = proposal(3, "scipy", attempt=1)
    second = outcome(fallback, (c,), (accepted(c),))
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["attempt"])
        return first if kwargs["attempt"] is primary else second

    monkeypatch.setattr(pipeline, "_execute_ordered_search_attempt", execute)
    result = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, fallback),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: 100),
    )
    assert calls == ([primary] if verification == "complete" else [primary, fallback])
    if verification != "complete":
        combined = result.selected_outcome.completed_stage_state.exact_assembly_result
        assert combined.accepted_candidates == verified + (accepted(c),)
        assert len(combined.verification_records) == len(verified) + 1


def batch(candidates, diagnostics=None):
    return SearchBatchResult(
        tuple(candidates),
        len(candidates),
        0,
        all_records=tuple(candidates),
        guard_feasible_ledger=tuple(candidates),
        search_diagnostics=diagnostics or {},
    )


def disable_other_proposals(monkeypatch):
    from geosolver.engine.standard.search import finite_guard_search, scale_chart

    monkeypatch.setattr(finite_guard_search, "search_finite_guards", lambda **_: None)
    monkeypatch.setattr(scale_chart, "search_positive_scale_chart", lambda **_: None)


@pytest.mark.parametrize("complete", [False, True])
def test_partial_float_filtering_of_finite_roots_preserves_ordinary_backend(monkeypatch, complete):
    from geosolver.engine.standard.search.discrete import square_difference

    a = proposal(1, "integer_square_difference")
    b = proposal(2, "ordinary")
    discrete = batch((a,), {"integer_square_difference": {"all_finite_seeds_admissible": complete}})
    ordinary = batch((b,))
    calls = []
    monkeypatch.setattr(square_difference, "scan_integer_square_branches", lambda **_: discrete)
    monkeypatch.setattr(
        search,
        "_build_search_backend",
        lambda **_: SimpleNamespace(run_search=lambda **kw: calls.append(kw) or ordinary),
    )
    disable_other_proposals(monkeypatch)
    result = search.run_search(
        bundle=None,
        evaluator=None,
        bounds=[(-10, 10)],
        initial_probe_result=InitialProbeResult((a,), {}),
        config=replace(NomadConfig(max_bb_eval=1), seed_values=(0,)),
    )
    assert len(calls) == (0 if complete else 1)
    assert result.candidates == ((a,) if complete else (a, b))


@pytest.mark.parametrize("dimensions", [1, 4])
def test_numeric_completion_cannot_reenter_integer_early_return(monkeypatch, dimensions):
    from geosolver.engine.standard.search.discrete import lattice_segments, square_difference

    def forbidden(**kwargs):
        raise AssertionError("integer enumeration reentered numeric completion")

    monkeypatch.setattr(square_difference, "scan_integer_square_branches", forbidden)
    monkeypatch.setattr(lattice_segments, "scan_integer_segments", forbidden)
    disable_other_proposals(monkeypatch)
    calls = []
    original = replace(proposal(1, "ordinary"), x_float=(1.0,) * dimensions)
    ordinary = batch((original,))
    monkeypatch.setattr(
        search,
        "_build_search_backend",
        lambda **_: SimpleNamespace(run_search=lambda **kw: calls.append(kw) or ordinary),
    )
    result = search.run_search(
        bundle=None,
        evaluator=None,
        bounds=[(-10, 10)] * dimensions,
        initial_probe_result=InitialProbeResult((original,), {}),
        config=replace(NomadConfig(max_bb_eval=1), seed_values=(0,)),
        allow_integer_shortcuts=False,
    )
    assert calls and result.candidates == (original,)


def test_float_rejected_square_root_remains_a_mathematical_completion_obligation():
    attempt = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    a, rejected = proposal(1, "integer_square_difference"), proposal(2, "integer_square_difference")
    first = outcome(attempt, (a,), (accepted(a),))
    stage = first.completed_stage_state
    stage = replace(stage, search_result=replace(stage.search_result, all_records=(a, rejected)))
    assert pipeline._algebraic_provenance_incomplete(stage)
