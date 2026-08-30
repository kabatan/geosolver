"""Line/circle and circle/circle intersection operations."""

from __future__ import annotations

import numpy as np
from sympy import N, simplify, sqrt

from geosolver.errors import GeometryDomainError, InfiniteSolutionsError
from geosolver.geometry.entities.base import Circle, Line, Point
from geosolver.geometry.registry import geometry_symbol


def _sign(value: object) -> int | None:
    simplified = simplify(value)
    if simplified == 0 or getattr(simplified, "is_zero", None) is True:
        return 0
    if getattr(simplified, "is_positive", None) is True:
        return 1
    if getattr(simplified, "is_negative", None) is True:
        return -1
    if getattr(simplified, "is_number", False):
        numeric = float(N(simplified, 50))
        return (numeric > 0) - (numeric < 0)
    return None


def _sorted_points(points: list[Point]) -> list[Point]:
    from functools import cmp_to_key

    def compare(left: Point, right: Point) -> int:
        for difference in (left.x - right.x, left.y - right.y):
            sign = _sign(difference)
            if sign is None:
                raise GeometryDomainError("cannot order symbolic intersection coordinates")
            if sign:
                return sign
        return 0

    return sorted(points, key=cmp_to_key(compare))


@geometry_symbol("IntersectLineCircle", category="intersections")
def IntersectLineCircle(line: Line, circle: Circle) -> list[Point]:
    """Line-circle intersections."""
    a, b, c_orig = line.a, line.b, line.c
    xc, yc, r = circle.center.x, circle.center.y, circle.radius

    c_shifted = a * xc + b * yc + c_orig
    div = a**2 + b**2
    if _sign(div) == 0:
        raise GeometryDomainError("line has a zero normal")
    dist_sq = c_shifted**2 / div
    delta = simplify(r**2 - dist_sq)
    delta_sign = _sign(delta)
    if delta_sign == -1:
        return []
    x0 = -a * c_shifted / div
    y0 = -b * c_shifted / div
    if delta_sign == 0:
        return [Point(xc + x0, yc + y0)]
    mult = sqrt(delta / div)
    p1 = Point(xc + x0 + b * mult, yc + y0 - a * mult)
    p2 = Point(xc + x0 - b * mult, yc + y0 + a * mult)
    return _sorted_points([p1, p2])


@IntersectLineCircle.set_numpy
def _IntersectLineCircle_numpy(line, circle):
    try:
        a, b, c_orig = line
    except Exception:
        a, b, c_orig = line.a, line.b, line.c

    try:
        xc, yc, r = circle
    except Exception:
        xc, yc, r = circle.center.x, circle.center.y, circle.radius

    div = a * a + b * b
    if div == 0:
        raise GeometryDomainError("line has a zero normal")
    c_shifted = a * xc + b * yc + c_orig

    dist_sq = c_shifted * c_shifted / div
    r_sq = r * r
    scale = max(abs(dist_sq), abs(r_sq), 1.0)
    tolerance = np.finfo(float).eps * 32 * scale
    if dist_sq > r_sq + tolerance:
        return []

    delta = max(0, r_sq - dist_sq)
    x0 = -a * c_shifted / div
    y0 = -b * c_shifted / div
    mult = np.sqrt(delta / div)
    p1 = [xc + x0 + b * mult, yc + y0 - a * mult]
    p2 = [xc + x0 - b * mult, yc + y0 + a * mult]
    if delta <= tolerance:
        return [p1]
    return sorted([p1, p2], key=lambda point: (point[0], point[1]))


@IntersectLineCircle.set_mpmath
def _IntersectLineCircle_mpmath(line, circle):
    from mpmath import sqrt as mp_sqrt

    from geosolver.geometry.mp.mp_core_types import MPPoint

    a, b, c_orig = line.a, line.b, line.c
    xc, yc, r = circle.center.x, circle.center.y, circle.radius
    div = a**2 + b**2
    if div == 0:
        raise GeometryDomainError("line has a zero normal")
    c_shifted = a * xc + b * yc + c_orig
    dist_sq = c_shifted**2 / div
    delta = r**2 - dist_sq
    if delta < 0:
        return []
    x0 = -a * c_shifted / div
    y0 = -b * c_shifted / div
    mult = mp_sqrt(delta / div)
    p1 = MPPoint(xc + x0 + b * mult, yc + y0 - a * mult)
    if delta == 0:
        return [p1]
    p2 = MPPoint(xc + x0 - b * mult, yc + y0 + a * mult)
    return sorted([p1, p2], key=lambda point: (point.x, point.y))


@geometry_symbol("IntersectCircles", category="intersections")
def IntersectCircles(c1: Circle, c2: Circle) -> list[Point]:
    """Circle-circle intersections."""
    x1, y1, r1 = c1.center.x, c1.center.y, c1.radius
    x2, y2, r2 = c2.center.x, c2.center.y, c2.radius

    d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
    if _sign(d2) == 0:
        if simplify(r1 - r2) == 0:
            raise InfiniteSolutionsError("coincident circles have infinitely many intersections")
        return []
    d = sqrt(d2)
    if _sign(d - (r1 + r2)) == 1 or _sign(d - abs(r1 - r2)) == -1:
        return []
    a = (r1**2 - r2**2 + d2) / (2 * d)
    arg = r1**2 - a**2
    arg_sign = _sign(arg)
    if arg_sign == -1:
        return []
    h = sqrt(arg)
    x0 = x1 + a * (x2 - x1) / d
    y0 = y1 + a * (y2 - y1) / d
    rx = -(y2 - y1) * (h / d)
    ry = (x2 - x1) * (h / d)
    p1 = Point(x0 + rx, y0 + ry)
    if arg_sign == 0:
        return [p1]
    p2 = Point(x0 - rx, y0 - ry)
    return _sorted_points([p1, p2])


@IntersectCircles.set_numpy
def _IntersectCircles_numpy(c1, c2):
    try:
        x1, y1, r1 = c1
    except Exception:
        x1, y1, r1 = c1.center.x, c1.center.y, c1.radius

    try:
        x2, y2, r2 = c2
    except Exception:
        x2, y2, r2 = c2.center.x, c2.center.y, c2.radius

    d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
    scale = max(abs(x1), abs(y1), abs(x2), abs(y2), abs(r1), abs(r2), 1.0)
    tolerance = np.finfo(float).eps * 32 * scale
    if d2 <= tolerance * tolerance:
        if abs(r1 - r2) <= tolerance:
            raise InfiniteSolutionsError("coincident circles have infinitely many intersections")
        return []
    d = np.sqrt(d2)
    if d > r1 + r2 + tolerance:
        return []
    if d < abs(r1 - r2) - tolerance:
        return []

    a = (r1 * r1 - r2 * r2 + d2) / (2 * d)
    arg = r1 * r1 - a * a
    if arg < 0:
        return []
    h = np.sqrt(arg)
    x0 = x1 + a * (x2 - x1) / d
    y0 = y1 + a * (y2 - y1) / d
    rx = -(y2 - y1) * (h / d)
    ry = (x2 - x1) * (h / d)
    p1 = [x0 + rx, y0 + ry]
    if arg <= tolerance * max(abs(r1 * r1), 1.0):
        return [p1]
    p2 = [x0 - rx, y0 - ry]
    return sorted([p1, p2], key=lambda point: (point[0], point[1]))


@IntersectCircles.set_mpmath
def _IntersectCircles_mpmath(c1, c2):
    from mpmath import sqrt as mp_sqrt

    from geosolver.geometry.mp.mp_core_types import MPPoint

    x1, y1, r1 = c1.center.x, c1.center.y, c1.radius
    x2, y2, r2 = c2.center.x, c2.center.y, c2.radius

    d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
    if d2 == 0:
        if r1 == r2:
            raise InfiniteSolutionsError("coincident circles have infinitely many intersections")
        return []
    d = mp_sqrt(d2)
    if d > r1 + r2 or d < abs(r1 - r2):
        return []

    a = (r1**2 - r2**2 + d2) / (2 * d)
    arg = r1**2 - a**2
    if arg < 0:
        return []
    h = mp_sqrt(arg)
    x0 = x1 + a * (x2 - x1) / d
    y0 = y1 + a * (y2 - y1) / d
    rx = -(y2 - y1) * (h / d)
    ry = (x2 - x1) * (h / d)
    p1 = MPPoint(x0 + rx, y0 + ry)
    if arg == 0:
        return [p1]
    p2 = MPPoint(x0 - rx, y0 - ry)
    return sorted([p1, p2], key=lambda point: (point.x, point.y))
