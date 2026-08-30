"""Float residual evaluation for pipeline IR problems."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.evaluation.float_expressions import (
    compute_residual_vector,
    residual_norm,
)

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
    residuals = compute_residual_vector(
        list(values),
        spec=bundle.spec,
        var_names=list(bundle.var_names),
        targets=list(bundle.targets),
        base_context=dict(bundle.base_context),
    )
    status = classify_evaluation_failure(residuals)
    norm = residual_norm(residuals) if status is EvaluationStatus.OK else float("inf")
    return FloatResidualEvaluation(
        residual_vector=list(residuals),
        residual_norm_float=norm,
        evaluation_status=status,
        is_finite=(status is EvaluationStatus.OK),
    )
