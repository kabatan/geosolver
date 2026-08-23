"""
Builder class extracted from mp_impl.
"""

from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from mpmath import mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPCircle, MPLine, MPPoint


class MPGeometryBuilder:
    def __init__(self, precision: int = 50):
        impl = _impl()
        impl.set_precision(precision + 20)
        self.precision = precision

    def point(self, x, y) -> "MPPoint":
        impl = _impl()
        return impl.MPPoint(impl._to_mpf(x), impl._to_mpf(y))

    def line(self, p1: "MPPoint", p2: "MPPoint") -> Optional["MPLine"]:
        return _impl().mp_line_through_two_points(p1, p2)

    def circle(self, center: "MPPoint", radius) -> "MPCircle":
        impl = _impl()
        return impl.MPCircle(center, impl._to_mpf(radius))

    def incircle(self, A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPCircle"]:
        return _impl().mp_incircle(A, B, C)

    def circumcircle(self, A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPCircle"]:
        return _impl().mp_circumcircle(A, B, C)

    def triangle_center(self, A: "MPPoint", B: "MPPoint", C: "MPPoint", n: int) -> Optional["MPPoint"]:
        return _impl().mp_triangle_center(A, B, C, n)

    def incircle_contact_point(
        self, A: "MPPoint", B: "MPPoint", C: "MPPoint", side: Optional[Tuple["MPPoint", "MPPoint"]] = None
    ):
        return _impl().mp_incircle_contact_point(A, B, C, side)

    def arc_midpoint(
        self,
        circle: "MPCircle",
        P1: "MPPoint",
        P2: "MPPoint",
        including: Optional["MPPoint"] = None,
        excluding: Optional["MPPoint"] = None,
    ):
        return _impl().mp_arc_midpoint(circle, P1, P2, including, excluding)

    def intersect(self, obj1, obj2, exclude: Optional["MPPoint"] = None):
        return _impl().mp_intersect(obj1, obj2, exclude)

    def perpendicular_line(self, line: "MPLine", point: "MPPoint") -> "MPLine":
        return _impl().mp_perpendicular_line(line, point)

    def midpoint(self, A: "MPPoint", B: "MPPoint") -> "MPPoint":
        return _impl().mp_midpoint(A, B)

    def distance(self, obj1, obj2) -> mpf:
        return _impl().mp_distance(obj1, obj2)

    def angle(self, l1: "MPLine", l2: "MPLine") -> mpf:
        return _impl().mp_angle_between_lines(l1, l2)

    def triangle_type(self, A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional[str]:
        return _impl().mp_triangle_type(A, B, C)

    def middle_point_on_line(self, A: "MPPoint", B: "MPPoint", C: "MPPoint") -> Optional["MPPoint"]:
        return _impl().mp_middle_point_on_line(A, B, C)

    def orthic_triangle(self, A: "MPPoint", B: "MPPoint", C: "MPPoint"):
        return _impl().mp_orthic_triangle(A, B, C)


def _impl():
    import geosolver.geometry.mp.mp_impl as impl

    return impl
