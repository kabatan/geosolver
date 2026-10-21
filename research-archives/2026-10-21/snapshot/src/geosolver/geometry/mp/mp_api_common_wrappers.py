"""Delegated common wrapper functions extracted from mp_api."""

from __future__ import annotations

from typing import Any

from mpmath import mp, mpf

from .mp_impl import (
    MPArc,
    MPCircle,
    MPLine,
    MPPoint,
    MPSegment,
    mp_arc_midpoint,
    mp_circumcircle,
    mp_distance,
    mp_incircle,
    mp_incircle_contact_point,
    mp_intersect,
    mp_midpoint,
    mp_parallel_line,
    mp_perpendicular_line,
    mp_triangle_center,
)


def MP_TriangleCenter(A: Any, B: Any, C: Any, n: Any) -> Any:
    return mp_triangle_center(A, B, C, n)


def MP_Incircle(A: Any, B: Any, C: Any) -> Any:
    return mp_incircle(A, B, C)


def MP_Circumcircle(A: Any, B: Any, C: Any) -> Any:
    return mp_circumcircle(A, B, C)


def _same_point(left: Any, right: Any) -> bool:
    return left is right or (
        isinstance(left, MPPoint) and isinstance(right, MPPoint) and left == right
    )


def _normalize_contact_side(A: Any, B: Any, C: Any, side: Any) -> Any:
    """Normalize the public side aliases to the pair expected by mp_impl."""
    if side is None:
        return None
    if isinstance(side, str):
        return {
            "BC": (B, C),
            "CA": (C, A),
            "AB": (A, B),
        }.get(side)
    # bool is an int subclass, but is not a meaningful side index.
    if isinstance(side, int | mpf) and not isinstance(side, bool):
        if side in (0, 1, 2):
            return {0: (B, C), 1: (C, A), 2: (A, B)}[int(side)]
        raise ValueError("contact side index must be 0, 1, or 2")
    if isinstance(side, tuple | list):
        return tuple(side) if len(side) == 2 else None
    if _same_point(side, A):
        return (B, C)
    if _same_point(side, B):
        return (C, A)
    if _same_point(side, C):
        return (A, B)
    return None


def MP_IncircleContactPoint(A: Any, B: Any, C: Any, side: Any = None) -> Any:
    normalized_side = _normalize_contact_side(A, B, C, side)
    if side is not None and normalized_side is None:
        raise ValueError("unknown incircle contact side")
    return mp_incircle_contact_point(A, B, C, normalized_side)


def MP_Intersect(
    obj1: Any,
    obj2: Any,
    n: Any = None,
    exclude: Any = None,
    near: Any = None,
    far: Any = None,
) -> Any:
    # Construction helpers conventionally return a single object.  Unwrap a
    # singleton result defensively so a backend that represents a unique
    # tangent/intersection as ``[line]`` remains composable in the DSL.
    if isinstance(obj1, list | tuple) and len(obj1) == 1:
        obj1 = obj1[0]
    if isinstance(obj2, list | tuple) and len(obj2) == 1:
        obj2 = obj2[0]
    return mp_intersect(obj1, obj2, n=n, exclude=exclude, near=near, far=far)


def _resolve_point_line(arg1: Any, arg2: Any) -> tuple[MPPoint, MPLine]:
    if isinstance(arg1, MPPoint) and isinstance(arg2, MPLine):
        return arg1, arg2
    if isinstance(arg1, MPLine) and isinstance(arg2, MPPoint):
        return arg2, arg1
    raise TypeError("Expected (MPPoint, MPLine) or (MPLine, MPPoint)")


def MP_PerpendicularLine(arg1: Any, arg2: Any) -> Any:
    point, line = _resolve_point_line(arg1, arg2)
    return mp_perpendicular_line(line, point)


def MP_ParallelLine(arg1: Any, arg2: Any) -> Any:
    point, line = _resolve_point_line(arg1, arg2)
    return mp_parallel_line(point, line)


def MP_Midpoint(A: Any, B: Any = None) -> Any:
    if B is None:
        if isinstance(A, MPSegment):
            return mp_midpoint(A.p1, A.p2)
        if isinstance(A, MPCircle):
            return A.center
        if isinstance(A, MPArc):
            return mp_arc_midpoint(A.circle, A.start, A.end, A.including, A.excluding)
        raise TypeError("Expected MPSegment, MPCircle, MPArc, or two MPPoint objects")
    return mp_midpoint(A, B)


def MP_Distance(obj1: Any, obj2: Any) -> Any:
    return mp_distance(obj1, obj2)


def _mp_sqdist(P: Any, Q: Any) -> Any:
    dx = P.x - Q.x
    dy = P.y - Q.y
    return dx * dx + dy * dy


def MP_Require(cond: bool, message: str = "Requirement failed") -> mpf:
    if not bool(cond):
        raise ValueError(message)
    return mpf("0")


def MP_N(value: Any, digits: int | None = None) -> mpf:
    if digits:
        with mp.workdps(max(mp.dps, digits + 5)):
            return mpf(value)
    return mpf(value)
