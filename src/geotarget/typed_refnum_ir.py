"""General, source-ordered typed IR for the frozen V15 double evaluator.

This module deliberately has no problem/corpus identity inputs.  Admission is
decided from resolved opcode signatures and the semantic ABI only.  A program
is either compiled completely or rejected completely; there is no node-level
fallback to the reference evaluator.

The runtime retains SymPy 1.14's binary53/libmp behavior at geometry object
boundaries.  In particular it does not replace transcendental operations with
``libm`` and it never enables ``fastmath``.  This matters for exact special
angles (for example ``cos(pi/2)``) and for the frozen branch behavior of
``Abs``, ``atan2`` and ``acos``.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import math
import operator
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from sympy import Abs, Rational, acos, atan2, cos, pi, simplify, sin, sqrt, sympify

SEMANTIC_ABI = "geotarget.typed-refnum-ir/sympy-1.14-libmp-bf53-v1"
ScalarKind = Literal["exact_int", "rational", "bf53", "scalar"]
ValueType = Literal["scalar", "point2", "point_or_list", "line2", "circle2"]


class UnsupportedTypedRefNumIR(RuntimeError):
    """The complete problem is outside this ABI."""


class TypedRefNumRuntimeFault(RuntimeError):
    """A frozen geometry constructor precondition failed at runtime."""


@dataclass(frozen=True)
class SupportKey:
    opcode: str
    operand_types: tuple[str, ...]
    result_type: str
    selector_kind: str
    semantic_abi: str = SEMANTIC_ABI


@dataclass(frozen=True)
class IRNode:
    opcode: str
    result_type: ValueType
    operands: tuple[IRNode, ...] = ()
    payload: Any = None


class NumericExactness(str, Enum):
    """Provenance lattice for numeric values contained in an IR result."""

    EXACT = "exact"
    BF53 = "bf53"
    MIXED = "mixed"
    NON_NUMERIC = "non_numeric"


class ConsumerRole(str, Enum):
    """Semantic role in which a producer value is consumed."""

    CONSTRUCTION_ROOT = "construction_root"
    CONSTRAINT_SIDE_ROOT = "constraint_side_root"
    ARITHMETIC_OPERAND = "arithmetic_operand"
    GEOMETRY_COORDINATE = "geometry_coordinate"
    GEOMETRY_OPERAND = "geometry_operand"
    CONSTRUCTOR_PRECONDITION = "constructor_precondition"
    SELECTOR = "selector"
    PREDICATE_OPERAND = "predicate_operand"
    ATTRIBUTE_OWNER = "attribute_owner"
    FUNCTION_OPERAND = "function_operand"


@dataclass(frozen=True)
class NumericEffects:
    """Conservative numeric effects propagated through one typed IR node."""

    may_fault: bool
    may_nonfinite: bool
    may_signed_zero: bool
    may_subnormal: bool
    exactness: NumericExactness
    branch_sensitive: bool
    requires_symbolic_composition: bool

    def enabled_effects(self) -> frozenset[str]:
        fields = (
            "may_fault",
            "may_nonfinite",
            "may_signed_zero",
            "may_subnormal",
            "branch_sensitive",
            "requires_symbolic_composition",
        )
        return frozenset(name for name in fields if getattr(self, name))


@dataclass(frozen=True)
class NumericEffectNode:
    index: int
    opcode: str
    result_type: str
    effects: NumericEffects


@dataclass(frozen=True)
class NumericEffectEdge:
    producer_index: int
    consumer_index: int | None
    consumer_opcode: str
    operand_index: int
    role: ConsumerRole
    root_ordinal: int | None
    effects: NumericEffects
    consumer_effects: NumericEffects | None


@dataclass(frozen=True)
class ConsumerCapability:
    """Effects a backend preserves for one consumer role."""

    allow_may_fault: bool = False
    allow_may_nonfinite: bool = False
    allow_signed_zero: bool = False
    allow_subnormal: bool = False
    allow_branch_sensitive: bool = False
    preserve_symbolic_composition: bool = False
    accepted_exactness: frozenset[NumericExactness] = frozenset(NumericExactness)


@dataclass(frozen=True)
class NumericEffectPolicy:
    default: ConsumerCapability
    by_role: Mapping[ConsumerRole, ConsumerCapability]

    def capability_for(self, role: ConsumerRole) -> ConsumerCapability:
        return self.by_role.get(role, self.default)


@dataclass(frozen=True)
class NumericEffectIssue:
    edge: NumericEffectEdge
    unsupported_effects: tuple[str, ...]


@dataclass(frozen=True)
class NumericEffectCertification:
    certified: bool
    issues: tuple[NumericEffectIssue, ...]


@dataclass(frozen=True)
class NumericEffectAnalysis:
    nodes: tuple[NumericEffectNode, ...]
    edges: tuple[NumericEffectEdge, ...]

    def fingerprint(self) -> str:
        rows = {
            "nodes": [
                {
                    "index": node.index,
                    "opcode": node.opcode,
                    "result_type": node.result_type,
                    "effects": {
                        "enabled": sorted(node.effects.enabled_effects()),
                        "exactness": node.effects.exactness.value,
                    },
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "producer": edge.producer_index,
                    "consumer": edge.consumer_index,
                    "consumer_opcode": edge.consumer_opcode,
                    "operand_index": edge.operand_index,
                    "role": edge.role.value,
                    "root_ordinal": edge.root_ordinal,
                    "consumer_effects": (
                        None
                        if edge.consumer_effects is None
                        else {
                            "enabled": sorted(edge.consumer_effects.enabled_effects()),
                            "exactness": edge.consumer_effects.exactness.value,
                        }
                    ),
                }
                for edge in self.edges
            ],
        }
        return hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class _Point:
    x: Any
    y: Any


@dataclass(frozen=True)
class _Line:
    a: Any
    b: Any
    c: Any


@dataclass(frozen=True)
class _Circle:
    center: _Point
    radius: Any


def _geometry_scalar(value: Any) -> Any:
    # Frozen Point/Line preserve Python ints but sympify every other scalar.
    return value if isinstance(value, int) and not isinstance(value, bool) else sympify(value)


def _point(x: Any, y: Any) -> _Point:
    return _Point(_geometry_scalar(x), _geometry_scalar(y))


def _circle(center: _Point, radius: Any) -> _Circle:
    radius = sympify(radius)
    # This is an authority-bearing constructor branch, not a deferred hint.
    if radius < 0:
        raise TypedRefNumRuntimeFault("Circle.radius must be non-negative")
    return _Circle(center, radius)


def _line_from_points(first: _Point, second: _Point) -> _Line:
    a = first.y - second.y
    b = second.x - first.x
    c = first.x * second.y - second.x * first.y
    return _line_from_coefficients(a, b, c)


def _line_from_coefficients(a: Any, b: Any, c: Any) -> _Line:
    a, b, c = (_geometry_scalar(value) for value in (a, b, c))
    norm = sqrt(a**2 + b**2)
    if norm == 0:
        raise TypedRefNumRuntimeFault("Line.norm must be non-zero")
    return _Line(a / norm, b / norm, c / norm)


def _distance(first: Any, second: Any) -> Any:
    if isinstance(first, _Point) and second is None:
        # Frozen Distance(point, None) takes its one-argument branch.  This is
        # observable when an unselected parallel LL Intersect returns None.
        return sqrt(first.x**2 + first.y**2)
    if isinstance(first, _Point) and isinstance(second, _Point):
        dx, dy = first.x - second.x, first.y - second.y
        return sqrt(dx**2 + dy**2)
    if isinstance(first, _Point) and isinstance(second, _Line):
        return Abs(second.a * first.x + second.b * first.y + second.c)
    if isinstance(first, _Line) and isinstance(second, _Point):
        return Abs(first.a * second.x + first.b * second.y + first.c)
    raise TypedRefNumRuntimeFault("unsupported Distance runtime operands")


def _area(points: tuple[_Point, ...]) -> Any:
    total: Any = 0
    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        total += first.x * second.y - first.y * second.x
    return Abs(total) / 2


def _angle(values: tuple[Any, ...]) -> Any:
    if len(values) == 3 and all(isinstance(value, _Point) for value in values):
        first, vertex, third = values
        bax, bay = first.x - vertex.x, first.y - vertex.y
        bcx, bcy = third.x - vertex.x, third.y - vertex.y
        return atan2(Abs(bax * bcy - bay * bcx), bax * bcx + bay * bcy)
    if len(values) == 2 and all(isinstance(value, _Line) for value in values):
        first, second = values
        return acos(Abs(first.a * second.a + first.b * second.b))
    raise TypedRefNumRuntimeFault("unsupported Angle runtime operands")


def _circumcenter(a: _Point, b: _Point, c: _Point) -> _Point:
    x1, y1, x2, y2, x3, y3 = a.x, a.y, b.x, b.y, c.x, c.y
    denominator = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if denominator == 0:
        return None  # type: ignore[return-value]  # frozen Optional[Point]
    ux = (
        (x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)
    ) / denominator
    uy = (
        (x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)
    ) / denominator
    return _point(ux, uy)


def _orthocenter(a: _Point, b: _Point, c: _Point) -> _Point:
    dx_bc, dy_bc = c.x - b.x, c.y - b.y
    k1 = dx_bc * a.x + dy_bc * a.y
    dx_ca, dy_ca = a.x - c.x, a.y - c.y
    k2 = dx_ca * b.x + dy_ca * b.y
    determinant = dx_bc * dy_ca - dx_ca * dy_bc
    if determinant == 0:
        return None  # type: ignore[return-value]  # frozen Optional[Point]
    return _point(
        (k1 * dy_ca - k2 * dy_bc) / determinant,
        (dx_bc * k2 - dx_ca * k1) / determinant,
    )


def _incenter(a: _Point, b: _Point, c: _Point) -> _Point:
    side_a, side_b, side_c = _distance(b, c), _distance(c, a), _distance(a, b)
    perimeter = side_a + side_b + side_c
    if perimeter == 0:
        return a
    return _point(
        (side_a * a.x + side_b * b.x + side_c * c.x) / perimeter,
        (side_a * a.y + side_b * b.y + side_c * c.y) / perimeter,
    )


def _excenter(a: _Point, b: _Point, c: _Point) -> _Point:
    side_a, side_b, side_c = _distance(b, c), _distance(c, a), _distance(a, b)
    denominator = -side_a + side_b + side_c
    if denominator == 0:
        return a
    return _point(
        (-side_a * a.x + side_b * b.x + side_c * c.x) / denominator,
        (-side_a * a.y + side_b * b.y + side_c * c.y) / denominator,
    )


def _foot(line: _Line, point: _Point) -> _Point:
    denominator = line.a**2 + line.b**2
    if denominator == 0:
        raise TypedRefNumRuntimeFault("Foot.denominator must be non-zero")
    return _point(
        (line.b * (line.b * point.x - line.a * point.y) - line.a * line.c) / denominator,
        (line.a * (-line.b * point.x + line.a * point.y) - line.b * line.c) / denominator,
    )


_BINARY = {
    "Add": operator.add,
    "Sub": operator.sub,
    "Mult": operator.mul,
    "Div": operator.truediv,
    "Pow": operator.pow,
}


def _eval_node(node: IRNode, values: dict[str, float], memo: dict[int, Any]) -> Any:
    identity = id(node)
    if identity in memo:
        return memo[identity]
    op = node.opcode
    # Avoid creating a generator for the numerous input/literal leaves on
    # every optimizer callback.  The empty tuple is immutable and shared.
    args = (
        tuple(_eval_node(child, values, memo) for child in node.operands) if node.operands else ()
    )
    if op == "ExactInt":
        result = int(node.payload)
    elif op == "Rational":
        numerator, denominator = node.payload
        result = Rational(numerator, denominator)
    elif op == "BF53Literal":
        result = float(node.payload)
    elif op == "BF53Input":
        result = float(values[str(node.payload)])
    elif op == "Pi":
        # The V15 expression context exports binary64 ``math.pi``.  Geometry
        # primitives such as PointOnCircle use SymPy's exact pi internally;
        # keeping these two boundaries distinct is part of the frozen ABI.
        result = math.pi
    elif op in _BINARY:
        result = _BINARY[op](args[0], args[1])
    elif op == "USub":
        result = -args[0]
    elif op == "UAdd":
        result = +args[0]
    elif op == "Sqrt":
        result = sqrt(args[0])
    elif op == "Cos":
        result = cos(args[0])
    elif op == "Sin":
        result = sin(args[0])
    elif op == "Abs":
        result = Abs(args[0])
    elif op == "Point":
        result = _point(args[0], args[1])
    elif op == "Circle":
        result = _circle(args[0], args[1])
    elif op == "PointOnCircle":
        circle, parameter = args
        angle = 2 * pi * parameter
        result = _point(
            circle.center.x + circle.radius * cos(angle),
            circle.center.y + circle.radius * sin(angle),
        )
    elif op == "PointOnSegment":
        first, second, parameter = args
        result = _point(
            first.x + parameter * (second.x - first.x),
            first.y + parameter * (second.y - first.y),
        )
    elif op == "PointOnLine":
        line, parameter = args
        denominator = line.a**2 + line.b**2
        result = _point(
            -line.a * line.c / denominator - line.b * parameter,
            -line.b * line.c / denominator + line.a * parameter,
        )
    elif op == "LinePP":
        result = _line_from_points(args[0], args[1])
    elif op == "LineABC":
        result = _line_from_coefficients(args[0], args[1], args[2])
    elif op in {"DistancePP", "DistancePL", "DistanceLP"}:
        result = _distance(args[0], args[1])
    elif op in {"DistancePC", "DistanceCP"}:
        if op == "DistancePC" and isinstance(args[0], _Point) and args[1] is None:
            result = _distance(args[0], None)
        else:
            point, circle = args if isinstance(args[0], _Point) else (args[1], args[0])
            result = Abs(_distance(point, circle.center) - circle.radius)
    elif op == "AreaPoints":
        result = _area(args)
    elif op in {"AnglePPP", "AngleLL"}:
        result = _angle(args)
    elif op == "MidpointPP":
        result = _point((args[0].x + args[1].x) / 2, (args[0].y + args[1].y) / 2)
    elif op == "CircleCenter":
        result = args[0].center
    elif op == "CircleRadius":
        result = args[0].radius
    elif op == "PointX":
        result = args[0].x
    elif op == "PointY":
        result = args[0].y
    elif op in {"Circumcenter", "Circumcircle"}:
        center = _circumcenter(args[0], args[1], args[2])
        result = (
            center
            if op == "Circumcenter" or center is None
            else _circle(center, _distance(center, args[0]))
        )
    elif op == "Orthocenter":
        result = _orthocenter(args[0], args[1], args[2])
    elif op == "Centroid":
        result = _point(
            (args[0].x + args[1].x + args[2].x) / 3,
            (args[0].y + args[1].y + args[2].y) / 3,
        )
    elif op == "Incenter":
        result = _incenter(args[0], args[1], args[2])
    elif op == "Incircle":
        a, b, c = args
        center = _incenter(a, b, c)
        double_area = Abs(a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
        perimeter = _distance(b, c) + _distance(c, a) + _distance(a, b)
        result = _circle(center, double_area / perimeter)
    elif op in {"Excenter", "Excircle"}:
        a, b, c = args
        if node.payload == "B":
            a, b, c = b, c, a
        elif node.payload == "C":
            a, b, c = c, a, b
        center = _excenter(a, b, c)
        if op == "Excenter":
            result = center
        else:
            double_area = Abs(a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
            denominator = -_distance(b, c) + _distance(c, a) + _distance(a, b)
            result = _circle(center, 0 if denominator == 0 else double_area / denominator)
    elif op in {"FootLP", "FootPL"}:
        line, point = args if isinstance(args[0], _Line) else (args[1], args[0])
        result = _foot(line, point)
    elif op in {"ParallelLineLP", "ParallelLinePL"}:
        line, point = args if isinstance(args[0], _Line) else (args[1], args[0])
        result = _line_from_coefficients(line.a, line.b, -(line.a * point.x + line.b * point.y))
    elif op in {"PerpendicularLineLP", "PerpendicularLinePL"}:
        line, point = args if isinstance(args[0], _Line) else (args[1], args[0])
        a, b = line.b, -line.a
        result = _line_from_coefficients(a, b, -(a * point.x + b * point.y))
    elif op == "ParallelLL":
        result = args[0].a * args[1].b - args[1].a * args[0].b
    elif op == "PerpendicularLL":
        result = args[0].a * args[1].a + args[0].b * args[1].b
    elif op == "OnCirclePC":
        result = _distance(args[0], args[1].center) - args[1].radius
    elif op == "OnLinePL":
        result = _distance(args[0], args[1])
    elif op == "OnLinePPP":
        point, first, second = args
        result = (first.x - point.x) * (second.y - point.y) - (first.y - point.y) * (
            second.x - point.x
        )
    elif op == "OnSegmentPPP":
        point, first, second = args
        result = _distance(first, point) + _distance(point, second) - _distance(first, second)
    elif op == "ReflectPP":
        result = _point(2 * args[1].x - args[0].x, 2 * args[1].y - args[0].y)
    elif op == "ReflectPL":
        projection = _foot(args[1], args[0])
        result = _point(2 * projection.x - args[0].x, 2 * projection.y - args[0].y)
    elif op in {"ContactPointCL", "ContactPointLC"}:
        circle, line = args if isinstance(args[0], _Circle) else (args[1], args[0])
        result = _foot(line, circle.center)
    elif op == "IncircleContactPoint":
        a, b, c = args
        side_a, side_b, side_c = _distance(b, c), _distance(c, a), _distance(a, b)
        semiperimeter = (side_a + side_b + side_c) / 2
        contacts = {
            "BC": _point(
                b.x + (c.x - b.x) * ((semiperimeter - side_b) / side_a),
                b.y + (c.y - b.y) * ((semiperimeter - side_b) / side_a),
            ),
            "CA": _point(
                c.x + (a.x - c.x) * ((semiperimeter - side_c) / side_b),
                c.y + (a.y - c.y) * ((semiperimeter - side_c) / side_b),
            ),
            "AB": _point(
                a.x + (b.x - a.x) * ((semiperimeter - side_a) / side_c),
                a.y + (b.y - a.y) * ((semiperimeter - side_a) / side_c),
            ),
        }
        result = contacts[str(node.payload)]
    elif op == "PerpendicularBisector":
        first, second = args
        mid_x, mid_y = (first.x + second.x) / 2, (first.y + second.y) / 2
        a, b = second.x - first.x, -(first.y - second.y)
        result = _line_from_coefficients(a, b, -(a * mid_x + b * mid_y))
    elif op == "AngleBisector":
        a, b, c = args
        bax, bay = a.x - b.x, a.y - b.y
        bcx, bcy = c.x - b.x, c.y - b.y
        norm_ba = simplify(sqrt(bax**2 + bay**2))
        norm_bc = simplify(sqrt(bcx**2 + bcy**2))
        if norm_ba == 0 or norm_bc == 0:
            result = None
        else:
            ux, uy = bax / norm_ba, bay / norm_ba
            vx, vy = bcx / norm_bc, bcy / norm_bc
            wx, wy = ux + vx, uy + vy
            if wx == 0 and wy == 0:
                wx, wy = -uy, ux
            px, py = b.x + wx, b.y + wy
            line_a, line_b = b.y - py, px - b.x
            line_c = -line_a * b.x - line_b * b.y
            result = _line_from_coefficients(line_a, line_b, line_c)
    elif op in {"IsTangentLC", "IsTangentCL"}:
        line, circle = args if isinstance(args[0], _Line) else (args[1], args[0])
        result = Abs(_distance(circle.center, line) - circle.radius)
    elif op == "Intersect":
        from mpmath import mp

        from geotarget.typed_refnum_intersections import evaluate_intersect_extension

        plan, selector_names = node.payload
        selectors = dict(zip(selector_names, args[2:], strict=True))
        result = evaluate_intersect_extension(
            plan,
            args[0],
            args[1],
            point_factory=_point,
            exclude=selectors.get("exclude"),
            near=selectors.get("near"),
            far=selectors.get("far"),
            ambient_dps=mp.dps,
        ).value
    else:  # pragma: no cover - compiler/runtime registry invariant
        raise TypedRefNumRuntimeFault(f"unknown typed opcode: {op}")
    memo[identity] = result
    return result


@dataclass(frozen=True)
class TypedRefNumProgram:
    variable_names: tuple[str, ...]
    constructions: tuple[tuple[str, IRNode], ...]
    constraints: tuple[tuple[IRNode, IRNode], ...]
    support_keys: tuple[SupportKey, ...]
    ast_node_count: int
    compile_seconds: float
    semantic_abi: str = SEMANTIC_ABI

    def numeric_effect_analysis(self) -> NumericEffectAnalysis:
        return analyze_numeric_effects(self)

    def evaluate(self, raw_values: list[float]) -> list[float]:
        if len(raw_values) != len(self.variable_names):
            raise ValueError("typed RefNum evaluator dimension mismatch")
        values = dict(zip(self.variable_names, raw_values, strict=True))
        memo: dict[int, Any] = {}
        try:
            for _name, expression in self.constructions:
                _eval_node(expression, values, memo)
        except Exception:
            # Frozen construction failure invalidates every constraint.
            return [float("nan")] * len(self.constraints)
        residuals: list[float] = []
        for left, right in self.constraints:
            try:
                # Frozen ABI converts each side separately then subtracts in
                # host binary64, in source constraint order.
                residuals.append(
                    float(_eval_node(left, values, memo)) - float(_eval_node(right, values, memo))
                )
            except Exception:
                residuals.append(float("nan"))
        return residuals

    def admission_trace(self) -> dict[str, Any]:
        key_rows = [
            {
                "opcode": key.opcode,
                "operand_types": list(key.operand_types),
                "result_type": key.result_type,
                "selector_kind": key.selector_kind,
                "semantic_abi": key.semantic_abi,
            }
            for key in self.support_keys
        ]
        digest = hashlib.sha256(
            json.dumps(key_rows, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "case_specific_routing": False,
            "problem_identity_read": False,
            "fallback_scope": "whole_problem",
            "support_key_fields": [
                "opcode",
                "resolved_operand_types",
                "result_type",
                "selector_kind",
                "semantic_abi",
            ],
            "support_key_sha256": digest,
            "ast_node_count": self.ast_node_count,
            "compile_seconds": self.compile_seconds,
            "resource_gate": {"max_ast_nodes": 10_000, "max_compile_seconds": 0.25},
            "guard_authority": "frozen_reference_delegate",
            "hard_feasibility_authority": "frozen_reference_delegate",
            "hp_and_exact_authority": "frozen_reference_delegate",
        }


_ARITHMETIC_OPS = {
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
}
_ATTRIBUTE_OPS = {"PointX", "PointY", "CircleCenter", "CircleRadius"}
_PREDICATE_OPS = {
    "OnCirclePC",
    "OnLinePL",
    "OnLinePPP",
    "OnSegmentPPP",
    "ParallelLL",
    "PerpendicularLL",
    "IsTangentLC",
    "IsTangentCL",
}
_INTRINSIC_FAULT_OPS = {
    "Div",
    "Pow",
    "Sqrt",
    "Circle",
    "LinePP",
    "LineABC",
    "PointOnCircle",
    "PointOnSegment",
    "PointOnLine",
    "DistancePP",
    "DistancePL",
    "DistanceLP",
    "DistancePC",
    "DistanceCP",
    "AreaPoints",
    "AnglePPP",
    "AngleLL",
    "Circumcenter",
    "Circumcircle",
    "Orthocenter",
    "Incircle",
    "Excenter",
    "Excircle",
    "FootLP",
    "FootPL",
    "Intersect",
    "AngleBisector",
}
_INTRINSIC_NONFINITE_OPS = _INTRINSIC_FAULT_OPS | {
    "Add",
    "Sub",
    "Mult",
    "Cos",
    "Sin",
}
_BRANCH_SENSITIVE_OPS = {
    "Abs",
    "Div",
    "Pow",
    "Sqrt",
    "Circle",
    "LinePP",
    "LineABC",
    "AnglePPP",
    "AngleLL",
    "Circumcenter",
    "Circumcircle",
    "Orthocenter",
    "Incenter",
    "Incircle",
    "Excenter",
    "Excircle",
    "Intersect",
    "OnSegmentPPP",
    "AngleBisector",
} | _PREDICATE_OPS
_SYMBOLIC_RESULT_OPS = {
    "Sqrt",
    "Cos",
    "Sin",
    "DistancePP",
    "DistancePL",
    "DistanceLP",
    "DistancePC",
    "DistanceCP",
    "AreaPoints",
    "AnglePPP",
    "AngleLL",
    "OnCirclePC",
    "IsTangentLC",
    "IsTangentCL",
}


def _join_exactness(values: tuple[NumericExactness, ...]) -> NumericExactness:
    numeric = {value for value in values if value is not NumericExactness.NON_NUMERIC}
    if not numeric:
        return NumericExactness.NON_NUMERIC
    if numeric == {NumericExactness.EXACT}:
        return NumericExactness.EXACT
    if numeric == {NumericExactness.BF53}:
        return NumericExactness.BF53
    return NumericExactness.MIXED


def _node_exactness(node: IRNode, operands: tuple[NumericEffects, ...]) -> NumericExactness:
    if node.opcode in {"ExactInt", "Rational"}:
        return NumericExactness.EXACT
    if node.opcode in {"BF53Literal", "BF53Input", "Pi"}:
        return NumericExactness.BF53
    return _join_exactness(tuple(effect.exactness for effect in operands))


def _intrinsic_signed_zero(node: IRNode) -> bool:
    if node.opcode == "BF53Input":
        return True
    if node.opcode == "BF53Literal":
        value = float(node.payload)
        return value == 0.0 and math.copysign(1.0, value) < 0
    return node.opcode in _ARITHMETIC_OPS | _SYMBOLIC_RESULT_OPS


def _intrinsic_subnormal(node: IRNode) -> bool:
    if node.opcode == "BF53Input":
        return True
    if node.opcode == "BF53Literal":
        value = abs(float(node.payload))
        return 0.0 < value < sys.float_info.min
    return node.opcode in _ARITHMETIC_OPS | _SYMBOLIC_RESULT_OPS


def _effects_for_node(node: IRNode, operands: tuple[NumericEffects, ...]) -> NumericEffects:
    return NumericEffects(
        may_fault=node.opcode in _INTRINSIC_FAULT_OPS
        or any(effect.may_fault for effect in operands),
        may_nonfinite=node.opcode in _INTRINSIC_NONFINITE_OPS
        or any(effect.may_nonfinite for effect in operands),
        may_signed_zero=_intrinsic_signed_zero(node)
        or any(effect.may_signed_zero for effect in operands),
        may_subnormal=_intrinsic_subnormal(node)
        or any(effect.may_subnormal for effect in operands),
        exactness=_node_exactness(node, operands),
        branch_sensitive=node.opcode in _BRANCH_SENSITIVE_OPS
        or any(effect.branch_sensitive for effect in operands),
        requires_symbolic_composition=node.opcode in _SYMBOLIC_RESULT_OPS
        or any(effect.requires_symbolic_composition for effect in operands),
    )


def _consumer_role(node: IRNode, operand: IRNode, operand_index: int) -> ConsumerRole:
    if node.opcode in _ARITHMETIC_OPS:
        return ConsumerRole.ARITHMETIC_OPERAND
    if node.opcode == "Point":
        return ConsumerRole.GEOMETRY_COORDINATE
    if node.opcode == "Circle" and operand_index == 1:
        return ConsumerRole.CONSTRUCTOR_PRECONDITION
    if node.opcode == "Intersect" and operand_index >= 2:
        return ConsumerRole.SELECTOR
    if node.opcode in _PREDICATE_OPS:
        return ConsumerRole.PREDICATE_OPERAND
    if node.opcode in _ATTRIBUTE_OPS:
        return ConsumerRole.ATTRIBUTE_OWNER
    if operand.result_type in {"point2", "point_or_list", "line2", "circle2"}:
        return ConsumerRole.GEOMETRY_OPERAND
    return ConsumerRole.FUNCTION_OPERAND


def analyze_numeric_effects(program: TypedRefNumProgram) -> NumericEffectAnalysis:
    """Build identity-free numeric effects for every node and consumer edge."""

    records: list[NumericEffectNode] = []
    node_indexes: dict[int, int] = {}
    effects_by_identity: dict[int, NumericEffects] = {}

    def visit(node: IRNode) -> NumericEffects:
        identity = id(node)
        if identity in effects_by_identity:
            return effects_by_identity[identity]
        operand_effects = tuple(visit(operand) for operand in node.operands)
        effects = _effects_for_node(node, operand_effects)
        index = len(records)
        node_indexes[identity] = index
        effects_by_identity[identity] = effects
        records.append(NumericEffectNode(index, node.opcode, node.result_type, effects))
        return effects

    for _name, root in program.constructions:
        visit(root)
    for constraint in program.constraints:
        for root in constraint:
            visit(root)

    edges: list[NumericEffectEdge] = []
    expanded: set[int] = set()

    def expand(node: IRNode) -> None:
        identity = id(node)
        if identity in expanded:
            return
        expanded.add(identity)
        consumer_index = node_indexes[identity]
        for operand_index, operand in enumerate(node.operands):
            edges.append(
                NumericEffectEdge(
                    producer_index=node_indexes[id(operand)],
                    consumer_index=consumer_index,
                    consumer_opcode=node.opcode,
                    operand_index=operand_index,
                    role=_consumer_role(node, operand, operand_index),
                    root_ordinal=None,
                    effects=effects_by_identity[id(operand)],
                    consumer_effects=effects_by_identity[identity],
                )
            )
            expand(operand)

    for ordinal, (_name, root) in enumerate(program.constructions):
        edges.append(
            NumericEffectEdge(
                producer_index=node_indexes[id(root)],
                consumer_index=None,
                consumer_opcode="$construction",
                operand_index=0,
                role=ConsumerRole.CONSTRUCTION_ROOT,
                root_ordinal=ordinal,
                effects=effects_by_identity[id(root)],
                consumer_effects=None,
            )
        )
        expand(root)
    for ordinal, constraint in enumerate(program.constraints):
        for side_index, root in enumerate(constraint):
            edges.append(
                NumericEffectEdge(
                    producer_index=node_indexes[id(root)],
                    consumer_index=None,
                    consumer_opcode="$constraint",
                    operand_index=side_index,
                    role=ConsumerRole.CONSTRAINT_SIDE_ROOT,
                    root_ordinal=ordinal,
                    effects=effects_by_identity[id(root)],
                    consumer_effects=None,
                )
            )
            expand(root)
    return NumericEffectAnalysis(tuple(records), tuple(edges))


def certify_numeric_effects(
    analysis: NumericEffectAnalysis, policy: NumericEffectPolicy
) -> NumericEffectCertification:
    """Certify every edge against backend capabilities, without problem identity."""

    issues: list[NumericEffectIssue] = []
    for edge in analysis.edges:
        effects = edge.effects
        transition_effects = edge.consumer_effects or effects
        capability = policy.capability_for(edge.role)
        unsupported: list[str] = []
        checks = (
            (transition_effects.may_fault, capability.allow_may_fault, "may_fault"),
            (
                transition_effects.may_nonfinite,
                capability.allow_may_nonfinite,
                "may_nonfinite",
            ),
            (effects.may_signed_zero, capability.allow_signed_zero, "may_signed_zero"),
            (effects.may_subnormal, capability.allow_subnormal, "may_subnormal"),
            (
                transition_effects.branch_sensitive,
                capability.allow_branch_sensitive,
                "branch_sensitive",
            ),
            (
                effects.requires_symbolic_composition,
                capability.preserve_symbolic_composition,
                "requires_symbolic_composition",
            ),
        )
        unsupported.extend(name for present, allowed, name in checks if present and not allowed)
        if effects.exactness not in capability.accepted_exactness:
            unsupported.append(f"exactness:{effects.exactness.value}")
        if unsupported:
            issues.append(NumericEffectIssue(edge, tuple(unsupported)))
    return NumericEffectCertification(not issues, tuple(issues))


@dataclass(frozen=True)
class TypedRefNumDispatch:
    """Whole-problem dispatcher decision and its auditable semantic inputs."""

    program: TypedRefNumProgram | None
    fallback_reason: str | None
    trace: dict[str, Any]

    @property
    def supported(self) -> bool:
        return self.program is not None


class TypedRefNumResidualEvaluator:
    """Residual facade; every non-double-residual authority stays frozen."""

    def __init__(self, reference: Any, program: TypedRefNumProgram):
        self.reference = reference
        self.program = program
        self.bundle = reference.bundle
        self.compiled_guards = reference.compiled_guards

    def evaluate_float_residual(self, values: list[float]):
        from geosolver._internal.autosolve.execution.interpreter_helpers import (
            _residual_norm,
        )
        from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import (
            EvaluationStatus,
            classify_evaluation_failure,
        )
        from geosolver._internal.pipeline.evaluator.evaluate_float_residual import (
            FloatResidualEvaluation,
        )

        residuals = self.program.evaluate(list(values))
        status = classify_evaluation_failure(residuals)
        norm = _residual_norm(residuals) if status is EvaluationStatus.OK else math.inf
        return FloatResidualEvaluation(
            residual_vector=residuals,
            residual_norm_float=norm,
            evaluation_status=status,
            is_finite=(status is EvaluationStatus.OK),
        )

    def evaluate_guard(self, values: list[float]):
        return self.reference.evaluate_guard(values)

    def evaluate_float_hard_feasibility(self, values: list[float]):
        return self.reference.evaluate_float_hard_feasibility(values)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.reference, name)


class _Compiler:
    def __init__(self, bundle: Any, *, max_ast_nodes: int, deadline: float):
        self.bundle = bundle
        self.max_ast_nodes = max_ast_nodes
        self.deadline = deadline
        self.node_count = 0
        self.types: dict[str, ValueType] = {name: "scalar" for name in bundle.var_names}
        self.nodes: dict[str, IRNode] = {
            name: IRNode("BF53Input", "scalar", payload=name) for name in bundle.var_names
        }
        self.types["pi"] = "scalar"
        self.nodes["pi"] = IRNode("Pi", "scalar")
        self.keys: set[SupportKey] = set()

    def _validate_frozen_call_contracts(self, tree: ast.AST) -> None:
        """Bind every call against the callable actually exported by V15.

        Typed lowering may implement fewer signatures than the frozen runtime,
        but it must never invent a symbol, alias, arity, or keyword accepted by
        neither the source context nor its selected SymPy backend.
        """

        context = self.bundle.base_context
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            if not isinstance(call.func, ast.Name):
                raise UnsupportedTypedRefNumIR("frozen call target must be a named symbol")
            name = call.func.id
            exported = context.get(name)
            if not callable(exported):
                raise UnsupportedTypedRefNumIR(
                    f"callable is not exported by frozen V15 context: {name}"
                )
            authority = getattr(exported, "_sympy", None) or exported
            try:
                signature = inspect.signature(authority)
                signature.bind(
                    *(object() for _ in call.args),
                    **{
                        keyword.arg: object()
                        for keyword in call.keywords
                        if keyword.arg is not None
                    },
                )
            except (TypeError, ValueError) as error:
                raise UnsupportedTypedRefNumIR(
                    f"frozen callable contract mismatch: {name}: {error}"
                ) from error
            if any(keyword.arg is None for keyword in call.keywords):
                raise UnsupportedTypedRefNumIR(
                    f"frozen callable **kwargs admission is unsupported: {name}"
                )

    def _tick(self, tree: ast.AST) -> None:
        self.node_count += sum(1 for _ in ast.walk(tree))
        if self.node_count > self.max_ast_nodes:
            raise UnsupportedTypedRefNumIR("typed IR AST resource limit exceeded")
        if time.monotonic() > self.deadline:
            raise UnsupportedTypedRefNumIR("typed IR compile time resource limit exceeded")

    def expression(self, source: str | int | float) -> IRNode:
        if isinstance(source, bool):
            raise UnsupportedTypedRefNumIR("bool is not a numeric literal")
        if isinstance(source, int):
            return IRNode("ExactInt", "scalar", payload=source)
        if isinstance(source, float):
            return IRNode("BF53Literal", "scalar", payload=source)
        tree = ast.parse(source, mode="eval")
        self._tick(tree)
        self._validate_frozen_call_contracts(tree)
        return self.visit(tree.body)

    def visit(self, node: ast.AST) -> IRNode:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, int | float):
                raise UnsupportedTypedRefNumIR("only non-bool numeric literals are supported")
            opcode = "ExactInt" if isinstance(node.value, int) else "BF53Literal"
            return IRNode(opcode, "scalar", payload=node.value)
        if isinstance(node, ast.Name):
            try:
                return self.nodes[node.id]
            except KeyError as error:
                raise UnsupportedTypedRefNumIR(f"unknown typed name: {node.id}") from error
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            operand = self.visit(node.operand)
            self._require_types((operand,), ("scalar",))
            opcode = type(node.op).__name__
            return self._make(opcode, "scalar", (operand,))
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, ast.Add | ast.Sub | ast.Mult | ast.Div | ast.Pow
        ):
            left, right = self.visit(node.left), self.visit(node.right)
            self._require_types((left, right), ("scalar", "scalar"))
            return self._make(type(node.op).__name__, "scalar", (left, right))
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            owner = self.visit(node.value)
            attributes = {
                ("point2", "x"): ("PointX", "scalar"),
                ("point2", "y"): ("PointY", "scalar"),
                ("point_or_list", "x"): ("PointX", "scalar"),
                ("point_or_list", "y"): ("PointY", "scalar"),
                ("circle2", "center"): ("CircleCenter", "point2"),
                ("circle2", "radius"): ("CircleRadius", "scalar"),
            }
            try:
                opcode, result_type = attributes[(owner.result_type, node.attr)]
            except KeyError as error:
                raise UnsupportedTypedRefNumIR(
                    f"unsupported typed attribute: {owner.result_type}.{node.attr}"
                ) from error
            return self._make(opcode, result_type, (owner,))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "Intersect":
                return self._intersect_call(node)
            if node.func.id in {"IncircleContactPoint", "ContactPoint"} and node.keywords:
                return self._incircle_contact_call(node)
            if node.func.id in {"Excenter", "Excircle"} and node.keywords:
                return self._excircle_call(node)
            if not node.keywords:
                return self._call(node.func.id, tuple(self.visit(arg) for arg in node.args))
        raise UnsupportedTypedRefNumIR(f"unsupported typed AST node: {type(node).__name__}")

    @staticmethod
    def _require_types(nodes: tuple[IRNode, ...], expected: tuple[str, ...]) -> None:
        observed = tuple(node.result_type for node in nodes)
        compatible = tuple(
            wanted == actual or (wanted == "point2" and actual == "point_or_list")
            for actual, wanted in zip(observed, expected, strict=True)
        )
        if not all(compatible):
            raise UnsupportedTypedRefNumIR(
                f"typed signature mismatch: expected {expected}, got {observed}"
            )

    def _make(self, opcode: str, result: ValueType, args: tuple[IRNode, ...]) -> IRNode:
        self.keys.add(SupportKey(opcode, tuple(arg.result_type for arg in args), result, "none"))
        return IRNode(opcode, result, args)

    def _call(self, name: str, args: tuple[IRNode, ...]) -> IRNode:
        actual_signature = tuple(arg.result_type for arg in args)
        # An exclude-only Intersect is a Point exactly when one candidate
        # survives; otherwise it is a list.  Compile Point consumers against
        # their ordinary signature, while retaining the union in the IR and
        # SupportKey.  A list then faults at the normal construction/constraint
        # evaluation boundary, exactly as the frozen evaluator does.
        signature = tuple(
            "point2" if value_type == "point_or_list" else value_type
            for value_type in actual_signature
        )
        if name == "sqrt" and signature == ("scalar",):
            return self._make("Sqrt", "scalar", args)
        if name in {"cos", "sin", "abs"} and signature == ("scalar",):
            return self._make(name.capitalize(), "scalar", args)
        if name == "Point" and signature == ("scalar", "scalar"):
            return self._make("Point", "point2", args)
        if name == "Circle" and signature == ("point2", "scalar"):
            return self._make("Circle", "circle2", args)
        if name == "PointOnCircle" and signature == ("circle2", "scalar"):
            return self._make("PointOnCircle", "point2", args)
        if name == "PointOnSegment" and signature == ("point2", "point2", "scalar"):
            return self._make("PointOnSegment", "point2", args)
        if name == "PointOnLine" and signature == ("line2", "scalar"):
            return self._make("PointOnLine", "point2", args)
        if name == "Line" and signature == ("point2", "point2"):
            return self._make("LinePP", "line2", args)
        if name == "Line" and signature == ("scalar", "scalar", "scalar"):
            return self._make("LineABC", "line2", args)
        distance_opcodes = {
            ("point2", "point2"): "DistancePP",
            ("point2", "line2"): "DistancePL",
            ("line2", "point2"): "DistanceLP",
            ("point2", "circle2"): "DistancePC",
            ("circle2", "point2"): "DistanceCP",
        }
        if name == "Distance" and signature in distance_opcodes:
            return self._make(distance_opcodes[signature], "scalar", args)
        if name == "Area" and len(args) >= 3 and set(signature) == {"point2"}:
            return self._make("AreaPoints", "scalar", args)
        if name == "Angle" and signature == ("point2", "point2", "point2"):
            return self._make("AnglePPP", "scalar", args)
        if name == "Angle" and signature == ("line2", "line2"):
            return self._make("AngleLL", "scalar", args)
        if name == "Midpoint" and signature == ("point2", "point2"):
            return self._make("MidpointPP", "point2", args)
        if name in {"Midpoint", "Center"} and signature == ("circle2",):
            return self._make("CircleCenter", "point2", args)
        if name == "Radius" and signature == ("circle2",):
            return self._make("CircleRadius", "scalar", args)
        if name in {"Circumcenter", "Orthocenter", "Centroid", "Incenter"} and signature == (
            "point2",
            "point2",
            "point2",
        ):
            return self._make(name, "point2", args)
        if name == "Incircle" and signature == ("point2", "point2", "point2"):
            return self._make("Incircle", "circle2", args)
        if name in {"Excenter", "Excircle"} and signature == (
            "point2",
            "point2",
            "point2",
        ):
            result_type: ValueType = "point2" if name == "Excenter" else "circle2"
            self.keys.add(
                SupportKey(
                    name,
                    actual_signature,
                    result_type,
                    "vertex:A",
                )
            )
            return IRNode(name, result_type, args, payload="A")
        if name in {"Circumcircle", "CircleThroughThreePoints"} and signature == (
            "point2",
            "point2",
            "point2",
        ):
            return self._make("Circumcircle", "circle2", args)
        if name == "CircleThroughPoint" and signature == ("point2", "point2"):
            center, point = args
            radius = self._make("DistancePP", "scalar", (center, point))
            return self._make("Circle", "circle2", (center, radius))
        symmetric_line_point = {
            ("line2", "point2"): "LP",
            ("point2", "line2"): "PL",
        }
        if name in {"FootOfPerpendicular", "Foot"} and signature in symmetric_line_point:
            return self._make(f"Foot{symmetric_line_point[signature]}", "point2", args)
        if name in {"ParallelLine", "PerpendicularLine"} and signature in symmetric_line_point:
            return self._make(f"{name}{symmetric_line_point[signature]}", "line2", args)
        if name in {"Parallel", "Perpendicular"} and signature == ("line2", "line2"):
            return self._make(f"{name}LL", "scalar", args)
        if name == "OnCircle" and signature == ("point2", "circle2"):
            return self._make("OnCirclePC", "scalar", args)
        if name in {"OnLine", "Collinear"} and signature == ("point2", "line2"):
            return self._make("OnLinePL", "scalar", args)
        if name in {"OnLine", "Collinear"} and signature == (
            "point2",
            "point2",
            "point2",
        ):
            return self._make("OnLinePPP", "scalar", args)
        if name == "OnSegment" and signature == ("point2", "point2", "point2"):
            return self._make("OnSegmentPPP", "scalar", args)
        if name == "Reflect" and signature == ("point2", "point2"):
            return self._make("ReflectPP", "point2", args)
        if name == "Reflect" and signature == ("point2", "line2"):
            return self._make("ReflectPL", "point2", args)
        contact = {("circle2", "line2"): "CL", ("line2", "circle2"): "LC"}
        if name == "ContactPoint" and signature in contact:
            return self._make(f"ContactPoint{contact[signature]}", "point2", args)
        if name == "PerpendicularBisector" and signature == ("point2", "point2"):
            return self._make("PerpendicularBisector", "line2", args)
        if name == "AngleBisector" and signature == ("point2", "point2", "point2"):
            return self._make("AngleBisector", "line2", args)
        tangent = {("line2", "circle2"): "LC", ("circle2", "line2"): "CL"}
        if name == "IsTangent" and signature in tangent:
            return self._make(f"IsTangent{tangent[signature]}", "scalar", args)
        raise UnsupportedTypedRefNumIR(f"unsupported typed call: {name}{signature}")

    def _intersect_call(self, node: ast.Call) -> IRNode:
        from geotarget.typed_refnum_intersections import compile_intersect_extension

        if len(node.args) != 2:
            raise UnsupportedTypedRefNumIR("Intersect requires two geometry operands")
        geometry = tuple(self.visit(argument) for argument in node.args)
        selector_literals: dict[str, Any] = {}
        selector_types: dict[str, str] = {}
        selector_names: list[str] = []
        selector_nodes: list[IRNode] = []
        for keyword in node.keywords:
            if keyword.arg is None:
                raise UnsupportedTypedRefNumIR("Intersect does not support ** selectors")
            if keyword.arg == "n":
                if not (
                    isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, int)
                    and not isinstance(keyword.value.value, bool)
                ):
                    raise UnsupportedTypedRefNumIR("Intersect n must be a literal int")
                selector_literals["n"] = keyword.value.value
                selector_types["n"] = "exact_int"
                continue
            selector_node = self.visit(keyword.value)
            selector_literals[keyword.arg] = selector_node
            selector_types[keyword.arg] = selector_node.result_type
            selector_names.append(keyword.arg)
            selector_nodes.append(selector_node)
        try:
            plan = compile_intersect_extension(
                tuple(value.result_type for value in geometry),
                selector_literals,
                selector_operand_types=selector_types,
            )
        except Exception as error:
            raise UnsupportedTypedRefNumIR(str(error)) from error
        if plan.result_type not in {"point2", "point_or_list"}:
            raise UnsupportedTypedRefNumIR(
                f"Intersect result {plan.result_type} is not supported by the typed IR"
            )
        result_type: ValueType = plan.result_type
        selector_signature = tuple(
            f"{name}:{value_type}" for name, value_type in plan.support_key.selector_operand_types
        )
        self.keys.add(
            SupportKey(
                "Intersect",
                tuple(value.result_type for value in geometry) + selector_signature,
                result_type,
                plan.support_key.selector_kind,
                plan.support_key.semantic_abi,
            )
        )
        return IRNode(
            "Intersect",
            result_type,
            geometry + tuple(selector_nodes),
            payload=(plan, tuple(selector_names)),
        )

    def _incircle_contact_call(self, node: ast.Call) -> IRNode:
        if len(node.args) != 3 or len(node.keywords) != 1:
            raise UnsupportedTypedRefNumIR("IncircleContactPoint requires three Points and side")
        keyword = node.keywords[0]
        if not (
            keyword.arg == "side"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value in {"BC", "CA", "AB", 0, 1, 2}
        ):
            raise UnsupportedTypedRefNumIR("IncircleContactPoint side must be BC, CA, or AB")
        args = tuple(self.visit(argument) for argument in node.args)
        self._require_types(args, ("point2", "point2", "point2"))
        side = {0: "BC", 1: "CA", 2: "AB"}.get(keyword.value.value, keyword.value.value)
        self.keys.add(
            SupportKey(
                "IncircleContactPoint",
                tuple(arg.result_type for arg in args),
                "point2",
                f"side:{side}",
            )
        )
        return IRNode("IncircleContactPoint", "point2", args, payload=side)

    def _excircle_call(self, node: ast.Call) -> IRNode:
        if len(node.args) != 3 or len(node.keywords) != 1:
            raise UnsupportedTypedRefNumIR("Excenter/Excircle requires three Points and vertex")
        keyword = node.keywords[0]
        if not (
            keyword.arg == "vertex"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value in {"A", "B", "C", 0, 1, 2}
        ):
            raise UnsupportedTypedRefNumIR("Excenter/Excircle vertex must be A, B, or C")
        args = tuple(self.visit(argument) for argument in node.args)
        self._require_types(args, ("point2", "point2", "point2"))
        vertex = {0: "A", 1: "B", 2: "C"}.get(keyword.value.value, keyword.value.value)
        opcode = node.func.id
        result_type: ValueType = "point2" if opcode == "Excenter" else "circle2"
        self.keys.add(
            SupportKey(
                opcode,
                tuple(arg.result_type for arg in args),
                result_type,
                f"vertex:{vertex}",
            )
        )
        return IRNode(opcode, result_type, args, payload=vertex)


def compile_typed_refnum_program(
    bundle: Any, *, max_ast_nodes: int = 10_000, max_compile_seconds: float = 0.25
) -> TypedRefNumProgram:
    """Compile a complete V15 residual program from semantic inputs only."""

    if max_ast_nodes < 1 or max_compile_seconds <= 0 or not math.isfinite(max_compile_seconds):
        raise ValueError("invalid typed IR resource gate")
    exported_names = frozenset(bundle.base_context)
    variable_collisions = sorted(set(bundle.var_names) & exported_names)
    construction_collisions = sorted(
        {item.name for item in bundle.spec.construction} & exported_names
    )
    if variable_collisions or construction_collisions:
        collisions = sorted(set(variable_collisions) | set(construction_collisions))
        raise UnsupportedTypedRefNumIR(
            "source-order namespace shadowing requires reference fallback: " + ", ".join(collisions)
        )
    started = time.monotonic()
    compiler = _Compiler(
        bundle, max_ast_nodes=max_ast_nodes, deadline=started + max_compile_seconds
    )
    constructions: list[tuple[str, IRNode]] = []
    for item in bundle.spec.construction:
        expression = compiler.expression(item.expr)
        if item.name in compiler.nodes:
            raise UnsupportedTypedRefNumIR(f"duplicate typed name: {item.name}")
        compiler.nodes[item.name] = expression
        compiler.types[item.name] = expression.result_type
        constructions.append((item.name, expression))
    constraints = tuple(
        (compiler.expression(left), compiler.expression(right))
        for left, right in zip(bundle.spec.constraints, bundle.targets, strict=True)
    )
    elapsed = time.monotonic() - started
    if elapsed > max_compile_seconds:
        raise UnsupportedTypedRefNumIR("typed IR compile time resource limit exceeded")
    return TypedRefNumProgram(
        variable_names=tuple(bundle.var_names),
        constructions=tuple(constructions),
        constraints=constraints,
        support_keys=tuple(
            sorted(compiler.keys, key=lambda key: (key.opcode, key.operand_types, key.result_type))
        ),
        ast_node_count=compiler.node_count,
        compile_seconds=elapsed,
    )


def dispatch_typed_refnum_program(
    bundle: Any, *, max_ast_nodes: int = 10_000, max_compile_seconds: float = 0.25
) -> TypedRefNumDispatch:
    """Attempt complete admission and return a trace for either decision.

    This is the only non-raising integration point intended for the product
    dispatcher.  It never exposes a partially compiled program.
    """

    attempted_opcodes: set[str] = set()
    parse_error = False
    sources: list[Any] = [item.expr for item in bundle.spec.construction]
    sources.extend(bundle.spec.constraints)
    sources.extend(bundle.targets)
    guard_opcodes: set[str] = set()
    for source in bundle.spec.guards:
        if not isinstance(source, str):
            guard_opcodes.add("UnsupportedGuardLiteral")
            continue
        try:
            guard_tree = ast.parse(source, mode="eval")
        except SyntaxError:
            guard_opcodes.add("ParseError")
            continue
        guard_opcodes.update(
            node.func.id
            for node in ast.walk(guard_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        )
    for source in sources:
        if not isinstance(source, str):
            attempted_opcodes.add(
                "ExactInt"
                if isinstance(source, int) and not isinstance(source, bool)
                else "BF53Literal"
                if isinstance(source, float)
                else "UnsupportedLiteral"
            )
            continue
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError:
            parse_error = True
            attempted_opcodes.add("ParseError")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                attempted_opcodes.add(node.func.id)
            elif isinstance(node, ast.operator | ast.unaryop):
                attempted_opcodes.add(type(node).__name__)

    common_trace = {
        "case_specific_routing": False,
        "problem_identity_read": False,
        "corpus_metadata_read": False,
        "truth_read": False,
        "fallback_scope": "whole_problem",
        "semantic_abi": SEMANTIC_ABI,
        "attempted_ast_opcodes": sorted(attempted_opcodes),
        "delegated_guard_opcodes": sorted(guard_opcodes),
        "parse_error": parse_error,
        "guard_authority": "frozen_reference_delegate",
        "hard_feasibility_authority": "frozen_reference_delegate",
        "hp_and_exact_authority": "frozen_reference_delegate",
        "resource_gate": {
            "max_ast_nodes": max_ast_nodes,
            "max_compile_seconds": max_compile_seconds,
        },
    }
    try:
        program = compile_typed_refnum_program(
            bundle,
            max_ast_nodes=max_ast_nodes,
            max_compile_seconds=max_compile_seconds,
        )
    except (SyntaxError, UnsupportedTypedRefNumIR, ValueError) as error:
        return TypedRefNumDispatch(
            program=None,
            fallback_reason=f"{type(error).__name__}: {error}",
            trace={**common_trace, "admitted": False, "partial_program_exposed": False},
        )
    return TypedRefNumDispatch(
        program=program,
        fallback_reason=None,
        trace={**common_trace, **program.admission_trace(), "admitted": True},
    )
