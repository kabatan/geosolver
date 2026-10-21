"""
Triangle metric helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPLine, MPPoint


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_line_class() -> type[MPLine]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def _mp_vector_class():
    from geosolver.geometry.mp.mp_impl import MPVector

    return MPVector


def mp_triangle_area(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return abs((B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x)) / 2


def mp_triangle_perimeter(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    return a + b + c


def mp_distance(obj1, obj2) -> mpf:
    point_cls = _mp_point_class()
    line_cls = _mp_line_class()
    if isinstance(obj1, point_cls) and isinstance(obj2, point_cls):
        return obj1.distance_to(obj2)
    if isinstance(obj1, point_cls) and isinstance(obj2, line_cls):
        return obj2.distance_to_point(obj1)
    if isinstance(obj1, line_cls) and isinstance(obj2, point_cls):
        return obj1.distance_to_point(obj2)
    raise TypeError(f"Unsupported types for distance: {type(obj1)}, {type(obj2)}")


def mp_midpoint(A: MPPoint, B: MPPoint) -> MPPoint:
    point_cls = _mp_point_class()
    return point_cls((A.x + B.x) / 2, (A.y + B.y) / 2)


def mp_perimeter(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return mp_triangle_perimeter(A, B, C)


def mp_is_acute_triangle(A: MPPoint, B: MPPoint, C: MPPoint) -> bool:
    a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2
    c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2
    tol = 32 * mp.eps * max(a2, b2, c2)

    area = mp_triangle_area(A, B, C)
    if area == 0 or area < tol:
        return False

    return a2 + b2 > c2 + tol and b2 + c2 > a2 + tol and c2 + a2 > b2 + tol


def mp_angle(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    from geosolver.geometry.mp.mp_line_relations import mp_angle_between_vectors

    vector_cls = _mp_vector_class()
    BA = vector_cls(A.x - B.x, A.y - B.y)
    BC = vector_cls(C.x - B.x, C.y - B.y)

    # A zero-length ray has no direction, hence no angle.  Do not coerce this
    # undefined case to zero: doing so makes coincident-point diagrams satisfy
    # angle constraints.  Non-zero rays, however small, remain valid because
    # the angle itself is scale invariant.
    if (BA.x == 0 and BA.y == 0) or (BC.x == 0 and BC.y == 0):
        raise ValueError("Angle undefined for zero-length ray")
    return mp_angle_between_vectors(BA, BC)


def mp_area(A: MPPoint, B: MPPoint, C: MPPoint) -> mpf:
    return mp_triangle_area(A, B, C)


def mp_centroid(A: MPPoint, B: MPPoint, C: MPPoint) -> MPPoint:
    point_cls = _mp_point_class()
    return point_cls((A.x + B.x + C.x) / 3, (A.y + B.y + C.y) / 3)
