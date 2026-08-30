"""Helpers for arc membership checks."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from sympy import N as _N

try:
    import mpmath
except ImportError:  # pragma: no cover
    mpmath = None

from geosolver.geometry.operations.arc_angle_helpers import (
    angle_in_arc,
    get_dynamic_tolerance_arc,
    point_angle,
)


def point_on_arc(arc: Any, point: Any) -> bool:
    """点が弧上にあるかどうかを判定"""
    dist = point.distance_to(arc.center)

    if mpmath and isinstance(dist, mpmath.mpf):
        radius_value = (
            mpmath.mpf(arc.radius) if not isinstance(arc.radius, mpmath.mpf) else arc.radius
        )
        tolerance = get_dynamic_tolerance_arc()
        if abs(dist - radius_value) > tolerance:
            return False
    elif hasattr(dist, "func"):
        try:
            dps = 50
            if mpmath:
                with suppress(Exception):
                    dps = max(50, int(mpmath.mp.dps * 4 / 5))
            val = float(_N(dist, dps))
            radius_value = float(_N(arc.radius, dps))
            tolerance = get_dynamic_tolerance_arc()
            if abs(val - radius_value) > tolerance:
                return False
        except Exception:
            pass
    else:
        radius_value = float(arc.radius)
        tolerance = get_dynamic_tolerance_arc()
        if abs(float(dist) - radius_value) > tolerance:
            return False

    angle = point_angle(arc.center, point)
    start_angle = point_angle(arc.center, arc.start)
    end_angle = point_angle(arc.center, arc.end)

    inc_angle = point_angle(arc.center, arc.including) if arc.including else None
    exc_angle = point_angle(arc.center, arc.excluding) if arc.excluding else None

    return angle_in_arc(angle, start_angle, end_angle, inc_angle, exc_angle)
