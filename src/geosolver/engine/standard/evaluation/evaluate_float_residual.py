"""Float residual evaluation for pipeline IR problems."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    _compute_residual_vector,
    _residual_norm,
)

from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle

from .classify_evaluation_failure import EvaluationStatus, classify_evaluation_failure


@dataclass(frozen=True)
class FloatResidualEvaluation:
    """Result of float residual evaluation."""

    residual_vector: list[float]
    residual_norm_float: float
    evaluation_status: EvaluationStatus
    is_finite: bool


def evaluate_float_residual(
    *,
    bundle: ProblemBundle,
    values: list[float],
) -> FloatResidualEvaluation:
    """Evaluate residuals in float space."""
    residuals = _compute_residual_vector(
        list(values),
        spec=bundle.spec,
        var_names=list(bundle.var_names),
        targets=list(bundle.targets),
        base_context=dict(bundle.base_context),
    )
    status = classify_evaluation_failure(residuals)
    if status is EvaluationStatus.OK:
        norm = _residual_norm(residuals)
    else:
        norm = float("inf")
    return FloatResidualEvaluation(
        residual_vector=list(residuals),
        residual_norm_float=norm,
        evaluation_status=status,
        is_finite=(status is EvaluationStatus.OK),
    )

