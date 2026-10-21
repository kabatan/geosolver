"""
Core high-precision geometry types extracted from mp_impl.
"""

from __future__ import annotations

from mpmath import mp, mpf
from mpmath import sqrt as mp_sqrt

from geosolver.errors import InvalidCircleError
from geosolver.geometry.mp.mp_conversion import to_mpf


class MPPoint:
    __slots__ = ["x", "y", "_circle_incidence"]

    def __init__(self, x, y):
        self.x = to_mpf(x)
        self.y = to_mpf(y)
        self._circle_incidence = None

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

    def to_float_tuple(self) -> tuple[float, float]:
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
    __slots__ = ["center", "radius", "_defining_incidence"]

    def __init__(self, center: MPPoint, radius):
        self.center = center
        self.radius = to_mpf(radius)
        if self.radius <= 0:
            raise InvalidCircleError("circle radius must be positive")
        self._defining_incidence = None

    def _state(self):
        return self.center.x, self.center.y, self.radius

    def _remember_defining_points(self, points):
        self._defining_incidence = (self._state(), tuple((p.x, p.y) for p in points))

    def _remember_parametric_point(self, point):
        point._circle_incidence = (self._state(), (point.x, point.y))

    def _has_proven_incidence(self, point):
        # These witnesses come only from constructions, never a proximity
        # tolerance. Coordinate snapshots invalidate them after any mutation.
        state, coordinates = self._state(), (point.x, point.y)
        if point._circle_incidence == (state, coordinates):
            return True
        return (
            self._defining_incidence is not None
            and self._defining_incidence[0] == state
            and coordinates in self._defining_incidence[1]
        )

    def __repr__(self):
        return f"MPCircle(center={self.center}, r={mp.nstr(self.radius, 15)})"
