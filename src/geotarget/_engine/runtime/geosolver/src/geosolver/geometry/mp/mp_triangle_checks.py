"""
Triangle classification/check helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPPoint


def mp_triangle_type(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional[str]:
    cross = (B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x)
    tol = mpf(10) ** (-(mp.dps - 5))

    if abs(cross) < tol:
        return None

    a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2
    c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2

    cos_A = b2 + c2 - a2
    cos_B = c2 + a2 - b2
    cos_C = a2 + b2 - c2

    tol_angle = mpf(10) ** (-(mp.dps // 2))
    if abs(cos_A) < tol_angle or abs(cos_B) < tol_angle or abs(cos_C) < tol_angle:
        return "right"
    if cos_A < 0 or cos_B < 0 or cos_C < 0:
        return "obtuse"
    return "acute"


def mp_middle_point_on_line(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPPoint"]:
    cross = (B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x)
    tol = mpf(10) ** (-(mp.dps - 5))
    if abs(cross) >= tol:
        return None

    dAB = (A.x - B.x) ** 2 + (A.y - B.y) ** 2
    dBC = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    dCA = (C.x - A.x) ** 2 + (C.y - A.y) ** 2

    if dCA >= dAB and dCA >= dBC:
        return B
    if dAB >= dBC and dAB >= dCA:
        return C
    return A


def mp_orthic_triangle(
    A: "MPPoint", B: "MPPoint", C: "MPPoint"
) -> Optional[Tuple["MPPoint", "MPPoint", "MPPoint"]]:
    cross = (B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x)
    tol = mpf(10) ** (-(mp.dps - 5))
    if abs(cross) < tol:
        return None

    point_cls = type(A)

    BC = C - B
    BC_len2 = BC.x**2 + BC.y**2
    if BC_len2 < tol:
        return None
    t_a = ((A.x - B.x) * BC.x + (A.y - B.y) * BC.y) / BC_len2
    Ha = point_cls(B.x + t_a * BC.x, B.y + t_a * BC.y)

    CA = A - C
    CA_len2 = CA.x**2 + CA.y**2
    if CA_len2 < tol:
        return None
    t_b = ((B.x - C.x) * CA.x + (B.y - C.y) * CA.y) / CA_len2
    Hb = point_cls(C.x + t_b * CA.x, C.y + t_b * CA.y)

    AB = B - A
    AB_len2 = AB.x**2 + AB.y**2
    if AB_len2 < tol:
        return None
    t_c = ((C.x - A.x) * AB.x + (C.y - A.y) * AB.y) / AB_len2
    Hc = point_cls(A.x + t_c * AB.x, A.y + t_c * AB.y)

    return (Ha, Hb, Hc)
