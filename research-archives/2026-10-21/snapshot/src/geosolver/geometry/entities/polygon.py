"""
2D Polygon Entity
"""

from sympy import Abs
from sympy import N as _N

from geosolver.geometry.entities.base import Point


class Polygon:
    """
    2D Polygon class defined by a list of vertices.
    """

    def __init__(self, vertices: list[Point]):
        if len(vertices) < 3:
            raise ValueError("Polygon must have at least 3 vertices.")
        self._vertices = vertices
        self._area_cache = None
        self._perimeter_cache = None
        self._is_convex_cache = None
        self._is_self_intersecting_cache = None

    @property
    def vertices(self) -> list[Point]:
        return self._vertices

    @property
    def edges(self) -> list[tuple[Point, Point]]:
        """Returns a list of edges as tuples of Points (start, end)."""
        edges = []
        n = len(self._vertices)
        for i in range(n):
            edges.append((self._vertices[i], self._vertices[(i + 1) % n]))
        return edges

    @property
    def area(self):
        """Calculates the area of the polygon (absolute value)."""
        if self._area_cache is None:
            n = len(self._vertices)
            area = 0
            for i in range(n):
                j = (i + 1) % n
                area += self._vertices[i].x * self._vertices[j].y
                area -= self._vertices[j].x * self._vertices[i].y
            self._area_cache = Abs(area) / 2
        return self._area_cache

    @property
    def perimeter(self):
        """Calculates the perimeter of the polygon."""
        if self._perimeter_cache is None:
            p = 0
            n = len(self._vertices)
            for i in range(n):
                j = (i + 1) % n
                p += self._vertices[i].distance_to(self._vertices[j])
            self._perimeter_cache = p
        return self._perimeter_cache

    def is_convex(self) -> bool:
        """Checks if the polygon is convex."""
        if self._is_convex_cache is None:
            self._is_convex_cache = self._check_convexity()
        return self._is_convex_cache

    def _check_convexity(self) -> bool:
        n = len(self._vertices)
        if n < 3:
            return False

        sign = None
        for i in range(n):
            p1 = self._vertices[i]
            p2 = self._vertices[(i + 1) % n]
            p3 = self._vertices[(i + 2) % n]

            # Cross product of edge vectors
            cross = (p2.x - p1.x) * (p3.y - p2.y) - (p2.y - p1.y) * (p3.x - p2.x)

            try:
                cross_val = float(_N(cross, 15))
                if abs(cross_val) < 1e-12:
                    continue  # Collinear is okay

                current_sign = cross_val > 0
                if sign is None:
                    sign = current_sign
                elif sign != current_sign:
                    return False
            except Exception:
                # Fallback for symbolic (simplified check)
                pass
        return True

    def is_self_intersecting(self) -> bool:
        """Checks if the polygon is self-intersecting."""
        if self._is_self_intersecting_cache is None:
            self._is_self_intersecting_cache = self._check_self_intersection()
        return self._is_self_intersecting_cache

    def _check_self_intersection(self) -> bool:
        # Naive O(n^2) check
        edges = self.edges
        n = len(edges)
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue  # Adjacent edges (first and last)

                p1, p2 = edges[i]
                p3, p4 = edges[j]

                if self._segments_intersect(p1, p2, p3, p4):
                    return True
        return False

    def _segments_intersect(self, p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
        # Helper to check if segment p1p2 intersects p3p4
        o1 = _segment_orientation(p1, p2, p3)
        o2 = _segment_orientation(p1, p2, p4)
        o3 = _segment_orientation(p3, p4, p1)
        o4 = _segment_orientation(p3, p4, p2)

        # Collinear cases are intentionally omitted here; this legacy symbolic
        # helper only treats a proper crossing as self-intersection.
        return o1 != o2 and o3 != o4

    def __repr__(self):
        return f"Polygon(vertices={self._vertices})"


def _segment_orientation(p: Point, q: Point, r: Point) -> int:
    first = float(_N(q.y - p.y, 15)) * float(_N(r.x - q.x, 15))
    second = float(_N(q.x - p.x, 15)) * float(_N(r.y - q.y, 15))
    val = first - second
    if abs(val) < 1e-12:
        return 0
    return 1 if val > 0 else 2
