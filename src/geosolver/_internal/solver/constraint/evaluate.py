"""Constraint residual evaluation helpers."""

from collections.abc import Callable, Sequence


def evaluate_constraint_residuals(
    constraints: Sequence[Callable[[Sequence[float]], float]],
    point: Sequence[float],
    targets: Sequence[float],
) -> list[float]:
    """Evaluate residual vector ``f(point) - target`` for each constraint."""
    if len(constraints) != len(targets):
        raise ValueError("constraints and targets must have the same length")
    values = [func(point) for func in constraints]
    return [float(value) - float(target) for value, target in zip(values, targets)]
