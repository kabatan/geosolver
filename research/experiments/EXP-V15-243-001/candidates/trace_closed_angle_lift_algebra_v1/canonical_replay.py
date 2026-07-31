"""Independent exact replay of the original unsigned Angle relation.

This module intentionally does not inspect a lifted product polynomial.  It
re-evaluates each original vector DAG, its orientation/range obligations, and
the source relation with canonical principal ``atan2`` semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import sympy as sp

from candidate import AngleAtom, AngleRelation, LiftFailure


@dataclass(frozen=True)
class ReplayResult:
    generated_replay_pass: bool
    reason: str
    source_residual: sp.Expr | None
    formal_authority_pass: bool = False
    target_release: bool = False


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
    raise LiftFailure("CANONICAL_REPLAY_EXACT_SIGN_UNDECIDED")


def _in_range(theta: sp.Expr, atom: AngleAtom) -> bool:
    lower_delta = sp.simplify(theta - sp.Rational(atom.lower_pi.numerator, atom.lower_pi.denominator) * sp.pi)
    upper_delta = sp.simplify(sp.Rational(atom.upper_pi.numerator, atom.upper_pi.denominator) * sp.pi - theta)
    lower_sign, upper_sign = _sign(lower_delta), _sign(upper_delta)
    return (
        (lower_sign > 0 if atom.lower_open else lower_sign >= 0)
        and (upper_sign > 0 if atom.upper_open else upper_sign >= 0)
    )


def _canonical_angle(
    atom: AngleAtom, substitutions: Mapping[sp.Symbol, sp.Expr]
) -> sp.Expr:
    dot = sp.simplify(atom.dot.subs(substitutions))
    oriented_cross = sp.simplify(atom.oriented_cross.subs(substitutions))
    if _sign(oriented_cross) <= 0:
        raise LiftFailure("CANONICAL_ANGLE_ORIENTATION_UNDEFINED_OR_WRONG")
    # With the source-proved orientation, oriented_cross is exactly abs(cross),
    # so atan2 returns the untouched unsigned Angle in its principal [0, pi] range.
    theta = sp.simplify(sp.atan2(oriented_cross, dot))
    if not _in_range(theta, atom):
        raise LiftFailure("CANONICAL_ANGLE_PRINCIPAL_RANGE_FAILED")
    return theta


def replay_original_relation(
    relation: AngleRelation, assignment: Mapping[sp.Symbol, object]
) -> ReplayResult:
    substitutions = {symbol: sp.sympify(value) for symbol, value in assignment.items()}
    try:
        residual = -sp.Rational(
            relation.pi_coefficient.numerator,
            relation.pi_coefficient.denominator,
        ) * sp.pi
        for term in relation.terms:
            coefficient = sp.Rational(
                term.coefficient.numerator, term.coefficient.denominator
            )
            residual += coefficient * _canonical_angle(term.atom, substitutions)
        residual = sp.simplify(sp.trigsimp(residual))
        if not _zero(residual):
            return ReplayResult(False, "ORIGINAL_ANGLE_RELATION_NONZERO", residual)
    except LiftFailure as error:
        return ReplayResult(False, str(error), None)
    return ReplayResult(True, "GENERATED_CANONICAL_REPLAY_ONLY", sp.Integer(0))
