"""
GeoSolver Geometry Module

幾何エンティティと演算を提供。

使用例:
    from geosolver.geometry import Point, Line, Circle, Distance, Angle
    
    A = Point(0, 0)
    B = Point(3, 4)
    Distance(A, B)  # 5
"""

from sympy import N as _N, pi, sqrt, cos, sin, tan, acos, asin, atan, atan2

# エンティティ
from geosolver.geometry.entities import Point, Line, Circle, midpoint, Segment, Ray, Polygon

# 演算関数
from geosolver.geometry.operations import (
    Distance,
    Midpoint,
    Center,
    Collinear,
    ContactPoint,
    Angle,
    Radius,
    Area,
    Vector,
    Dot,
    OnSegment,
    OnLine,
    IsTangent,
    Perpendicular,
    Parallel,
    Slope,
    Length,
    Perimeter,
    Circumference,
    OnCircle,
    ParallelismMeasure,
    # Numeric constraints
    IsInteger,
    IsPrime,
    # Constructions
    AngleBisector,
    PerpendicularLine,
    ParallelLine,
    PerpendicularBisector,
    FootOfPerpendicular,
    PointOnLine,
    PointOnSegment,
    PointOnCircle,
    TangentLine,
    CircleThroughPoint,
    CircleThroughThreePoints,
    InscribedPolygonVertices,
    # Intersections
    Intersect,
    IntersectLines,
    IntersectLineCircle,
    IntersectCircles,
    ClosestPoint,
    # Triangle centers
    Centroid,
    Incenter,
    Circumcenter,
    Orthocenter,
    Incircle,
    Circumcircle,
    Excenter,
    Excircle,
    NinePointCircle,
    TriangleCenter,
    NinePointCenter,
    SymmedianPoint,
    GergonnePoint,
    NagelPoint,
    Mittenpunkt,
    SpiekerCenter,
    FeuerbachPoint,
    FermatPoint,
    IsodynamicPoint,
    IncircleContactPoint,
    # Arc
    Arc,
    PointOnArc,
    Rotate,
    Reflect,
    PowerOfPoint,
    Polar,
    Pole,
    RadicalAxis,
    RegularPolygon,
    InscribedPolygon,
)

# レジストリとランタイム
from geosolver.geometry.registry import (
    geometry_symbol,
    get_function,
    list_functions,
    MultiFunctionWrapper,
)
from geosolver.geometry.runtime import (
    BackendType,
    GeometryRuntime,
    use_runtime,
    fast_mode,
    high_precision_mode,
    get_precision,
    get_backend,
)

# Assume関数（制約条件用）
from geosolver.geometry.safety import (
    Assume,
    Bound,
    AssumeEq,
    AssumeNe,
    AssumeLt,
    AssumeLe,
    AssumeGt,
    AssumeGe,
    AssumeAcute,
    AssumeRight,
    AssumeObtuse,
    AssumeConvex,
    AssumeNoSelfIntersecting,
    AssumeOrder,
    AssumptionError,
)
from geosolver.geometry._public_api_symbols import GEOMETRY_PUBLIC_API


def evalf(expr, precision=15):
    """
    数値評価（sympy.Nの別名）

    Args:
        expr: 評価する式
        precision: 精度（桁数）

    Returns:
        数値評価結果
    """
    # mpmath の数値型はそのまま返す
    try:
        import mpmath

        if isinstance(expr, (mpmath.mpf, mpmath.mpc)):
            return expr
    except ImportError:
        pass

    return _N(expr, precision)


__all__ = GEOMETRY_PUBLIC_API
