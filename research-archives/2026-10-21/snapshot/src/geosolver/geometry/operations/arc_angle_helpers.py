"""Angle and trigonometric helper functions for arc operations."""

from __future__ import annotations

import math
from typing import Any

from sympy import N as _N
from sympy import atan2, pi

try:
    import mpmath
except ImportError:  # pragma: no cover
    mpmath = None


def get_atan2(y: Any, x: Any) -> Any:
    if mpmath and (isinstance(y, mpmath.mpf) or isinstance(x, mpmath.mpf)):
        return mpmath.atan2(y, x)
    if isinstance(y, int | float) and isinstance(x, int | float):
        return math.atan2(y, x)
    return atan2(y, x)


def point_angle(center: Any, point: Any) -> Any:
    return get_atan2(point.y - center.y, point.x - center.x)


def to_comparable_angle(val: Any) -> Any:
    if mpmath and isinstance(val, mpmath.mpf):
        return val
    try:
        return float(_N(val))
    except Exception:
        return None


def in_arc_ccw(x: Any, start: Any, end: Any) -> bool:
    if start <= end:
        return start <= x <= end
    return x >= start or x <= end


def normalize_angle(angle: Any) -> Any:
    if mpmath and isinstance(angle, mpmath.mpf):
        two_pi = 2 * mpmath.pi
        result = angle % two_pi
        if result < 0:
            result += two_pi
        return result

    if isinstance(angle, int | float):
        two_pi = 2 * math.pi
        result = angle % two_pi
        if result < 0:
            result += two_pi
        return result

    two_pi = 2 * pi
    result = angle
    try:
        val = float(_N(result))
        turns = math.floor(val / (2 * math.pi))
        result = result - turns * two_pi
    except Exception:
        pass
    return result


def angle_in_arc(
    angle: Any,
    start_angle: Any,
    end_angle: Any,
    including_angle: Any = None,
    excluding_angle: Any = None,
) -> bool:
    a = normalize_angle(angle)
    s = normalize_angle(start_angle)
    e = normalize_angle(end_angle)

    a_v = to_comparable_angle(a)
    s_v = to_comparable_angle(s)
    e_v = to_comparable_angle(e)

    if a_v is None or s_v is None or e_v is None:
        return True

    pi_val = mpmath.pi if mpmath and isinstance(a_v, mpmath.mpf) else math.pi

    two_pi = 2 * pi_val

    inc_v = None
    if including_angle is not None:
        inc_v = to_comparable_angle(normalize_angle(including_angle))

    exc_v = None
    if excluding_angle is not None:
        exc_v = to_comparable_angle(normalize_angle(excluding_angle))

    in_arc1 = in_arc_ccw(a_v, s_v, e_v)
    in_arc2 = not in_arc1

    if inc_v is not None:
        inc_in_arc1 = in_arc_ccw(inc_v, s_v, e_v)
        use_arc1 = inc_in_arc1
    elif exc_v is not None:
        exc_in_arc1 = in_arc_ccw(exc_v, s_v, e_v)
        use_arc1 = not exc_in_arc1
    else:
        diff = e_v - s_v
        if diff < 0:
            diff += two_pi
        use_arc1 = diff <= pi_val

    return (in_arc1 and use_arc1) or (in_arc2 and not use_arc1)


def get_dynamic_tolerance_arc() -> Any:
    if mpmath:
        try:
            dps = mpmath.mp.dps
            return mpmath.mpf(10) ** (-dps + 10)
        except Exception:
            pass
    return 1e-9
