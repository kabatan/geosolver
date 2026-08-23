"""
円弧 (Arc) クラスと関連関数

円弧上の点を扱うための機能を提供。
"""

from typing import Optional, Any
import math
from sympy import sqrt
try:
    import mpmath
except ImportError:
    mpmath = None

from geosolver.geometry.registry import geometry_symbol
from geosolver.geometry.entities import Point, Line, Circle

from geosolver.geometry.operations.arc_membership import point_on_arc as _point_on_arc_impl
from geosolver.geometry.operations.arc_angle_helpers import (
    angle_in_arc as _angle_in_arc,
    angle_to_value as _angle_to_value,
    get_cos as _get_cos,
    get_dynamic_tolerance_arc as _get_dynamic_tolerance_arc,
    get_sin as _get_sin,
    normalize_angle as _normalize_angle,
    point_angle as _point_angle,
)


class Arc:
    """
    円弧を表すクラス

    使用例:
        Arc(circle, start_point, end_point)
        Arc(circle, start_point, end_point, including=point)  # 指定点を含む弧
        Arc(circle, start_point, end_point, excluding=point)  # 指定点を含まない弧
    """

    def __init__(
        self,
        circle: Circle,
        start_point: Point,
        end_point: Point,
        including: Optional[Point] = None,
        excluding: Optional[Point] = None,
    ):
        if not isinstance(circle, Circle):
            raise TypeError("Arc requires a Circle as first argument")
        if not isinstance(start_point, Point) or not isinstance(end_point, Point):
            raise TypeError("Arc requires Points for start and end")
        if including is not None and excluding is not None:
            raise ValueError("Cannot specify both including and excluding")

        self.circle = circle
        self.start = start_point
        self.end = end_point
        self.including = including
        self.excluding = excluding

    @property
    def center(self) -> Point:
        """円弧の中心（円の中心）"""
        return self.circle.center

    @property
    def radius(self):
        """円弧の半径"""
        return self.circle.radius

    def __repr__(self):
        inc_exc = ""
        if self.including is not None:
            inc_exc = f", including={self.including}"
        elif self.excluding is not None:
            inc_exc = f", excluding={self.excluding}"
        return f"Arc({self.circle}, {self.start}, {self.end}{inc_exc})"


def _point_on_arc(arc: Arc, point: Point) -> bool:
    return _point_on_arc_impl(arc, point)


def arc_midpoint(arc: Arc) -> Point:
    """弧の中点を計算"""
    start_angle = _point_angle(arc.center, arc.start)
    end_angle = _point_angle(arc.center, arc.end)

    s = _normalize_angle(start_angle)
    e = _normalize_angle(end_angle)

    # 角度を数値化して平均をとる
    s_f = _angle_to_value(s)
    e_f = _angle_to_value(e)
    pi_val = mpmath.pi if mpmath and isinstance(s_f, mpmath.mpf) else math.pi
    two_pi = 2 * pi_val

    # Counter-clockwise arc length from s to e.
    diff = e_f - s_f
    if diff < 0:
        diff += two_pi

    # Candidate midpoints for the two arcs.
    mid_angle1 = (s_f + diff / 2) % two_pi
    mid_angle2 = (mid_angle1 + pi_val) % two_pi

    inc_angle = _point_angle(arc.center, arc.including) if arc.including else None
    exc_angle = _point_angle(arc.center, arc.excluding) if arc.excluding else None

    if inc_angle is not None or exc_angle is not None:
        inc_val = _angle_to_value(_normalize_angle(inc_angle)) if inc_angle is not None else None
        exc_val = _angle_to_value(_normalize_angle(exc_angle)) if exc_angle is not None else None

        m1_ok = _angle_in_arc(mid_angle1, s_f, e_f, inc_val, exc_val)
        m2_ok = _angle_in_arc(mid_angle2, s_f, e_f, inc_val, exc_val)

        if m1_ok and not m2_ok:
            mid_angle = mid_angle1
        elif m2_ok and not m1_ok:
            mid_angle = mid_angle2
        else:
            # Ambiguous: default to shorter arc
            mid_angle = mid_angle1 if diff <= pi_val else mid_angle2
    else:
        # Default: shorter arc
        mid_angle = mid_angle1 if diff <= pi_val else mid_angle2

    # 中点の座標
    # cos, sin を適切に選択
    cos_val = _get_cos(mid_angle)
    sin_val = _get_sin(mid_angle)

    x = arc.center.x + arc.radius * cos_val
    y = arc.center.y + arc.radius * sin_val
    return Point(x, y)


# PointOnArc: 弧上のパラメトリック点
@geometry_symbol("PointOnArc", category="parametric")
def PointOnArc(arc: Arc, t: Any) -> Point:
    """
    弧上の点（パラメータt: 0→1で弧の始点から終点）

    Args:
        arc: Arc オブジェクト
        t: パラメータ (0-1)

    Returns:
        Point
    """
    start_angle = _point_angle(arc.center, arc.start)
    end_angle = _point_angle(arc.center, arc.end)

    # 弧の向きを考慮
    # 将来的に including/excluding に基づく弧選択を拡張
    # 現在は単純に角度補間（反時計回りとは限らない？）
    # 本来は Arc クラス自体が向きや選択範囲を正規化して持つべきだが
    # ここでは単純な線形補間

    angle = start_angle + t * (end_angle - start_angle)

    cos_val = _get_cos(angle)
    sin_val = _get_sin(angle)

    x = arc.center.x + arc.radius * cos_val
    y = arc.center.y + arc.radius * sin_val
    return Point(x, y)


# Intersect のArc対応（別モジュールで統合する必要あり）
def line_arc_intersection(line: Line, arc: Arc):
    """直線と弧の交点"""
    from geosolver.geometry.operations.intersections import IntersectLineCircle

    # まず直線と円の交点を求める
    intersections = IntersectLineCircle(line, arc.circle)

    # 弧上の点のみをフィルタ
    result = []
    for pt in intersections:
        if _point_on_arc(arc, pt):
            result.append(pt)

    if len(result) == 1:
        return result[0]
    return result


__all__ = [
    "Arc",
    "PointOnArc",
    "arc_midpoint",
    "line_arc_intersection",
]
