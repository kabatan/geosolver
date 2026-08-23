"""
Core high-precision geometry types extracted from mp_impl.
"""

from __future__ import annotations

from typing import Tuple

from mpmath import mp, mpf, sqrt as mp_sqrt

from geosolver.geometry.mp.mp_conversion import to_mpf


class MPPoint:
    __slots__ = ["x", "y"]

    def __init__(self, x, y):
        self.x = to_mpf(x)
        self.y = to_mpf(y)

    def __repr__(self):
        return f"MPPoint({mp.nstr(self.x, 15)}, {mp.nstr(self.y, 15)})"

    def __add__(self, other):
        return MPPoint(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return MPPoint(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        s = to_mpf(scalar)
        return MPPoint(self.x * s, self.y * s)

    def __rmul__(self, scalar):
        return self.__mul__(scalar)

    def __truediv__(self, scalar):
        s = to_mpf(scalar)
        return MPPoint(self.x / s, self.y / s)

    def __eq__(self, other):
        if not isinstance(other, MPPoint):
            return False
        tol = mpf(10) ** (-(mp.dps - 5))
        return abs(self.x - other.x) < tol and abs(self.y - other.y) < tol

    def dot(self, other) -> mpf:
        return self.x * other.x + self.y * other.y

    def cross(self, other) -> mpf:
        return self.x * other.y - self.y * other.x

    def norm(self) -> mpf:
        return mp_sqrt(self.x**2 + self.y**2)

    def distance_to(self, other) -> mpf:
        return mp_sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def to_float_tuple(self) -> Tuple[float, float]:
        return (float(self.x), float(self.y))


class MPLine:
    __slots__ = ["a", "b", "c"]

    def __init__(self, a, b, c):
        a = to_mpf(a)
        b = to_mpf(b)
        c = to_mpf(c)

        norm = mp_sqrt(a**2 + b**2)
        if norm == 0:
            raise ValueError("Invalid line")
        self.a = a / norm
        self.b = b / norm
        self.c = c / norm

    def __repr__(self):
        return f"MPLine({mp.nstr(self.a, 6)}*x + {mp.nstr(self.b, 6)}*y + {mp.nstr(self.c, 6)} = 0)"

    def direction_vector(self) -> MPPoint:
        return MPPoint(-self.b, self.a)

    def normal_vector(self) -> MPPoint:
        return MPPoint(self.a, self.b)

    def distance_to_point(self, p: MPPoint) -> mpf:
        return abs(self.a * p.x + self.b * p.y + self.c)


class MPCircle:
    __slots__ = ["center", "radius"]

    def __init__(self, center: MPPoint, radius):
        self.center = center
        self.radius = to_mpf(radius)

    def __repr__(self):
        return f"MPCircle(center={self.center}, r={mp.nstr(self.radius, 15)})"
