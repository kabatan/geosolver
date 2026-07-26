"""Measurement and predicate helpers for mpmath API compatibility."""

from __future__ import annotations

from mpmath import mp

from .mp_impl import (
    MPLine,
    mp_angle,
    mp_angle_between_lines,
    mp_arc,
    mp_area,
    mp_evalf,
    mp_inscribed_polygon_vertices,
    mp_parallel_line,
    mp_parallelism_measure,
    mp_perimeter,
    mp_point_factory,
    mp_point_on_segment,
    mp_polygon_area,
)


def MP_PointOnSegment(p1, p2, t, exclude=None):
    return mp_point_on_segment(p1, p2, t, exclude)


def MP_ParallelLine(point, line):
    return mp_parallel_line(point, line)


def MP_Perimeter(A, B, C):
    return mp_perimeter(A, B, C)


def MP_IsAcuteTriangle(A, B, C):
    angle_a = mp_angle(B, A, C)
    angle_b = mp_angle(A, B, C)
    angle_c = mp_angle(A, C, B)
    max_angle = max([angle_a, angle_b, angle_c])
    return max(mp.mpf(0), max_angle - mp.pi / 2)


def MP_IsRightTriangle(A, B, C):
    angle_a = mp_angle(B, A, C)
    angle_b = mp_angle(A, B, C)
    angle_c = mp_angle(A, C, B)
    diff_a = abs(angle_a - mp.pi / 2)
    diff_b = abs(angle_b - mp.pi / 2)
    diff_c = abs(angle_c - mp.pi / 2)
    return min(diff_a, diff_b, diff_c)


def MP_IsObtuseTriangle(A, B, C):
    angle_a = mp_angle(B, A, C)
    angle_b = mp_angle(A, B, C)
    angle_c = mp_angle(A, C, B)
    max_angle = max([angle_a, angle_b, angle_c])
    return max(mp.mpf(0), mp.pi / 2 - max_angle)


def MP_evalf(value, precision=15):
    return mp_evalf(value, precision)


def MP_Arc(circle, start, end, including=None, excluding=None):
    return mp_arc(circle, start, end, including, excluding)


def MP_PointFactory(obj, t, including=None, excluding=None, exclude=None):
    return mp_point_factory(obj, t, including, excluding, exclude)


def MP_InscribedPolygonVertices(circle, *t_params):
    return mp_inscribed_polygon_vertices(circle, *t_params)


def MP_Angle(*args):
    if len(args) == 2:
        l1, l2 = args
        if isinstance(l1, MPLine) and isinstance(l2, MPLine):
            return mp_angle_between_lines(l1, l2)
        raise TypeError("Expected two MPLine objects")
    if len(args) == 3:
        a, b, c = args
        return mp_angle(a, b, c)
    raise TypeError("MP_Angle expects 2 or 3 arguments")


def MP_ParallelismMeasure(l1, l2, method: str = "cross"):
    if not (isinstance(l1, MPLine) and isinstance(l2, MPLine)):
        raise TypeError("Expected two MPLine objects")
    return mp_parallelism_measure(l1, l2, method)


def MP_Area(*args):
    if len(args) >= 3:
        if len(args) == 3:
            return mp_area(args[0], args[1], args[2])
        return mp_polygon_area(*args)
    if len(args) == 1:
        circle = args[0]
        if hasattr(circle, "radius"):
            return mp.pi * circle.radius**2
    raise ValueError("Area requires 1 circle or 3+ points")
