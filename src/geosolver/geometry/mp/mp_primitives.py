"""Primitive intersection helpers for high-precision geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from mpmath import (
    mp,
    mpf,
    atan2 as mp_atan2,
    cos as mp_cos,
    pi as mp_pi,
    sin as mp_sin,
    sqrt as mp_sqrt,
)

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPArc, MPCircle, MPLine, MPPoint

from geosolver.geometry.mp.mp_primitives_intersections import (
    mp_circle_circle_intersection,
    mp_intersect,
    mp_line_circle_intersection,
)


ARC_MIDPOINT_TOLERANCE_DPS_RATIO = mpf("0.8")


def _normalize_angle(angle: mpf) -> mpf:
    two_pi = mpf(2) * mp_pi
    normalized = angle % two_pi
    if normalized < 0:
        normalized += two_pi
    return normalized


def _in_arc_ccw(angle: mpf, start: mpf, end: mpf) -> bool:
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def _angle_in_arc(
    angle: mpf,
    start_angle: mpf,
    end_angle: mpf,
    including_angle: Optional[mpf] = None,
    excluding_angle: Optional[mpf] = None,
) -> bool:
    a = _normalize_angle(angle)
    s = _normalize_angle(start_angle)
    e = _normalize_angle(end_angle)

    in_arc1 = _in_arc_ccw(a, s, e)
    in_arc2 = not in_arc1

    if including_angle is not None:
        use_arc1 = _in_arc_ccw(_normalize_angle(including_angle), s, e)
    elif excluding_angle is not None:
        use_arc1 = not _in_arc_ccw(_normalize_angle(excluding_angle), s, e)
    else:
        diff = e - s
        if diff < 0:
            diff += mpf(2) * mp_pi
        use_arc1 = diff <= mp_pi

    return (in_arc1 and use_arc1) or (in_arc2 and not use_arc1)


def _is_point_on_arc(point: "MPPoint", arc: "MPArc") -> bool:
    center = arc.circle.center
    theta_start = mp_atan2(arc.start.y - center.y, arc.start.x - center.x)
    theta_end = mp_atan2(arc.end.y - center.y, arc.end.x - center.x)
    theta_point = mp_atan2(point.y - center.y, point.x - center.x)

    if arc.including is not None:
        including_angle = mp_atan2(arc.including.y - center.y, arc.including.x - center.x)
        return _angle_in_arc(theta_point, theta_start, theta_end, including_angle, None)
    if arc.excluding is not None:
        excluding_angle = mp_atan2(arc.excluding.y - center.y, arc.excluding.x - center.x)
        return _angle_in_arc(theta_point, theta_start, theta_end, None, excluding_angle)
    return _angle_in_arc(theta_point, theta_start, theta_end, None, None)


def mp_arc_midpoint(
    circle: "MPCircle",
    p1: "MPPoint",
    p2: "MPPoint",
    including: Optional["MPPoint"] = None,
    excluding: Optional["MPPoint"] = None,
) -> Union[list["MPPoint"], "MPPoint"]:
    """Return midpoint candidates (or selected midpoint) on an arc."""
    if including is not None and excluding is not None:
        raise ValueError("Cannot specify both including and excluding")

    center = circle.center
    radius = circle.radius
    v1x = p1.x - center.x
    v1y = p1.y - center.y
    v2x = p2.x - center.x
    v2y = p2.y - center.y

    sum_x = v1x + v2x
    sum_y = v1y + v2y
    sum_norm = mp_sqrt(sum_x * sum_x + sum_y * sum_y)

    scale = max(abs(v1x), abs(v1y), abs(v2x), abs(v2y), abs(radius), mpf(1))
    tolerance = mpf(10) ** (-mp.dps * ARC_MIDPOINT_TOLERANCE_DPS_RATIO) * scale

    if sum_norm <= tolerance:
        theta1 = mp_atan2(v1y, v1x)
        mid1 = theta1 + mp_pi / 2
        mid2 = mid1 + mp_pi
        m1 = type(p1)(center.x + radius * mp_cos(mid1), center.y + radius * mp_sin(mid1))
        m2 = type(p1)(center.x + radius * mp_cos(mid2), center.y + radius * mp_sin(mid2))
    else:
        unit_x = sum_x / sum_norm
        unit_y = sum_y / sum_norm
        m1 = type(p1)(center.x + radius * unit_x, center.y + radius * unit_y)
        m2 = type(p1)(center.x - radius * unit_x, center.y - radius * unit_y)

    if including is None and excluding is None:
        return [m1, m2]

    start_angle = mp_atan2(p1.y - center.y, p1.x - center.x)
    end_angle = mp_atan2(p2.y - center.y, p2.x - center.x)
    including_angle = (
        mp_atan2(including.y - center.y, including.x - center.x) if including is not None else None
    )
    excluding_angle = (
        mp_atan2(excluding.y - center.y, excluding.x - center.x) if excluding is not None else None
    )
    m1_angle = mp_atan2(m1.y - center.y, m1.x - center.x)
    m2_angle = mp_atan2(m2.y - center.y, m2.x - center.x)

    m1_ok = _angle_in_arc(m1_angle, start_angle, end_angle, including_angle, excluding_angle)
    m2_ok = _angle_in_arc(m2_angle, start_angle, end_angle, including_angle, excluding_angle)
    if m1_ok and not m2_ok:
        return m1
    if m2_ok and not m1_ok:
        return m2
    if including is not None:
        d1 = (m1.x - including.x) ** 2 + (m1.y - including.y) ** 2
        d2 = (m2.x - including.x) ** 2 + (m2.y - including.y) ** 2
        return m1 if d1 <= d2 else m2
    if excluding is not None:
        d1 = (m1.x - excluding.x) ** 2 + (m1.y - excluding.y) ** 2
        d2 = (m2.x - excluding.x) ** 2 + (m2.y - excluding.y) ** 2
        return m2 if d1 <= d2 else m1
    return [m1, m2]
