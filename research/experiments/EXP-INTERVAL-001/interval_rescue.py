"""Truth-blind, capability-limited interval/Krawczyk proposal lane.

This is deliberately a disposable experiment, not a second answer authority.
Only expressions whose complete DAG can be interval-evaluated enter the lane.
Every point emitted here must still pass the existing local solver and canonical
source replay before it can affect a solve result.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import time
from typing import Callable, Iterable, Sequence


SUPPORTED_OPS = frozenset({"const", "var", "add", "sub", "mul", "neg", "pow", "div"})
EXPECTED_ARITY = {"const": 0, "var": 0, "neg": 1, "pow": 1, "add": 2, "sub": 2, "mul": 2, "div": 2}
UNSUPPORTED_OPS = frozenset(
    {"abs", "branch", "callback", "cos", "exp", "log", "max", "min", "opaque", "sin", "sqrt"}
)


class IntervalFailure(ValueError):
    """A safe failure of the validated interval path."""


def _down(value: float) -> float:
    if math.isnan(value):
        raise IntervalFailure("NaN interval endpoint")
    return math.nextafter(value, -math.inf)


def _up(value: float) -> float:
    if math.isnan(value):
        raise IntervalFailure("NaN interval endpoint")
    return math.nextafter(value, math.inf)


@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lo) and math.isfinite(self.hi) and self.lo <= self.hi):
            raise IntervalFailure("interval must be finite and ordered")

    @classmethod
    def point(cls, value: float) -> "Interval":
        value = float(value)
        if not math.isfinite(value):
            raise IntervalFailure("point interval must be finite")
        return cls(value, value)

    def __add__(self, other: "Interval") -> "Interval":
        return Interval(_down(self.lo + other.lo), _up(self.hi + other.hi))

    def __sub__(self, other: "Interval") -> "Interval":
        return Interval(_down(self.lo - other.hi), _up(self.hi - other.lo))

    def __neg__(self) -> "Interval":
        return Interval(-self.hi, -self.lo)

    def __mul__(self, other: "Interval") -> "Interval":
        products = (
            self.lo * other.lo,
            self.lo * other.hi,
            self.hi * other.lo,
            self.hi * other.hi,
        )
        return Interval(_down(min(products)), _up(max(products)))

    def reciprocal(self) -> "Interval":
        if self.contains(0.0):
            raise IntervalFailure("division interval contains zero")
        values = (1.0 / self.lo, 1.0 / self.hi)
        return Interval(_down(min(values)), _up(max(values)))

    def __truediv__(self, other: "Interval") -> "Interval":
        return self * other.reciprocal()

    def pow_int(self, exponent: int) -> "Interval":
        if exponent < 0:
            return self.pow_int(-exponent).reciprocal()
        if exponent == 0:
            return Interval.point(1.0)
        if exponent % 2 == 1:
            return Interval(_down(self.lo**exponent), _up(self.hi**exponent))
        maximum = max(abs(self.lo), abs(self.hi)) ** exponent
        minimum = 0.0 if self.contains(0.0) else min(abs(self.lo), abs(self.hi)) ** exponent
        return Interval(_down(minimum), _up(maximum))

    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    def midpoint(self) -> float:
        return self.lo + (self.hi - self.lo) * 0.5

    @property
    def width(self) -> float:
        return self.hi - self.lo

    def strictly_inside(self, other: "Interval") -> bool:
        return other.lo < self.lo and self.hi < other.hi

    def intersection(self, other: "Interval") -> "Interval":
        lo = max(self.lo, other.lo)
        hi = min(self.hi, other.hi)
        if lo > hi:
            raise IntervalFailure("empty interval intersection")
        return Interval(lo, hi)


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple["Expr", ...] = ()
    value: float | int | None = None

    def __add__(self, other: object) -> "Expr":
        return Expr("add", (self, as_expr(other)))

    def __radd__(self, other: object) -> "Expr":
        return as_expr(other) + self

    def __sub__(self, other: object) -> "Expr":
        return Expr("sub", (self, as_expr(other)))

    def __rsub__(self, other: object) -> "Expr":
        return as_expr(other) - self

    def __mul__(self, other: object) -> "Expr":
        return Expr("mul", (self, as_expr(other)))

    def __rmul__(self, other: object) -> "Expr":
        return as_expr(other) * self

    def __truediv__(self, other: object) -> "Expr":
        return Expr("div", (self, as_expr(other)))

    def __rtruediv__(self, other: object) -> "Expr":
        return as_expr(other) / self

    def __neg__(self) -> "Expr":
        return Expr("neg", (self,))

    def __pow__(self, exponent: int) -> "Expr":
        if not isinstance(exponent, int):
            return Expr("unsupported-power", (self,))
        return Expr("pow", (self,), exponent)


def Var(index: int) -> Expr:  # noqa: N802 - fixture DSL intentionally mirrors algebra
    return Expr("var", value=index)


def Const(value: float) -> Expr:  # noqa: N802
    return Expr("const", value=float(value))


def unsupported(op: str, *args: Expr) -> Expr:
    return Expr(op, tuple(args))


def as_expr(value: object) -> Expr:
    if isinstance(value, Expr):
        return value
    if isinstance(value, (int, float)):
        return Const(float(value))
    raise TypeError(f"cannot convert {type(value).__name__} to Expr")


@dataclass(frozen=True)
class Problem:
    residuals: tuple[Expr, ...]
    bounds: tuple[tuple[float, float], ...]
    source_kind: str = "validated-dag"
    branch_state: str = "single"
    strict_guard_state: str = "interior"
    opaque_callbacks: bool = False


@dataclass(frozen=True)
class RescueConfig:
    max_dimension: int = 2
    max_box_width: float = 4.0
    max_box_volume: float = 16.0
    max_boxes: int = 32
    max_depth: int = 8
    max_seconds: float = 0.050
    max_proposals: int = 4
    total_launch_slots: int = 8
    minimum_baseline_fraction: float = 0.25
    singular_rcond_floor: float = 1.0e-12


@dataclass(frozen=True)
class Applicability:
    applicable: bool
    reason: str
    dimension: int


@dataclass(frozen=True)
class Proposal:
    point: tuple[float, ...]
    source_box: tuple[tuple[float, float], ...]
    enclosure: tuple[tuple[float, float], ...]
    certificate_kind: str = "krawczyk-strict-inclusion"
    authority: bool = False
    requires_local_solver: bool = True
    requires_canonical_source_replay: bool = True


@dataclass(frozen=True)
class RescueResult:
    status: str
    reason: str
    applicability: Applicability
    proposals: tuple[Proposal, ...]
    boxes_visited: int
    boxes_excluded: int
    boxes_split: int
    singular_midpoints: int
    krawczyk_attempts: int
    work_cap: int
    time_cap_seconds: float
    answer_promotions: int = 0


@dataclass(frozen=True)
class Launch:
    kind: str
    proposal: Proposal | None


@dataclass(frozen=True)
class PortfolioPlan:
    launches: tuple[Launch, ...]
    baseline_slots: int
    interval_slots: int
    minimum_baseline_slots: int


def _walk(expressions: Iterable[Expr]) -> Iterable[Expr]:
    pending = list(expressions)
    seen: set[int] = set()
    while pending:
        expression = pending.pop()
        identity = id(expression)
        if identity in seen:
            continue
        seen.add(identity)
        yield expression
        pending.extend(expression.args)


def _validate_config(config: RescueConfig) -> None:
    if config.max_dimension < 1 or config.max_boxes < 1 or config.max_depth < 0:
        raise ValueError("dimension/work/depth caps must be positive")
    if config.max_box_width <= 0 or config.max_box_volume <= 0 or config.max_seconds <= 0:
        raise ValueError("box/time caps must be positive")
    if config.max_proposals < 0 or config.total_launch_slots < 1:
        raise ValueError("proposal/launch caps are invalid")
    if not 0.0 <= config.minimum_baseline_fraction <= 1.0:
        raise ValueError("baseline fraction must be in [0, 1]")
    if not math.isfinite(config.singular_rcond_floor) or config.singular_rcond_floor <= 0:
        raise ValueError("singular threshold must be finite and positive")


def applicability(problem: Problem, config: RescueConfig = RescueConfig()) -> Applicability:
    """Decide from syntax/capabilities only; no truth or case identity is visible."""

    _validate_config(config)
    dimension = len(problem.bounds)
    if not 1 <= dimension <= config.max_dimension:
        return Applicability(False, "dimension-outside-cap", dimension)
    if len(problem.residuals) != dimension:
        return Applicability(False, "nonsquare-system", dimension)
    if problem.source_kind != "validated-dag" or problem.opaque_callbacks:
        return Applicability(False, "validated-dag-unavailable", dimension)
    if problem.branch_state != "single":
        return Applicability(False, "branch-crossing-or-unknown", dimension)
    if problem.strict_guard_state != "interior":
        return Applicability(False, "strict-guard-not-interior", dimension)

    volume = 1.0
    for lower, upper in problem.bounds:
        if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
            return Applicability(False, "invalid-or-unbounded-box", dimension)
        width = upper - lower
        if not math.isfinite(width) or width > config.max_box_width:
            return Applicability(False, "box-width-cap", dimension)
        volume *= width
    if not math.isfinite(volume) or volume > config.max_box_volume:
        return Applicability(False, "box-volume-cap", dimension)

    for expression in _walk(problem.residuals):
        if not isinstance(expression, Expr):
            return Applicability(False, "malformed-expression-node", dimension)
        if expression.op not in SUPPORTED_OPS:
            suffix = "transcendental" if expression.op in UNSUPPORTED_OPS else "unknown"
            return Applicability(False, f"unsupported-{suffix}-op:{expression.op}", dimension)
        if len(expression.args) != EXPECTED_ARITY[expression.op]:
            return Applicability(False, f"malformed-arity:{expression.op}", dimension)
        if expression.op == "var":
            if not isinstance(expression.value, int) or not 0 <= expression.value < dimension:
                return Applicability(False, "invalid-variable-index", dimension)
        elif expression.op == "const":
            if expression.value is None or not math.isfinite(float(expression.value)):
                return Applicability(False, "nonfinite-constant", dimension)
        elif expression.op == "pow":
            if not isinstance(expression.value, int) or not 0 <= expression.value <= 6:
                return Applicability(False, "unsupported-power", dimension)

    # Domain validation (not discovery work) catches division through zero.
    try:
        _evaluate(problem.residuals, _initial_box(problem), dimension)
    except (ArithmeticError, IndexError, TypeError, ValueError):
        return Applicability(False, "interval-domain-not-validated", dimension)
    return Applicability(True, "validated-low-dimensional-smooth-dag", dimension)


def _initial_box(problem: Problem) -> tuple[Interval, ...]:
    return tuple(Interval(float(lower), float(upper)) for lower, upper in problem.bounds)


def _evaluate(
    residuals: Sequence[Expr],
    box: Sequence[Interval],
    dimension: int,
) -> tuple[tuple[Interval, ...], tuple[tuple[Interval, ...], ...]]:
    cache: dict[int, tuple[Interval, tuple[Interval, ...]]] = {}
    zero = Interval.point(0.0)
    one = Interval.point(1.0)

    def visit(expression: Expr) -> tuple[Interval, tuple[Interval, ...]]:
        key = id(expression)
        if key in cache:
            return cache[key]
        if expression.op == "const":
            value = Interval.point(float(expression.value))
            gradient = (zero,) * dimension
        elif expression.op == "var":
            index = int(expression.value)
            value = box[index]
            gradient = tuple(one if item == index else zero for item in range(dimension))
        elif expression.op == "neg":
            child, child_gradient = visit(expression.args[0])
            value = -child
            gradient = tuple(-item for item in child_gradient)
        elif expression.op in {"add", "sub", "mul", "div"}:
            left, left_gradient = visit(expression.args[0])
            right, right_gradient = visit(expression.args[1])
            if expression.op == "add":
                value = left + right
                gradient = tuple(a + b for a, b in zip(left_gradient, right_gradient))
            elif expression.op == "sub":
                value = left - right
                gradient = tuple(a - b for a, b in zip(left_gradient, right_gradient))
            elif expression.op == "mul":
                value = left * right
                gradient = tuple(a * right + left * b for a, b in zip(left_gradient, right_gradient))
            else:
                value = left / right
                denominator = right.pow_int(2)
                gradient = tuple(
                    (a * right - left * b) / denominator
                    for a, b in zip(left_gradient, right_gradient)
                )
        elif expression.op == "pow":
            child, child_gradient = visit(expression.args[0])
            exponent = int(expression.value)
            value = child.pow_int(exponent)
            if exponent == 0:
                gradient = (zero,) * dimension
            else:
                coefficient = Interval.point(float(exponent))
                factor = coefficient * child.pow_int(exponent - 1)
                gradient = tuple(factor * item for item in child_gradient)
        else:
            raise IntervalFailure(f"unsupported expression op {expression.op}")
        cache[key] = value, gradient
        return value, gradient

    rows = tuple(visit(expression) for expression in residuals)
    return tuple(row[0] for row in rows), tuple(row[1] for row in rows)


def _inverse_point(matrix: Sequence[Sequence[float]], floor: float) -> tuple[tuple[float, ...], ...] | None:
    dimension = len(matrix)
    if dimension == 1:
        entry = matrix[0][0]
        if not math.isfinite(entry) or abs(entry) <= floor:
            return None
        return ((1.0 / entry,),)
    if dimension != 2:
        return None
    a, b = matrix[0]
    c, d = matrix[1]
    determinant = a * d - b * c
    scale = max(abs(a), abs(b), abs(c), abs(d), 1.0)
    if not math.isfinite(determinant) or abs(determinant) <= floor * scale * scale:
        return None
    inverse = ((d / determinant, -b / determinant), (-c / determinant, a / determinant))
    return inverse if all(math.isfinite(value) for row in inverse for value in row) else None


def _matvec(matrix: Sequence[Sequence[Interval]], vector: Sequence[Interval]) -> tuple[Interval, ...]:
    result = []
    for row in matrix:
        total = Interval.point(0.0)
        for coefficient, value in zip(row, vector):
            total = total + coefficient * value
        result.append(total)
    return tuple(result)


def _matmul(
    left: Sequence[Sequence[Interval]],
    right: Sequence[Sequence[Interval]],
) -> tuple[tuple[Interval, ...], ...]:
    columns = tuple(zip(*right))
    return tuple(
        tuple(_matvec((row,), column)[0] for column in columns)
        for row in left
    )


def _krawczyk(
    residuals: Sequence[Expr],
    box: Sequence[Interval],
    config: RescueConfig,
) -> tuple[tuple[Interval, ...] | None, bool]:
    dimension = len(box)
    center = tuple(value.midpoint() for value in box)
    point_box = tuple(Interval.point(value) for value in center)
    fpoint, point_jacobian_interval = _evaluate(residuals, point_box, dimension)
    _fbox, box_jacobian = _evaluate(residuals, box, dimension)
    point_jacobian = tuple(
        tuple(entry.midpoint() for entry in row) for row in point_jacobian_interval
    )
    inverse = _inverse_point(point_jacobian, config.singular_rcond_floor)
    if inverse is None:
        return None, True
    preconditioner = tuple(tuple(Interval.point(value) for value in row) for row in inverse)
    identity = tuple(
        tuple(Interval.point(1.0 if row == column else 0.0) for column in range(dimension))
        for row in range(dimension)
    )
    preconditioned_jacobian = _matmul(preconditioner, box_jacobian)
    defect = tuple(
        tuple(identity[row][column] - preconditioned_jacobian[row][column] for column in range(dimension))
        for row in range(dimension)
    )
    base_shift = _matvec(preconditioner, fpoint)
    base = tuple(point_box[index] - base_shift[index] for index in range(dimension))
    displacement = tuple(box[index] - point_box[index] for index in range(dimension))
    correction = _matvec(defect, displacement)
    operator = tuple(base[index] + correction[index] for index in range(dimension))
    if all(operator[index].strictly_inside(box[index]) for index in range(dimension)):
        return operator, False
    return None, False


def _split(box: Sequence[Interval]) -> tuple[tuple[Interval, ...], tuple[Interval, ...]]:
    dimension = max(range(len(box)), key=lambda index: box[index].width)
    midpoint = box[dimension].midpoint()
    left = list(box)
    right = list(box)
    left[dimension] = Interval(box[dimension].lo, midpoint)
    right[dimension] = Interval(midpoint, box[dimension].hi)
    return tuple(left), tuple(right)


def discover(
    problem: Problem,
    config: RescueConfig = RescueConfig(),
    *,
    clock: Callable[[], float] = time.monotonic,
) -> RescueResult:
    """Breadth-first bounded rescue; certificates become proposals only."""

    gate = applicability(problem, config)
    if not gate.applicable:
        return RescueResult(
            "inapplicable", gate.reason, gate, (), 0, 0, 0, 0, 0,
            config.max_boxes, config.max_seconds,
        )
    start = clock()
    queue = deque([(_initial_box(problem), 0)])
    proposals: list[Proposal] = []
    visited = excluded = splits = singular = attempts = 0
    reason = "queue-drained"
    status = "complete"

    while queue and len(proposals) < config.max_proposals:
        if clock() - start >= config.max_seconds:
            status, reason = "time-cap", "interval-time-cap"
            break
        if visited >= config.max_boxes:
            status, reason = "work-cap", "interval-box-cap"
            break
        box, depth = queue.popleft()
        visited += 1
        try:
            fbox, _jacobian = _evaluate(problem.residuals, box, gate.dimension)
            if any(not value.contains(0.0) for value in fbox):
                excluded += 1
                continue
            attempts += 1
            enclosure, midpoint_singular = _krawczyk(problem.residuals, box, config)
            singular += int(midpoint_singular)
        except (ArithmeticError, IndexError, TypeError, ValueError):
            status, reason = "safe-fallback", "interval-evaluation-failed"
            proposals = []
            break
        if enclosure is not None:
            proposals.append(
                Proposal(
                    tuple(value.midpoint() for value in enclosure),
                    tuple((value.lo, value.hi) for value in box),
                    tuple((value.lo, value.hi) for value in enclosure),
                )
            )
            continue
        if depth < config.max_depth:
            left, right = _split(box)
            queue.extend(((left, depth + 1), (right, depth + 1)))
            splits += 1

    if len(proposals) >= config.max_proposals and queue:
        status, reason = "proposal-cap", "interval-proposal-cap"
    return RescueResult(
        status,
        reason,
        gate,
        tuple(proposals),
        visited,
        excluded,
        splits,
        singular,
        attempts,
        config.max_boxes,
        config.max_seconds,
    )


def portfolio_plan(result: RescueResult, config: RescueConfig = RescueConfig()) -> PortfolioPlan:
    """Interleave proposals without consuming the preregistered baseline quota."""

    _validate_config(config)
    minimum = math.ceil(config.total_launch_slots * config.minimum_baseline_fraction)
    capacity = max(0, config.total_launch_slots - minimum)
    admitted = result.proposals[: min(capacity, config.max_proposals)]
    launches: list[Launch] = []
    proposal_index = 0
    while len(launches) < config.total_launch_slots:
        # A baseline launch always leads each pair, so early interruption remains safe.
        launches.append(Launch("baseline", None))
        if len(launches) >= config.total_launch_slots:
            break
        if proposal_index < len(admitted):
            launches.append(Launch("interval-proposal", admitted[proposal_index]))
            proposal_index += 1
        else:
            launches.append(Launch("baseline", None))
    baseline = sum(item.kind == "baseline" for item in launches)
    interval = len(launches) - baseline
    return PortfolioPlan(tuple(launches), baseline, interval, minimum)


__all__ = [
    "Const",
    "Expr",
    "Interval",
    "IntervalFailure",
    "Launch",
    "PortfolioPlan",
    "Problem",
    "Proposal",
    "RescueConfig",
    "RescueResult",
    "Var",
    "applicability",
    "discover",
    "portfolio_plan",
    "unsupported",
]
