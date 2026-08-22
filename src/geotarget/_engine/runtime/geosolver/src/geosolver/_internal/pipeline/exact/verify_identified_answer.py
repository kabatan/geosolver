"""Verification helpers for identified exact candidates."""

from __future__ import annotations

from collections.abc import Sequence

from mpmath import mp

from geosolver._internal.solver.exact.polynomial_search import (
    canonicalize_polynomial,
    nearest_real_root_distance,
)
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def _evaluate_polynomial(coefficients: Sequence[int], value: MPFloat) -> MPFloat:
    total = mp.mpf("0")
    for coefficient in coefficients:
        total = (total * value) + mp.mpf(int(coefficient))
    return total


def verify_identified_answer(
    *,
    coefficients: Sequence[int],
    numeric_value: MPFloat,
    precision_dps: int,
) -> tuple[bool, MPFloat]:
    """Verify an exact candidate using its canonical root, not only residual.

    A repeated relation such as ``(x - 72)^2`` makes the polynomial residual
    quadratic in the numeric error.  Checking that residual alone can therefore
    accept an approximation that is nowhere near the claimed precision.  We
    first reduce the relation to the distinct irreducible factor compatible
    with the value, then require both the canonical residual and the distance
    to its nearest real root to meet the same tolerance.
    """
    canonical = canonicalize_polynomial(coefficients, numeric_value)
    if canonical is None:
        return False, mp.inf
    with mp.workdps(int(precision_dps)):
        residual = abs(_evaluate_polynomial(canonical, numeric_value))
        tolerance = mp.power(mp.mpf("10"), -(max(int(precision_dps) - 20, 1)))
        root_distance = nearest_real_root_distance(canonical, numeric_value)
        is_verified = bool(
            mp.isfinite(residual)
            and residual <= tolerance
            and mp.isfinite(root_distance)
            and root_distance <= tolerance
        )
    return is_verified, residual

