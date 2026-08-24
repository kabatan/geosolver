"""Deduplicate final solutions with residual priority."""

from collections.abc import Sequence

from .remove_candidates import _distance


def remove_duplicate_solutions(
    solutions: Sequence[Sequence[float]], residuals: Sequence[float], tolerance: float
) -> tuple[list[list[float]], list[float]]:
    """Remove near-duplicate solutions while keeping smaller residuals."""
    unique_points: list[list[float]] = []
    unique_residuals: list[float] = []
    for solution, residual in zip(solutions, residuals):
        point = [float(value) for value in solution]
        for index, existing in enumerate(unique_points):
            if _distance(point, existing) <= tolerance:
                if float(residual) < unique_residuals[index]:
                    unique_points[index] = point
                    unique_residuals[index] = float(residual)
                break
        else:
            unique_points.append(point)
            unique_residuals.append(float(residual))
    return unique_points, unique_residuals
