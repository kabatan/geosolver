"""
Triangle circle helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint


def _mp_circle_class() -> type[MPCircle]:
    from geosolver.geometry.mp.mp_impl import MPCircle

    return MPCircle


def _mp_circumcircle(a: MPPoint, b: MPPoint, c: MPPoint):
    from geosolver.geometry.mp.mp_impl import mp_circumcircle

    return mp_circumcircle(a, b, c)


def _mp_triangle_area(a: MPPoint, b: MPPoint, c: MPPoint) -> mpf:
    from geosolver.geometry.mp.mp_impl import mp_triangle_area

    return mp_triangle_area(a, b, c)


def mp_nine_point_center(A: MPPoint, B: MPPoint, C: MPPoint) -> MPPoint | None:
    circ = _mp_circumcircle(A, B, C)
    if circ is None:
        return None
    center_o = circ.center
    return type(A)((A.x + B.x + C.x - center_o.x) / 2, (A.y + B.y + C.y - center_o.y) / 2)


def mp_nine_point_circle(A: MPPoint, B: MPPoint, C: MPPoint) -> MPCircle | None:
    circ = _mp_circumcircle(A, B, C)
    if circ is None:
        return None
    center_o = circ.center
    center = type(A)((A.x + B.x + C.x - center_o.x) / 2, (A.y + B.y + C.y - center_o.y) / 2)
    return _mp_circle_class()(center, circ.radius / 2)


def mp_excircle(A: MPPoint, B: MPPoint, C: MPPoint, vertex: str = "A") -> MPCircle | None:
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    s = (a + b + c) / 2

    tol = 32 * mp.eps * max(a, b, c)
    area = _mp_triangle_area(A, B, C)
    if area == 0 or area < tol * max(a, b, c):
        return None

    vertex_u = vertex.upper()
    if vertex_u == "A":
        denom = -a + b + c
        if abs(denom) < tol:
            return None
        center_x = (-a * A.x + b * B.x + c * C.x) / denom
        center_y = (-a * A.y + b * B.y + c * C.y) / denom
        radius = area / (s - a)
    elif vertex_u == "B":
        denom = a - b + c
        if abs(denom) < tol:
            return None
        center_x = (a * A.x - b * B.x + c * C.x) / denom
        center_y = (a * A.y - b * B.y + c * C.y) / denom
        radius = area / (s - b)
    elif vertex_u == "C":
        denom = a + b - c
        if abs(denom) < tol:
            return None
        center_x = (a * A.x + b * B.x - c * C.x) / denom
        center_y = (a * A.y + b * B.y - c * C.y) / denom
        radius = area / (s - c)
    else:
        raise ValueError(f"Invalid vertex: {vertex}. Must be 'A', 'B', or 'C'")

    point_cls = type(A)
    circle_cls = _mp_circle_class()
    return circle_cls(point_cls(center_x, center_y), radius)


def mp_excenter(A: MPPoint, B: MPPoint, C: MPPoint, vertex: str = "A") -> MPPoint | None:
    excircle = mp_excircle(A, B, C, vertex)
    return excircle.center if excircle else None
