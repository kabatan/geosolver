"""High-precision answer evaluation for pipeline IR problems."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mpmath import mp

from geosolver._internal.autosolve.answer.evaluate_hp import _evaluate_answer_high_precision
from geosolver.ir.errors import IRCompileError
from geosolver._internal.solver.precision.type_guards.ensure_no_float import (
    ensure_high_precision_mode,
)
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf

from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle

from .classify_evaluation_failure import EvaluationStatus


@dataclass(frozen=True)
class HPAnswerEvaluation:
    """Result of high-precision answer evaluation."""

    answer_hp: MPFloat | None
    evaluation_status: EvaluationStatus


def evaluate_answer_hp(
    *,
    bundle: ProblemBundle,
    values: Sequence[MPFloat],
    precision: int,
) -> HPAnswerEvaluation:
    """Evaluate answer expression at high precision.

    The caller must execute this function inside ``high_precision_mode()``.
    """
    ensure_high_precision_mode(context="pipeline.evaluate_answer_hp")
    try:
        raw_value, _value_text, _ctx = _evaluate_answer_high_precision(
            bundle.spec,
            bundle.var_names,
            list(values),
            precision=int(precision),
        )
    except IRCompileError:
        return HPAnswerEvaluation(
            answer_hp=None,
            evaluation_status=EvaluationStatus.EVALUATION_FAILED,
        )
    if raw_value is None:
        return HPAnswerEvaluation(
            answer_hp=None,
            evaluation_status=EvaluationStatus.EVALUATION_FAILED,
        )
    answer = strict_to_mpf(raw_value, context="pipeline.evaluate_answer_hp")
    if not mp.isfinite(answer):
        return HPAnswerEvaluation(
            answer_hp=answer,
            evaluation_status=EvaluationStatus.NON_FINITE,
        )
    return HPAnswerEvaluation(
        answer_hp=answer,
        evaluation_status=EvaluationStatus.OK,
    )

