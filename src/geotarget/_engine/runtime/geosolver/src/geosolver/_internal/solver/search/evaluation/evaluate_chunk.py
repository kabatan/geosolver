"""Evaluate a chunk of candidate points."""

from collections.abc import Callable, Sequence

from .evaluate_point import evaluate_point


def evaluate_chunk(
    points: Sequence[Sequence[float]], objective: Callable[[Sequence[float]], float]
) -> list[tuple[float, list[float]]]:
    """Evaluate all points in a chunk and return score-point tuples."""
    return [evaluate_point(point, objective) for point in points]
