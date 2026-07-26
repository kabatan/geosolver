"""Line/circle and circle/circle intersection operations."""

from __future__ import annotations

from typing import List

import numpy as np
from sympy import Max, sqrt

from geosolver.geometry.entities.base import Circle, Line, Point
from geosolver.geometry.registry import geometry_symbol


@geometry_symbol("IntersectLineCircle", category="intersections")
def IntersectLineCircle(line: Line, circle: Circle) -> List[Point]:
    """Line-circle intersections."""
    a, b, c_orig = line.a, line.b, line.c
    xc, yc, r = circle.center.x, circle.center.y, circle.radius

    c_shifted = a * xc + b * yc + c_orig
    div = a**2 + b**2
    if div == 0:
        return [Point(1e9, 1e9), Point(1e9, 1e9)]
    dist_sq = c_shifted**2 / div
    delta_val = r**2 - dist_sq
    mult = sqrt(Max(0, delta_val) / div)
    x0 = -a * c_shifted / div
    y0 = -b * c_shifted / div
    p1 = Point(xc + x0 + b * mult, yc + y0 - a * mult)
    p2 = Point(xc + x0 - b * mult, yc + y0 + a * mult)
    return [p1, p2]


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
    if div < 1e-25:
        return []
    c_shifted = a * xc + b * yc + c_orig

    dist_sq = c_shifted * c_shifted / div
    r_sq = r * r
    if dist_sq > r_sq + 1e-12:
        return []

    delta = max(0, r_sq - dist_sq)
    x0 = -a * c_shifted / div
    y0 = -b * c_shifted / div
    mult = np.sqrt(delta / div)
    p1 = [xc + x0 + b * mult, yc + y0 - a * mult]
    p2 = [xc + x0 - b * mult, yc + y0 + a * mult]
    return [p1, p2]


@IntersectLineCircle.set_mpmath
def _IntersectLineCircle_mpmath(line, circle):
    from mpmath import sqrt as mp_sqrt

    a, b, c_orig = line.a, line.b, line.c
    xc, yc, r = circle.center.x, circle.center.y, circle.radius
    div = a**2 + b**2
    if div == 0:
        return []
    c_shifted = a * xc + b * yc + c_orig
    dist_sq = c_shifted**2 / div
    if dist_sq > r**2:
        return []

    delta = r**2 - dist_sq
    x0 = -a * c_shifted / div
    y0 = -b * c_shifted / div
    mult = mp_sqrt(delta / div)
    p1 = Point(xc + x0 + b * mult, yc + y0 - a * mult)
    p2 = Point(xc + x0 - b * mult, yc + y0 + a * mult)
    return [p1, p2]


@geometry_symbol("IntersectCircles", category="intersections")
def IntersectCircles(c1: Circle, c2: Circle) -> List[Point]:
    """Circle-circle intersections."""
    x1, y1, r1 = c1.center.x, c1.center.y, c1.radius
    x2, y2, r2 = c2.center.x, c2.center.y, c2.radius

    d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
    d = sqrt(d2)
    a = (r1**2 - r2**2 + d2) / (2 * d)
    arg = r1**2 - a**2
    h = sqrt(Max(0, arg))
    x0 = x1 + a * (x2 - x1) / d
    y0 = y1 + a * (y2 - y1) / d
    rx = -(y2 - y1) * (h / d)
    ry = (x2 - x1) * (h / d)
    p1 = Point(x0 + rx, y0 + ry)
    p2 = Point(x0 - rx, y0 - ry)
    return [p1, p2]


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
    if d2 < 1e-20:
        return []
    d = np.sqrt(d2)
    if d > r1 + r2 + 1e-12:
        return []
    if d < abs(r1 - r2) - 1e-12:
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
    p2 = [x0 - rx, y0 - ry]
    return [p1, p2]


@IntersectCircles.set_mpmath
def _IntersectCircles_mpmath(c1, c2):
    from mpmath import sqrt as mp_sqrt

    x1, y1, r1 = c1.center.x, c1.center.y, c1.radius
    x2, y2, r2 = c2.center.x, c2.center.y, c2.radius

    d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
    d = mp_sqrt(d2)
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
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
    p1 = Point(x0 + rx, y0 + ry)
    p2 = Point(x0 - rx, y0 - ry)
    return [p1, p2]
