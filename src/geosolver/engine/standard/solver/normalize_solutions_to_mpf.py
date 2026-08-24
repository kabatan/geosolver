"""Normalize solve candidate vectors to strict mpf values."""

from __future__ import annotations

from typing import Any, Sequence

from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf


def normalize_solutions_to_mpf(
    solutions: Sequence[Sequence[object]],
    *,
    context: str,
) -> tuple[list[list[Any]], int]:
    """Convert candidate values to mpf and fail-closed on float-like values."""
    normalized: list[list[Any]] = []
    float_origin_count = 0
    for solution_index, solution in enumerate(solutions):
        converted: list[Any] = []
        for value_index, value in enumerate(solution):
            if isinstance(value, float):
                float_origin_count += 1
                raise HighPrecisionContaminationError(
                    f"float-like value is forbidden in high precision path "
                    f"({context}[{solution_index}][{value_index}]): {value}"
                )
            converted.append(
                strict_to_mpf(value, context=f"{context}[{solution_index}][{value_index}]")
            )
        normalized.append(converted)
    return normalized, int(float_origin_count)

