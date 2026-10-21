"""Triangle excenter and excircle operations."""

from typing import Any

from geosolver.geometry.entities.base import Circle, Point
from geosolver.geometry.registry import geometry_symbol


def _mp_point_distance(p1: Point, p2: Point):
    from mpmath import sqrt

    return sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)


@geometry_symbol("Excenter", category="triangle")
def Excenter(A: Point, B: Point, C: Point, vertex: Any = None) -> Point:
    """
    Triangle Excenter.
    By default (vertex=None or vertex=A), returns Excenter opposite to A (I_A).
    Specify vertex=B or vertex=C (or "B", "C", or index 1, 2) to get I_B or I_C.
    """
    if vertex is not None:
        idx = 0
        if vertex == A or vertex == "A" or vertex == 0:
            idx = 0
        elif vertex == B or vertex == "B" or vertex == 1:
            idx = 1
        elif vertex == C or vertex == "C" or vertex == 2:
            idx = 2
        if idx == 1:
            return Excenter(B, C, A)
        if idx == 2:
            return Excenter(C, A, B)

    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    denom = -a + b + c
    if denom == 0:
        return A
    return Point(
        (-a * A.x + b * B.x + c * C.x) / denom,
        (-a * A.y + b * B.y + c * C.y) / denom,
    )


@Excenter.set_numpy
def _Excenter_numpy(A, B, C, vertex=None):
    """NumPy"""
    import numpy as np

    if vertex is not None:
        idx = 0
        if vertex == "A" or vertex == 0:
            idx = 0
        elif vertex == "B" or vertex == 1:
            idx = 1
        elif vertex == "C" or vertex == 2:
            idx = 2
        elif vertex is B:
            idx = 1
        elif vertex is C:
            idx = 2

        if idx == 1:
            A, B, C = B, C, A
        elif idx == 2:
            A, B, C = C, A, B

    A = np.asarray(A)
    B = np.asarray(B)
    C = np.asarray(C)
    a = np.linalg.norm(B - C)
    b = np.linalg.norm(C - A)
    c = np.linalg.norm(A - B)

    denom = -a + b + c
    if abs(denom) < 1e-12:
        return A

    return (-a * A + b * B + c * C) / denom


@Excenter.set_mpmath
def _Excenter_mpmath(A, B, C, vertex=None):
    """mpmath"""
    if vertex is not None:
        if vertex == B or vertex == "B" or vertex == 1:
            return _Excenter_mpmath(B, C, A)
        if vertex == C or vertex == "C" or vertex == 2:
            return _Excenter_mpmath(C, A, B)

    a = _mp_point_distance(B, C)
    b = _mp_point_distance(C, A)
    c = _mp_point_distance(A, B)
    denom = -a + b + c
    return Point(
        (-a * A.x + b * B.x + c * C.x) / denom,
        (-a * A.y + b * B.y + c * C.y) / denom,
    )


@geometry_symbol("Excircle", category="triangle")
def Excircle(A: Point, B: Point, C: Point, vertex: Any = None) -> Circle:
    """Triangle Excircle (default opposite to A). Specify vertex=B/C for others."""
    if vertex is not None:
        idx = 0
        if vertex == A or vertex == "A" or vertex == 0:
            idx = 0
        elif vertex == B or vertex == "B" or vertex == 1:
            idx = 1
        elif vertex == C or vertex == "C" or vertex == 2:
            idx = 2

        if idx == 1:
            return Excircle(B, C, A)
        if idx == 2:
            return Excircle(C, A, B)

    center = Excenter(A, B, C)
    x1, y1 = A.x, A.y
    x2, y2 = B.x, B.y
    x3, y3 = C.x, C.y
    double_area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    denom = -a + b + c

    if denom == 0:
        return Circle(center, 0)

    r = double_area / denom
    return Circle(center, r)


@Excircle.set_numpy
def _Excircle_numpy(A, B, C, vertex=None):
    """NumPy"""
    import numpy as np

    if vertex is not None:
        idx = 0
        if vertex == "A" or vertex == 0:
            idx = 0
        elif vertex == "B" or vertex == 1:
            idx = 1
        elif vertex == "C" or vertex == 2:
            idx = 2
        elif vertex is B:
            idx = 1
        elif vertex is C:
            idx = 2

        if idx == 1:
            A, B, C = B, C, A
        elif idx == 2:
            A, B, C = C, A, B

    center = _Excenter_numpy(A, B, C)
    Ax, Ay = A
    Bx, By = B
    Cx, Cy = C
    double_area = abs(Ax * (By - Cy) + Bx * (Cy - Ay) + Cx * (Ay - By))

    a = np.linalg.norm(np.asarray(B) - np.asarray(C))
    b = np.linalg.norm(np.asarray(C) - np.asarray(A))
    c = np.linalg.norm(np.asarray(A) - np.asarray(B))

    denom = -a + b + c
    r = double_area / denom
    return [center[0], center[1], r]


@Excircle.set_mpmath
def _Excircle_mpmath(A, B, C, vertex=None):
    """mpmath"""
    if vertex is not None:
        if vertex == B or vertex == "B" or vertex == 1:
            return _Excircle_mpmath(B, C, A)
        if vertex == C or vertex == "C" or vertex == 2:
            return _Excircle_mpmath(C, A, B)

    center = _Excenter_mpmath(A, B, C)
    x1, y1 = A.x, A.y
    x2, y2 = B.x, B.y
    x3, y3 = C.x, C.y
    double_area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

    a = _mp_point_distance(B, C)
    b = _mp_point_distance(C, A)
    c = _mp_point_distance(A, B)
    denom = -a + b + c

    r = double_area / denom
    return Circle(center, r)
