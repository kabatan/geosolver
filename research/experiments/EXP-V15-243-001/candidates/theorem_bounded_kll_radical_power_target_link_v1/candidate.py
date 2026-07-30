"""Disposable synthetic prototype for bounded KLL radical-power target links."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

import sympy as sp


T = sp.Symbol("T")
MAX_DEGREE = 4
MAX_HEIGHT = 2**20
KLL_BITS = 256
RADICAL_POWER = 2


@dataclass(frozen=True)
class RegularRootBox:
    variables: tuple[sp.Symbol, ...]
    equations: tuple[sp.Expr, ...]
    guards: tuple[sp.Relational, ...]
    witness: Mapping[sp.Symbol, sp.Expr]
    intervals: Mapping[sp.Symbol, tuple[sp.Rational, sp.Rational]]
    complete: bool = True


@dataclass(frozen=True)
class Proposal:
    polynomial: sp.Expr
    target_expression: sp.Expr
    generators: tuple[sp.Expr, ...]
    cofactors: tuple[sp.Expr, ...]
    link_power: int
    target_interval: tuple[sp.Rational, sp.Rational]
    identity_omitted_from_proposal: bool = False


@dataclass(frozen=True)
class Source:
    root_box: RegularRootBox
    proposal: Proposal


@dataclass(frozen=True)
class Result:
    emitted: bool
    status: str
    descriptor: tuple[tuple[int, ...], int] | None
    kll_calls: int
    kll_bits: int
    used_radical_power: bool


def _zero(expression: sp.Expr) -> bool:
    value = sp.factor(sp.cancel(sp.together(expression)))
    return value == 0 or value.is_zero is True or value.equals(0) is True


def _relation_true(relation) -> bool:
    simplified = sp.simplify(relation)
    return simplified is sp.true


def _primitive_coefficients(polynomial: sp.Poly) -> tuple[int, ...]:
    denominator = sp.ilcm(*(coefficient.q for coefficient in polynomial.all_coeffs()))
    coefficients = tuple(int(coefficient * denominator) for coefficient in polynomial.all_coeffs())
    common = math.gcd(*(abs(coefficient) for coefficient in coefficients if coefficient))
    coefficients = tuple(coefficient // common for coefficient in coefficients)
    if coefficients[0] < 0:
        coefficients = tuple(-coefficient for coefficient in coefficients)
    return coefficients


def _regular_box_valid(box: RegularRootBox) -> bool:
    if not box.complete or len(box.equations) != len(box.variables):
        return False
    if set(box.witness) != set(box.variables) or set(box.intervals) != set(box.variables):
        return False
    if any(not _zero(equation.subs(box.witness)) for equation in box.equations):
        return False
    if any(not _relation_true(guard.subs(box.witness)) for guard in box.guards):
        return False
    for variable in box.variables:
        lower, upper = box.intervals[variable]
        value = box.witness[variable]
        if not _relation_true(sp.StrictGreaterThan(value, lower)):
            return False
        if not _relation_true(sp.StrictLessThan(value, upper)):
            return False
    jacobian = sp.Matrix(box.equations).jacobian(box.variables)
    return not _zero(jacobian.det().subs(box.witness))


def _bounded_irreducible_polynomial(expression: sp.Expr) -> tuple[sp.Poly, tuple[int, ...]] | None:
    try:
        polynomial = sp.Poly(expression, T, domain=sp.QQ)
    except Exception:
        return None
    if not 1 <= polynomial.degree() <= MAX_DEGREE:
        return None
    coefficients = _primitive_coefficients(polynomial)
    if max(abs(coefficient) for coefficient in coefficients) > MAX_HEIGHT:
        return None
    if not polynomial.is_irreducible:
        return None
    if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
        return None
    return polynomial, coefficients


def _single_root_ordinal(polynomial: sp.Poly, interval) -> int | None:
    lower, upper = interval
    if lower >= upper or polynomial.count_roots(lower, upper) != 1:
        return None
    isolators = polynomial.intervals(eps=sp.Rational(1, 10**30))
    ordinal = 0
    selected = 0
    for (left, right), multiplicity in isolators:
        if right <= lower:
            ordinal += multiplicity
        elif left >= upper:
            continue
        elif lower <= left and right <= upper:
            selected += multiplicity
        else:
            return None
    return ordinal if selected == 1 else None


def _kll_one_proposal(source: Source) -> Proposal:
    # Synthetic D0 stub: one frozen 256-bit KLL proposal is supplied by the
    # caller. It is evidence generation only; none of its claims are trusted.
    return source.proposal


def solve(source: Source, *, allow_radical_power: bool = True) -> Result:
    proposal = _kll_one_proposal(source)
    if not _regular_box_valid(source.root_box):
        return Result(False, "INVALID_ROOT_BOX", None, 1, KLL_BITS, False)
    bounded = _bounded_irreducible_polynomial(proposal.polynomial)
    if bounded is None:
        return Result(False, "INVALID_POLYNOMIAL", None, 1, KLL_BITS, False)
    polynomial, coefficients = bounded
    if len(proposal.generators) != len(proposal.cofactors):
        return Result(False, "MALFORMED_COFACTORS", None, 1, KLL_BITS, False)
    if proposal.link_power not in ((1, RADICAL_POWER) if allow_radical_power else (1,)):
        return Result(False, "UNSUPPORTED_LINK_POWER", None, 1, KLL_BITS, False)

    h = proposal.target_expression
    relation = sp.expand(polynomial.as_expr().subs(T, h))
    left = sp.expand(relation ** proposal.link_power)
    right = sp.expand(sum(
        cofactor * generator
        for cofactor, generator in zip(proposal.cofactors, proposal.generators, strict=True)
    ))
    if not _zero(left - right):
        return Result(False, "COFACTOR_IDENTITY_FAILED", None, 1, KLL_BITS, False)
    witness = source.root_box.witness
    if any(not _zero(generator.subs(witness)) for generator in proposal.generators):
        return Result(False, "GENERATOR_NOT_LINKED_TO_R", None, 1, KLL_BITS, False)
    target_value = sp.simplify(h.subs(witness))
    if not _zero(polynomial.as_expr().subs(T, target_value)):
        return Result(False, "TARGET_NOT_ROOT", None, 1, KLL_BITS, False)
    lower, upper = proposal.target_interval
    if not _relation_true(sp.StrictGreaterThan(target_value, lower)):
        return Result(False, "TARGET_OUTSIDE_INTERVAL", None, 1, KLL_BITS, False)
    if not _relation_true(sp.StrictLessThan(target_value, upper)):
        return Result(False, "TARGET_OUTSIDE_INTERVAL", None, 1, KLL_BITS, False)
    ordinal = _single_root_ordinal(polynomial, proposal.target_interval)
    if ordinal is None:
        return Result(False, "INTERVAL_NOT_SINGLE_ROOT", None, 1, KLL_BITS, False)
    return Result(
        True,
        "EXACT_TARGET_LINK",
        (coefficients, ordinal),
        1,
        KLL_BITS,
        proposal.link_power == RADICAL_POWER,
    )


__all__ = ["KLL_BITS", "Proposal", "RegularRootBox", "Result", "Source", "T", "solve"]
