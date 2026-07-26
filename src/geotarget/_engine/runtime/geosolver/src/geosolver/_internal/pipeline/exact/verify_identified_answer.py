"""Verification helpers for identified exact candidates."""

from __future__ import annotations

from collections.abc import Sequence

from mpmath import mp

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
    """Verify polynomial residual at numeric value."""
    with mp.workdps(int(precision_dps)):
        residual = abs(_evaluate_polynomial(coefficients, numeric_value))
        tolerance = mp.power(mp.mpf("10"), -(max(int(precision_dps) - 20, 1)))
        is_verified = bool(mp.isfinite(residual) and residual <= tolerance)
    return is_verified, residual

