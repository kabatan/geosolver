"""Evaluate one candidate point."""

from collections.abc import Callable, Sequence


def evaluate_point(point: Sequence[float], objective: Callable[[Sequence[float]], float]) -> tuple[float, list[float]]:
    """Return objective value and a copied point."""
    return float(objective(point)), [float(value) for value in point]
