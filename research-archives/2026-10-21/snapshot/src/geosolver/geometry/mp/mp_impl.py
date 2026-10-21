"""
超高精度幾何計算ライブラリ（mpmath版）

mpmathを使用して任意精度（50桁以上）の計算を実現。
numpy/sympyで見つかった解をさらに精密化するために使用。
"""

from mpmath import (
    mp,
    mpf,
)

from geosolver.engine.standard.config.environment.mp_degenerate_floors import (
    get_mp_degenerate_abs_floor,
    get_mp_degenerate_rel_floor,
)
from geosolver.geometry.mp.mp_arc_entities import MPArc
from geosolver.geometry.mp.mp_arc_entities import mp_arc as _mp_arc_impl
from geosolver.geometry.mp.mp_aux_entities import (
    MPRay,
    MPSegment,
    MPVector,
)
from geosolver.geometry.mp.mp_aux_entities import (
    mp_ray as _mp_ray_impl,
)
from geosolver.geometry.mp.mp_aux_entities import (
    mp_segment as _mp_segment_impl,
)
from geosolver.geometry.mp.mp_aux_entities import (
    mp_vector as _mp_vector_impl,
)
from geosolver.geometry.mp.mp_bisectors import (
    mp_angle_bisector as _mp_angle_bisector_impl,
)
from geosolver.geometry.mp.mp_bisectors import (
    mp_perpendicular_bisector as _mp_perpendicular_bisector_impl,
)
from geosolver.geometry.mp.mp_circle_relations import (
    mp_power_of_point as _mp_power_of_point_impl,
)
from geosolver.geometry.mp.mp_circle_relations import (
    mp_radical_axis as _mp_radical_axis_impl,
)
from geosolver.geometry.mp.mp_circle_relations import (
    mp_tangent_line as _mp_tangent_line_impl,
)
from geosolver.geometry.mp.mp_conversion import (
    mp_evalf as _mp_evalf_impl,
)
from geosolver.geometry.mp.mp_conversion import (
    to_mpf as _to_mpf_impl,
)
from geosolver.geometry.mp.mp_core_types import MPCircle, MPLine, MPPoint
from geosolver.geometry.mp.mp_impl_point_wrappers import (
    _mp_check_excluded_points,
    mp_middle_point_on_line,
    mp_orthic_triangle,
    mp_point_on_arc,
    mp_point_on_circle,
    mp_point_on_line,
    mp_point_on_segment,
    mp_triangle_type,
)
from geosolver.geometry.mp.mp_incircle_helpers import (
    mp_incircle as _mp_incircle_impl,
)
from geosolver.geometry.mp.mp_incircle_helpers import (
    mp_incircle_contact_point as _mp_incircle_contact_point_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_angle_between_lines as _mp_angle_between_lines_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_angle_between_vectors as _mp_angle_between_vectors_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_line_line_intersection as _mp_line_line_intersection_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_line_through_two_points as _mp_line_through_two_points_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_parallelism_measure as _mp_parallelism_measure_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_perpendicular_line as _mp_perpendicular_line_impl,
)
from geosolver.geometry.mp.mp_number_constraints import (
    mp_is_integer as _mp_is_integer_impl,
)
from geosolver.geometry.mp.mp_number_constraints import (
    mp_is_prime as _mp_is_prime_impl,
)
from geosolver.geometry.mp.mp_parametric_points import (
    mp_point_factory as _mp_point_factory_impl,
)
from geosolver.geometry.mp.mp_polygon_checks import (
    mp_has_self_intersection as _mp_has_self_intersection_impl,
)
from geosolver.geometry.mp.mp_polygon_checks import (
    mp_inscribed_polygon_vertices as _mp_inscribed_polygon_vertices_impl,
)
from geosolver.geometry.mp.mp_polygon_checks import (
    mp_is_convex as _mp_is_convex_impl,
)
from geosolver.geometry.mp.mp_polygon_checks import (
    mp_polygon_area as _mp_polygon_area_impl,
)
from geosolver.geometry.mp.mp_predicates import (
    mp_are_collinear as _mp_are_collinear_impl,
)
from geosolver.geometry.mp.mp_predicates import (
    mp_are_concyclic as _mp_are_concyclic_impl,
)
from geosolver.geometry.mp.mp_predicates import (
    mp_are_parallel as _mp_are_parallel_impl,
)
from geosolver.geometry.mp.mp_predicates import (
    mp_are_perpendicular as _mp_are_perpendicular_impl,
)
from geosolver.geometry.mp.mp_predicates import (
    mp_slope as _mp_slope_impl,
)
from geosolver.geometry.mp.mp_primitives import (
    mp_arc_midpoint as _mp_arc_midpoint_impl,
)
from geosolver.geometry.mp.mp_primitives import (
    mp_circle_circle_intersection as _mp_circle_circle_intersection_impl,
)
from geosolver.geometry.mp.mp_primitives import (
    mp_intersect as _mp_intersect_impl,
)
from geosolver.geometry.mp.mp_primitives import (
    mp_line_circle_intersection as _mp_line_circle_intersection_impl,
)
from geosolver.geometry.mp.mp_transformations import (
    mp_closest_point as _mp_closest_point_impl,
)
from geosolver.geometry.mp.mp_transformations import (
    mp_reflect as _mp_reflect_impl,
)
from geosolver.geometry.mp.mp_transformations import (
    mp_rotate as _mp_rotate_impl,
)
from geosolver.geometry.mp.mp_triangle_centers import (
    mp_triangle_center as _mp_triangle_center_impl,
)
from geosolver.geometry.mp.mp_triangle_circles import (
    mp_excenter as _mp_excenter_impl,
)
from geosolver.geometry.mp.mp_triangle_circles import (
    mp_excircle as _mp_excircle_impl,
)
from geosolver.geometry.mp.mp_triangle_circles import (
    mp_nine_point_center as _mp_nine_point_center_impl,
)
from geosolver.geometry.mp.mp_triangle_circles import (
    mp_nine_point_circle as _mp_nine_point_circle_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_angle as _mp_angle_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_area as _mp_area_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_centroid as _mp_centroid_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_distance as _mp_distance_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_is_acute_triangle as _mp_is_acute_triangle_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_midpoint as _mp_midpoint_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_perimeter as _mp_perimeter_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_triangle_area as _mp_triangle_area_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_triangle_perimeter as _mp_triangle_perimeter_impl,
)


def _to_mpf(value):
    return _to_mpf_impl(value)


def _mp_area_tolerance(scale_len: mpf) -> mpf:
    """Precision-relative area uncertainty, with explicit opt-in legacy floors.

    A length scale must be squared even for microscopic figures.  The former
    absolute precision floor (and max(scale,1)) rejected ordinary triangles
    solely because they were small, especially at binary64 precision.
    """
    return _mp_area_tolerance_squared(_to_mpf(scale_len) ** 2)


def _mp_area_tolerance_squared(scale_squared: mpf) -> mpf:
    try:
        rel_floor = mp.mpf(get_mp_degenerate_rel_floor(default="0"))
    except Exception:
        rel_floor = mp.mpf("0")
    try:
        abs_floor = mp.mpf(get_mp_degenerate_abs_floor())
    except Exception:
        abs_floor = mp.mpf("0")

    return max(abs_floor, max(32 * mp.eps, rel_floor) * abs(scale_squared))


def mp_triangle_area(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return _mp_triangle_area_impl(A, B, C)


def mp_triangle_perimeter(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return _mp_triangle_perimeter_impl(A, B, C)


# =============================================================================
# 高精度幾何関数群（GeoGebra互換API対応）
# =============================================================================


def mp_distance(obj1, obj2) -> mpf:
    return _mp_distance_impl(obj1, obj2)


def mp_midpoint(A: MPPoint, B: MPPoint) -> MPPoint:
    return _mp_midpoint_impl(A, B)


def mp_circumcircle(A: MPPoint, B: MPPoint, C: MPPoint) -> MPCircle | None:
    """外接円"""
    # Translate before squaring, avoiding cancellation from a remote origin.
    bx, by = B.x - A.x, B.y - A.y
    cx, cy = C.x - A.x, C.y - A.y
    d = 2 * mp.fdot((bx, by), (cy, -cx))

    # Degeneracy guard: near-collinear points make circumcircle ill-defined.
    # Use a scale-aware tolerance to avoid ultra-thin triangles.
    bx2_by2 = bx**2 + by**2
    cx2_cy2 = cx**2 + cy**2
    scale_squared = max(bx2_by2, cx2_cy2, (bx - cx) ** 2 + (by - cy) ** 2)
    tol = _mp_area_tolerance_squared(scale_squared)
    if d == 0 or abs(d) < tol:
        return None
    ux = A.x + (bx2_by2 * cy - cx2_cy2 * by) / d
    uy = A.y + (cx2_cy2 * bx - bx2_by2 * cx) / d

    center = MPPoint(ux, uy)
    radius = center.distance_to(A)

    circle = MPCircle(center, radius)
    circle._remember_defining_points((A, B, C))
    return circle


def mp_triangle_center(A: MPPoint, B: MPPoint, C: MPPoint, n: int) -> MPPoint | None:
    return _mp_triangle_center_impl(A, B, C, n)


def mp_incircle_contact_point(
    A: MPPoint, B: MPPoint, C: MPPoint, side: tuple[MPPoint, MPPoint] | None = None
) -> list[MPPoint] | MPPoint:
    return _mp_incircle_contact_point_impl(A, B, C, side=side)


def mp_arc_midpoint(
    circle: MPCircle,
    P1: MPPoint,
    P2: MPPoint,
    including: MPPoint | None = None,
    excluding: MPPoint | None = None,
) -> list[MPPoint] | MPPoint:
    """円弧中点計算の委譲ラッパー。"""
    return _mp_arc_midpoint_impl(circle, P1, P2, including, excluding)


def mp_circle_circle_intersection(
    c1: MPCircle,
    c2: MPCircle,
    exclude: MPPoint | None = None,
) -> list[MPPoint] | MPPoint | None:
    """2円交点計算の委譲ラッパー。"""
    return _mp_circle_circle_intersection_impl(c1, c2, exclude)


def mp_line_circle_intersection(
    line: MPLine,
    circle: MPCircle,
    exclude: MPPoint | None = None,
) -> list[MPPoint] | MPPoint | None:
    """直線円交点計算の委譲ラッパー。"""
    return _mp_line_circle_intersection_impl(line, circle, exclude)


def mp_intersect(
    obj1,
    obj2,
    exclude: MPPoint | None = None,
    near: MPPoint | None = None,
    far: MPPoint | None = None,
    **kwargs,
) -> list[MPPoint] | MPPoint | None:
    """交点統合処理の委譲ラッパー。"""
    return _mp_intersect_impl(obj1, obj2, exclude=exclude, near=near, far=far, **kwargs)


def mp_incircle(A: MPPoint, B: MPPoint, C: MPPoint) -> MPCircle | None:
    return _mp_incircle_impl(A, B, C)


def mp_line_through_two_points(p1: MPPoint, p2: MPPoint) -> MPLine | None:
    return _mp_line_through_two_points_impl(p1, p2)


def mp_perpendicular_line(line: MPLine, point: MPPoint) -> MPLine:
    return _mp_perpendicular_line_impl(line, point)


def mp_line_line_intersection(l1: MPLine, l2: MPLine) -> MPPoint | None:
    return _mp_line_line_intersection_impl(l1, l2)


def mp_angle_between_vectors(v1: MPPoint, v2: MPPoint) -> mpf:
    return _mp_angle_between_vectors_impl(v1, v2)


def mp_parallelism_measure(l1: MPLine, l2: MPLine, method: str = "cross") -> mpf:
    return _mp_parallelism_measure_impl(l1, l2, method=method)


def mp_angle_between_lines(l1: MPLine, l2: MPLine) -> mpf:
    return _mp_angle_between_lines_impl(l1, l2)


# Compatibility exports used by the public high-precision DSL context.  These
# wrappers are intentionally imported after the implementation helpers above;
# they resolve this module lazily and therefore do not create an import cycle.
from .mp_impl_common_wrappers import (  # noqa: E402
    mp_angle,
    mp_angle_bisector,
    mp_arc,
    mp_are_concyclic,
    mp_area,
    mp_centroid,
    mp_circumcenter,
    mp_circumference,
    mp_closest_point,
    mp_evalf,
    mp_excenter,
    mp_excircle,
    mp_incenter,
    mp_inscribed_polygon_vertices,
    mp_is_integer,
    mp_is_prime,
    mp_length,
    mp_nine_point_center,
    mp_nine_point_circle,
    mp_orthocenter,
    mp_parallel_line,
    mp_perpendicular_bisector,
    mp_point_factory,
    mp_polygon_area,
    mp_power_of_point,
    mp_radical_axis,
    mp_radius,
    mp_ray,
    mp_reflect,
    mp_rotate,
    mp_segment,
    mp_slope,
    mp_tangent_line,
    mp_vector,
)
