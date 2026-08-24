"""Apply Zone B conversion for solve candidate vectors."""

from __future__ import annotations

from typing import Any, Callable, Sequence


def boundary_normalize_solutions(
    solutions: Sequence[Sequence[object]],
    *,
    context: str,
    converter: Callable[[object, str], Any],
) -> list[list[Any]]:
    """Convert candidate vectors through the supplied boundary converter."""
    normalized: list[list[Any]] = []
    for solution_index, solution in enumerate(solutions):
        converted: list[Any] = []
        for value_index, value in enumerate(solution):
            converted.append(
                converter(value, f"{context}[{solution_index}][{value_index}]")
            )
        normalized.append(converted)
    return normalized

