"""
円弧 (Arc) クラスと関連関数

円弧上の点を扱うための機能を提供。
"""

from typing import Any

try:
    import mpmath
except ImportError:
    mpmath = None

from geosolver.geometry.entities import Circle, Line, Point
from geosolver.geometry.operations.arc_membership import point_on_arc as _point_on_arc_impl
from geosolver.geometry.registry import geometry_symbol


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
        circle: Circle = None,
        start_point: Point = None,
        end_point: Point = None,
        including: Point | None = None,
        excluding: Point | None = None,
        **aliases,
    ):
        from geosolver.geometry.arc_parameters import resolve_arc_arguments

        circle, start_point, end_point = resolve_arc_arguments(
            circle, start_point, end_point, aliases
        )
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
        from geosolver.geometry.arc_parameters import arc_parameters

        arc_parameters(circle, start_point, end_point, including, excluding, tolerance="1e-12")

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
    """Midpoint on the same selected arc as PointOnArc."""
    return PointOnArc(arc, 0.5)


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
    from mpmath import mp

    from geosolver.geometry.arc_parameters import arc_parameters

    with mp.workdps(40):
        parameter = mp.mpf(str(t))
        if not 0 <= parameter <= 1:
            raise ValueError("PointOnArc parameter must be in [0, 1]")
        first, sweep = arc_parameters(
            arc.circle, arc.start, arc.end, arc.including, arc.excluding, tolerance="1e-12"
        )
        angle = first + parameter * sweep
        return Point(
            arc.center.x + arc.radius * mp.cos(angle), arc.center.y + arc.radius * mp.sin(angle)
        )


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
