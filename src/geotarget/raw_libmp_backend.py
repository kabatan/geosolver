"""Low-allocation binary53 backend for the general typed V15 residual IR.

The backend is intentionally compiled from :mod:`typed_refnum_ir` opcodes,
not from problem identities or corpus membership.  It uses SymPy 1.14's own
``mpmath.libmp`` primitives and the same 53-bit/round-to-nearest boundaries as
the frozen evaluator.  Unsupported programs are rejected as a whole.

This backend is selected by the optimized product dispatcher only after its
bitwise differential, optimizer-trace, and performance gates passed.  Every
unsupported opcode still rejects the complete problem.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import threading
from dataclasses import dataclass
from typing import Any

from mpmath.libmp.libelefun import mpf_acos, mpf_atan, mpf_atan2, mpf_cos, mpf_pi, mpf_sin
from mpmath.libmp.libmpf import (
    ComplexResult,
    fnan,
    from_float,
    from_int,
    fzero,
    mpf_abs,
    mpf_add,
    mpf_div,
    mpf_eq,
    mpf_mod,
    mpf_mul,
    mpf_mul_int,
    mpf_neg,
    mpf_pos,
    mpf_pow_int,
    mpf_sqrt,
    mpf_sub,
    normalize,
    round_nearest,
    to_float,
)
from sympy.core.evalf import add_terms

from geotarget.deferred_scalar_tape import (
    DeferredScalar,
    DeferredScalarTape,
    InputSlot,
    compile_deferred_scalar,
)
from geotarget.typed_refnum_intersections import DoubleSelectorTraceEntry, IntersectPlan
from geotarget.typed_refnum_ir import (
    ConsumerCapability,
    ConsumerRole,
    IRNode,
    NumericEffectAnalysis,
    NumericEffectPolicy,
    TypedRefNumProgram,
    certify_numeric_effects,
)

RAW_LIBMP_ABI = "geotarget.raw-libmp/sympy-1.14-bf53-v1"
MAX_EXACT_UNARY_DOWNSTREAM_NODES = 32
_PREC = 53
_EVALF_PREC = 57  # Expr.evalf() computes four guard bits before Float(53).
_TRIG_ARG_PREC = _EVALF_PREC + 20
_PERIODIC_CANCELLATION_GUARD = 356
_PERIODIC_DISTANCE_GUARD = 5
_MISSING = object()


class UnsupportedRawLibmpBackend(RuntimeError):
    """The complete typed program is outside the raw backend ABI."""


class RawLibmpRuntimeFault(RuntimeError):
    """A frozen construction precondition failed."""


@dataclass(frozen=True, slots=True)
class _Deferred:
    """A numeric SymPy expression whose evaluation is intentionally delayed."""

    opcode: str
    operands: tuple[Any, ...]


_DEFERRED_STATE = threading.local()


def _defer(opcode: str, operands: tuple[Any, ...]) -> _Deferred:
    """Hash-cons one callback's symbolic-coordinate DAG."""

    cache: dict[tuple[Any, ...], _Deferred] | None = getattr(
        _DEFERRED_STATE, "cache", None
    )
    if cache is None:
        return _Deferred(opcode, operands)
    # Value-keying is semantically significant: independently constructed but
    # equal scalar subexpressions are shared by SymPy before its final evalf
    # boundary.  An identity-only key changes rounding histories by one ULP in
    # otherwise shallow PointOnCircle consumers, so the production closure
    # retains this canonical structural key.
    key = (opcode, operands)
    existing = cache.get(key)
    if existing is not None:
        return existing
    value = _Deferred(opcode, operands)
    cache[key] = value
    return value


def _dynamic_tape_template(
    value: Any,
    inputs: list[Any],
    memo: dict[int, Any],
) -> Any:
    """Map one branch-stable runtime DAG to an InputSlot tape template."""

    if _is_mpf(value) or isinstance(value, float):
        slot = InputSlot(len(inputs))
        inputs.append(value)
        return slot
    if isinstance(value, int):
        return value
    if isinstance(value, _LocalInvalid):
        raise RawLibmpRuntimeFault(value.reason)
    identity = id(value)
    cached = memo.get(identity)
    if cached is not None:
        return cached
    if isinstance(value, _Deferred):
        # Reserve before recursion is unnecessary because the scalar DAG is
        # acyclic.  Identity memoization preserves CSE and shared geometry
        # provenance across Intersect/Circle/Line consumers.
        converted = DeferredScalar(
            value.opcode,
            tuple(_dynamic_tape_template(item, inputs, memo) for item in value.operands),
        )
        memo[identity] = converted
        return converted
    if isinstance(value, tuple | list):
        converted_tuple = tuple(
            _dynamic_tape_template(item, inputs, memo) for item in value
        )
        memo[identity] = converted_tuple
        return converted_tuple
    raise RawLibmpRuntimeFault(f"unsupported periodic tape leaf: {type(value)!r}")


def _evaluate_cached_periodic_tape(
    program_identity: int,
    root_key: tuple[int, int],
    value: Scalar,
) -> float:
    inputs, topology_digest = _runtime_tape_signature(value)
    tapes: dict[tuple[int, tuple[int, int], str], DeferredScalarTape] = getattr(
        _DEFERRED_STATE, "tapes", None
    )
    if tapes is None:
        tapes = {}
        _DEFERRED_STATE.tapes = tapes
    cache_key = (program_identity, root_key, topology_digest)
    tape = tapes.get(cache_key)
    if tape is None:
        template_inputs: list[Any] = []
        template = _dynamic_tape_template(value, template_inputs, {})
        if len(template_inputs) != len(inputs):  # pragma: no cover - invariant
            raise RawLibmpRuntimeFault("periodic tape input topology changed during compile")
        tape = compile_deferred_scalar(template)
        tapes[cache_key] = tape
    return tape.evaluate_float(inputs)


def _runtime_tape_signature(value: Any) -> tuple[list[Any], str]:
    """Collect dynamic slots and a stable branch topology in one DAG walk."""

    inputs: list[Any] = []
    digest = hashlib.sha256()
    references: dict[int, int] = {}

    def emit(item: Any) -> None:
        if _is_mpf(item) or isinstance(item, float):
            ordinal = len(inputs)
            inputs.append(item)
            digest.update(b"I")
            digest.update(ordinal.to_bytes(8, "big"))
            return
        if isinstance(item, int):
            encoded = str(item).encode("ascii")
            digest.update(b"C")
            digest.update(len(encoded).to_bytes(4, "big"))
            digest.update(encoded)
            return
        if isinstance(item, _LocalInvalid):
            raise RawLibmpRuntimeFault(item.reason)
        identity = id(item)
        reference = references.get(identity)
        if reference is not None:
            digest.update(b"R")
            digest.update(reference.to_bytes(8, "big"))
            return
        references[identity] = len(references)
        if isinstance(item, _Deferred):
            opcode = item.opcode.encode("ascii")
            digest.update(b"D")
            digest.update(len(opcode).to_bytes(2, "big"))
            digest.update(opcode)
            digest.update(len(item.operands).to_bytes(4, "big"))
            for operand in item.operands:
                emit(operand)
            return
        if isinstance(item, tuple | list):
            digest.update(b"T")
            digest.update(len(item).to_bytes(4, "big"))
            for child in item:
                emit(child)
            return
        raise RawLibmpRuntimeFault(
            f"unsupported periodic runtime topology node: {type(item)!r}"
        )

    emit(value)
    return inputs, digest.hexdigest()


@dataclass(frozen=True, slots=True)
class _LocalInvalid:
    """A non-real scalar that faults only the residuals which consume it.

    SymPy permits non-real expressions to live in construction objects and
    raises only when the frozen evaluator finally converts an affected
    residual to ``float``.  Keeping this tag in the numeric DAG prevents one
    bad coordinate or angle from poisoning independent constraints.
    """

    reason: str


Mpf = tuple[int, int, int, int]
Scalar = int | float | Mpf | _Deferred | _LocalInvalid
Point = tuple[Scalar, Scalar]
Line = tuple[Scalar, Scalar, Scalar]
Circle = tuple[Point, Scalar]


def _is_mpf(value: Any) -> bool:
    # libmp's public representation is a four-item tuple.  Every tuple which
    # enters this closed evaluator is produced by libmp itself or by one of
    # the geometry constructors below (whose Point/Line/Circle tuples have
    # arity 2/3/2).  Checking every mpf limb on every primitive operation was
    # therefore redundant: it was the largest allocator/interpreter hotspot
    # in callback profiles.  Keep the arity discriminator at this boundary;
    # malformed external tuples are not part of RawLibmpProgram's ABI.
    return type(value) is tuple and len(value) == 4


def _mpf_sign(value: Mpf) -> int | None:
    """Classify an arbitrary-exponent libmp value without binary64 underflow."""

    if value == fnan:
        return None
    if value == fzero:
        return 0
    return -1 if value[0] else 1


def _as_mpf(value: Scalar) -> Mpf:
    if isinstance(value, _LocalInvalid):
        raise RawLibmpRuntimeFault(value.reason)
    if isinstance(value, _Deferred):
        return _eval_deferred(value, _PREC)
    if _is_mpf(value):
        return value  # type: ignore[return-value]
    if isinstance(value, int):
        return from_int(value)
    return from_float(value)


def _as_float(value: Scalar) -> float:
    if isinstance(value, _LocalInvalid):
        raise RawLibmpRuntimeFault(value.reason)
    if isinstance(value, _Deferred):
        if _contains_deferred_opcode(value, {"on_circle_pc"}) and _contains_subnormal_leaf(
            value
        ):
            # SymPy's accuracy restart observes exact cancellations below the
            # normal binary64 range.  This value-class fallback is independent
            # of problem/corpus identity and is only reached for subnormal
            # leaves in the guarded PointOnCircle predicate boundary.
            return float(_sympy_boundary_scalar(value))
        # A frozen Angle remains an atan2/acos expression until the enclosing
        # constraint-side Float conversion.  Evaluating just the Angle first
        # loses SymPy's exact quadrant ``pi`` and changes downstream scalar
        # arithmetic by several ULP.  Rebuild the complete admitted scalar
        # closure at that one boundary instead.
        if _contains_deferred_opcode(
            value, {"angle_ppp", "angle_ll", "sympy_atan2"}
        ):
            return float(_sympy_boundary_scalar(value))
        if _contains_deferred_opcode(value, {"periodic_cos", "periodic_sin"}) and (
            _contains_deferred_opcode(value, {"div", "abs"})
        ):
            # A periodic point consumed by normalized-line or absolute-value
            # geometry retains the complete expression at SymPy's residual
            # boundary.  Closing the quotient/Abs eagerly is observably
            # different by 1--2 ULP.  Deep roots use their separately
            # qualified cached tape and do not pass through this direct path.
            return float(_sympy_boundary_scalar(value))
        if _contains_deferred_opcode(value, {"periodic_cos", "periodic_sin"}):
            return to_float(
                mpf_pos(
                    _eval_periodic_scalar_tape(value, _EVALF_PREC),
                    _PREC,
                    round_nearest,
                )
            )
        # Expr.evalf() asks for four guard bits, then creates Float(53).
        return to_float(mpf_pos(_eval_deferred(value, _EVALF_PREC), _PREC, round_nearest))
    if _is_mpf(value):
        return to_float(value)  # type: ignore[arg-type]
    return float(value)


def _as_float_periodic_correctness_oracle(value: Scalar) -> float:
    """Slow full-symbolic boundary used only by explicit correctness tests."""

    if isinstance(value, _Deferred) and _contains_deferred_opcode(
        value, {"periodic_cos", "periodic_sin"}
    ):
        return float(_sympy_boundary_scalar(value))
    return _as_float(value)


def _contains_deferred_opcode(value: Any, opcodes: set[str]) -> bool:
    if isinstance(value, _Deferred):
        return value.opcode in opcodes or any(
            _contains_deferred_opcode(operand, opcodes) for operand in value.operands
        )
    if isinstance(value, tuple | list):
        return any(_contains_deferred_opcode(item, opcodes) for item in value)
    return False


def _contains_subnormal_leaf(value: Any) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if _is_mpf(item):
            converted = to_float(item)
            if item != fzero and (converted == 0.0 or abs(converted) < sys.float_info.min):
                return True
        elif isinstance(item, _Deferred):
            pending.extend(item.operands)
        elif isinstance(item, tuple | list):
            pending.extend(item)
    return False


def _add(left: Scalar, right: Scalar) -> Scalar:
    if isinstance(left, _LocalInvalid):
        return left
    if isinstance(right, _LocalInvalid):
        return right
    if isinstance(left, _Deferred) or isinstance(right, _Deferred):
        return _defer("add", (left, right))
    if _is_mpf(left) or _is_mpf(right):
        return mpf_add(_as_mpf(left), _as_mpf(right), _PREC, round_nearest)
    return left + right


def _sub(left: Scalar, right: Scalar) -> Scalar:
    if isinstance(left, _LocalInvalid):
        return left
    if isinstance(right, _LocalInvalid):
        return right
    deferred_exact_cancellation = False
    if isinstance(left, _Deferred) and left == right:
        try:
            expression = _sympy_boundary_scalar(left)
            deferred_exact_cancellation = bool(
                _contains_input_free_exact_unary(left)
                and expression.is_real is True
                and expression.is_finite is True
            )
        except Exception:
            deferred_exact_cancellation = False
    if deferred_exact_cancellation:
        return 0
    if isinstance(left, _Deferred) or isinstance(right, _Deferred):
        return _defer("sub", (left, right))
    if _is_mpf(left) or _is_mpf(right):
        return mpf_sub(_as_mpf(left), _as_mpf(right), _PREC, round_nearest)
    return left - right


def _mul(left: Scalar, right: Scalar) -> Scalar:
    if isinstance(left, _LocalInvalid):
        return left
    if isinstance(right, _LocalInvalid):
        return right
    if isinstance(left, _Deferred) or isinstance(right, _Deferred):
        if left is right:
            return _defer("square", (left,))
        return _defer("mul", (left, right))
    if _is_mpf(left) or _is_mpf(right):
        return mpf_mul(_as_mpf(left), _as_mpf(right), _PREC, round_nearest)
    return left * right


def _div(left: Scalar, right: Scalar) -> Scalar:
    if isinstance(left, _LocalInvalid):
        return left
    if isinstance(right, _LocalInvalid):
        return right
    if isinstance(left, _Deferred) or isinstance(right, _Deferred):
        return _defer("div", (left, right))
    if isinstance(left, int) and _is_mpf(right):
        # SymPy constructs Integer / Float as Integer * Pow(Float, -1):
        # the reciprocal is rounded to the Float's precision before the
        # integer multiplication.  A direct mpf_div differs by one ULP for a
        # substantial fraction of inputs and perturbs normalized Line terms.
        reciprocal = mpf_pow_int(right, -1, _PREC, round_nearest)
        return mpf_mul(from_int(left), reciprocal, _PREC, round_nearest)
    if _is_mpf(left) or _is_mpf(right):
        return mpf_div(_as_mpf(left), _as_mpf(right), _PREC, round_nearest)
    return left / right


def _neg(value: Scalar) -> Scalar:
    if isinstance(value, _LocalInvalid):
        return value
    if isinstance(value, _Deferred):
        return _defer("neg", (value,))
    return mpf_neg(value) if _is_mpf(value) else -value  # type: ignore[arg-type]


def _abs(value: Scalar) -> Scalar:
    if isinstance(value, _LocalInvalid):
        return value
    if isinstance(value, _Deferred):
        return _defer("abs", (value,))
    return mpf_abs(value) if _is_mpf(value) else abs(value)  # type: ignore[arg-type]


def _sqrt(value: Scalar) -> Scalar:
    if isinstance(value, _LocalInvalid):
        return value
    if isinstance(value, _Deferred):
        return _defer("sqrt", (value,))
    if _is_mpf(value):
        try:
            return mpf_sqrt(value, _PREC, round_nearest)  # type: ignore[arg-type]
        except ComplexResult:
            return _LocalInvalid("square root is non-real")
    if isinstance(value, int) and value >= 0:
        root = math.isqrt(value)
        if root * root == value:
            return root
        return _defer("sqrt", (value,))
    if isinstance(value, int):
        return _LocalInvalid("square root is non-real")
    # A non-square exact radical remains symbolic in SymPy.  The raw backend
    # rejects such source nodes at compile time; this branch covers only a
    # dynamically produced host float.
    if isinstance(value, float):
        try:
            return mpf_sqrt(from_float(value), _PREC, round_nearest)
        except ComplexResult:
            return _LocalInvalid("square root is non-real")
    raise RawLibmpRuntimeFault("unsupported exact radical")


def _evalf_unary(function: Any, value: Scalar) -> Scalar:
    if isinstance(value, _LocalInvalid):
        return value
    if isinstance(value, int | _Deferred):
        opcode = "acos" if function is mpf_acos else "cos" if function is mpf_cos else "sin"
        return _defer(opcode, (value,))  # type: ignore[return-value]
    try:
        raw = function(_as_mpf(value), _EVALF_PREC, round_nearest)
    except ComplexResult:
        return _LocalInvalid("real unary function received an out-of-domain value")
    return mpf_pos(raw, _PREC, round_nearest)


def _point(x: Scalar, y: Scalar) -> Point:
    # Frozen Point preserves Python ints and sympifies every other scalar.
    return (
        x if isinstance(x, int | _Deferred | _LocalInvalid) else _as_mpf(x),
        y if isinstance(y, int | _Deferred | _LocalInvalid) else _as_mpf(y),
    )


def _circle(center: Point, radius: Scalar) -> Circle:
    radius = radius if isinstance(radius, int | _Deferred | _LocalInvalid) else _as_mpf(radius)
    if (
        not isinstance(radius, _LocalInvalid)
        and isinstance(radius, _Deferred)
        and _as_float(radius) < 0
        or _is_mpf(radius)
        and radius[0]
        or isinstance(radius, int)
        and radius < 0
    ):
        raise RawLibmpRuntimeFault("Circle.radius must be non-negative")
    return center, radius


def _line_coefficients(a: Scalar, b: Scalar, c: Scalar) -> Line:
    norm = _sqrt(_add(_mul(a, a), _mul(b, b)))
    if (_is_mpf(norm) and mpf_eq(norm, from_int(0))) or norm == 0:
        raise RawLibmpRuntimeFault("Line.norm must be non-zero")
    return _div(a, norm), _div(b, norm), _div(c, norm)


def _distance_pp(first: Point, second: Point | None) -> Scalar:
    if second is None:
        # The frozen public Distance signature defaults its second argument to
        # None, so Distance(point, a_parallel_LL_intersection) is the unary
        # distance from the origin rather than a runtime fault.
        return _sqrt(_add(_mul(first[0], first[0]), _mul(first[1], first[1])))
    if any(
        isinstance(coordinate, _Deferred)
        for point in (first, second)
        for coordinate in point
    ):
        return _defer("distance_pp", (first, second))
    dx, dy = _sub(first[0], second[0]), _sub(first[1], second[1])
    return _sqrt(_add(_mul(dx, dx), _mul(dy, dy)))


def _distance_pl(point: Point, line: Line) -> Scalar:
    return _abs(_add(_add(_mul(line[0], point[0]), _mul(line[1], point[1])), line[2]))


def _area_points(points: tuple[Point, ...]) -> Scalar:
    # SymPy canonically collects the repeated center/trigonometric terms in a
    # shoelace sum before evalf.  Evaluating an expanded numeric shoelace tree
    # changes Area by several ULP when a PointOnCircle coordinate is still
    # symbolic.  Retain that expression boundary only for the periodic flow;
    # ordinary points stay on the allocation-free numeric path.
    if any(isinstance(coordinate, _Deferred) for point in points for coordinate in point):
        return _defer("area_points", (points,))
    total: Scalar = 0
    for position, first in enumerate(points):
        second = points[(position + 1) % len(points)]
        total = _add(total, _sub(_mul(first[0], second[1]), _mul(first[1], second[0])))
    return _div(_abs(total), 2)


def _is_zero(value: Scalar) -> bool:
    if isinstance(value, _LocalInvalid):
        return False
    return mpf_eq(value, from_int(0)) if _is_mpf(value) else value == 0


def _circumcenter(a: Point, b: Point, c: Point) -> Point | None:
    x1, y1, x2, y2, x3, y3 = (*a, *b, *c)
    denominator = _mul(
        2,
        _add(
            _add(_mul(x1, _sub(y2, y3)), _mul(x2, _sub(y3, y1))),
            _mul(x3, _sub(y1, y2)),
        ),
    )
    if _is_zero(denominator):
        return None
    square1 = _add(_mul(x1, x1), _mul(y1, y1))
    square2 = _add(_mul(x2, x2), _mul(y2, y2))
    square3 = _add(_mul(x3, x3), _mul(y3, y3))
    ux = _div(
        _add(
            _add(_mul(square1, _sub(y2, y3)), _mul(square2, _sub(y3, y1))),
            _mul(square3, _sub(y1, y2)),
        ),
        denominator,
    )
    uy = _div(
        _add(
            _add(_mul(square1, _sub(x3, x2)), _mul(square2, _sub(x1, x3))),
            _mul(square3, _sub(x2, x1)),
        ),
        denominator,
    )
    return _point(ux, uy)


def _incenter(a: Point, b: Point, c: Point, *, external: bool = False) -> Point:
    side_a, side_b, side_c = _distance_pp(b, c), _distance_pp(c, a), _distance_pp(a, b)
    signed_a = _neg(side_a) if external else side_a
    denominator = _add(_add(signed_a, side_b), side_c)
    if _is_zero(denominator):
        return a
    return _point(
        _div(
            _add(_add(_mul(signed_a, a[0]), _mul(side_b, b[0])), _mul(side_c, c[0])),
            denominator,
        ),
        _div(
            _add(_add(_mul(signed_a, a[1]), _mul(side_b, b[1])), _mul(side_c, c[1])),
            denominator,
        ),
    )


def _foot(line: Line, point: Point) -> Point:
    denominator = _add(_mul(line[0], line[0]), _mul(line[1], line[1]))
    if _is_zero(denominator):
        raise RawLibmpRuntimeFault("Foot.denominator must be non-zero")
    return _point(
        _div(
            _sub(
                _mul(line[1], _sub(_mul(line[1], point[0]), _mul(line[0], point[1]))),
                _mul(line[0], line[2]),
            ),
            denominator,
        ),
        _div(
            _sub(
                _mul(line[0], _add(_neg(_mul(line[1], point[0])), _mul(line[0], point[1]))),
                _mul(line[1], line[2]),
            ),
            denominator,
        ),
    )


def _raw_intersection_candidates(
    plan: IntersectPlan, first: Any, second: Any
) -> list[Point] | None:
    operand_types = plan.support_key.operand_types
    if operand_types == ("line2", "line2"):
        determinant = _sub(_mul(first[0], second[1]), _mul(second[0], first[1]))
        if _is_zero(determinant):
            return None
        return [
            _point(
                _div(_sub(_mul(first[1], second[2]), _mul(second[1], first[2])), determinant),
                _div(_sub(_mul(first[2], second[0]), _mul(second[2], first[0])), determinant),
            )
        ]
    if operand_types == ("circle2", "line2"):
        line, circle = second, first
    elif operand_types == ("line2", "circle2"):
        line, circle = first, second
    else:
        first_center, first_radius = first
        second_center, second_radius = second
        dx, dy = _sub(first_center[0], second_center[0]), _sub(first_center[1], second_center[1])
        distance_squared = _add(_mul(dx, dx), _mul(dy, dy))
        distance = _sqrt(distance_squared)
        along = _div(
            _add(
                _sub(_mul(first_radius, first_radius), _mul(second_radius, second_radius)),
                distance_squared,
            ),
            _mul(2, distance),
        )
        height_squared = _sub(_mul(first_radius, first_radius), _mul(along, along))
        height = _sqrt(0 if _as_float(height_squared) < 0 else height_squared)
        center_dx = _sub(second_center[0], first_center[0])
        center_dy = _sub(second_center[1], first_center[1])
        x0 = _add(first_center[0], _div(_mul(along, center_dx), distance))
        y0 = _add(first_center[1], _div(_mul(along, center_dy), distance))
        offset_x = _neg(_mul(center_dy, _div(height, distance)))
        offset_y = _mul(center_dx, _div(height, distance))
        return [
            _point(_add(x0, offset_x), _add(y0, offset_y)),
            _point(_sub(x0, offset_x), _sub(y0, offset_y)),
        ]
    a, b, c = line
    center, radius = circle
    shifted = _add(_add(_mul(a, center[0]), _mul(b, center[1])), c)
    divisor = _add(_mul(a, a), _mul(b, b))
    if _is_zero(divisor):
        sentinel = _point(1e9, 1e9)
        return [sentinel, sentinel]
    distance_squared = _div(_mul(shifted, shifted), divisor)
    delta = _sub(_mul(radius, radius), distance_squared)
    multiplier = _sqrt(_div(0 if _as_float(delta) < 0 else delta, divisor))
    x0, y0 = _div(_neg(_mul(a, shifted)), divisor), _div(_neg(_mul(b, shifted)), divisor)
    return [
        _point(
            _add(_add(center[0], x0), _mul(b, multiplier)),
            _sub(_add(center[1], y0), _mul(a, multiplier)),
        ),
        _point(
            _sub(_add(center[0], x0), _mul(b, multiplier)),
            _add(_add(center[1], y0), _mul(a, multiplier)),
        ),
    ]


def _raw_point_equal(first: Point, second: Point) -> bool:
    if _is_zero(_sub(first[0], second[0])) and _is_zero(_sub(first[1], second[1])):
        return True
    return (
        abs(_as_float(_sub(first[0], second[0]))) < 1e-14
        and abs(_as_float(_sub(first[1], second[1]))) < 1e-14
    )


def evaluate_raw_intersect(
    plan: IntersectPlan,
    first: Any,
    second: Any,
    *,
    selector_values: dict[str, Point] | None = None,
    ambient_dps: int = 15,
) -> tuple[Point | list[Point] | None, DoubleSelectorTraceEntry | None]:
    """Evaluate a point-valued frozen Intersect plan and expose its branch trace."""

    candidates = _raw_intersection_candidates(plan, first, second)
    selector_kind = plan.support_key.selector_kind
    base_kind = selector_kind.removesuffix("+n")
    if candidates is None and selector_kind == "none":
        # IntersectLines returns None for parallel/coincident lines.  None is
        # a construction value in the frozen evaluator, not a construction
        # fault; its eventual consumer determines fault scope.
        return None, None
    if not candidates:
        raise RawLibmpRuntimeFault("No intersection found")
    active = list(enumerate(candidates))
    selectors = selector_values or {}
    if base_kind == "exclude":
        excluded = selectors["exclude"]
        tolerance_squared = (10 ** (-ambient_dps + 10)) ** 2
        active = [
            (index, candidate)
            for index, candidate in active
            if not _raw_point_equal(candidate, excluded)
            and _as_float(
                _add(
                    _mul(_sub(candidate[0], excluded[0]), _sub(candidate[0], excluded[0])),
                    _mul(_sub(candidate[1], excluded[1]), _sub(candidate[1], excluded[1])),
                )
            )
            > tolerance_squared
        ]
        if not active:
            raise RawLibmpRuntimeFault("No intersection found after exclusion")
    elif base_kind in {"near", "far"}:
        reference = selectors[base_kind]

        def squared_distance(item: tuple[int, Point]) -> float:
            candidate = item[1]
            dx, dy = _sub(candidate[0], reference[0]), _sub(candidate[1], reference[1])
            return _as_float(_add(_mul(dx, dx), _mul(dy, dy)))

        active.sort(key=squared_distance, reverse=base_kind == "far")
    if selector_kind == "exclude" and len(active) > 1:
        # Frozen exclude-only selection is deliberately not an implicit first
        # root selector: if exclusion leaves multiple candidates it returns
        # the complete list.  A point consumer then determines whether that
        # list is invalid locally or aborts a dependent construction.
        original_index = active[0][0]
        return [candidate for _index, candidate in active], DoubleSelectorTraceEntry(
            selector_kind="exclude",
            candidate_count=len(active),
            selected_original_index=original_index,
            selected_active_index=0,
            ambient_dps=ambient_dps,
            hp_authority_complete=False,
        )
    ordinal = plan.ordinal or 1
    if ordinal > len(active):
        raise RawLibmpRuntimeFault(f"Intersection #{ordinal} does not exist")
    active_index = ordinal - 1
    original_index, chosen = active[active_index]
    trace_kind = "n" if base_kind == "n" else base_kind
    trace = None
    if selector_kind != "none":
        trace = DoubleSelectorTraceEntry(
            selector_kind=trace_kind,
            candidate_count=len(active),
            selected_original_index=original_index,
            selected_active_index=active_index,
            ambient_dps=ambient_dps,
            hp_authority_complete=trace_kind == "n",
        )
    return chosen, trace


def _periodic_trig(parameter: Scalar, *, cosine: bool) -> Scalar:
    """Evaluate ``cos/sin(2*pi*parameter)`` with frozen SymPy reductions."""

    if isinstance(parameter, _LocalInvalid):
        return parameter
    coefficient = mpf_mul_int(_as_mpf(parameter), 2, _PREC, round_nearest)
    # SymPy canonicalizes exact quarter turns before evalf.  Preserve those
    # exact zeros/ones because subsequent geometry arithmetic observes them.
    half = mpf_div(from_int(1), from_int(2), _PREC, round_nearest)
    # Reduction by an even integer is exact for binary53 coefficients in the
    # supported magnitude range.  mpf floor/mod is avoided here: host fmod
    # would introduce a second numeric semantics.  Integer subtraction uses
    # libmp at the same 53-bit boundary.
    # Reduce in libmp space.  Host-float ``floor`` overflows for finite
    # binary64 parameters near max-float and loses the exact even-integer
    # reduction which frozen SymPy performs before evaluating trig.
    reduced = mpf_mod(coefficient, from_int(2), _PREC, round_nearest)
    if mpf_eq(reduced, from_int(0)):
        return 1 if cosine else 0
    if mpf_eq(reduced, half):
        return 0 if cosine else 1
    if mpf_eq(reduced, from_int(1)):
        return -1 if cosine else 0
    three_halves = mpf_add(from_int(1), half, _PREC, round_nearest)
    if mpf_eq(reduced, three_halves):
        return 0 if cosine else -1
    # A non-special trigonometric term stays symbolic inside frozen geometry.
    # Rounding it here was the source of the initial 1--4 ULP differential.
    # Keep the unreduced BF53 coefficient in the symbolic expression.  The
    # frozen constructor is ``cos/sin(2*pi*t)``; replacing it by an equivalent
    # modulo-2 argument changes evalf's pi multiplication/range-reduction
    # history for ordinary (non-special) turns.  ``reduced`` is authority only
    # for recognizing the exact quarter-turn constants above.
    return _defer("periodic_cos" if cosine else "periodic_sin", (coefficient,))


def _sympy_boundary_scalar(value: Scalar):
    """Rebuild the small symbolic boundary retained by frozen periodic geometry."""

    from sympy import Abs as SympyAbs
    from sympy import Float, Integer, acos, atan, atan2, cos, pi, sin, sqrt

    if isinstance(value, _LocalInvalid):
        raise RawLibmpRuntimeFault(value.reason)
    if isinstance(value, int):
        return Integer(value)
    if _is_mpf(value):
        # libmp retains exponents beyond binary64's representable range.
        # Routing through ``to_float`` underflowed tiny determinant/dot terms
        # to zero before a deferred Angle/geometry expression reached the
        # same SymPy boundary as the frozen evaluator.
        return Float._new(value, _PREC)
    if isinstance(value, float):
        return Float(value)
    op, args = value.opcode, value.operands
    if op in {"distance_pp", "distance_pp_flat"}:
        first, second = args
        dx = _sympy_boundary_scalar(first[0]) - _sympy_boundary_scalar(second[0])
        dy = _sympy_boundary_scalar(first[1]) - _sympy_boundary_scalar(second[1])
        return sqrt(dx**2 + dy**2)
    if op == "area_points":
        points = args[0]
        total: Any = Integer(0)
        for position, first in enumerate(points):
            second = points[(position + 1) % len(points)]
            total += _sympy_boundary_scalar(first[0]) * _sympy_boundary_scalar(
                second[1]
            ) - _sympy_boundary_scalar(first[1]) * _sympy_boundary_scalar(second[0])
        return SympyAbs(total) / 2
    if op == "on_circle_pc":
        point, center, radius = args
        dx = _sympy_boundary_scalar(point[0]) - _sympy_boundary_scalar(center[0])
        dy = _sympy_boundary_scalar(point[1]) - _sympy_boundary_scalar(center[1])
        return sqrt(dx**2 + dy**2) - _sympy_boundary_scalar(radius)
    if op == "angle_ppp":
        determinant, dot = args
        return atan2(
            _sympy_boundary_scalar(determinant),
            _sympy_boundary_scalar(dot),
        )
    if op == "angle_ll":
        return acos(_sympy_boundary_scalar(args[0]))
    converted = tuple(_sympy_boundary_scalar(item) for item in args)
    if op == "add":
        return converted[0] + converted[1]
    if op == "sub":
        return converted[0] - converted[1]
    if op == "mul":
        return converted[0] * converted[1]
    if op == "div":
        return converted[0] / converted[1]
    if op == "neg":
        return -converted[0]
    if op == "abs":
        return SympyAbs(converted[0])
    if op == "sqrt":
        return sqrt(converted[0])
    if op == "square":
        return converted[0] ** 2
    if op == "pow_int":
        return converted[0] ** converted[1]
    if op in {"periodic_cos", "periodic_sin"}:
        function = cos if op == "periodic_cos" else sin
        return function(converted[0] * pi)
    if op == "cos":
        return cos(converted[0])
    if op == "sin":
        return sin(converted[0])
    if op == "acos":
        return acos(converted[0])
    if op == "atan":
        return atan(converted[0])
    if op in {"atan2", "sympy_atan2"}:
        return atan2(converted[0], converted[1])
    if op == "pi":
        return pi
    raise RawLibmpRuntimeFault(f"unsupported symbolic boundary operand: {op}")


def _contains_input_free_exact_unary(value: Any) -> bool:
    def input_free(item: Any) -> bool:
        if isinstance(item, int):
            return True
        if isinstance(item, _Deferred):
            return item.opcode not in {"periodic_cos", "periodic_sin"} and all(
                input_free(operand) for operand in item.operands
            )
        if isinstance(item, tuple) and not _is_mpf(item):
            return all(input_free(operand) for operand in item)
        return False

    if isinstance(value, _Deferred):
        if value.opcode in {"sqrt", "cos", "sin"} and all(
            input_free(operand) for operand in value.operands
        ):
            return True
        return any(_contains_input_free_exact_unary(operand) for operand in value.operands)
    if isinstance(value, tuple) and not _is_mpf(value):
        return any(_contains_input_free_exact_unary(operand) for operand in value)
    return False


def _eval_deferred(expression: _Deferred | Scalar, precision: int) -> Mpf:
    """Evaluate the delayed real subset with SymPy evalf precision schedules."""

    if not isinstance(expression, _Deferred):
        return _as_mpf(expression)
    if _contains_input_free_exact_unary(expression):
        # Keep the complete consumer expression symbolic.  Rounding sqrt/cos/
        # sin to BF53 before a Line normalization or distance cancellation is
        # observably different from frozen SymPy's single constraint-boundary
        # conversion.
        return from_float(float(_sympy_boundary_scalar(expression)))
    op, args = expression.opcode, expression.operands
    if op in {"periodic_cos", "periodic_sin"}:
        coefficient = _as_mpf(args[0])
        argument_precision = precision + 20
        # The argument is a canonical SymPy Mul(Float, pi).  evalf_mul uses
        # ``prec + len(args) + 5`` for its factors, then normalizes the exact
        # mantissa product to the requested argument precision.
        working = argument_precision + 7
        pi_value = mpf_pi(working, round_nearest)
        sign = coefficient[0] ^ pi_value[0]
        mantissa = coefficient[1] * pi_value[1]
        exponent = coefficient[2] + pi_value[2]
        argument = normalize(
            sign,
            mantissa,
            exponent,
            mantissa.bit_length(),
            argument_precision,
            round_nearest,
        )
        function = mpf_cos if op == "periodic_cos" else mpf_sin
        return function(argument, precision, round_nearest)
    if op in {"area_points", "distance_pp"}:
        # SymPy's float conversion tracks the 53-bit accuracy attached to
        # substituted Float coefficients.  Evaluating the same expression at
        # arbitrarily higher precision changes near-quarter-turn rounding, so
        # preserve the frozen conversion boundary exactly.  The compiler
        # admits these deferred expressions only at qualified boundaries.
        return from_float(float(_sympy_boundary_scalar(expression)))
    if op in {"add", "sub"}:
        left = _eval_deferred(args[0], precision + 10)
        right = _eval_deferred(args[1], precision + 10)
        if op == "sub":
            right = mpf_neg(right)
        # For two finite real terms this is evalf_add/add_terms without the
        # accuracy restart (Float substitutions are assigned requested
        # accuracy by SymPy itself).
        result, _accuracy = add_terms(
            [(left, precision + 10), (right, precision + 10)],
            precision,
            precision,
        )
        return from_int(0) if result is None else result
    if op == "mul":
        working = precision + 7  # two operands: prec + len(args) + 5
        left = _eval_deferred(args[0], working)
        right = _eval_deferred(args[1], working)
        sign = left[0] ^ right[0]
        mantissa = left[1] * right[1]
        exponent = left[2] + right[2]
        return normalize(sign, mantissa, exponent, mantissa.bit_length(), precision, round_nearest)
    if op == "div":
        # SymPy represents division as Mul(left, Pow(right, -1)); the same
        # guard budget is sufficient for this real binary53 subset.
        working = precision + 7
        return mpf_div(
            _eval_deferred(args[0], working),
            _eval_deferred(args[1], working + 5),
            precision,
            round_nearest,
        )
    if op == "neg":
        return mpf_neg(_eval_deferred(args[0], precision))
    if op == "abs":
        return mpf_abs(_eval_deferred(args[0], precision + 2))
    if op == "sqrt":
        return mpf_sqrt(_eval_deferred(args[0], precision + 5), precision, round_nearest)
    if op == "square":
        return mpf_pow_int(_eval_deferred(args[0], precision + 5), 2, precision, round_nearest)
    if op == "pow_int":
        return mpf_pow_int(
            _eval_deferred(args[0], precision + 5),
            int(args[1]),
            precision,
            round_nearest,
        )
    if op in {"cos", "sin"}:
        function = mpf_cos if op == "cos" else mpf_sin
        return function(_eval_deferred(args[0], precision + 20), precision, round_nearest)
    if op == "acos":
        return mpf_acos(_eval_deferred(args[0], precision + 5), precision, round_nearest)
    if op == "atan":
        return mpf_atan(_eval_deferred(args[0], precision + 5), precision, round_nearest)
    if op == "pi":
        return mpf_pi(precision, round_nearest)
    if op == "sympy_atan2":
        # atan2.eval canonicalizes real numeric quadrants to atan(y/x), with
        # a symbolic +/- pi term in the negative-x half-plane.
        y, x = args
        x_sign_probe = _mpf_sign(_eval_deferred(x, _PREC))
        y_sign_probe = _mpf_sign(_eval_deferred(y, _PREC))
        if x_sign_probe is None or y_sign_probe is None:
            return fnan
        if x_sign_probe == 0:
            if y_sign_probe == 0:
                return fnan
            half_pi = mpf_div(
                mpf_pi(precision + 10, round_nearest),
                from_int(2),
                precision,
                round_nearest,
            )
            return half_pi if y_sign_probe > 0 else mpf_neg(half_pi)
        ratio = _defer("div", (y, x))
        angle: _Deferred = _defer("atan", (ratio,))
        if x_sign_probe < 0:
            pi_term: Any = _defer("pi", ())
            if y_sign_probe < 0:
                pi_term = _defer("neg", (pi_term,))
            angle = _defer("add", (angle, pi_term))
        return _eval_deferred(angle, precision)
    if op == "atan2":
        return mpf_atan2(
            _eval_deferred(args[0], precision + 5),
            _eval_deferred(args[1], precision + 5),
            precision,
            round_nearest,
        )
    raise RawLibmpRuntimeFault(f"unknown deferred opcode: {op}")


def _eval_periodic_scalar_tape(
    expression: Scalar,
    precision: int,
    memo: dict[tuple[int, int], Mpf] | None = None,
) -> Mpf:
    """Evaluate the periodic scalar closure without rebuilding a SymPy tree.

    This is the execution kernel for correctness-qualified periodic closures.
    Its opcodes form a flat numeric sub-language; recursive calls only walk
    the already-created topology and use libmp slots, never SymPy objects.
    Geometry aggregations retain their producer expressions until this final
    BF53 boundary instead of rounding Distance/Area operands independently.
    """

    if memo is None:
        memo = {}
    key = (id(expression), precision)
    cached = memo.get(key)
    if cached is not None:
        return cached
    result = _eval_periodic_scalar_tape_uncached(expression, precision, memo)
    memo[key] = result
    return result


def _eval_periodic_scalar_tape_uncached(
    expression: Scalar,
    precision: int,
    memo: dict[tuple[int, int], Mpf],
) -> Mpf:
    if not isinstance(expression, _Deferred):
        return _as_mpf(expression)
    op, args = expression.opcode, expression.operands

    def evaluate(value: Scalar, work_precision: int) -> Mpf:
        return _eval_periodic_scalar_tape(value, work_precision, memo)
    if op in {"periodic_cos", "periodic_sin"}:
        return _eval_deferred(expression, precision)
    if op in {"add", "sub"}:
        left = evaluate(args[0], precision + 10)
        right = evaluate(args[1], precision + 10)
        if op == "sub":
            right = mpf_neg(right)
        result, _accuracy = add_terms(
            [(left, precision + 10), (right, precision + 10)],
            precision,
            precision,
        )
        return from_int(0) if result is None else result
    if op == "mul":
        working = precision + 7
        left = evaluate(args[0], working)
        right = evaluate(args[1], working)
        return normalize(
            left[0] ^ right[0],
            left[1] * right[1],
            left[2] + right[2],
            (left[1] * right[1]).bit_length(),
            precision,
            round_nearest,
        )
    if op == "div":
        working = precision + 7
        return mpf_div(
            evaluate(args[0], working),
            evaluate(args[1], working + 5),
            precision,
            round_nearest,
        )
    if op == "neg":
        return mpf_neg(evaluate(args[0], precision))
    if op == "abs":
        return mpf_abs(evaluate(args[0], precision + 2))
    if op == "sqrt":
        return mpf_sqrt(evaluate(args[0], precision + 5), precision, round_nearest)
    if op in {"square", "pow_int"}:
        exponent = 2 if op == "square" else int(args[1])
        return mpf_pow_int(
            evaluate(args[0], precision + 5), exponent, precision, round_nearest
        )
    if op == "distance_pp":
        return _eval_deferred(expression, precision)
    if op == "distance_pp_flat":
        first, second = args
        working = precision + _PERIODIC_DISTANCE_GUARD
        dx = _defer("sub", (first[0], second[0]))
        dy = _defer("sub", (first[1], second[1]))
        squared = _defer(
            "add", (_defer("square", (dx,)), _defer("square", (dy,)))
        )
        return mpf_sqrt(evaluate(squared, working + 5), precision, round_nearest)
    if op == "on_circle_pc":
        point, center, radius = args
        distance = _defer("distance_pp", (point, center))
        # Unlike a standalone Distance result, the predicate keeps the sqrt
        # and radius in one SymPy expression until its final Float boundary.
        first, second = distance.operands
        dx = _defer("sub", (first[0], second[0]))
        dy = _defer("sub", (first[1], second[1]))
        squared = _defer(
            "add", (_defer("square", (dx,)), _defer("square", (dy,)))
        )
        # Intersections can make this predicate cancel hundreds of bits.  The
        # frozen symbolic tree retains that cancellation; a fixed high guard
        # budget is cheaper than reconstructing/simplifying the tree and is
        # sufficient for binary53 producer leaves plus the certified geometry
        # depth cap.
        working = precision + _PERIODIC_CANCELLATION_GUARD
        distance_value = mpf_sqrt(evaluate(squared, working + 5), working, round_nearest)
        radius_value = evaluate(radius, working)
        result, _accuracy = add_terms(
            [(distance_value, working), (mpf_neg(radius_value), working)],
            precision,
            precision,
        )
        return from_int(0) if result is None else result
    if op == "area_points":
        # Area's canonical Add ordering is structure-sensitive.  The direct
        # Area closure was independently qualified at its BF53 boundary;
        # retain that specialized evaluator until the generated flat ordering
        # table covers arbitrary polygon arity.
        return _eval_deferred(expression, precision)
    # Angle/exact-unary closures already have a separately bit-qualified
    # libmp evaluator.  They remain in the same topology without SymPy.
    return _eval_deferred(expression, precision)


def _atan2_sympy(y: Scalar, x: Scalar) -> Scalar:
    """Reproduce ``atan2``'s Float ratio and symbolic-pi quadrant path."""

    if isinstance(y, _LocalInvalid):
        return y
    if isinstance(x, _LocalInvalid):
        return x
    if isinstance(y, _Deferred) or isinstance(x, _Deferred):
        return _defer("sympy_atan2", (y, x))
    y_mpf, x_mpf = _as_mpf(y), _as_mpf(x)
    y_sign, x_sign = _mpf_sign(y_mpf), _mpf_sign(x_mpf)
    if y_sign is None or x_sign is None:
        return fnan
    if x_sign == 0:
        if y_sign > 0:
            return _div(math.pi, 2)
        if y_sign < 0:
            return _div(-math.pi, 2)
        return fnan
    ratio = mpf_div(y_mpf, x_mpf, _PREC, round_nearest)
    angle = mpf_pos(mpf_atan(ratio, _EVALF_PREC, round_nearest), _PREC, round_nearest)
    if x_sign < 0:
        pi_value = mpf_pi(_TRIG_ARG_PREC, round_nearest)
        angle = mpf_add(
            angle,
            pi_value if y_sign >= 0 else mpf_neg(pi_value),
            _EVALF_PREC,
            round_nearest,
        )
        angle = mpf_pos(angle, _PREC, round_nearest)
    return angle


_SUPPORTED = {
    "ExactInt",
    "BF53Literal",
    "BF53Input",
    "Pi",
    "Add",
    "Sub",
    "Mult",
    "Div",
    "Pow",
    "USub",
    "UAdd",
    "Sqrt",
    "Cos",
    "Sin",
    "Abs",
    "Point",
    "Circle",
    "PointOnCircle",
    "PointOnSegment",
    "PointOnLine",
    "LinePP",
    "LineABC",
    "DistancePP",
    "DistancePL",
    "DistanceLP",
    "DistancePC",
    "DistanceCP",
    "AreaPoints",
    "AnglePPP",
    "AngleLL",
    "MidpointPP",
    "CircleCenter",
    "CircleRadius",
    "PointX",
    "PointY",
    "Circumcenter",
    "Circumcircle",
    "Orthocenter",
    "Centroid",
    "Incenter",
    "Incircle",
    "Excenter",
    "Excircle",
    "FootLP",
    "FootPL",
    "ParallelLineLP",
    "ParallelLinePL",
    "PerpendicularLineLP",
    "PerpendicularLinePL",
    "ParallelLL",
    "PerpendicularLL",
    "OnCirclePC",
    "OnLinePL",
    "OnLinePPP",
    "OnSegmentPPP",
    "ReflectPP",
    "ReflectPL",
    "ContactPointCL",
    "ContactPointLC",
    "IncircleContactPoint",
    "PerpendicularBisector",
    "AngleBisector",
    "IsTangentLC",
    "IsTangentCL",
    "Intersect",
}


@dataclass(frozen=True, slots=True)
class _RawNode:
    opcode: str
    operands: tuple[int, ...]
    payload: Any


@dataclass(frozen=True, slots=True)
class RawLibmpProgram:
    """Identity-free executable raw-libmp residual program."""

    variable_names: tuple[str, ...]
    nodes: tuple[_RawNode, ...]
    construction_roots: tuple[int, ...]
    constraint_roots: tuple[tuple[int, int], ...]
    semantic_abi: str = RAW_LIBMP_ABI
    periodic_deep_constraint_sides: tuple[tuple[bool, bool], ...] = ()

    def metadata(self) -> dict[str, Any]:
        opcodes = sorted({node.opcode for node in self.nodes})
        support_key = {
            "opcodes": opcodes,
            "semantic_abi": self.semantic_abi,
            "fallback_scope": "whole_problem",
        }
        return {
            **support_key,
            "support_key_sha256": hashlib.sha256(
                json.dumps(support_key, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "case_specific_routing": False,
            "problem_identity_read": False,
            "corpus_metadata_read": False,
            "native_libm": False,
            "fastmath": False,
            "numeric_backend": "mpmath.libmp binary53 round_nearest",
        }

    def evaluate(self, raw_values: list[float]) -> list[float]:
        if len(raw_values) != len(self.variable_names):
            raise ValueError("raw libmp evaluator dimension mismatch")
        # One thread-local hash-cons table is reused as a preallocated logical
        # slot map for this callback.  Replacing it here prevents provenance
        # or values from leaking between optimizer starts/problems.
        _DEFERRED_STATE.cache = {}
        memo: list[Any] = [_MISSING] * len(self.nodes)

        def evaluate_node(index: int) -> Any:
            cached = memo[index]
            if cached is not _MISSING:
                return cached
            node = self.nodes[index]
            op = node.opcode
            # Leaves account for a substantial fraction of a typed DAG.  Do
            # not allocate their generator/argument tuple on every optimizer
            # callback.
            args = tuple(evaluate_node(child) for child in node.operands) if node.operands else ()
            if op == "ExactInt":
                result: Any = int(node.payload)
            elif op == "BF53Literal":
                result = float(node.payload)
            elif op == "BF53Input":
                result = float(raw_values[int(node.payload)])
            elif op == "Pi":
                result = math.pi
            elif op == "Add":
                result = _add(args[0], args[1])
            elif op == "Sub":
                result = _sub(args[0], args[1])
            elif op == "Mult":
                result = _mul(args[0], args[1])
            elif op == "Div":
                result = _div(args[0], args[1])
            elif op == "Pow":
                exponent = args[1]
                if not isinstance(exponent, int):
                    raise RawLibmpRuntimeFault("raw Pow requires an exact integer exponent")
                result = (
                    mpf_pow_int(args[0], exponent, _PREC, round_nearest)
                    if _is_mpf(args[0])
                    else _defer("pow_int", (args[0], exponent))
                    if isinstance(args[0], _Deferred)
                    else args[0] ** exponent
                )
            elif op == "USub":
                result = _neg(args[0])
            elif op == "UAdd":
                result = args[0]
            elif op == "Sqrt":
                result = _sqrt(args[0])
            elif op == "Cos":
                result = _evalf_unary(mpf_cos, args[0])
            elif op == "Sin":
                result = _evalf_unary(mpf_sin, args[0])
            elif op == "Abs":
                result = _abs(args[0])
            elif op == "Point":
                result = _point(args[0], args[1])
            elif op == "Circle":
                result = _circle(args[0], args[1])
            elif op == "PointOnCircle":
                center, radius = args[0]
                result = _point(
                    _add(center[0], _mul(radius, _periodic_trig(args[1], cosine=True))),
                    _add(center[1], _mul(radius, _periodic_trig(args[1], cosine=False))),
                )
            elif op == "PointOnSegment":
                first, second, parameter = args
                result = _point(
                    _add(first[0], _mul(parameter, _sub(second[0], first[0]))),
                    _add(first[1], _mul(parameter, _sub(second[1], first[1]))),
                )
            elif op == "PointOnLine":
                line, parameter = args
                denominator = _add(_mul(line[0], line[0]), _mul(line[1], line[1]))
                result = _point(
                    _sub(
                        _div(_neg(_mul(line[0], line[2])), denominator),
                        _mul(line[1], parameter),
                    ),
                    _add(
                        _div(_neg(_mul(line[1], line[2])), denominator),
                        _mul(line[0], parameter),
                    ),
                )
            elif op == "LinePP":
                first, second = args
                result = _line_coefficients(
                    _sub(first[1], second[1]),
                    _sub(second[0], first[0]),
                    _sub(_mul(first[0], second[1]), _mul(second[0], first[1])),
                )
            elif op == "LineABC":
                result = _line_coefficients(args[0], args[1], args[2])
            elif op == "DistancePP":
                result = _distance_pp(args[0], args[1])
                if node.payload == "periodic_flat" and isinstance(result, _Deferred):
                    result = _defer("distance_pp_flat", result.operands)
            elif op == "DistancePL":
                result = (
                    _distance_pp(args[0], None)
                    if args[1] is None
                    else _distance_pl(args[0], args[1])
                )
            elif op == "DistanceLP":
                result = _distance_pl(args[1], args[0])
            elif op in {"DistancePC", "DistanceCP"}:
                if op == "DistancePC" and args[1] is None:
                    result = _distance_pp(args[0], None)
                else:
                    point, circle = (args[0], args[1]) if op == "DistancePC" else (args[1], args[0])
                    result = _abs(_sub(_distance_pp(point, circle[0]), circle[1]))
            elif op == "AreaPoints":
                result = _area_points(args)
            elif op == "AnglePPP":
                first, vertex, third = args
                bax, bay = _sub(first[0], vertex[0]), _sub(first[1], vertex[1])
                bcx, bcy = _sub(third[0], vertex[0]), _sub(third[1], vertex[1])
                determinant = _abs(_sub(_mul(bax, bcy), _mul(bay, bcx)))
                dot = _add(_mul(bax, bcx), _mul(bay, bcy))
                result = (
                    _defer("angle_ppp", (determinant, dot))
                    if node.payload == "constraint_scalar_deferred"
                    else _atan2_sympy(determinant, dot)
                )
            elif op == "AngleLL":
                dot = _abs(_add(_mul(args[0][0], args[1][0]), _mul(args[0][1], args[1][1])))
                result = (
                    _defer("angle_ll", (dot,))
                    if node.payload == "constraint_scalar_deferred"
                    else _evalf_unary(mpf_acos, dot)
                )
            elif op == "MidpointPP":
                result = _point(
                    _div(_add(args[0][0], args[1][0]), 2),
                    _div(_add(args[0][1], args[1][1]), 2),
                )
            elif op == "CircleCenter":
                result = args[0][0]
            elif op == "CircleRadius":
                result = args[0][1]
            elif op == "PointX":
                result = args[0][0]
            elif op == "PointY":
                result = args[0][1]
            elif op in {"Circumcenter", "Circumcircle"}:
                center = _circumcenter(args[0], args[1], args[2])
                result = (
                    center
                    if op == "Circumcenter" or center is None
                    else _circle(center, _distance_pp(center, args[0]))
                )
            elif op == "Orthocenter":
                a, b, c = args
                dx_bc, dy_bc = _sub(c[0], b[0]), _sub(c[1], b[1])
                k1 = _add(_mul(dx_bc, a[0]), _mul(dy_bc, a[1]))
                dx_ca, dy_ca = _sub(a[0], c[0]), _sub(a[1], c[1])
                k2 = _add(_mul(dx_ca, b[0]), _mul(dy_ca, b[1]))
                determinant = _sub(_mul(dx_bc, dy_ca), _mul(dx_ca, dy_bc))
                result = (
                    None
                    if _is_zero(determinant)
                    else _point(
                        _div(_sub(_mul(k1, dy_ca), _mul(k2, dy_bc)), determinant),
                        _div(_sub(_mul(dx_bc, k2), _mul(dx_ca, k1)), determinant),
                    )
                )
            elif op == "Centroid":
                result = _point(
                    _div(_add(_add(args[0][0], args[1][0]), args[2][0]), 3),
                    _div(_add(_add(args[0][1], args[1][1]), args[2][1]), 3),
                )
            elif op == "Incenter":
                result = _incenter(args[0], args[1], args[2])
            elif op == "Incircle":
                a, b, c = args
                center = _incenter(a, b, c)
                double_area = _abs(
                    _add(
                        _add(_mul(a[0], _sub(b[1], c[1])), _mul(b[0], _sub(c[1], a[1]))),
                        _mul(c[0], _sub(a[1], b[1])),
                    )
                )
                perimeter = _add(_add(_distance_pp(b, c), _distance_pp(c, a)), _distance_pp(a, b))
                # Frozen Incircle defines the all-coincident case as the
                # incenter with zero radius rather than letting 0/0 abort the
                # complete construction pass.
                result = _circle(center, 0 if _is_zero(perimeter) else _div(double_area, perimeter))
            elif op in {"Excenter", "Excircle"}:
                a, b, c = args
                if node.payload == "B":
                    a, b, c = b, c, a
                elif node.payload == "C":
                    a, b, c = c, a, b
                center = _incenter(a, b, c, external=True)
                if op == "Excenter":
                    result = center
                else:
                    double_area = _abs(
                        _add(
                            _add(
                                _mul(a[0], _sub(b[1], c[1])),
                                _mul(b[0], _sub(c[1], a[1])),
                            ),
                            _mul(c[0], _sub(a[1], b[1])),
                        )
                    )
                    denominator = _add(
                        _add(_neg(_distance_pp(b, c)), _distance_pp(c, a)),
                        _distance_pp(a, b),
                    )
                    result = _circle(
                        center, 0 if _is_zero(denominator) else _div(double_area, denominator)
                    )
            elif op in {"FootLP", "FootPL"}:
                line, point = (args[0], args[1]) if op == "FootLP" else (args[1], args[0])
                result = _foot(line, point)
            elif op in {"ParallelLineLP", "ParallelLinePL"}:
                line, point = (args[0], args[1]) if op.endswith("LP") else (args[1], args[0])
                result = _line_coefficients(
                    line[0],
                    line[1],
                    _neg(_add(_mul(line[0], point[0]), _mul(line[1], point[1]))),
                )
            elif op in {"PerpendicularLineLP", "PerpendicularLinePL"}:
                line, point = (args[0], args[1]) if op.endswith("LP") else (args[1], args[0])
                a, b = line[1], _neg(line[0])
                result = _line_coefficients(a, b, _neg(_add(_mul(a, point[0]), _mul(b, point[1]))))
            elif op == "ParallelLL":
                result = _sub(_mul(args[0][0], args[1][1]), _mul(args[1][0], args[0][1]))
            elif op == "PerpendicularLL":
                result = _add(_mul(args[0][0], args[1][0]), _mul(args[0][1], args[1][1]))
            elif op == "OnCirclePC":
                distance = _distance_pp(args[0], args[1][0])
                result = (
                    _defer("on_circle_pc", (args[0], args[1][0], args[1][1]))
                    if _contains_deferred_opcode(
                        (distance, args[1][1]), {"periodic_cos", "periodic_sin"}
                    )
                    else _sub(distance, args[1][1])
                )
            elif op == "OnLinePL":
                result = _distance_pl(args[0], args[1])
            elif op == "OnLinePPP":
                point, first, second = args
                result = _sub(
                    _mul(_sub(first[0], point[0]), _sub(second[1], point[1])),
                    _mul(_sub(first[1], point[1]), _sub(second[0], point[0])),
                )
            elif op == "OnSegmentPPP":
                result = _sub(
                    _add(_distance_pp(args[1], args[0]), _distance_pp(args[0], args[2])),
                    _distance_pp(args[1], args[2]),
                )
            elif op == "ReflectPP":
                result = _point(
                    _sub(_mul(2, args[1][0]), args[0][0]),
                    _sub(_mul(2, args[1][1]), args[0][1]),
                )
            elif op == "ReflectPL":
                projection = _foot(args[1], args[0])
                result = _point(
                    _sub(_mul(2, projection[0]), args[0][0]),
                    _sub(_mul(2, projection[1]), args[0][1]),
                )
            elif op in {"ContactPointCL", "ContactPointLC"}:
                circle, line = (args[0], args[1]) if op == "ContactPointCL" else (args[1], args[0])
                result = _foot(line, circle[0])
            elif op == "IncircleContactPoint":
                a, b, c = args
                side_a, side_b, side_c = _distance_pp(b, c), _distance_pp(c, a), _distance_pp(a, b)
                semiperimeter = _div(_add(_add(side_a, side_b), side_c), 2)

                def contact(first: Point, second: Point, numerator: Scalar, side: Scalar) -> Point:
                    try:
                        ratio = _div(numerator, side)
                        return _point(
                            _add(first[0], _mul(_sub(second[0], first[0]), ratio)),
                            _add(first[1], _mul(_sub(second[1], first[1]), ratio)),
                        )
                    except Exception:
                        # Frozen SymPy eagerly creates all D/E/F points.  A
                        # zero side produces zoo/nan coordinates but does not
                        # abort construction of a different selected side.
                        return _point(fnan, fnan)

                contacts = {
                    "BC": contact(b, c, _sub(semiperimeter, side_b), side_a),
                    "CA": contact(c, a, _sub(semiperimeter, side_c), side_b),
                    "AB": contact(a, b, _sub(semiperimeter, side_a), side_c),
                }
                result = contacts[str(node.payload)]
            elif op == "PerpendicularBisector":
                first, second = args
                mid_x, mid_y = (
                    _div(_add(first[0], second[0]), 2),
                    _div(_add(first[1], second[1]), 2),
                )
                a, b = _sub(second[0], first[0]), _neg(_sub(first[1], second[1]))
                # The frozen helper catches its degenerate Line constructor
                # and stores None.  Consumers then decide the fault scope.
                result = (
                    None
                    if _is_zero(a) and _is_zero(b)
                    else _line_coefficients(a, b, _neg(_add(_mul(a, mid_x), _mul(b, mid_y))))
                )
            elif op == "AngleBisector":
                a, b, c = args
                bax, bay = _sub(a[0], b[0]), _sub(a[1], b[1])
                bcx, bcy = _sub(c[0], b[0]), _sub(c[1], b[1])
                norm_ba = _sqrt(_add(_mul(bax, bax), _mul(bay, bay)))
                norm_bc = _sqrt(_add(_mul(bcx, bcx), _mul(bcy, bcy)))
                if _is_zero(norm_ba) or _is_zero(norm_bc):
                    result = None
                else:
                    ux, uy = _div(bax, norm_ba), _div(bay, norm_ba)
                    vx, vy = _div(bcx, norm_bc), _div(bcy, norm_bc)
                    wx, wy = _add(ux, vx), _add(uy, vy)
                    if _is_zero(wx) and _is_zero(wy):
                        wx, wy = _neg(uy), ux
                    px, py = _add(b[0], wx), _add(b[1], wy)
                    line_a, line_b = _sub(b[1], py), _sub(px, b[0])
                    line_c = _sub(_neg(_mul(line_a, b[0])), _mul(line_b, b[1]))
                    result = _line_coefficients(line_a, line_b, line_c)
            elif op in {"IsTangentLC", "IsTangentCL"}:
                line, circle = (args[0], args[1]) if op == "IsTangentLC" else (args[1], args[0])
                result = _abs(_sub(_distance_pl(circle[0], line), circle[1]))
            elif op == "Intersect":
                plan, selector_names = node.payload
                selector_values = dict(zip(selector_names, args[2:], strict=True))
                result, _trace = evaluate_raw_intersect(
                    plan,
                    args[0],
                    args[1],
                    selector_values=selector_values,
                )
            else:  # pragma: no cover - compiler/runtime invariant
                raise RawLibmpRuntimeFault(f"unknown raw opcode: {op}")
            memo[index] = result
            return result

        try:
            for root in self.construction_roots:
                evaluate_node(root)
        except Exception:
            return [float("nan")] * len(self.constraint_roots)
        residuals: list[float] = []
        for constraint_ordinal, (left, right) in enumerate(self.constraint_roots):
            try:
                left_value, right_value = evaluate_node(left), evaluate_node(right)
                deep_sides = (
                    self.periodic_deep_constraint_sides[constraint_ordinal]
                    if constraint_ordinal < len(self.periodic_deep_constraint_sides)
                    else (False, False)
                )
                if any(deep_sides):
                    left_float = (
                        _as_float(left_value)
                        if not deep_sides[0]
                        or _contains_deferred_opcode(left_value, {"on_circle_pc"})
                        else _evaluate_cached_periodic_tape(id(self), (left, 0), left_value)
                        if isinstance(left_value, _Deferred)
                        else _as_float(left_value)
                    )
                    right_float = (
                        _as_float(right_value)
                        if not deep_sides[1]
                        or _contains_deferred_opcode(right_value, {"on_circle_pc"})
                        else _evaluate_cached_periodic_tape(id(self), (right, 1), right_value)
                        if isinstance(right_value, _Deferred)
                        else _as_float(right_value)
                    )
                else:
                    left_float = _as_float(left_value)
                    right_float = _as_float(right_value)
                residuals.append(left_float - right_float)
            except Exception:
                residuals.append(float("nan"))
        return residuals


def compile_raw_libmp_program(program: TypedRefNumProgram) -> RawLibmpProgram:
    """Compile by opcode/type semantics only; reject any partial program."""

    nodes: list[_RawNode] = []
    indexes: dict[int, int] = {}
    exact_indexes: dict[tuple[Any, ...], int] = {}
    exact_nodes: set[int] = set()
    input_indexes = {name: index for index, name in enumerate(program.variable_names)}

    periodic_deep_opcodes = {
        "Circumcircle",
        "PerpendicularLineLP",
        "PerpendicularLinePL",
        "ReflectPP",
        "ReflectPL",
        "Intersect",
    }
    qualified_point_on_circle_consumers = {
        # Scalar/coordinate closure used to build derived entities.
        "PointX",
        "PointY",
        "CircleCenter",
        "CircleRadius",
        "Add",
        "Sub",
        "Mult",
        "Div",
        "Pow",
        "USub",
        "UAdd",
        "Abs",
        "Sqrt",
        # The first qualified derived geometry closure.
        "Point",
        "MidpointPP",
        "LinePP",
        "LineABC",
        "Circle",
        "Circumcircle",
        "PerpendicularLineLP",
        "PerpendicularLinePL",
        "ReflectPP",
        "ReflectPL",
        "Intersect",
        # Qualified terminal measurements.
        "DistancePP",
        "DistancePL",
        "DistanceLP",
        "DistancePC",
        "DistanceCP",
        "AreaPoints",
        "AnglePPP",
        "AngleLL",
        "OnCirclePC",
    }
    # These consumers are implemented by the raw runtime, but their current
    # libmp expression topology is not a rounding-equivalent replacement for
    # the frozen SymPy BF53 boundary when fed by periodic coordinates.  The
    # distinction is structural (producer/consumer signature), never based on
    # a problem id or corpus membership.  Keep the whole program on the
    # reference evaluator until that signature has passed generated
    # differential and optimizer-trace qualification.
    unqualified_periodic_rounding_consumers = {
        "Circumcircle",
        "PerpendicularLineLP",
        "PerpendicularLinePL",
        "ReflectPP",
        "ReflectPL",
        "Intersect",
        "OnCirclePC",
    }

    analysis = program.numeric_effect_analysis()

    def certify_periodic_effect_closure() -> set[int]:
        """Certify all downstream PointOnCircle edges by effect and type.

        Taint starts at every periodic point and follows the typed consumer
        graph.  This is deliberately independent of construction names,
        source ids, and corpus membership.  The opcode set records operations
        whose raw implementation preserves deferred symbolic composition;
        the shared effect policy additionally certifies fault, non-finite,
        signed-zero, subnormal, and branch-sensitive transitions.
        """

        tainted = {
            node.index for node in analysis.nodes if node.opcode == "PointOnCircle"
        }
        tainted_edges = []
        changed = True
        while changed:
            changed = False
            for edge in analysis.edges:
                if edge.producer_index not in tainted:
                    continue
                tainted_edges.append(edge)
                if edge.consumer_opcode in unqualified_periodic_rounding_consumers:
                    raise UnsupportedRawLibmpBackend(
                        "PointOnCircle rounding edge into "
                        f"{edge.consumer_opcode} ({edge.role.value}) is not qualified"
                    )
                if edge.consumer_index is None:
                    continue
                if edge.consumer_opcode not in qualified_point_on_circle_consumers:
                    raise UnsupportedRawLibmpBackend(
                        "PointOnCircle effect edge into "
                        f"{edge.consumer_opcode} ({edge.role.value}) is not qualified"
                    )
                if edge.consumer_index not in tainted:
                    tainted.add(edge.consumer_index)
                    changed = True

        capability = ConsumerCapability(
            allow_may_fault=True,
            allow_may_nonfinite=True,
            allow_signed_zero=True,
            allow_subnormal=True,
            allow_branch_sensitive=True,
            preserve_symbolic_composition=True,
        )
        certification = certify_numeric_effects(
            NumericEffectAnalysis(
                tuple(node for node in analysis.nodes if node.index in tainted),
                tuple(dict.fromkeys(tainted_edges)),
            ),
            NumericEffectPolicy(
                default=capability,
                by_role={role: capability for role in ConsumerRole},
            ),
        )
        if not certification.certified:  # pragma: no cover - policy invariant
            issue = certification.issues[0]
            raise UnsupportedRawLibmpBackend(
                "PointOnCircle numeric effect is not preserved at "
                f"{issue.edge.consumer_opcode}: {','.join(issue.unsupported_effects)}"
            )
        return tainted

    periodic_tainted = certify_periodic_effect_closure()

    def subtree_contains_opcode(node: IRNode, opcode: str, seen: set[int]) -> bool:
        identity = id(node)
        if identity in seen:
            return False
        seen.add(identity)
        return node.opcode == opcode or any(
            subtree_contains_opcode(child, opcode, seen) for child in node.operands
        )

    def contains_periodic_deep(node: IRNode, seen: set[int] | None = None) -> bool:
        """Whether this root contains a deep consumer fed by PointOnCircle.

        This decision is structural and root-local.  A deep periodic branch in
        one constraint must not change the rounding boundary of an unrelated
        direct periodic measurement in the same problem.
        """

        if seen is None:
            seen = set()
        identity = id(node)
        if identity in seen:
            return False
        seen.add(identity)
        if node.opcode in periodic_deep_opcodes and subtree_contains_opcode(
            node, "PointOnCircle", set()
        ):
            return True
        return any(contains_periodic_deep(child, seen) for child in node.operands)

    qualified_periodic_deep_roots = {
        # Coordinate projections are terminal scalar observations.  They are
        # already certified in the PointOnCircle consumer closure above and
        # must remain available when an intersection selector (near/far/
        # exclude) depends on the periodic point.
        "PointX",
        "PointY",
        "DistancePP",
        "DistancePL",
        "DistanceLP",
        "DistancePC",
        "DistanceCP",
        "AreaPoints",
        "AnglePPP",
        "AngleLL",
        "OnCirclePC",
    }
    for constraint in program.constraints:
        for side in constraint:
            if (
                contains_periodic_deep(side)
                and side.opcode not in qualified_periodic_deep_roots
            ):
                raise UnsupportedRawLibmpBackend(
                    "PointOnCircle deep scalar composition root is not "
                    f"bit-qualified: {side.opcode}"
                )

    # A non-periodic Distance may fault while producing a construction
    # coordinate.  Frozen construction evaluation then invalidates a broader
    # scope than a predicate-side raw residual.  Keep that edge fail-closed.
    # Periodic chains are separately certified above and retain their
    # deferred expression through the final predicate boundary.
    distance_tainted = {
        node.index
        for node in analysis.nodes
        if node.opcode.startswith("Distance") and node.index not in periodic_tainted
    }
    changed = True
    while changed:
        changed = False
        for edge in analysis.edges:
            if edge.producer_index not in distance_tainted:
                continue
            if edge.consumer_opcode == "OnCirclePC":
                raise UnsupportedRawLibmpBackend(
                    "Distance-derived geometry consumed by OnCircle is not "
                    "fault-scope-qualified"
                )
            if (
                edge.consumer_index is not None
                and edge.consumer_index not in distance_tainted
            ):
                distance_tainted.add(edge.consumer_index)
                changed = True

    periodic_producer_opcodes = {
        # Scalars.  Exact and BF53 provenance remains attached to the typed
        # node; this list admits operation semantics, not arbitrary Python.
        "BF53Input",
        "BF53Literal",
        "ExactInt",
        "Pi",
        "Add",
        "Sub",
        "Mult",
        "Div",
        "Pow",
        "USub",
        "UAdd",
        "Sqrt",
        "Cos",
        "Sin",
        "Abs",
        "PointX",
        "PointY",
        "CircleRadius",
        "DistancePP",
        "DistancePL",
        "DistanceLP",
        "DistancePC",
        "DistanceCP",
        "AreaPoints",
        "AnglePPP",
        "AngleLL",
        # Geometry values whose raw implementations retain libmp/deferred
        # coordinates and fail with the same constructor scope.
        "Point",
        "MidpointPP",
        "CircleCenter",
        "LinePP",
        "LineABC",
        "Circle",
        "Circumcenter",
        "Circumcircle",
        "Centroid",
        "FootLP",
        "FootPL",
        "PerpendicularLineLP",
        "PerpendicularLinePL",
        "ReflectPP",
        "ReflectPL",
        "Intersect",
        "PointOnCircle",
    }

    def is_qualified_periodic_producer(node: IRNode, seen: set[int]) -> bool:
        identity = id(node)
        if identity in seen:
            return True
        seen.add(identity)
        return node.opcode in periodic_producer_opcodes and all(
            is_qualified_periodic_producer(child, seen) for child in node.operands
        )

    def is_qualified_periodic_circle(circle: IRNode) -> bool:
        """Recognize only the circle shape covered by the periodic ABI.

        PointOnCircle keeps trigonometric coordinates symbolic in the frozen
        evaluator.  Arithmetic in its center, radius, or parameter therefore
        is not transitively qualified merely because each individual opcode
        has a raw implementation.
        """

        if circle.result_type != "circle2":
            return False
        return is_qualified_periodic_producer(circle, set())

    def unqualified_point_on_circle_shape(node: IRNode, seen: set[int]) -> str | None:
        if id(node) in seen:
            return None
        seen.add(id(node))
        if node.opcode == "PointOnCircle":
            circle, parameter = node.operands
            if not is_qualified_periodic_circle(circle):
                return "circle producer"
            if parameter.result_type != "scalar" or not is_qualified_periodic_producer(
                parameter, set()
            ):
                return "parameter producer"
        for child in node.operands:
            unqualified = unqualified_point_on_circle_shape(child, seen)
            if unqualified is not None:
                return unqualified
        return None

    for _name, construction in program.constructions:
        unqualified_shape = unqualified_point_on_circle_shape(construction, set())
        if unqualified_shape is not None:
            raise UnsupportedRawLibmpBackend(
                f"PointOnCircle {unqualified_shape} is not composition-qualified"
            )
    for left, right in program.constraints:
        for side in (left, right):
            unqualified_shape = unqualified_point_on_circle_shape(side, set())
            if unqualified_shape is not None:
                raise UnsupportedRawLibmpBackend(
                    f"PointOnCircle {unqualified_shape} is not composition-qualified"
                )

    def has_input(node: IRNode, seen: set[int]) -> bool:
        if id(node) in seen:
            return False
        seen.add(id(node))
        return node.opcode == "BF53Input" or any(
            has_input(child, seen) for child in node.operands
        )

    def contains_input_free_exact_unary(node: IRNode, seen: set[int]) -> bool:
        if id(node) in seen:
            return False
        seen.add(id(node))
        if node.opcode in {"Sqrt", "Cos", "Sin"} and not has_input(
            node.operands[0], set()
        ):
            return True
        return any(
            contains_input_free_exact_unary(child, seen) for child in node.operands
        )

    all_nodes: dict[int, IRNode] = {}

    def collect_nodes(node: IRNode) -> None:
        if id(node) in all_nodes:
            return
        all_nodes[id(node)] = node
        for child in node.operands:
            collect_nodes(child)

    for _name, construction in program.constructions:
        collect_nodes(construction)
    for constraint in program.constraints:
        for side in constraint:
            collect_nodes(side)
    exact_downstream_count = sum(
        contains_input_free_exact_unary(node, set()) for node in all_nodes.values()
    )
    if exact_downstream_count > MAX_EXACT_UNARY_DOWNSTREAM_NODES:
        # The correctness-first SymPy boundary is intentionally bounded by
        # DAG structure.  Larger closures need the future compiled,
        # accuracy-aware tape; admitting them here would make an "optimized"
        # callback take seconds.  This resource gate is independent of case
        # identity and belongs to the raw ABI.
        raise UnsupportedRawLibmpBackend(
            "exact unary downstream DAG exceeds the qualified resource cap"
        )

    angle_opcodes = {"AnglePPP", "AngleLL"}
    angle_scalar_consumers = {
        "Add",
        "Sub",
        "Mult",
        "Div",
        "Pow",
        "USub",
        "UAdd",
        "Abs",
        "Sqrt",
        "Cos",
        "Sin",
    }
    deferred_angle_ids: set[int] = set()

    def qualify_angle_paths(
        node: IRNode,
        *,
        path_is_scalar: bool,
        direct_constraint_side: bool,
    ) -> None:
        """Qualify every Angle producer/use edge without reading case identity.

        The frozen producer is symbolic.  It may be retained through the
        listed pure scalar operations and materialized once at a residual
        boundary.  Geometry, selector, and predicate consumers observe a
        different fault/rounding scope, so any such path rejects the entire
        problem rather than mixing evaluators within one geometry DAG.
        """

        if node.opcode in angle_opcodes:
            if not path_is_scalar:
                raise UnsupportedRawLibmpBackend(
                    "Angle composition through a geometry or selector consumer "
                    "is not bit-qualified"
                )
            if not direct_constraint_side:
                deferred_angle_ids.add(id(node))
            return
        child_path_is_scalar = path_is_scalar and node.opcode in angle_scalar_consumers
        for child in node.operands:
            qualify_angle_paths(
                child,
                path_is_scalar=child_path_is_scalar,
                direct_constraint_side=False,
            )

    for _name, construction in program.constructions:
        # An Angle stored directly as a scalar construction remains symbolic.
        # For every other construction, the opcode chain itself decides
        # whether this is a qualified scalar alias or an unsafe geometry use.
        qualify_angle_paths(
            construction,
            path_is_scalar=True,
            direct_constraint_side=False,
        )
    for constraint in program.constraints:
        for side in constraint:
            qualify_angle_paths(
                side,
                path_is_scalar=True,
                direct_constraint_side=True,
            )

    def compile_node(node: IRNode) -> int:
        identity = id(node)
        if identity in indexes:
            return indexes[identity]
        if node.opcode not in _SUPPORTED:
            raise UnsupportedRawLibmpBackend(f"unsupported raw opcode: {node.opcode}")
        if node.opcode == "Rational":
            raise UnsupportedRawLibmpBackend("exact Rational is outside raw ABI v1")
        children = tuple(compile_node(child) for child in node.operands)
        if node.opcode == "Pow":
            exponent = node.operands[1]
            if exponent.opcode != "ExactInt":
                raise UnsupportedRawLibmpBackend("raw Pow exponent must be an exact integer")
        input_free_exact = node.opcode in {
            "ExactInt",
            "Pi",
            "Add",
            "Sub",
            "Mult",
            "Div",
            "Pow",
            "USub",
            "UAdd",
            "Sqrt",
            "Cos",
            "Sin",
            "Abs",
        } and all(child in exact_nodes for child in children)
        exact_key = (
            node.opcode,
            repr(node.payload),
            children,
        )
        if input_free_exact and exact_key in exact_indexes:
            index = exact_indexes[exact_key]
            indexes[identity] = index
            return index
        index = len(nodes)
        indexes[identity] = index
        payload = input_indexes[str(node.payload)] if node.opcode == "BF53Input" else node.payload
        if node.opcode == "DistancePP" and contains_periodic_deep(node):
            payload = "periodic_flat"
        if node.opcode in angle_opcodes and identity in deferred_angle_ids:
            payload = "constraint_scalar_deferred"
        nodes.append(_RawNode(node.opcode, children, payload))
        if input_free_exact:
            exact_indexes[exact_key] = index
            exact_nodes.add(index)
        return index

    construction_roots = tuple(compile_node(node) for _name, node in program.constructions)
    constraint_roots = tuple(
        (compile_node(left), compile_node(right)) for left, right in program.constraints
    )
    periodic_deep_constraint_sides = tuple(
        (contains_periodic_deep(left), contains_periodic_deep(right))
        for left, right in program.constraints
    )
    return RawLibmpProgram(
        variable_names=program.variable_names,
        nodes=tuple(nodes),
        construction_roots=construction_roots,
        constraint_roots=constraint_roots,
        periodic_deep_constraint_sides=periodic_deep_constraint_sides,
    )


__all__ = [
    "RAW_LIBMP_ABI",
    "RawLibmpProgram",
    "UnsupportedRawLibmpBackend",
    "compile_raw_libmp_program",
]
