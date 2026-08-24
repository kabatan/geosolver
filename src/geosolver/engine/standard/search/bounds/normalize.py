"""Bounds normalization utilities."""

from typing import Optional, Sequence

DEFAULT_BOUNDS: tuple[float, float] = (-100.0, 100.0)


def normalize_bounds(
    bounds: Optional[Sequence[Optional[tuple[float, float]]]], n: int
) -> list[tuple[float, float]]:
    """Normalize optional bounds into a list of length ``n``."""
    if bounds is None:
        return [DEFAULT_BOUNDS] * n
    normalized: list[tuple[float, float]] = []
    for bound in bounds:
        if bound is None:
            normalized.append(DEFAULT_BOUNDS)
            continue
        lower, upper = bound
        normalized.append((float(lower), float(upper)))
    while len(normalized) < n:
        normalized.append(DEFAULT_BOUNDS)
    return normalized[:n]
