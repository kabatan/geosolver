"""Finite-difference Jacobian helpers for constraints."""

from collections.abc import Callable, Sequence


def compute_constraint_jacobian(
    evaluator: Callable[[Sequence[float]], Sequence[float]],
    point: Sequence[float],
    delta: float = 1e-8,
) -> list[list[float]]:
    """Compute Jacobian matrix with forward finite differences."""
    base = [float(value) for value in evaluator(point)]
    dimension = len(point)
    jacobian: list[list[float]] = [[0.0] * dimension for _ in range(len(base))]
    for column in range(dimension):
        shifted = list(point)
        shifted[column] = float(shifted[column]) + float(delta)
        values = [float(value) for value in evaluator(shifted)]
        for row, (new_value, base_value) in enumerate(zip(values, base)):
            jacobian[row][column] = (new_value - base_value) / float(delta)
    return jacobian
