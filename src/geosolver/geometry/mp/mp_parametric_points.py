"""
Parametric point construction helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mpmath import atan2 as mp_atan2
from mpmath import cos as mp_cos
from mpmath import pi as mp_pi
from mpmath import sin as mp_sin

from geosolver.geometry.mp.mp_conversion import to_mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPArc, MPCircle, MPLine, MPPoint


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_arc_class() -> type[MPArc]:
    from geosolver.geometry.mp.mp_impl import MPArc

    return MPArc


def _mp_circle_class() -> type[MPCircle]:
    from geosolver.geometry.mp.mp_impl import MPCircle

    return MPCircle


def _mp_line_class() -> type[MPLine]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def _check_excluded_points(point: MPPoint, exclude: Any) -> None:
    from geosolver.geometry.mp.mp_impl import _mp_check_excluded_points

    _mp_check_excluded_points(point, exclude)


def mp_point_on_line(line: MPLine, t: Any, exclude: Any = None) -> MPPoint:
    t_mpf = to_mpf(t)
    point_cls = _mp_point_class()

    base_x = -line.a * line.c
    base_y = -line.b * line.c
    dir_x = -line.b
    dir_y = line.a

    result = point_cls(base_x + t_mpf * dir_x, base_y + t_mpf * dir_y)
    _check_excluded_points(result, exclude)
    return result


def mp_point_on_segment(p1: MPPoint, p2: MPPoint, t: Any, exclude: Any = None) -> MPPoint:
    from geosolver.errors import CoincidentPointsError, GeometryDomainError

    t_mpf = to_mpf(t)
    if p1.x == p2.x and p1.y == p2.y:
        raise CoincidentPointsError("segment endpoints must be distinct")
    if not 0 <= t_mpf <= 1:
        raise GeometryDomainError("segment parameter must be in [0, 1]")
    point_cls = _mp_point_class()

    result = point_cls(p1.x + t_mpf * (p2.x - p1.x), p1.y + t_mpf * (p2.y - p1.y))
    _check_excluded_points(result, exclude)
    return result


def mp_point_on_circle(circle: MPCircle, t: Any, exclude: Any = None) -> MPPoint:
    t_mpf = to_mpf(t)
    point_cls = _mp_point_class()

    theta = 2 * mp_pi * t_mpf
    result = point_cls(
        circle.center.x + circle.radius * mp_cos(theta),
        circle.center.y + circle.radius * mp_sin(theta),
    )
    circle._remember_parametric_point(result)
    _check_excluded_points(result, exclude)
    return result


def mp_point_on_arc(
    circle: MPCircle,
    point1: MPPoint,
    point2: MPPoint,
    t: Any,
    including: MPPoint | None = None,
    excluding: MPPoint | None = None,
    exclude: Any = None,
) -> MPPoint | None:
    if including is not None and excluding is not None:
        raise ValueError("Cannot specify both including and excluding")

    t_mpf = to_mpf(t)
    if t_mpf < 0 or t_mpf > 1:
        raise ValueError("arc parameter must be in [0, 1]")

    O = circle.center
    r = circle.radius

    theta1 = mp_atan2(point1.y - O.y, point1.x - O.x)
    theta2 = mp_atan2(point2.y - O.y, point2.x - O.x)

    ccw_angle = theta2 - theta1
    while ccw_angle < 0:
        ccw_angle += 2 * mp_pi
    while ccw_angle >= 2 * mp_pi:
        ccw_angle -= 2 * mp_pi

    cw_angle = 2 * mp_pi - ccw_angle
    use_ccw = ccw_angle < mp_pi

    if including is not None or excluding is not None:
        ref_point = including if including is not None else excluding
        use_including = including is not None

        theta_ref = mp_atan2(ref_point.y - O.y, ref_point.x - O.x)
        ref_angle = theta_ref - theta1
        while ref_angle < 0:
            ref_angle += 2 * mp_pi
        while ref_angle >= 2 * mp_pi:
            ref_angle -= 2 * mp_pi

        ref_in_ccw_arc = ref_angle <= ccw_angle
        use_ccw = ref_in_ccw_arc if use_including else (not ref_in_ccw_arc)

    theta = theta1 + t_mpf * ccw_angle if use_ccw else theta1 - t_mpf * cw_angle
    point_cls = _mp_point_class()
    result = point_cls(O.x + r * mp_cos(theta), O.y + r * mp_sin(theta))
    _check_excluded_points(result, exclude)
    return result


def mp_point_factory(
    obj: Any,
    t: Any,
    including: MPPoint | None = None,
    excluding: MPPoint | None = None,
    exclude: Any = None,
) -> Any:
    t_mpf = to_mpf(t)
    arc_cls = _mp_arc_class()
    circle_cls = _mp_circle_class()
    line_cls = _mp_line_class()

    if isinstance(obj, circle_cls):
        return mp_point_on_circle(obj, t_mpf, exclude)
    if isinstance(obj, arc_cls):
        return mp_point_on_arc(
            obj.circle,
            obj.start,
            obj.end,
            t_mpf,
            including=obj.including if including is None else including,
            excluding=obj.excluding if excluding is None else excluding,
            exclude=exclude,
        )
    if isinstance(obj, line_cls):
        return mp_point_on_line(obj, t_mpf, exclude)
    raise TypeError(f"Unsupported object type for PointFactory: {type(obj)}")
