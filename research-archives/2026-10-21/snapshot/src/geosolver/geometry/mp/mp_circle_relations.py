"""
Circle relation helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf

from geosolver.errors import GeometryDomainError, NoIntersectionError

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPLine, MPPoint


def _mp_line_class() -> type[MPLine]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_line_through_two_points(p1: MPPoint, p2: MPPoint):
    from geosolver.geometry.mp.mp_impl import mp_line_through_two_points

    return mp_line_through_two_points(p1, p2)


def _tol() -> mpf:
    return mpf(10) ** (-(mp.dps - 10))


def mp_tangent_line(circle: MPCircle, point: MPPoint) -> list[MPLine] | None:
    O = circle.center
    r = circle.radius
    vx = point.x - O.x
    vy = point.y - O.y
    d2 = vx * vx + vy * vy
    r2 = r * r
    line_cls = _mp_line_class()
    point_cls = _mp_point_class()

    difference = d2 - r2
    if circle._has_proven_incidence(point):
        return [line_cls(vx, vy, -(vx * point.x + vy * point.y))]
    if difference < 0:
        raise NoIntersectionError("an interior point has no real tangent line")
    if difference == 0:
        return [line_cls(vx, vy, -(vx * point.x + vy * point.y))]
    if d2 == 0:
        raise GeometryDomainError("tangent is undefined at the circle center")
    offset = r * mp.sqrt(difference) / d2
    base_x = O.x + r2 * vx / d2
    base_y = O.y + r2 * vy / d2
    first_point = point_cls(base_x + offset * (-vy), base_y + offset * vx)
    second_point = point_cls(base_x - offset * (-vy), base_y - offset * vx)
    first = _mp_line_through_two_points(point, first_point)
    second = _mp_line_through_two_points(point, second_point)
    if first is None or second is None:
        raise GeometryDomainError("failed to construct tangent line")
    return [first, second]


def mp_radical_axis(c1: MPCircle, c2: MPCircle) -> MPLine | None:
    O1, O2 = c1.center, c2.center
    r1, r2 = c1.radius, c2.radius

    d = O1.distance_to(O2)
    if d < _tol():
        return None

    a = 2 * (O2.x - O1.x)
    b = 2 * (O2.y - O1.y)
    c = (O1.x**2 + O1.y**2 - r1**2) - (O2.x**2 + O2.y**2 - r2**2)

    line_cls = _mp_line_class()
    return line_cls(a, b, c)


def mp_power_of_point(point: MPPoint, circle: MPCircle) -> mpf:
    return (point.x - circle.center.x) ** 2 + (point.y - circle.center.y) ** 2 - circle.radius**2
