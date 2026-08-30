"""Extracted advanced construction operations."""

from __future__ import annotations

from typing import Any

from sympy import cos, pi, sin, sqrt

from geosolver.errors import CoincidentPointsError, GeometryDomainError, NoIntersectionError
from geosolver.geometry.entities.base import Circle, Line, Point
from geosolver.geometry.entities.polygon import Polygon
from geosolver.geometry.operations.constructions_extra_backends import (
    circle_through_point_mpmath_impl,
    circle_through_point_numpy_impl,
    circle_through_three_points_mpmath_impl,
    circle_through_three_points_numpy_impl,
    point_on_circle_mpmath_impl,
    point_on_circle_numpy_impl,
    point_on_line_mpmath_impl,
    point_on_line_numpy_impl,
    point_on_segment_mpmath_impl,
    point_on_segment_numpy_impl,
    tangent_mpmath_impl,
    tangent_numpy_impl,
)
from geosolver.geometry.registry import geometry_symbol


@geometry_symbol("PointOnLine", category="parametric")
def PointOnLine(line: Line, t: Any) -> Point:
    a, b, c = line.a, line.b, line.c
    denom = a**2 + b**2
    base_x = -a * c / denom
    base_y = -b * c / denom
    return Point(base_x - b * t, base_y + a * t)


@geometry_symbol("PointOnSegment", category="parametric")
def PointOnSegment(p1: Point, p2: Point, t: Any) -> Point:
    if p1.x == p2.x and p1.y == p2.y:
        raise CoincidentPointsError("segment endpoints must be distinct")
    if not 0 <= t <= 1:
        raise GeometryDomainError("segment parameter must be in [0, 1]")
    return Point(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y))


@PointOnSegment.set_numpy
def _PointOnSegment_numpy(p1, p2, t):
    return point_on_segment_numpy_impl(p1, p2, t)


@PointOnSegment.set_mpmath
def _PointOnSegment_mpmath(p1, p2, t):
    return point_on_segment_mpmath_impl(p1, p2, t)


@PointOnLine.set_numpy
def _PointOnLine_numpy(line, t):
    return point_on_line_numpy_impl(line, t)


@PointOnLine.set_mpmath
def _PointOnLine_mpmath(line, t):
    return point_on_line_mpmath_impl(line, t)


@geometry_symbol("PointOnCircle", category="parametric")
def PointOnCircle(circle: Circle, t: Any) -> Point:
    angle = 2 * pi * t
    return Point(
        circle.center.x + circle.radius * cos(angle),
        circle.center.y + circle.radius * sin(angle),
    )


@PointOnCircle.set_numpy
def _PointOnCircle_numpy(circle, t):
    return point_on_circle_numpy_impl(circle, t)


@PointOnCircle.set_mpmath
def _PointOnCircle_mpmath(circle, t):
    return point_on_circle_mpmath_impl(circle, t)


@geometry_symbol("Tangent", category="constructions")
def Tangent(point: Point, circle: Circle, use_first: bool = True) -> Line | None:
    vx = point.x - circle.center.x
    vy = point.y - circle.center.y
    d2 = vx**2 + vy**2
    r2 = circle.radius**2
    difference = d2 - r2
    sign = getattr(difference, "is_positive", None)
    if difference == 0 or getattr(difference, "is_zero", None) is True:
        return Line(vx, vy, -(vx * point.x + vy * point.y))
    if getattr(difference, "is_negative", None) is True:
        raise NoIntersectionError("an interior point has no real tangent line")
    if sign is None and getattr(difference, "is_number", False) and float(difference.evalf(50)) < 0:
        raise NoIntersectionError("an interior point has no real tangent line")
    if d2 == 0:
        raise GeometryDomainError("tangent is undefined at the circle center")
    offset = circle.radius * sqrt(difference) / d2
    base_x = circle.center.x + r2 * vx / d2
    base_y = circle.center.y + r2 * vy / d2
    direction = 1 if use_first else -1
    tangent_point = Point(
        base_x + direction * offset * (-vy),
        base_y + direction * offset * vx,
    )
    return Line(point, tangent_point)


@Tangent.set_numpy
def _Tangent_numpy(point, circle, use_first=True):
    return tangent_numpy_impl(point, circle, use_first)


@Tangent.set_mpmath
def _Tangent_mpmath(point, circle, use_first=True):
    return tangent_mpmath_impl(point, circle, use_first)


@geometry_symbol("CircleThroughPoint", category="constructions")
def CircleThroughPoint(center: Point, point: Point) -> Circle:
    return Circle(center, center.distance_to(point))


@CircleThroughPoint.set_numpy
def _CircleThroughPoint_numpy(center, point):
    return circle_through_point_numpy_impl(center, point)


@CircleThroughPoint.set_mpmath
def _CircleThroughPoint_mpmath(center, point):
    return circle_through_point_mpmath_impl(center, point)


def _get_raise_on_degenerate_flag() -> bool:
    from geosolver.geometry.operations.constructions import get_raise_on_degenerate

    return get_raise_on_degenerate()


@geometry_symbol("CircleThroughThreePoints", category="constructions")
def CircleThroughThreePoints(p1: Point, p2: Point, p3: Point) -> Circle | None:
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if D == 0:
        if _get_raise_on_degenerate_flag():
            raise CoincidentPointsError("Points are collinear")
        return None
    Ux = (
        (x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)
    ) / D
    Uy = (
        (x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)
    ) / D
    center = Point(Ux, Uy)
    return Circle(center, center.distance_to(p1))


@CircleThroughThreePoints.set_numpy
def _CircleThroughThreePoints_numpy(p1, p2, p3):
    return circle_through_three_points_numpy_impl(p1, p2, p3)


@CircleThroughThreePoints.set_mpmath
def _CircleThroughThreePoints_mpmath(p1, p2, p3):
    return circle_through_three_points_mpmath_impl(p1, p2, p3)


@geometry_symbol("RegularPolygon", category="constructions")
def RegularPolygon(p1: Point, p2: Point, n: int, ccw: bool = True) -> Polygon:
    vertices = [p1, p2]
    angle_step = 2 * pi / n
    if not ccw:
        angle_step = -angle_step
    current_p = p2
    prev_p = p1
    for _ in range(2, n):
        dx = current_p.x - prev_p.x
        dy = current_p.y - prev_p.y
        rx = dx * cos(angle_step) - dy * sin(angle_step)
        ry = dx * sin(angle_step) + dy * cos(angle_step)
        next_p = Point(current_p.x + rx, current_p.y + ry)
        vertices.append(next_p)
        prev_p = current_p
        current_p = next_p
    return Polygon(vertices)


@RegularPolygon.set_numpy
def _RegularPolygon_numpy(p1, p2, n, ccw=True):
    import numpy as np

    vertices = [p1, p2]
    angle_step = 2 * np.pi / n
    if not ccw:
        angle_step = -angle_step
    curr_x, curr_y = p2
    prev_x, prev_y = p1
    for _ in range(2, n):
        dx = curr_x - prev_x
        dy = curr_y - prev_y
        c = np.cos(angle_step)
        s = np.sin(angle_step)
        rx = dx * c - dy * s
        ry = dx * s + dy * c
        next_x = curr_x + rx
        next_y = curr_y + ry
        vertices.append([next_x, next_y])
        prev_x, prev_y = curr_x, curr_y
        curr_x, curr_y = next_x, next_y
    return vertices


@RegularPolygon.set_mpmath
def _RegularPolygon_mpmath(p1, p2, n, ccw=True):
    from mpmath import cos, pi, sin

    from geosolver.geometry.mp.mp_impl import MPPoint
    from geosolver.geometry.mp.mp_polygon import MPPolygon

    if int(n) != n or n < 3 or p1 == p2:
        raise ValueError("RegularPolygon requires distinct vertices and integer n >= 3")
    n = int(n)

    vertices = [p1, p2]
    angle_step = 2 * pi / n
    if not ccw:
        angle_step = -angle_step
    current_p = p2
    prev_p = p1
    for _ in range(2, n):
        dx = current_p.x - prev_p.x
        dy = current_p.y - prev_p.y
        c = cos(angle_step)
        s = sin(angle_step)
        rx = dx * c - dy * s
        ry = dx * s + dy * c
        next_p = MPPoint(current_p.x + rx, current_p.y + ry)
        vertices.append(next_p)
        prev_p = current_p
        current_p = next_p
    return MPPolygon(vertices)


@geometry_symbol("InscribedPolygon", category="constructions")
def InscribedPolygon(circle: Circle, *t_params) -> Polygon:
    if not t_params or any(not 0 < t < 1 for t in t_params):
        raise GeometryDomainError("inscribed polygon parameters must be in (0, 1)")
    O = circle.center
    r = circle.radius
    P1 = Point(O.x, O.y + r)
    vertices = [P1]
    theta_start = pi / 2
    theta_prev = theta_start
    for t in t_params:
        remaining_angle = (theta_start + 2 * pi) - theta_prev
        theta_new = theta_prev + t * remaining_angle
        vertices.append(Point(O.x + r * cos(theta_new), O.y + r * sin(theta_new)))
        theta_prev = theta_new
    return Polygon(vertices)


@InscribedPolygon.set_numpy
def _InscribedPolygon_numpy(circle, *t_params):
    import numpy as np

    if not t_params or any(not 0 < t < 1 for t in t_params):
        raise GeometryDomainError("inscribed polygon parameters must be in (0, 1)")

    cx, cy, r = circle
    vertices = [[cx, cy + r]]
    theta_start = np.pi / 2
    theta_prev = theta_start
    for t in t_params:
        remaining = (theta_start + 2 * np.pi) - theta_prev
        theta_new = theta_prev + t * remaining
        vertices.append([cx + r * np.cos(theta_new), cy + r * np.sin(theta_new)])
        theta_prev = theta_new
    return vertices


@InscribedPolygon.set_mpmath
def _InscribedPolygon_mpmath(circle, *t_params):
    from geosolver.geometry.mp.mp_impl import mp_inscribed_polygon_vertices
    from geosolver.geometry.mp.mp_polygon import MPPolygon

    return MPPolygon(mp_inscribed_polygon_vertices(circle, *t_params))


@geometry_symbol("InscribedPolygonVertices", category="constructions")
def InscribedPolygonVertices(circle: Circle, *t_params) -> list[Point]:
    return InscribedPolygon(circle, *t_params).vertices


@InscribedPolygonVertices.set_numpy
def _InscribedPolygonVertices_numpy(circle, *t_params):
    return _InscribedPolygon_numpy(circle, *t_params)


@InscribedPolygonVertices.set_mpmath
def _InscribedPolygonVertices_mpmath(circle, *t_params):
    return _InscribedPolygon_mpmath(circle, *t_params).vertices
