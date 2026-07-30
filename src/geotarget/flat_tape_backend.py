"""Flat, preallocated SSA evaluator for the typed binary53 geometry subset.

Admission requires the complete raw semantic/effect gate, then checks typed
opcodes, operand/result signatures, and numeric-effect flow.  The callback
path is an iterative tape walk: it performs no recursive IR dispatch and
creates no Point/Line/Circle wrapper objects.
"""

from __future__ import annotations

import math
import sys
import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from mpmath.libmp.libelefun import mpf_cos, mpf_sin
from mpmath.libmp.libmpf import mpf_pow_int, round_nearest

from geotarget.raw_libmp_backend import (
    _PREC,
    RAW_LIBMP_ABI,
    RawLibmpProgram,
    RawLibmpRuntimeFault,
    _abs,
    _add,
    _as_float,
    _atan2_sympy,
    _circle,
    _circumcenter,
    _div,
    _evalf_unary,
    _incenter,
    _is_mpf,
    _is_zero,
    _mul,
    _neg,
    _periodic_trig,
    _sqrt,
    _sub,
    compile_raw_libmp_program,
)
from geotarget.typed_refnum_ir import (
    SEMANTIC_ABI as TYPED_REFNUM_ABI,
)
from geotarget.typed_refnum_ir import (
    ConsumerRole,
    IRNode,
    TypedRefNumProgram,
)

FLAT_TAPE_ABI = "geotarget.flat-ssa-tape/sympy-1.14-bf53-v1"
FLAT_TAPE_QUALIFICATION_GATE = "permanent_generated_bitwise_deep_fanout_optimizer_replay_v1"


class UnsupportedFlatTapeBackend(RuntimeError):
    """The complete typed program is outside the flat tape ABI."""


class _FlatValueClassFallback(RuntimeError):
    """A qualified tape reached a branch delegated to the raw authority."""


class _Kind(IntEnum):
    SCALAR = 0
    POINT = 1
    LINE = 2
    CIRCLE = 3


class _Op(IntEnum):
    EXACT_INT = 1
    BF53_LITERAL = 2
    BF53_INPUT = 3
    PI = 4
    ADD = 5
    SUB = 6
    MUL = 7
    DIV = 8
    POW = 9
    NEG = 10
    POS = 11
    SQRT = 12
    COS = 13
    SIN = 14
    ABS = 15
    POINT = 20
    POINT_X = 21
    POINT_Y = 22
    MIDPOINT = 23
    POINT_ON_SEGMENT = 24
    CIRCLE = 30
    CIRCLE_CENTER = 31
    CIRCLE_RADIUS = 32
    POINT_ON_CIRCLE = 33
    LINE_PP = 40
    LINE_ABC = 41
    DISTANCE_PP = 50
    DISTANCE_PL = 51
    DISTANCE_LP = 52
    DISTANCE_PC = 53
    DISTANCE_CP = 54
    AREA = 55
    ANGLE_PPP = 56
    CIRCUMCENTER = 60
    CIRCUMCIRCLE = 61
    ORTHOCENTER = 62
    CENTROID = 63
    INCENTER = 64
    INCIRCLE = 65
    INTERSECT_LL = 70


_OPCODES = {
    "ExactInt": _Op.EXACT_INT,
    "BF53Literal": _Op.BF53_LITERAL,
    "BF53Input": _Op.BF53_INPUT,
    "Pi": _Op.PI,
    "Add": _Op.ADD,
    "Sub": _Op.SUB,
    "Mult": _Op.MUL,
    "Div": _Op.DIV,
    "Pow": _Op.POW,
    "USub": _Op.NEG,
    "UAdd": _Op.POS,
    "Sqrt": _Op.SQRT,
    "Cos": _Op.COS,
    "Sin": _Op.SIN,
    "Abs": _Op.ABS,
    "Point": _Op.POINT,
    "PointX": _Op.POINT_X,
    "PointY": _Op.POINT_Y,
    "MidpointPP": _Op.MIDPOINT,
    "PointOnSegment": _Op.POINT_ON_SEGMENT,
    "Circle": _Op.CIRCLE,
    "CircleCenter": _Op.CIRCLE_CENTER,
    "CircleRadius": _Op.CIRCLE_RADIUS,
    # PointOnCircle remains implemented in the tape executor so its eventual
    # qualification does not require an ABI redesign.  It is intentionally
    # absent from the admitted opcode map until the periodic-boundary replay
    # suite qualifies it for production selection.
    "LinePP": _Op.LINE_PP,
    "LineABC": _Op.LINE_ABC,
    "DistancePP": _Op.DISTANCE_PP,
    "DistancePL": _Op.DISTANCE_PL,
    "DistanceLP": _Op.DISTANCE_LP,
    "DistancePC": _Op.DISTANCE_PC,
    "DistanceCP": _Op.DISTANCE_CP,
    "AreaPoints": _Op.AREA,
    "AnglePPP": _Op.ANGLE_PPP,
    "Circumcenter": _Op.CIRCUMCENTER,
    "Circumcircle": _Op.CIRCUMCIRCLE,
    "Orthocenter": _Op.ORTHOCENTER,
    "Centroid": _Op.CENTROID,
    "Incenter": _Op.INCENTER,
    "Incircle": _Op.INCIRCLE,
    "Intersect": _Op.INTERSECT_LL,
}

_KINDS = {
    "scalar": _Kind.SCALAR,
    "point2": _Kind.POINT,
    "line2": _Kind.LINE,
    "circle2": _Kind.CIRCLE,
}

_SIGNATURES: dict[str, tuple[tuple[str, ...], str]] = {
    "ExactInt": ((), "scalar"),
    "BF53Literal": ((), "scalar"),
    "BF53Input": ((), "scalar"),
    "Pi": ((), "scalar"),
    "Add": (("scalar", "scalar"), "scalar"),
    "Sub": (("scalar", "scalar"), "scalar"),
    "Mult": (("scalar", "scalar"), "scalar"),
    "Div": (("scalar", "scalar"), "scalar"),
    "Pow": (("scalar", "scalar"), "scalar"),
    "USub": (("scalar",), "scalar"),
    "UAdd": (("scalar",), "scalar"),
    "Sqrt": (("scalar",), "scalar"),
    "Cos": (("scalar",), "scalar"),
    "Sin": (("scalar",), "scalar"),
    "Abs": (("scalar",), "scalar"),
    "Point": (("scalar", "scalar"), "point2"),
    "PointX": (("point2",), "scalar"),
    "PointY": (("point2",), "scalar"),
    "MidpointPP": (("point2", "point2"), "point2"),
    "PointOnSegment": (("point2", "point2", "scalar"), "point2"),
    "Circle": (("point2", "scalar"), "circle2"),
    "CircleCenter": (("circle2",), "point2"),
    "CircleRadius": (("circle2",), "scalar"),
    "LinePP": (("point2", "point2"), "line2"),
    "LineABC": (("scalar", "scalar", "scalar"), "line2"),
    "DistancePP": (("point2", "point2"), "scalar"),
    "DistancePL": (("point2", "line2"), "scalar"),
    "DistanceLP": (("line2", "point2"), "scalar"),
    "DistancePC": (("point2", "circle2"), "scalar"),
    "DistanceCP": (("circle2", "point2"), "scalar"),
    "AnglePPP": (("point2", "point2", "point2"), "scalar"),
    "Circumcenter": (("point2", "point2", "point2"), "point2"),
    "Circumcircle": (("point2", "point2", "point2"), "circle2"),
    "Orthocenter": (("point2", "point2", "point2"), "point2"),
    "Centroid": (("point2", "point2", "point2"), "point2"),
    "Incenter": (("point2", "point2", "point2"), "point2"),
    "Incircle": (("point2", "point2", "point2"), "circle2"),
    "Intersect": (("line2", "line2"), "point2"),
}


@dataclass(frozen=True, slots=True)
class _Ref:
    kind: _Kind
    index: int


@dataclass(frozen=True, slots=True)
class _Instruction:
    op: _Op
    output: _Ref
    operands: tuple[_Ref, ...]
    payload: Any = None


@dataclass(frozen=True, slots=True)
class _FlatTapeAdmission:
    typed_program: TypedRefNumProgram
    typed_semantic_abi: str
    raw_semantic_gate: RawLibmpProgram
    raw_support_key_sha256: str
    raw_semantic_abi: str
    numeric_effect_fingerprint: str
    admission_compile_seconds: float


class _Buffers:
    __slots__ = (
        "scalars",
        "point_x",
        "point_y",
        "line_a",
        "line_b",
        "line_c",
        "circle_x",
        "circle_y",
        "circle_r",
    )

    def __init__(self, slot_counts: tuple[int, int, int, int]) -> None:
        scalar_count, point_count, line_count, circle_count = slot_counts
        self.scalars: list[Any] = [0] * scalar_count
        self.point_x: list[Any] = [0] * point_count
        self.point_y: list[Any] = [0] * point_count
        self.line_a: list[Any] = [0] * line_count
        self.line_b: list[Any] = [0] * line_count
        self.line_c: list[Any] = [0] * line_count
        self.circle_x: list[Any] = [0] * circle_count
        self.circle_y: list[Any] = [0] * circle_count
        self.circle_r: list[Any] = [0] * circle_count


class FlatTapeProgram:
    """Reusable buffers plus immutable construction/constraint tapes."""

    semantic_abi = FLAT_TAPE_ABI

    def __init__(
        self,
        *,
        variable_names: tuple[str, ...],
        slot_counts: tuple[int, int, int, int],
        construction_tape: tuple[_Instruction, ...],
        construction_names: tuple[str, ...],
        construction_roots: tuple[_Ref, ...],
        constraint_tapes: tuple[tuple[tuple[_Instruction, ...], _Ref, _Ref], ...],
        admission: _FlatTapeAdmission,
    ) -> None:
        self.variable_names = variable_names
        self.slot_counts = slot_counts
        self.construction_tape = construction_tape
        self.construction_names = construction_names
        self.construction_roots = construction_roots
        self.constraint_tapes = constraint_tapes
        self.admission = admission
        self._thread_local = threading.local()
        self._hard_thread_local = threading.local()

    def _buffers(self) -> _Buffers:
        buffers = getattr(self._thread_local, "buffers", None)
        if buffers is None:
            buffers = _Buffers(self.slot_counts)
            self._thread_local.buffers = buffers
        return buffers

    def _hard_buffers(self) -> _Buffers:
        buffers = getattr(self._hard_thread_local, "buffers", None)
        if buffers is None:
            buffers = _Buffers(self.slot_counts)
            self._hard_thread_local.buffers = buffers
        return buffers

    @property
    def instruction_count(self) -> int:
        return len(self.construction_tape) + sum(
            len(tape) for tape, _left, _right in self.constraint_tapes
        )

    def metadata(self) -> dict[str, Any]:
        instructions = [
            *self.construction_tape,
            *(instruction for tape, _left, _right in self.constraint_tapes for instruction in tape),
        ]
        scalar_count, point_count, line_count, circle_count = self.slot_counts
        return {
            "semantic_abi": self.semantic_abi,
            "qualification_gate": FLAT_TAPE_QUALIFICATION_GATE,
            "qualification_status": "permanent_test_gate",
            "instruction_count": self.instruction_count,
            "constraint_count": len(self.constraint_tapes),
            "slot_counts": {
                "scalar": scalar_count,
                "point2": point_count,
                "line2": line_count,
                "circle2": circle_count,
            },
            "opcodes": sorted({instruction.op.name for instruction in instructions}),
            "preallocated_slots": True,
            "scratch_isolation": "thread_local_reused_per_thread",
            "numeric_lanes_share_values": False,
            "subnormal_input_policy": "raw_semantic_gate_value_class_fallback",
            "recursive_callback_dispatch": False,
            "whole_problem_admission": True,
            "raw_semantic_gate_support_key_sha256": self.admission.raw_support_key_sha256,
            "numeric_effect_fingerprint": self.admission.numeric_effect_fingerprint,
            "admission_compile_seconds": self.admission.admission_compile_seconds,
            "case_specific_routing": False,
            "problem_identity_read": False,
            "fallback_scope": "whole_problem",
        }

    def _execute(
        self, tape: tuple[_Instruction, ...], raw_values: list[float], buffers: _Buffers
    ) -> None:
        s = buffers.scalars
        px, py = buffers.point_x, buffers.point_y
        la, lb, lc = buffers.line_a, buffers.line_b, buffers.line_c
        cx, cy, cr = buffers.circle_x, buffers.circle_y, buffers.circle_r
        for instruction in tape:
            op, out, args = instruction.op, instruction.output, instruction.operands
            if op is _Op.EXACT_INT:
                s[out.index] = int(instruction.payload)
            elif op is _Op.BF53_LITERAL:
                s[out.index] = float(instruction.payload)
            elif op is _Op.BF53_INPUT:
                s[out.index] = float(raw_values[int(instruction.payload)])
            elif op is _Op.PI:
                s[out.index] = math.pi
            elif op is _Op.ADD:
                s[out.index] = _add(s[args[0].index], s[args[1].index])
            elif op is _Op.SUB:
                s[out.index] = _sub(s[args[0].index], s[args[1].index])
            elif op is _Op.MUL:
                s[out.index] = _mul(s[args[0].index], s[args[1].index])
            elif op is _Op.DIV:
                s[out.index] = _div(s[args[0].index], s[args[1].index])
            elif op is _Op.POW:
                base, exponent = s[args[0].index], s[args[1].index]
                if not isinstance(exponent, int):
                    raise ValueError("flat Pow requires exact integer exponent")
                s[out.index] = (
                    mpf_pow_int(base, exponent, _PREC, round_nearest)
                    if _is_mpf(base)
                    else base**exponent
                )
            elif op is _Op.NEG:
                s[out.index] = _neg(s[args[0].index])
            elif op is _Op.POS:
                s[out.index] = s[args[0].index]
            elif op is _Op.SQRT:
                s[out.index] = _sqrt(s[args[0].index])
            elif op is _Op.COS:
                s[out.index] = _evalf_unary(mpf_cos, s[args[0].index])
            elif op is _Op.SIN:
                s[out.index] = _evalf_unary(mpf_sin, s[args[0].index])
            elif op is _Op.ABS:
                s[out.index] = _abs(s[args[0].index])
            elif op is _Op.POINT:
                px[out.index], py[out.index] = s[args[0].index], s[args[1].index]
            elif op is _Op.POINT_X:
                s[out.index] = px[args[0].index]
            elif op is _Op.POINT_Y:
                s[out.index] = py[args[0].index]
            elif op is _Op.MIDPOINT:
                px[out.index] = _div(_add(px[args[0].index], px[args[1].index]), 2)
                py[out.index] = _div(_add(py[args[0].index], py[args[1].index]), 2)
            elif op is _Op.POINT_ON_SEGMENT:
                t = s[args[2].index]
                px[out.index] = _add(
                    px[args[0].index], _mul(t, _sub(px[args[1].index], px[args[0].index]))
                )
                py[out.index] = _add(
                    py[args[0].index], _mul(t, _sub(py[args[1].index], py[args[0].index]))
                )
            elif op is _Op.CIRCLE:
                center, radius = args
                _circle((px[center.index], py[center.index]), s[radius.index])
                cx[out.index], cy[out.index], cr[out.index] = (
                    px[center.index],
                    py[center.index],
                    s[radius.index],
                )
            elif op is _Op.CIRCLE_CENTER:
                px[out.index], py[out.index] = cx[args[0].index], cy[args[0].index]
            elif op is _Op.CIRCLE_RADIUS:
                s[out.index] = cr[args[0].index]
            elif op is _Op.POINT_ON_CIRCLE:
                circle, parameter = args
                t = s[parameter.index]
                px[out.index] = _add(
                    cx[circle.index], _mul(cr[circle.index], _periodic_trig(t, cosine=True))
                )
                py[out.index] = _add(
                    cy[circle.index], _mul(cr[circle.index], _periodic_trig(t, cosine=False))
                )
            elif op is _Op.LINE_PP:
                first, second = args
                a = _sub(py[first.index], py[second.index])
                b = _sub(px[second.index], px[first.index])
                c = _sub(
                    _mul(px[first.index], py[second.index]),
                    _mul(px[second.index], py[first.index]),
                )
                norm = _sqrt(_add(_mul(a, a), _mul(b, b)))
                if _is_zero(norm):
                    raise RawLibmpRuntimeFault("Line.norm must be non-zero")
                la[out.index] = _div(a, norm)
                lb[out.index] = _div(b, norm)
                lc[out.index] = _div(c, norm)
            elif op is _Op.LINE_ABC:
                a, b, c = (s[arg.index] for arg in args)
                norm = _sqrt(_add(_mul(a, a), _mul(b, b)))
                if _is_zero(norm):
                    raise RawLibmpRuntimeFault("Line.norm must be non-zero")
                la[out.index] = _div(a, norm)
                lb[out.index] = _div(b, norm)
                lc[out.index] = _div(c, norm)
            elif op is _Op.DISTANCE_PP:
                first, second = args
                dx, dy = (
                    _sub(px[first.index], px[second.index]),
                    _sub(py[first.index], py[second.index]),
                )
                s[out.index] = _sqrt(_add(_mul(dx, dx), _mul(dy, dy)))
            elif op in {_Op.DISTANCE_PL, _Op.DISTANCE_LP}:
                point, line = (args[0], args[1]) if op is _Op.DISTANCE_PL else (args[1], args[0])
                s[out.index] = _abs(
                    _add(
                        _add(
                            _mul(la[line.index], px[point.index]),
                            _mul(lb[line.index], py[point.index]),
                        ),
                        lc[line.index],
                    )
                )
            elif op in {_Op.DISTANCE_PC, _Op.DISTANCE_CP}:
                point, circle = (args[0], args[1]) if op is _Op.DISTANCE_PC else (args[1], args[0])
                dx, dy = (
                    _sub(px[point.index], cx[circle.index]),
                    _sub(py[point.index], cy[circle.index]),
                )
                radius_distance = _sqrt(_add(_mul(dx, dx), _mul(dy, dy)))
                s[out.index] = _abs(_sub(radius_distance, cr[circle.index]))
            elif op is _Op.AREA:
                total: Any = 0
                for position, first in enumerate(args):
                    second = args[(position + 1) % len(args)]
                    total = _add(
                        total,
                        _sub(
                            _mul(px[first.index], py[second.index]),
                            _mul(py[first.index], px[second.index]),
                        ),
                    )
                s[out.index] = _div(_abs(total), 2)
            elif op is _Op.ANGLE_PPP:
                first, vertex, third = args
                bax, bay = (
                    _sub(px[first.index], px[vertex.index]),
                    _sub(py[first.index], py[vertex.index]),
                )
                bcx, bcy = (
                    _sub(px[third.index], px[vertex.index]),
                    _sub(py[third.index], py[vertex.index]),
                )
                determinant = _abs(_sub(_mul(bax, bcy), _mul(bay, bcx)))
                dot = _add(_mul(bax, bcx), _mul(bay, bcy))
                s[out.index] = _atan2_sympy(determinant, dot)
            elif op in {_Op.CIRCUMCENTER, _Op.CIRCUMCIRCLE}:
                first, second, third = args
                a = (px[first.index], py[first.index])
                b = (px[second.index], py[second.index])
                c = (px[third.index], py[third.index])
                center = _circumcenter(a, b, c)
                if center is None:
                    raise _FlatValueClassFallback("Circumcenter denominator is zero")
                if op is _Op.CIRCUMCENTER:
                    px[out.index], py[out.index] = center
                else:
                    radius = _sqrt(
                        _add(
                            _mul(_sub(center[0], a[0]), _sub(center[0], a[0])),
                            _mul(_sub(center[1], a[1]), _sub(center[1], a[1])),
                        )
                    )
                    _circle(center, radius)
                    cx[out.index], cy[out.index], cr[out.index] = (
                        center[0],
                        center[1],
                        radius,
                    )
            elif op is _Op.ORTHOCENTER:
                first, second, third = args
                a = (px[first.index], py[first.index])
                b = (px[second.index], py[second.index])
                c = (px[third.index], py[third.index])
                dx_bc, dy_bc = _sub(c[0], b[0]), _sub(c[1], b[1])
                k1 = _add(_mul(dx_bc, a[0]), _mul(dy_bc, a[1]))
                dx_ca, dy_ca = _sub(a[0], c[0]), _sub(a[1], c[1])
                k2 = _add(_mul(dx_ca, b[0]), _mul(dy_ca, b[1]))
                determinant = _sub(_mul(dx_bc, dy_ca), _mul(dx_ca, dy_bc))
                if _is_zero(determinant):
                    raise _FlatValueClassFallback("Orthocenter determinant is zero")
                px[out.index] = _div(_sub(_mul(k1, dy_ca), _mul(k2, dy_bc)), determinant)
                py[out.index] = _div(_sub(_mul(dx_bc, k2), _mul(dx_ca, k1)), determinant)
            elif op is _Op.CENTROID:
                first, second, third = args
                px[out.index] = _div(
                    _add(
                        _add(px[first.index], px[second.index]),
                        px[third.index],
                    ),
                    3,
                )
                py[out.index] = _div(
                    _add(
                        _add(py[first.index], py[second.index]),
                        py[third.index],
                    ),
                    3,
                )
            elif op in {_Op.INCENTER, _Op.INCIRCLE}:
                first, second, third = args
                a = (px[first.index], py[first.index])
                b = (px[second.index], py[second.index])
                c = (px[third.index], py[third.index])
                center = _incenter(a, b, c)
                if op is _Op.INCENTER:
                    px[out.index], py[out.index] = center
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
                    side_a = _sqrt(
                        _add(
                            _mul(_sub(b[0], c[0]), _sub(b[0], c[0])),
                            _mul(_sub(b[1], c[1]), _sub(b[1], c[1])),
                        )
                    )
                    side_b = _sqrt(
                        _add(
                            _mul(_sub(c[0], a[0]), _sub(c[0], a[0])),
                            _mul(_sub(c[1], a[1]), _sub(c[1], a[1])),
                        )
                    )
                    side_c = _sqrt(
                        _add(
                            _mul(_sub(a[0], b[0]), _sub(a[0], b[0])),
                            _mul(_sub(a[1], b[1]), _sub(a[1], b[1])),
                        )
                    )
                    perimeter = _add(_add(side_a, side_b), side_c)
                    radius = 0 if _is_zero(perimeter) else _div(double_area, perimeter)
                    _circle(center, radius)
                    cx[out.index], cy[out.index], cr[out.index] = (
                        center[0],
                        center[1],
                        radius,
                    )
            elif op is _Op.INTERSECT_LL:
                first, second = args
                determinant = _sub(
                    _mul(la[first.index], lb[second.index]),
                    _mul(la[second.index], lb[first.index]),
                )
                if _is_zero(determinant):
                    raise _FlatValueClassFallback("parallel line intersection")
                px[out.index] = _div(
                    _sub(
                        _mul(lb[first.index], lc[second.index]),
                        _mul(lb[second.index], lc[first.index]),
                    ),
                    determinant,
                )
                py[out.index] = _div(
                    _sub(
                        _mul(lc[first.index], la[second.index]),
                        _mul(lc[second.index], la[first.index]),
                    ),
                    determinant,
                )
            else:  # pragma: no cover - compile/runtime invariant
                raise AssertionError(op)

    def evaluate(self, raw_values: list[float]) -> list[float]:
        if len(raw_values) != len(self.variable_names):
            raise ValueError("flat tape evaluator dimension mismatch")
        # Binary64 normal/subnormal transitions are semantic boundaries in
        # the frozen SymPy evaluator (not merely performance details).  The
        # raw libmp program retained by the admission token is independently
        # bit-qualified for this value class, while the scalarized flat tape
        # can underflow an intermediate before Angle/Distance observes it.
        # Delegate only this input value class; the decision is independent of
        # source identity and applies to every admitted V15 program.
        if any(
            math.isfinite(value) and value != 0.0 and abs(value) <= sys.float_info.min
            for value in raw_values
        ):
            return self.admission.raw_semantic_gate.evaluate(raw_values)
        buffers = self._buffers()
        try:
            self._execute(self.construction_tape, raw_values, buffers)
        except _FlatValueClassFallback:
            return self.admission.raw_semantic_gate.evaluate(raw_values)
        except Exception:
            return [float("nan")] * len(self.constraint_tapes)
        residuals: list[float] = []
        for tape, left, right in self.constraint_tapes:
            try:
                self._execute(tape, raw_values, buffers)
                residuals.append(
                    _as_float(buffers.scalars[left.index]) - _as_float(buffers.scalars[right.index])
                )
            except _FlatValueClassFallback:
                return self.admission.raw_semantic_gate.evaluate(raw_values)
            except Exception:
                residuals.append(float("nan"))
        return residuals

    def evaluate_hard_point_lane(
        self,
        raw_values: list[float],
        required_names: frozenset[str],
    ) -> dict[str, tuple[float, float]] | None:
        """Evaluate required point constructions in an isolated float lane.

        Returning ``None`` requests whole-callback fallback. The method never
        exposes residual-lane buffers and therefore cannot share values across
        the BF53 residual and float hard-feasibility boundaries.
        """

        if len(raw_values) != len(self.variable_names) or any(
            not math.isfinite(value) or (value != 0.0 and abs(value) <= sys.float_info.min)
            for value in raw_values
        ):
            return None
        buffers = self._hard_buffers()
        try:
            self._execute(self.construction_tape, raw_values, buffers)
            points: dict[str, tuple[float, float]] = {}
            for name, root in zip(
                self.construction_names,
                self.construction_roots,
                strict=True,
            ):
                if name not in required_names:
                    continue
                if root.kind is not _Kind.POINT:
                    return None
                points[name] = (
                    _as_float(buffers.point_x[root.index]),
                    _as_float(buffers.point_y[root.index]),
                )
            return points if len(points) == len(required_names) else None
        except Exception:
            return None


def _authorize_flat_tape_specialization(
    program: TypedRefNumProgram, raw_semantic_gate: RawLibmpProgram
) -> _FlatTapeAdmission:
    """Issue an identity-bound admission only after the raw effect gate."""

    if program.semantic_abi != TYPED_REFNUM_ABI:
        raise UnsupportedFlatTapeBackend("typed semantic ABI mismatch")
    if not isinstance(raw_semantic_gate, RawLibmpProgram):
        raise UnsupportedFlatTapeBackend("raw semantic/effect admission is required")
    if raw_semantic_gate.semantic_abi != RAW_LIBMP_ABI:
        raise UnsupportedFlatTapeBackend("raw semantic ABI mismatch")
    if raw_semantic_gate.variable_names != program.variable_names:
        raise UnsupportedFlatTapeBackend("raw and typed variable layouts differ")
    if len(raw_semantic_gate.constraint_roots) != len(program.constraints):
        raise UnsupportedFlatTapeBackend("raw and typed constraint layouts differ")
    # Bind the gate to this complete typed DAG, not merely to an opcode set or
    # variable/constraint layout.  RawLibmpProgram's frozen dataclass equality
    # covers every node operand, payload, construction root and constraint
    # root.  This second deterministic compile runs once per problem, outside
    # the callback path, and closes cross-program token substitution.
    started = time.perf_counter()
    expected_raw_gate = compile_raw_libmp_program(program)
    if expected_raw_gate != raw_semantic_gate:
        raise UnsupportedFlatTapeBackend(
            "raw semantic gate provenance does not match the typed program"
        )
    metadata = raw_semantic_gate.metadata()
    effect_analysis = program.numeric_effect_analysis()
    geometry_roles = {
        ConsumerRole.GEOMETRY_COORDINATE,
        ConsumerRole.GEOMETRY_OPERAND,
        ConsumerRole.CONSTRUCTOR_PRECONDITION,
        ConsumerRole.SELECTOR,
        ConsumerRole.PREDICATE_OPERAND,
        ConsumerRole.ATTRIBUTE_OWNER,
        ConsumerRole.FUNCTION_OPERAND,
    }
    unsupported_symbolic_edges = tuple(
        edge
        for edge in effect_analysis.edges
        if edge.effects.requires_symbolic_composition and edge.role in geometry_roles
    )
    if unsupported_symbolic_edges:
        edge = unsupported_symbolic_edges[0]
        raise UnsupportedFlatTapeBackend(
            "flat tape does not preserve symbolic geometry composition: "
            f"{edge.consumer_opcode}[{edge.operand_index}]"
        )
    effect_nodes = {node.index: node for node in effect_analysis.nodes}
    for edge in effect_analysis.edges:
        producer = effect_nodes[edge.producer_index]
        if producer.opcode == "AnglePPP" and edge.consumer_opcode in {
            "Add",
            "Sub",
            "Mult",
            "Div",
            "Pow",
            "USub",
            "UAdd",
            "Abs",
            "Sqrt",
        }:
            raise UnsupportedFlatTapeBackend(
                "flat tape does not preserve frozen Angle scalar composition: "
                f"{edge.consumer_opcode}[{edge.operand_index}]"
            )
    return _FlatTapeAdmission(
        typed_program=program,
        typed_semantic_abi=program.semantic_abi,
        raw_semantic_gate=raw_semantic_gate,
        raw_support_key_sha256=str(metadata["support_key_sha256"]),
        raw_semantic_abi=raw_semantic_gate.semantic_abi,
        numeric_effect_fingerprint=effect_analysis.fingerprint(),
        admission_compile_seconds=time.perf_counter() - started,
    )


def compile_flat_tape_program(
    program: TypedRefNumProgram, *, raw_semantic_gate: RawLibmpProgram
) -> FlatTapeProgram:
    """Run raw/effect admission and compile one qualified flat program."""

    admission = _authorize_flat_tape_specialization(program, raw_semantic_gate)
    if admission.typed_semantic_abi != TYPED_REFNUM_ABI or program.semantic_abi != TYPED_REFNUM_ABI:
        raise UnsupportedFlatTapeBackend("typed semantic ABI mismatch")
    if (
        admission.raw_semantic_abi != RAW_LIBMP_ABI
        or admission.raw_semantic_gate.semantic_abi != RAW_LIBMP_ABI
    ):
        raise UnsupportedFlatTapeBackend("raw semantic ABI mismatch")

    counters = [_SlotCounter() for _ in range(4)]
    input_indexes = {name: index for index, name in enumerate(program.variable_names)}

    def compile_nodes(
        roots: tuple[IRNode, ...], seed: dict[int, _Ref]
    ) -> tuple[tuple[_Instruction, ...], tuple[_Ref, ...], dict[int, _Ref]]:
        memo = dict(seed)
        tape: list[_Instruction] = []

        def compile_node(node: IRNode) -> _Ref:
            identity = id(node)
            if identity in memo:
                return memo[identity]
            op = _OPCODES.get(node.opcode)
            kind = _KINDS.get(node.result_type)
            if op is None or kind is None:
                raise UnsupportedFlatTapeBackend(
                    f"unsupported typed signature: {node.opcode}->{node.result_type}"
                )
            if node.opcode == "AreaPoints":
                if (
                    len(node.operands) < 3
                    or any(child.result_type != "point2" for child in node.operands)
                    or node.result_type != "scalar"
                ):
                    raise UnsupportedFlatTapeBackend("invalid AreaPoints typed signature")
            else:
                signature = _SIGNATURES.get(node.opcode)
                observed = tuple(child.result_type for child in node.operands)
                if signature is None or signature != (observed, node.result_type):
                    raise UnsupportedFlatTapeBackend(
                        f"invalid typed signature: {node.opcode}{observed}->{node.result_type}"
                    )
            if node.opcode == "ExactInt" and (
                not isinstance(node.payload, int) or isinstance(node.payload, bool)
            ):
                raise UnsupportedFlatTapeBackend("invalid ExactInt payload")
            if node.opcode == "BF53Literal" and (
                not isinstance(node.payload, float) or not math.isfinite(node.payload)
            ):
                raise UnsupportedFlatTapeBackend("invalid BF53Literal payload")
            if node.opcode == "BF53Input" and str(node.payload) not in input_indexes:
                raise UnsupportedFlatTapeBackend("unknown BF53Input payload")
            intersect_payload_ok = False
            if node.opcode == "Intersect" and node.payload is not None:
                plan, selector_names = node.payload
                intersect_payload_ok = (
                    plan.support_key.operand_types == ("line2", "line2")
                    and plan.result_type == "point2"
                    and not selector_names
                )
                if not intersect_payload_ok:
                    raise UnsupportedFlatTapeBackend(
                        "only selector-free line-line Intersect is qualified"
                    )
            if node.opcode not in {"ExactInt", "BF53Literal", "BF53Input"} and (
                node.payload is not None and not intersect_payload_ok
            ):
                raise UnsupportedFlatTapeBackend(
                    f"unexpected payload for {node.opcode}: {node.payload!r}"
                )
            operands = tuple(compile_node(child) for child in node.operands)
            output = _Ref(kind, counters[int(kind)].take())
            payload = (
                input_indexes[str(node.payload)]
                if op is _Op.BF53_INPUT
                else None
                if op is _Op.INTERSECT_LL
                else node.payload
            )
            if op is _Op.POW and (len(node.operands) != 2 or node.operands[1].opcode != "ExactInt"):
                raise UnsupportedFlatTapeBackend("flat Pow exponent must be ExactInt")
            memo[identity] = output
            tape.append(_Instruction(op, output, operands, payload))
            return output

        outputs = tuple(compile_node(root) for root in roots)
        return tuple(tape), outputs, memo

    construction_nodes = tuple(node for _name, node in program.constructions)
    construction_tape, construction_roots, construction_memo = compile_nodes(construction_nodes, {})
    constraint_tapes = []
    for left, right in program.constraints:
        tape, outputs, _memo = compile_nodes((left, right), construction_memo)
        if outputs[0].kind is not _Kind.SCALAR or outputs[1].kind is not _Kind.SCALAR:
            raise UnsupportedFlatTapeBackend("constraint roots must both be scalar")
        constraint_tapes.append((tape, outputs[0], outputs[1]))
    return FlatTapeProgram(
        variable_names=program.variable_names,
        slot_counts=tuple(counter.value for counter in counters),  # type: ignore[arg-type]
        construction_tape=construction_tape,
        construction_names=tuple(name for name, _node in program.constructions),
        construction_roots=construction_roots,
        constraint_tapes=tuple(constraint_tapes),
        admission=admission,
    )


class _SlotCounter:
    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0

    def take(self) -> int:
        value = self.value
        self.value += 1
        return value


__all__ = [
    "FLAT_TAPE_ABI",
    "FLAT_TAPE_QUALIFICATION_GATE",
    "FlatTapeProgram",
    "UnsupportedFlatTapeBackend",
    "compile_flat_tape_program",
]
