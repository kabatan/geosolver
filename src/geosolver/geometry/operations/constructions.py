"""
作図関数モジュール

各関数はSymPy(デフォルト), NumPy(高速), mpmath(高精度)の3つの実装を持つ。
"""

from typing import Any

from sympy import simplify, sqrt

from geosolver.geometry.entities.base import Line, Point
from geosolver.geometry.operations.constructions_extra import (
    CircleThroughPoint,
    CircleThroughThreePoints,
    InscribedPolygon,
    InscribedPolygonVertices,
    PointOnCircle,
    PointOnLine,
    PointOnSegment,
    RegularPolygon,
    Tangent,
    _CircleThroughPoint_mpmath,
    _CircleThroughPoint_numpy,
    _CircleThroughThreePoints_mpmath,
    _CircleThroughThreePoints_numpy,
    _InscribedPolygon_mpmath,
    _InscribedPolygon_numpy,
    _PointOnCircle_mpmath,
    _PointOnCircle_numpy,
    _PointOnLine_mpmath,
    _PointOnLine_numpy,
    _PointOnSegment_mpmath,
    _PointOnSegment_numpy,
    _RegularPolygon_mpmath,
    _RegularPolygon_numpy,
    _Tangent_mpmath,
    _Tangent_numpy,
)
from geosolver.geometry.operations.constructions_linear_backends import (
    foot_of_perpendicular_mpmath_impl,
    foot_of_perpendicular_numpy_impl,
    parallel_line_mpmath_impl,
    parallel_line_numpy_impl,
    perpendicular_line_mpmath_impl,
    perpendicular_line_numpy_impl,
)
from geosolver.geometry.registry import geometry_symbol

# =============================================================================
# PerpendicularLine
# =============================================================================


@geometry_symbol("PerpendicularLine", category="constructions")
def PerpendicularLine(arg1: Any, arg2: Any) -> Line:
    """点を通り、直線に垂直な直線。

    IR/GeoGebra 互換のため、引数順 (line, point) と (point, line) の両方を受け付ける。
    """
    # SymPy (Exact)
    if isinstance(arg1, Line) and isinstance(arg2, Point):
        line, point = arg1, arg2
    elif isinstance(arg1, Point) and isinstance(arg2, Line):
        point, line = arg1, arg2
    else:
        # Let it crash loudly: this is a misuse.
        line, point = arg1, arg2

    a = line.b
    b = -line.a
    c = -(a * point.x + b * point.y)
    return Line(a, b, c)


@PerpendicularLine.set_numpy
def _PerpendicularLine_numpy(arg1, arg2):
    return perpendicular_line_numpy_impl(arg1, arg2)


@PerpendicularLine.set_mpmath
def _PerpendicularLine_mpmath(arg1, arg2):
    return perpendicular_line_mpmath_impl(arg1, arg2)


# =============================================================================
# ParallelLine
# =============================================================================


@geometry_symbol("ParallelLine", category="constructions")
def ParallelLine(arg1: Any, arg2: Any) -> Line:
    """点を通り、直線に平行な直線。

    IR/GeoGebra 互換のため、引数順 (line, point) と (point, line) の両方を受け付ける。
    """
    # SymPy
    if isinstance(arg1, Line) and isinstance(arg2, Point):
        line, point = arg1, arg2
    elif isinstance(arg1, Point) and isinstance(arg2, Line):
        point, line = arg1, arg2
    else:
        line, point = arg1, arg2

    a = line.a
    b = line.b
    c = -(a * point.x + b * point.y)
    return Line(a, b, c)


@ParallelLine.set_numpy
def _ParallelLine_numpy(arg1, arg2):
    return parallel_line_numpy_impl(arg1, arg2)


@ParallelLine.set_mpmath
def _ParallelLine_mpmath(arg1, arg2):
    return parallel_line_mpmath_impl(arg1, arg2)


# =============================================================================
# PerpendicularBisector
# =============================================================================


@geometry_symbol("PerpendicularBisector", category="constructions")
def PerpendicularBisector(p1: Point, p2: Point) -> Line | None:
    """2点の垂直二等分線"""
    # SymPy
    try:
        # 中点
        mid_x = (p1.x + p2.x) / 2
        mid_y = (p1.y + p2.y) / 2

        # 2点を通る直線の係数 a, b
        # a = y1 - y2, b = x2 - x1
        l_a = p1.y - p2.y
        l_b = p2.x - p1.x

        # 垂直二等分線はこれに垂直 -> 係数を入れ替え
        # perp_a = l_b, perp_b = -l_a
        a = l_b
        b = -l_a
        c = -(a * mid_x + b * mid_y)
        return Line(a, b, c)
    except Exception:
        return None


@PerpendicularBisector.set_numpy
def _PerpendicularBisector_numpy(p1, p2):
    """NumPy"""
    # p1, p2: [x, y]
    # mid: [(x1+x2)/2, (y1+y2)/2]
    mid_x = 0.5 * (p1[0] + p2[0])
    mid_y = 0.5 * (p1[1] + p2[1])

    # line through p1, p2: a = y1-y2, b = x2-x1
    l_a = p1[1] - p2[1]
    l_b = p2[0] - p1[0]

    # perp bisector: a' = l_b, b' = -l_a
    a = l_b
    b = -l_a
    c = -(a * mid_x + b * mid_y)

    # ノルムチェックが必要ならここで行う (退化判定)
    sq_norm = a * a + b * b
    if sq_norm < 1e-20:  # 非常に近い点
        return None

    return [a, b, c]


@PerpendicularBisector.set_mpmath
def _PerpendicularBisector_mpmath(p1, p2):
    """mpmath"""
    try:
        mid_x = (p1.x + p2.x) / 2
        mid_y = (p1.y + p2.y) / 2
        l_a = p1.y - p2.y
        l_b = p2.x - p1.x
        a = l_b
        b = -l_a
        c = -(a * mid_x + b * mid_y)
        return Line(a, b, c)
    except Exception:
        return None


# =============================================================================
# AngleBisector
# =============================================================================


@geometry_symbol("AngleBisector", category="constructions")
def AngleBisector(A: Point, B: Point, C: Point) -> Line | None:
    """角ABCの二等分線（B頂点）"""
    # SymPy
    try:
        BA = A - B
        BC = C - B
        norm_BA = simplify(sqrt(BA.x**2 + BA.y**2))
        norm_BC = simplify(sqrt(BC.x**2 + BC.y**2))

        # ゼロ除算チェック
        if norm_BA == 0 or norm_BC == 0:
            return None

        u = Point(BA.x / norm_BA, BA.y / norm_BA)
        v = Point(BC.x / norm_BC, BC.y / norm_BC)

        w = u + v  # 二等分ベクトル

        # wが0ベクトルの場合（180度）、垂直なベクトルを取る
        if w.x == 0 and w.y == 0:
            w = Point(-u.y, u.x)

        # P = B + w を通る直線
        P = B + w

        # Line through B and P
        a = B.y - P.y
        b = P.x - B.x
        c = -a * B.x - b * B.y
        return Line(a, b, c)

    except Exception:
        return None


@AngleBisector.set_numpy
def _AngleBisector_numpy(A, B, C):
    """NumPy"""
    import numpy as np
    # A, B, C: arrays

    BA = A - B
    BC = C - B

    norm_BA = np.linalg.norm(BA)
    norm_BC = np.linalg.norm(BC)

    if norm_BA < 1e-10 or norm_BC < 1e-10:
        return None

    u = BA / norm_BA
    v = BC / norm_BC
    w = u + v

    norm_w = np.linalg.norm(w)
    if norm_w < 1e-10:
        w = np.array([-u[1], u[0]])  # Rotate 90 deg

    # Line through B with direction w
    # normal vector (-w_y, w_x)
    n_x = -w[1]
    n_y = w[0]

    c = -(n_x * B[0] + n_y * B[1])
    return [n_x, n_y, c]


@AngleBisector.set_mpmath
def _AngleBisector_mpmath(A, B, C):
    """mpmath"""
    from mpmath import sqrt

    try:
        BA = A - B
        BC = C - B
        # Pointクラスがmpmath対応している前提
        norm_BA = sqrt(BA.x**2 + BA.y**2)
        norm_BC = sqrt(BC.x**2 + BC.y**2)

        u = Point(BA.x / norm_BA, BA.y / norm_BA)
        v = Point(BC.x / norm_BC, BC.y / norm_BC)
        w = u + v

        if abs(w.x) < 1e-20 and abs(w.y) < 1e-20:
            w = Point(-u.y, u.x)

        P = B + w
        a = B.y - P.y
        b = P.x - B.x
        c = -a * B.x - b * B.y
        return Line(a, b, c)
    except Exception:
        return None


# =============================================================================
# FootOfPerpendicular
# =============================================================================


@geometry_symbol("FootOfPerpendicular", category="constructions")
def FootOfPerpendicular(arg1: Any, arg2: Any) -> Point:
    """点から直線への垂線の足

    IR/GeoGebra 互換のため、引数順 (line, point) と (point, line) の両方を受け付ける。
    """
    # SymPy
    if isinstance(arg1, Line) and isinstance(arg2, Point):
        line, point = arg1, arg2
    elif isinstance(arg1, Point) and isinstance(arg2, Line):
        point, line = arg1, arg2
    else:
        line, point = arg1, arg2

    a, b, c = line.a, line.b, line.c
    x0, y0 = point.x, point.y
    denom = a**2 + b**2

    x = (b * (b * x0 - a * y0) - a * c) / denom
    y = (a * (-b * x0 + a * y0) - b * c) / denom

    return Point(x, y)


@FootOfPerpendicular.set_numpy
def _FootOfPerpendicular_numpy(arg1, arg2):
    return foot_of_perpendicular_numpy_impl(arg1, arg2)


@FootOfPerpendicular.set_mpmath
def _FootOfPerpendicular_mpmath(arg1, arg2):
    return foot_of_perpendicular_mpmath_impl(arg1, arg2)
