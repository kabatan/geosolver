"""
Advanced Geometry Operations

Implements Polar, Pole, Power, RadicalAxis, etc.
"""

from typing import Optional, Union, Any, List
from geosolver.geometry.registry import geometry_symbol
from geosolver.geometry.entities.base import Point, Line, Circle
from geosolver.core.errors import CoincidentPointsError
from geosolver.geometry.operations.advanced_helpers import (
    compute_polar_coeffs,
    compute_pole_point,
    compute_radical_axis_coeffs,
)

# =============================================================================
# Power of Point
# =============================================================================

@geometry_symbol("PowerOfPoint", category="advanced")
def PowerOfPoint(point: Point, circle: Circle) -> Any:
    """Circle power of a point P w.r.t circle C: dist(P, C)^2 - r^2"""
    d2 = (point.x - circle.center.x)**2 + (point.y - circle.center.y)**2
    return d2 - circle.radius**2

@PowerOfPoint.set_numpy
def _PowerOfPoint_numpy(point, circle):
    """NumPy"""
    import numpy as np
    cx, cy, r = circle
    px, py = point
    d2 = (px - cx)**2 + (py - cy)**2
    return d2 - r**2

@PowerOfPoint.set_mpmath
def _PowerOfPoint_mpmath(point, circle):
    """mpmath"""
    d2 = (point.x - circle.center.x)**2 + (point.y - circle.center.y)**2
    return d2 - circle.radius**2


# =============================================================================
# Polar Line
# =============================================================================

@geometry_symbol("Polar", category="advanced")
def Polar(point: Point, circle: Circle) -> Line:
    """Polar line of point P w.r.t. circle C"""
    # Formula: (x0-a)(x-a) + (y0-b)(y-b) = r^2
    # x(x0-a) - a(x0-a) + y(y0-b) - b(y0-b) - r^2 = 0
    # Coeffs:
    # A = x0 - a
    # B = y0 - b
    # C = -a(x0 - a) - b(y0 - b) - r^2
    #   = -a*A - b*B - r^2
    
    cx, cy = circle.center.x, circle.center.y
    r = circle.radius
    px, py = point.x, point.y
    
    A, B, C = compute_polar_coeffs(cx, cy, r, px, py)
    
    return Line(A, B, C)

@Polar.set_numpy
def _Polar_numpy(point, circle):
    """NumPy"""
    import numpy as np
    cx, cy, r = circle
    px, py = point
    
    A, B, C = compute_polar_coeffs(cx, cy, r, px, py)
    return [A, B, C]

@Polar.set_mpmath
def _Polar_mpmath(point, circle):
    """mpmath"""
    cx, cy = circle.center.x, circle.center.y
    r = circle.radius
    px, py = point.x, point.y
    
    A, B, C = compute_polar_coeffs(cx, cy, r, px, py)
    return Line(A, B, C)


# =============================================================================
# Pole Point
# =============================================================================

@geometry_symbol("Pole", category="advanced")
def Pole(line: Line, circle: Circle) -> Optional[Point]:
    """Pole point of line L w.r.t. circle C"""
    # Formula derived:
    # k = -r^2 / (L*xc + M*yc + N)
    # P = C + k * (L, M)
    
    L, M, N = line.a, line.b, line.c
    xc, yc = circle.center.x, circle.center.y
    r = circle.radius
    
    pole_point = compute_pole_point(L, M, N, xc, yc, r, 0)
    if pole_point is None:
        return None
    return Point(pole_point[0], pole_point[1])

@Pole.set_numpy
def _Pole_numpy(line, circle):
    """NumPy"""
    import numpy as np
    L, M, N = line
    xc, yc, r = circle
    
    pole_point = compute_pole_point(L, M, N, xc, yc, r, 1e-12)
    if pole_point is None:
        return None
    return [pole_point[0], pole_point[1]]

@Pole.set_mpmath
def _Pole_mpmath(line, circle):
    """mpmath"""
    L, M, N = line.a, line.b, line.c
    xc, yc = circle.center.x, circle.center.y
    r = circle.radius
    
    pole_point = compute_pole_point(L, M, N, xc, yc, r, 1e-20)
    if pole_point is None:
        return None
    return Point(pole_point[0], pole_point[1])


# =============================================================================
# Radical Axis
# =============================================================================

@geometry_symbol("RadicalAxis", category="advanced")
def RadicalAxis(circ1: Circle, circ2: Circle) -> Optional[Line]:
    """Radical Axis of two circles"""
    # 2(x2 - x1)x + 2(y2 - y1)y + (x1^2 + y1^2 - r1^2 - x2^2 - y2^2 + r2^2) = 0
    x1, y1 = circ1.center.x, circ1.center.y
    r1 = circ1.radius
    x2, y2 = circ2.center.x, circ2.center.y
    r2 = circ2.radius
    
    A, B, C = compute_radical_axis_coeffs(x1, y1, r1, x2, y2, r2)
    
    if A == 0 and B == 0:
        return None # Concentric circles have no radical axis

    return Line(A, B, C)

@RadicalAxis.set_numpy
def _RadicalAxis_numpy(circ1, circ2):
    """NumPy"""
    import numpy as np
    x1, y1, r1 = circ1
    x2, y2, r2 = circ2
    
    A, B, C = compute_radical_axis_coeffs(x1, y1, r1, x2, y2, r2)
    
    if abs(A) < 1e-12 and abs(B) < 1e-12:
        return None

    return [A, B, C]

@RadicalAxis.set_mpmath
def _RadicalAxis_mpmath(circ1, circ2):
    """mpmath"""
    x1, y1 = circ1.center.x, circ1.center.y
    r1 = circ1.radius
    x2, y2 = circ2.center.x, circ2.center.y
    r2 = circ2.radius
    
    A, B, C = compute_radical_axis_coeffs(x1, y1, r1, x2, y2, r2)
    
    if abs(A) < 1e-20 and abs(B) < 1e-20:
        return None

    return Line(A, B, C)
