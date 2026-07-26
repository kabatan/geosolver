"""
Geometric predicate helpers extracted from mp_impl.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from mpmath import mp, mpf

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPLine, MPPoint


def _tol() -> mpf:
    return mpf(10) ** (-(mp.dps - 10))


def _mp_circumcircle(a: "MPPoint", b: "MPPoint", c: "MPPoint"):
    from geosolver.geometry.mp.mp_impl import mp_circumcircle

    return mp_circumcircle(a, b, c)


def mp_are_collinear(A: "MPPoint", B: "MPPoint", C: "MPPoint") -> bool:
    cross = (B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x)
    return abs(cross) < _tol()


def mp_are_parallel(l1: "MPLine", l2: "MPLine") -> bool:
    det = l1.a * l2.b - l2.a * l1.b
    return abs(det) < _tol()


def mp_are_perpendicular(l1: "MPLine", l2: "MPLine") -> bool:
    dot = l1.a * l2.a + l1.b * l2.b
    return abs(dot) < _tol()


def mp_are_concyclic(A: "MPPoint", B: "MPPoint", C: "MPPoint", D: "MPPoint") -> bool:
    circ = _mp_circumcircle(A, B, C)
    if circ is None:
        return False

    dist_D = circ.center.distance_to(D)
    return abs(dist_D - circ.radius) < _tol()


def mp_slope(line: "MPLine") -> Optional[mpf]:
    if abs(line.b) < _tol():
        return None
    return -line.a / line.b
