"""Core TriangleCenter implementation and backend bindings."""

from typing import Any

from sympy import sqrt

from geosolver.geometry.entities.base import Point
from geosolver.geometry.operations.triangle_centers_numpy_backend import (
    triangle_center_numpy_impl,
)
from geosolver.geometry.registry import geometry_symbol


def _triangle_ops():
    import geosolver.geometry.operations.triangle as triangle_ops

    return triangle_ops


def _sin_shifted_symbolic(sin_value: Any, cos_value: Any, sign: int) -> Any:
    sqrt3_div_2 = sqrt(3) / 2
    half = 0.5
    return sin_value * half + cos_value * sign * sqrt3_div_2


@geometry_symbol("TriangleCenter", category="triangle")
def TriangleCenter(A: Point, B: Point, C: Point, n: int) -> Point | None:
    """Generic Triangle Center function (Kimberling center X(n))."""
    triangle_ops = _triangle_ops()
    if n == 1:
        return triangle_ops.Incenter(A, B, C)
    if n == 2:
        return triangle_ops.Centroid(A, B, C)
    if n == 3:
        return triangle_ops.Circumcenter(A, B, C)
    if n == 4:
        return triangle_ops.Orthocenter(A, B, C)
    if n == 5:
        center_o = triangle_ops.Circumcenter(A, B, C)
        center_h = triangle_ops.Orthocenter(A, B, C)
        if center_o is None or center_h is None:
            return None
        return Point((center_o.x + center_h.x) / 2, (center_o.y + center_h.y) / 2)

    a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2
    c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2

    if n == 6:
        denom = a2 + b2 + c2
        if denom == 0:
            return None
        return Point(
            (a2 * A.x + b2 * B.x + c2 * C.x) / denom,
            (a2 * A.y + b2 * B.y + c2 * C.y) / denom,
        )

    a = sqrt(a2)
    b = sqrt(b2)
    c = sqrt(c2)

    if n == 7:
        s = (a + b + c) / 2
        u = (s - b) * (s - c)
        v = (s - c) * (s - a)
        w = (s - a) * (s - b)
    elif n == 8:
        s = (a + b + c) / 2
        u = s - a
        v = s - b
        w = s - c
    elif n == 9:
        s = (a + b + c) / 2
        u = a * (s - a)
        v = b * (s - b)
        w = c * (s - c)
    elif n == 10:
        u = b + c
        v = c + a
        w = a + b
    elif n == 11:
        cos_a = (b2 + c2 - a2) / (2 * b * c)
        cos_b = (c2 + a2 - b2) / (2 * c * a)
        cos_c = (a2 + b2 - c2) / (2 * a * b)

        sin_a = sqrt(1 - cos_a**2)
        sin_b = sqrt(1 - cos_b**2)
        sin_c = sqrt(1 - cos_c**2)

        cos_b_minus_c = cos_b * cos_c + sin_b * sin_c
        cos_c_minus_a = cos_c * cos_a + sin_c * sin_a
        cos_a_minus_b = cos_a * cos_b + sin_a * sin_b

        u = 1 - cos_b_minus_c
        v = 1 - cos_c_minus_a
        w = 1 - cos_a_minus_b
    elif n in (13, 14, 15, 16):
        cos_a = (b2 + c2 - a2) / (2 * b * c)
        cos_b = (c2 + a2 - b2) / (2 * c * a)
        cos_c = (a2 + b2 - c2) / (2 * a * b)

        sin_a = sqrt(1 - cos_a**2)
        sin_b = sqrt(1 - cos_b**2)
        sin_c = sqrt(1 - cos_c**2)

        sign = 1 if n in (13, 15) else -1
        sin_a_shift = _sin_shifted_symbolic(sin_a, cos_a, sign)
        sin_b_shift = _sin_shifted_symbolic(sin_b, cos_b, sign)
        sin_c_shift = _sin_shifted_symbolic(sin_c, cos_c, sign)

        if n in (13, 14):
            u = sin_a * sin_b_shift * sin_c_shift
            v = sin_b * sin_c_shift * sin_a_shift
            w = sin_c * sin_a_shift * sin_b_shift
        else:
            u = sin_a * sin_a_shift
            v = sin_b * sin_b_shift
            w = sin_c * sin_c_shift
    else:
        return None

    total = u + v + w
    return Point((u * A.x + v * B.x + w * C.x) / total, (u * A.y + v * B.y + w * C.y) / total)


@TriangleCenter.set_numpy
def _TriangleCenter_numpy(A: Any, B: Any, C: Any, n: int):
    """NumPy implementation for Triangle Centers."""
    triangle_ops = _triangle_ops()
    return triangle_center_numpy_impl(A, B, C, n, triangle_ops)


@TriangleCenter.set_mpmath
def _TriangleCenter_mpmath(A: Any, B: Any, C: Any, n: int):
    """mpmath implementation."""
    from geosolver.geometry.mp.mp_impl import mp_triangle_center

    return mp_triangle_center(A, B, C, int(n))
