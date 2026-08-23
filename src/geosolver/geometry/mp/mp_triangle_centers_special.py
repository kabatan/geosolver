"""Special high-index triangle center computations (n=13..16)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from mpmath import acos as mp_acos, mpf, pi as mp_pi, sin as mp_sin, sqrt as mp_sqrt

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPPoint


def _angles_and_side_lengths(
    A: "MPPoint", B: "MPPoint", C: "MPPoint"
) -> tuple[Any, Any, Any, Any, Any, Any]:
    a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2
    c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2
    a = mp_sqrt(a2)
    b = mp_sqrt(b2)
    c = mp_sqrt(c2)

    cos_A = (b2 + c2 - a2) / (2 * b * c) if b * c != 0 else mpf(1)
    cos_B = (c2 + a2 - b2) / (2 * c * a) if c * a != 0 else mpf(1)
    cos_C = (a2 + b2 - c2) / (2 * a * b) if a * b != 0 else mpf(1)

    angle_A = mp_acos(max(min(cos_A, mpf(1)), mpf(-1)))
    angle_B = mp_acos(max(min(cos_B, mpf(1)), mpf(-1)))
    angle_C = mp_acos(max(min(cos_C, mpf(1)), mpf(-1)))
    return angle_A, angle_B, angle_C, a, b, c


def compute_special_triangle_center(
    A: "MPPoint",
    B: "MPPoint",
    C: "MPPoint",
    n: int,
    tol: Any,
    point_cls: type["MPPoint"],
    centroid_fn,
) -> Optional["MPPoint"]:
    if n not in {13, 14, 15, 16}:
        return None

    angle_A, angle_B, angle_C, _, _, _ = _angles_and_side_lengths(A, B, C)
    offset = mp_pi / 3

    if n == 13:
        threshold = 2 * mp_pi / 3
        if angle_A >= threshold:
            return A
        if angle_B >= threshold:
            return B
        if angle_C >= threshold:
            return C
        sin_A_offset = mp_sin(angle_A + offset)
        sin_B_offset = mp_sin(angle_B + offset)
        sin_C_offset = mp_sin(angle_C + offset)
        if abs(sin_A_offset) < tol or abs(sin_B_offset) < tol or abs(sin_C_offset) < tol:
            return centroid_fn(A, B, C)
        wa = 1 / sin_A_offset
        wb = 1 / sin_B_offset
        wc = 1 / sin_C_offset
        total = wa + wb + wc
        return point_cls((wa * A.x + wb * B.x + wc * C.x) / total, (wa * A.y + wb * B.y + wc * C.y) / total)

    if n == 14:
        sin_A_offset = mp_sin(angle_A - offset)
        sin_B_offset = mp_sin(angle_B - offset)
        sin_C_offset = mp_sin(angle_C - offset)
        if abs(sin_A_offset) < tol or abs(sin_B_offset) < tol or abs(sin_C_offset) < tol:
            return centroid_fn(A, B, C)
        wa = 1 / sin_A_offset
        wb = 1 / sin_B_offset
        wc = 1 / sin_C_offset
        total = wa + wb + wc
        return point_cls((wa * A.x + wb * B.x + wc * C.x) / total, (wa * A.y + wb * B.y + wc * C.y) / total)

    if n == 15:
        wa = mp_sin(angle_A + offset)
        wb = mp_sin(angle_B + offset)
        wc = mp_sin(angle_C + offset)
        total = wa + wb + wc
        if abs(total) < tol:
            return centroid_fn(A, B, C)
        return point_cls((wa * A.x + wb * B.x + wc * C.x) / total, (wa * A.y + wb * B.y + wc * C.y) / total)

    wa = mp_sin(angle_A - offset)
    wb = mp_sin(angle_B - offset)
    wc = mp_sin(angle_C - offset)
    total = wa + wb + wc
    if abs(total) < tol:
        return centroid_fn(A, B, C)
    return point_cls((wa * A.x + wb * B.x + wc * C.x) / total, (wa * A.y + wb * B.y + wc * C.y) / total)
