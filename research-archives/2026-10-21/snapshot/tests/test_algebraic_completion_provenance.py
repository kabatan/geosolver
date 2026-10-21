"""Completion follows root provenance while retaining verified answer records."""

import importlib
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

pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")


def source(index, *, backend="exact_polynomial", attempt=0):
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


def refined(origin):
    return RefinedCandidate(
        (mp.mpf(origin.x_float[0]),),
        mp.mpf(0),
        mp.mpf(1),
        "target_reached",
        (),
        source=origin,
        candidate_id=origin.candidate_id,
        hard_feasible=True,
        revision=2,
        coordinate_uncertainty=(mp.mpf("1e-60"),),
    )


def outcome(attempt, proposals, accepted, values):
    assembly = ExactAssemblyResult(
        accepted,
        accepted,
        tuple(values),
        tuple(SimpleNamespace(candidate=c) for c in accepted),
        tuple(values),
        0,
        (),
        tuple({"candidate_uid": c.candidate_uid, "verified": True} for c in accepted),
    )
    stage = pipeline._CompletedPipelineStageState(
        initial_probe_result=None,
        search_result=SearchBatchResult(proposals, len(proposals), 0, all_records=proposals),
        refinement_result=RefinementBatchResult(accepted, len(accepted), len(accepted)),
        exact_assembly_result=assembly,
        rescue_search_summary={},
        integer_fallback_summary={},
    )
    return pipeline._OrderedSearchAttemptOutcome(attempt, stage)


@pytest.mark.parametrize("values", [("1", "2"), ("7", "7")])
def test_partial_polynomial_verification_runs_numeric_fallback_and_unions_records(
    monkeypatch, values
):
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    fallback = pipeline._OrderedSearchAttemptDescriptor("hybrid_fallback", "fallback", None, None)
    a, unresolved = source(1), source(2)
    b = source(3, backend="scipy", attempt=1)
    first = outcome(primary, (a, unresolved), (refined(a),), values[:1])
    second = outcome(fallback, (b,), (refined(b),), values[1:])
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
    assert calls == [primary, fallback]
    selected = result.selected_outcome.completed_stage_state
    assert selected.exact_assembly_result.answer_values == values
    assert {c.source.candidate_key for c in selected.exact_assembly_result.accepted_candidates} == {
        a.candidate_key,
        b.candidate_key,
    }
    assert len(selected.exact_assembly_result.candidate_records) == 2
    assert all(c.revision == 2 for c in selected.exact_assembly_result.accepted_candidates)
    assert len(selected.exact_assembly_result.verification_records) == 2
    assert selected.refinement_result.attempted_count == 2


def test_two_verified_configurations_with_one_target_value_do_not_trigger_fallback(monkeypatch):
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    fallback = pipeline._OrderedSearchAttemptDescriptor("hybrid_fallback", "fallback", None, None)
    a, b = source(1), source(2)
    first = outcome(primary, (a, b), (refined(a), refined(b)), ("7", "7"))
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["attempt"])
        return first

    monkeypatch.setattr(pipeline, "_execute_ordered_search_attempt", execute)
    result = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, fallback),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: 100),
    )
    assert calls == [primary]
    assert result.selected_outcome is first


def test_algebraic_discovery_is_primary_only(monkeypatch):
    seen = []
    stage = SimpleNamespace(search_result=SearchBatchResult((), 0, 0))

    def run(**kwargs):
        seen.append(kwargs["allow_algebraic"])
        return stage

    monkeypatch.setattr(pipeline, "_run_pipeline_stage", run)
    monkeypatch.setattr(pipeline, "_complete_pipeline_stage", lambda **_: stage)
    for attempt_id in ("primary", "hybrid_fallback"):
        attempt = pipeline._OrderedSearchAttemptDescriptor(attempt_id, attempt_id, None, None)
        pipeline._execute_ordered_search_attempt(
            attempt=attempt,
            bundle=None,
            evaluator=None,
            bounds=[],
            refiner=None,
            runtime_budget=None,
        )
    assert seen == [True, False]


@pytest.mark.parametrize("numeric_accepts", [True, False])
def test_incomplete_prepass_completes_original_primary_before_hybrid(monkeypatch, numeric_accepts):
    config = SimpleNamespace(
        global_search_mode="disco_mads", search=SimpleNamespace(seed_values=(37,))
    )
    hybrid_config = SimpleNamespace(
        global_search_mode="hybrid", search=SimpleNamespace(seed_values=(37, 38, 39))
    )
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", config, 37)
    fallback = pipeline._OrderedSearchAttemptDescriptor(
        "hybrid_fallback", "fallback", hybrid_config, 137
    )
    a, unresolved = source(1), source(2)
    numeric = source(3, backend="nomad", attempt=2)
    hybrid = source(4, backend="scipy", attempt=1)
    optional_stage = outcome(primary, (a, unresolved), (refined(a),), ("1",)).completed_stage_state
    numeric_stage = outcome(
        primary,
        (numeric,),
        (refined(numeric),) if numeric_accepts else (),
        ("3",) if numeric_accepts else (),
    ).completed_stage_state
    hybrid_stage = outcome(fallback, (hybrid,), (refined(hybrid),), ("4",)).completed_stage_state
    calls, completions = [], []

    def run(**kwargs):
        # A fresh proposal captures the current candidate-attempt context.
        marker = FloatCandidate((0.0,), 0, 0, True, EvaluationStatus.OK, 0, 0)
        calls.append(
            (
                kwargs["pipeline_config"],
                kwargs["seed_base"],
                kwargs["allow_algebraic"],
                marker.origin_attempt,
            )
        )
        if kwargs["allow_algebraic"]:
            return optional_stage
        return numeric_stage if kwargs["pipeline_config"] is config else hybrid_stage

    def complete(**kwargs):
        completions.append(kwargs["stage_state"])
        return kwargs["stage_state"]

    monkeypatch.setattr(pipeline, "_run_pipeline_stage", run)
    monkeypatch.setattr(pipeline, "_complete_pipeline_stage", complete)
    selected = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, fallback),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: 100),
    ).selected_outcome.completed_stage_state
    expected_calls = [(config, 37, True, 0), (config, 37, False, 2)]
    if not numeric_accepts:
        expected_calls.append((hybrid_config, 137, False, 1))
    assert calls == expected_calls
    assert completions == ([numeric_stage] if numeric_accepts else [numeric_stage, hybrid_stage])
    assert selected.exact_assembly_result.answer_values == (
        ("1", "3") if numeric_accepts else ("1", "4")
    )
    assert len(selected.exact_assembly_result.verification_records) == 2
    assert all(c.revision == 2 for c in selected.exact_assembly_result.accepted_candidates)
    assert not pipeline._algebraic_provenance_incomplete(selected)
    expected_records = (
        (a, unresolved, numeric) if numeric_accepts else (a, unresolved, numeric, hybrid)
    )
    assert selected.search_result.all_records == expected_records


def test_expired_prepass_retains_verified_records_without_starting_new_search(monkeypatch):
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    fallback = pipeline._OrderedSearchAttemptDescriptor("hybrid_fallback", "fallback", None, None)
    a, unresolved = source(1), source(2)
    stage = outcome(primary, (a, unresolved), (refined(a),), ("1",)).completed_stage_state
    calls = []

    def run(**kwargs):
        calls.append(kwargs["allow_algebraic"])
        return stage

    monkeypatch.setattr(pipeline, "_run_pipeline_stage", run)
    monkeypatch.setattr(
        pipeline, "_complete_pipeline_stage", lambda **kwargs: kwargs["stage_state"]
    )
    selected = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, fallback),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: 0),
    ).selected_outcome.completed_stage_state
    assert calls == [True]
    assert selected.exact_assembly_result.accepted_candidates == (refined(a),)
    assert (
        selected.exact_assembly_result.verification_records
        == stage.exact_assembly_result.verification_records
    )
