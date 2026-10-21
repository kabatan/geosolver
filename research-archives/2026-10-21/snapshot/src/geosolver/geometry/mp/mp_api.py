"""High-precision geometry functions exposed to the DSL context."""

from mpmath import mp, mpf

from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf

from .mp_api_common_wrappers import (
    MP_N,
    MP_Circumcircle,
    MP_Distance,
    MP_Incircle,
    MP_IncircleContactPoint,
    MP_Intersect,
    MP_Midpoint,
    MP_ParallelLine,
    MP_PerpendicularLine,
    MP_Require,
    MP_TriangleCenter,
    _mp_sqdist,
)
from .mp_api_geometry import (
    MP_AngleBisector,
    MP_AreConcyclic,
    MP_Center,
    MP_Centroid,
    MP_Circle,
    MP_Circumcenter,
    MP_Circumference,
    MP_ClosestPoint,
    MP_Excenter,
    MP_Excircle,
    MP_FermatPoint,
    MP_FeuerbachPoint,
    MP_FirstFermatPoint,
    MP_FirstIsodynamicPoint,
    MP_GergonnePoint,
    MP_HasSelfIntersection,
    MP_HomotetyCenter,
    MP_Incenter,
    MP_IncircleContactPoints,
    MP_InTouch,
    MP_IsConvex,
    MP_IsInteger,
    MP_IsodynamicPoint,
    MP_IsPrime,
    MP_Length,
    MP_MiddlePoint,
    MP_MiddlePointOnLine,
    MP_MittenPunkt,
    MP_NagelPoint,
    MP_NinePointCenter,
    MP_NinePointCircle,
    MP_OrthicTriangle,
    MP_Orthocenter,
    MP_Parallel,
    MP_Perpendicular,
    MP_PerpendicularBisector,
    MP_PointOnArc,
    MP_PointOnCircle,
    MP_PointOnLine,
    MP_Polar,
    MP_Pole,
    MP_Polygon,
    MP_PolygonArea,
    MP_Power,
    MP_PowerOfPoint,
    MP_Quadrilateral,
    MP_RadicalAxis,
    MP_Radius,
    MP_Ray,
    MP_Reflect,
    MP_Rotate,
    MP_SecondFermatPoint,
    MP_SecondIsodynamicPoint,
    MP_Segment,
    MP_Slope,
    MP_SpiekerCenter,
    MP_SymmedianPoint,
    MP_Tangent,
    MP_TangentLine,
    MP_TriangleArea,
    MP_TriangleType,
    MP_Vector,
)
from .mp_api_measurements import (
    MP_Angle,
    MP_Arc,
    MP_Area,
    MP_evalf,
    MP_InscribedPolygonVertices,
    MP_IsAcuteTriangle,
    MP_IsObtuseTriangle,
    MP_IsRightTriangle,
    MP_ParallelismMeasure,
    MP_Perimeter,
    MP_PointFactory,
    MP_PointOnSegment,
)
from .mp_impl import (
    MPArc,
    MPCircle,
    MPLine,
    MPPoint,
    mp_line_through_two_points,
)


def _to_mpf(value):
    if isinstance(value, mpf):
        return value
    try:
        return strict_to_mpf(value, context="geometry.mp_api")
    except HighPrecisionContaminationError:
        raise
    except Exception as exc:
        raise TypeError(
            f"Unsupported high precision numeric value in geometry.mp_api: {value!r}"
        ) from exc


def MP_Point(x, y):
    return MPPoint(_to_mpf(x), _to_mpf(y))


def MP_Line(*args):
    if len(args) == 2 and isinstance(args[0], MPPoint) and isinstance(args[1], MPPoint):
        line = mp_line_through_two_points(args[0], args[1])
        if line is None:
            raise ValueError("Cannot create line from identical points")
        return line
    # The public geometry API also permits a line in coefficient form
    # ``Line(a, b, c)`` for ``a*x + b*y + c = 0``.  Keep this conversion at
    # the high-precision boundary so DSL expressions do not need a separate
    # coordinate-only workaround.
    if len(args) == 3:
        a, b, c = (_to_mpf(value) for value in args)
        if a == 0 and b == 0:
            raise ValueError("Cannot create a line with zero coefficients")
        return MPLine(a, b, c)
    if len(args) == 1 and isinstance(args[0], MPLine):
        return args[0]
    raise TypeError(
        "Line expects two MPPoint objects, one MPLine, or three numeric coefficients. "
        f"Got: {[type(a) for a in args]}"
    )


def MP_OnLine(
    point: MPPoint,
    obj1: MPLine | MPPoint,
    obj2: MPPoint | None = None,
    ordered: bool = False,
) -> mpf:
    if not isinstance(point, MPPoint):
        raise TypeError("First argument must be a Point")

    if isinstance(obj1, MPLine) and obj2 is None:
        return obj1.distance_to_point(point)

    if isinstance(obj1, MPPoint) and isinstance(obj2, MPPoint):
        v1 = obj1 - point
        v2 = obj2 - point
        collinear_residual = v1.cross(v2)
        if ordered:
            order_residual = (
                point.distance_to(obj1) + obj1.distance_to(obj2) - point.distance_to(obj2)
            )
            return collinear_residual**2 + order_residual**2
        return collinear_residual

    raise TypeError("Invalid arguments for OnLine")


def MP_OnCircle(point: MPPoint, circle: MPCircle) -> mpf:
    if not isinstance(point, MPPoint):
        raise TypeError("First argument must be a Point")
    if not isinstance(circle, MPCircle):
        raise TypeError("Second argument must be a Circle")
    return point.distance_to(circle.center) - circle.radius


def _as_tangent_circle_mp(obj: object) -> MPCircle | None:
    if isinstance(obj, MPCircle):
        return obj
    if isinstance(obj, MPArc):
        return obj.circle
    return None


def MP_OnSegment(point: MPPoint, start: MPPoint, end: MPPoint) -> mpf:
    if not isinstance(point, MPPoint):
        raise TypeError("First argument must be a Point")
    if not isinstance(start, MPPoint) or not isinstance(end, MPPoint):
        raise TypeError("OnSegment requires three Points")
    return start.distance_to(point) + point.distance_to(end) - start.distance_to(end)


def MP_Collinear(point1: MPPoint, point2: MPPoint, point3: MPPoint, ordered: bool = False) -> mpf:
    return MP_OnLine(point1, point2, point3, ordered=ordered)


def MP_FootOfPerpendicular(arg1: object, arg2: object) -> MPPoint:
    if isinstance(arg1, MPLine) and isinstance(arg2, MPPoint):
        line, point = arg1, arg2
    elif isinstance(arg1, MPPoint) and isinstance(arg2, MPLine):
        point, line = arg1, arg2
    else:
        raise TypeError("FootOfPerpendicular expects (MPPoint, MPLine) or (MPLine, MPPoint)")

    a, b, c = line.a, line.b, line.c
    x0, y0 = point.x, point.y
    denom = a**2 + b**2

    x = (b * (b * x0 - a * y0) - a * c) / denom
    y = (a * (-b * x0 + a * y0) - b * c) / denom

    return MPPoint(x, y)


def MP_IsTangent(obj1: object, obj2: object) -> mpf:
    if isinstance(obj1, MPLine):
        circle = _as_tangent_circle_mp(obj2)
        if circle is not None:
            return abs(obj1.distance_to_point(circle.center) - circle.radius)

    if isinstance(obj2, MPLine):
        circle = _as_tangent_circle_mp(obj1)
        if circle is not None:
            return abs(obj2.distance_to_point(circle.center) - circle.radius)

    circle1 = _as_tangent_circle_mp(obj1)
    circle2 = _as_tangent_circle_mp(obj2)
    if circle1 is not None and circle2 is not None:
        center_distance = circle1.center.distance_to(circle2.center)
        radius1 = circle1.radius
        radius2 = circle2.radius
        if center_distance == 0 and radius1 == radius2:
            return radius1 + radius2
        external_residual = abs(center_distance - (radius1 + radius2))
        internal_residual = abs(center_distance - abs(radius1 - radius2))
        return min(external_residual, internal_residual)

    raise TypeError("IsTangent supports (Line, Circle/Arc) or (Circle/Arc, Circle/Arc)")
