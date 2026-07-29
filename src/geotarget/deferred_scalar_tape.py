"""Compiled libmp tape for delayed scalar geometry expressions.

The frozen evaluator deliberately keeps a small scalar expression symbolic
until the final ``Float`` boundary.  Rebuilding that expression with SymPy on
every optimizer callback is correct but expensive.  This module lowers the
topology once into precision-specialised SSA slots and subsequently executes
only libmp operations.

The compiler is intentionally independent of ``raw_libmp_backend``.  It
accepts :class:`DeferredScalar` nodes and, for the raw adapter, any object with
the same ``opcode``/``operands`` attributes.  Dynamic leaves are represented
by :class:`InputSlot`.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from mpmath.libmp.libelefun import (
    mpf_acos,
    mpf_atan,
    mpf_cos,
    mpf_pi,
    mpf_sin,
)
from mpmath.libmp.libmpf import (
    fnan,
    from_float,
    from_int,
    fzero,
    mpf_abs,
    mpf_div,
    mpf_eq,
    mpf_mod,
    mpf_mul_int,
    mpf_neg,
    mpf_pos,
    mpf_pow_int,
    mpf_sqrt,
    normalize,
    round_nearest,
    to_float,
)
from sympy.core.evalf import add_terms

Mpf = tuple[int, int, int, int]

DEFERRED_SCALAR_TAPE_ABI = "geotarget.deferred-scalar-tape/sympy-1.14-bf53-v1"
BF53_PRECISION = 53
EVALF_BOUNDARY_PRECISION = 57
PERIODIC_GEOMETRY_CANCELLATION_GUARD = 356


class UnsupportedDeferredScalar(RuntimeError):
    """Raised when a delayed expression lies outside the frozen scalar ABI."""


@dataclass(frozen=True, slots=True)
class InputSlot:
    """A binary64 callback input identified by its stable ordinal."""

    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("input slot index must be non-negative")


@dataclass(frozen=True, slots=True)
class DeferredScalar:
    """Small public construction node accepted by the tape compiler."""

    opcode: str
    operands: tuple[Any, ...]


def deferred(opcode: str, *operands: Any) -> DeferredScalar:
    """Create a delayed scalar node without importing the raw backend."""

    return DeferredScalar(opcode, tuple(operands))


def periodic_sin(parameter: Any) -> DeferredScalar:
    """Return ``sin(2*pi*parameter)`` with frozen BF53 modulo semantics."""

    return deferred("periodic_sin_turns", parameter)


def periodic_cos(parameter: Any) -> DeferredScalar:
    """Return ``cos(2*pi*parameter)`` with frozen BF53 modulo semantics."""

    return deferred("periodic_cos_turns", parameter)


def area(points: Sequence[tuple[Any, Any]]) -> DeferredScalar:
    """Create the frozen absolute shoelace reduction for ``points``."""

    if len(points) < 3:
        raise ValueError("Area requires at least three points")
    return deferred("area_points", tuple(points))


def angle_atan2(determinant: Any, dot: Any) -> DeferredScalar:
    """Create the oriented point-angle boundary used by frozen ``Angle``."""

    return deferred("angle_ppp", determinant, dot)


def angle_acos(cosine: Any) -> DeferredScalar:
    """Create the unoriented line-angle boundary used by frozen ``Angle``."""

    return deferred("angle_ll", cosine)


class _Op(IntEnum):
    CONST = 1
    INPUT = 2
    ADD = 3
    SUB = 4
    MUL = 5
    DIV = 6
    NEG = 7
    ABS = 8
    SQRT = 9
    POW_INT = 10
    SIN = 11
    COS = 12
    ACOS = 13
    ATAN = 14
    PI = 15
    PERIODIC_SIN = 16
    PERIODIC_COS = 17
    ANGLE_ATAN2 = 18


@dataclass(frozen=True, slots=True)
class _Instruction:
    op: _Op
    out: int
    args: tuple[int, ...]
    precision: int
    payload: Any = None


def _is_mpf(value: Any) -> bool:
    return type(value) is tuple and len(value) == 4 and all(isinstance(item, int) for item in value)


def _as_mpf(value: Any) -> Mpf:
    if _is_mpf(value):
        return value
    if isinstance(value, bool):
        return from_int(int(value))
    if isinstance(value, int):
        return from_int(value)
    if isinstance(value, float):
        return from_float(value)
    raise TypeError(f"scalar input must be int, float, or libmp tuple; got {type(value)!r}")


def _sign(value: Mpf) -> int | None:
    if value == fnan:
        return None
    if value == fzero:
        return 0
    return -1 if value[0] else 1


def _mul_exact(left: Mpf, right: Mpf, precision: int) -> Mpf:
    mantissa = left[1] * right[1]
    return normalize(
        left[0] ^ right[0],
        mantissa,
        left[2] + right[2],
        mantissa.bit_length(),
        precision,
        round_nearest,
    )


def _sum_two(left: Mpf, right: Mpf, precision: int, accuracy: int) -> Mpf:
    result, _accuracy = add_terms([(left, accuracy), (right, accuracy)], precision, precision)
    # ``add_terms`` represents exact cancellation with SymPy's deliberately
    # malformed scaled-zero tuple (its sign limb is a list).  That sentinel is
    # only valid inside evalf accuracy accounting; a numeric tape must close it
    # to the ordinary libmp zero before a downstream opcode consumes the slot.
    return from_int(0) if result is None or not isinstance(result[0], int) else result


def _periodic_value(coefficient: Mpf, *, cosine: bool, precision: int) -> Mpf:
    zero = from_int(0)
    one = from_int(1)
    half = mpf_div(one, from_int(2), BF53_PRECISION, round_nearest)
    if mpf_eq(coefficient, zero):
        return one if cosine else zero
    if mpf_eq(coefficient, half):
        return zero if cosine else one
    if mpf_eq(coefficient, one):
        return from_int(-1) if cosine else zero
    three_halves = _sum_two(one, half, BF53_PRECISION, BF53_PRECISION)
    if mpf_eq(coefficient, three_halves):
        return zero if cosine else from_int(-1)

    argument_precision = precision + 20
    working = argument_precision + 7
    argument = _mul_exact(coefficient, mpf_pi(working, round_nearest), argument_precision)
    function = mpf_cos if cosine else mpf_sin
    return function(argument, precision, round_nearest)


class _Compiler:
    def __init__(self, boundary_precision: int) -> None:
        self.boundary_precision = boundary_precision
        self.instructions: list[_Instruction] = []
        self.cache: dict[tuple[int, int], int] = {}
        self.input_count = 0
        # Synthetic lowering nodes are keyed by identity just like raw
        # ``_Deferred`` objects.  Retain them until compilation finishes so
        # CPython cannot recycle an id and alias an unrelated topology node.
        self._retained: list[Any] = []

    def emit(
        self,
        op: _Op,
        args: Iterable[int],
        precision: int,
        payload: Any = None,
    ) -> int:
        out = len(self.instructions)
        self.instructions.append(_Instruction(op, out, tuple(args), precision, payload))
        return out

    def compile(self, value: Any, precision: int) -> int:
        if isinstance(value, InputSlot):
            self.input_count = max(self.input_count, value.index + 1)
            key = (id(value), 0)
            cached = self.cache.get(key)
            if cached is not None:
                return cached
            slot = self.emit(_Op.INPUT, (), precision, value.index)
            self.cache[key] = slot
            return slot
        if isinstance(value, int | float) or _is_mpf(value):
            # Constants are exact leaves; the requested precision is irrelevant.
            key = (id(value), -1)
            cached = self.cache.get(key)
            if cached is not None:
                return cached
            slot = self.emit(_Op.CONST, (), precision, _as_mpf(value))
            self.cache[key] = slot
            return slot
        if not hasattr(value, "opcode") or not hasattr(value, "operands"):
            raise UnsupportedDeferredScalar(f"unsupported delayed scalar leaf: {type(value)!r}")

        key = (id(value), precision)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        op = str(value.opcode)
        args = tuple(value.operands)
        self._retained.append(value)

        if op == "area_points":
            points = tuple(args[0])
            if len(points) < 3:
                raise UnsupportedDeferredScalar("area_points requires at least three points")
            total: Any = 0
            for position, first in enumerate(points):
                second = points[(position + 1) % len(points)]
                cross = DeferredScalar(
                    "sub",
                    (
                        DeferredScalar("mul", (first[0], second[1])),
                        DeferredScalar("mul", (first[1], second[0])),
                    ),
                )
                total = DeferredScalar("add", (total, cross))
            lowered = DeferredScalar("div", (DeferredScalar("abs", (total,)), 2))
            slot = self.compile(lowered, precision)
            self.cache[key] = slot
            return slot

        if op in {"distance_pp", "distance_pp_flat"}:
            first, second = args
            dx = DeferredScalar("sub", (first[0], second[0]))
            dy = DeferredScalar("sub", (first[1], second[1]))
            lowered = DeferredScalar(
                "sqrt",
                (
                    DeferredScalar(
                        "add",
                        (
                            DeferredScalar("square", (dx,)),
                            DeferredScalar("square", (dy,)),
                        ),
                    ),
                ),
            )
            slot = self.compile(lowered, precision)
            self.cache[key] = slot
            return slot

        if op == "on_circle_pc":
            point, center, radius = args
            distance = DeferredScalar("distance_pp_flat", (point, center))
            # The frozen symbolic boundary evaluates both cancelling terms at
            # a high guard precision but rounds their *difference* directly
            # to the requested boundary precision.  Compiling an ordinary
            # high-precision Sub here would round twice and can turn the tiny
            # non-zero residual of an exact constructed intersection into 0.
            working = precision + PERIODIC_GEOMETRY_CANCELLATION_GUARD
            distance_slot = self.compile(distance, working)
            radius_slot = self.compile(radius, working)
            slot = self.emit(
                _Op.SUB,
                (distance_slot, radius_slot),
                precision,
                working,
            )
            self.cache[key] = slot
            return slot

        if op in {"angle_ppp", "sympy_atan2"}:
            if len(args) != 2:
                raise UnsupportedDeferredScalar(f"{op} requires two operands")
            y, x = args
            y_sign = self.compile(y, BF53_PRECISION)
            x_sign = self.compile(x, BF53_PRECISION)
            # Do not materialize division instructions here: all flat
            # instructions execute eagerly, while atan2 must avoid y/x when
            # x is zero.  Load operands at both branch-specific guard budgets
            # and perform only the selected division in ANGLE_ATAN2.
            positive_y = self.compile(y, precision + 12)
            positive_x = self.compile(x, precision + 17)
            negative_y = self.compile(y, precision + 22)
            negative_x = self.compile(x, precision + 27)
            slot = self.emit(
                _Op.ANGLE_ATAN2,
                (
                    y_sign,
                    x_sign,
                    positive_y,
                    positive_x,
                    negative_y,
                    negative_x,
                ),
                precision,
            )
            self.cache[key] = slot
            return slot

        if op == "angle_ll":
            op, args = "acos", (args[0],)
        if op in {"periodic_sin_turns", "periodic_cos_turns"}:
            parameter = self.compile(args[0], BF53_PRECISION)
            slot = self.emit(
                _Op.PERIODIC_COS if op == "periodic_cos_turns" else _Op.PERIODIC_SIN,
                (parameter,),
                precision,
                True,
            )
            self.cache[key] = slot
            return slot
        if op in {"periodic_sin", "periodic_cos"}:
            coefficient = self.compile(args[0], BF53_PRECISION)
            slot = self.emit(
                _Op.PERIODIC_COS if op == "periodic_cos" else _Op.PERIODIC_SIN,
                (coefficient,),
                precision,
                False,
            )
            self.cache[key] = slot
            return slot

        binary = {"add": _Op.ADD, "sub": _Op.SUB, "mul": _Op.MUL, "div": _Op.DIV}
        unary = {
            "neg": _Op.NEG,
            "abs": _Op.ABS,
            "sqrt": _Op.SQRT,
            "sin": _Op.SIN,
            "cos": _Op.COS,
            "acos": _Op.ACOS,
            "atan": _Op.ATAN,
        }
        if op in binary:
            if len(args) != 2:
                raise UnsupportedDeferredScalar(f"{op} requires two operands")
            if op in {"add", "sub"}:
                child_precisions = (precision + 10, precision + 10)
            elif op == "mul":
                child_precisions = (precision + 7, precision + 7)
            else:
                child_precisions = (precision + 7, precision + 12)
            children = tuple(
                self.compile(arg, child_precision)
                for arg, child_precision in zip(args, child_precisions, strict=True)
            )
            slot = self.emit(binary[op], children, precision)
        elif op in unary:
            if len(args) != 1:
                raise UnsupportedDeferredScalar(f"{op} requires one operand")
            extra = {
                "neg": 0,
                "abs": 2,
                "sqrt": 5,
                "sin": 20,
                "cos": 20,
                "acos": 5,
                "atan": 5,
            }[op]
            slot = self.emit(unary[op], (self.compile(args[0], precision + extra),), precision)
        elif op in {"square", "pow_int"}:
            exponent = 2 if op == "square" else int(args[1])
            slot = self.emit(
                _Op.POW_INT,
                (self.compile(args[0], precision + 5),),
                precision,
                exponent,
            )
        elif op == "pi":
            slot = self.emit(_Op.PI, (), precision)
        else:
            raise UnsupportedDeferredScalar(f"unsupported delayed scalar opcode: {op}")
        self.cache[key] = slot
        return slot


class DeferredScalarTape:
    """Immutable compiled topology with one reusable value buffer per thread."""

    __slots__ = (
        "abi",
        "boundary_precision",
        "input_count",
        "instructions",
        "root_slot",
        "slot_count",
        "_local",
        "_fallback_root",
        "_periodic_parameter_tapes",
        "_subnormal_sympy_boundary",
    )

    def __init__(
        self,
        instructions: tuple[_Instruction, ...],
        root_slot: int,
        input_count: int,
        boundary_precision: int,
        *,
        fallback_root: Any = None,
        periodic_parameter_tapes: dict[int, DeferredScalarTape] | None = None,
        subnormal_sympy_boundary: bool = False,
    ) -> None:
        self.abi = DEFERRED_SCALAR_TAPE_ABI
        self.instructions = instructions
        self.root_slot = root_slot
        self.slot_count = len(instructions)
        self.input_count = input_count
        self.boundary_precision = boundary_precision
        self._local = threading.local()
        self._fallback_root = fallback_root
        self._periodic_parameter_tapes = periodic_parameter_tapes or {}
        self._subnormal_sympy_boundary = subnormal_sympy_boundary

    def _buffer(self) -> list[Mpf]:
        values = getattr(self._local, "values", None)
        if values is None or len(values) != self.slot_count:
            values = [fzero] * self.slot_count
            self._local.values = values
        return values

    def evaluate_mpf(self, inputs: Sequence[int | float | Mpf]) -> Mpf:
        if len(inputs) < self.input_count:
            raise ValueError(
                f"expected at least {self.input_count} scalar inputs, got {len(inputs)}"
            )
        values = self._buffer()
        for instruction in self.instructions:
            op = instruction.op
            args = instruction.args
            precision = instruction.precision
            if op == _Op.CONST:
                result = instruction.payload
            elif op == _Op.INPUT:
                result = _as_mpf(inputs[instruction.payload])
            elif op in {_Op.ADD, _Op.SUB}:
                right = values[args[1]]
                if op == _Op.SUB:
                    right = mpf_neg(right)
                result = _sum_two(
                    values[args[0]],
                    right,
                    precision,
                    instruction.payload
                    if instruction.payload is not None
                    else precision + 10,
                )
            elif op == _Op.MUL:
                result = _mul_exact(values[args[0]], values[args[1]], precision)
            elif op == _Op.DIV:
                result = mpf_div(values[args[0]], values[args[1]], precision, round_nearest)
            elif op == _Op.NEG:
                result = mpf_neg(values[args[0]])
            elif op == _Op.ABS:
                result = mpf_abs(values[args[0]])
            elif op == _Op.SQRT:
                result = mpf_sqrt(values[args[0]], precision, round_nearest)
            elif op == _Op.POW_INT:
                result = mpf_pow_int(values[args[0]], instruction.payload, precision, round_nearest)
            elif op == _Op.SIN:
                result = mpf_sin(values[args[0]], precision, round_nearest)
            elif op == _Op.COS:
                result = mpf_cos(values[args[0]], precision, round_nearest)
            elif op == _Op.ACOS:
                result = mpf_acos(values[args[0]], precision, round_nearest)
            elif op == _Op.ATAN:
                result = mpf_atan(values[args[0]], precision, round_nearest)
            elif op == _Op.PI:
                result = mpf_pi(precision, round_nearest)
            elif op in {_Op.PERIODIC_SIN, _Op.PERIODIC_COS}:
                coefficient = values[args[0]]
                if instruction.payload:
                    coefficient = mpf_mul_int(coefficient, 2, BF53_PRECISION, round_nearest)
                    coefficient = mpf_mod(
                        coefficient,
                        from_int(2),
                        BF53_PRECISION,
                        round_nearest,
                    )
                result = _periodic_value(
                    coefficient,
                    cosine=op == _Op.PERIODIC_COS,
                    precision=precision,
                )
            elif op == _Op.ANGLE_ATAN2:
                y_sign = _sign(values[args[0]])
                x_sign = _sign(values[args[1]])
                if y_sign is None or x_sign is None:
                    result = fnan
                elif x_sign == 0:
                    if y_sign == 0:
                        result = fnan
                    else:
                        half_pi = mpf_div(
                            mpf_pi(precision + 10, round_nearest),
                            from_int(2),
                            precision,
                            round_nearest,
                        )
                        result = half_pi if y_sign > 0 else mpf_neg(half_pi)
                elif x_sign > 0:
                    ratio = mpf_div(
                        values[args[2]],
                        values[args[3]],
                        precision + 5,
                        round_nearest,
                    )
                    result = mpf_atan(ratio, precision, round_nearest)
                else:
                    ratio = mpf_div(
                        values[args[4]],
                        values[args[5]],
                        precision + 15,
                        round_nearest,
                    )
                    angle = mpf_atan(ratio, precision + 10, round_nearest)
                    pi_term = mpf_pi(precision + 10, round_nearest)
                    if y_sign < 0:
                        pi_term = mpf_neg(pi_term)
                    result = _sum_two(angle, pi_term, precision, precision + 10)
            else:  # pragma: no cover - exhaustive IntEnum dispatch
                raise AssertionError(f"unknown tape opcode: {op}")
            values[instruction.out] = result
        return values[self.root_slot]

    def evaluate_float(self, inputs: Sequence[int | float | Mpf]) -> float:
        if self._subnormal_sympy_boundary and any(
            _is_binary64_subnormal(value) for value in inputs[: self.input_count]
        ):
            return float(
                _sympy_subnormal_boundary(
                    self._fallback_root,
                    inputs,
                    self._periodic_parameter_tapes,
                )
            )
        value = self.evaluate_mpf(inputs)
        return to_float(mpf_pos(value, BF53_PRECISION, round_nearest))


def _is_binary64_subnormal(value: int | float | Mpf) -> bool:
    if isinstance(value, int):
        return False
    if _is_mpf(value):
        if value in (fzero, fnan):
            return False
        converted = to_float(value)
        return converted == 0.0 or abs(converted) < sys.float_info.min
    return value != 0.0 and abs(value) < sys.float_info.min


def _contains_angle_boundary(value: Any) -> bool:
    if hasattr(value, "opcode") and hasattr(value, "operands"):
        if str(value.opcode) in {"angle_ppp", "angle_ll", "sympy_atan2"}:
            return True
        return any(_contains_angle_boundary(item) for item in value.operands)
    if isinstance(value, tuple | list) and not _is_mpf(value):
        return any(_contains_angle_boundary(item) for item in value)
    return False


def _contains_guarded_geometry_boundary(value: Any) -> bool:
    if hasattr(value, "opcode") and hasattr(value, "operands"):
        if str(value.opcode) == "on_circle_pc":
            return True
        return any(_contains_guarded_geometry_boundary(item) for item in value.operands)
    if isinstance(value, tuple | list) and not _is_mpf(value):
        return any(_contains_guarded_geometry_boundary(item) for item in value)
    return False


def _contains_periodic_boundary(value: Any) -> bool:
    if hasattr(value, "opcode") and hasattr(value, "operands"):
        if str(value.opcode) in {
            "periodic_sin_turns",
            "periodic_cos_turns",
            "periodic_sin",
            "periodic_cos",
        }:
            return True
        return any(_contains_periodic_boundary(item) for item in value.operands)
    if isinstance(value, tuple | list) and not _is_mpf(value):
        return any(_contains_periodic_boundary(item) for item in value)
    return False


def _collect_periodic_parameters(value: Any, target: dict[int, Any]) -> None:
    if hasattr(value, "opcode") and hasattr(value, "operands"):
        opcode = str(value.opcode)
        if opcode in {
            "periodic_sin_turns",
            "periodic_cos_turns",
            "periodic_sin",
            "periodic_cos",
        }:
            target[id(value)] = value.operands[0]
        for item in value.operands:
            _collect_periodic_parameters(item, target)
    elif isinstance(value, tuple | list) and not _is_mpf(value):
        for item in value:
            _collect_periodic_parameters(item, target)


def _sympy_subnormal_boundary(
    value: Any,
    inputs: Sequence[int | float | Mpf],
    periodic_parameter_tapes: dict[int, DeferredScalarTape],
):
    """Rebuild the frozen Angle boundary only for binary64 subnormals.

    SymPy's ``atan2`` boundary retains the *complete enclosing expression*.
    At minimum-subnormal inputs its accuracy restart can observe exact
    cancellations that cannot be represented by an eagerly closed libmp
    scaled-zero slot.  This rare value-class route is deliberately outside the
    normal flat callback path; normal and merely-small values never import or
    allocate SymPy objects here.
    """

    from sympy import Abs as SympyAbs
    from sympy import Float, Integer, acos, atan, atan2, cos, pi, sin, sqrt

    if isinstance(value, InputSlot):
        return Float._new(_as_mpf(inputs[value.index]), BF53_PRECISION)
    if isinstance(value, int):
        return Integer(value)
    if _is_mpf(value):
        return Float._new(value, BF53_PRECISION)
    if isinstance(value, float):
        return Float(value)
    if not hasattr(value, "opcode") or not hasattr(value, "operands"):
        raise UnsupportedDeferredScalar(f"unsupported subnormal boundary leaf: {type(value)!r}")
    opcode = str(value.opcode)
    operands = tuple(value.operands)
    if opcode == "area_points":
        points = operands[0]
        total: Any = Integer(0)
        for position, first in enumerate(points):
            second = points[(position + 1) % len(points)]
            total += _sympy_subnormal_boundary(
                first[0], inputs, periodic_parameter_tapes
            ) * _sympy_subnormal_boundary(
                second[1], inputs, periodic_parameter_tapes
            ) - _sympy_subnormal_boundary(
                first[1], inputs, periodic_parameter_tapes
            ) * _sympy_subnormal_boundary(second[0], inputs, periodic_parameter_tapes)
        return SympyAbs(total) / 2
    if opcode in {"distance_pp", "distance_pp_flat"}:
        first, second = operands
        dx = _sympy_subnormal_boundary(
            first[0], inputs, periodic_parameter_tapes
        ) - _sympy_subnormal_boundary(second[0], inputs, periodic_parameter_tapes)
        dy = _sympy_subnormal_boundary(
            first[1], inputs, periodic_parameter_tapes
        ) - _sympy_subnormal_boundary(second[1], inputs, periodic_parameter_tapes)
        return sqrt(dx**2 + dy**2)
    if opcode == "on_circle_pc":
        point, center, radius = operands
        distance = DeferredScalar("distance_pp_flat", (point, center))
        return _sympy_subnormal_boundary(
            distance, inputs, periodic_parameter_tapes
        ) - _sympy_subnormal_boundary(radius, inputs, periodic_parameter_tapes)
    if opcode in {
        "periodic_sin_turns",
        "periodic_cos_turns",
        "periodic_sin",
        "periodic_cos",
    }:
        coefficient = periodic_parameter_tapes[id(value)].evaluate_mpf(inputs)
        coefficient = mpf_pos(coefficient, BF53_PRECISION, round_nearest)
        if opcode.endswith("_turns"):
            coefficient = mpf_mul_int(coefficient, 2, BF53_PRECISION, round_nearest)
            reduced = mpf_mod(
                coefficient, from_int(2), BF53_PRECISION, round_nearest
            )
            half = mpf_div(
                from_int(1), from_int(2), BF53_PRECISION, round_nearest
            )
            special = {
                (0, True): 1,
                (0, False): 0,
                (1, True): 0,
                (1, False): 1,
                (2, True): -1,
                (2, False): 0,
                (3, True): 0,
                (3, False): -1,
            }
            quarter_index = next(
                (
                    index
                    for index, candidate in enumerate(
                        (
                            from_int(0),
                            half,
                            from_int(1),
                            _sum_two(
                                from_int(1),
                                half,
                                BF53_PRECISION,
                                BF53_PRECISION,
                            ),
                        )
                    )
                    if mpf_eq(reduced, candidate)
                ),
                None,
            )
            if quarter_index is not None:
                return Integer(special[(quarter_index, "cos" in opcode)])
            # For non-special turns frozen SymPy retains the *unreduced*
            # BF53 coefficient in sin/cos.  Modulo is authority only for
            # recognizing exact quarter turns; evaluating the reduced value
            # changes tiny negative and huge-argument semantics.
        converted = Float._new(coefficient, BF53_PRECISION)
        function = cos if "cos" in opcode else sin
        return function(converted * pi)
    if opcode == "angle_ppp":
        return atan2(
            _sympy_subnormal_boundary(operands[0], inputs, periodic_parameter_tapes),
            _sympy_subnormal_boundary(operands[1], inputs, periodic_parameter_tapes),
        )
    if opcode == "angle_ll":
        return acos(_sympy_subnormal_boundary(operands[0], inputs, periodic_parameter_tapes))
    converted = tuple(
        _sympy_subnormal_boundary(item, inputs, periodic_parameter_tapes) for item in operands
    )
    if opcode == "add":
        return converted[0] + converted[1]
    if opcode == "sub":
        return converted[0] - converted[1]
    if opcode == "mul":
        return converted[0] * converted[1]
    if opcode == "div":
        return converted[0] / converted[1]
    if opcode == "neg":
        return -converted[0]
    if opcode == "abs":
        return SympyAbs(converted[0])
    if opcode == "sqrt":
        return sqrt(converted[0])
    if opcode == "square":
        return converted[0] ** 2
    if opcode == "pow_int":
        return converted[0] ** int(operands[1])
    if opcode == "sin":
        return sin(converted[0])
    if opcode == "cos":
        return cos(converted[0])
    if opcode == "acos":
        return acos(converted[0])
    if opcode == "atan":
        return atan(converted[0])
    if opcode in {"atan2", "sympy_atan2"}:
        return atan2(converted[0], converted[1])
    if opcode == "pi":
        return pi
    raise UnsupportedDeferredScalar(f"unsupported subnormal boundary opcode: {opcode}")


def compile_deferred_scalar(
    expression: Any,
    *,
    boundary_precision: int = EVALF_BOUNDARY_PRECISION,
    _enable_subnormal_fallback: bool = True,
) -> DeferredScalarTape:
    """Compile one delayed scalar root into an immutable executable tape."""

    if boundary_precision < BF53_PRECISION:
        raise ValueError("boundary precision must be at least 53 bits")
    compiler = _Compiler(boundary_precision)
    root = compiler.compile(expression, boundary_precision)
    requires_subnormal_boundary = _enable_subnormal_fallback and (
        _contains_angle_boundary(expression)
        or _contains_guarded_geometry_boundary(expression)
        or _contains_periodic_boundary(expression)
    )
    periodic_parameter_tapes: dict[int, DeferredScalarTape] = {}
    if requires_subnormal_boundary:
        parameters: dict[int, Any] = {}
        _collect_periodic_parameters(expression, parameters)
        periodic_parameter_tapes = {
            identity: compile_deferred_scalar(
                parameter,
                boundary_precision=BF53_PRECISION,
                _enable_subnormal_fallback=False,
            )
            for identity, parameter in parameters.items()
        }
    return DeferredScalarTape(
        tuple(compiler.instructions),
        root,
        compiler.input_count,
        boundary_precision,
        fallback_root=expression if requires_subnormal_boundary else None,
        periodic_parameter_tapes=periodic_parameter_tapes,
        subnormal_sympy_boundary=requires_subnormal_boundary,
    )


__all__ = [
    "BF53_PRECISION",
    "DEFERRED_SCALAR_TAPE_ABI",
    "EVALF_BOUNDARY_PRECISION",
    "DeferredScalar",
    "DeferredScalarTape",
    "InputSlot",
    "UnsupportedDeferredScalar",
    "angle_acos",
    "angle_atan2",
    "area",
    "compile_deferred_scalar",
    "deferred",
    "periodic_cos",
    "periodic_sin",
]
