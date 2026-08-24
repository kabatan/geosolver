"""Numeric helper utilities extracted from safety module."""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple


def to_float(value: Any) -> float:
    """Convert value to float with support for sympy/mpmath objects."""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if hasattr(value, "_mpf_"):
            return float(value)
        if hasattr(value, "evalf"):
            return float(value.evalf())
        return float(value)
    except Exception as exc:
        raise ValueError(f"Cannot convert to float: {value}") from exc


def to_point_xy(point: Any, *, to_float_fn: Callable[[Any], float]) -> Tuple[float, float]:
    """Convert point-like object to ``(x, y)`` float coordinates."""
    if hasattr(point, "x") and hasattr(point, "y"):
        return to_float_fn(point.x), to_float_fn(point.y)
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return to_float_fn(point[0]), to_float_fn(point[1])
    raise ValueError(f"Cannot interpret point: {point}")


def normalize_interval(
    bounds: Any, *, to_float_fn: Callable[[Any], float]
) -> Tuple[Optional[float], Optional[float]]:
    """Normalize bound spec into ``(lo, hi)`` float pair."""
    if isinstance(bounds, dict):
        lo = bounds.get("lo", bounds.get("min"))
        hi = bounds.get("hi", bounds.get("max"))
    elif isinstance(bounds, (list, tuple)) and len(bounds) == 2:
        lo, hi = bounds
    else:
        raise ValueError("bounds must be (lo, hi) or dict with lo/hi")

    lo_v = to_float_fn(lo) if lo is not None else None
    hi_v = to_float_fn(hi) if hi is not None else None
    return lo_v, hi_v


def is_acute_triangle(
    A: Any,
    B: Any,
    C: Any,
    rel_floor: Optional[float],
    abs_floor: Optional[float],
    *,
    to_point_xy_fn: Callable[[Any], Tuple[float, float]],
    get_tolerance_fn: Callable[[float, Optional[float], Optional[float]], float],
) -> bool:
    """Check whether three points form an acute triangle."""
    ax, ay = to_point_xy_fn(A)
    bx, by = to_point_xy_fn(B)
    cx, cy = to_point_xy_fn(C)

    a2 = (bx - cx) ** 2 + (by - cy) ** 2
    b2 = (cx - ax) ** 2 + (cy - ay) ** 2
    c2 = (ax - bx) ** 2 + (ay - by) ** 2

    scale = max(1.0, a2, b2, c2)
    tol = get_tolerance_fn(scale, rel_floor, abs_floor)

    area = abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) * 0.5
    if area <= tol:
        return False

    return (b2 + c2) > (a2 + tol) and (c2 + a2) > (b2 + tol) and (a2 + b2) > (c2 + tol)
