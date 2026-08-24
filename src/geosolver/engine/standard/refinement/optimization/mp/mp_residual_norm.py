"""Compute L2 norm of an MP residual vector."""

from __future__ import annotations

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


def mp_residual_norm(residual: list[MPFloat]) -> MPFloat:
    """Compute L2 norm of residual vector using compensated summation.

    Args:
        residual: Residual vector.

    Returns:
        L2 norm sqrt(sum(r_i^2)).
    """
    squared_sum = mp.fsum([r * r for r in residual])
    return mp.sqrt(squared_sum)
