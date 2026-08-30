"""Delegated linear-construction backend implementations."""

from __future__ import annotations

from typing import Any

from geosolver.geometry.entities.base import Line, Point


def perpendicular_line_numpy_impl(arg1: Any, arg2: Any) -> list[Any]:
    try:
        if len(arg1) == 3 and len(arg2) == 2:
            line, point = arg1, arg2
        elif len(arg1) == 2 and len(arg2) == 3:
            point, line = arg1, arg2
        else:
            line, point = arg1, arg2
    except Exception:
        line, point = arg1, arg2

    return [line[1], -line[0], -line[1] * point[0] + line[0] * point[1]]


def perpendicular_line_mpmath_impl(arg1: Any, arg2: Any) -> Line:
    if isinstance(arg1, Line) and isinstance(arg2, Point):
        line, point = arg1, arg2
    elif isinstance(arg1, Point) and isinstance(arg2, Line):
        point, line = arg1, arg2
    else:
        line, point = arg1, arg2

    a = line.b
    b = -line.a
    c = -(a * point.x + b * point.y)
    return Line(a, b, c)


def parallel_line_numpy_impl(arg1: Any, arg2: Any) -> list[Any]:
    try:
        if len(arg1) == 3 and len(arg2) == 2:
            line, point = arg1, arg2
        elif len(arg1) == 2 and len(arg2) == 3:
            point, line = arg1, arg2
        else:
            line, point = arg1, arg2
    except Exception:
        line, point = arg1, arg2

    return [line[0], line[1], -line[0] * point[0] - line[1] * point[1]]


def parallel_line_mpmath_impl(arg1: Any, arg2: Any) -> Line:
    if isinstance(arg1, Line) and isinstance(arg2, Point):
        line, point = arg1, arg2
    elif isinstance(arg1, Point) and isinstance(arg2, Line):
        point, line = arg1, arg2
    else:
        line, point = arg1, arg2

    a = line.a
    b = line.b
    c = -(a * point.x + b * point.y)
    return Line(a, b, c)


def foot_of_perpendicular_numpy_impl(arg1: Any, arg2: Any) -> list[Any]:
    try:
        if len(arg1) == 3 and len(arg2) == 2:
            line, point = arg1, arg2
        elif len(arg1) == 2 and len(arg2) == 3:
            point, line = arg1, arg2
        else:
            line, point = arg1, arg2
    except Exception:
        line, point = arg1, arg2

    a, b, c = line
    x0, y0 = point
    denom = a * a + b * b

    if denom < 1e-20:
        return point

    x = (b * (b * x0 - a * y0) - a * c) / denom
    y = (a * (-b * x0 + a * y0) - b * c) / denom
    return [x, y]


def foot_of_perpendicular_mpmath_impl(arg1: Any, arg2: Any) -> Point:
    if isinstance(arg1, Line) and isinstance(arg2, Point):
        line, point = arg1, arg2
    elif isinstance(arg1, Point) and isinstance(arg2, Line):
        point, line = arg1, arg2
    else:
        line, point = arg1, arg2

    a, b, c = line.a, line.b, line.c
    x0, y0 = point.x, point.y
    denom = a**2 + b**2
    x = (b * (b * x0 - a * y0) - a * c) / denom
    y = (a * (-b * x0 + a * y0) - b * c) / denom
    return Point(x, y)
