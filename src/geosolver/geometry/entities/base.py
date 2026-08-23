"""
2D幾何の基本エンティティ - Point, Line, Circle

sympy を使用した高精度シンボリック計算に対応。
既存のgeometry/geometry2d/basics.pyからの移植。
"""

from sympy import (
    sympify,
    sqrt,
    Abs,
    expand,
    N as _N,
    pi,
)
from typing import Union, Optional

from .linear_primitives import Ray, Segment, midpoint

__all__ = ["Point", "Line", "Circle", "Segment", "Ray", "midpoint", "_sympify_preserve_precision"]


_MPF_TYPE = None


class Point:
    """
    2次元の点クラス

    座標は sympy の式として保持され、高精度計算が可能。
    ベクトル演算（加算、減算、スカラー倍、内積、外積）にも対応。

    Examples:
        >>> A = Point(1, 2)
        >>> B = Point(3, 0)
        >>> C = A + B           # Point(4, 2)
        >>> d = A.distance_to(B) # sqrt(8)
    """

    def __init__(
        self, x: Union[int, float, str] = 0, y: Union[int, float, str] = 0
    ):
        """
        点の初期化

        Args:
            x, y: 座標（int, float, sympyの式、または文字列表現）
        """
        if isinstance(x, int):
            self.x = x
        else:
            self.x = _sympify_preserve_precision(x)

        if isinstance(y, int):
            self.y = y
        else:
            self.y = _sympify_preserve_precision(y)
        self._norm_cache = None
        self._hash_cache = None

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def __eq__(self, other):
        if not isinstance(other, Point):
            return False
        if self.x == other.x and self.y == other.y:
            return True
        try:
            dx = float(_N(self.x - other.x, 15))
            dy = float(_N(self.y - other.y, 15))
            if abs(dx) < 1e-14 and abs(dy) < 1e-14:
                return True
        except Exception:
            pass
        return False

    def __hash__(self):
        if self._hash_cache is None:
            self._hash_cache = hash((self.x, self.y))
        return self._hash_cache

    def __add__(self, other):
        """ベクトル加算"""
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        """ベクトル減算"""
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        """スカラー倍"""
        if isinstance(scalar, (int, float)):
            return Point(self.x * scalar, self.y * scalar)
        s = _sympify_preserve_precision(scalar)
        return Point(self.x * s, self.y * s)

    def __rmul__(self, scalar):
        """スカラー倍（逆順）"""
        if isinstance(scalar, (int, float)):
            return Point(self.x * scalar, self.y * scalar)
        s = _sympify_preserve_precision(scalar)
        return Point(self.x * s, self.y * s)

    def __truediv__(self, scalar):
        """スカラー除算"""
        if isinstance(scalar, (int, float)):
            return Point(self.x / scalar, self.y / scalar)
        s = _sympify_preserve_precision(scalar)
        return Point(self.x / s, self.y / s)

    def __neg__(self):
        """符号反転"""
        return Point(-self.x, -self.y)

    def distance_to(self, other: "Point"):
        """他の点との距離（sympyの厳密な表現）"""
        dx = self.x - other.x
        dy = self.y - other.y
        return sqrt(dx**2 + dy**2)

    def dot(self, other: "Point"):
        """内積"""
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Point"):
        """外積（2Dではスカラー値）"""
        return self.x * other.y - self.y * other.x

    def norm(self):
        """ノルム（原点からの距離）"""
        if self._norm_cache is None:
            self._norm_cache = sqrt(self.x**2 + self.y**2)
        return self._norm_cache

    def normalize(self) -> "Point":
        """単位ベクトル化"""
        n = self.norm()
        if n == 0:
            return Point(0, 0)
        return Point(self.x / n, self.y / n)

    def evalf(self, precision: int = 15):
        """数値評価（指定した精度で）"""
        return Point(_N(self.x, precision), _N(self.y, precision))

    def simplify(self) -> "Point":
        """式を簡約化"""
        return Point(expand(self.x), expand(self.y))


class Line:
    """
    2次元の直線クラス（ax + by + c = 0）

    係数は正規化される（a^2 + b^2 = 1）。

    Examples:
        >>> L = Line(1, 1, -2)  # x + y - 2 = 0
        >>> d = L.distance_to_point(Point(0, 0))  # sqrt(2)
    """

    def __init__(
        self,
        arg1: Union[int, float, str, Point],
        arg2: Union[int, float, str, Point],
        arg3: Union[int, float, str, None] = None,
    ):
        """
        直線の作成

        Args:
            Line(a, b, c): ax + by + c = 0
            Line(p1, p2): 2点を通る直線
        """
        from geosolver.geometry.entities.base import Point

        if isinstance(arg1, Point) and isinstance(arg2, Point):
            # 2点定義: (y1 - y2)x + (x2 - x1)y + x1y2 - x2y1 = 0
            # a = y1 - y2, b = x2 - x1, c = x1*y2 - x2*y1
            a = arg1.y - arg2.y
            b = arg2.x - arg1.x
            c = arg1.x * arg2.y - arg2.x * arg1.y
        else:
            if arg3 is None:
                raise ValueError("Line requires either two points or three coefficients (a, b, c)")
            a, b, c = arg1, arg2, arg3

        a = a if isinstance(a, int) else _sympify_preserve_precision(a)
        b = b if isinstance(b, int) else _sympify_preserve_precision(b)
        c = c if isinstance(c, int) else _sympify_preserve_precision(c)

        norm = sqrt(a**2 + b**2)
        if norm == 0:
            raise ValueError("Dimensions of line must be non-zero (points must be distinct)")

        self.a = a / norm
        self.b = b / norm
        self.c = c / norm
        self._normal_cache = None
        self._direction_cache = None

    def __repr__(self):
        return f"Line({self.a}*x + {self.b}*y + {self.c} = 0)"

    def __eq__(self, other):
        if not isinstance(other, Line):
            return False
        if self.a == other.a and self.b == other.b and self.c == other.c:
            return True
        try:
            da = float(_N(self.a - other.a, 15))
            db = float(_N(self.b - other.b, 15))
            dc = float(_N(self.c - other.c, 15))
            if abs(da) < 1e-14 and abs(db) < 1e-14 and abs(dc) < 1e-14:
                return True
        except Exception:
            pass
        return False

    def distance_to_point(self, p: Point):
        """点から直線までの距離"""
        return Abs(self.a * p.x + self.b * p.y + self.c)

    def contains_point(self, p: Point) -> bool:
        """点が直線上にあるか"""
        val = self.a * p.x + self.b * p.y + self.c
        if val == 0:
            return True
        try:
            return abs(float(_N(val, 15))) < 1e-14
        except Exception:
            return val.simplify() == 0

    def is_parallel(self, other: "Line") -> bool:
        """２直線が平行か"""
        det = self.a * other.b - self.b * other.a
        if det == 0:
            return True
        try:
            return abs(float(_N(det, 15))) < 1e-14
        except Exception:
            return det.simplify() == 0

    def is_perpendicular(self, other: "Line") -> bool:
        """２直線が垂直か"""
        dot = self.a * other.a + self.b * other.b
        if dot == 0:
            return True
        try:
            return abs(float(_N(dot, 15))) < 1e-14
        except Exception:
            return dot.simplify() == 0

    def normal_vector(self) -> Point:
        """法線ベクトル"""
        if self._normal_cache is None:
            self._normal_cache = Point(self.a, self.b)
        return self._normal_cache

    def direction_vector(self) -> Point:
        """方向ベクトル"""
        if self._direction_cache is None:
            self._direction_cache = Point(-self.b, self.a)
        return self._direction_cache

    def evalf(self, precision: int = 15):
        """数値評価"""
        return Line(
            _N(self.a, precision), _N(self.b, precision), _N(self.c, precision)
        )


class Circle:
    """
    2次元の円クラス

    中心点と半径で定義。

    Examples:
        >>> C = Circle(Point(0, 0), 5)  # 原点中心、半径5
        >>> C.contains_point(Point(3, 4))  # True
    """

    def __init__(self, center: Point, radius: Union[int, float, str]):
        radius = sympify(radius)
        if radius < 0:
            raise ValueError("Radius must be non-negative")
        self.center = center
        self.radius = radius

    def __repr__(self):
        return f"Circle(center={self.center}, radius={self.radius})"

    def __eq__(self, other):
        if not isinstance(other, Circle):
            return False
        diff = self.radius - other.radius
        if diff == 0 and self.center == other.center:
            return True
        try:
            return self.center == other.center and abs(float(_N(diff, 15))) < 1e-14
        except Exception:
            return self.center == other.center and expand(diff) == 0

    def contains_point(self, p: Point) -> bool:
        """点が円周上にあるか"""
        dist = self.center.distance_to(p)
        diff = dist - self.radius
        if diff == 0:
            return True
        try:
            return abs(float(_N(diff, 15))) < 1e-14
        except Exception:
            return expand(diff) == 0

    def is_inside(self, p: Point) -> bool:
        """点が円の内部にあるか"""
        dist = self.center.distance_to(p)
        return _N(dist) < _N(self.radius)

    def area(self):
        """円の面積"""
        return pi * self.radius**2

    def circumference(self):
        """円周の長さ"""
        return 2 * pi * self.radius

    def evalf(self, precision: int = 15):
        """数値評価"""
        return Circle(self.center.evalf(precision), _N(self.radius, precision))


def _sympify_preserve_precision(value):
    """sympify の前処理。

    mpmath.mpf をそのまま sympify すると float 経由で丸められ、
    高精度最適化の有効桁が失われることがある。
    文字列化してから sympify することで桁を保持する。
    """
    global _MPF_TYPE
    if _MPF_TYPE is None:
        try:
            import mpmath

            _MPF_TYPE = type(mpmath.mpf("1.0"))
        except Exception:
            _MPF_TYPE = False

    try:
        if _MPF_TYPE and isinstance(value, _MPF_TYPE):
            return sympify(str(value))
    except Exception:
        pass
    return sympify(value)


