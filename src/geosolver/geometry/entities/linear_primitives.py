"""Linear primitive entities extracted from base geometry entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geosolver.errors import GeometryDomainError

if TYPE_CHECKING:
    from .base import Point


class Segment:
    """線分"""

    def __init__(self, p1: Point, p2: Point) -> None:
        from geosolver.geometry.entities.base import Point

        if not (isinstance(p1, Point) and isinstance(p2, Point)):
            raise TypeError("Segment requires two Points")
        if p1.x == p2.x and p1.y == p2.y:
            raise GeometryDomainError("Segment requires two distinct points")
        self.p1 = p1
        self.p2 = p2

    def length(self):
        return self.p1.distance_to(self.p2)

    def __repr__(self) -> str:
        return f"Segment({self.p1}, {self.p2})"

    def evalf(self, digits=None):
        return Segment(self.p1.evalf(digits), self.p2.evalf(digits))


class Ray:
    """半直線"""

    def __init__(self, start: Point, through: Point) -> None:
        from geosolver.geometry.entities.base import Point

        if not (isinstance(start, Point) and isinstance(through, Point)):
            raise TypeError("Ray requires two Points")
        if start.x == through.x and start.y == through.y:
            raise GeometryDomainError("Ray requires two distinct points")
        self.start = start
        self.through = through

    def __repr__(self) -> str:
        return f"Ray({self.start}, through={self.through})"

    def evalf(self, digits=None):
        return Ray(self.start.evalf(digits), self.through.evalf(digits))


def midpoint(A: Point, B: Point) -> Point:
    from geosolver.geometry.entities.base import Point

    return Point((A.x + B.x) / 2, (A.y + B.y) / 2)
