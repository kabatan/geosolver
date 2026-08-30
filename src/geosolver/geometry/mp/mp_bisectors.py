"""
Bisector helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPLine, MPPoint


def _mp_line_class() -> type[MPLine]:
    from geosolver.geometry.mp.mp_impl import MPLine

    return MPLine


def _mp_point_class() -> type[MPPoint]:
    from geosolver.geometry.mp.mp_impl import MPPoint

    return MPPoint


def _mp_vector_class():
    from geosolver.geometry.mp.mp_impl import MPVector

    return MPVector


def _mp_midpoint(a: MPPoint, b: MPPoint) -> MPPoint:
    from geosolver.geometry.mp.mp_impl import mp_midpoint

    return mp_midpoint(a, b)


def _mp_line_through_two_points(a: MPPoint, b: MPPoint):
    from geosolver.geometry.mp.mp_impl import mp_line_through_two_points

    return mp_line_through_two_points(a, b)


def _tol() -> mpf:
    return mpf(10) ** (-(mp.dps - 10))


def mp_perpendicular_bisector(A: MPPoint, B: MPPoint) -> MPLine:
    mid = _mp_midpoint(A, B)
    dx = B.x - A.x
    dy = B.y - A.y
    a = dx
    b = dy
    c = -(dx * mid.x + dy * mid.y)
    line_cls = _mp_line_class()
    return line_cls(a, b, c)


def mp_angle_bisector(A: MPPoint, B: MPPoint, C: MPPoint) -> MPLine:
    vector_cls = _mp_vector_class()
    line_cls = _mp_line_class()
    point_cls = _mp_point_class()

    BA = vector_cls(A.x - B.x, A.y - B.y)
    BC = vector_cls(C.x - B.x, C.y - B.y)

    norm_BA = BA.norm()
    norm_BC = BC.norm()
    tol = _tol()

    if norm_BA < tol or norm_BC < tol:
        return _mp_line_through_two_points(B, A if norm_BC < tol else C)

    unit_BA = vector_cls(BA.x / norm_BA, BA.y / norm_BA)
    unit_BC = vector_cls(BC.x / norm_BC, BC.y / norm_BC)
    bisector_dir = vector_cls(unit_BA.x + unit_BC.x, unit_BA.y + unit_BC.y)

    if bisector_dir.norm() < tol:
        return line_cls(-BA.y, BA.x, BA.y * B.x - BA.x * B.y)

    through_point = point_cls(B.x + bisector_dir.x, B.y + bisector_dir.y)
    return _mp_line_through_two_points(B, through_point)
