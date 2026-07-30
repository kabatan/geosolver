"""Closed, equality-only semantic dispatch for exact source replay.

This candidate repairs a relation only after the current QQBar replay failed
at its scalar coercion seam.  It does not add ordering, sign tests, general
transcendentals, or a scalar-to-angle coercion.  A bounded Qbar[pi] affine
form is compared coefficientwise, using pi's transcendence over Qbar.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
from typing import Any, Mapping, Union

import sympy as sp


SCHEMA = "geotarget.v15-243-typed-semantic-equal-qbar-pi-affine/v1"
POINT_ANGLE = "POINT_UNSIGNED_RADIAN_[0,PI]"
LINE_ANGLE = "LINE_ACUTE_RADIAN_[0,PI/2]"
MAX_AFFINE_NODES = 12
REOPEN_FAILURES = frozenset(
    ("value is not exact rational", "scalar is not an exact angle expression")
)


class FailClosed(ValueError):
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def _exact_algebraic(value: object) -> sp.Expr:
    if isinstance(value, (str, bytes, bool, float)) or not isinstance(value, sp.Expr):
        if isinstance(value, int) and not isinstance(value, bool):
            value = sp.Integer(value)
        else:
            raise FailClosed("Qbar value must already be exact")
    if value.has(sp.Float) or value.free_symbols:
        raise FailClosed("Qbar value is approximate or open")
    if value.is_algebraic is not True or value.is_real is not True:
        raise FailClosed("value is not proved real algebraic")
    return value


def _zero(value: sp.Expr) -> bool:
    value = sp.simplify(value)
    if value == 0 or value.is_zero is True:
        return True
    if value.is_zero is False:
        return False
    answer = value.equals(0)
    if answer is None:
        raise FailClosed("exact algebraic equality is undecidable")
    return bool(answer)


def _equal(left: sp.Expr, right: sp.Expr) -> bool:
    return _zero(left - right)


def _sign(value: sp.Expr) -> int:
    if _zero(value):
        return 0
    if value.is_positive is True:
        return 1
    if value.is_negative is True:
        return -1
    raise FailClosed("exact algebraic sign is undecidable")


@dataclass(frozen=True)
class RationalValue:
    value: Fraction


@dataclass(frozen=True)
class QBarValue:
    value: sp.Expr


@dataclass(frozen=True)
class PiMultiple:
    coefficient: Fraction


@dataclass(frozen=True)
class PiAffine:
    coefficient: sp.Expr
    offset: sp.Expr
    node_count: int


@dataclass(frozen=True)
class AngleValue:
    cosine: sp.Expr
    sine: sp.Expr
    unit: str
    domain: str
    direct_source_angle: bool


TypedValue = Union[RationalValue, QBarValue, PiMultiple, PiAffine, AngleValue]


@dataclass(frozen=True)
class ReplayLedger:
    original_failure: str
    direct_source_equality: bool = True
    source_bytes_exact: bool = True
    coordinate_roots_exact: bool = True
    constraints_exact_except_selected_relation: bool = True
    guards_bounds_exact: bool = True
    branch_selector_phase_exact: bool = True
    selected_relation_only_failure: bool = True
    raw_target_exact: bool = True
    square_free_minpoly_exact: bool = True
    real_root_ordinal_exact: bool = True
    isolator_exact: bool = True
    truth_used: bool = False
    routing_used: bool = False
    order_or_sign_requested: bool = False

    def ready(self) -> bool:
        values = asdict(self)
        return bool(
            values.pop("original_failure") in REOPEN_FAILURES
            and values.pop("truth_used") is False
            and values.pop("routing_used") is False
            and values.pop("order_or_sign_requested") is False
            and all(value is True for value in values.values())
        )

    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(asdict(self))).hexdigest()


def _keys(node: Mapping[str, Any], allowed: set[str]) -> None:
    if set(node) != allowed:
        raise FailClosed("typed source node has unknown or missing fields")


def _as_affine(value: TypedValue, *, node_count: int) -> PiAffine:
    if isinstance(value, PiAffine):
        count = value.node_count + node_count
        result = PiAffine(value.coefficient, value.offset, count)
    elif isinstance(value, PiMultiple):
        result = PiAffine(sp.Rational(value.coefficient.numerator, value.coefficient.denominator), sp.Integer(0), node_count)
    elif isinstance(value, RationalValue):
        result = PiAffine(sp.Integer(0), sp.Rational(value.value.numerator, value.value.denominator), node_count)
    elif isinstance(value, QBarValue):
        result = PiAffine(sp.Integer(0), value.value, node_count)
    else:
        raise FailClosed("angle/unknown value cannot enter Qbar[pi]")
    if result.node_count > MAX_AFFINE_NODES:
        raise FailClosed("Qbar[pi] affine form exceeds candidate bound")
    return result


def _algebraic_scalar(value: TypedValue) -> sp.Expr:
    if isinstance(value, RationalValue):
        return sp.Rational(value.value.numerator, value.value.denominator)
    if isinstance(value, QBarValue):
        return value.value
    raise FailClosed("affine scaling needs a typed algebraic scalar")


def _add_sub(left: TypedValue, right: TypedValue, *, subtract: bool, nodes: int) -> TypedValue:
    if isinstance(left, AngleValue) or isinstance(right, AngleValue):
        raise FailClosed("nested angle arithmetic is outside direct equality")
    if isinstance(left, (PiMultiple, PiAffine)) or isinstance(right, (PiMultiple, PiAffine)):
        first = _as_affine(left, node_count=0)
        second = _as_affine(right, node_count=0)
        sign = -1 if subtract else 1
        result = PiAffine(
            sp.simplify(first.coefficient + sign * second.coefficient),
            sp.simplify(first.offset + sign * second.offset),
            nodes,
        )
        if result.node_count > MAX_AFFINE_NODES:
            raise FailClosed("Qbar[pi] affine form exceeds candidate bound")
        return result
    if type(left) is not type(right):
        raise FailClosed("mixed exact scalar types are not coerced")
    if isinstance(left, RationalValue):
        return RationalValue(left.value - right.value if subtract else left.value + right.value)
    if isinstance(left, QBarValue):
        return QBarValue(sp.simplify(left.value - right.value if subtract else left.value + right.value))
    raise FailClosed("unsupported typed addition")


def _multiply(left: TypedValue, right: TypedValue, *, nodes: int) -> TypedValue:
    left_pi = isinstance(left, (PiMultiple, PiAffine))
    right_pi = isinstance(right, (PiMultiple, PiAffine))
    if left_pi and right_pi:
        raise FailClosed("nonlinear pi product is outside affine authority")
    if left_pi or right_pi:
        pi_value, scalar = (left, right) if left_pi else (right, left)
        scalar_value = _algebraic_scalar(scalar)
        if isinstance(pi_value, PiMultiple) and isinstance(scalar, RationalValue):
            return PiMultiple(pi_value.coefficient * scalar.value)
        affine = _as_affine(pi_value, node_count=0)
        if nodes > MAX_AFFINE_NODES:
            raise FailClosed("Qbar[pi] affine form exceeds candidate bound")
        return PiAffine(sp.simplify(affine.coefficient * scalar_value), sp.simplify(affine.offset * scalar_value), nodes)
    if isinstance(left, AngleValue) or isinstance(right, AngleValue):
        raise FailClosed("angle scaling is outside direct equality")
    if type(left) is not type(right):
        raise FailClosed("mixed exact scalar types are not coerced")
    if isinstance(left, RationalValue):
        return RationalValue(left.value * right.value)
    if isinstance(left, QBarValue):
        return QBarValue(sp.simplify(left.value * right.value))
    raise FailClosed("unsupported typed multiplication")


def _divide(left: TypedValue, right: TypedValue, *, nodes: int) -> TypedValue:
    if isinstance(right, (PiMultiple, PiAffine, AngleValue)):
        raise FailClosed("division by pi/angle is outside affine authority")
    divisor = _algebraic_scalar(right)
    if _zero(divisor):
        raise FailClosed("division by zero")
    if isinstance(left, PiMultiple) and isinstance(right, RationalValue):
        return PiMultiple(left.coefficient / right.value)
    if isinstance(left, (PiMultiple, PiAffine)):
        affine = _as_affine(left, node_count=0)
        if nodes > MAX_AFFINE_NODES:
            raise FailClosed("Qbar[pi] affine form exceeds candidate bound")
        return PiAffine(sp.simplify(affine.coefficient / divisor), sp.simplify(affine.offset / divisor), nodes)
    if isinstance(left, AngleValue):
        raise FailClosed("angle division is outside direct equality")
    if type(left) is not type(right):
        raise FailClosed("mixed exact scalar types are not coerced")
    if isinstance(left, RationalValue):
        return RationalValue(left.value / right.value)
    if isinstance(left, QBarValue):
        return QBarValue(sp.simplify(left.value / right.value))
    raise FailClosed("unsupported typed division")


def compile_operand(node: Mapping[str, Any], *, depth: int = 0) -> tuple[TypedValue, int]:
    if not isinstance(node, Mapping) or depth > MAX_AFFINE_NODES:
        raise FailClosed("typed source expression is missing or too deeply nested")
    operation = node.get("op")
    if operation == "rational":
        _keys(node, {"op", "numerator", "denominator"})
        numerator, denominator = node["numerator"], node["denominator"]
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (numerator, denominator)) or denominator == 0:
            raise FailClosed("rational literal is malformed")
        return RationalValue(Fraction(numerator, denominator)), 1
    if operation == "qbar":
        _keys(node, {"op", "value"})
        return QBarValue(_exact_algebraic(node["value"])), 1
    if operation == "pi":
        _keys(node, {"op"})
        return PiMultiple(Fraction(1)), 1
    if operation == "angle":
        _keys(node, {"op", "cosine", "sine", "unit", "domain", "direct"})
        cosine = _exact_algebraic(node["cosine"])
        sine = _exact_algebraic(node["sine"])
        domain = node["domain"]
        if node["direct"] is not True or node["unit"] != "radian" or domain not in (POINT_ANGLE, LINE_ANGLE):
            raise FailClosed("angle is not a direct known-domain radian Angle")
        if not _zero(cosine * cosine + sine * sine - 1) or _sign(sine) < 0:
            raise FailClosed("angle unit pair/domain is invalid")
        if domain == LINE_ANGLE and _sign(cosine) < 0:
            raise FailClosed("line angle is outside the acute domain")
        return AngleValue(cosine, sine, "radian", domain, True), 1
    if operation == "neg":
        _keys(node, {"op", "arg"})
        value, count = compile_operand(node["arg"], depth=depth + 1)
        nodes = count + 1
        if isinstance(value, RationalValue):
            return RationalValue(-value.value), nodes
        if isinstance(value, QBarValue):
            return QBarValue(-value.value), nodes
        if isinstance(value, PiMultiple):
            return PiMultiple(-value.coefficient), nodes
        if isinstance(value, PiAffine) and nodes <= MAX_AFFINE_NODES:
            return PiAffine(-value.coefficient, -value.offset, nodes), nodes
        raise FailClosed("nested angle/oversized affine negation is unsupported")
    if operation in ("add", "sub", "mul", "div"):
        _keys(node, {"op", "left", "right"})
        left, left_nodes = compile_operand(node["left"], depth=depth + 1)
        right, right_nodes = compile_operand(node["right"], depth=depth + 1)
        nodes = left_nodes + right_nodes + 1
        if operation == "add":
            return _add_sub(left, right, subtract=False, nodes=nodes), nodes
        if operation == "sub":
            return _add_sub(left, right, subtract=True, nodes=nodes), nodes
        if operation == "mul":
            return _multiply(left, right, nodes=nodes), nodes
        return _divide(left, right, nodes=nodes), nodes
    # pow, trig, nested comparisons, calls, variables with unknown types, and
    # every order/sign operator deliberately land here.
    raise FailClosed("unknown, nested, nonlinear, or non-equality source operation")


def typed_semantic_equal(left: TypedValue, right: TypedValue) -> bool:
    # The only mixed-type rule: Q has one canonical exact embedding in Qbar.
    # It exists at equality dispatch only and is never exposed to arithmetic,
    # ordering, signs, angles, or affine construction.
    if isinstance(left, QBarValue) and isinstance(right, RationalValue):
        embedded = sp.Rational(right.value.numerator, right.value.denominator)
        return _equal(left.value, embedded)
    if isinstance(left, RationalValue) and isinstance(right, QBarValue):
        embedded = sp.Rational(left.value.numerator, left.value.denominator)
        return _equal(embedded, right.value)
    if type(left) is not type(right):
        raise FailClosed("mixed typed equality is not coerced")
    if isinstance(left, RationalValue):
        return left.value == right.value
    if isinstance(left, QBarValue):
        return _equal(left.value, right.value)
    if isinstance(left, PiMultiple):
        return left.coefficient == right.coefficient
    if isinstance(left, PiAffine):
        return _equal(left.coefficient, right.coefficient) and _equal(left.offset, right.offset)
    if isinstance(left, AngleValue):
        if (left.unit, left.domain, left.direct_source_angle) != (right.unit, right.domain, right.direct_source_angle):
            raise FailClosed("mixed angle unit/domain/provenance")
        return _equal(left.cosine, right.cosine) and _equal(left.sine, right.sine)
    raise FailClosed("unknown typed equality")


def prove_direct_relation(relation: Mapping[str, Any], ledger: ReplayLedger) -> dict[str, Any]:
    if not ledger.ready():
        return {"status": "FALLBACK", "authority_pass": False, "reason": "incomplete replay ledger"}
    try:
        _keys(relation, {"op", "left", "right"})
        if relation["op"] != "equal":
            raise FailClosed("only a direct source equality is supported")
        left, _ = compile_operand(relation["left"])
        right, _ = compile_operand(relation["right"])
        equal = typed_semantic_equal(left, right)
    except FailClosed as error:
        return {"status": "FALLBACK", "authority_pass": False, "reason": str(error)}
    if not equal:
        return {"status": "PROVED_UNEQUAL", "authority_pass": False, "reason": "typed coefficients differ"}
    rational_embedding = (
        isinstance(left, QBarValue) and isinstance(right, RationalValue)
    ) or (
        isinstance(left, RationalValue) and isinstance(right, QBarValue)
    )
    return {
        "schema_version": SCHEMA,
        "status": "TYPED_SOURCE_EQUALITY_REPAIRED",
        "authority_pass": True,
        "ledger_sha256": ledger.digest(),
        "closed_dispatch_type": (
            "CANONICAL_RATIONAL_INTO_QBAR_EQUALITY"
            if rational_embedding
            else type(left).__name__
        ),
        "qbar_pi_affine_coefficientwise": isinstance(left, PiAffine),
        "canonical_rational_into_qbar_embedding": rational_embedding,
        "order_sign_or_coercive_broadening": False,
    }


def repair_or_current_exact_fallback(
    current_exact_bytes: bytes,
    *,
    relation: Mapping[str, Any],
    ledger: ReplayLedger,
) -> bytes:
    result = prove_direct_relation(relation, ledger)
    if result.get("authority_pass") is not True:
        return current_exact_bytes
    return _canonical_json(result) + b"\n"
