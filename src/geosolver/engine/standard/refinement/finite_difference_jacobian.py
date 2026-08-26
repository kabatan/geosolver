"""Finite-difference Jacobian for high-precision refinement."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat

MAX_STEP_REDUCTIONS = 6
MAX_STEP_EXPONENT = 30


def compute_finite_difference_jacobian(
    *,
    point: Sequence[MPFloat],
    dps: int,
    residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None],
    one_sided_at_cusp: bool = False,
) -> list[list[MPFloat]] | None:
    """Compute a Jacobian matrix by finite differences.

    Centered differences are the least biased choice for smooth residuals,
    but they cancel at an absolute-value/``atan2(abs(...), ...)`` cusp.  For
    explicitly marked nonsmooth systems, use a non-zero one-sided directional
    slope only when the two one-sided slopes have opposite signs and the
    centered slope is numerical zero.  The default remains the historical
    centered scheme so unrelated smooth problems retain their behavior.
    """
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
                    centered = (plus_vec[row] - minus_vec[row]) / denominator
                    if one_sided_at_cusp:
                        forward = (plus_vec[row] - base[row]) / step
                        backward = (base[row] - minus_vec[row]) / step
                        scale = max(mp.mpf("1"), abs(forward), abs(backward), abs(centered))
                        tolerance = 100 * mp.eps * scale
                        if (
                            abs(centered) <= tolerance
                            and abs(forward) > tolerance
                            and abs(backward) > tolerance
                            and forward * backward < 0
                        ):
                            # A derivative does not exist at a true cusp.  A
                            # directional slope is still useful to Newton/LM;
                            # choose the stronger side deterministically.
                            centered = (
                                forward
                                if abs(forward) >= abs(backward)
                                else backward
                            )
                    jacobian[row][column] = centered
                success = True
                break
            if not success:
                return None
    return jacobian

