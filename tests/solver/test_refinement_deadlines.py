"""Refinement deadlines contracts and numerical regressions."""

import time
from dataclasses import replace

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import mpmath_refiner as implementation
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.engine.standard.refinement.refiner_config import RefinerConfig
from geosolver.runtime.deadline import runtime_session


def fixture(*, nonlinear=False):
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constraints": ["x*x-2" if nonlinear else "x-2"],
                "answer": "x",
            }
        )
    )
    candidate = FloatCandidate(
        x_float=(2.0,),
        score=4.0,
        residual_norm_float=2.0,
        guard_ok=True,
        evaluation_status=EvaluationStatus.OK,
        origin_seed=0,
        origin_start_point_index=0,
        candidate_id=7,
    )
    refiner = MpmathRefiner(
        RefinerConfig(
            schedule_dps=(50,),
            closure_schedule_dps=(),
            max_stage_iters=5,
            direct_accept_residual=None,
        )
    )
    return evaluator, candidate, refiner


@pytest.mark.parametrize("operation", ["compute_finite_difference_jacobian", "run_line_search"])
def test_deadline_inside_an_iteration_keeps_the_previous_successful_update(monkeypatch, operation):
    evaluator, candidate, refiner = fixture(nonlinear=True)
    original = getattr(implementation, operation)
    calls = 0

    def timeout_on_second_call(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TimeoutError("cutoff between the outer deadline check and evaluation")
        return original(**kwargs)

    monkeypatch.setattr(implementation, operation, timeout_on_second_call)
    with mp.workdps(180), runtime_session(time.monotonic() + 15):
        result = refiner.refine_candidates(
            bundle=evaluator.bundle, evaluator=evaluator, candidates=(candidate,)
        )
        assert calls == 2 and len(result.candidates) == 1
        draft = result.candidates[0]
        assert 1 < draft.x_hp[0] < 2
        assert draft.refinement_status == "deadline_reached"
        assert draft.answer_hp is None and draft.residual_norm_hp == mp.inf
        assert draft.candidate_id == candidate.candidate_id and draft.source is candidate
        # The deferred iterate is not an answer. It still needs the original
        # independent verification and exact identification under remaining time.
        exact = assemble_exact_results(refined_candidates=(draft,), evaluator=evaluator)
        assert exact.answer_values == ("sqrt(2)",)


def test_timeout_during_final_answer_evaluation_returns_an_unverified_draft(monkeypatch):
    evaluator, candidate, refiner = fixture()

    def timeout(*args, **kwargs):
        raise TimeoutError("answer evaluation reached the phase cutoff")

    monkeypatch.setattr(MpmathRefiner, "_evaluate_answer", timeout)
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        result = refiner._build_refined_candidate(
            bundle=evaluator.bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=[mp.mpf(2)],
            phase_history=(),
            stage_status="target_reached",
            candidate_id=7,
            answer_dps=120,
        )
    assert result.x_hp == (mp.mpf(2),) and result.answer_hp is None
    assert result.refinement_status == "deadline_reached" and not result.hard_feasible


def test_timeout_at_polish_entry_keeps_its_input_coordinate(monkeypatch):
    evaluator, _, refiner = fixture()

    def timeout(*args, **kwargs):
        raise TimeoutError("polish preparation reached the phase cutoff")

    monkeypatch.setattr(implementation, "_evaluate_hard_feasibility", timeout)
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        point, _, status, precision = refiner._apply_post_lm_closure_polish(
            bundle=evaluator.bundle,
            evaluator=evaluator,
            bounds=((None, None),),
            point=[mp.mpf(2)],
            phase_history=(),
            stage_status="target_reached",
            answer_dps=120,
        )
    assert point == [mp.mpf(2)] and status == "deadline_reached" and precision == 120


def test_timeout_in_optional_integer_followup_does_not_drop_a_completed_primary(monkeypatch):
    evaluator, candidate, refiner = fixture()
    candidate = replace(candidate, x_float=(5.0,))

    def timeout(*args, **kwargs):
        raise TimeoutError("optional integer follow-up reached the phase cutoff")

    monkeypatch.setattr(implementation, "_build_integer_constraint_closures", timeout)
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        result = refiner.refine_candidates(
            bundle=evaluator.bundle, evaluator=evaluator, candidates=(candidate,)
        )
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_id == 7
    assert abs(result.candidates[0].x_hp[0] - 2) < mp.mpf("1e-20")


def test_timeout_in_direct_probe_retains_the_initial_point(monkeypatch):
    evaluator, candidate, refiner = fixture()

    def timeout(*args, **kwargs):
        raise TimeoutError("direct probe reached the phase cutoff")

    monkeypatch.setattr(MpmathRefiner, "_direct_accept_candidate", timeout)
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        result = refiner.refine_candidates(
            bundle=evaluator.bundle, evaluator=evaluator, candidates=(candidate,)
        )
    assert len(result.candidates) == 1
    assert result.candidates[0].x_hp == (mp.mpf(2),)
    assert result.candidates[0].refinement_status == "deadline_reached"


def test_shared_expired_deadline_does_not_start_another_candidate(monkeypatch):
    evaluator, candidate, refiner = fixture()

    def unexpected(*args, **kwargs):
        pytest.fail("refinement started after the shared deadline")

    monkeypatch.setattr(MpmathRefiner, "_refine_single_candidate", unexpected)
    with runtime_session(time.monotonic() - 1):
        result = refiner.refine_candidates(
            bundle=evaluator.bundle, evaluator=evaluator, candidates=(candidate,)
        )
    assert result.attempted_count == 0 and not result.candidates


def test_completed_closure_residual_is_not_evaluated_again_for_an_unused_value(monkeypatch):
    evaluator, _, refiner = fixture()
    refiner = replace(refiner, config=replace(refiner.config, closure_schedule_dps=(250,)))
    original = MpmathRefiner._residual_vector_for_stage
    calls = 0

    def counted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MpmathRefiner, "_residual_vector_for_stage", counted)
    monkeypatch.setattr(
        implementation, "_run_findroot_closure", lambda **kwargs: ([mp.mpf(2)], mp.mpf(0))
    )
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        point, history, status, precision = refiner._apply_post_lm_closure_polish(
            bundle=evaluator.bundle,
            evaluator=evaluator,
            bounds=((None, None),),
            point=[mp.mpf(2)],
            phase_history=(),
            stage_status="target_reached",
            answer_dps=50,
        )
    assert point == [mp.mpf(2)] and status == "target_reached" and precision == 250
    assert len(history) == 1 and calls == 1


def test_later_closure_timeout_retains_the_last_completed_precision(monkeypatch):
    evaluator, _, refiner = fixture()
    refiner = replace(refiner, config=replace(refiner.config, closure_schedule_dps=(250, 350)))

    def close(**kwargs):
        if kwargs["dps"] == 350:
            raise TimeoutError("later closure stage reached the cutoff")
        return [mp.mpf(2)], mp.mpf(0)

    monkeypatch.setattr(implementation, "_run_findroot_closure", close)
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        point, history, status, precision = refiner._apply_post_lm_closure_polish(
            bundle=evaluator.bundle,
            evaluator=evaluator,
            bounds=((None, None),),
            point=[mp.mpf(2)],
            phase_history=(),
            stage_status="target_reached",
            answer_dps=50,
        )
    assert point == [mp.mpf(2)] and status == "deadline_reached" and precision == 250
    assert len(history) == 1
