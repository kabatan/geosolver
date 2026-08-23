"""Extracted geometry wrapper functions for mp_api."""

from __future__ import annotations

from mpmath import mpf

from geosolver._internal.solver.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf
from .mp_api_geometry_centers import (
    MP_FeuerbachPoint,
    MP_FermatPoint,
    MP_FirstFermatPoint,
    MP_FirstIsodynamicPoint,
    MP_GergonnePoint,
    MP_IsodynamicPoint,
    MP_MittenPunkt,
    MP_NagelPoint,
    MP_SecondFermatPoint,
    MP_SecondIsodynamicPoint,
    MP_SpiekerCenter,
    MP_SymmedianPoint,
)

from .mp_impl import (
    MPArc,
    MPCircle,
    MPLine,
    MPPoint,
    MPSegment,
    mp_angle_between_lines,
    mp_angle_bisector,
    mp_are_concyclic,
    mp_centroid,
    mp_circumcenter,
    mp_circumcircle,
    mp_circumference,
    mp_closest_point,
    mp_evalf,
    mp_excenter,
    mp_excircle,
    mp_incenter,
    mp_incircle_contact_point,
    mp_is_integer,
    mp_is_prime,
    mp_length,
    mp_middle_point_on_line,
    mp_nine_point_center,
    mp_nine_point_circle,
    mp_orthic_triangle,
    mp_orthocenter,
    mp_perpendicular_bisector,
    mp_point_on_arc,
    mp_point_on_circle,
    mp_point_on_line,
    mp_power_of_point,
    mp_radical_axis,
    mp_radius,
    mp_ray,
    mp_reflect,
    mp_rotate,
    mp_segment,
    mp_slope,
    mp_tangent_line,
    mp_triangle_area,
    mp_triangle_center,
    mp_triangle_type,
    mp_vector,
)
from .mp_polygon_checks import (
    mp_has_self_intersection,
    mp_is_convex,
    mp_polygon_area,
)


def _to_mpf(value):
    if isinstance(value, mpf):
        return value
    try:
        return strict_to_mpf(value, context="geometry.mp_api_geometry")
    except HighPrecisionContaminationError:
        raise
    except Exception as exc:
        raise TypeError(
            f"Unsupported high precision numeric value in geometry.mp_api_geometry: {value!r}"
        ) from exc


def MP_Centroid(A, B, C):
    return mp_centroid(A, B, C)


def MP_Circumcenter(A, B, C):
    return mp_circumcenter(A, B, C)


def MP_Incenter(A, B, C):
    return mp_incenter(A, B, C)


def MP_Orthocenter(A, B, C):
    return mp_orthocenter(A, B, C)


def MP_Segment(p1, p2):
    return mp_segment(p1, p2)


def MP_Ray(start, through):
    return mp_ray(start, through)


def MP_Vector(A, B):
    return mp_vector(A, B)


def MP_ClosestPoint(point, line):
    return mp_closest_point(point, line)


def MP_Rotate(point, angle, center=None):
    """Rotate using the public ``Rotate(point, angle, center)`` signature.

    Older internal callers used ``(point, center, angle)``.  Accept that
    ordering as well while making the public ordering the canonical one.
    """
    if isinstance(angle, MPPoint):
        # Backward compatibility for the former internal ordering.
        legacy_center = angle
        angle, center = center, legacy_center
    if center is None:
        center = MPPoint(0, 0)
    if not isinstance(center, MPPoint):
        raise TypeError("Rotate center must be an MPPoint")
    return mp_rotate(point, center, angle)


def MP_Reflect(point, mirror):
    return mp_reflect(point, mirror)


def MP_AreConcyclic(A, B, C, D):
    return mp_are_concyclic(A, B, C, D)


def MP_Slope(line):
    return mp_slope(line)


def MP_Length(segment):
    return mp_length(segment)


def MP_Radius(circle):
    return mp_radius(circle)


def MP_Circumference(circle):
    return mp_circumference(circle)


def MP_NinePointCenter(A, B, C):
    return mp_nine_point_center(A, B, C)


def MP_NinePointCircle(A, B, C):
    return mp_nine_point_circle(A, B, C)


def MP_Excircle(A, B, C, vertex="A"):
    return mp_excircle(A, B, C, vertex)


def MP_Excenter(A, B, C, vertex="A"):
    return mp_excenter(A, B, C, vertex)


def MP_PerpendicularBisector(A, B):
    return mp_perpendicular_bisector(A, B)


def MP_AngleBisector(A, B, C):
    return mp_angle_bisector(A, B, C)


def _select_tangent_line(lines, use_first=True):
    """Match the high-level Tangent API, which returns one line."""
    if lines is None:
        return None
    if isinstance(lines, (list, tuple)):
        if not lines:
            return None
        return lines[0] if use_first else lines[-1]
    return lines


def _normalize_point_circle_args(arg1, arg2, operation):
    """Normalize public ``(point, circle)`` and legacy ``(circle, point)``."""
    if isinstance(arg1, MPCircle) and isinstance(arg2, MPPoint):
        return arg2, arg1
    if isinstance(arg1, MPPoint) and isinstance(arg2, MPCircle):
        return arg1, arg2
    raise TypeError(f"{operation} expects a point and a circle")


def MP_TangentLine(arg1, arg2, use_first=True):
    # ``TangentLine`` is a public alias of ``Tangent(point, circle)`` while
    # the historical low-level helper used ``(circle, point)``.  Accept both
    # orders at the boundary.
    point, circle = _normalize_point_circle_args(arg1, arg2, "TangentLine")
    return _select_tangent_line(mp_tangent_line(circle, point), use_first)


def MP_RadicalAxis(c1, c2):
    return mp_radical_axis(c1, c2)


def MP_PowerOfPoint(point, circle):
    return mp_power_of_point(point, circle)


def MP_Circle(*args):
    if len(args) == 2 and isinstance(args[0], MPPoint):
        return MPCircle(args[0], _to_mpf(args[1]))
    if len(args) == 3 and all(isinstance(a, MPPoint) for a in args):
        return mp_circumcircle(args[0], args[1], args[2])
    raise TypeError("Circle expects (center, radius) or (A, B, C)")


def MP_TriangleArea(A, B, C):
    return mp_triangle_area(A, B, C)


def MP_TriangleType(A, B, C):
    return mp_triangle_type(A, B, C)


def MP_evalf(value, precision=15):
    return mp_evalf(value, precision)


def MP_PointOnLine(line, t):
    return mp_point_on_line(line, t)


def MP_PointOnCircle(circle, t):
    return mp_point_on_circle(circle, t)


def MP_PointOnArc(arc_or_circle, start=None, end=None, t=None, including=None, excluding=None):
    if isinstance(arc_or_circle, MPArc):
        arc = arc_or_circle
        if start is not None and not isinstance(start, MPPoint):
            t = start
        return mp_point_on_arc(arc.circle, arc.start, arc.end, t)
    if isinstance(arc_or_circle, MPCircle):
        return mp_point_on_arc(arc_or_circle, start, end, t, including, excluding)
    raise TypeError("Expected MPArc or MPCircle")


def MP_MiddlePointOnLine(line, P, d):
    return mp_middle_point_on_line(line, P, d)


def MP_MiddlePoint(A, B, C):
    dAB = A.distance_to(B)
    dBC = B.distance_to(C)
    dCA = C.distance_to(A)
    if dAB >= dBC and dAB >= dCA:
        return C
    if dBC >= dAB and dBC >= dCA:
        return A
    return B


def MP_OrthicTriangle(A, B, C):
    return mp_orthic_triangle(A, B, C)


def MP_Center(obj):
    if isinstance(obj, MPCircle):
        return obj.center
    if isinstance(obj, MPArc):
        return obj.circle.center
    raise TypeError("Expected MPCircle or MPArc")


def MP_Tangent(arg1, arg2, use_first=True):
    """Return one tangent line for either public or legacy argument order."""
    point, circle = _normalize_point_circle_args(arg1, arg2, "Tangent")
    return _select_tangent_line(mp_tangent_line(circle, point), use_first)


def MP_Perpendicular(line1, line2):
    if not (isinstance(line1, MPLine) and isinstance(line2, MPLine)):
        raise TypeError("Perpendicular requires two Lines (MPLine, MPLine)")
    return line1.a * line2.a + line1.b * line2.b


def MP_Parallel(line1, line2):
    if not (isinstance(line1, MPLine) and isinstance(line2, MPLine)):
        raise TypeError("Parallel requires two Lines (MPLine, MPLine)")
    return line1.a * line2.b - line2.a * line1.b


def MP_Polar(point, circle):
    center = circle.center
    r = circle.radius
    dx = point.x - center.x
    dy = point.y - center.y
    d2 = dx * dx + dy * dy
    if d2 == 0:
        raise ValueError("Point cannot be at center of circle")
    k = r * r / d2
    inv_x = center.x + k * dx
    inv_y = center.y + k * dy
    return MPLine(-dy, dx, dy * inv_x - dx * inv_y)


def MP_Pole(line, circle):
    center = circle.center
    r = circle.radius
    foot = mp_closest_point(center, line)
    dx = foot.x - center.x
    dy = foot.y - center.y
    d2 = dx * dx + dy * dy
    if d2 == 0:
        raise ValueError("Line passes through center, pole is at infinity")
    k = r * r / d2
    return MPPoint(center.x + k * dx, center.y + k * dy)


def MP_Power(point, circle):
    return mp_power_of_point(point, circle)


def MP_HomotetyCenter(circle1, circle2, is_external=None, internal=None):
    if internal is not None:
        is_external = not internal
    if is_external is None:
        is_external = True
    c1, c2 = circle1.center, circle2.center
    r1, r2 = circle1.radius, circle2.radius
    if r1 == r2 and is_external:
        raise ValueError("External homothety center is at infinity for equal radii")
    if is_external:
        denom = r1 - r2
        x = (r1 * c2.x - r2 * c1.x) / denom
        y = (r1 * c2.y - r2 * c1.y) / denom
    else:
        denom = r1 + r2
        x = (r1 * c2.x + r2 * c1.x) / denom
        y = (r1 * c2.y + r2 * c1.y) / denom
    return MPPoint(x, y)


def MP_IncircleContactPoints(A, B, C):
    points = mp_incircle_contact_point(A, B, C, None)
    D, E, F = points
    return (D, E, F)


def MP_IsConvex(*points):
    return mp_is_convex(*points)


def MP_HasSelfIntersection(*points):
    return mp_has_self_intersection(*points)


def MP_PolygonArea(*points):
    return mp_polygon_area(*points)


def MP_InTouch(A, B, C):
    return MP_IncircleContactPoints(A, B, C)


def MP_Polygon(*points):
    # Match the public Polygon constructor, which accepts a single sequence of
    # vertices, while retaining the historical variadic MP spelling.  Without
    # this normalization ``Polygon([A, B, C])`` becomes ``([A, B, C],)`` and
    # geometry guards see the whole vertex list as one point.
    if len(points) == 1 and isinstance(points[0], (list, tuple)):
        points = tuple(points[0])
    return tuple(points)


def MP_Quadrilateral(A, B, C, D):
    return (A, B, C, D)


def MP_IsInteger(x):
    return mp_is_integer(x)


def MP_IsPrime(x):
    return mp_is_prime(x)


__all__ = [
    "MP_AngleBisector",
    "MP_AreConcyclic",
    "MP_Center",
    "MP_Centroid",
    "MP_Circle",
    "MP_Circumcenter",
    "MP_Circumference",
    "MP_ClosestPoint",
    "MP_Excenter",
    "MP_Excircle",
    "MP_FeuerbachPoint",
    "MP_FermatPoint",
    "MP_FirstFermatPoint",
    "MP_FirstIsodynamicPoint",
    "MP_GergonnePoint",
    "MP_HasSelfIntersection",
    "MP_HomotetyCenter",
    "MP_IncircleContactPoints",
    "MP_InTouch",
    "MP_Incenter",
    "MP_IsConvex",
    "MP_IsInteger",
    "MP_IsodynamicPoint",
    "MP_IsPrime",
    "MP_Length",
    "MP_MiddlePoint",
    "MP_MiddlePointOnLine",
    "MP_MittenPunkt",
    "MP_NagelPoint",
    "MP_NinePointCenter",
    "MP_NinePointCircle",
    "MP_OrthicTriangle",
    "MP_Orthocenter",
    "MP_Parallel",
    "MP_PerpendicularBisector",
    "MP_Perpendicular",
    "MP_PointOnArc",
    "MP_PointOnCircle",
    "MP_PointOnLine",
    "MP_Polar",
    "MP_Pole",
    "MP_Polygon",
    "MP_PolygonArea",
    "MP_Power",
    "MP_PowerOfPoint",
    "MP_Quadrilateral",
    "MP_RadicalAxis",
    "MP_Radius",
    "MP_Ray",
    "MP_Reflect",
    "MP_Rotate",
    "MP_SecondFermatPoint",
    "MP_SecondIsodynamicPoint",
    "MP_Segment",
    "MP_Slope",
    "MP_SpiekerCenter",
    "MP_SymmedianPoint",
    "MP_Tangent",
    "MP_TangentLine",
    "MP_TriangleArea",
    "MP_TriangleType",
    "MP_Vector",
    "MP_evalf",
]
