"""
Auxiliary geometry entity classes extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf, sqrt as mp_sqrt

from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPPoint


class MPSegment:
    __slots__ = ["p1", "p2"]

    def __init__(self, p1: "MPPoint", p2: "MPPoint"):
        self.p1 = p1
        self.p2 = p2

    def __repr__(self):
        return f"MPSegment({self.p1}, {self.p2})"

    def length(self) -> mpf:
        return self.p1.distance_to(self.p2)

    def midpoint(self) -> "MPPoint":
        return _mp_midpoint(self.p1, self.p2)


class MPRay:
    __slots__ = ["start", "through"]

    def __init__(self, start: "MPPoint", through: "MPPoint"):
        self.start = start
        self.through = through

    def __repr__(self):
        return f"MPRay({self.start}, {self.through})"


class MPVector:
    __slots__ = ["x", "y"]

    def __init__(self, x, y):
        self.x = x if isinstance(x, mpf) else strict_to_mpf(x, context="geometry.mp_aux_entities.MPVector.x")
        self.y = y if isinstance(y, mpf) else strict_to_mpf(y, context="geometry.mp_aux_entities.MPVector.y")

    def __repr__(self):
        return f"MPVector({mp.nstr(self.x, 15)}, {mp.nstr(self.y, 15)})"

    def norm(self) -> mpf:
        return mp_sqrt(self.x**2 + self.y**2)

    def dot(self, other) -> mpf:
        return self.x * other.x + self.y * other.y

    def cross(self, other) -> mpf:
        return self.x * other.y - self.y * other.x


def mp_segment(p1: "MPPoint", p2: "MPPoint") -> MPSegment:
    return MPSegment(p1, p2)


def mp_ray(start: "MPPoint", through: "MPPoint") -> MPRay:
    return MPRay(start, through)


def mp_vector(A: "MPPoint", B: "MPPoint") -> MPVector:
    return MPVector(B.x - A.x, B.y - A.y)


def _mp_midpoint(p1: "MPPoint", p2: "MPPoint") -> "MPPoint":
    from geosolver.geometry.mp.mp_impl import mp_midpoint

    return mp_midpoint(p1, p2)
