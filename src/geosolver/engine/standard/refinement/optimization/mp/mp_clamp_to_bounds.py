"""Clamp point to bounds at multiprecision."""

from __future__ import annotations

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


def mp_clamp_to_bounds(
    x: list[MPFloat],
    bounds: list[tuple[MPFloat | None, MPFloat | None]] | None,
) -> list[MPFloat]:
    """Project point onto box bounds.

    Args:
        x: Current point.
        bounds: Per-variable (lower, upper) bounds. None means no bound.

    Returns:
        Clamped point.
    """
    if bounds is None:
        return list(x)

    result: list[MPFloat] = []
    for i, val in enumerate(x):
        if i < len(bounds):
            lo, hi = bounds[i]
            if lo is not None:
                val = max(val, mp.mpf(lo))
            if hi is not None:
                val = min(val, mp.mpf(hi))
        result.append(val)
    return result
