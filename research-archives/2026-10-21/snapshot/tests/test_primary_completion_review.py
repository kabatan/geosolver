"""Independent cutoff and evidence review of optional-to-primary completion."""

import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from mpmath import mp
from test_algebraic_completion_provenance import outcome, pipeline, refined, source

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.runtime import worker
from geosolver.runtime.deadline import retain_candidates
from geosolver.runtime.protocol import WorkerRequest


def configs():
    first = SimpleNamespace(
        global_search_mode="disco_mads", search=SimpleNamespace(seed_values=(43,))
    )
    second = SimpleNamespace(
        global_search_mode="hybrid", search=SimpleNamespace(seed_values=(43, 44, 45))
    )
    return (
        pipeline._OrderedSearchAttemptDescriptor("primary", "primary", first, 43),
        pipeline._OrderedSearchAttemptDescriptor("hybrid_fallback", "fallback", second, 143),
    )


def completed(stage):
    return pipeline._CompletedPipelineStageState(
        initial_probe_result=stage.initial_probe_result,
        search_result=stage.search_result,
        refinement_result=stage.refinement_result,
        exact_assembly_result=stage.exact_assembly_result,
        rescue_search_summary={},
        integer_fallback_summary={},
    )


@pytest.mark.parametrize("numeric_has_answer", [False, True])
def test_normal_deadline_during_numeric_primary_retains_original_evidence(
    monkeypatch, numeric_has_answer
):
    primary, hybrid = configs()
    a, unresolved = source(1), source(2)
    n = source(3, backend="nomad", attempt=2)
    first = outcome(primary, (a, unresolved), (refined(a),), ("1",)).completed_stage_state
    second = outcome(
        primary,
        (n,),
        (refined(n),) if numeric_has_answer else (),
        ("3",) if numeric_has_answer else (),
    ).completed_stage_state
    remaining = [100]
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        if kwargs["allow_algebraic"]:
            return first
        assert kwargs["pipeline_config"] is primary.pipeline_config
        assert kwargs["seed_base"] == primary.initial_probe_seed_base
        remaining[0] = 0
        return second

    monkeypatch.setattr(pipeline, "_run_pipeline_stage", run)
    monkeypatch.setattr(pipeline, "_complete_pipeline_stage", lambda **kw: kw["stage_state"])
    result = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, hybrid),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: remaining[0]),
    )
    assert len(calls) == 2 and not result.fallback_triggered
    assembly = result.selected_outcome.completed_stage_state.exact_assembly_result
    assert assembly.accepted_candidates[0] is first.exact_assembly_result.accepted_candidates[0]
    assert assembly.candidate_records[0] is first.exact_assembly_result.candidate_records[0]
    assert assembly.verification_records[0] is first.exact_assembly_result.verification_records[0]
    assert assembly.accepted_candidates[0].revision == 2
    assert assembly.accepted_candidates[0].source.originating_branch_box == a.originating_branch_box
    assert (
        assembly.accepted_candidates[0].candidate_key
        == first.exact_assembly_result.accepted_candidates[0].candidate_key
    )


@pytest.mark.parametrize("hybrid_has_answer", [False, True])
def test_optional_verified_records_survive_an_empty_or_successful_hybrid(
    monkeypatch, hybrid_has_answer
):
    primary, hybrid = configs()
    a, unresolved = source(1), source(2)
    n = source(3, backend="nomad", attempt=2)
    h = source(4, backend="scipy", attempt=1)
    first = outcome(primary, (a, unresolved), (refined(a),), ("1",)).completed_stage_state
    numeric = outcome(primary, (n,), (), ()).completed_stage_state
    fallback = outcome(
        hybrid,
        (h,),
        (refined(h),) if hybrid_has_answer else (),
        ("4",) if hybrid_has_answer else (),
    ).completed_stage_state

    def run(**kwargs):
        if kwargs["allow_algebraic"]:
            return first
        return numeric if kwargs["pipeline_config"] is primary.pipeline_config else fallback

    monkeypatch.setattr(pipeline, "_run_pipeline_stage", run)
    monkeypatch.setattr(pipeline, "_complete_pipeline_stage", lambda **kw: kw["stage_state"])
    result = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, hybrid),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: 100),
    )
    assert result.fallback_triggered
    selected = result.selected_outcome.completed_stage_state
    assembly = selected.exact_assembly_result
    assert assembly.accepted_candidates[0] is first.exact_assembly_result.accepted_candidates[0]
    assert assembly.verification_records[0] is first.exact_assembly_result.verification_records[0]
    assert selected.search_result.all_records == (a, unresolved, n, h)
    assert len(assembly.accepted_candidates) == 1 + int(hybrid_has_answer)
    assert result.selected_outcome.attempt is hybrid


@pytest.mark.parametrize(
    "cutoff",
    [
        "numeric_start",
        "numeric_after_assembly",
        "numeric_completion",
        "hybrid_start",
        "hybrid_after_assembly",
    ],
)
def test_worker_cutoff_preserves_atomic_descriptors_revisions_and_branch_evidence(
    monkeypatch, cutoff
):
    primary, hybrid = configs()
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constraints": ["(x-2)*(x-4)"],
                "answer": "x+1",
            }
        )
    )
    observed_attempts = []
    saved = {}

    def point(value, backend):
        return FloatCandidate(
            (float(value),),
            0,
            0,
            True,
            EvaluationStatus.OK,
            43,
            int(value),
            candidate_id=17,
            origin_backend=backend,
            originating_branch_box=((str(value - 0.25), str(value + 0.25)),),
        )

    def stage(proposals, accepted_source=None):
        candidates = (
            ()
            if accepted_source is None
            else (
                RefinedCandidate(
                    (mp.mpf(accepted_source.x_float[0]),),
                    mp.mpf(0),
                    mp.mpf(999),
                    "stalled",
                    (),
                    source=accepted_source,
                    candidate_id=17,
                ),
            )
        )
        assembly = assemble_exact_results(refined_candidates=candidates, evaluator=evaluator)
        return pipeline._PipelineStageState(
            InitialProbeResult(tuple(proposals), {}),
            SearchBatchResult(tuple(proposals), len(proposals), 0, all_records=tuple(proposals)),
            RefinementBatchResult(candidates, len(candidates), len(candidates)),
            assembly,
        )

    def run(**kwargs):
        marker = point(2, "marker")
        observed_attempts.append(marker.origin_attempt)
        if kwargs["allow_algebraic"]:
            a, unresolved = point(2, "exact_polynomial"), point(4, "exact_polynomial")
            optional = stage((a, unresolved), a)
            saved["optional"] = optional.exact_assembly_result.accepted_candidates[0]
            return optional
        is_numeric = kwargs["pipeline_config"] is primary.pipeline_config
        if is_numeric and cutoff == "numeric_start":
            # A later invalid draft must never replace the accepted revision.
            old = saved["optional"]
            retain_candidates(
                (
                    replace(
                        old, x_hp=(mp.mpf(99),), answer_hp=mp.mpf(100), revision=old.revision + 1
                    ),
                )
            )
            raise TimeoutError("numeric search cutoff")
        if not is_numeric and cutoff == "hybrid_start":
            raise TimeoutError("hybrid search cutoff")
        original = point(4, "nomad" if is_numeric else "scipy")
        result = stage(
            (original,), original if cutoff.startswith("numeric") or not is_numeric else None
        )
        if (is_numeric and cutoff == "numeric_after_assembly") or (
            not is_numeric and cutoff == "hybrid_after_assembly"
        ):
            raise TimeoutError("cutoff after atomic exact descriptor")
        return result

    def finish(**kwargs):
        if cutoff == "numeric_completion":
            raise TimeoutError("numeric completion cutoff")
        return completed(kwargs["stage_state"])

    def execute_pipeline(*args, **kwargs):
        return pipeline._run_ordered_search_attempts(
            ordered_attempts=(primary, hybrid),
            bundle=None,
            evaluator=evaluator,
            bounds=[(-10, 10)],
            refiner=None,
            runtime_budget=SimpleNamespace(remaining_sec=lambda: 100),
        )

    monkeypatch.setattr(pipeline, "_run_pipeline_stage", run)
    monkeypatch.setattr(pipeline, "_complete_pipeline_stage", finish)
    monkeypatch.setattr(worker, "run_external_pipeline", execute_pipeline)
    artifact = worker.execute(
        WorkerRequest(engine_document={}, deadline_monotonic=time.monotonic() + 30)
    )
    assert artifact.status == "completed" and artifact.public_solved
    assert artifact.termination_reason == "time_limit_reached"
    assert "3" in artifact.exact_candidates
    expected_count = (
        2
        if cutoff in {"numeric_after_assembly", "numeric_completion", "hybrid_after_assembly"}
        else 1
    )
    accepted_records = [record for record in artifact.candidate_records if record["accepted"]]
    assert len(artifact.answers) == expected_count
    assert len(accepted_records) == expected_count
    by_attempt = {record["source"]["origin_attempt"]: record for record in accepted_records}
    original = by_attempt[0]
    assert mp.mpf(original["x_hp"][0]) == 2
    assert mp.mpf(original["answer_hp"]) == 3
    assert original["revision"] == saved["optional"].revision
    assert original["source"]["originating_branch_box"] == [["1.75", "2.25"]]
    evidence = artifact.diagnostics["pipeline_summary"]["verification_records"]
    assert any(
        item["candidate_uid"] == original["candidate_uid"] and item["verified"] for item in evidence
    )
    assert len({record["candidate_uid"] for record in accepted_records}) == expected_count
    assert observed_attempts == ([0, 2, 1] if cutoff.startswith("hybrid") else [0, 2])
