"""Deduplicate candidate points by geometric tolerance."""

from collections.abc import Sequence


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)) ** 0.5


def remove_duplicate_candidates(candidates: Sequence[Sequence[float]], tolerance: float) -> list[list[float]]:
    """Remove near-duplicate candidates using Euclidean distance."""
    unique: list[list[float]] = []
    for candidate in candidates:
        point = [float(value) for value in candidate]
        if all(_distance(point, existing) > tolerance for existing in unique):
            unique.append(point)
    return unique
