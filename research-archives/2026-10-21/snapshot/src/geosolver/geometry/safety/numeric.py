"""Numeric helper utilities extracted from safety module."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def to_float(value: Any) -> float:
    """Convert value to float with support for sympy/mpmath objects."""
    try:
        if isinstance(value, int | float):
            return float(value)
        if hasattr(value, "_mpf_"):
            return float(value)
        if hasattr(value, "evalf"):
            return float(value.evalf())
        return float(value)
    except Exception as exc:
        raise ValueError(f"Cannot convert to float: {value}") from exc


def to_point_xy(point: Any, *, to_float_fn: Callable[[Any], float]) -> tuple[float, float]:
    """Convert point-like object to ``(x, y)`` float coordinates."""
    if hasattr(point, "x") and hasattr(point, "y"):
        return to_float_fn(point.x), to_float_fn(point.y)
    if isinstance(point, list | tuple) and len(point) >= 2:
        return to_float_fn(point[0]), to_float_fn(point[1])
    raise ValueError(f"Cannot interpret point: {point}")


def normalize_interval(
    bounds: Any, *, to_float_fn: Callable[[Any], float]
) -> tuple[float | None, float | None]:
    """Normalize bound spec into ``(lo, hi)`` float pair."""
    if isinstance(bounds, dict):
        lo = bounds.get("lo", bounds.get("min"))
        hi = bounds.get("hi", bounds.get("max"))
    elif isinstance(bounds, list | tuple) and len(bounds) == 2:
        lo, hi = bounds
    else:
        raise ValueError("bounds must be (lo, hi) or dict with lo/hi")

    lo_v = to_float_fn(lo) if lo is not None else None
    hi_v = to_float_fn(hi) if hi is not None else None
    return lo_v, hi_v
