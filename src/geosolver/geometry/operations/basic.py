"""
基本的な幾何演算関数

registryに登録された関数を提供。
"""

from sympy import sqrt, N as _N, pi, Abs, Min
from typing import Any, Optional, List, Union

from geosolver.geometry.registry import geometry_symbol
from geosolver.geometry.entities import Point, Line, Circle, midpoint as _midpoint
from geosolver.geometry.operations.arc import Arc, arc_midpoint
from geosolver.geometry.operations.basic_relations import (
    are_concyclic_impl,
    circumference_impl,
    length_impl,
    parallel_impl,
    parallelism_measure_impl,
    perimeter_impl,
    perpendicular_impl,
    slope_impl,
)

__all__ = [
    "Distance",
    "Midpoint",
    "Angle",
    "Radius",
    "Area",
    "OnSegment",
    "OnLine",
    "OnCircle",
    "IsTangent",
    "Perpendicular",
    "Parallel",
    "Slope",
    "Length",
    "Perimeter",
    "Circumference",
    "AreConcyclic",
    "ParallelismMeasure",
]


def _as_tangent_circle(obj: object) -> Optional[Circle]:
    if isinstance(obj, Circle):
        return obj
    if isinstance(obj, Arc):
        return obj.circle
    return None


@geometry_symbol("Distance", category="basic")
def Distance(obj1, obj2=None):
    """
    2つのオブジェクト間の距離を計算

    GeoGebra互換:
        Distance(<点>, <点>)
        Distance(<点>, <直線>)

    Args:
        obj1: 点、直線、または円
        obj2: 点、直線、または円（省略時は原点からの距離）

    Returns:
        距離（sympy式）

    Examples:
        >>> Distance(Point(0, 0), Point(3, 4))
        5
        >>> Distance(Point(0, 0), Line(1, 0, -5))
        5
    """
    if obj2 is None:
        # 原点からの距離
        if isinstance(obj1, Point):
            return obj1.norm()
        raise TypeError(f"Distance requires two arguments for {type(obj1)}")

    if isinstance(obj1, Point) and isinstance(obj2, Point):
        return obj1.distance_to(obj2)

    if isinstance(obj1, Point) and isinstance(obj2, Line):
        return obj2.distance_to_point(obj1)

    if isinstance(obj1, Line) and isinstance(obj2, Point):
        return obj1.distance_to_point(obj2)

    if isinstance(obj1, Point) and isinstance(obj2, Circle):
        return Abs(obj1.distance_to(obj2.center) - obj2.radius)

    if isinstance(obj1, Circle) and isinstance(obj2, Point):
        return Abs(obj2.distance_to(obj1.center) - obj1.radius)

    raise TypeError(f"Distance not supported for {type(obj1)} and {type(obj2)}")


@geometry_symbol("Midpoint", category="basic")
def Midpoint(obj1, obj2=None):
    """
    中点を計算

    GeoGebra互換:
        Midpoint(<点>, <点>)   # 2点の中点
        Midpoint(<円>)         # 円の中心
        Midpoint(<弧>)         # 弧の中点

    Args:
        obj1: 点、円、または弧
        obj2: 点（オプション）

    Returns:
        中点（Point）

    Examples:
        >>> Midpoint(Point(0, 0), Point(4, 6))
        Point(2, 3)
    """
    if obj2 is None:
        if isinstance(obj1, Circle):
            return obj1.center
        if isinstance(obj1, Arc):
            return arc_midpoint(obj1)
        raise TypeError(f"Midpoint requires two points, a single circle, or a single arc")

    if isinstance(obj1, Point) and isinstance(obj2, Point):
        return _midpoint(obj1, obj2)

    raise TypeError(f"Midpoint not supported for {type(obj1)} and {type(obj2)}")


@geometry_symbol("Angle", category="basic")
def Angle(obj1, obj2=None, obj3=None):
    """
    角度を計算

    GeoGebra互換:
        Angle(<点>, <頂点>, <点>)  # 3点で定義される角
        Angle(<直線>, <直線>)      # 2直線のなす角

    Args:
        obj1, obj2, obj3: 点または直線

    Returns:
        角度（ラジアン、sympy式）

    Examples:
        >>> Angle(Point(1, 0), Point(0, 0), Point(0, 1))
        pi/2
    """
    from sympy import acos, atan2

    if obj3 is not None:
        # 3点: A, B, C → 頂点Bでの角度
        A, B, C = obj1, obj2, obj3
        if not all(isinstance(p, Point) for p in [A, B, C]):
            raise TypeError("Angle(A, B, C) requires three Points")

        BA = A - B
        BC = C - B
        # An angle is undefined when either ray has zero length.  Returning
        # ``atan2(0, 0) == 0`` silently turns a coincident-point construction
        # into a valid zero-angle constraint and can make the solver certify a
        # degenerate diagram.  Keep symbolic expressions untouched, but reject
        # cases that are provably coincident at construction time.
        if BA.dot(BA) == 0 or BC.dot(BC) == 0:
            raise ValueError("Angle undefined for coincident points")
        dot = BA.dot(BC)
        cross = BA.cross(BC)

        # atan2で符号付き角度を計算
        return atan2(Abs(cross), dot)

    if obj2 is not None:
        # 2直線のなす角
        if isinstance(obj1, Line) and isinstance(obj2, Line):
            # 法線ベクトルの内積から角度を計算
            dot = obj1.a * obj2.a + obj1.b * obj2.b
            return acos(Abs(dot))

    raise TypeError(f"Angle not supported for given arguments")


@geometry_symbol("Radius", category="basic")
def Radius(circle):
    """
    円の半径を返す

    Args:
        circle: Circle オブジェクト

    Returns:
        半径（sympy式）
    """
    if isinstance(circle, Circle):
        return circle.radius
    raise TypeError(f"Radius requires a Circle, got {type(circle)}")


@geometry_symbol("Area", category="basic")
def Area(*args):
    """
    面積を計算

    GeoGebra互換:
        Area(<円>)             # 円の面積
        Area(<点>, <点>, <点>) # 三角形の面積

    Args:
        obj1, obj2, obj3: 円または3つの点

    Returns:
        面積（sympy式）
    """
    if len(args) == 1:
        obj1 = args[0]
        if isinstance(obj1, Circle):
            return obj1.area()

    if len(args) >= 3:
        points = list(args)
        if not all(isinstance(p, Point) for p in points):
            raise TypeError("Area requires Point arguments")

        # Polygon area via shoelace (triangles included)
        s = 0
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            s += p1.x * p2.y - p1.y * p2.x
        return Abs(s) / 2

    raise TypeError("Area not supported for given arguments")


@geometry_symbol("Vector", category="basic")
def Vector(p1, p2):
    """Vector from p1 to p2."""
    if isinstance(p1, Point) and isinstance(p2, Point):
        return p2 - p1
    raise TypeError("Vector requires two Points")


@geometry_symbol("Dot", category="basic")
def Dot(obj1, obj2):
    """Dot product between vectors/points or line normals."""
    try:
        return obj1.dot(obj2)
    except Exception:
        pass
    if isinstance(obj1, Line) and isinstance(obj2, Line):
        return obj1.a * obj2.a + obj1.b * obj2.b
    try:
        return obj1.x * obj2.x + obj1.y * obj2.y
    except Exception as exc:
        raise TypeError("Dot requires vector-like inputs") from exc


@geometry_symbol("OnLine", category="basic")
def OnLine(point, obj1, obj2=None, ordered=False):
    """
    点が直線上にあるか（制約用関数: 残差=0を期待）
    OnLine(P, Line) -> Distance(P, Line) (or signed distance)
    OnLine(P, A, B) -> Area(A, P, B) (collinearity)
    OnLine(P, A, B, ordered=True) -> collinearity + order check
    
    Args:
        point: Point
        obj1: Line or Point
        obj2: Point (if obj1 is Point)
        ordered: bool - True の場合、obj1-point-obj2の順序時のみ0を返す
    
    Returns:
        残差 (float/Expr)
    """
    if not isinstance(point, Point):
        raise TypeError("First argument must be a Point")
        
    if isinstance(obj1, Line) and obj2 is None:
        return obj1.distance_to_point(point)
        
    if isinstance(obj1, Point) and isinstance(obj2, Point):
        # 3点 A, B, C が同一直線上 <=> Area(A, B, C) == 0
        # 外積を使用
        v1 = obj1 - point
        v2 = obj2 - point
        collinear_residual = v1.cross(v2)
        
        if ordered:
            # obj1-point-obj2 の順序チェック 
            # -> point-obj1-obj2 (point -> obj1 ->  obj2) の順序チェックに変更
            # Distance(point, obj1) + Distance(obj1, obj2) - Distance(point, obj2) = 0
            order_residual = Distance(point, obj1) + Distance(obj1, obj2) - Distance(point, obj2)
            # 両方の条件を満たす必要がある（二乗和で結合）
            return collinear_residual**2 + order_residual**2
        
        return collinear_residual
        
    raise TypeError("Invalid arguments for OnLine")


@OnLine.set_mpmath
def _OnLine_mpmath(point: Any, obj1: Any, obj2: Any = None, ordered: bool = False) -> Any:
    from geosolver.geometry.mp.mp_core_types import MPLine, MPPoint

    if not isinstance(point, MPPoint):
        raise TypeError("First argument must be a Point")

    if isinstance(obj1, MPLine) and obj2 is None:
        return obj1.distance_to_point(point)

    if isinstance(obj1, MPPoint) and isinstance(obj2, MPPoint):
        v1 = obj1 - point
        v2 = obj2 - point
        collinear_residual = v1.cross(v2)

        if ordered:
            order_residual = (
                point.distance_to(obj1)
                + obj1.distance_to(obj2)
                - point.distance_to(obj2)
            )
            return collinear_residual**2 + order_residual**2

        return collinear_residual

    raise TypeError("Invalid arguments for OnLine")


@geometry_symbol("OnCircle", category="basic")
def OnCircle(point: Any, circle: Any) -> Any:
    if not isinstance(point, Point):
        raise TypeError("First argument must be a Point")
    if not isinstance(circle, Circle):
        raise TypeError("Second argument must be a Circle")
    return Distance(point, circle.center) - circle.radius


@OnCircle.set_mpmath
def _OnCircle_mpmath(point: Any, circle: Any) -> Any:
    from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint

    if not isinstance(point, MPPoint):
        raise TypeError("First argument must be a Point")
    if not isinstance(circle, MPCircle):
        raise TypeError("Second argument must be a Circle")
    return point.distance_to(circle.center) - circle.radius


@geometry_symbol("OnSegment", category="basic")
def OnSegment(point, start, end):
    """
    点が線分上にあるか
    
    OnSegment(P, A, B) <=> PがAB上にあり、かつ A-P-B の順序
    Returns: (resid_line, resid_order) ? 
    However, GeoSolver solvers expect a single expression or sum of squares.
    Usually we decompose this into:
      1. OnLine(P, A, B)
      2. Distance(A, P) + Distance(P, B) - Distance(A, B) = 0
    Here we return the sum of absolute residuals or simply the distance sum condition 
    (which implies collinearity if strictly equal, but numerically we need both).
    
    Ideally, this should be handled by validtor expanding it into multiple constraints,
    but for simple interpretation, we return a value that is 0 iff on segment.
    """
    if not all(isinstance(p, Point) for p in [point, start, end]):
        raise TypeError("OnSegment requires three Points")
        
    # dist condition implies collinearity in Euclidean geometry (triangle inequality equality)
    return Distance(start, point) + Distance(point, end) - Distance(start, end)


@geometry_symbol("IsTangent", category="basic")
def IsTangent(obj1, obj2):
    """
    2つの幾何オブジェクトが接しているかを測る残差 (0 が接する状態)
    
    対応組み合わせ:
      - Line と Circle/Arc
      - Circle/Arc と Circle/Arc（外接・内接のいずれも可）
    
    Returns:
        残差 (float/Expr) - 0 で接し、それ以外は距離差
    """
    if isinstance(obj1, Line):
        circle = _as_tangent_circle(obj2)
        if circle:
            return Abs(Distance(circle.center, obj1) - circle.radius)

    if isinstance(obj2, Line):
        circle = _as_tangent_circle(obj1)
        if circle:
            return Abs(Distance(circle.center, obj2) - circle.radius)

    c1, c2 = _as_tangent_circle(obj1), _as_tangent_circle(obj2)
    if c1 and c2:
        d = Distance(c1.center, c2.center)
        r1, r2 = c1.radius, c2.radius
        external = Abs(d - (r1 + r2))
        internal = Abs(d - Abs(r1 - r2))
        
        # Use a smooth minimum to avoid non-differentiable points
        # Smooth minimum: min(a, b) ≈ (a + b - sqrt((a-b)^2)) / 2
        # However, this still has issues at a=b.
        # Better: use a penalty that naturally minimizes the smallest distance
        # Actually, for optimizer, just use min() is OK if we handle it carefully.
        # But for better gradient, we can use: (external^p + internal^p)^(1/p) for large p
        # Or simply: use the smaller one directly (sympy Min is OK)
        # 
        # Actually, the issue is that when both are far from 0, optimizer doesn't know which to pursue.
        # Solution: Use a weighted combination that emphasizes the smaller value
        # residual = min(external, internal) works, but let's try: sqrt(external^2 + internal^2) / sqrt(2)
        # No, that would penalize both equally.
        #
        # Best approach: return the minimum directly, and trust the optimizer to find the right basin.
        # If needed, we can add a secondary optimization pass that tries both scenarios.
        # For now, keep Min() but add a soft penalty to guide the optimizer:
        # residual = Min(external, internal) + 0.01 * (external + internal)
        # This way, even if one is at zero, reducing the other still helps.
        
        # Simple robust version: just use Min (sympy handles it)
        return Min(external, internal)

    raise TypeError("IsTangent supports (Line, Circle/Arc) or (Circle/Arc, Circle/Arc)")


@IsTangent.set_mpmath
def _IsTangent_mpmath(obj1, obj2):
    """mpmath backend"""
    from geosolver.geometry.mp.mp_api import MP_IsTangent

    return MP_IsTangent(obj1, obj2)

@geometry_symbol("Perpendicular", category="basic")
def Perpendicular(obj1, obj2):
    """
    2つのオブジェクトが垂直か
    Line, Line -> dot product of direction vectors
    """
    return perpendicular_impl(obj1, obj2)


@geometry_symbol("Parallel", category="basic")
def Parallel(obj1, obj2):
    """
    2つのオブジェクトが平行か
    Line, Line -> cross product of direction vectors (or normals)
    """
    return parallel_impl(obj1, obj2)


@geometry_symbol("Slope", category="basic")
def Slope(obj1, obj2=None):
    """
    直線の傾きを計算
    """
    return slope_impl(obj1, obj2)


@geometry_symbol("Length", category="basic")
def Length(obj):
    """
    線分などの長さを計算
    """
    return length_impl(obj)


@geometry_symbol("Perimeter", category="basic")
def Perimeter(*args):
    """
    多角形の周長を計算
    """
    return perimeter_impl(args)


@geometry_symbol("Circumference", category="basic")
def Circumference(circle):
    """
    円の周長を計算
    """
    return circumference_impl(circle)


@geometry_symbol("AreConcyclic", category="basic")
def AreConcyclic(p1, p2, p3, p4):
    """
    4点が同一円周上にあるか（制約用）
    """
    return are_concyclic_impl(p1, p2, p3, p4)


@geometry_symbol("ParallelismMeasure", category="basic")
def ParallelismMeasure(l1, l2, method="cross"):
    """
    2直線の平行度
    """
    return parallelism_measure_impl(l1, l2, method=method)
