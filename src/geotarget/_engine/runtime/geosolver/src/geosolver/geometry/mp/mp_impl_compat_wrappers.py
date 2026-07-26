"""Compatibility wrappers extracted from mp_impl."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from mpmath import mpf

from .mp_arc_entities import MPArc
from .mp_aux_entities import MPRay, MPSegment, MPVector
from .mp_core_types import MPCircle, MPLine, MPPoint


@lru_cache(maxsize=1)
def _impl_module():
    from geosolver.geometry.mp import mp_impl as _impl

    return _impl


def mp_segment(p1: MPPoint, p2: MPPoint) -> MPSegment:
    return _impl_module()._mp_segment_impl(p1, p2)


def mp_inscribed_polygon_vertices(circle: MPCircle, *t_params) -> list:
    return _impl_module()._mp_inscribed_polygon_vertices_impl(circle, *t_params)


def mp_parallel_line(point: MPPoint, line: MPLine) -> MPLine:
    new_c = -(line.a * point.x + line.b * point.y)
    return MPLine(line.a, line.b, new_c)


def mp_perimeter(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return _impl_module()._mp_perimeter_impl(A, B, C)


def mp_is_acute_triangle(A: MPPoint, B: MPPoint, C: MPPoint) -> bool:
    return _impl_module()._mp_is_acute_triangle_impl(A, B, C)


def mp_evalf(value, precision=15):
    return _impl_module()._mp_evalf_impl(value=value, precision=precision)


def mp_arc(
    circle: MPCircle,
    start: MPPoint,
    end: MPPoint,
    including: Optional[MPPoint] = None,
    excluding: Optional[MPPoint] = None,
) -> MPArc:
    return _impl_module()._mp_arc_impl(circle, start, end, including=including, excluding=excluding)


def mp_point_factory(obj, t, including=None, excluding=None, exclude=None):
    return _impl_module()._mp_point_factory_impl(
        obj=obj,
        t=t,
        including=including,
        excluding=excluding,
        exclude=exclude,
    )


def mp_ray(start: MPPoint, through: MPPoint) -> MPRay:
    return _impl_module()._mp_ray_impl(start, through)


def mp_vector(A: MPPoint, B: MPPoint) -> MPVector:
    return _impl_module()._mp_vector_impl(A, B)


def mp_angle(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return _impl_module()._mp_angle_impl(A, B, C)


def mp_area(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return _impl_module()._mp_area_impl(A, B, C)


def mp_centroid(A: MPPoint, B: MPPoint, C: MPPoint) -> MPPoint:
    return _impl_module()._mp_centroid_impl(A, B, C)


def mp_circumcenter(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPPoint]:
    circ = _impl_module().mp_circumcircle(A, B, C)
    return circ.center if circ else None


def mp_incenter(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPPoint]:
    return _impl_module().mp_triangle_center(A, B, C, 1)


def mp_orthocenter(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPPoint]:
    return _impl_module().mp_triangle_center(A, B, C, 4)


def mp_closest_point(point: MPPoint, line: MPLine) -> MPPoint:
    return _impl_module()._mp_closest_point_impl(point, line)


def mp_rotate(point: MPPoint, center: MPPoint, angle) -> MPPoint:
    return _impl_module()._mp_rotate_impl(point, center, angle)


def mp_reflect(point: MPPoint, mirror) -> MPPoint:
    return _impl_module()._mp_reflect_impl(point, mirror)


def mp_are_collinear(A: MPPoint, B: MPPoint, C: MPPoint) -> bool:
    return _impl_module()._mp_are_collinear_impl(A, B, C)


def mp_are_parallel(l1: MPLine, l2: MPLine) -> bool:
    return _impl_module()._mp_are_parallel_impl(l1, l2)


def mp_are_perpendicular(l1: MPLine, l2: MPLine) -> bool:
    return _impl_module()._mp_are_perpendicular_impl(l1, l2)


def mp_are_concyclic(A: MPPoint, B: MPPoint, C: MPPoint, D: MPPoint) -> bool:
    return _impl_module()._mp_are_concyclic_impl(A, B, C, D)


def mp_slope(line: MPLine) -> Optional[mpf]:
    return _impl_module()._mp_slope_impl(line)


def mp_length(segment: MPSegment) -> mpf:
    return segment.length()


def mp_radius(circle: MPCircle) -> mpf:
    return circle.radius


def mp_circumference(circle: MPCircle) -> mpf:
    return 2 * _impl_module().mp_pi * circle.radius


def mp_nine_point_center(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPPoint]:
    return _impl_module()._mp_nine_point_center_impl(A, B, C)


def mp_nine_point_circle(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPCircle]:
    return _impl_module()._mp_nine_point_circle_impl(A, B, C)


def mp_excircle(A: MPPoint, B: MPPoint, C: MPPoint, vertex: str = "A") -> Optional[MPCircle]:
    return _impl_module()._mp_excircle_impl(A, B, C, vertex=vertex)


def mp_excenter(A: MPPoint, B: MPPoint, C: MPPoint, vertex: str = "A") -> Optional[MPPoint]:
    return _impl_module()._mp_excenter_impl(A, B, C, vertex=vertex)


def mp_perpendicular_bisector(A: MPPoint, B: MPPoint) -> MPLine:
    return _impl_module()._mp_perpendicular_bisector_impl(A, B)


def mp_angle_bisector(A: MPPoint, B: MPPoint, C: MPPoint) -> MPLine:
    return _impl_module()._mp_angle_bisector_impl(A, B, C)


def mp_tangent_line(circle: MPCircle, point: MPPoint) -> Optional[List[MPLine]]:
    return _impl_module()._mp_tangent_line_impl(circle, point)


def mp_radical_axis(c1: MPCircle, c2: MPCircle) -> Optional[MPLine]:
    return _impl_module()._mp_radical_axis_impl(c1, c2)


def mp_power_of_point(point: MPPoint, circle: MPCircle) -> mpf:
    return _impl_module()._mp_power_of_point_impl(point, circle)


def mp_is_convex(*points) -> Optional[bool]:
    return _impl_module()._mp_is_convex_impl(*points)


def mp_has_self_intersection(*points) -> Optional[bool]:
    return _impl_module()._mp_has_self_intersection_impl(*points)


def mp_polygon_area(*points):
    return _impl_module()._mp_polygon_area_impl(*points)


def mp_is_integer(x) -> mpf:
    return _impl_module()._mp_is_integer_impl(x)


def mp_is_prime(x) -> mpf:
    return _impl_module()._mp_is_prime_impl(x)
