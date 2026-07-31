"""Fail-closed projective-complex lift for rational linear Angle relations.

This disposable D0 kernel is deliberately smaller than a source compiler.  It
accepts already typed direct ``Angle(u, v)`` atoms and constructs only an exact
proposal cover.  The cover is never authority: orientation, principal range,
winding, and the original Angle relation must all survive a separate replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from typing import Mapping

import sympy as sp


SCHEMA = "geotarget.trace-closed-angle-lift-algebra/v1"
MAX_ANGLE_ATOMS = 8
MAX_COEFFICIENT_DENOMINATOR = 24
MAX_COEFFICIENT_NUMERATOR_BITS = 64
MAX_DENOMINATOR_LCM = 10_000
MAX_ABS_EXPONENT = 12
MAX_TOTAL_EXPONENT = 24
MAX_ABS_TARGET_INTEGER = 64
MAX_COMPILED_OPERATIONS = 2_000
MAX_COMPILED_TEXT = 32_768


class LiftFailure(ValueError):
    """The relation is not proved safe for this proposal lane."""


def _fraction(value: object) -> Fraction:
    if isinstance(value, (bool, float)):
        raise LiftFailure("COEFFICIENT_TYPE_FORBIDDEN")
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int) and not isinstance(value, bool):
        result = Fraction(value)
    elif isinstance(value, sp.Rational):
        result = Fraction(int(value.p), int(value.q))
    elif isinstance(value, str):
        try:
            result = Fraction(value)
        except (ValueError, ZeroDivisionError) as error:
            raise LiftFailure("COEFFICIENT_IS_NOT_EXACT_RATIONAL") from error
    else:
        raise LiftFailure("COEFFICIENT_TYPE_FORBIDDEN")
    if result.denominator > MAX_COEFFICIENT_DENOMINATOR:
        raise LiftFailure("COEFFICIENT_DENOMINATOR_CAP")
    if abs(result.numerator).bit_length() > MAX_COEFFICIENT_NUMERATOR_BITS:
        raise LiftFailure("COEFFICIENT_NUMERATOR_BIT_CAP")
    return result


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _expr_text(value: object) -> str:
    return sp.srepr(sp.sympify(value))


def _zero(value: object) -> bool:
    expression = sp.simplify(sp.sympify(value))
    return expression == 0 or expression.is_zero is True


def _sign(value: object) -> int:
    expression = sp.simplify(sp.sympify(value))
    if _zero(expression):
        return 0
    if expression.is_positive is True or sp.ask(sp.Q.positive(expression)) is True:
        return 1
    if expression.is_negative is True or sp.ask(sp.Q.negative(expression)) is True:
        return -1
    raise LiftFailure("EXACT_SIGN_UNDECIDED")


@dataclass(frozen=True)
class AngleAtom:
    """One typed direct source Angle and its source-proved sheet facts.

    ``canonical_dag`` is an opaque digest/key supplied by the typed source
    frontend.  It must identify the untouched Angle DAG, not a case name.
    Ranges are rational multiples of pi.
    """

    canonical_dag: str
    u: tuple[sp.Expr, sp.Expr]
    v: tuple[sp.Expr, sp.Expr]
    orientation: int
    lower_pi: Fraction = Fraction(0)
    upper_pi: Fraction = Fraction(1)
    lower_open: bool = True
    upper_open: bool = True

    def __post_init__(self) -> None:
        if not self.canonical_dag or len(self.canonical_dag) > 256:
            raise LiftFailure("ANGLE_DAG_KEY_MALFORMED")
        if len(self.u) != 2 or len(self.v) != 2:
            raise LiftFailure("ANGLE_VECTOR_DIMENSION_UNSUPPORTED")
        if self.orientation not in (-1, 1):
            raise LiftFailure("ANGLE_ORIENTATION_NOT_SOURCE_PROVED")
        lower, upper = _fraction(self.lower_pi), _fraction(self.upper_pi)
        if lower < 0 or upper > 1 or lower > upper:
            raise LiftFailure("PRINCIPAL_RANGE_OUTSIDE_UNSIGNED_ANGLE")
        if lower == upper and (self.lower_open or self.upper_open):
            raise LiftFailure("PRINCIPAL_RANGE_EMPTY")
        object.__setattr__(self, "u", tuple(sp.sympify(item) for item in self.u))
        object.__setattr__(self, "v", tuple(sp.sympify(item) for item in self.v))
        object.__setattr__(self, "lower_pi", lower)
        object.__setattr__(self, "upper_pi", upper)

    @property
    def dot(self) -> sp.Expr:
        return sp.expand(self.u[0] * self.v[0] + self.u[1] * self.v[1])

    @property
    def oriented_cross(self) -> sp.Expr:
        cross = self.u[0] * self.v[1] - self.u[1] * self.v[0]
        return sp.expand(self.orientation * cross)

    def payload(self) -> dict[str, object]:
        return {
            "canonical_dag": self.canonical_dag,
            "u": [_expr_text(item) for item in self.u],
            "v": [_expr_text(item) for item in self.v],
            "orientation": self.orientation,
            "range_pi": [
                str(self.lower_pi),
                str(self.upper_pi),
                self.lower_open,
                self.upper_open,
            ],
        }


@dataclass(frozen=True)
class AngleTerm:
    atom: AngleAtom
    coefficient: Fraction

    def __post_init__(self) -> None:
        object.__setattr__(self, "coefficient", _fraction(self.coefficient))


@dataclass(frozen=True)
class AngleRelation:
    """The untouched source assertion sum(q_i * Angle_i) = q_pi * pi."""

    terms: tuple[AngleTerm, ...]
    pi_coefficient: Fraction

    def __post_init__(self) -> None:
        object.__setattr__(self, "terms", tuple(self.terms))
        object.__setattr__(self, "pi_coefficient", _fraction(self.pi_coefficient))
        if not self.terms:
            raise LiftFailure("ANGLE_RELATION_EMPTY")


@dataclass(frozen=True)
class OrientationLedgerEntry:
    canonical_dag: str
    required_sign: int
    expression: sp.Expr


@dataclass(frozen=True)
class PrincipalRangeLedgerEntry:
    canonical_dag: str
    lower_pi: Fraction
    upper_pi: Fraction
    lower_open: bool
    upper_open: bool


@dataclass(frozen=True)
class WindingLedger:
    lower_pi: Fraction
    upper_pi: Fraction
    lower_open: bool
    upper_open: bool
    target_integer: int
    admissible_windings: tuple[int, ...]


@dataclass(frozen=True)
class PhaseCover:
    atoms: tuple[AngleAtom, ...]
    exponents: tuple[int, ...]
    target_integer: int
    real_polynomial: sp.Expr
    imaginary_polynomial: sp.Expr
    sign_polynomial: sp.Expr
    source_relation_sha256: str
    algebraic_cover_sha256: str
    authority_pass: bool = False
    target_release: bool = False


@dataclass(frozen=True)
class ExactAngleProposal:
    cover: PhaseCover
    orientation_ledger: tuple[OrientationLedgerEntry, ...]
    principal_range_ledger: tuple[PrincipalRangeLedgerEntry, ...]
    winding_ledger: WindingLedger
    status: str = "PROPOSAL_READY_REPLAY_REQUIRED"
    authority_pass: bool = False
    target_release: bool = False


@dataclass(frozen=True)
class ProposalCheck:
    passed: bool
    reason: str
    authority_pass: bool = False
    target_release: bool = False


def _normalized_terms(
    relation: AngleRelation,
) -> tuple[tuple[AngleAtom, Fraction], ...]:
    atoms: dict[str, AngleAtom] = {}
    coefficients: dict[str, Fraction] = {}
    for term in relation.terms:
        key = term.atom.canonical_dag
        previous = atoms.get(key)
        if previous is not None and previous.payload() != term.atom.payload():
            raise LiftFailure("ANGLE_DAG_KEY_COLLISION")
        atoms[key] = term.atom
        coefficients[key] = coefficients.get(key, Fraction(0)) + term.coefficient
    normalized = tuple(
        (atoms[key], coefficients[key])
        for key in sorted(atoms)
        if coefficients[key] != 0
    )
    if not normalized:
        raise LiftFailure("ANGLE_RELATION_CANCELS_IDENTICALLY")
    if len(normalized) > MAX_ANGLE_ATOMS:
        raise LiftFailure("ANGLE_ATOM_CAP")
    return normalized


def is_legacy_sector3_shape(relation: AngleRelation) -> bool:
    """Conservatively exclude the normalized old Sector-3 relation family.

    That older closed shape is ``a*Angle_1 = b*Angle_2`` with one direct
    Angle on each side and positive integer a,b in 1..3.  It has no pi term,
    offset, sum, difference within a side, fractional coefficient, or nested
    scale.  A real syntax census must still call the frozen scanner on the
    original DAG because normalization can over-exclude canceled syntax.
    """

    if relation.pi_coefficient != 0:
        return False
    try:
        normalized = _normalized_terms(relation)
    except LiftFailure:
        return False
    if len(normalized) != 2:
        return False
    values = [coefficient for _atom, coefficient in normalized]
    return (
        values[0] * values[1] < 0
        and all(value.denominator == 1 for value in values)
        and all(1 <= abs(value.numerator) <= 3 for value in values)
    )


def _denominator_clear(
    relation: AngleRelation,
) -> tuple[tuple[tuple[AngleAtom, int], ...], int]:
    normalized = _normalized_terms(relation)
    denominator = math.lcm(
        relation.pi_coefficient.denominator,
        *(coefficient.denominator for _atom, coefficient in normalized),
    )
    if denominator > MAX_DENOMINATOR_LCM:
        raise LiftFailure("DENOMINATOR_LCM_CAP")
    exponents = tuple(
        (atom, int(coefficient * denominator)) for atom, coefficient in normalized
    )
    target = int(relation.pi_coefficient * denominator)
    if abs(target) > MAX_ABS_TARGET_INTEGER:
        raise LiftFailure("ABS_TARGET_INTEGER_CAP")
    if any(abs(exponent) > MAX_ABS_EXPONENT for _atom, exponent in exponents):
        raise LiftFailure("ABS_EXPONENT_CAP")
    if sum(abs(exponent) for _atom, exponent in exponents) > MAX_TOTAL_EXPONENT:
        raise LiftFailure("TOTAL_EXPONENT_CAP")
    return exponents, target


def _pair_multiply(
    left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]
) -> tuple[sp.Expr, sp.Expr]:
    a, b = left
    c, d = right
    return sp.expand(a * c - b * d), sp.expand(a * d + b * c)


def _pair_power(pair: tuple[sp.Expr, sp.Expr], exponent: int) -> tuple[sp.Expr, sp.Expr]:
    if exponent < 0:
        pair = (pair[0], -pair[1])
        exponent = -exponent
    result = (sp.Integer(1), sp.Integer(0))
    base = pair
    while exponent:
        if exponent & 1:
            result = _pair_multiply(result, base)
        exponent >>= 1
        if exponent:
            base = _pair_multiply(base, base)
    return result


def _audit_expression(expression: sp.Expr) -> None:
    if len(str(expression)) > MAX_COMPILED_TEXT:
        raise LiftFailure("COMPILED_TEXT_CAP")
    if int(sp.count_ops(expression, visual=False)) > MAX_COMPILED_OPERATIONS:
        raise LiftFailure("COMPILED_OPERATION_CAP")


def build_phase_cover(relation: AngleRelation) -> PhaseCover:
    """Build the modulo-2pi algebraic cover; this object is never authority."""

    if is_legacy_sector3_shape(relation):
        raise LiftFailure("LEGACY_SECTOR3_SHAPE_EXCLUDED")
    cleared, target = _denominator_clear(relation)
    real, imaginary = sp.Integer(1), sp.Integer(0)
    for atom, exponent in cleared:
        real, imaginary = _pair_multiply(
            (real, imaginary),
            _pair_power((atom.dot, atom.oriented_cross), exponent),
        )
    sign = sp.expand(real if target % 2 == 0 else -real)
    real, imaginary = sp.expand(real), sp.expand(imaginary)
    for expression in (real, imaginary, sign):
        _audit_expression(expression)
    relation_payload = {
        "schema": SCHEMA,
        "terms": [
            {"atom": atom.payload(), "exponent": exponent}
            for atom, exponent in cleared
        ],
        "target_integer": target,
    }
    cover_payload = {
        "real": _expr_text(real),
        "imaginary": _expr_text(imaginary),
        "sign": _expr_text(sign),
        "target_integer": target,
    }
    return PhaseCover(
        atoms=tuple(atom for atom, _exponent in cleared),
        exponents=tuple(exponent for _atom, exponent in cleared),
        target_integer=target,
        real_polynomial=real,
        imaginary_polynomial=imaginary,
        sign_polynomial=sign,
        source_relation_sha256=_sha256(relation_payload),
        algebraic_cover_sha256=_sha256(cover_payload),
    )


def _winding_ledger(cover: PhaseCover) -> WindingLedger:
    lower = Fraction(0)
    upper = Fraction(0)
    lower_open = False
    upper_open = False
    for atom, exponent in zip(cover.atoms, cover.exponents, strict=True):
        if exponent >= 0:
            lower += exponent * atom.lower_pi
            upper += exponent * atom.upper_pi
            if exponent:
                lower_open = lower_open or atom.lower_open
                upper_open = upper_open or atom.upper_open
        else:
            lower += exponent * atom.upper_pi
            upper += exponent * atom.lower_pi
            lower_open = lower_open or atom.upper_open
            upper_open = upper_open or atom.lower_open
    lower_winding = (lower - cover.target_integer) / 2
    upper_winding = (upper - cover.target_integer) / 2
    first = (
        math.floor(lower_winding) + 1
        if lower_open
        else math.ceil(lower_winding)
    )
    last = (
        math.ceil(upper_winding) - 1
        if upper_open
        else math.floor(upper_winding)
    )
    admissible = tuple(range(first, last + 1)) if first <= last else ()
    return WindingLedger(
        lower_pi=lower,
        upper_pi=upper,
        lower_open=lower_open,
        upper_open=upper_open,
        target_integer=cover.target_integer,
        admissible_windings=admissible,
    )


def compile_relation(relation: AngleRelation) -> ExactAngleProposal:
    cover = build_phase_cover(relation)
    winding = _winding_ledger(cover)
    if winding.admissible_windings != (0,):
        raise LiftFailure(
            "NONZERO_OR_AMBIGUOUS_WINDING:" + repr(winding.admissible_windings)
        )
    orientations = tuple(
        OrientationLedgerEntry(atom.canonical_dag, 1, atom.oriented_cross)
        for atom in cover.atoms
    )
    ranges = tuple(
        PrincipalRangeLedgerEntry(
            atom.canonical_dag,
            atom.lower_pi,
            atom.upper_pi,
            atom.lower_open,
            atom.upper_open,
        )
        for atom in cover.atoms
    )
    return ExactAngleProposal(cover, orientations, ranges, winding)


def check_exact_proposal(
    proposal: ExactAngleProposal, assignment: Mapping[sp.Symbol, object]
) -> ProposalCheck:
    """Check proposal equations and ledgers exactly, without granting authority."""

    substitutions = {symbol: sp.sympify(value) for symbol, value in assignment.items()}
    try:
        for atom, orientation, principal_range in zip(
            proposal.cover.atoms,
            proposal.orientation_ledger,
            proposal.principal_range_ledger,
            strict=True,
        ):
            if atom.canonical_dag != orientation.canonical_dag or atom.canonical_dag != principal_range.canonical_dag:
                return ProposalCheck(False, "LEDGER_ATOM_BINDING_MISMATCH")
            entry = orientation
            if _sign(entry.expression.subs(substitutions)) != entry.required_sign:
                return ProposalCheck(False, "ORIENTATION_UNDEFINED_OR_WRONG_SHEET")
            theta = sp.simplify(
                sp.atan2(
                    atom.oriented_cross.subs(substitutions),
                    atom.dot.subs(substitutions),
                )
            )
            lower = sp.Rational(
                principal_range.lower_pi.numerator,
                principal_range.lower_pi.denominator,
            ) * sp.pi
            upper = sp.Rational(
                principal_range.upper_pi.numerator,
                principal_range.upper_pi.denominator,
            ) * sp.pi
            lower_sign = _sign(theta - lower)
            upper_sign = _sign(upper - theta)
            if not (
                (lower_sign > 0 if principal_range.lower_open else lower_sign >= 0)
                and (upper_sign > 0 if principal_range.upper_open else upper_sign >= 0)
            ):
                return ProposalCheck(False, "PRINCIPAL_RANGE_LEDGER_FAILED")
        imaginary = proposal.cover.imaginary_polynomial.subs(substitutions)
        if not _zero(imaginary):
            return ProposalCheck(False, "PROJECTIVE_PRODUCT_NOT_REAL")
        if _sign(proposal.cover.sign_polynomial.subs(substitutions)) <= 0:
            return ProposalCheck(False, "PROJECTIVE_PRODUCT_WRONG_PI_PARITY")
    except LiftFailure as error:
        return ProposalCheck(False, str(error))
    return ProposalCheck(True, "EXACT_PROPOSAL_ONLY_REPLAY_REQUIRED")


def prejoin_or_baseline(
    relation: AngleRelation,
    assignment: Mapping[sp.Symbol, object],
    untouched_baseline: object,
) -> object:
    """The D0 kernel cannot replace the baseline or emit a target."""

    try:
        proposal = compile_relation(relation)
        if not check_exact_proposal(proposal, assignment).passed:
            return untouched_baseline
    except Exception:
        return untouched_baseline
    return untouched_baseline
