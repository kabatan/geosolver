"""
GeoSolver Geometry Module

幾何エンティティと演算を提供。

使用例:
    from geosolver.geometry import Point, Line, Circle, Distance, Angle

    A = Point(0, 0)
    B = Point(3, 4)
    Distance(A, B)  # 5
"""

from sympy import N as _N
from sympy import acos, asin, atan, atan2, cos, pi, sin, sqrt, tan

from geosolver.geometry._public_api_symbols import GEOMETRY_PUBLIC_API

# エンティティ
from geosolver.geometry.entities import Circle, Line, Point, Polygon, Ray, Segment, midpoint

# 演算関数
from geosolver.geometry.operations import (
    Angle,
    # Constructions
    AngleBisector,
    # Arc
    Arc,
    Area,
    AreConcyclic,
    Center,
    # Triangle centers
    Centroid,
    CircleThroughPoint,
    CircleThroughThreePoints,
    Circumcenter,
    Circumcircle,
    Circumference,
    ClosestPoint,
    Collinear,
    ContactPoint,
    # Numeric constraints
    Degrees,
    Distance,
    Dot,
    Excenter,
    Excircle,
    FermatPoint,
    FeuerbachPoint,
    FootOfPerpendicular,
    GergonnePoint,
    Incenter,
    Incircle,
    IncircleContactPoint,
    InscribedPolygon,
    InscribedPolygonVertices,
    # Intersections
    Intersect,
    IntersectCircles,
    IntersectLineCircle,
    IntersectLines,
    IsInteger,
    IsodynamicPoint,
    IsPrime,
    IsTangent,
    Length,
    Midpoint,
    Mittenpunkt,
    NagelPoint,
    NinePointCenter,
    NinePointCircle,
    OnCircle,
    OnLine,
    OnSegment,
    Orthocenter,
    Parallel,
    ParallelismMeasure,
    ParallelLine,
    Perimeter,
    Perpendicular,
    PerpendicularBisector,
    PerpendicularLine,
    PointOnArc,
    PointOnCircle,
    PointOnLine,
    PointOnSegment,
    Polar,
    Pole,
    PowerOfPoint,
    RadicalAxis,
    Radius,
    Reflect,
    RegularPolygon,
    Rotate,
    Slope,
    SpiekerCenter,
    SymmedianPoint,
    Tangent,
    TangentLine,
    TriangleCenter,
    Vector,
)

# レジストリとランタイム
from geosolver.geometry.registry import (
    MultiFunctionWrapper,
    geometry_symbol,
    get_function,
    list_functions,
)
from geosolver.geometry.runtime import (
    BackendType,
    GeometryRuntime,
    fast_mode,
    get_backend,
    get_precision,
    high_precision_mode,
    use_runtime,
)

# Assume関数（制約条件用）
from geosolver.geometry.safety import (
    Assume,
    AssumeAcute,
    AssumeConvex,
    AssumeEq,
    AssumeGe,
    AssumeGt,
    AssumeLe,
    AssumeLt,
    AssumeNe,
    AssumeNoSelfIntersecting,
    AssumeObtuse,
    AssumeOrder,
    AssumeRight,
    AssumptionError,
    Bound,
)


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

        if isinstance(expr, mpmath.mpf | mpmath.mpc):
            return expr
    except ImportError:
        pass

    return _N(expr, precision)


__all__ = GEOMETRY_PUBLIC_API
