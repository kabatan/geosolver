"""Finite-difference Jacobian for high-precision refinement."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat

MAX_STEP_REDUCTIONS = 6
MAX_STEP_EXPONENT = 30


def compute_finite_difference_jacobian(
    *,
    point: Sequence[MPFloat],
    dps: int,
    residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None],
) -> list[list[MPFloat]] | None:
    """Compute Jacobian matrix by centered finite differences."""
    base = residual_fn(list(point), int(dps))
    if base is None:
        return None
    rows = len(base)
    cols = len(point)
    jacobian: list[list[MPFloat]] = [
        [mp.mpf("0") for _ in range(cols)]
        for _ in range(rows)
    ]
    with mp.workdps(int(dps)):
        for column in range(cols):
            exponent = min(max(int(dps) // 2, 1), MAX_STEP_EXPONENT)
            step = max(mp.mpf("1"), abs(point[column])) * mp.power(mp.mpf("10"), -exponent)
            success = False
            for _ in range(MAX_STEP_REDUCTIONS):
                plus = [mp.mpf(value) for value in point]
                minus = [mp.mpf(value) for value in point]
                plus[column] += step
                minus[column] -= step
                plus_vec = residual_fn(plus, int(dps))
                minus_vec = residual_fn(minus, int(dps))
                if plus_vec is None or minus_vec is None:
                    step /= mp.mpf("2")
                    continue
                denominator = mp.mpf("2") * step
                for row in range(rows):
                    jacobian[row][column] = (plus_vec[row] - minus_vec[row]) / denominator
                success = True
                break
            if not success:
                return None
    return jacobian

