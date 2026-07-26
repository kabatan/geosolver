"""
Circle relation helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from mpmath import acos as mp_acos, atan2 as mp_atan2, cos as mp_cos, mp, mpf, sin as mp_sin

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPLine, MPPoint


def _mp_line_class() -> type["MPLine"]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def _mp_point_class() -> type["MPPoint"]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_line_through_two_points(p1: "MPPoint", p2: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_line_through_two_points

    return mp_line_through_two_points(p1, p2)


def _tol() -> mpf:
    return mpf(10) ** (-(mp.dps - 10))


def mp_tangent_line(circle: "MPCircle", point: "MPPoint") -> Optional[List["MPLine"]]:
    O = circle.center
    r = circle.radius
    d = point.distance_to(O)

    tol = _tol()
    line_cls = _mp_line_class()
    point_cls = _mp_point_class()

    if d < r - tol:
        return None

    if abs(d - r) < tol:
        dx = point.x - O.x
        dy = point.y - O.y
        a = -dy
        b = dx
        c = -(a * point.x + b * point.y)
        return [line_cls(a, b, c)]

    half_angle = mp_acos(r / d)
    base_angle = mp_atan2(point.y - O.y, point.x - O.x)

    angle1 = base_angle + half_angle
    angle2 = base_angle - half_angle

    T1 = point_cls(O.x + r * mp_cos(angle1), O.y + r * mp_sin(angle1))
    T2 = point_cls(O.x + r * mp_cos(angle2), O.y + r * mp_sin(angle2))

    line1 = _mp_line_through_two_points(point, T1)
    line2 = _mp_line_through_two_points(point, T2)
    return [line1, line2]


def mp_radical_axis(c1: "MPCircle", c2: "MPCircle") -> Optional["MPLine"]:
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


def mp_power_of_point(point: "MPPoint", circle: "MPCircle") -> mpf:
    d = point.distance_to(circle.center)
    return d**2 - circle.radius**2
