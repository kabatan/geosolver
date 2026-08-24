"""
超高精度幾何計算ライブラリ（mpmath版）

mpmathを使用して任意精度（50桁以上）の計算を実現。
numpy/sympyで見つかった解をさらに精密化するために使用。
"""

from mpmath import (
    mp,
    mpf,
    sqrt as mp_sqrt,
    acos as mp_acos,
    atan2 as mp_atan2,
    pi as mp_pi,
    sin as mp_sin,
    cos as mp_cos,
)
from functools import partial
from typing import Optional, Tuple, List, Callable, Union, Dict

from geosolver.engine.standard.precision.utilities import to_mpf_sanitized
from geosolver.engine.standard.config.environment.mp_degenerate_floors import (
    get_mp_degenerate_abs_floor,
    get_mp_degenerate_rel_floor,
)
from geosolver.geometry.mp.mp_primitives import (
    mp_arc_midpoint as _mp_arc_midpoint_impl,
    mp_circle_circle_intersection as _mp_circle_circle_intersection_impl,
    mp_intersect as _mp_intersect_impl,
    mp_line_circle_intersection as _mp_line_circle_intersection_impl,
)
from geosolver.geometry.mp.mp_newton import (
    refine_to_high_precision as _refine_to_high_precision_impl,
    _solve_linear_system as _solve_linear_system_impl,
)
from geosolver.geometry.mp.mp_conversion import (
    to_mpf as _to_mpf_impl,
    mp_evalf as _mp_evalf_impl,
    convert_sympy_input as _convert_sympy_input_impl,
)
from geosolver.geometry.mp.mp_parametric_points import (
    mp_point_on_line as _mp_point_on_line_impl,
    mp_point_on_segment as _mp_point_on_segment_impl,
    mp_point_on_circle as _mp_point_on_circle_impl,
    mp_point_on_arc as _mp_point_on_arc_impl,
    mp_point_factory as _mp_point_factory_impl,
)
from geosolver.geometry.mp.mp_triangle_checks import (
    mp_triangle_type as _mp_triangle_type_impl,
    mp_middle_point_on_line as _mp_middle_point_on_line_impl,
    mp_orthic_triangle as _mp_orthic_triangle_impl,
)
from geosolver.geometry.mp.mp_polygon_checks import (
    mp_inscribed_polygon_vertices as _mp_inscribed_polygon_vertices_impl,
    mp_is_convex as _mp_is_convex_impl,
    mp_has_self_intersection as _mp_has_self_intersection_impl,
    mp_polygon_area as _mp_polygon_area_impl,
)
from geosolver.geometry.mp.mp_number_constraints import (
    mp_is_integer as _mp_is_integer_impl,
    mp_is_prime as _mp_is_prime_impl,
)
from geosolver.geometry.mp.mp_line_relations import (
    mp_line_through_two_points as _mp_line_through_two_points_impl,
    mp_perpendicular_line as _mp_perpendicular_line_impl,
    mp_line_line_intersection as _mp_line_line_intersection_impl,
    mp_angle_between_vectors as _mp_angle_between_vectors_impl,
    mp_parallelism_measure as _mp_parallelism_measure_impl,
    mp_angle_between_lines as _mp_angle_between_lines_impl,
)
from geosolver.geometry.mp.mp_predicates import (
    mp_are_collinear as _mp_are_collinear_impl,
    mp_are_parallel as _mp_are_parallel_impl,
    mp_are_perpendicular as _mp_are_perpendicular_impl,
    mp_are_concyclic as _mp_are_concyclic_impl,
    mp_slope as _mp_slope_impl,
)
from geosolver.geometry.mp.mp_circle_relations import (
    mp_tangent_line as _mp_tangent_line_impl,
    mp_radical_axis as _mp_radical_axis_impl,
    mp_power_of_point as _mp_power_of_point_impl,
)
from geosolver.geometry.mp.mp_triangle_circles import (
    mp_nine_point_center as _mp_nine_point_center_impl,
    mp_nine_point_circle as _mp_nine_point_circle_impl,
    mp_excircle as _mp_excircle_impl,
    mp_excenter as _mp_excenter_impl,
)
from geosolver.geometry.mp.mp_bisectors import (
    mp_perpendicular_bisector as _mp_perpendicular_bisector_impl,
    mp_angle_bisector as _mp_angle_bisector_impl,
)
from geosolver.geometry.mp.mp_transformations import (
    mp_closest_point as _mp_closest_point_impl,
    mp_rotate as _mp_rotate_impl,
    mp_reflect as _mp_reflect_impl,
)
from geosolver.geometry.mp.mp_triangle_centers import (
    mp_triangle_center as _mp_triangle_center_impl,
)
from geosolver.geometry.mp.mp_incircle_helpers import (
    mp_incircle_contact_point as _mp_incircle_contact_point_impl,
    mp_incircle as _mp_incircle_impl,
)
from geosolver.geometry.mp.mp_triangle_metrics import (
    mp_triangle_area as _mp_triangle_area_impl,
    mp_triangle_perimeter as _mp_triangle_perimeter_impl,
    mp_distance as _mp_distance_impl,
    mp_midpoint as _mp_midpoint_impl,
    mp_perimeter as _mp_perimeter_impl,
    mp_is_acute_triangle as _mp_is_acute_triangle_impl,
    mp_angle as _mp_angle_impl,
    mp_area as _mp_area_impl,
    mp_centroid as _mp_centroid_impl,
)
from geosolver.geometry.mp.mp_aux_entities import (
    MPSegment,
    MPRay,
    MPVector,
    mp_segment as _mp_segment_impl,
    mp_ray as _mp_ray_impl,
    mp_vector as _mp_vector_impl,
)
from geosolver.geometry.mp.mp_builder import MPGeometryBuilder
from geosolver.geometry.mp.mp_core_types import MPPoint, MPLine, MPCircle
from geosolver.geometry.mp.mp_arc_entities import (
    MPArc,
    MPExcludedPointError,
    mp_check_excluded_points as _mp_check_excluded_points_impl,
    mp_arc as _mp_arc_impl,
)
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


def _to_mpf(value):
    return _to_mpf_impl(value)


def _mp_area_tolerance(scale_len: mpf) -> mpf:
    """Return an area tolerance for degeneracy checks.

    mpmath runs at very high dps (hundreds of digits) during HP refinement.
    Using only a dps-based tolerance can allow extremely thin triangles that are
    numerically valid but geometrically meaningless for typical contest problems,
    and can create spurious "solutions".

    We therefore add a scale-aware floor: tol >= rel_floor * scale^2.
    Override with env vars if needed.
    """
    try:
        rel_floor = mp.mpf(get_mp_degenerate_rel_floor())
    except Exception:
        rel_floor = mp.mpf("1e-30")
    try:
        abs_floor = mp.mpf(get_mp_degenerate_abs_floor())
    except Exception:
        abs_floor = mp.mpf("0")

    # dps-based tolerance (very small at high dps)
    dps_tol = mpf(10) ** (-(mp.dps - 10)) if mp.dps > 20 else mpf("1e-10")
    s = max(mpf("1"), _to_mpf(scale_len))
    return max(dps_tol, abs_floor, rel_floor * (s * s))


def set_precision(dps: int = 50):
    """
    計算精度を設定

    Args:
        dps: 小数点以下の桁数（例: 50 = 50桁精度）
    """
    mp.dps = dps


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


def mp_circumcircle(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPCircle]:
    """外接円"""
    ax, ay = A.x, A.y
    bx, by = B.x, B.y
    cx, cy = C.x, C.y

    d = mpf(2) * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))

    # Degeneracy guard: near-collinear points make circumcircle ill-defined.
    # Use a scale-aware tolerance to avoid ultra-thin triangles.
    try:
        a_len = B.distance_to(C)
        b_len = C.distance_to(A)
        c_len = A.distance_to(B)
        scale = max(mpf("1"), a_len, b_len, c_len)
    except Exception:
        scale = mpf("1")
    tol = _mp_area_tolerance(scale)
    if abs(d) < tol:
        return None

    ax2_ay2 = ax**2 + ay**2
    bx2_by2 = bx**2 + by**2
    cx2_cy2 = cx**2 + cy**2

    ux = (ax2_ay2 * (by - cy) + bx2_by2 * (cy - ay) + cx2_cy2 * (ay - by)) / d
    uy = (ax2_ay2 * (cx - bx) + bx2_by2 * (ax - cx) + cx2_cy2 * (bx - ax)) / d

    center = MPPoint(ux, uy)
    radius = center.distance_to(A)

    return MPCircle(center, radius)


def mp_triangle_center(A: MPPoint, B: MPPoint, C: MPPoint, n: int) -> Optional[MPPoint]:
    return _mp_triangle_center_impl(A, B, C, n)


def mp_incircle_contact_point(
    A: MPPoint, B: MPPoint, C: MPPoint, side: Optional[Tuple[MPPoint, MPPoint]] = None
) -> Union[List[MPPoint], MPPoint]:
    return _mp_incircle_contact_point_impl(A, B, C, side=side)


def mp_arc_midpoint(
    circle: MPCircle,
    P1: MPPoint,
    P2: MPPoint,
    including: Optional[MPPoint] = None,
    excluding: Optional[MPPoint] = None,
) -> Union[List[MPPoint], MPPoint]:
    """円弧中点計算の委譲ラッパー。"""
    return _mp_arc_midpoint_impl(circle, P1, P2, including, excluding)


def mp_circle_circle_intersection(
    c1: MPCircle,
    c2: MPCircle,
    exclude: Optional[MPPoint] = None,
) -> Union[List[MPPoint], MPPoint, None]:
    """2円交点計算の委譲ラッパー。"""
    return _mp_circle_circle_intersection_impl(c1, c2, exclude)


def mp_line_circle_intersection(
    line: MPLine,
    circle: MPCircle,
    exclude: Optional[MPPoint] = None,
) -> Union[List[MPPoint], MPPoint, None]:
    """直線円交点計算の委譲ラッパー。"""
    return _mp_line_circle_intersection_impl(line, circle, exclude)


def mp_intersect(
    obj1,
    obj2,
    exclude: Optional[MPPoint] = None,
    near: Optional[MPPoint] = None,
    far: Optional[MPPoint] = None,
    **kwargs,
) -> Union[List[MPPoint], MPPoint, None]:
    """交点統合処理の委譲ラッパー。"""
    return _mp_intersect_impl(obj1, obj2, exclude=exclude, near=near, far=far, **kwargs)


def mp_incircle(A: MPPoint, B: MPPoint, C: MPPoint) -> Optional[MPCircle]:
    return _mp_incircle_impl(A, B, C)


def mp_line_through_two_points(p1: MPPoint, p2: MPPoint) -> Optional[MPLine]:
    return _mp_line_through_two_points_impl(p1, p2)


def mp_perpendicular_line(line: MPLine, point: MPPoint) -> MPLine:
    return _mp_perpendicular_line_impl(line, point)


def mp_line_line_intersection(l1: MPLine, l2: MPLine) -> Optional[MPPoint]:
    return _mp_line_line_intersection_impl(l1, l2)


def mp_angle_between_vectors(v1: MPPoint, v2: MPPoint) -> mpf:
    return _mp_angle_between_vectors_impl(v1, v2)


def mp_parallelism_measure(l1: MPLine, l2: MPLine, method: str = "cross") -> mpf:
    return _mp_parallelism_measure_impl(l1, l2, method=method)


def mp_angle_between_lines(l1: MPLine, l2: MPLine) -> mpf:
    return _mp_angle_between_lines_impl(l1, l2)


def refine_to_high_precision(
    x0: List[float],
    f_mp: Callable,
    v: List[float],
    target_precision: int = 50,
    max_iterations: int = 100,
    verbose: bool = False,
) -> Tuple[List[mpf], mpf, int]:
    """
    Compatibility wrapper for high-precision refinement.
    """
    return _refine_to_high_precision_impl(
        x0=x0,
        f_mp=f_mp,
        v=v,
        target_precision=target_precision,
        max_iterations=max_iterations,
        verbose=verbose,
    )


def _solve_linear_system(A, b, n):
    """
    Compatibility wrapper for linear system solving.
    """
    return _solve_linear_system_impl(A=A, b=b, n=n)


def _evaluate_sympy_vector_function(f_sympy: Callable, vec):
    converted_vec = _convert_sympy_input_impl(vec)
    result = f_sympy(converted_vec)
    return [_to_mpf(r) for r in result]


def create_mp_f_from_sympy(
    f_sympy: Callable, geometry_converters: Dict[str, Callable] = None
) -> Callable:
    """
    sympy版の関数からmpmath版の高精度関数を生成するラッパー

    注意: これは単純なラッパーで、sympy内部の精度限界は回避できません。
    完全な高精度計算には、関数を直接mpmath版で書き直す必要があります。

    Args:
        f_sympy: sympy版の関数
        geometry_converters: 幾何オブジェクト変換器のマップ

    Returns:
        mpmath版の関数（精度は依然としてsympyに制限される）
    """

    return partial(_evaluate_sympy_vector_function, f_sympy)


from .mp_impl_compat_wrappers import (
    mp_arc,
    mp_area,
    mp_angle,
    mp_angle_bisector,
    mp_are_collinear,
    mp_are_concyclic,
    mp_are_parallel,
    mp_are_perpendicular,
    mp_centroid,
    mp_circumcenter,
    mp_circumference,
    mp_closest_point,
    mp_evalf,
    mp_excenter,
    mp_excircle,
    mp_has_self_intersection,
    mp_incenter,
    mp_inscribed_polygon_vertices,
    mp_is_acute_triangle,
    mp_is_convex,
    mp_is_integer,
    mp_is_prime,
    mp_length,
    mp_nine_point_center,
    mp_nine_point_circle,
    mp_orthocenter,
    mp_parallel_line,
    mp_perimeter,
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
