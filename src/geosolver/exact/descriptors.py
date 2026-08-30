from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sympy

from geosolver.problem.models import (
    AffinePiAnswer,
    AlgebraicAnswer,
    AlgebraicNumberDescriptor,
    ExactAnswer,
)


def _rational_text(value: sympy.Rational) -> str:
    numerator, denominator = value.as_numer_denom()
    if denominator == 1:
        return str(numerator)
    return f"{numerator}/{denominator}"


def _decimal_text(value: sympy.Expr, digits: int = 50) -> str:
    return str(sympy.N(value, digits))


def _affine_pi(expression: sympy.Expr) -> AffinePiAnswer | None:
    coefficient = sympy.simplify(expression.coeff(sympy.pi))
    constant = sympy.simplify(expression.subs(sympy.pi, 0))
    if coefficient == 0:
        return None
    if coefficient.is_real is not True or coefficient.is_algebraic is not True:
        return None
    if constant.is_real is not True or constant.is_algebraic is not True:
        return None
    if sympy.simplify(expression - coefficient * sympy.pi - constant) != 0:
        return None
    return AffinePiAnswer(
        pi_coefficient=_describe_algebraic(coefficient),
        constant=_describe_algebraic(constant),
        decimal=_decimal_text(expression),
    )


def _root_interval(
    polynomial: sympy.Poly,
    root: sympy.Expr,
) -> tuple[int, tuple[str, str]]:
    real_roots = list(sympy.polys.polytools.intervals(polynomial, eps=sympy.Rational(1, 10**60)))
    # Exact comparisons distinguish roots even when decimal previews coincide.
    # Never break an unresolved comparison by choosing the nearest interval.
    matches = []
    roots = sympy.real_roots(polynomial.as_expr(), polynomial.gens[0])
    for index, ((left, right), _multiplicity) in enumerate(real_roots):
        identical = index < len(roots) and sympy.simplify(root - roots[index]) == 0
        if identical or ((root >= left) is sympy.true and (root <= right) is sympy.true):
            matches.append((index, left, right))
    if len(matches) != 1:
        raise ValueError("exact root could not be uniquely matched to its isolating interval")
    index, left, right = matches[0]
    return index, (_rational_text(left), _rational_text(right))


def _describe_algebraic(
    expression: sympy.Expr, verified_polynomial=None
) -> AlgebraicNumberDescriptor:
    if expression.is_real is False or expression.is_algebraic is False:
        raise ValueError(f"value is not real algebraic: {expression}")
    polynomial_expression = (
        sympy.minimal_polynomial(expression)
        if verified_polynomial is None
        else sum(
            sympy.Integer(c) * sympy.Symbol("x") ** i
            for i, c in enumerate(reversed(verified_polynomial))
        )
    )
    generator = next(iter(polynomial_expression.free_symbols), sympy.Symbol("x"))
    polynomial = sympy.Poly(polynomial_expression, generator, domain=sympy.ZZ)
    primitive = polynomial.primitive()[1]
    if primitive.LC() < 0:
        primitive = -primitive
    root_index, interval = _root_interval(primitive, expression)
    return AlgebraicNumberDescriptor(
        minimal_polynomial=[str(coefficient) for coefficient in primitive.all_coeffs()],
        real_root_index=root_index,
        isolating_interval=interval,
        decimal=_decimal_text(expression),
    )


def describe_exact(
    value: str | int | float | sympy.Expr, *, verified_polynomial=None
) -> ExactAnswer:
    expression = sympy.sympify(value)
    pi_answer = _affine_pi(expression)
    if pi_answer is not None and expression.has(sympy.pi):
        return pi_answer
    return AlgebraicAnswer(value=_describe_algebraic(expression, verified_polynomial))


def assemble_exact_answers(candidates: Iterable[Any]) -> tuple[list[ExactAnswer], list[str]]:
    """Exactify every candidate before deduplicating by its mathematical identity."""
    answers: list[ExactAnswer] = []
    warnings: list[str] = []
    seen: set[tuple[object, ...]] = set()
    for candidate in candidates:
        try:
            answer = describe_exact(candidate)
        except Exception as error:
            warnings.append(f"exactification failed for {candidate!r}: {error}")
            continue
        key = answer.canonical_key()
        if key in seen:
            continue
        seen.add(key)
        answers.append(answer)
    return answers, warnings
