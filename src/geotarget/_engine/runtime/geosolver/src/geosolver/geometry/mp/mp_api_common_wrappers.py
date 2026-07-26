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


def MP_IncircleContactPoint(A: Any, B: Any, C: Any, side: Any = None) -> Any:
    return mp_incircle_contact_point(A, B, C, side)


def MP_Intersect(obj1: Any, obj2: Any, exclude: Any = None, **kwargs: Any) -> Any:
    return mp_intersect(obj1, obj2, exclude=exclude, **kwargs)


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
        mp.dps = max(mp.dps, digits + 5)
    return mpf(value)