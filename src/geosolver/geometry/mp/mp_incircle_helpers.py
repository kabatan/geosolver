"""
Incircle-related helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING, Union

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint


def _mp_point_class() -> type["MPPoint"]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_circle_class() -> type["MPCircle"]:
    from geosolver.geometry.mp.mp_impl import MPCircle

    return MPCircle


def _mp_triangle_area(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> mpf:
    from geosolver.geometry.mp.mp_impl import mp_triangle_area

    return mp_triangle_area(A, B, C)


def _mp_area_tolerance(scale_len: mpf) -> mpf:
    from geosolver.geometry.mp.mp_impl import _mp_area_tolerance

    return _mp_area_tolerance(scale_len)


def _contact_on_segment(P1: "MPPoint", P2: "MPPoint", dist_from_P1: mpf, tol: mpf) -> "MPPoint":
    point_cls = _mp_point_class()
    seg_len = P1.distance_to(P2)
    if seg_len < tol:
        return P1
    t = dist_from_P1 / seg_len
    return point_cls(P1.x + t * (P2.x - P1.x), P1.y + t * (P2.y - P1.y))


def mp_incircle_contact_point(
    A: "MPPoint", B: "MPPoint", C: "MPPoint", side: Optional[Tuple["MPPoint", "MPPoint"]] = None
) -> Union[List["MPPoint"], "MPPoint", None]:
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)

    try:
        area = _mp_triangle_area(A, B, C)
        scale = max(mpf("1"), a, b, c)
        if area < _mp_area_tolerance(scale):
            return None
    except Exception:
        pass

    s = (a + b + c) / 2
    tol = mpf(10) ** (-(mp.dps - 10))

    D = _contact_on_segment(B, C, s - b, tol)
    E = _contact_on_segment(C, A, s - c, tol)
    F = _contact_on_segment(A, B, s - a, tol)

    if side is None:
        return [D, E, F]

    P1, P2 = side
    if (P1 == B and P2 == C) or (P1 == C and P2 == B):
        return D
    if (P1 == C and P2 == A) or (P1 == A and P2 == C):
        return E
    if (P1 == A and P2 == B) or (P1 == B and P2 == A):
        return F
    raise ValueError("Invalid side specification")


def mp_incircle(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPCircle"]:
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)

    perimeter = a + b + c
    if perimeter < mpf("1e-30"):
        return None

    try:
        area = _mp_triangle_area(A, B, C)
        scale = max(mpf("1"), a, b, c)
        if area < _mp_area_tolerance(scale):
            return None
    except Exception:
        pass

    point_cls = _mp_point_class()
    x = (a * A.x + b * B.x + c * C.x) / perimeter
    y = (a * A.y + b * B.y + c * C.y) / perimeter
    center = point_cls(x, y)

    area = _mp_triangle_area(A, B, C)
    s = perimeter / 2
    radius = area / s

    circle_cls = _mp_circle_class()
    return circle_cls(center, radius)
