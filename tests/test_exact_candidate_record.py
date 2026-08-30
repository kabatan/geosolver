from types import SimpleNamespace

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
from geosolver.engine.standard.evaluation.final_verifier import FinalVerificationResult
from geosolver.engine.standard.orchestration.assemble_exact_results import (
    assemble_exact_results,
)


def _candidate() -> RefinedCandidate:
    return RefinedCandidate(
        x_hp=(mp.mpf("1"),),
        residual_norm_hp=mp.mpf("0"),
        answer_hp=mp.mpf("1"),
        refinement_status="target_reached",
        phase_history=("fixture",),
        candidate_id=1,
        hard_feasible=True,
    )


def _evaluator():
    return SimpleNamespace(
        exact_candidate_cache={}, bundle=SimpleNamespace(spec=SimpleNamespace(answer_expr="1"))
    )


def test_numeric_feasible_candidate_is_not_public_when_exactification_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.verify_final_candidate",
        lambda **_kwargs: FinalVerificationResult(
            normalized_residual=mp.mpf(0),
            precision_dps=180,
            hard_feasible=True,
            verified=True,
            residual_norm=mp.mpf(0),
            min_margin=None,
            status="verified",
            hard_failure_tags=(),
            values=(mp.mpf(1),),
            answer_hp=mp.mpf(1),
            answer_uncertainty=mp.mpf(0),
        ),
    )
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.identify_answer",
        lambda **_kwargs: ExactIdentificationResult(
            exact_status="failed",
            identification_method="none",
            input_precision_dps=120,
            minimal_polynomial=None,
            polynomial_degree=None,
            selected_exact_value=None,
            verification_residual=None,
            numeric_fallback_value=mp.mpf("1"),
        ),
    )

    result = assemble_exact_results(refined_candidates=(_candidate(),), evaluator=_evaluator())

    assert len(result.numeric_feasible_candidates) == 1
    assert result.accepted_candidates == ()
    assert result.answer_values == ()
    assert result.candidate_records[0].candidate.candidate_id == 1
    assert result.rejection_tags == ("exactification_failed",)


def test_exactification_does_not_start_after_deadline(monkeypatch) -> None:
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.verify_final_candidate",
        lambda **_kwargs: FinalVerificationResult(
            normalized_residual=mp.mpf(0),
            precision_dps=180,
            hard_feasible=True,
            verified=True,
            residual_norm=mp.mpf(0),
            min_margin=None,
            status="verified",
            hard_failure_tags=(),
            values=(mp.mpf(1),),
            answer_hp=mp.mpf(1),
            answer_uncertainty=mp.mpf(0),
        ),
    )
    calls: list[object] = []
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.identify_answer",
        lambda **kwargs: calls.append(kwargs),
    )
    monotonic_values = iter((0.0, 2.0))
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.time.monotonic",
        lambda: next(monotonic_values),
    )

    result = assemble_exact_results(
        refined_candidates=(_candidate(),),
        evaluator=_evaluator(),
        deadline_monotonic=1.0,
    )

    assert calls == []
    assert len(result.numeric_feasible_candidates) == 1
    assert result.numeric_feasible_candidates[0].revision == 1
    assert result.answer_values == ()
    assert "deadline_before_exactification" in result.rejection_tags
