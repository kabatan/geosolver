"""
Triangle center computation extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf
from mpmath import sqrt as mp_sqrt

from geosolver.geometry.mp.mp_triangle_centers_special import compute_special_triangle_center

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPPoint


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_triangle_area(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    from geosolver.geometry.mp.mp_impl import mp_triangle_area

    return mp_triangle_area(A, B, C)


def _mp_circumcircle(A: MPPoint, B: MPPoint, C: MPPoint):
    from geosolver.geometry.mp.mp_impl import mp_circumcircle

    return mp_circumcircle(A, B, C)


def _mp_line_through_two_points(A: MPPoint, B: MPPoint):
    from geosolver.geometry.mp.mp_impl import mp_line_through_two_points

    return mp_line_through_two_points(A, B)


def _mp_line_line_intersection(l1, l2):
    from geosolver.geometry.mp.mp_impl import mp_line_line_intersection

    return mp_line_line_intersection(l1, l2)


def _mp_nine_point_circle(A: MPPoint, B: MPPoint, C: MPPoint):
    from geosolver.geometry.mp.mp_impl import mp_nine_point_circle

    return mp_nine_point_circle(A, B, C)


def _contact_point_on_segment(p1: MPPoint, p2: MPPoint, dist_from_p1: mpf, tol: mpf) -> MPPoint:
    point_cls = _mp_point_class()
    seg_len = p1.distance_to(p2)
    if seg_len < tol:
        return p1
    t = dist_from_p1 / seg_len
    return point_cls(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y))


def mp_triangle_center(A: MPPoint, B: MPPoint, C: MPPoint, n: int) -> MPPoint | None:
    point_cls = _mp_point_class()
    from geosolver.geometry.mp.mp_impl import _mp_area_tolerance_squared

    a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2
    c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2
    area = _mp_triangle_area(A, B, C)
    scale_squared = max(a2, b2, c2)
    if area == 0 or area < _mp_area_tolerance_squared(scale_squared):
        return None
    if n in (13, 14, 15, 16):
        return compute_special_triangle_center(A, B, C, n, point_cls)
    if n in (1, 7, 8, 9, 10, 11):
        a, b, c = mp.sqrt(a2), mp.sqrt(b2), mp.sqrt(c2)
        scale = max(a, b, c)
        tol = 32 * mp.eps * scale
    if n == 1:
        total = a + b + c
        if total <= tol:
            return None
        return point_cls(
            (a * A.x + b * B.x + c * C.x) / total, (a * A.y + b * B.y + c * C.y) / total
        )
    if n == 2:
        return point_cls((A.x + B.x + C.x) / 3, (A.y + B.y + C.y) / 3)
    if n == 3:
        circ = _mp_circumcircle(A, B, C)
        return circ.center if circ else None
    if n == 4:
        circ = _mp_circumcircle(A, B, C)
        if circ is None:
            return None
        O = circ.center
        return point_cls(A.x + B.x + C.x - 2 * O.x, A.y + B.y + C.y - 2 * O.y)
    if n == 5:
        circ = _mp_circumcircle(A, B, C)
        if circ is None:
            return None
        O = circ.center
        return point_cls((A.x + B.x + C.x - O.x) / 2, (A.y + B.y + C.y - O.y) / 2)
    if n == 6:
        total = a2 + b2 + c2
        if total <= 32 * mp.eps * scale_squared:
            return None
        return point_cls(
            (a2 * A.x + b2 * B.x + c2 * C.x) / total, (a2 * A.y + b2 * B.y + c2 * C.y) / total
        )
    if n == 7:
        s = (a + b + c) / 2
        D = _contact_point_on_segment(B, C, s - b, tol)
        E = _contact_point_on_segment(C, A, s - c, tol)
        line_AD = _mp_line_through_two_points(A, D)
        line_BE = _mp_line_through_two_points(B, E)
        if line_AD is None or line_BE is None:
            return None
        return _mp_line_line_intersection(line_AD, line_BE)
    if n == 8:
        s = (a + b + c) / 2
        Na = _contact_point_on_segment(B, C, s - c, tol)
        Nb = _contact_point_on_segment(C, A, s - a, tol)
        line_ANa = _mp_line_through_two_points(A, Na)
        line_BNb = _mp_line_through_two_points(B, Nb)
        if line_ANa is None or line_BNb is None:
            return None
        return _mp_line_line_intersection(line_ANa, line_BNb)
    if n == 9:
        s = (a + b + c) / 2
        wa = a * (s - a)
        wb = b * (s - b)
        wc = c * (s - c)
        total = wa + wb + wc
        return point_cls(
            (wa * A.x + wb * B.x + wc * C.x) / total, (wa * A.y + wb * B.y + wc * C.y) / total
        )
    if n == 10:
        total = 2 * (a + b + c)
        return point_cls(
            ((b + c) * A.x + (c + a) * B.x + (a + b) * C.x) / total,
            ((b + c) * A.y + (c + a) * B.y + (a + b) * C.y) / total,
        )
    if n == 11:
        nine = _mp_nine_point_circle(A, B, C)
        if nine is None:
            return None
        perimeter = a + b + c
        I = point_cls(
            (a * A.x + b * B.x + c * C.x) / perimeter, (a * A.y + b * B.y + c * C.y) / perimeter
        )
        N = nine.center
        R9 = nine.radius
        dx = I.x - N.x
        dy = I.y - N.y
        d2 = dx * dx + dy * dy
        if d2 <= tol * tol:
            from geosolver.errors import GeometryDomainError

            raise GeometryDomainError("Feuerbach point is not uniquely resolved")
        d = mp_sqrt(d2)
        t = R9 / d
        return point_cls(N.x + t * dx, N.y + t * dy)

    raise ValueError(f"Unsupported triangle center: n={n}")
