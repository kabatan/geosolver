"""Type-directed lazy geometry expansion for compiled residual plans.

The frozen geometry objects validate numeric invariants in their constructors.
Those checks cannot be executed while compiler variables are SymPy symbols: a
comparison such as ``radius < 0`` is a symbolic relation, not a Python boolean.

This module provides a deliberately separate compile-time geometry context.
It preserves the frozen formulas and records numeric preconditions for later
qualification, but never asks a symbolic relation for its truth value.  The
support decision depends only on DSL operations, operand types, selector mode,
and this module's semantic ABI.  It never reads problem IDs or corpus metadata.

Intersection selection is intentionally outside this first ABI.  Candidate
ordering, exclusion tolerance, and selector-trace replay require their own
qualified implementation; encountering ``Intersect`` fails the whole symbolic
expansion rather than mixing execution backends within a problem.
"""

from __future__ import annotations

import ast
import contextlib
import signal
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sympy import (
    Abs,
    Max,
    Min,
    Piecewise,
    Symbol,
    acos,
    atan2,
    cos,
    pi,
    simplify,
    sin,
    sqrt,
    sympify,
)
from sympy.core.basic import Basic

SEMANTIC_ABI = "geotarget.lazy-symbolic-geometry/sympy-1.14-v1"


class UnsupportedLazyGeometry(RuntimeError):
    """The expression requires semantics outside the lazy geometry ABI."""


class LazyCompilationLimitExceeded(UnsupportedLazyGeometry):
    """A general compile resource limit was exceeded."""


@dataclass(frozen=True)
class LazyCompilationLimits:
    max_ast_nodes: int = 50_000
    # SymPy can spend superlinear time simplifying a new expression even when
    # the eventual DAG is modest.  Keep the accumulated object-boundary DAG
    # deliberately small and fall back before entering that regime.
    max_dag_nodes: int = 220
    max_expression_input_cost: int = 1_000
    wall_seconds: float = 0.045

    def __post_init__(self) -> None:
        if self.max_ast_nodes < 1:
            raise ValueError("max_ast_nodes must be positive")
        if self.max_dag_nodes < 1:
            raise ValueError("max_dag_nodes must be positive")
        if self.max_expression_input_cost < 1:
            raise ValueError("max_expression_input_cost must be positive")
        if self.wall_seconds <= 0 or not float(self.wall_seconds) < float("inf"):
            raise ValueError("wall_seconds must be positive and finite")


@dataclass(frozen=True)
class DeferredValidation:
    """A numeric constructor precondition that is undecidable at compile time."""

    kind: str
    expression: Any
    source: str


@dataclass(frozen=True)
class DeferredSelector:
    """A selector decision represented symbolically until numeric evaluation."""

    kind: str
    candidate_count: int
    selected_index: int | Any
    semantic_abi: str = SEMANTIC_ABI


@dataclass
class LazyGeometryState:
    """Per-compilation state; it must not be shared between problems."""

    limits: LazyCompilationLimits = field(default_factory=LazyCompilationLimits)
    validations: list[DeferredValidation] = field(default_factory=list)
    selectors: list[DeferredSelector] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)
    dag_node_count: int = 0
    maximum_expression_input_cost: int = 0
    _accounted_node_ids: set[int] = field(default_factory=set, repr=False)

    def require(self, kind: str, expression: Any, source: str) -> None:
        self.validations.append(DeferredValidation(kind, expression, source))

    def record_selector(self, kind: str, candidate_count: int, selected_index: Any) -> None:
        self.selectors.append(DeferredSelector(kind, candidate_count, selected_index))

    def check_wall(self, operator: str) -> None:
        elapsed = time.monotonic() - self.started_at
        if elapsed > self.limits.wall_seconds:
            raise LazyCompilationLimitExceeded(
                "compile wall limit exceeded: "
                f"operator={operator}, elapsed={elapsed:.6f}, "
                f"limit={self.limits.wall_seconds:.6f}"
            )

    def account(self, value: Any, operator: str) -> None:
        """Count unique DAG/object nodes while preserving shared subexpressions."""

        stack = [value]
        while stack:
            current = stack.pop()
            if isinstance(current, str | bytes | int | float | bool | type(None)):
                continue
            identity = id(current)
            if identity in self._accounted_node_ids:
                continue
            self._accounted_node_ids.add(identity)
            self.dag_node_count += 1
            if self.dag_node_count > self.limits.max_dag_nodes:
                raise LazyCompilationLimitExceeded(
                    "compile DAG node limit exceeded: "
                    f"operator={operator}, nodes={self.dag_node_count}, "
                    f"limit={self.limits.max_dag_nodes}"
                )
            if isinstance(current, Basic):
                stack.extend(current.args)
            elif isinstance(current, LazyPoint):
                stack.extend((current.x, current.y))
            elif isinstance(current, LazyLine):
                stack.extend((current.a, current.b, current.c))
            elif isinstance(current, LazyCircle):
                stack.extend((current.center, current.radius))
            elif isinstance(current, LazySegment):
                stack.extend((current.p1, current.p2))
            elif isinstance(current, tuple | list):
                stack.extend(current)
        self.check_wall(operator)

    def check_expression_inputs(
        self,
        expression: str,
        context: Mapping[str, Any],
        operator: str,
    ) -> None:
        """Bound repeated-subtree work before SymPy starts eager simplification."""

        names = {
            node.id
            for node in ast.walk(ast.parse(expression, mode="eval"))
            if isinstance(node, ast.Name) and node.id in context
        }
        stack = [context[name] for name in names]
        cost = 0
        while stack:
            current = stack.pop()
            if isinstance(current, str | bytes | int | float | bool | type(None)):
                continue
            cost += 1
            if cost > self.limits.max_expression_input_cost:
                raise LazyCompilationLimitExceeded(
                    "compile expression input-cost limit exceeded: "
                    f"operator={operator}, cost={cost}, "
                    f"limit={self.limits.max_expression_input_cost}"
                )
            if isinstance(current, Basic):
                # Do not deduplicate: repeated subtrees predict the work of
                # eager algebraic reconstruction better than unique DAG size.
                stack.extend(current.args)
            elif isinstance(current, LazyPoint):
                stack.extend((current.x, current.y))
            elif isinstance(current, LazyLine):
                stack.extend((current.a, current.b, current.c))
            elif isinstance(current, LazyCircle):
                stack.extend((current.center, current.radius))
            elif isinstance(current, LazySegment):
                stack.extend((current.p1, current.p2))
            elif isinstance(current, tuple | list):
                stack.extend(current)
        self.maximum_expression_input_cost = max(self.maximum_expression_input_cost, cost)
        self.check_wall(operator)


@contextlib.contextmanager
def _expression_deadline(state: LazyGeometryState, operator: str):
    """Apply a hard POSIX deadline where it is safe, otherwise check cooperatively."""

    state.check_wall(operator)
    remaining = state.limits.wall_seconds - (time.monotonic() - state.started_at)
    can_arm = (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "setitimer")
        and signal.getitimer(signal.ITIMER_REAL)[0] == 0
    )
    if not can_arm:
        yield
        state.check_wall(operator)
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise LazyCompilationLimitExceeded(
            "compile wall limit exceeded: "
            f"operator={operator}, nodes={state.dag_node_count}, "
            f"limit={state.limits.wall_seconds:.6f}"
        )

    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, remaining))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    state.check_wall(operator)


@dataclass(frozen=True, eq=False)
class LazyPoint:
    x: Any
    y: Any

    def __add__(self, other: LazyPoint) -> LazyPoint:
        return LazyPoint(self.x + other.x, self.y + other.y)

    def __sub__(self, other: LazyPoint) -> LazyPoint:
        return LazyPoint(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: Any) -> LazyPoint:
        return LazyPoint(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: Any) -> LazyPoint:
        return LazyPoint(self.x / scalar, self.y / scalar)

    def __neg__(self) -> LazyPoint:
        return LazyPoint(-self.x, -self.y)

    def distance_to(self, other: LazyPoint) -> Any:
        dx = self.x - other.x
        dy = self.y - other.y
        return sqrt(dx**2 + dy**2)

    def dot(self, other: LazyPoint) -> Any:
        return self.x * other.x + self.y * other.y

    def cross(self, other: LazyPoint) -> Any:
        return self.x * other.y - self.y * other.x

    def norm(self) -> Any:
        return sqrt(self.x**2 + self.y**2)


@dataclass(frozen=True, eq=False)
class LazyLine:
    a: Any
    b: Any
    c: Any

    def distance_to_point(self, point: LazyPoint) -> Any:
        return Abs(self.a * point.x + self.b * point.y + self.c)


@dataclass(frozen=True, eq=False)
class LazyCircle:
    center: LazyPoint
    radius: Any

    def area(self) -> Any:
        return pi * self.radius**2


@dataclass(frozen=True, eq=False)
class LazySegment:
    p1: LazyPoint
    p2: LazyPoint

    def length(self) -> Any:
        return self.p1.distance_to(self.p2)


def _point(value: Any, y: Any | None = None) -> LazyPoint:
    if y is None:
        if isinstance(value, LazyPoint):
            return value
        if isinstance(value, Sequence) and len(value) == 2:
            return LazyPoint(sympify(value[0]), sympify(value[1]))
        raise TypeError("Point requires two scalar coordinates")
    return LazyPoint(sympify(value), sympify(y))


def _line(state: LazyGeometryState, first: Any, second: Any, third: Any = None) -> LazyLine:
    if isinstance(first, LazyPoint) and isinstance(second, LazyPoint) and third is None:
        a = first.y - second.y
        b = second.x - first.x
        c = first.x * second.y - second.x * first.y
    elif third is not None:
        a, b, c = sympify(first), sympify(second), sympify(third)
    else:
        raise TypeError("Line requires two Points or three coefficients")
    norm = sqrt(a**2 + b**2)
    state.require("nonzero", norm, "Line.norm")
    return LazyLine(a / norm, b / norm, c / norm)


def _circle(state: LazyGeometryState, center: Any, radius: Any) -> LazyCircle:
    if not isinstance(center, LazyPoint):
        raise TypeError("Circle center must be a Point")
    radius = sympify(radius)
    state.require("nonnegative", radius, "Circle.radius")
    return LazyCircle(center, radius)


def _distance(first: Any, second: Any = None) -> Any:
    if second is None and isinstance(first, LazyPoint):
        return first.norm()
    if isinstance(first, LazyPoint) and isinstance(second, LazyPoint):
        return first.distance_to(second)
    if isinstance(first, LazyPoint) and isinstance(second, LazyLine):
        return second.distance_to_point(first)
    if isinstance(first, LazyLine) and isinstance(second, LazyPoint):
        return first.distance_to_point(second)
    if isinstance(first, LazyPoint) and isinstance(second, LazyCircle):
        return Abs(first.distance_to(second.center) - second.radius)
    if isinstance(first, LazyCircle) and isinstance(second, LazyPoint):
        return Abs(second.distance_to(first.center) - first.radius)
    raise TypeError("unsupported Distance operand types")


def _midpoint(first: Any, second: Any = None) -> LazyPoint:
    if second is None and isinstance(first, LazyCircle):
        return first.center
    if isinstance(first, LazyPoint) and isinstance(second, LazyPoint):
        return LazyPoint((first.x + second.x) / 2, (first.y + second.y) / 2)
    raise TypeError("unsupported Midpoint operand types")


def _angle(first: Any, second: Any = None, third: Any = None) -> Any:
    if all(isinstance(point, LazyPoint) for point in (first, second, third)):
        ba = first - second
        bc = third - second
        return atan2(Abs(ba.cross(bc)), ba.dot(bc))
    if isinstance(first, LazyLine) and isinstance(second, LazyLine) and third is None:
        return acos(Abs(first.a * second.a + first.b * second.b))
    raise TypeError("unsupported Angle operand types")


def _area(*objects: Any) -> Any:
    if len(objects) == 1 and isinstance(objects[0], LazyCircle):
        return objects[0].area()
    if len(objects) >= 3 and all(isinstance(point, LazyPoint) for point in objects):
        total: Any = 0
        for index, first in enumerate(objects):
            second = objects[(index + 1) % len(objects)]
            total += first.x * second.y - first.y * second.x
        return Abs(total) / 2
    raise TypeError("Area requires a Circle or at least three Points")


def _on_line(point: LazyPoint, first: Any, second: Any = None, ordered: bool = False) -> Any:
    if isinstance(first, LazyLine) and second is None:
        return first.distance_to_point(point)
    if isinstance(first, LazyPoint) and isinstance(second, LazyPoint):
        cross = (first - point).cross(second - point)
        if ordered:
            order = _distance(point, first) + _distance(first, second) - _distance(point, second)
            return cross**2 + order**2
        return cross
    raise TypeError("unsupported OnLine operand types")


def _circumcenter(state: LazyGeometryState, a: LazyPoint, b: LazyPoint, c: LazyPoint) -> LazyPoint:
    x1, y1, x2, y2, x3, y3 = a.x, a.y, b.x, b.y, c.x, c.y
    denominator = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    state.require("nonzero", denominator, "Circumcenter.denominator")
    ux = (
        (x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)
    ) / denominator
    uy = (
        (x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)
    ) / denominator
    return LazyPoint(ux, uy)


def _orthocenter(state: LazyGeometryState, a: LazyPoint, b: LazyPoint, c: LazyPoint) -> LazyPoint:
    dx_bc, dy_bc = c.x - b.x, c.y - b.y
    k1 = dx_bc * a.x + dy_bc * a.y
    dx_ca, dy_ca = a.x - c.x, a.y - c.y
    k2 = dx_ca * b.x + dy_ca * b.y
    determinant = dx_bc * dy_ca - dx_ca * dy_bc
    state.require("nonzero", determinant, "Orthocenter.determinant")
    return LazyPoint(
        (k1 * dy_ca - k2 * dy_bc) / determinant,
        (dx_bc * k2 - dx_ca * k1) / determinant,
    )


def _circumcircle(
    state: LazyGeometryState,
    circle_factory: Callable[[Any, Any], LazyCircle],
    a: LazyPoint,
    b: LazyPoint,
    c: LazyPoint,
) -> LazyCircle:
    center = _circumcenter(state, a, b, c)
    return circle_factory(center, center.distance_to(a))


def _incenter(state: LazyGeometryState, a: LazyPoint, b: LazyPoint, c: LazyPoint) -> LazyPoint:
    side_a = b.distance_to(c)
    side_b = c.distance_to(a)
    side_c = a.distance_to(b)
    perimeter = side_a + side_b + side_c
    state.require("nonzero", perimeter, "Incenter.perimeter")
    return LazyPoint(
        (side_a * a.x + side_b * b.x + side_c * c.x) / perimeter,
        (side_a * a.y + side_b * b.y + side_c * c.y) / perimeter,
    )


def _incircle(state: LazyGeometryState, a: LazyPoint, b: LazyPoint, c: LazyPoint) -> LazyCircle:
    center = _incenter(state, a, b, c)
    double_area = Abs(a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
    perimeter = b.distance_to(c) + c.distance_to(a) + a.distance_to(b)
    state.require("nonzero", perimeter, "Incircle.perimeter")
    return _circle(state, center, double_area / perimeter)


def _incircle_contact(a: LazyPoint, b: LazyPoint, c: LazyPoint, side: Any = None) -> Any:
    side_a, side_b, side_c = b.distance_to(c), c.distance_to(a), a.distance_to(b)
    semiperimeter = (side_a + side_b + side_c) / 2
    d = b + (c - b) * ((semiperimeter - side_b) / side_a)
    e = c + (a - c) * ((semiperimeter - side_c) / side_b)
    f = a + (b - a) * ((semiperimeter - side_a) / side_c)
    if side is None:
        return [d, e, f]
    if isinstance(side, str | int) and side in ("BC", 0):
        return d
    if isinstance(side, str | int) and side in ("CA", 1):
        return e
    if isinstance(side, str | int) and side in ("AB", 2):
        return f
    raise UnsupportedLazyGeometry("symbolic point-valued side selectors are unsupported")


def _excenter(
    state: LazyGeometryState, a: LazyPoint, b: LazyPoint, c: LazyPoint, vertex: Any = None
) -> LazyPoint:
    if isinstance(vertex, str | int) and vertex in ("B", 1):
        return _excenter(state, b, c, a)
    if isinstance(vertex, str | int) and vertex in ("C", 2):
        return _excenter(state, c, a, b)
    if vertex is not None and not (isinstance(vertex, str | int) and vertex in ("A", 0)):
        raise UnsupportedLazyGeometry("symbolic point-valued excenter selector is unsupported")
    side_a, side_b, side_c = b.distance_to(c), c.distance_to(a), a.distance_to(b)
    denominator = -side_a + side_b + side_c
    state.require("nonzero", denominator, "Excenter.denominator")
    return LazyPoint(
        (-side_a * a.x + side_b * b.x + side_c * c.x) / denominator,
        (-side_a * a.y + side_b * b.y + side_c * c.y) / denominator,
    )


def _line_line_candidates(
    state: LazyGeometryState, first: LazyLine, second: LazyLine
) -> list[LazyPoint]:
    determinant = first.a * second.b - second.a * first.b
    state.require("nonzero", determinant, "Intersect.LineLine.determinant")
    return [
        LazyPoint(
            (first.b * second.c - second.b * first.c) / determinant,
            (first.c * second.a - second.c * first.a) / determinant,
        )
    ]


def _line_circle_candidates(line: LazyLine, circle: LazyCircle) -> list[LazyPoint]:
    a, b, c = line.a, line.b, line.c
    xc, yc, radius = circle.center.x, circle.center.y, circle.radius
    shifted = a * xc + b * yc + c
    divisor = a**2 + b**2
    distance_squared = shifted**2 / divisor
    delta = radius**2 - distance_squared
    multiplier = sqrt(Max(0, delta) / divisor)
    x0 = -a * shifted / divisor
    y0 = -b * shifted / divisor
    return [
        LazyPoint(xc + x0 + b * multiplier, yc + y0 - a * multiplier),
        LazyPoint(xc + x0 - b * multiplier, yc + y0 + a * multiplier),
    ]


def _circle_circle_candidates(
    state: LazyGeometryState, first: LazyCircle, second: LazyCircle
) -> list[LazyPoint]:
    x1, y1, radius1 = first.center.x, first.center.y, first.radius
    x2, y2, radius2 = second.center.x, second.center.y, second.radius
    distance_squared = (x1 - x2) ** 2 + (y1 - y2) ** 2
    distance = sqrt(distance_squared)
    state.require("nonzero", distance, "Intersect.CircleCircle.center_distance")
    along = (radius1**2 - radius2**2 + distance_squared) / (2 * distance)
    height = sqrt(Max(0, radius1**2 - along**2))
    x0 = x1 + along * (x2 - x1) / distance
    y0 = y1 + along * (y2 - y1) / distance
    offset_x = -(y2 - y1) * (height / distance)
    offset_y = (x2 - x1) * (height / distance)
    return [
        LazyPoint(x0 + offset_x, y0 + offset_y),
        LazyPoint(x0 - offset_x, y0 - offset_y),
    ]


def _distance_squared(first: LazyPoint, second: LazyPoint) -> Any:
    dx = first.x - second.x
    dy = first.y - second.y
    return dx * dx + dy * dy


def _select_candidates(
    state: LazyGeometryState,
    candidates: list[LazyPoint],
    *,
    n: Any = None,
    exclude: Any = None,
    near: Any = None,
    far: Any = None,
) -> LazyPoint | list[LazyPoint]:
    if exclude is not None:
        if not isinstance(exclude, LazyPoint):
            raise TypeError("exclude selector requires a Point")
        matching = [
            index
            for index, candidate in enumerate(candidates)
            if simplify(candidate.x - exclude.x) == 0 and simplify(candidate.y - exclude.y) == 0
        ]
        # This is deliberately proof-based.  The frozen approximate Point
        # equality remains the authority whenever symbolic identity cannot
        # establish exactly which candidate is removed.
        if len(matching) > 1:
            raise UnsupportedLazyGeometry("exclude candidate identity is not symbolically unique")
        selected_index = 1 - matching[0] if matching else 0
        # With no symbolic match, use the frozen selector-trace ABI's stable
        # original-candidate ordinal.  The runtime authority records ordinal
        # zero for this fallback selection; differential qualification remains
        # mandatory before this shadow path can be enabled.
        remaining = [candidates[selected_index]]
        if n not in (None, 1):
            raise UnsupportedLazyGeometry("exclude ordinal is outside candidate range")
        state.record_selector("exclude", len(candidates), selected_index)
        return remaining[0]
    active_selectors = sum(value is not None for value in (near, far))
    if active_selectors > 1:
        raise UnsupportedLazyGeometry("near and far selectors are mutually exclusive")
    if n is not None:
        if not isinstance(n, int) or isinstance(n, bool):
            raise UnsupportedLazyGeometry("intersection ordinal must be a literal integer")
        if n < 1 or n > len(candidates):
            raise UnsupportedLazyGeometry("intersection ordinal is outside candidate range")
        if near is None and far is None:
            state.record_selector("n", len(candidates), n - 1)
            return candidates[n - 1]
    if len(candidates) == 1:
        selector = "near" if near is not None else "far" if far is not None else "single"
        state.record_selector(selector, 1, 0)
        return candidates[0]
    if near is None and far is None:
        return candidates

    reference = near if near is not None else far
    if not isinstance(reference, LazyPoint):
        raise TypeError("near/far selector requires a Point")
    first_distance = _distance_squared(candidates[0], reference)
    second_distance = _distance_squared(candidates[1], reference)
    choose_first = (
        first_distance <= second_distance if near is not None else first_distance >= second_distance
    )
    first, second = candidates
    selected = LazyPoint(
        Piecewise((first.x, choose_first), (second.x, True)),
        Piecewise((first.y, choose_first), (second.y, True)),
    )
    selector_kind = "near" if near is not None else "far"
    state.record_selector(selector_kind, 2, Piecewise((0, choose_first), (1, True)))
    # `n` is applied after sorting, exactly as in the frozen selector.  With
    # two candidates n=2 means the opposite branch.
    if n == 2:
        selected = LazyPoint(
            Piecewise((second.x, choose_first), (first.x, True)),
            Piecewise((second.y, choose_first), (first.y, True)),
        )
    return selected


def _intersect(
    state: LazyGeometryState,
    first: Any,
    second: Any,
    *,
    n: Any = None,
    exclude: Any = None,
    near: Any = None,
    far: Any = None,
) -> LazyPoint | list[LazyPoint]:
    if isinstance(first, LazyLine) and isinstance(second, LazyLine):
        candidates = _line_line_candidates(state, first, second)
    elif isinstance(first, LazyLine) and isinstance(second, LazyCircle):
        candidates = _line_circle_candidates(first, second)
    elif isinstance(first, LazyCircle) and isinstance(second, LazyLine):
        candidates = _line_circle_candidates(second, first)
    elif isinstance(first, LazyCircle) and isinstance(second, LazyCircle):
        candidates = _circle_circle_candidates(state, first, second)
    else:
        raise UnsupportedLazyGeometry("unsupported Intersect operand types")
    return _select_candidates(
        state,
        candidates,
        n=n,
        exclude=exclude,
        near=near,
        far=far,
    )


def build_lazy_geometry_context(
    state: LazyGeometryState | None = None,
) -> tuple[dict[str, Callable[..., Any]], LazyGeometryState]:
    """Return the general compile-time geometry context and its validation log."""

    state = state or LazyGeometryState()
    point = _point

    def line(first: Any, second: Any, third: Any = None) -> LazyLine:
        return _line(state, first, second, third)

    def circle(center: Any, radius: Any) -> LazyCircle:
        return _circle(state, center, radius)

    def point_on_line(value: LazyLine, parameter: Any) -> LazyPoint:
        denominator = value.a**2 + value.b**2
        return LazyPoint(
            -value.a * value.c / denominator - value.b * parameter,
            -value.b * value.c / denominator + value.a * parameter,
        )

    def point_on_segment(first: LazyPoint, second: LazyPoint, parameter: Any) -> LazyPoint:
        return LazyPoint(
            first.x + parameter * (second.x - first.x),
            first.y + parameter * (second.y - first.y),
        )

    def point_on_circle(value: LazyCircle, parameter: Any) -> LazyPoint:
        angle = 2 * pi * parameter
        return LazyPoint(
            value.center.x + value.radius * cos(angle),
            value.center.y + value.radius * sin(angle),
        )

    def foot(first: Any, second: Any) -> LazyPoint:
        value, point_value = (first, second) if isinstance(first, LazyLine) else (second, first)
        denominator = value.a**2 + value.b**2
        return LazyPoint(
            (value.b * (value.b * point_value.x - value.a * point_value.y) - value.a * value.c)
            / denominator,
            (value.a * (-value.b * point_value.x + value.a * point_value.y) - value.b * value.c)
            / denominator,
        )

    def parallel_line(first: Any, second: Any) -> LazyLine:
        value, point_value = (first, second) if isinstance(first, LazyLine) else (second, first)
        return line(value.a, value.b, -(value.a * point_value.x + value.b * point_value.y))

    def perpendicular_line(first: Any, second: Any) -> LazyLine:
        value, point_value = (first, second) if isinstance(first, LazyLine) else (second, first)
        a, b = value.b, -value.a
        return line(a, b, -(a * point_value.x + b * point_value.y))

    def perpendicular_bisector(first: LazyPoint, second: LazyPoint) -> LazyLine:
        mid_x, mid_y = (first.x + second.x) / 2, (first.y + second.y) / 2
        a, b = second.x - first.x, -(first.y - second.y)
        return line(a, b, -(a * mid_x + b * mid_y))

    def angle_bisector(a: LazyPoint, b: LazyPoint, c: LazyPoint) -> LazyLine:
        ba, bc = a - b, c - b
        norm_ba, norm_bc = ba.norm(), bc.norm()
        state.require("nonzero", norm_ba, "AngleBisector.BA")
        state.require("nonzero", norm_bc, "AngleBisector.BC")
        direction = ba / norm_ba + bc / norm_bc
        state.require("nonzero_vector", (direction.x, direction.y), "AngleBisector.direction")
        target = b + direction
        return line(b, target)

    def reflect(value: LazyPoint, axis: Any) -> LazyPoint:
        if isinstance(axis, LazyPoint):
            return LazyPoint(2 * axis.x - value.x, 2 * axis.y - value.y)
        if isinstance(axis, LazyLine):
            projection = foot(axis, value)
            return LazyPoint(2 * projection.x - value.x, 2 * projection.y - value.y)
        raise TypeError("Reflect supports Point axes and Line axes")

    def contact_point(*args: Any, **kwargs: Any) -> Any:
        if (
            len(args) == 2
            and not kwargs
            and {type(args[0]), type(args[1])} == {LazyCircle, LazyLine}
        ):
            circle_value = args[0] if isinstance(args[0], LazyCircle) else args[1]
            line_value = args[1] if isinstance(args[1], LazyLine) else args[0]
            return foot(line_value, circle_value.center)
        return _incircle_contact(*args, **kwargs)

    def excircle(a: LazyPoint, b: LazyPoint, c: LazyPoint, vertex: Any = None) -> LazyCircle:
        center = _excenter(state, a, b, c, vertex)
        if isinstance(vertex, str | int) and vertex in ("B", 1):
            a, b, c = b, c, a
        elif isinstance(vertex, str | int) and vertex in ("C", 2):
            a, b, c = c, a, b
        double_area = Abs(a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
        denominator = -b.distance_to(c) + c.distance_to(a) + a.distance_to(b)
        state.require("nonzero", denominator, "Excircle.denominator")
        return circle(center, double_area / denominator)

    context: dict[str, Callable[..., Any]] = {
        "Point": point,
        "Line": line,
        "LineThrough": line,
        "Circle": circle,
        "Distance": _distance,
        "Midpoint": _midpoint,
        "Angle": _angle,
        "Radius": lambda value: value.radius,
        "Center": lambda value: value.center,
        "Area": _area,
        "Vector": lambda first, second: second - first,
        "Dot": lambda first, second: first.dot(second),
        "OnLine": _on_line,
        "Collinear": lambda a, b, c, ordered=False: _on_line(a, b, c, ordered),
        "OnCircle": lambda point_value, value: _distance(point_value, value.center) - value.radius,
        "OnSegment": lambda point_value, first, second: _distance(first, point_value)
        + _distance(point_value, second)
        - _distance(first, second),
        "PointOnLine": point_on_line,
        "PointOnSegment": point_on_segment,
        "PointOnCircle": point_on_circle,
        "CircleThroughPoint": lambda center, point_value: circle(
            center, center.distance_to(point_value)
        ),
        "CircleThroughThreePoints": lambda a, b, c: _circumcircle(state, circle, a, b, c),
        "Circumcenter": lambda a, b, c: _circumcenter(state, a, b, c),
        "Circumcircle": lambda a, b, c: _circumcircle(state, circle, a, b, c),
        "Orthocenter": lambda a, b, c: _orthocenter(state, a, b, c),
        "Centroid": lambda a, b, c: LazyPoint((a.x + b.x + c.x) / 3, (a.y + b.y + c.y) / 3),
        "Incenter": lambda a, b, c: _incenter(state, a, b, c),
        "Incircle": lambda a, b, c: _incircle(state, a, b, c),
        "IncircleContactPoint": _incircle_contact,
        "ContactPoint": contact_point,
        "Excenter": lambda a, b, c, vertex=None: _excenter(state, a, b, c, vertex),
        "Excircle": excircle,
        "FootOfPerpendicular": foot,
        "ParallelLine": parallel_line,
        "PerpendicularLine": perpendicular_line,
        "PerpendicularBisector": perpendicular_bisector,
        "AngleBisector": angle_bisector,
        "Reflect": reflect,
        "Parallel": lambda first, second: first.a * second.b - second.a * first.b,
        "Perpendicular": lambda first, second: first.a * second.a + first.b * second.b,
        "IsTangent": lambda first, second: (
            Abs(_distance(second.center, first) - second.radius)
            if isinstance(first, LazyLine) and isinstance(second, LazyCircle)
            else Abs(_distance(first.center, second) - first.radius)
            if isinstance(first, LazyCircle) and isinstance(second, LazyLine)
            else Min(
                Abs(_distance(first.center, second.center) - (first.radius + second.radius)),
                Abs(_distance(first.center, second.center) - Abs(first.radius - second.radius)),
            )
        ),
        "Intersect": lambda first, second, **selectors: _intersect(
            state, first, second, **selectors
        ),
    }
    return context, state


_SCALAR_CALLS = frozenset({"abs", "cos", "float", "int", "max", "min", "sin", "sqrt"})


def _preflight_bundle(
    bundle: Any,
    *,
    geometry_calls: set[str],
    limits: LazyCompilationLimits,
) -> None:
    """Reject unsupported AST semantics before constructing any symbolic DAG."""

    expressions = [item.expr for item in bundle.spec.construction]
    expressions.extend(bundle.spec.constraints)
    expressions.extend(target for target in bundle.targets if isinstance(target, str))
    ast_nodes = 0
    allowed_calls = geometry_calls | set(_SCALAR_CALLS)
    for expression in expressions:
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            ast_nodes += 1
            if ast_nodes > limits.max_ast_nodes:
                raise LazyCompilationLimitExceeded(
                    "compile AST node limit exceeded: "
                    f"operator=preflight, nodes={ast_nodes}, "
                    f"limit={limits.max_ast_nodes}"
                )
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name):
                raise UnsupportedLazyGeometry(
                    "unsupported call in preflight: operator=attribute_call"
                )
            call_name = node.func.id
            if call_name not in allowed_calls:
                raise UnsupportedLazyGeometry(
                    f"unsupported call in preflight: operator={call_name}"
                )
            if call_name != "Intersect":
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            unknown = set(keywords) - {"n", "exclude", "near", "far"}
            if unknown:
                raise UnsupportedLazyGeometry(
                    f"unsupported Intersect selector in preflight: selector={sorted(unknown)[0]}"
                )
            if "exclude" in keywords:
                raise UnsupportedLazyGeometry(
                    "exclude selection requires the selector-trace semantic ABI"
                )
            if "near" in keywords and "far" in keywords:
                raise UnsupportedLazyGeometry("near and far selectors are mutually exclusive")
            if "n" in keywords:
                ordinal = keywords["n"]
                if not (
                    isinstance(ordinal, ast.Constant)
                    and isinstance(ordinal.value, int)
                    and not isinstance(ordinal.value, bool)
                ):
                    raise UnsupportedLazyGeometry("intersection ordinal must be a literal integer")


@dataclass(frozen=True)
class LazyExpansion:
    symbols: tuple[Symbol, ...]
    sides: tuple[tuple[Any, Any], ...]
    validations: tuple[DeferredValidation, ...]
    selectors: tuple[DeferredSelector, ...]
    dag_node_count: int
    maximum_expression_input_cost: int
    semantic_abi: str = SEMANTIC_ABI


@dataclass(frozen=True)
class LazyExpansionResult:
    """Whole-problem support decision for callers with a reference fallback."""

    expansion: LazyExpansion | None
    fallback_reason: str | None

    @property
    def supported(self) -> bool:
        return self.expansion is not None


def expand_bundle_symbolically(
    bundle: Any,
    *,
    limits: LazyCompilationLimits | None = None,
) -> LazyExpansion:
    """Expand a V15 bundle without invoking numeric constructor validation."""

    from geosolver.ir.compiler import safe_eval_expr

    state = LazyGeometryState(limits=limits or LazyCompilationLimits())
    geometry_context, state = build_lazy_geometry_context(state)
    with _expression_deadline(state, "preflight"):
        _preflight_bundle(
            bundle,
            geometry_calls=set(geometry_context),
            limits=state.limits,
        )
    symbols = tuple(Symbol(name) for name in bundle.var_names)
    context = dict(bundle.base_context)
    context.update(geometry_context)
    context.update(dict(zip(bundle.var_names, symbols, strict=True)))
    for item in bundle.spec.construction:
        with _expression_deadline(state, "construction"):
            state.check_expression_inputs(item.expr, context, "construction")
            value = safe_eval_expr(item.expr, context)
            state.account(value, "construction")
        context[item.name] = value
    sides: list[tuple[Any, Any]] = []
    for left_text, right_source in zip(bundle.spec.constraints, bundle.targets, strict=True):
        with _expression_deadline(state, "constraint"):
            state.check_expression_inputs(left_text, context, "constraint")
            if isinstance(right_source, str):
                state.check_expression_inputs(right_source, context, "constraint_target")
            left = safe_eval_expr(left_text, context)
            right = (
                safe_eval_expr(right_source, context)
                if isinstance(right_source, str)
                else sympify(right_source)
            )
            scalar_types = Basic | int | float
            if not isinstance(left, scalar_types) or not isinstance(right, scalar_types):
                raise UnsupportedLazyGeometry(
                    "constraint side did not reduce to a scalar expression"
                )
            state.account((left, right), "constraint")
        sides.append((left, right))
    return LazyExpansion(
        symbols,
        tuple(sides),
        tuple(state.validations),
        tuple(state.selectors),
        state.dag_node_count,
        state.maximum_expression_input_cost,
    )


def try_expand_bundle_symbolically(
    bundle: Any,
    *,
    limits: LazyCompilationLimits | None = None,
) -> LazyExpansionResult:
    """Fail closed at problem granularity without obscuring the reason."""

    try:
        return LazyExpansionResult(expand_bundle_symbolically(bundle, limits=limits), None)
    except Exception as error:
        return LazyExpansionResult(None, f"{type(error).__name__}: {error}")


def lazy_geometry_manifest() -> Mapping[str, Any]:
    return {
        "semantic_abi": SEMANTIC_ABI,
        "case_specific_routing": False,
        "support_inputs": ["ast_opcode", "operand_type", "selector_kind", "semantic_abi"],
        "intersection_policy": "LL_LC_CL_CC_n_near_far; exclude_fails_closed",
        "validation_policy": "deferred_numeric_preconditions",
    }
