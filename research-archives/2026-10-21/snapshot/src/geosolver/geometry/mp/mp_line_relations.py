"""
Line/angle relation helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import (
    mp,
    mpf,
)
from mpmath import (
    sqrt as mp_sqrt,
)

from geosolver.errors import InfiniteSolutionsError, NoIntersectionError

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPLine, MPPoint


def _mp_line_class() -> type[MPLine]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _line_tolerance() -> mpf:
    return mpf(10) ** (-max(50, int(mp.dps) - 10))


def mp_line_through_two_points(p1: MPPoint, p2: MPPoint) -> MPLine | None:
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    if dx == 0 and dy == 0:
        return None

    a = -dy
    b = dx
    c = -(a * p1.x + b * p1.y)
    line_cls = _mp_line_class()
    return line_cls(a, b, c)


def mp_perpendicular_line(line: MPLine, point: MPPoint) -> MPLine:
    a = line.b
    b = -line.a
    c = -(a * point.x + b * point.y)
    line_cls = _mp_line_class()
    return line_cls(a, b, c)


def mp_line_line_intersection(l1: MPLine, l2: MPLine) -> MPPoint | None:
    det = l1.a * l2.b - l2.a * l1.b
    if det == 0:
        if l1.a * l2.c == l2.a * l1.c and l1.b * l2.c == l2.b * l1.c:
            raise InfiniteSolutionsError("coincident lines have infinitely many intersections")
        raise NoIntersectionError("parallel lines do not intersect")

    x = (l1.b * l2.c - l2.b * l1.c) / det
    y = (l2.a * l1.c - l1.a * l2.c) / det
    point_cls = _mp_point_class()
    return point_cls(x, y)


def mp_angle_between_vectors(v1: MPPoint, v2: MPPoint) -> mpf:
    cross, dot = _angle_products(v1, v2)
    return mp.atan2(abs(cross), dot)


def _angle_products(v1: MPPoint, v2: MPPoint) -> tuple[mpf, mpf]:
    if (v1.x == 0 and v1.y == 0) or (v2.x == 0 and v2.y == 0):
        raise ValueError("Angle undefined for zero-length vector")
    # fdot accumulates exact binary products before rounding the sum once.  This
    # avoids cancellation in nearly parallel/perpendicular directions without
    # doubling the precision of every norm, division and inverse trig function.
    cross = mp.fdot((v1.x, v1.y), (v2.y, -v2.x))
    dot = mp.fdot((v1.x, v1.y), (v2.x, v2.y))
    return cross, dot


def mp_parallelism_measure(l1: MPLine, l2: MPLine, method: str = "cross") -> mpf:
    v1 = l1.direction_vector()
    v2 = l2.direction_vector()

    norm1 = v1.norm()
    norm2 = v2.norm()

    tol = _line_tolerance()
    if norm1 < tol or norm2 < tol:
        return mpf("0")

    point_cls = _mp_point_class()
    n1 = point_cls(v1.x / norm1, v1.y / norm1)
    n2 = point_cls(v2.x / norm2, v2.y / norm2)

    if method == "cross":
        return n1.x * n2.y - n1.y * n2.x
    if method == "diff":
        diff_same = mp_sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2)
        diff_opp = mp_sqrt((n1.x + n2.x) ** 2 + (n1.y + n2.y) ** 2)
        return min(diff_same, diff_opp)
    raise ValueError(f"Unknown method: {method}")


def mp_angle_between_lines(l1: MPLine, l2: MPLine) -> mpf:
    cross, dot = _angle_products(l1.direction_vector(), l2.direction_vector())
    return mp.atan2(abs(cross), abs(dot))
