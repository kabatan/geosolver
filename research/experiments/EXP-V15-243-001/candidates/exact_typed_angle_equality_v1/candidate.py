"""Disposable exact fallback for direct, same-typed ``Angle = Angle``.

This deliberately does not compile general expressions.  It repairs one QQBar
failure mode: scalar subtraction of two principal angles invents full-turn
lifts even though the typed angle domains are injective.  Equality is instead
proved from an exact normalized dot/cross pair, without square roots.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable, Literal

import sympy as sp


POINT_DOMAIN = "POINT_UNSIGNED_RADIAN_[0,PI]"
LINE_DOMAIN = "LINE_ACUTE_RADIAN_[0,PI/2]"
DIRECT_RELATION = "DIRECT_TYPED_ANGLE_EQUALITY"
AMBIGUOUS_FAILURE = "angle equality has ambiguous full-turn lift"


class FailClosed(ValueError):
    """The exact preconditions were not proved; keep the original fallback."""


def _sym(value: Any) -> sp.Expr:
    # Parsing belongs to canonical replay.  This candidate accepts exact values,
    # not expression strings from an untrusted source.
    if isinstance(value, (str, bytes, bool)):
        raise FailClosed("coordinate must already be an exact algebraic value")
    out = sp.sympify(value)
    if out.has(sp.Float):
        raise FailClosed("approximate floating coordinate is not exact replay")
    algebraic = out.is_algebraic
    if algebraic is not True:
        raise FailClosed("coordinate is not proved exact algebraic")
    return out


def _zero(value: sp.Expr) -> bool:
    value = sp.cancel(sp.expand(value))
    if value == 0 or value.is_zero is True:
        return True
    if value.is_zero is False:
        return False
    equal = value.equals(0)
    if equal is True:
        return True
    if equal is False:
        return False
    raise FailClosed("algebraic equality is undecidable in the prototype")


def _sign(value: sp.Expr) -> int:
    value = sp.cancel(sp.expand(value))
    if _zero(value):
        return 0
    if value.is_positive is True:
        return 1
    if value.is_negative is True:
        return -1
    positive = sp.ask(sp.Q.positive(value))
    negative = sp.ask(sp.Q.negative(value))
    if positive is True:
        return 1
    if negative is True:
        return -1
    raise FailClosed("algebraic sign is undecidable in the prototype")


@dataclass(frozen=True)
class ExactPoint:
    x: sp.Expr
    y: sp.Expr

    @classmethod
    def of(cls, x: Any, y: Any) -> "ExactPoint":
        return cls(_sym(x), _sym(y))


@dataclass(frozen=True)
class ExactLine:
    # ax + by + c = 0.  Orientation is intentionally not semantic.
    a: sp.Expr
    b: sp.Expr
    c: sp.Expr

    @classmethod
    def of(cls, a: Any, b: Any, c: Any = 0) -> "ExactLine":
        return cls(_sym(a), _sym(b), _sym(c))


@dataclass(frozen=True)
class TypedAngle:
    kind: Literal["point_unsigned", "line_acute", "oriented", "full_circle"]
    args: tuple[Any, ...]
    unit: str
    domain: str

    @classmethod
    def point(
        cls,
        first: ExactPoint,
        vertex: ExactPoint,
        third: ExactPoint,
        *,
        unit: str = "radian",
        domain: str = POINT_DOMAIN,
    ) -> "TypedAngle":
        return cls("point_unsigned", (first, vertex, third), unit, domain)

    @classmethod
    def line(
        cls,
        first: ExactLine,
        second: ExactLine,
        *,
        unit: str = "radian",
        domain: str = LINE_DOMAIN,
    ) -> "TypedAngle":
        return cls("line_acute", (first, second), unit, domain)


@dataclass(frozen=True)
class ReplayLedger:
    """All non-angle authority obligations supplied by canonical replay."""

    relation_shape: str = DIRECT_RELATION
    source_equations_exact: bool = True
    typed_guards_exact: bool = True
    definedness_exact: bool = True
    branch_selector_phase_exact: bool = True
    raw_target_exact: bool = True
    descriptor_polynomial_exact: bool = True
    square_free_minpoly_exact: bool = True
    root_ordinal_exact: bool = True
    isolator_exact: bool = True
    original_failure_solely_angle_lift: bool = True
    qreflect_used: bool = False

    def authority_ready(self) -> bool:
        values = asdict(self)
        return (
            values.pop("relation_shape") == DIRECT_RELATION
            and values.pop("qreflect_used") is False
            and all(value is True for value in values.values())
        )

    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class PairCertificate:
    kind: str
    dot_sign_left: int | None
    dot_sign_right: int | None
    dot_square_identity: str
    cross_square_identity: str
    nonzero_norms: bool


@dataclass(frozen=True)
class RelationResult:
    equal: bool
    authority_pass: bool
    status: str
    reason: str
    certificate: PairCertificate | None
    replay_digest: str


def _sub(left: ExactPoint, right: ExactPoint) -> tuple[sp.Expr, sp.Expr]:
    return left.x - right.x, left.y - right.y


def _dot(left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]) -> sp.Expr:
    return left[0] * right[0] + left[1] * right[1]


def _cross(left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]) -> sp.Expr:
    return left[0] * right[1] - left[1] * right[0]


def _measure(angle: TypedAngle) -> tuple[sp.Expr, sp.Expr, sp.Expr, int | None]:
    """Return dot, cross, product of squared norms, semantic dot sign."""
    if angle.kind == "point_unsigned":
        if angle.domain != POINT_DOMAIN or angle.unit != "radian" or len(angle.args) != 3:
            raise FailClosed("point Angle has unknown unit/domain/arity")
        first, vertex, third = angle.args
        if not all(isinstance(item, ExactPoint) for item in angle.args):
            raise FailClosed("point Angle has non-point arguments")
        u = _sub(first, vertex)
        v = _sub(third, vertex)
        n1 = _dot(u, u)
        n2 = _dot(v, v)
        if _sign(n1) != 1 or _sign(n2) != 1:
            raise FailClosed("point Angle has a zero/invalid ray")
        dot = _dot(u, v)
        cross = _cross(u, v)
        return dot, cross, n1 * n2, _sign(dot)

    if angle.kind == "line_acute":
        if angle.domain != LINE_DOMAIN or angle.unit != "radian" or len(angle.args) != 2:
            raise FailClosed("line Angle has unknown unit/domain/arity")
        first, second = angle.args
        if not all(isinstance(item, ExactLine) for item in angle.args):
            raise FailClosed("line Angle has non-line arguments")
        # Direction vectors (-b, a); offsets are irrelevant.
        u = (-first.b, first.a)
        v = (-second.b, second.a)
        n1 = _dot(u, u)
        n2 = _dot(v, v)
        if _sign(n1) != 1 or _sign(n2) != 1:
            raise FailClosed("line Angle has a zero normal")
        return _dot(u, v), _cross(u, v), n1 * n2, None

    raise FailClosed("oriented/full-circle Angle is unsupported by this DSL")


def prove_typed_angle_equality(
    left: TypedAngle,
    right: TypedAngle,
    ledger: ReplayLedger,
) -> RelationResult:
    """Prove equality in the typed principal domain, or fail closed."""
    digest = ledger.digest()
    if not ledger.authority_ready():
        return RelationResult(False, False, "FALLBACK", "incomplete canonical replay", None, digest)
    if (left.kind, left.unit, left.domain) != (right.kind, right.unit, right.domain):
        return RelationResult(False, False, "FALLBACK", "mixed Angle type/unit/domain", None, digest)

    try:
        d1, c1, q1, s1 = _measure(left)
        d2, c2, q2, s2 = _measure(right)
        dot_identity = _zero(d1 * d1 * q2 - d2 * d2 * q1)
        cross_identity = _zero(c1 * c1 * q2 - c2 * c2 * q1)
        # Point Angle spans [0,pi], so cosine sign distinguishes supplementary
        # angles.  Line Angle is acute and uses |dot|, so signs are immaterial.
        sign_identity = left.kind == "line_acute" or s1 == s2
        equal = dot_identity and cross_identity and sign_identity
        cert = PairCertificate(
            kind=left.kind,
            dot_sign_left=s1,
            dot_sign_right=s2,
            dot_square_identity=str(sp.factor(d1 * d1 * q2 - d2 * d2 * q1)),
            cross_square_identity=str(sp.factor(c1 * c1 * q2 - c2 * c2 * q1)),
            nonzero_norms=True,
        )
    except FailClosed as exc:
        return RelationResult(False, False, "FALLBACK", str(exc), None, digest)

    if not equal:
        return RelationResult(False, False, "PROVED_UNEQUAL", "normalized exact pair differs", cert, digest)
    return RelationResult(True, True, "PROVED_EQUAL", "same typed normalized exact pair", cert, digest)


def repair_ambiguous_full_turn(
    original: dict[str, Any],
    left: TypedAngle,
    right: TypedAngle,
    ledger: ReplayLedger,
) -> dict[str, Any]:
    """Candidate-private splice; never changes any non-matching fallback."""
    if original.get("failure") != AMBIGUOUS_FAILURE:
        return {**original, "candidate_activation": False}
    result = prove_typed_angle_equality(left, right, ledger)
    if not result.authority_pass:
        return {
            **original,
            "candidate_activation": True,
            "candidate_status": result.status,
            "candidate_reason": result.reason,
            "authority_pass": False,
        }
    return {
        "status": "EXACT_TYPED_ANGLE_EQUALITY_REPAIRED",
        "candidate_activation": True,
        "authority_pass": True,
        "replay_digest": result.replay_digest,
        "certificate": asdict(result.certificate) if result.certificate else None,
    }


def classify_source_relation(node: dict[str, Any]) -> bool:
    """Static, source-only activation predicate; it evaluates no coordinates."""
    if node.get("op") != "Equal" or set(node) - {"op", "left", "right"}:
        return False
    left = node.get("left")
    right = node.get("right")
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    allowed = {"op", "args", "unit", "domain"}
    if set(left) - allowed or set(right) - allowed:
        return False
    if left.get("op") != "Angle" or right.get("op") != "Angle":
        return False
    if left.get("unit") != "radian" or right.get("unit") != "radian":
        return False
    la = left.get("args")
    ra = right.get("args")
    if not isinstance(la, list) or not isinstance(ra, list) or len(la) != len(ra):
        return False
    expected = {3: POINT_DOMAIN, 2: LINE_DOMAIN}.get(len(la))
    return expected is not None and left.get("domain") == right.get("domain") == expected


def exact_point(values: Iterable[Any]) -> ExactPoint:
    x, y = tuple(values)
    return ExactPoint.of(x, y)


def exact_line(values: Iterable[Any]) -> ExactLine:
    values = tuple(values)
    if len(values) == 2:
        values = (*values, 0)
    a, b, c = values
    return ExactLine.of(a, b, c)
