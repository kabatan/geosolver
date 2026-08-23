"""
Triangle operations module

This module provides functions for constructing triangle centers and related circles.
Implementations are provided for SymPy, NumPy, and mpmath backends.
"""

from typing import Optional, Union, List, Any
from sympy import sqrt, sin, cos, tan, acos, pi
from geosolver.geometry.registry import geometry_symbol
from geosolver.geometry.entities.base import Point, Line, Circle
from geosolver.core.errors import CoincidentPointsError, CollinearPointsError
from geosolver.geometry.operations.triangle_circle_backends import (
    incenter_mpmath_impl,
    incenter_numpy_impl,
    incircle_mpmath_impl,
    incircle_numpy_impl,
    nine_point_circle_mpmath_impl,
    nine_point_circle_numpy_impl,
)
from geosolver.geometry.operations.triangle_excircles import Excenter, Excircle

# =============================================================================
# Triangle Centers
# =============================================================================


def _mp_point_distance(p1: Point, p2: Point):
    from mpmath import sqrt

    return sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

@geometry_symbol("Centroid", category="triangle")
def Centroid(A: Point, B: Point, C: Point) -> Point:
    """Triangle Centroid (G = (A+B+C)/3)"""
    return Point((A.x + B.x + C.x) / 3, (A.y + B.y + C.y) / 3)

@Centroid.set_numpy
def _Centroid_numpy(A, B, C):
    """NumPy"""
    import numpy as np
    A = np.asarray(A)
    B = np.asarray(B)
    C = np.asarray(C)
    return (A + B + C) / 3.0

@Centroid.set_mpmath
def _Centroid_mpmath(A, B, C):
    """mpmath"""
    return Point((A.x + B.x + C.x) / 3, (A.y + B.y + C.y) / 3)


@geometry_symbol("Circumcenter", category="triangle")
def Circumcenter(A: Point, B: Point, C: Point) -> Optional[Point]:
    """Triangle Circumcenter (Intersection of perpendicular bisectors)"""
    # Reuse CircleThroughThreePoints logic or re-implement
    # Avoiding circular imports, we can use the formula directly
    x1, y1 = A.x, A.y
    x2, y2 = B.x, B.y
    x3, y3 = C.x, C.y
    
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if D == 0:
        return None
        
    Ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / D
    Uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / D
    return Point(Ux, Uy)

def _circumcenter_numpy_impl(A, B, C):
    """NumPy implementation for Circumcenter (internal)"""
    import numpy as np
    x1, y1 = A
    x2, y2 = B
    x3, y3 = C
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    
    # Smooth regularization: D_reg = D / (1 + |D|/eps) * (1 + eps/|D|)
    # This keeps D_reg ≈ D for large |D|, but smoothly approaches ±eps for small |D|
    eps = 1e-10
    D_sign = 1.0 if D >= 0 else -1.0
    D_abs = abs(D)
    # Smooth regularization: avoids 1/0 while preserving gradient
    D_reg = D_sign * (D_abs + eps)
    
    Ux_num = (x1*x1 + y1*y1) * (y2 - y3) + (x2*x2 + y2*y2) * (y3 - y1) + (x3*x3 + y3*y3) * (y1 - y2)
    Uy_num = (x1*x1 + y1*y1) * (x3 - x2) + (x2*x2 + y2*y2) * (x1 - x3) + (x3*x3 + y3*y3) * (x2 - x1)
    
    Ux = Ux_num / D_reg
    Uy = Uy_num / D_reg
    
    # Smooth soft-capping using tanh to preserve differentiability
    # Maps [-inf, inf] -> [-max_coord, max_coord] smoothly
    max_coord = 1e6
    Ux = max_coord * np.tanh(Ux / max_coord)
    Uy = max_coord * np.tanh(Uy / max_coord)
    
    return [Ux, Uy]

@Circumcenter.set_numpy
def _Circumcenter_numpy(A, B, C):
    """NumPy - Smooth and differentiable for all configurations"""
    return _circumcenter_numpy_impl(A, B, C)

@Circumcenter.set_mpmath
def _Circumcenter_mpmath(A, B, C):
    """mpmath - Smooth and differentiable for all configurations"""
    from mpmath import mpf, tanh
    x1, y1 = A.x, A.y
    x2, y2 = B.x, B.y
    x3, y3 = C.x, C.y
    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    
    # Smooth regularization: D_reg = D + eps * sign(D)
    eps = mpf('1e-10')
    D_sign = 1 if D >= 0 else -1
    D_abs = abs(D)
    D_reg = D_sign * (D_abs + eps)
    
    Ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / D_reg
    Uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / D_reg
    
    # Smooth soft-capping using tanh
    max_coord = mpf('1e6')
    Ux = max_coord * tanh(Ux / max_coord)
    Uy = max_coord * tanh(Uy / max_coord)
    
    return Point(Ux, Uy)


@geometry_symbol("Orthocenter", category="triangle")
def Orthocenter(A: Point, B: Point, C: Point) -> Optional[Point]:
    """Triangle Orthocenter (Intersection of altitudes)"""
    # H = A + B + C - 2*O (Euler line property: OH = 3OG, H = 3G - 2O = A+B+C - 2O)
    # This is efficient if we have O.
    
    # Alternatively, intersection of altitudes.
    # Slope BC: m_BC = (y3-y2)/(x3-x2)
    # Altitude from A has slope -1/m_BC.
    
    # Using vector formula:
    # ax + by + c = 0 for altitude from A.
    # Normal is vector BC: (x3-x2, y3-y2)
    # So: (x3-x2)x + (y3-y2)y = (x3-x2)x1 + (y3-y2)y1
    
    # Altitude A: (x3-x2)x + (y3-y2)y = k1
    # Altitude B: (x1-x3)x + (y1-y3)y = k2
    
    dx_bc = C.x - B.x
    dy_bc = C.y - B.y
    k1 = dx_bc * A.x + dy_bc * A.y
    
    dx_ca = A.x - C.x
    dy_ca = A.y - C.y
    k2 = dx_ca * B.x + dy_ca * B.y
    
    # Solve linear system:
    # dx_bc * x + dy_bc * y = k1
    # dx_ca * x + dy_ca * y = k2
    
    det = dx_bc * dy_ca - dx_ca * dy_bc
    if det == 0:
        return None # Collinear
        
    x = (k1 * dy_ca - k2 * dy_bc) / det
    y = (dx_bc * k2 - dx_ca * k1) / det
    
    return Point(x, y)

@Orthocenter.set_numpy
def _Orthocenter_numpy(A, B, C):
    """NumPy"""
    dx_bc = C[0] - B[0]
    dy_bc = C[1] - B[1]
    k1 = dx_bc * A[0] + dy_bc * A[1]
    
    dx_ca = A[0] - C[0]
    dy_ca = A[1] - C[1]
    k2 = dx_ca * B[0] + dy_ca * B[1]
    
    det = dx_bc * dy_ca - dx_ca * dy_bc
    if abs(det) < 1e-12:
        return None
        
    x = (k1 * dy_ca - k2 * dy_bc) / det
    y = (dx_bc * k2 - dx_ca * k1) / det
    return [x, y]


@Orthocenter.set_mpmath
def _Orthocenter_mpmath(A, B, C):
    """mpmath"""
    dx_bc = C.x - B.x
    dy_bc = C.y - B.y
    k1 = dx_bc * A.x + dy_bc * A.y
    dx_ca = A.x - C.x
    dy_ca = A.y - C.y
    k2 = dx_ca * B.x + dy_ca * B.y
    det = dx_bc * dy_ca - dx_ca * dy_bc
    if abs(det) < 1e-20:
        return None
    x = (k1 * dy_ca - k2 * dy_bc) / det
    y = (dx_bc * k2 - dx_ca * k1) / det
    return Point(x, y)


@geometry_symbol("Incenter", category="triangle")
def Incenter(A: Point, B: Point, C: Point) -> Point:
    """Triangle Incenter"""
    # I = (aA + bB + cC) / (a + b + c)
    # where a, b, c are side lengths BC, CA, AB
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    
    perimeter = a + b + c
    if perimeter == 0:
        return A # Degenerate
        
    return Point(
        (a * A.x + b * B.x + c * C.x) / perimeter,
        (a * A.y + b * B.y + c * C.y) / perimeter
    )

@Incenter.set_numpy
def _Incenter_numpy(A, B, C):
    """NumPy"""
    return incenter_numpy_impl(A, B, C)

@Incenter.set_mpmath
def _Incenter_mpmath(A, B, C):
    """mpmath"""
    return incenter_mpmath_impl(
        A,
        B,
        C,
        point_class=Point,
        distance_fn=_mp_point_distance,
    )


# =============================================================================
# Triangle Circles
# =============================================================================

@geometry_symbol("Incircle", category="triangle")
def Incircle(A: Point, B: Point, C: Point) -> Circle:
    """Triangle Incircle"""
    center = Incenter(A, B, C)
    # radius is Area / s, or distance from I to any side
    # Area = 0.5 * |(xB-xA)(yC-yA) - (xC-xA)(yB-yA)|
    # s = (a+b+c)/2
    
    # Distance from center to Line AB
    # Area of Triangle AIB = 0.5 * c * r ? Yes.
    # Total Area = 0.5 * p * r -> r = 2 * Area / p
    
    x1, y1 = A.x, A.y
    x2, y2 = B.x, B.y
    x3, y3 = C.x, C.y
    
    double_area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    perimeter = a + b + c
    
    if perimeter == 0:
        return Circle(center, 0)
        
    r = double_area / perimeter
    return Circle(center, r)

@Incircle.set_numpy
def _Incircle_numpy(A, B, C):
    """NumPy"""
    return incircle_numpy_impl(A, B, C, incenter_numpy_fn=_Incenter_numpy)

@Incircle.set_mpmath
def _Incircle_mpmath(A, B, C):
    """mpmath"""
    return incircle_mpmath_impl(
        A,
        B,
        C,
        incenter_mpmath_fn=_Incenter_mpmath,
        circle_class=Circle,
        distance_fn=_mp_point_distance,
    )

@geometry_symbol("NinePointCircle", category="triangle")
def NinePointCircle(A: Point, B: Point, C: Point) -> Optional[Circle]:
    """Nine Point Circle (Feuerbach Circle)"""
    # Center N is midpoint of OH.
    # Radius R/2 (where R is circumradius).
    
    O = Circumcenter(A, B, C)
    H = Orthocenter(A, B, C)
    
    if O is None or H is None:
        return None
        
    center = Point((O.x + H.x)/2, (O.y + H.y)/2)
    
    # Circumradius
    R = O.distance_to(A)
    return Circle(center, R/2)

@NinePointCircle.set_numpy
def _NinePointCircle_numpy(A, B, C):
    """NumPy"""
    return nine_point_circle_numpy_impl(
        A,
        B,
        C,
        circumcenter_numpy_fn=_Circumcenter_numpy,
        orthocenter_numpy_fn=_Orthocenter_numpy,
    )

@NinePointCircle.set_mpmath
def _NinePointCircle_mpmath(A, B, C):
    """mpmath"""
    return nine_point_circle_mpmath_impl(
        A,
        B,
        C,
        circumcenter_mpmath_fn=_Circumcenter_mpmath,
        orthocenter_mpmath_fn=_Orthocenter_mpmath,
        point_class=Point,
        circle_class=Circle,
    )


@geometry_symbol("IncircleContactPoint", category="triangle")
def IncircleContactPoint(A: Point, B: Point, C: Point, side: Optional[Any] = None) -> Union[Point, List[Point]]:
    """
    内接円の接点を計算
    
    Args:
        A, B, C: 三角形の頂点
        side: 対象とする辺 (Point, "AB", "BC", "CA", 0, 1, 2)
              None の場合は3つの接点のリスト [BC, CA, AB] を返す
              
    Returns:
        Point または List[Point]
    """
    # s = (a+b+c)/2
    a = B.distance_to(C)
    b = C.distance_to(A)
    c = A.distance_to(B)
    s = (a + b + c) / 2
    
    # BC上の接点 D: 点Bから (s-b) の距離
    # D = B + (C-B) * ((s-b)/a)
    D = B + (C - B) * ((s - b) / a)
    
    # CA上の接点 E: 点Cから (s-c) の距離
    E = C + (A - C) * ((s - c) / b)
    
    # AB上の接点 F: 点Aから (s-a) の距離
    F = A + (B - A) * ((s - a) / c)
    
    if side is None:
        return [D, E, F]
    
    # side 判定 (簡易)
    if side == "BC" or side == 0 or side == A:
        return D
    if side == "CA" or side == 1 or side == B:
        return E
    if side == "AB" or side == 2 or side == C:
        return F
    
    return [D, E, F]

# Alias
IncircleContactPoints = IncircleContactPoint

@IncircleContactPoint.set_numpy
def _IncircleContactPoint_numpy(A, B, C, side=None):
    """NumPy"""
    import numpy as np
    A = np.asarray(A)
    B = np.asarray(B)
    C = np.asarray(C)
    
    a = np.linalg.norm(B - C)
    b = np.linalg.norm(C - A)
    c = np.linalg.norm(A - B)
    s = (a + b + c) / 2
    
    D = B + (C - B) * ((s - b) / a)
    E = C + (A - C) * ((s - c) / b)
    F = A + (B - A) * ((s - a) / c)
    
    if side is None:
        return [D, E, F]
    # ... side 判定は numpy 用に簡略化が必要だが、通常 side=None で使われる
    return [D, E, F]

@IncircleContactPoint.set_mpmath
def _IncircleContactPoint_mpmath(A, B, C, side=None):
    """mpmath"""
    from geosolver.geometry.mp.mp_api import MP_IncircleContactPoint
    return MP_IncircleContactPoint(A, B, C, side)

from geosolver.geometry.operations.triangle_circumcircle import (
    Circumcircle,
    _Circumcircle_numpy,
    _Circumcircle_mpmath,
)

from geosolver.geometry.operations.triangle_centers import (
    TriangleCenter,
    NinePointCenter,
    SymmedianPoint,
    GergonnePoint,
    NagelPoint,
    Mittenpunkt,
    SpiekerCenter,
    FeuerbachPoint,
    FermatPoint,
    IsodynamicPoint,
)
