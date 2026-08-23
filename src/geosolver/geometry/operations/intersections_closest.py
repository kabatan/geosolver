"""Closest point operations for intersection module."""

from typing import Any

from sympy import sqrt

from geosolver.geometry.entities.base import Circle, Line, Point
from geosolver.geometry.registry import geometry_symbol


@geometry_symbol("ClosestPoint", category="intersections")
def ClosestPoint(arg1: Any, arg2: Any) -> Point:
    """Return the closest point on an object to a given point."""
    point = None
    obj = None

    if isinstance(arg1, Point) and not isinstance(arg2, Point):
        point, obj = arg1, arg2
    elif isinstance(arg2, Point) and not isinstance(arg1, Point):
        obj, point = arg1, arg2
    else:
        point, obj = arg1, arg2

    if isinstance(obj, Line):
        a, b, c = obj.a, obj.b, obj.c
        x0, y0 = point.x, point.y
        denom = a**2 + b**2
        x = (b * (b * x0 - a * y0) - a * c) / denom
        y = (a * (-b * x0 + a * y0) - b * c) / denom
        return Point(x, y)

    if isinstance(obj, Circle):
        cx, cy, r = obj.center.x, obj.center.y, obj.radius
        px, py = point.x, point.y
        dx = px - cx
        dy = py - cy
        d = sqrt(dx**2 + dy**2)
        if d == 0:
            return obj.center
        return Point(cx + r * dx / d, cy + r * dy / d)

    raise NotImplementedError(f"ClosestPoint not implemented for {type(obj)}")


@ClosestPoint.set_numpy
def _ClosestPoint_numpy(arg1, arg2):
    """NumPy implementation."""
    point = None
    obj = None

    try:
        len1 = len(arg1)
        len2 = len(arg2)
        if len1 == 2 and len2 == 3:
            point, obj = arg1, arg2
        elif len1 == 3 and len2 == 2:
            obj, point = arg1, arg2
        else:
            point, obj = arg1, arg2
    except Exception:
        point, obj = arg1, arg2

    a, b, c = obj
    x0, y0 = point
    denom = a * a + b * b
    x = (b * (b * x0 - a * y0) - a * c) / denom
    y = (a * (-b * x0 + a * y0) - b * c) / denom
    return [x, y]


@ClosestPoint.set_mpmath
def _ClosestPoint_mpmath(arg1, arg2):
    """mpmath implementation."""
    from mpmath import sqrt

    point = None
    obj = None

    if isinstance(arg1, Point) and not isinstance(arg2, Point):
        point, obj = arg1, arg2
    elif isinstance(arg2, Point) and not isinstance(arg1, Point):
        obj, point = arg1, arg2
    else:
        point, obj = arg1, arg2

    if isinstance(obj, Line):
        a, b, c = obj.a, obj.b, obj.c
        x0, y0 = point.x, point.y
        denom = a**2 + b**2
        x = (b * (b * x0 - a * y0) - a * c) / denom
        y = (a * (-b * x0 + a * y0) - b * c) / denom
        return Point(x, y)
    if isinstance(obj, Circle):
        cx, cy, r = obj.center.x, obj.center.y, obj.radius
        px, py = point.x, point.y
        dx = px - cx
        dy = py - cy
        d = sqrt(dx**2 + dy**2)
        if d == 0:
            return Point(cx, cy)
        return Point(cx + r * dx / d, cy + r * dy / d)
    return Point(0, 0)
