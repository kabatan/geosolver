"""Tolerance computation for legacy solve/optimize engines.

WP4: Returns mpf values directly — no float intermediary.
"""

from __future__ import annotations

from mpmath import mp, mpf


_MAX_DECIMAL_EXPONENT: int = 300


def solve_residual_tolerance(precision: int) -> mpf:
    """Compute residual tolerance as mpf for the given precision.

    Args:
        precision: Target decimal precision.

    Returns:
        An ``mpf`` tolerance value (e.g. 10^{-precision}).
    """
    p = max(1, int(precision))
    if p < 16:
        return mp.mpf("1e-7")

    exponent = min(_MAX_DECIMAL_EXPONENT, p)
    return mp.power(10, -exponent)
