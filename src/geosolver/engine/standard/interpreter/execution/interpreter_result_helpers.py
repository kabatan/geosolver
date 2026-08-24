"""Result assembly helpers for autosolve interpreter."""

from __future__ import annotations

import math
from typing import Any

from geosolver.engine.standard.interpreter.answer import _wrap_exact_value
from geosolver.core.result import SolveResult, SolveStatus


def residual_norm(residuals: list[float]) -> float:
    if not residuals:
        return 0.0
    return math.sqrt(sum(value * value for value in residuals))


def build_success_result(
    *,
    values: list[float],
    residuals: list[float],
    precision: int,
    metadata: dict[str, Any],
    answer_value: Any,
) -> SolveResult:
    residual_value = residual_norm(residuals)
    status = SolveStatus.SUCCESS if math.isfinite(residual_value) else SolveStatus.NUMERIC_INSTABILITY
    result = SolveResult(
        status=status,
        value=values,
        solutions=[values],
        answer_values=[answer_value] if answer_value is not None else [],
        residual=residual_value,
        precision_achieved=precision,
        metadata=metadata,
    )
    if answer_value is not None:
        try:
            result.exact_answer = _wrap_exact_value(answer_value)
        except Exception:
            result.exact_answer = _wrap_exact_value(answer_value, numeric_override=answer_value)
        result.metadata["numeric_answer"] = answer_value
        result.metadata["numeric_answer_raw"] = answer_value
        result.metadata["formatted_answer"] = answer_value
    return result
