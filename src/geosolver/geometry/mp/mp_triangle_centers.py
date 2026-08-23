"""
Triangle center computation extracted from mp_impl.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from mpmath import mp, mpf, sin as mp_sin, sqrt as mp_sqrt
from geosolver.geometry.mp.mp_triangle_centers_special import compute_special_triangle_center

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPPoint


def _mp_point_class() -> type["MPPoint"]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_area_tolerance(scale_len: mpf) -> mpf:
    from geosolver.geometry.mp.mp_impl import _mp_area_tolerance

    return _mp_area_tolerance(scale_len)


def _mp_triangle_area(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> mpf:
    from geosolver.geometry.mp.mp_impl import mp_triangle_area

    return mp_triangle_area(A, B, C)


def _mp_circumcircle(A: "MPPoint", B: "MPPoint", C: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_circumcircle

    return mp_circumcircle(A, B, C)


def _mp_midpoint(A: "MPPoint", B: "MPPoint") -> "MPPoint":
    from geosolver.geometry.mp.mp_impl import mp_midpoint

    return mp_midpoint(A, B)


def _mp_line_through_two_points(A: "MPPoint", B: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_line_through_two_points

    return mp_line_through_two_points(A, B)


def _mp_line_line_intersection(l1, l2):
    from geosolver.geometry.mp.mp_impl import mp_line_line_intersection

    return mp_line_line_intersection(l1, l2)


def _mp_incircle(A: "MPPoint", B: "MPPoint", C: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_incircle

    return mp_incircle(A, B, C)


def _mp_nine_point_circle(A: "MPPoint", B: "MPPoint", C: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_nine_point_circle

    return mp_nine_point_circle(A, B, C)


def _mp_centroid(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> "MPPoint":
    from geosolver.geometry.mp.mp_impl import mp_centroid

    return mp_centroid(A, B, C)


def _contact_point_on_segment(p1: "MPPoint", p2: "MPPoint", dist_from_p1: mpf, tol: mpf) -> "MPPoint":
    point_cls = _mp_point_class()
    seg_len = p1.distance_to(p2)
    if seg_len < tol:
        return p1
    t = dist_from_p1 / seg_len
    return point_cls(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y))


def mp_triangle_center(A: "MPPoint", B: "MPPoint", C: "MPPoint", n: int) -> Optional["MPPoint"]:
    point_cls = _mp_point_class()
    tol = mpf(10) ** (-(mp.dps - 10))

    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)

    area = _mp_triangle_area(A, B, C)
    scale = max(mpf("1"), a, b, c)
    if area < max(tol, _mp_area_tolerance(scale)):
        return None

    if n == 1:
        total = a + b + c
        if total < tol:
            return None
        return point_cls((a * A.x + b * B.x + c * C.x) / total, (a * A.y + b * B.y + c * C.y) / total)
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
        orthocenter = mp_triangle_center(A, B, C, 4)
        circumcenter = mp_triangle_center(A, B, C, 3)
        if orthocenter is None or circumcenter is None:
            return None
        return _mp_midpoint(orthocenter, circumcenter)
    if n == 6:
        a2, b2, c2 = a**2, b**2, c**2
        total = a2 + b2 + c2
        if total < tol:
            return None
        return point_cls((a2 * A.x + b2 * B.x + c2 * C.x) / total, (a2 * A.y + b2 * B.y + c2 * C.y) / total)
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
        return point_cls((wa * A.x + wb * B.x + wc * C.x) / total, (wa * A.y + wb * B.y + wc * C.y) / total)
    if n == 10:
        Ma = _mp_midpoint(B, C)
        Mb = _mp_midpoint(C, A)
        Mc = _mp_midpoint(A, B)
        return mp_triangle_center(Ma, Mb, Mc, 1)
    if n == 11:
        inc = _mp_incircle(A, B, C)
        nine = _mp_nine_point_circle(A, B, C)
        if inc is None or nine is None:
            return None
        I = inc.center
        N = nine.center
        R9 = nine.radius
        dx = I.x - N.x
        dy = I.y - N.y
        d2 = dx * dx + dy * dy
        if d2 < tol:
            return I
        d = mp_sqrt(d2)
        if d == 0:
            return I
        t = R9 / d
        return point_cls(N.x + t * dx, N.y + t * dy)

    special_center = compute_special_triangle_center(A, B, C, n, tol, point_cls, _mp_centroid)
    if special_center is not None:
        return special_center

    raise ValueError(f"Unsupported triangle center: n={n}")
