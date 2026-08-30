"""
Line/angle relation helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import (
    acos as mp_acos,
)
from mpmath import (
    asin as mp_asin,
)
from mpmath import (
    mp,
    mpf,
)
from mpmath import (
    pi as mp_pi,
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
    original_dps = mp.dps
    precision_scope = mp.workdps(original_dps * 2 + 50)
    precision_scope.__enter__()

    try:
        norm1 = v1.norm()
        norm2 = v2.norm()

        if norm1 == 0 or norm2 == 0:
            raise ValueError("Angle undefined for zero-length vector")

        point_cls = _mp_point_class()
        n1 = point_cls(v1.x / norm1, v1.y / norm1)
        n2 = point_cls(v2.x / norm2, v2.y / norm2)

        cos_angle = n1.dot(n2)
        sin_angle = n1.x * n2.y - n1.y * n2.x

        abs_cos = abs(cos_angle)
        abs_sin = abs(sin_angle)

        if abs_cos > abs_sin:
            if abs_sin > 1:
                abs_sin = mpf("1")
            angle = mp_asin(abs_sin)
            if cos_angle < 0:
                angle = mp_pi - angle
        else:
            if cos_angle > 1:
                cos_angle = mpf("1")
            elif cos_angle < -1:
                cos_angle = mpf("-1")
            angle = mp_acos(cos_angle)

        return +angle
    finally:
        precision_scope.__exit__(None, None, None)


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
    original_dps = mp.dps
    precision_scope = mp.workdps(original_dps * 2 + 50)
    precision_scope.__enter__()

    try:
        v1 = l1.direction_vector()
        v2 = l2.direction_vector()

        norm1 = v1.norm()
        norm2 = v2.norm()

        if norm1 == 0 or norm2 == 0:
            raise ValueError("Angle undefined for zero-length line direction")

        cross = v1.x * v2.y - v1.y * v2.x
        sin_angle = cross / (norm1 * norm2)
        abs_sin = abs(sin_angle)

        if abs_sin < mpf("0.5"):
            if abs_sin > 1:
                abs_sin = mpf("1")
            angle = mp_asin(abs_sin)
        else:
            cos_angle = v1.dot(v2) / (norm1 * norm2)
            if cos_angle > 1:
                cos_angle = mpf("1")
            elif cos_angle < -1:
                cos_angle = mpf("-1")
            angle = mp_acos(abs(cos_angle))
        return +angle
    finally:
        precision_scope.__exit__(None, None, None)
