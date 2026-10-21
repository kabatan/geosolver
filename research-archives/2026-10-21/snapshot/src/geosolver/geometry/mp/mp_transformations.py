"""
Point transformation helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import cos as mp_cos
from mpmath import sin as mp_sin

from geosolver.geometry.mp.mp_conversion import to_mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPLine, MPPoint


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_line_class() -> type[MPLine]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def mp_closest_point(point: MPPoint, line: MPLine) -> MPPoint:
    t = -(line.a * point.x + line.b * point.y + line.c)
    point_cls = _mp_point_class()
    return point_cls(point.x + t * line.a, point.y + t * line.b)


def mp_rotate(point: MPPoint, center: MPPoint, angle) -> MPPoint:
    angle_mpf = to_mpf(angle)
    dx = point.x - center.x
    dy = point.y - center.y

    cos_a = mp_cos(angle_mpf)
    sin_a = mp_sin(angle_mpf)

    new_x = center.x + dx * cos_a - dy * sin_a
    new_y = center.y + dx * sin_a + dy * cos_a
    point_cls = _mp_point_class()
    return point_cls(new_x, new_y)


def mp_reflect(point: MPPoint, mirror) -> MPPoint:
    line_cls = _mp_line_class()
    point_cls = _mp_point_class()

    if isinstance(mirror, line_cls):
        foot = mp_closest_point(point, mirror)
        return point_cls(2 * foot.x - point.x, 2 * foot.y - point.y)
    if isinstance(mirror, point_cls):
        return point_cls(2 * mirror.x - point.x, 2 * mirror.y - point.y)
    raise TypeError(f"Unsupported mirror type: {type(mirror)}")
