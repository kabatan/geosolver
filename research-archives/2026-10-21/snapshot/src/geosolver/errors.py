"""
GeoSolver エラー階層

例外は「プログラマの誤り」「不正入力」に限定。
数値不安定/時間切れ/退化は SolveResult.status で表現する。
"""


class GeometryError(Exception):
    """幾何計算の基底例外クラス"""

    pass


class GeometryDomainError(GeometryError):
    """The requested object is outside the nondegenerate Euclidean domain."""


class AmbiguousResultError(GeometryError):
    """A construction has several branches and no unique selector."""


class InfiniteSolutionsError(GeometryError):
    """A construction has infinitely many valid results."""


class DegenerateGeometryError(GeometryDomainError):
    """退化した図形（無効な図形）の例外"""

    pass


class CoincidentPointsError(DegenerateGeometryError):
    """2点以上が一致する場合"""

    pass


class NoIntersectionError(GeometryError):
    """交点が存在しない場合"""

    pass


class InvalidCircleError(DegenerateGeometryError):
    """無効な円（半径がゼロまたは負）"""

    pass
