"""Scale-adaptive point generation."""

from collections.abc import Sequence


def generate_scale_adaptive_points(
    n: int, bounds: Sequence[tuple[float, float]], n_points: int
) -> list[list[float]]:
    """Generate linearly spaced points across each dimension scale."""
    if n_points <= 1:
        return [[(float(low) + float(high)) / 2.0 for low, high in bounds]]
    points: list[list[float]] = []
    for index in range(n_points):
        ratio = index / (n_points - 1)
        points.append([float(low) + (float(high) - float(low)) * ratio for low, high in bounds[:n]])
    return points
