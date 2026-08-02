"""Source-semantic forward-AD Jacobian with charged one-sided fallbacks.

This is a disposable local-algorithm candidate.  The original byte-bound DSL
remains the only residual and endpoint authority.  A small forward-mode AD
interpreter mirrors supported public geometry primitives solely to compute a
Jacobian.  Every mirrored scalar row is checked against the corresponding
value returned by the untouched evaluator at the current point.  A row which
is unsupported or fails that value-parity check is differentiated by charged
one-sided finite differences through the original evaluator.

No equation, source variable, guard, or bound is removed.  The algorithm does
not gauge-fix, infer hard bounds, inspect case identity, or use truth/target
counts.  Final endpoints are replayed by the caller's original evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import linalg
from scipy.sparse.linalg import lsmr


ANALYTIC_CPQR = "analytic_forward_ad_cpqr"
ANALYTIC_LSMR = "analytic_forward_ad_lsmr"


@dataclass(frozen=True)
class Configuration:
    name: str
    linear_solver: str
    fd_relative_step: float = 2.0e-7
    initial_trust_radius: float = 1.0
    initial_damping: float = 1.0e-4
    rank_rtol: float = 3.0e-10
    success_residual_inf: float = 1.0e-8
    maximum_iterations: int = 48
    guard_weight: float = 1.0
    parity_rtol: float = 2.0e-8
    parity_atol: float = 2.0e-10


CONFIGURATIONS = {
    ANALYTIC_CPQR: Configuration(ANALYTIC_CPQR, "cpqr"),
    ANALYTIC_LSMR: Configuration(ANALYTIC_LSMR, "lsmr"),
}


@dataclass(frozen=True)
class CandidateOutcome:
    endpoint: np.ndarray
    status: str
    counters: Mapping[str, int]


class UnsupportedExpression(ValueError):
    """One expression cannot be mirrored by the disposable AD interpreter."""


class Dual:
    """Scalar value and a dense forward derivative vector."""

    __slots__ = ("value", "derivative")
    __array_priority__ = 1000

    def __init__(self, value: Any, derivative: Sequence[float]) -> None:
        self.value = float(value)
        self.derivative = np.asarray(derivative, dtype=float)
        if self.derivative.ndim != 1:
            raise UnsupportedExpression("dual derivative is not a vector")

    @property
    def dimension(self) -> int:
        return int(self.derivative.size)

    def _coerce(self, other: Any) -> "Dual":
        if isinstance(other, Dual):
            if other.dimension != self.dimension:
                raise UnsupportedExpression("dual dimensions differ")
            return other
        if isinstance(other, (bool, int, float, np.integer, np.floating)):
            return Dual(float(other), np.zeros(self.dimension))
        raise UnsupportedExpression(f"unsupported dual operand {type(other).__name__}")

    def __add__(self, other: Any) -> "Dual":
        rhs = self._coerce(other)
        return Dual(self.value + rhs.value, self.derivative + rhs.derivative)

    __radd__ = __add__

    def __sub__(self, other: Any) -> "Dual":
        rhs = self._coerce(other)
        return Dual(self.value - rhs.value, self.derivative - rhs.derivative)

    def __rsub__(self, other: Any) -> "Dual":
        rhs = self._coerce(other)
        return Dual(rhs.value - self.value, rhs.derivative - self.derivative)

    def __mul__(self, other: Any) -> "Dual":
        rhs = self._coerce(other)
        return Dual(
            self.value * rhs.value,
            self.derivative * rhs.value + rhs.derivative * self.value,
        )

    __rmul__ = __mul__

    def __truediv__(self, other: Any) -> "Dual":
        rhs = self._coerce(other)
        if rhs.value == 0.0:
            raise UnsupportedExpression("dual division by zero")
        return Dual(
            self.value / rhs.value,
            (self.derivative * rhs.value - rhs.derivative * self.value)
            / (rhs.value * rhs.value),
        )

    def __rtruediv__(self, other: Any) -> "Dual":
        rhs = self._coerce(other)
        return rhs.__truediv__(self)

    def __pow__(self, exponent: Any) -> "Dual":
        if isinstance(exponent, Dual):
            if np.any(exponent.derivative != 0.0) or self.value <= 0.0:
                raise UnsupportedExpression("nonconstant or nonpositive dual power")
            exponent = exponent.value
        if not isinstance(exponent, (int, float, np.integer, np.floating)):
            raise UnsupportedExpression("unsupported power")
        power = float(exponent)
        try:
            value = self.value**power
            factor = power * (self.value ** (power - 1.0))
        except (ValueError, OverflowError, ZeroDivisionError) as error:
            raise UnsupportedExpression("invalid power") from error
        return Dual(value, factor * self.derivative)

    def __rpow__(self, base: Any) -> "Dual":
        if not isinstance(base, (int, float, np.integer, np.floating)) or base <= 0:
            raise UnsupportedExpression("unsupported reverse power")
        value = float(base) ** self.value
        return Dual(value, value * math.log(float(base)) * self.derivative)

    def __neg__(self) -> "Dual":
        return Dual(-self.value, -self.derivative)

    def __pos__(self) -> "Dual":
        return self

    def __abs__(self) -> "Dual":
        if self.value > 0.0:
            return self
        if self.value < 0.0:
            return -self
        return Dual(0.0, np.zeros(self.dimension))

    def __float__(self) -> float:
        return self.value

    def __lt__(self, other: Any) -> bool:
        return self.value < self._coerce(other).value

    def __le__(self, other: Any) -> bool:
        return self.value <= self._coerce(other).value

    def __gt__(self, other: Any) -> bool:
        return self.value > self._coerce(other).value

    def __ge__(self, other: Any) -> bool:
        return self.value >= self._coerce(other).value


def _dimension_of(*values: Any) -> int:
    for value in values:
        if isinstance(value, Dual):
            return value.dimension
        if isinstance(value, ADPoint):
            return value.x.dimension
        if isinstance(value, ADLine):
            return value.a.dimension
        if isinstance(value, ADCircle):
            return value.radius.dimension
        if isinstance(value, (list, tuple)):
            try:
                return _dimension_of(*value)
            except UnsupportedExpression:
                pass
    raise UnsupportedExpression("expression has no differentiable scalar")


def _dual(value: Any, dimension: int) -> Dual:
    if isinstance(value, Dual):
        if value.dimension != dimension:
            raise UnsupportedExpression("dual dimensions differ")
        return value
    if isinstance(value, (bool, int, float, np.integer, np.floating)):
        return Dual(float(value), np.zeros(dimension))
    raise UnsupportedExpression(f"expected scalar, received {type(value).__name__}")


def _unary(value: Any, function, derivative) -> Dual:
    dimension = _dimension_of(value)
    raw = _dual(value, dimension)
    try:
        output = float(function(raw.value))
        slope = float(derivative(raw.value))
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        raise UnsupportedExpression("unary primitive outside its domain") from error
    return Dual(output, slope * raw.derivative)


def ad_sqrt(value: Any) -> Dual:
    return _unary(value, math.sqrt, lambda x: 0.5 / math.sqrt(x))


def ad_sin(value: Any) -> Dual:
    return _unary(value, math.sin, math.cos)


def ad_cos(value: Any) -> Dual:
    return _unary(value, math.cos, lambda x: -math.sin(x))


def ad_tan(value: Any) -> Dual:
    return _unary(value, math.tan, lambda x: 1.0 / math.cos(x) ** 2)


def ad_asin(value: Any) -> Dual:
    return _unary(value, math.asin, lambda x: 1.0 / math.sqrt(1.0 - x * x))


def ad_acos(value: Any) -> Dual:
    return _unary(value, math.acos, lambda x: -1.0 / math.sqrt(1.0 - x * x))


def ad_atan(value: Any) -> Dual:
    return _unary(value, math.atan, lambda x: 1.0 / (1.0 + x * x))


def ad_exp(value: Any) -> Dual:
    return _unary(value, math.exp, math.exp)


def ad_log(value: Any) -> Dual:
    return _unary(value, math.log, lambda x: 1.0 / x)


def ad_atan2(y: Any, x: Any) -> Dual:
    dimension = _dimension_of(y, x)
    yy, xx = _dual(y, dimension), _dual(x, dimension)
    denominator = xx.value * xx.value + yy.value * yy.value
    if denominator == 0.0:
        raise UnsupportedExpression("atan2 is singular at the origin")
    return Dual(
        math.atan2(yy.value, xx.value),
        (xx.value * yy.derivative - yy.value * xx.derivative) / denominator,
    )


def ad_abs(value: Any) -> Any:
    return abs(value) if isinstance(value, Dual) else abs(value)


def ad_min(*values: Any) -> Any:
    if len(values) == 1 and isinstance(values[0], (list, tuple)):
        values = tuple(values[0])
    if not values:
        raise UnsupportedExpression("min of empty sequence")
    return min(values, key=lambda value: float(value) if isinstance(value, Dual) else value)


def ad_max(*values: Any) -> Any:
    if len(values) == 1 and isinstance(values[0], (list, tuple)):
        values = tuple(values[0])
    if not values:
        raise UnsupportedExpression("max of empty sequence")
    return max(values, key=lambda value: float(value) if isinstance(value, Dual) else value)


@dataclass(frozen=True)
class ADPoint:
    x: Dual
    y: Dual

    def __add__(self, other: Any) -> "ADPoint":
        if not isinstance(other, ADPoint):
            raise UnsupportedExpression("point addition expects a point")
        return ADPoint(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Any) -> "ADPoint":
        if not isinstance(other, ADPoint):
            raise UnsupportedExpression("point subtraction expects a point")
        return ADPoint(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: Any) -> "ADPoint":
        return ADPoint(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: Any) -> "ADPoint":
        return ADPoint(self.x / scalar, self.y / scalar)

    def __neg__(self) -> "ADPoint":
        return ADPoint(-self.x, -self.y)

    def dot(self, other: "ADPoint") -> Dual:
        return self.x * other.x + self.y * other.y

    def cross(self, other: "ADPoint") -> Dual:
        return self.x * other.y - self.y * other.x

    def norm(self) -> Dual:
        return ad_sqrt(self.x * self.x + self.y * self.y)

    def distance_to(self, other: "ADPoint") -> Dual:
        return (self - other).norm()


@dataclass(frozen=True)
class ADLine:
    a: Dual
    b: Dual
    c: Dual

    def distance_to_point(self, point: ADPoint) -> Dual:
        return abs(self.a * point.x + self.b * point.y + self.c)


@dataclass(frozen=True)
class ADCircle:
    center: ADPoint
    radius: Dual


@dataclass(frozen=True)
class ADPolygon:
    points: tuple[ADPoint, ...]


def Point(x: Any = 0.0, y: Any = 0.0) -> ADPoint:
    dimension = _dimension_of(x, y)
    return ADPoint(_dual(x, dimension), _dual(y, dimension))


def Line(first: Any, second: Any, third: Any | None = None) -> ADLine:
    dimension = _dimension_of(first, second, third)
    if isinstance(first, ADPoint) and isinstance(second, ADPoint) and third is None:
        a = first.y - second.y
        b = second.x - first.x
        c = first.x * second.y - second.x * first.y
    else:
        if third is None:
            raise UnsupportedExpression("line expects two points or three coefficients")
        a, b, c = (_dual(first, dimension), _dual(second, dimension), _dual(third, dimension))
    norm = ad_sqrt(a * a + b * b)
    if norm.value <= 1.0e-30:
        raise UnsupportedExpression("line through coincident points")
    return ADLine(a / norm, b / norm, c / norm)


def Circle(center: ADPoint, radius: Any) -> ADCircle:
    if not isinstance(center, ADPoint):
        raise UnsupportedExpression("circle center is not a point")
    return ADCircle(center, _dual(radius, center.x.dimension))


def Polygon(points: Sequence[ADPoint]) -> ADPolygon:
    if not isinstance(points, (list, tuple)) or not all(
        isinstance(point, ADPoint) for point in points
    ):
        raise UnsupportedExpression("polygon expects a point sequence")
    return ADPolygon(tuple(points))


def Distance(first: Any, second: Any | None = None) -> Dual:
    if second is None and isinstance(first, ADPoint):
        return first.norm()
    if isinstance(first, ADPoint) and isinstance(second, ADPoint):
        return first.distance_to(second)
    if isinstance(first, ADPoint) and isinstance(second, ADLine):
        return second.distance_to_point(first)
    if isinstance(first, ADLine) and isinstance(second, ADPoint):
        return first.distance_to_point(second)
    if isinstance(first, ADPoint) and isinstance(second, ADCircle):
        return abs(first.distance_to(second.center) - second.radius)
    if isinstance(first, ADCircle) and isinstance(second, ADPoint):
        return abs(second.distance_to(first.center) - first.radius)
    raise UnsupportedExpression("unsupported Distance signature")


def Midpoint(first: Any, second: Any | None = None) -> ADPoint:
    if second is None and isinstance(first, ADCircle):
        return first.center
    if isinstance(first, ADPoint) and isinstance(second, ADPoint):
        return (first + second) / 2.0
    raise UnsupportedExpression("unsupported Midpoint signature")


def Angle(first: Any, second: Any = None, third: Any = None) -> Dual:
    if all(isinstance(value, ADPoint) for value in (first, second, third)):
        left = first - second
        right = third - second
        return ad_atan2(abs(left.cross(right)), left.dot(right))
    if isinstance(first, ADLine) and isinstance(second, ADLine) and third is None:
        return ad_acos(abs(first.a * second.a + first.b * second.b))
    raise UnsupportedExpression("unsupported Angle signature")


def Radius(circle: ADCircle) -> Dual:
    if not isinstance(circle, ADCircle):
        raise UnsupportedExpression("Radius expects a circle")
    return circle.radius


def Area(*values: Any) -> Dual:
    if len(values) == 1 and isinstance(values[0], ADCircle):
        return math.pi * values[0].radius * values[0].radius
    if len(values) == 1 and isinstance(values[0], ADPolygon):
        values = values[0].points
    if len(values) >= 3 and all(isinstance(value, ADPoint) for value in values):
        total = values[0].x * 0.0
        for index, first in enumerate(values):
            second = values[(index + 1) % len(values)]
            total = total + first.x * second.y - first.y * second.x
        return abs(total) / 2.0
    raise UnsupportedExpression("Area expects a circle or at least three points")


def Vector(first: ADPoint, second: ADPoint) -> ADPoint:
    return second - first


def Dot(first: Any, second: Any) -> Dual:
    if isinstance(first, ADPoint) and isinstance(second, ADPoint):
        return first.dot(second)
    if isinstance(first, ADLine) and isinstance(second, ADLine):
        return first.a * second.a + first.b * second.b
    raise UnsupportedExpression("Dot expects vectors/points or lines")


def OnLine(point: ADPoint, first: Any, second: Any = None, ordered: bool = False) -> Dual:
    if not isinstance(point, ADPoint):
        raise UnsupportedExpression("OnLine first argument is not a point")
    if isinstance(first, ADLine) and second is None:
        return first.distance_to_point(point)
    if isinstance(first, ADPoint) and isinstance(second, ADPoint):
        left, right = first - point, second - point
        collinear = left.cross(right)
        if ordered:
            order = Distance(point, first) + Distance(first, second) - Distance(point, second)
            return collinear * collinear + order * order
        return collinear
    raise UnsupportedExpression("unsupported OnLine signature")


def Collinear(first: ADPoint, second: ADPoint, third: ADPoint, ordered: bool = False) -> Dual:
    return OnLine(first, second, third, ordered=ordered)


def OnCircle(point: ADPoint, circle: ADCircle) -> Dual:
    if not isinstance(point, ADPoint) or not isinstance(circle, ADCircle):
        raise UnsupportedExpression("OnCircle expects point and circle")
    return Distance(point, circle.center) - circle.radius


def OnSegment(point: ADPoint, start: ADPoint, end: ADPoint) -> Dual:
    return Distance(start, point) + Distance(point, end) - Distance(start, end)


def IsTangent(first: Any, second: Any) -> Dual:
    if isinstance(first, ADLine) and isinstance(second, ADCircle):
        return abs(Distance(second.center, first) - second.radius)
    if isinstance(second, ADLine) and isinstance(first, ADCircle):
        return abs(Distance(first.center, second) - first.radius)
    if isinstance(first, ADCircle) and isinstance(second, ADCircle):
        distance = Distance(first.center, second.center)
        external = abs(distance - (first.radius + second.radius))
        internal = abs(distance - abs(first.radius - second.radius))
        return ad_min(external, internal)
    raise UnsupportedExpression("unsupported IsTangent signature")


def Perpendicular(first: ADLine, second: ADLine) -> Dual:
    if not isinstance(first, ADLine) or not isinstance(second, ADLine):
        raise UnsupportedExpression("Perpendicular expects lines")
    return first.a * second.a + first.b * second.b


def Parallel(first: ADLine, second: ADLine) -> Dual:
    if not isinstance(first, ADLine) or not isinstance(second, ADLine):
        raise UnsupportedExpression("Parallel expects lines")
    return first.a * second.b - second.a * first.b


def ParallelismMeasure(first: ADLine, second: ADLine, method: str = "cross") -> Dual:
    if method != "cross":
        denominator = ad_sqrt(first.a * first.a + first.b * first.b) * ad_sqrt(
            second.a * second.a + second.b * second.b
        )
        return Parallel(first, second) / denominator
    return Parallel(first, second)


def Circumcenter(first: ADPoint, second: ADPoint, third: ADPoint) -> ADPoint:
    x1, y1 = first.x, first.y
    x2, y2 = second.x, second.y
    x3, y3 = third.x, third.y
    denominator = 2.0 * (
        x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    )
    if abs(denominator.value) <= 1.0e-30:
        raise UnsupportedExpression("degenerate circumcenter")
    ux = (
        (x1 * x1 + y1 * y1) * (y2 - y3)
        + (x2 * x2 + y2 * y2) * (y3 - y1)
        + (x3 * x3 + y3 * y3) * (y1 - y2)
    ) / denominator
    uy = (
        (x1 * x1 + y1 * y1) * (x3 - x2)
        + (x2 * x2 + y2 * y2) * (x1 - x3)
        + (x3 * x3 + y3 * y3) * (x2 - x1)
    ) / denominator
    return ADPoint(ux, uy)


def Circumcircle(first: ADPoint, second: ADPoint, third: ADPoint) -> ADCircle:
    center = Circumcenter(first, second, third)
    return ADCircle(center, Distance(center, first))


def Incenter(first: ADPoint, second: ADPoint, third: ADPoint) -> ADPoint:
    a = Distance(second, third)
    b = Distance(third, first)
    c = Distance(first, second)
    perimeter = a + b + c
    if perimeter.value <= 1.0e-30:
        raise UnsupportedExpression("degenerate incenter")
    return ADPoint(
        (a * first.x + b * second.x + c * third.x) / perimeter,
        (a * first.y + b * second.y + c * third.y) / perimeter,
    )


def Incircle(first: ADPoint, second: ADPoint, third: ADPoint) -> ADCircle:
    center = Incenter(first, second, third)
    twice_area = abs(
        first.x * (second.y - third.y)
        + second.x * (third.y - first.y)
        + third.x * (first.y - second.y)
    )
    perimeter = Distance(second, third) + Distance(third, first) + Distance(first, second)
    if perimeter.value <= 1.0e-30:
        raise UnsupportedExpression("degenerate incircle")
    return ADCircle(center, twice_area / perimeter)


def Excenter(
    first: ADPoint,
    second: ADPoint,
    third: ADPoint,
    vertex: Any = None,
) -> ADPoint:
    if vertex in ("B", 1):
        return Excenter(second, third, first)
    if vertex in ("C", 2):
        return Excenter(third, first, second)
    a = Distance(second, third)
    b = Distance(third, first)
    c = Distance(first, second)
    denominator = -a + b + c
    if abs(denominator.value) <= 1.0e-30:
        raise UnsupportedExpression("degenerate excenter")
    return ADPoint(
        (-a * first.x + b * second.x + c * third.x) / denominator,
        (-a * first.y + b * second.y + c * third.y) / denominator,
    )


def Excircle(
    first: ADPoint,
    second: ADPoint,
    third: ADPoint,
    vertex: Any = None,
) -> ADCircle:
    if vertex in ("B", 1):
        return Excircle(second, third, first)
    if vertex in ("C", 2):
        return Excircle(third, first, second)
    center = Excenter(first, second, third)
    twice_area = abs(
        first.x * (second.y - third.y)
        + second.x * (third.y - first.y)
        + third.x * (first.y - second.y)
    )
    denominator = -Distance(second, third) + Distance(third, first) + Distance(first, second)
    if abs(denominator.value) <= 1.0e-30:
        raise UnsupportedExpression("degenerate excircle")
    return ADCircle(center, twice_area / denominator)


def Orthocenter(first: ADPoint, second: ADPoint, third: ADPoint) -> ADPoint:
    dx_bc, dy_bc = third.x - second.x, third.y - second.y
    k1 = dx_bc * first.x + dy_bc * first.y
    dx_ca, dy_ca = first.x - third.x, first.y - third.y
    k2 = dx_ca * second.x + dy_ca * second.y
    determinant = dx_bc * dy_ca - dx_ca * dy_bc
    if abs(determinant.value) <= 1.0e-30:
        raise UnsupportedExpression("degenerate orthocenter")
    return ADPoint(
        (k1 * dy_ca - k2 * dy_bc) / determinant,
        (dx_bc * k2 - dx_ca * k1) / determinant,
    )


def PerpendicularBisector(first: ADPoint, second: ADPoint) -> ADLine:
    middle = Midpoint(first, second)
    a = second.x - first.x
    b = second.y - first.y
    return Line(a, b, -(a * middle.x + b * middle.y))


def AngleBisector(first: ADPoint, vertex: ADPoint, third: ADPoint) -> ADLine:
    left, right = first - vertex, third - vertex
    left_norm, right_norm = left.norm(), right.norm()
    if left_norm.value <= 1.0e-30 or right_norm.value <= 1.0e-30:
        raise UnsupportedExpression("degenerate angle bisector")
    direction = left / left_norm + right / right_norm
    if math.hypot(direction.x.value, direction.y.value) <= 1.0e-20:
        direction = ADPoint(-left.y / left_norm, left.x / left_norm)
    point = vertex + direction
    return Line(vertex, point)


def FootOfPerpendicular(first: Any, second: Any) -> ADPoint:
    if isinstance(first, ADLine) and isinstance(second, ADPoint):
        line, point = first, second
    elif isinstance(first, ADPoint) and isinstance(second, ADLine):
        point, line = first, second
    else:
        raise UnsupportedExpression("foot expects line and point")
    denominator = line.a * line.a + line.b * line.b
    return ADPoint(
        (line.b * (line.b * point.x - line.a * point.y) - line.a * line.c)
        / denominator,
        (line.a * (-line.b * point.x + line.a * point.y) - line.b * line.c)
        / denominator,
    )


def ClosestPoint(first: Any, second: Any) -> ADPoint:
    if isinstance(first, ADPoint) and isinstance(second, (ADLine, ADCircle)):
        point, obj = first, second
    elif isinstance(second, ADPoint) and isinstance(first, (ADLine, ADCircle)):
        obj, point = first, second
    else:
        raise UnsupportedExpression("ClosestPoint expects a point and line/circle")
    if isinstance(obj, ADLine):
        return FootOfPerpendicular(point, obj)
    delta = point - obj.center
    distance = delta.norm()
    if distance.value <= 1.0e-30:
        raise UnsupportedExpression("circle closest point is ambiguous at center")
    return obj.center + delta * (obj.radius / distance)


def ContactPoint(first: Any, second: Any) -> ADPoint:
    if isinstance(first, ADCircle) and isinstance(second, ADLine):
        return ClosestPoint(first.center, second)
    if isinstance(second, ADCircle) and isinstance(first, ADLine):
        return ClosestPoint(second.center, first)
    raise UnsupportedExpression("ContactPoint supports circle-line only")


def Reflect(point: ADPoint, axis: Any) -> ADPoint:
    if not isinstance(point, ADPoint):
        raise UnsupportedExpression("Reflect object is not a point")
    if isinstance(axis, ADPoint):
        return 2.0 * axis - point
    if isinstance(axis, ADLine):
        foot = FootOfPerpendicular(point, axis)
        return 2.0 * foot - point
    raise UnsupportedExpression("unsupported reflection axis")


def Rotate(point: ADPoint, angle: Any, center: ADPoint | None = None) -> ADPoint:
    if center is None:
        dimension = point.x.dimension
        center = ADPoint(Dual(0.0, np.zeros(dimension)), Dual(0.0, np.zeros(dimension)))
    delta = point - center
    cosine, sine = ad_cos(angle), ad_sin(angle)
    return ADPoint(
        delta.x * cosine - delta.y * sine + center.x,
        delta.x * sine + delta.y * cosine + center.y,
    )


def Intersect(first: Any, second: Any, **_selection: Any) -> ADPoint:
    if not isinstance(first, ADLine) or not isinstance(second, ADLine):
        raise UnsupportedExpression("AD Intersect currently supports line-line only")
    determinant = first.a * second.b - second.a * first.b
    if abs(determinant.value) <= 1.0e-30:
        raise UnsupportedExpression("parallel line intersection")
    return ADPoint(
        (first.b * second.c - second.b * first.c) / determinant,
        (second.a * first.c - first.a * second.c) / determinant,
    )


def IsAcuteTriangle(first: ADPoint, second: ADPoint, third: ADPoint) -> Dual:
    maximum = ad_max(
        Angle(second, first, third),
        Angle(first, second, third),
        Angle(first, third, second),
    )
    return ad_max(0.0, maximum - math.pi / 2.0)


def IsRightTriangle(first: ADPoint, second: ADPoint, third: ADPoint) -> Dual:
    return ad_min(
        abs(Angle(second, first, third) - math.pi / 2.0),
        abs(Angle(first, second, third) - math.pi / 2.0),
        abs(Angle(first, third, second) - math.pi / 2.0),
    )


def IsObtuseTriangle(first: ADPoint, second: ADPoint, third: ADPoint) -> Dual:
    maximum = ad_max(
        Angle(second, first, third),
        Angle(first, second, third),
        Angle(first, third, second),
    )
    return ad_max(0.0, math.pi / 2.0 - maximum)


AD_FUNCTIONS: dict[str, Any] = {
    "Point": Point,
    "Line": Line,
    "Circle": Circle,
    "Polygon": Polygon,
    "Distance": Distance,
    "Midpoint": Midpoint,
    "Angle": Angle,
    "Radius": Radius,
    "Area": Area,
    "Vector": Vector,
    "Dot": Dot,
    "OnLine": OnLine,
    "Collinear": Collinear,
    "OnCircle": OnCircle,
    "OnSegment": OnSegment,
    "IsTangent": IsTangent,
    "Perpendicular": Perpendicular,
    "Parallel": Parallel,
    "ParallelismMeasure": ParallelismMeasure,
    "Circumcenter": Circumcenter,
    "Circumcircle": Circumcircle,
    "Incenter": Incenter,
    "Incircle": Incircle,
    "Excenter": Excenter,
    "Excircle": Excircle,
    "Orthocenter": Orthocenter,
    "PerpendicularBisector": PerpendicularBisector,
    "AngleBisector": AngleBisector,
    "FootOfPerpendicular": FootOfPerpendicular,
    "ClosestPoint": ClosestPoint,
    "ContactPoint": ContactPoint,
    "Reflect": Reflect,
    "Rotate": Rotate,
    "Intersect": Intersect,
    "IsAcuteTriangle": IsAcuteTriangle,
    "IsRightTriangle": IsRightTriangle,
    "IsObtuseTriangle": IsObtuseTriangle,
    "sqrt": ad_sqrt,
    "sin": ad_sin,
    "cos": ad_cos,
    "tan": ad_tan,
    "asin": ad_asin,
    "acos": ad_acos,
    "atan": ad_atan,
    "atan2": ad_atan2,
    "exp": ad_exp,
    "log": ad_log,
    "abs": ad_abs,
    "Abs": ad_abs,
    "min": ad_min,
    "Min": ad_min,
    "max": ad_max,
    "Max": ad_max,
    "pi": math.pi,
    "e": math.e,
    "True": True,
    "False": False,
}


def _constraint_pair(raw: object) -> tuple[str, object]:
    if isinstance(raw, Mapping):
        left, right = raw.get("def"), raw.get("value", 0)
        if not isinstance(left, str):
            raise ValueError("constraint has no source expression")
        return left, right
    if isinstance(raw, str):
        return raw, 0
    raise ValueError("unsupported untouched constraint record")


def _eval_source(expression: object, context: Mapping[str, object]) -> Any:
    if isinstance(expression, (bool, int, float)):
        return expression
    if not isinstance(expression, str):
        raise UnsupportedExpression("source expression is not a scalar/string")
    from geosolver.ir.compiler import safe_eval_expr

    try:
        return safe_eval_expr(expression, dict(context))
    except Exception as error:
        raise UnsupportedExpression(str(error)) from error


@dataclass(frozen=True)
class ADProgram:
    variable_names: tuple[str, ...]
    construction: tuple[tuple[str, str], ...]
    constraints: tuple[tuple[str, object], ...]
    guards: tuple[object, ...]

    @property
    def dimension(self) -> int:
        return len(self.variable_names)

    @property
    def residual_dimension(self) -> int:
        return len(self.constraints)

    def _context(self, point: Sequence[float]) -> dict[str, object]:
        values = np.asarray(point, dtype=float)
        if values.shape != (self.dimension,) or not np.all(np.isfinite(values)):
            raise UnsupportedExpression("AD point is malformed")
        context = dict(AD_FUNCTIONS)
        for index, (name, value) in enumerate(zip(self.variable_names, values, strict=True)):
            derivative = np.zeros(self.dimension)
            derivative[index] = 1.0
            context[name] = Dual(float(value), derivative)
        for name, expression in self.construction:
            try:
                context[name] = _eval_source(expression, context)
            except UnsupportedExpression:
                # Preserve later independent constructions.  A dependent row
                # fails closed when its name is absent.
                context.pop(name, None)
        return context

    def relation_rows(self, point: Sequence[float]) -> tuple[Dual | None, ...]:
        context = self._context(point)
        rows: list[Dual | None] = []
        for left, right in self.constraints:
            try:
                value = _eval_source(left, context) - _eval_source(right, context)
                rows.append(_dual(value, self.dimension))
            except Exception:
                rows.append(None)
        return tuple(rows)

    def guard_rows(self, point: Sequence[float], tolerance: float = 1.0e-12) -> tuple[Dual | None, ...]:
        context = self._context(point)
        rows: list[Dual | None] = []
        for guard in self.guards:
            try:
                rows.append(_guard_violation_dual(guard, context, self.dimension, tolerance))
            except Exception:
                rows.append(None)
        return tuple(rows)


def compile_program(document: Mapping[str, object]) -> ADProgram:
    variables = document.get("variables")
    if not isinstance(variables, Mapping):
        raise ValueError("source variables mapping is missing")
    raw_names = variables.get("names")
    if not isinstance(raw_names, list):
        raise ValueError("source variable names are missing")
    names = tuple(str(name) for name in raw_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("source variable names are empty or duplicated")
    raw_construction = document.get("construction")
    if raw_construction is None:
        raw_construction = []
    if not isinstance(raw_construction, list):
        raise ValueError("source construction is not a list")
    construction: list[tuple[str, str]] = []
    for item in raw_construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str) or not isinstance(item.get("expr"), str):
            raise ValueError("source construction item is malformed")
        construction.append((str(item["name"]), str(item["expr"])))
    raw_constraints = document.get("constraints")
    if raw_constraints is None:
        raw_constraints = []
    if not isinstance(raw_constraints, list):
        raise ValueError("source constraints are not a list")
    constraints = tuple(_constraint_pair(raw) for raw in raw_constraints)
    raw_guards = document.get("guards")
    if raw_guards is None:
        raw_guards = []
    if not isinstance(raw_guards, list):
        raise ValueError("source guards are not a list")
    from geosolver._internal.autosolve.guards.compile import compile_guard_expr

    guards = tuple(compile_guard_expr(str(source)) for source in raw_guards)
    return ADProgram(names, tuple(construction), constraints, guards)


def _positive_part(value: Dual) -> Dual:
    if value.value > 0.0:
        return value
    return Dual(0.0, np.zeros(value.dimension))


def _guard_violation_dual(
    guard: object,
    context: Mapping[str, object],
    dimension: int,
    tolerance: float,
) -> Dual:
    kind = str(getattr(guard, "kind", ""))
    if kind == "compare":
        left = _dual(_eval_source(getattr(guard, "lhs_expr"), context), dimension)
        right = _dual(_eval_source(getattr(guard, "rhs_expr"), context), dimension)
        operator = str(getattr(guard, "operator", ""))
        if operator == ">":
            return _positive_part(right - left + tolerance)
        if operator == ">=":
            return _positive_part(right - left - tolerance)
        if operator == "<":
            return _positive_part(left - right + tolerance)
        if operator == "<=":
            return _positive_part(left - right - tolerance)
        if operator == "==":
            return _positive_part(abs(left - right) - tolerance)
        if operator == "!=":
            return _positive_part(tolerance - abs(left - right))
        raise UnsupportedExpression("unknown compare guard")
    if kind in {"bound", "bound_open"}:
        value = _dual(_eval_source(getattr(guard, "lhs_expr"), context), dimension)
        total = Dual(0.0, np.zeros(dimension))
        lower_expr = getattr(guard, "lower_expr", None)
        upper_expr = getattr(guard, "upper_expr", None)
        offset = tolerance if kind == "bound_open" else -tolerance
        if lower_expr is not None:
            lower = _dual(_eval_source(lower_expr, context), dimension)
            total = total + _positive_part(lower - value + offset)
        if upper_expr is not None:
            upper = _dual(_eval_source(upper_expr, context), dimension)
            total = total + _positive_part(value - upper + offset)
        return total
    if kind == "residual":
        residual = _dual(
            _eval_source(getattr(guard, "residual_expr"), context), dimension
        )
        return _positive_part(abs(residual) - tolerance)
    # Logical and raw predicates are intentionally left to charged FD.
    raise UnsupportedExpression("guard kind is not analytically mirrored")


@dataclass
class _State:
    x: np.ndarray
    augmented: np.ndarray
    relation: np.ndarray
    semantics_valid: bool
    violation_inf: float

    @property
    def relation_inf(self) -> float:
        if not np.all(np.isfinite(self.relation)):
            return math.inf
        return float(np.linalg.norm(self.relation, ord=np.inf))

    @property
    def objective(self) -> float:
        if not np.all(np.isfinite(self.augmented)):
            return math.inf
        value = float(np.dot(self.augmented, self.augmented))
        return 0.5 * value if math.isfinite(value) else math.inf


def _make_state(case: object, point: np.ndarray, guard_weight: float) -> _State:
    observation = case.evaluate(np.asarray(point, dtype=float))
    relation = np.asarray(observation.residual, dtype=float)
    if relation.shape != (case.residual_dimension,) or not observation.finite or not np.all(np.isfinite(relation)):
        relation = np.full(case.residual_dimension, 1.0e6)
    raw_violation = np.asarray(observation.violation_vector, dtype=float)
    raw_violation = np.maximum(
        0.0, np.where(np.isfinite(raw_violation), raw_violation, 1.0e6)
    )
    augmented = np.concatenate(
        (relation, float(guard_weight) * np.log1p(raw_violation))
    )
    return _State(
        np.asarray(point, dtype=float).copy(),
        augmented,
        relation,
        bool(observation.finite and observation.semantics_valid),
        float(np.max(raw_violation, initial=0.0)),
    )


def _better(left: _State, right: _State) -> bool:
    return (
        not left.semantics_valid,
        left.violation_inf if not left.semantics_valid else 0.0,
        left.relation_inf,
        left.objective,
    ) < (
        not right.semantics_valid,
        right.violation_inf if not right.semantics_valid else 0.0,
        right.relation_inf,
        right.objective,
    )


def _parity_matches(calculated: float, observed: float, configuration: Configuration) -> bool:
    return bool(
        math.isfinite(calculated)
        and math.isfinite(observed)
        and abs(calculated - observed)
        <= configuration.parity_atol
        + configuration.parity_rtol * max(1.0, abs(observed))
    )


def _hybrid_jacobian(
    case: object,
    program: ADProgram,
    current: _State,
    origin: np.ndarray,
    scales: np.ndarray,
    lower_z: np.ndarray,
    upper_z: np.ndarray,
    configuration: Configuration,
    counters: dict[str, int],
) -> np.ndarray:
    dimension = program.dimension
    row_count = current.augmented.size
    jacobian = np.zeros((row_count, dimension))
    supported = np.zeros(row_count, dtype=bool)

    relation_rows = program.relation_rows(current.x)
    for index, row in enumerate(relation_rows):
        if row is None:
            continue
        if _parity_matches(row.value, current.relation[index], configuration) and np.all(
            np.isfinite(row.derivative)
        ):
            jacobian[index, :] = row.derivative * scales
            supported[index] = True
            counters["analytic_relation_rows"] += 1
        else:
            counters["relation_parity_fallback_rows"] += 1

    guard_start = program.residual_dimension
    guard_rows = program.guard_rows(current.x)
    for ordinal, row in enumerate(guard_rows):
        index = guard_start + ordinal
        if index >= row_count - 1 or row is None:
            continue
        transformed_value = configuration.guard_weight * math.log1p(max(0.0, row.value))
        if _parity_matches(transformed_value, current.augmented[index], configuration) and np.all(
            np.isfinite(row.derivative)
        ):
            jacobian[index, :] = (
                configuration.guard_weight * row.derivative / (1.0 + max(0.0, row.value))
            ) * scales
            supported[index] = True
            counters["analytic_guard_rows"] += 1
        else:
            counters["guard_parity_fallback_rows"] += 1

    # The final opaque hard-feasibility component is locally constant whenever
    # it is inactive.  Active/unknown hard feasibility always fails closed to
    # a charged finite difference.
    if row_count > guard_start + len(guard_rows) and current.augmented[-1] == 0.0:
        supported[-1] = True
        counters["analytic_inactive_hard_rows"] += 1

    unsupported = np.flatnonzero(~supported)
    counters["analytic_rows_total"] += int(np.count_nonzero(supported))
    counters["fd_fallback_rows_total"] += int(unsupported.size)
    if unsupported.size == 0:
        return jacobian

    z = (current.x - origin) / scales
    # One directional sample per column is the fail-closed fallback.  This is
    # deliberately simple: no structural zeros are asserted for an unsupported
    # row, and all samples are charged by the original evaluator.
    for column in range(dimension):
        nominal = configuration.fd_relative_step * max(1.0, abs(float(z[column])))
        trial_value = min(float(upper_z[column]), float(z[column] + nominal))
        if trial_value == z[column]:
            trial_value = max(float(lower_z[column]), float(z[column] - nominal))
        delta = trial_value - z[column]
        if delta == 0.0:
            continue
        trial_z = z.copy()
        trial_z[column] = trial_value
        trial = _make_state(case, origin + scales * trial_z, configuration.guard_weight)
        jacobian[unsupported, column] = (
            trial.augmented[unsupported] - current.augmented[unsupported]
        ) / delta
        counters["fd_direction_evaluations"] += 1
    return jacobian


def _rank_aware_step(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    rank_rtol: float,
    solver: str,
) -> tuple[np.ndarray, int]:
    rows, columns = jacobian.shape
    if columns == 0:
        return np.empty(0), 0
    if not np.all(np.isfinite(jacobian)) or not np.all(np.isfinite(residual)):
        return np.zeros(columns), 0
    singular = linalg.svdvals(jacobian, check_finite=False)
    threshold = rank_rtol * max(1.0, float(singular[0]) if singular.size else 0.0)
    rank = int(np.count_nonzero(singular > threshold))
    if solver == "lsmr":
        regularizer = math.sqrt(max(damping, 1.0e-16)) * np.eye(columns)
        augmented = np.vstack((jacobian, regularizer))
        rhs = -np.concatenate((residual, np.zeros(columns)))
        result = lsmr(
            augmented,
            rhs,
            atol=rank_rtol,
            btol=rank_rtol,
            maxiter=max(20, min(200, 4 * columns)),
        )
        return np.asarray(result[0], dtype=float), rank
    if solver != "cpqr":
        raise ValueError(f"unknown linear solver {solver!r}")
    _q, r, pivots = linalg.qr(
        jacobian, mode="economic", pivoting=True, check_finite=False
    )
    diagonal = np.abs(np.diag(r))
    qr_threshold = rank_rtol * max(
        1.0, float(diagonal[0]) if diagonal.size else 0.0
    )
    rank = int(np.count_nonzero(diagonal > qr_threshold))
    step = np.zeros(columns)
    if rank:
        selected = np.asarray(pivots[:rank], dtype=int)
        reduced = jacobian[:, selected]
        augmented = np.vstack(
            (reduced, math.sqrt(max(damping, 1.0e-16)) * np.eye(rank))
        )
        rhs = -np.concatenate((residual, np.zeros(rank)))
        reduced_step, *_ = linalg.lstsq(
            augmented, rhs, cond=rank_rtol, check_finite=False
        )
        step[selected] = reduced_step
    return step, rank


def solve_local(
    case: object,
    program: ADProgram,
    configuration: Configuration,
    start: Sequence[float],
    *,
    max_callbacks: int,
    deadline_monotonic: float,
) -> CandidateOutcome:
    if program.dimension != int(case.dimension) or program.residual_dimension != int(
        case.residual_dimension
    ):
        raise ValueError("AD program shape differs from the original evaluator")
    start = np.asarray(start, dtype=float)
    if start.shape != (program.dimension,) or not np.all(np.isfinite(start)):
        raise ValueError("start has wrong shape or is nonfinite")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")
    counters = {
        "starts_attempted": 1,
        "iterations": 0,
        "accepted_steps": 0,
        "rejected_steps": 0,
        "analytic_relation_rows": 0,
        "analytic_guard_rows": 0,
        "analytic_inactive_hard_rows": 0,
        "analytic_rows_total": 0,
        "fd_fallback_rows_total": 0,
        "relation_parity_fallback_rows": 0,
        "guard_parity_fallback_rows": 0,
        "fd_direction_evaluations": 0,
        "rank_deficient_iterations": 0,
        "reported_safe_endpoint": 0,
        "deadline_stops": 0,
        "budget_stops": 0,
        "linear_failures": 0,
    }
    origin = np.asarray(case.origin, dtype=float)
    scales = np.asarray(case.scales, dtype=float)
    lower = np.asarray(case.lower, dtype=float)
    upper = np.asarray(case.upper, dtype=float)
    if (
        origin.shape != start.shape
        or scales.shape != start.shape
        or not np.all(np.isfinite(origin))
        or not np.all(np.isfinite(scales))
        or np.any(scales <= 0.0)
    ):
        raise ValueError("opaque compiler scale metadata is invalid")
    lower_z = (lower - origin) / scales
    upper_z = (upper - origin) / scales
    clipped_start = np.minimum(np.maximum(start, lower), upper)
    try:
        current = _make_state(case, clipped_start, configuration.guard_weight)
    except Exception as error:
        if error.__class__.__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(clipped_start.copy(), "budget_before_start", counters)
        raise
    best = current
    trust_radius = configuration.initial_trust_radius
    damping = configuration.initial_damping
    stagnation = 0
    for _ in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if current.semantics_valid and current.relation_inf <= configuration.success_residual_inf:
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1
        try:
            jacobian = _hybrid_jacobian(
                case,
                program,
                current,
                origin,
                scales,
                lower_z,
                upper_z,
                configuration,
                counters,
            )
            step, rank = _rank_aware_step(
                jacobian,
                current.augmented,
                damping,
                configuration.rank_rtol,
                configuration.linear_solver,
            )
        except Exception as error:
            if error.__class__.__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["linear_failures"] += 1
            break
        counters["rank_deficient_iterations"] += int(rank < min(jacobian.shape))
        step_norm = float(np.linalg.norm(step))
        if not math.isfinite(step_norm) or step_norm == 0.0:
            damping = min(1.0e12, damping * 10.0)
            trust_radius = max(1.0e-8, trust_radius * 0.5)
            stagnation += 1
            if stagnation >= 4:
                break
            continue
        if step_norm > trust_radius:
            step *= trust_radius / step_norm
            step_norm = trust_radius
        current_z = (current.x - origin) / scales
        trial_z = np.minimum(np.maximum(current_z + step, lower_z), upper_z)
        trial_x = origin + scales * trial_z
        try:
            trial = _make_state(case, trial_x, configuration.guard_weight)
        except Exception as error:
            if error.__class__.__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["rejected_steps"] += 1
            damping = min(1.0e12, damping * 10.0)
            trust_radius = max(1.0e-8, trust_radius * 0.5)
            continue
        if _better(trial, best):
            best = trial
        predicted = current.augmented + jacobian @ (trial_z - current_z)
        predicted_reduction = current.objective - 0.5 * float(np.dot(predicted, predicted))
        actual_reduction = current.objective - trial.objective
        ratio = (
            actual_reduction / predicted_reduction
            if predicted_reduction > 0.0 and math.isfinite(predicted_reduction)
            else -math.inf
        )
        accepted = _better(trial, current) or (
            actual_reduction > 0.0 and ratio > 1.0e-4
        )
        if accepted:
            current = trial
            counters["accepted_steps"] += 1
            stagnation = 0
            if ratio > 0.75:
                trust_radius = min(100.0, max(trust_radius, 2.0 * step_norm))
                damping = max(1.0e-14, damping * 0.3)
            elif ratio < 0.25:
                trust_radius = max(1.0e-8, trust_radius * 0.5)
                damping = min(1.0e12, damping * 3.0)
        else:
            counters["rejected_steps"] += 1
            stagnation += 1
            trust_radius = max(1.0e-8, trust_radius * 0.35)
            damping = min(1.0e12, damping * 8.0)
            if stagnation >= 8:
                break
    if best.semantics_valid and best.relation_inf <= configuration.success_residual_inf:
        counters["reported_safe_endpoint"] = 1
        status = "safe_root"
    elif time.monotonic() >= deadline_monotonic:
        status = "deadline"
    else:
        status = "stalled_or_budget"
    return CandidateOutcome(best.x.copy(), status, counters)


__all__ = [
    "ANALYTIC_CPQR",
    "ANALYTIC_LSMR",
    "CONFIGURATIONS",
    "ADProgram",
    "CandidateOutcome",
    "Configuration",
    "Dual",
    "compile_program",
    "solve_local",
]
