"""
Triangle circle helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint


def _mp_circle_class() -> type["MPCircle"]:
    from geosolver.geometry.mp.mp_impl import MPCircle

    return MPCircle


def _mp_midpoint(a: "MPPoint", b: "MPPoint") -> "MPPoint":
    from geosolver.geometry.mp.mp_impl import mp_midpoint

    return mp_midpoint(a, b)


def _mp_triangle_center(a: "MPPoint", b: "MPPoint", c: "MPPoint", n: int):
    from geosolver.geometry.mp.mp_impl import mp_triangle_center

    return mp_triangle_center(a, b, c, n)


def _mp_circumcenter(a: "MPPoint", b: "MPPoint", c: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_circumcenter

    return mp_circumcenter(a, b, c)


def _mp_circumcircle(a: "MPPoint", b: "MPPoint", c: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_circumcircle

    return mp_circumcircle(a, b, c)


def _mp_triangle_area(a: "MPPoint", b: "MPPoint", c: "MPPoint") -> mpf:
    from geosolver.geometry.mp.mp_impl import mp_triangle_area

    return mp_triangle_area(a, b, c)


def _tol() -> mpf:
    return mpf(10) ** (-(mp.dps - 10))


def mp_nine_point_center(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPPoint"]:
    orthocenter = _mp_triangle_center(A, B, C, 4)
    circumcenter = _mp_circumcenter(A, B, C)
    if orthocenter is None or circumcenter is None:
        return None
    return _mp_midpoint(orthocenter, circumcenter)


def mp_nine_point_circle(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPCircle"]:
    center = mp_nine_point_center(A, B, C)
    circumcircle = _mp_circumcircle(A, B, C)
    if center is None or circumcircle is None:
        return None

    circle_cls = _mp_circle_class()
    return circle_cls(center, circumcircle.radius / 2)


def mp_excircle(A: "MPPoint", B: "MPPoint", C: "MPPoint", vertex: str = "A") -> Optional["MPCircle"]:
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    s = (a + b + c) / 2

    tol = _tol()
    area = _mp_triangle_area(A, B, C)
    if area < tol:
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


def mp_excenter(A: "MPPoint", B: "MPPoint", C: "MPPoint", vertex: str = "A") -> Optional["MPPoint"]:
    excircle = mp_excircle(A, B, C, vertex)
    return excircle.center if excircle else None
