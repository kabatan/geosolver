"""NumPy backend implementation for triangle center operations."""

from __future__ import annotations

from typing import Any


def _sin_shifted_numpy_backend(sin_value: Any, cos_value: Any, sign: float, np_mod: Any) -> Any:
    sqrt3_div_2 = np_mod.sqrt(3) / 2
    half = 0.5
    return sin_value * half + cos_value * sign * sqrt3_div_2


def triangle_center_numpy_impl(A: Any, B: Any, C: Any, n: int, triangle_ops: Any) -> Any:
    if n == 1:
        return triangle_ops._Incenter_numpy(A, B, C)
    if n == 2:
        return triangle_ops._Centroid_numpy(A, B, C)
    if n == 3:
        return triangle_ops._circumcenter_numpy_impl(A, B, C)
    if n == 4:
        return triangle_ops._Orthocenter_numpy(A, B, C)

    import numpy as np

    a_arr = np.asarray(A)
    b_arr = np.asarray(B)
    c_arr = np.asarray(C)

    a = np.linalg.norm(b_arr - c_arr)
    b = np.linalg.norm(c_arr - a_arr)
    c = np.linalg.norm(a_arr - b_arr)
    u, v, w = 0.0, 0.0, 0.0

    if n == 5:
        center_o = triangle_ops._circumcenter_numpy_impl(A, B, C)
        center_h = triangle_ops._Orthocenter_numpy(A, B, C)
        if center_o is None or center_h is None:
            return None
        return [(center_o[0] + center_h[0]) / 2, (center_o[1] + center_h[1]) / 2]
    if n == 6:
        u, v, w = a**2, b**2, c**2
    elif n == 7:
        s = (a + b + c) / 2
        u, v, w = (s - b) * (s - c), (s - c) * (s - a), (s - a) * (s - b)
    elif n == 8:
        s = (a + b + c) / 2
        u, v, w = s - a, s - b, s - c
    elif n == 9:
        s = (a + b + c) / 2
        u, v, w = a * (s - a), b * (s - b), c * (s - c)
    elif n == 10:
        u, v, w = b + c, c + a, a + b
    elif n == 11:
        cos_a = (b**2 + c**2 - a**2) / (2 * b * c)
        cos_b = (c**2 + a**2 - b**2) / (2 * c * a)
        cos_c = (a**2 + b**2 - c**2) / (2 * a * b)

        cos_a = np.clip(cos_a, -1.0, 1.0)
        cos_b = np.clip(cos_b, -1.0, 1.0)
        cos_c = np.clip(cos_c, -1.0, 1.0)

        sin_a = np.sqrt(1 - cos_a**2)
        sin_b = np.sqrt(1 - cos_b**2)
        sin_c = np.sqrt(1 - cos_c**2)

        cos_b_minus_c = cos_b * cos_c + sin_b * sin_c
        cos_c_minus_a = cos_c * cos_a + sin_c * sin_a
        cos_a_minus_b = cos_a * cos_b + sin_a * sin_b

        u = 1 - cos_b_minus_c
        v = 1 - cos_c_minus_a
        w = 1 - cos_a_minus_b
    elif n in (13, 14, 15, 16):
        cos_a = (b**2 + c**2 - a**2) / (2 * b * c)
        cos_b = (c**2 + a**2 - b**2) / (2 * c * a)
        cos_c = (a**2 + b**2 - c**2) / (2 * a * b)

        cos_a = np.clip(cos_a, -1.0, 1.0)
        cos_b = np.clip(cos_b, -1.0, 1.0)
        cos_c = np.clip(cos_c, -1.0, 1.0)

        sin_a = np.sqrt(1 - cos_a**2)
        sin_b = np.sqrt(1 - cos_b**2)
        sin_c = np.sqrt(1 - cos_c**2)

        sign = 1 if n in (13, 15) else -1
        sin_a_shift = _sin_shifted_numpy_backend(sin_a, cos_a, sign, np)
        sin_b_shift = _sin_shifted_numpy_backend(sin_b, cos_b, sign, np)
        sin_c_shift = _sin_shifted_numpy_backend(sin_c, cos_c, sign, np)

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
    if abs(total) < 1e-12:
        return None
    point = (u * a_arr + v * b_arr + w * c_arr) / total
    return [point[0], point[1]]