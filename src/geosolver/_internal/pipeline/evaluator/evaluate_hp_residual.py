"""High-precision residual evaluation for pipeline IR problems."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mpmath import mp

from geosolver._internal.autosolve.execution.interpreter_modes import (
    _compute_residual_vector_high_precision,
    _residual_norm_high_precision,
)
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat

from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle

from .classify_evaluation_failure import EvaluationStatus, classify_evaluation_failure


@dataclass(frozen=True)
class HPResidualEvaluation:
    """Result of high-precision residual evaluation."""

    residual_vector: list[MPFloat]
    residual_norm_hp: MPFloat
    evaluation_status: EvaluationStatus
    is_finite: bool


def evaluate_hp_residual(
    *,
    bundle: ProblemBundle,
    values: Sequence[MPFloat],
    precision: int,
) -> HPResidualEvaluation:
    """Evaluate residuals at the given precision.

    The caller must execute this function inside ``high_precision_mode()``.
    """
    residuals = _compute_residual_vector_high_precision(
        list(values),
        spec=bundle.spec,
        var_names=list(bundle.var_names),
        targets=list(bundle.targets),
        base_context=dict(bundle.base_context),
        precision=int(precision),
    )
    status = classify_evaluation_failure(residuals)
    norm = _residual_norm_high_precision(residuals)
    return HPResidualEvaluation(
        residual_vector=[mp.mpf(value) for value in residuals],
        residual_norm_hp=mp.mpf(norm),
        evaluation_status=status,
        is_finite=(status is EvaluationStatus.OK),
    )

