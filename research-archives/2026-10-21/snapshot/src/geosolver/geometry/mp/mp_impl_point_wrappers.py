"""Delegated wrappers extracted from mp_impl for point and triangle-check helpers."""

from __future__ import annotations

from geosolver.geometry.mp.mp_arc_entities import (
    mp_check_excluded_points as _mp_check_excluded_points_impl,
)
from geosolver.geometry.mp.mp_core_types import MPCircle, MPLine, MPPoint
from geosolver.geometry.mp.mp_parametric_points import (
    mp_point_on_arc as _mp_point_on_arc_impl,
)
from geosolver.geometry.mp.mp_parametric_points import (
    mp_point_on_circle as _mp_point_on_circle_impl,
)
from geosolver.geometry.mp.mp_parametric_points import (
    mp_point_on_line as _mp_point_on_line_impl,
)
from geosolver.geometry.mp.mp_parametric_points import (
    mp_point_on_segment as _mp_point_on_segment_impl,
)
from geosolver.geometry.mp.mp_triangle_checks import (
    mp_middle_point_on_line as _mp_middle_point_on_line_impl,
)
from geosolver.geometry.mp.mp_triangle_checks import (
    mp_orthic_triangle as _mp_orthic_triangle_impl,
)
from geosolver.geometry.mp.mp_triangle_checks import (
    mp_triangle_type as _mp_triangle_type_impl,
)


def mp_triangle_type(A: MPPoint, B: MPPoint, C: MPPoint) -> str | None:
    return _mp_triangle_type_impl(A=A, B=B, C=C)


def mp_middle_point_on_line(A: MPPoint, B: MPPoint, C: MPPoint) -> MPPoint | None:
    return _mp_middle_point_on_line_impl(A=A, B=B, C=C)


def mp_orthic_triangle(
    A: MPPoint, B: MPPoint, C: MPPoint
) -> tuple[MPPoint, MPPoint, MPPoint] | None:
    return _mp_orthic_triangle_impl(A=A, B=B, C=C)


def _mp_check_excluded_points(point: MPPoint, exclude, tol=None):
    return _mp_check_excluded_points_impl(point, exclude, tol=tol)


def mp_point_on_line(line: MPLine, t, exclude=None) -> MPPoint:
    return _mp_point_on_line_impl(line=line, t=t, exclude=exclude)


def mp_point_on_segment(p1: MPPoint, p2: MPPoint, t, exclude=None) -> MPPoint:
    return _mp_point_on_segment_impl(p1=p1, p2=p2, t=t, exclude=exclude)


def mp_point_on_circle(circle: MPCircle, t, exclude=None) -> MPPoint:
    return _mp_point_on_circle_impl(circle=circle, t=t, exclude=exclude)


def mp_point_on_arc(
    circle: MPCircle,
    point1: MPPoint,
    point2: MPPoint,
    t,
    including: MPPoint | None = None,
    excluding: MPPoint | None = None,
    exclude=None,
) -> MPPoint | None:
    return _mp_point_on_arc_impl(
        circle=circle,
        point1=point1,
        point2=point2,
        t=t,
        including=including,
        excluding=excluding,
        exclude=exclude,
    )
