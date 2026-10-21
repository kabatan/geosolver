"""Delegated backend implementations for constructions_extra operations."""

from __future__ import annotations

from typing import Any

from geosolver.geometry.entities.base import Circle, Line, Point


def point_on_segment_numpy_impl(p1: Any, p2: Any, t: Any) -> list[Any]:
    from geosolver.errors import CoincidentPointsError, GeometryDomainError

    if p1[0] == p2[0] and p1[1] == p2[1]:
        raise CoincidentPointsError("segment endpoints must be distinct")
    if not 0 <= t <= 1:
        raise GeometryDomainError("segment parameter must be in [0, 1]")
    return [p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])]


def point_on_segment_mpmath_impl(p1: Any, p2: Any, t: Any) -> Any:
    from geosolver.geometry.mp.mp_impl import mp_point_on_segment

    return mp_point_on_segment(p1, p2, t)


def point_on_line_numpy_impl(line: Any, t: Any) -> list[Any]:
    a, b, c = line
    denom = a * a + b * b
    base_x = -a * c / denom
    base_y = -b * c / denom
    return [base_x - b * t, base_y + a * t]


def point_on_line_mpmath_impl(line: Line, t: Any) -> Point:
    from geosolver.geometry.mp.mp_core_types import MPPoint

    a, b, c = line.a, line.b, line.c
    denom = a**2 + b**2
    base_x = -a * c / denom
    base_y = -b * c / denom
    return MPPoint(base_x - b * t, base_y + a * t)


def point_on_circle_numpy_impl(circle: Any, t: Any) -> list[Any]:
    import numpy as np

    cx, cy, r = circle
    angle = 2 * np.pi * t
    return [cx + r * np.cos(angle), cy + r * np.sin(angle)]


def point_on_circle_mpmath_impl(circle: Circle, t: Any) -> Point:
    from mpmath import cos as mp_cos
    from mpmath import pi as mp_pi
    from mpmath import sin as mp_sin

    from geosolver.geometry.mp.mp_core_types import MPPoint

    angle = 2 * mp_pi * t
    return MPPoint(
        circle.center.x + circle.radius * mp_cos(angle),
        circle.center.y + circle.radius * mp_sin(angle),
    )


def tangent_numpy_impl(point: Any, circle: Any, use_first: bool = True) -> list[Any] | None:
    import numpy as np

    cx, cy, r = circle
    px, py = point
    dx = cx - px
    dy = cy - py
    d2 = dx * dx + dy * dy
    r2 = r * r
    if d2 < r2 - 1e-12:
        return None
    d = np.sqrt(d2)
    L = np.sqrt(max(0, d2 - r2))
    sin_a = r / d
    cos_a = L / d
    ux = dx / d
    uy = dy / d
    if use_first:
        rx = ux * cos_a - uy * sin_a
        ry = ux * sin_a + uy * cos_a
    else:
        rx = ux * cos_a + uy * sin_a
        ry = -ux * sin_a + uy * cos_a
    tx = px + L * rx
    ty = py + L * ry
    a = py - ty
    b = tx - px
    c = -a * px - b * py
    return [a, b, c]


def tangent_mpmath_impl(point: Point, circle: Circle, use_first: bool = True) -> Line:
    from mpmath import sqrt

    from geosolver.geometry.mp.mp_core_types import MPLine

    cx, cy = circle.center.x, circle.center.y
    r = circle.radius
    px, py = point.x, point.y
    dx = cx - px
    dy = cy - py
    d2 = dx * dx + dy * dy
    r2 = r * r
    d = sqrt(d2)
    L = sqrt(d2 - r2)
    sin_a = r / d
    cos_a = L / d
    ux = dx / d
    uy = dy / d
    if use_first:
        rx = ux * cos_a - uy * sin_a
        ry = ux * sin_a + uy * cos_a
    else:
        rx = ux * cos_a + uy * sin_a
        ry = -ux * sin_a + uy * cos_a
    tx = px + L * rx
    ty = py + L * ry
    a = py - ty
    b = tx - px
    c = -a * px - b * py
    return MPLine(a, b, c)


def circle_through_point_numpy_impl(center: Any, point: Any) -> list[Any]:
    import numpy as np

    dx = center[0] - point[0]
    dy = center[1] - point[1]
    return [center[0], center[1], np.sqrt(dx * dx + dy * dy)]


def circle_through_point_mpmath_impl(center: Point, point: Point) -> Circle:
    from mpmath import sqrt

    from geosolver.geometry.mp.mp_core_types import MPCircle

    dx = center.x - point.x
    dy = center.y - point.y
    return MPCircle(center, sqrt(dx**2 + dy**2))


def circle_through_three_points_numpy_impl(p1: Any, p2: Any, p3: Any) -> list[Any] | None:
    import numpy as np

    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(D) < 1e-12:
        return None
    Ux = (
        (x1 * x1 + y1 * y1) * (y2 - y3)
        + (x2 * x2 + y2 * y2) * (y3 - y1)
        + (x3 * x3 + y3 * y3) * (y1 - y2)
    ) / D
    Uy = (
        (x1 * x1 + y1 * y1) * (x3 - x2)
        + (x2 * x2 + y2 * y2) * (x1 - x3)
        + (x3 * x3 + y3 * y3) * (x2 - x1)
    ) / D
    dx = x1 - Ux
    dy = y1 - Uy
    return [Ux, Uy, np.sqrt(dx * dx + dy * dy)]


def circle_through_three_points_mpmath_impl(p1: Point, p2: Point, p3: Point) -> Circle | None:
    from geosolver.geometry.mp.mp_impl import mp_circumcircle

    return mp_circumcircle(p1, p2, p3)
