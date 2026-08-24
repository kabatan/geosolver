"""
莠､轤ｹ險育ｮ励Δ繧ｸ繝･繝ｼ繝ｫ

蜷・未謨ｰ縺ｯSymPy(繝・ヵ繧ｩ繝ｫ繝・, NumPy(鬮倬・, mpmath(鬮倡ｲｾ蠎ｦ)縺ｮ3縺､縺ｮ螳溯｣・ｒ謖√▽縲・
"""

from typing import Optional, Union, List, Any
import numpy as np
from sympy import sqrt, simplify, solve, N as _N, Abs, Max
from geosolver.geometry.registry import geometry_symbol
from geosolver.geometry.entities.base import Point, Line, Circle
from geosolver.errors import NoIntersectionError, ParallelLinesError
from geosolver.geometry.operations.intersections_closest import ClosestPoint
from geosolver.geometry.operations.intersections_circle_ops import (
    IntersectLineCircle,
    _IntersectLineCircle_numpy,
    _IntersectLineCircle_mpmath,
    IntersectCircles,
    _IntersectCircles_numpy,
    _IntersectCircles_mpmath,
)
from geosolver.geometry.operations.intersections_selection import (
    dist_sq as _dist_sq_helper,
    get_dynamic_tolerance as _get_dynamic_tolerance_helper,
    select_intersection as _select_intersection,
    to_float_safe as _to_float_safe_helper,
)

# =============================================================================
# Intersect (Generic)
# =============================================================================


def _to_float_safe(expr: Any) -> float:
    return _to_float_safe_helper(expr)


def _dist_sq(p1: Any, p2: Any) -> Any:
    return _dist_sq_helper(p1, p2)


def _get_dynamic_tolerance() -> float:
    return _get_dynamic_tolerance_helper()


@geometry_symbol("Intersect", category="intersections")
def Intersect(
    obj1: Any,
    obj2: Any,
    n: Optional[int] = None,
    exclude: Optional[Point] = None,
    near: Optional[Point] = None,
    far: Optional[Point] = None,
) -> Any:
    """
    豎守畑莠､轤ｹ險育ｮ・

    Args:
        obj1, obj2: 莠､蟾ｮ縺輔○繧九が繝悶ず繧ｧ繧ｯ繝・
        n: n逡ｪ逶ｮ縺ｮ莠､轤ｹ繧貞叙蠕暦ｼ・-indexed・・
        exclude: 髯､螟悶☆繧狗せ
        near: 縺薙・轤ｹ縺ｫ譛繧りｿ代＞莠､轤ｹ繧帝∈謚・
        far: 縺薙・轤ｹ縺九ｉ譛繧る□縺・ｺ､轤ｹ繧帝∈謚・
    """
    # Arc蟇ｾ蠢懶ｼ亥ｾｪ迺ｰ繧､繝ｳ繝昴・繝亥屓驕ｿ縺ｮ縺溘ａ驕・ｻｶ繧､繝ｳ繝昴・繝茨ｼ・
    from geosolver.geometry.operations.arc import Arc, line_arc_intersection

    result = None

    # Arc 縺後≠繧後・蜈医↓蜃ｦ逅・
    if isinstance(obj1, Arc) or isinstance(obj2, Arc):
        arc = obj1 if isinstance(obj1, Arc) else obj2
        other = obj2 if isinstance(obj1, Arc) else obj1

        if isinstance(other, Line):
            result = line_arc_intersection(other, arc)
        elif isinstance(other, Circle):
            # Circle 縺ｨ Arc 縺ｮ莠､轤ｹ
            circle_intersects = IntersectCircles(other, arc.circle)
            # 蠑ｧ荳翫・轤ｹ縺ｮ縺ｿ繝輔ぅ繝ｫ繧ｿ
            from geosolver.geometry.operations.arc import _point_on_arc

            result = [pt for pt in circle_intersects if _point_on_arc(arc, pt)]
        elif isinstance(other, Arc):
            # Arc 縺ｨ Arc 縺ｮ莠､轤ｹ
            circle_intersects = IntersectCircles(obj1.circle, obj2.circle)
            from geosolver.geometry.operations.arc import _point_on_arc

            result = [
                pt
                for pt in circle_intersects
                if _point_on_arc(obj1, pt) and _point_on_arc(obj2, pt)
            ]
        else:
            raise NotImplementedError(f"Intersection not implemented for Arc and {type(other)}")

    elif isinstance(obj1, Line) and isinstance(obj2, Line):
        result = IntersectLines(obj1, obj2)
    elif isinstance(obj1, Line) and isinstance(obj2, Circle):
        result = IntersectLineCircle(obj1, obj2)
    elif isinstance(obj1, Circle) and isinstance(obj2, Line):
        result = IntersectLineCircle(obj2, obj1)
    elif isinstance(obj1, Circle) and isinstance(obj2, Circle):
        result = IntersectCircles(obj1, obj2)
    else:
        raise NotImplementedError(f"Intersection not implemented for {type(obj1)} and {type(obj2)}")

    # 蠕悟・逅・ｼ磯∈謚槭Ο繧ｸ繝・け・・
    return _select_intersection(result, n, exclude, near, far)


@Intersect.set_numpy
def _Intersect_numpy(obj1, obj2):
    """NumPy generic dispatch"""
    # obj1, obj2 are lists/arrays. We need to guess type by length?
    # Line: len=3, Circle: len=3... Ambiguous.
    # In fast_geometry, we typically know the types from the IR context.
    # This generic function might be hard to support in pure numpy without metadata.
    # For now, simplistic length check won't work.
    # Assume context passed types or handle specific calls directly.
    pass


# =============================================================================
# IntersectLines
# =============================================================================


@geometry_symbol("IntersectLines", category="intersections")
def IntersectLines(l1: Line, l2: Line) -> Optional[Point]:
    """2逶ｴ邱壹・莠､轤ｹ"""
    # SymPy
    # l1: a1 x + b1 y + c1 = 0
    # l2: a2 x + b2 y + c2 = 0
    # det = a1 b2 - a2 b1
    det = l1.a * l2.b - l2.a * l1.b

    if det == 0:
        # Parallel lines - no intersection
        return None

    x = (l1.b * l2.c - l2.b * l1.c) / det
    y = (l2.a * l1.c - l1.a * l2.c) / det
    return Point(x, y)


@IntersectLines.set_numpy
def _IntersectLines_numpy(l1, l2):
    """NumPy"""
    # l1, l2: [a, b, c]
    det = l1[0] * l2[1] - l2[0] * l1[1]
    if abs(det) < 1e-12:
        # Parallel lines
        return None
    x = (l1[1] * l2[2] - l2[1] * l1[2]) / det
    y = (l2[0] * l1[2] - l1[0] * l2[2]) / det
    return [x, y]


@IntersectLines.set_mpmath
def _IntersectLines_mpmath(l1, l2):
    """mpmath"""
    det = l1.a * l2.b - l2.a * l1.b
    if abs(det) < 1e-25:
        # Parallel lines - no intersection
        return None
    x = (l1.b * l2.c - l2.b * l1.c) / det
    y = (l2.a * l1.c - l1.a * l2.c) / det
    return Point(x, y)


# =============================================================================
# IntersectLineCircle
# =============================================================================


