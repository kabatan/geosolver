from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sympy

from geosolver.problem.models import AffinePiAnswer, AlgebraicAnswer, ExactAnswer


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
    if not coefficient.is_Rational or not constant.is_Rational:
        return None
    if sympy.simplify(expression - coefficient * sympy.pi - constant) != 0:
        return None
    return AffinePiAnswer(
        pi_coefficient=_rational_text(coefficient),
        constant=_rational_text(constant),
        decimal=_decimal_text(expression),
    )


def _root_interval(
    polynomial: sympy.Poly,
    root: sympy.Expr,
) -> tuple[int, tuple[str, str]]:
    real_roots = list(sympy.polys.polytools.intervals(polynomial, eps=sympy.Rational(1, 10**60)))
    root_value = sympy.N(root, 80)
    expanded: list[tuple[float, tuple[sympy.Rational, sympy.Rational]]] = []
    for interval, multiplicity in real_roots:
        left, right = interval
        midpoint = sympy.N((left + right) / 2, 80)
        for _ in range(int(multiplicity)):
            expanded.append((abs(float(midpoint - root_value)), (left, right)))
    if not expanded:
        raise ValueError("minimal polynomial has no real root")
    nearest = min(range(len(expanded)), key=lambda index: expanded[index][0])
    left, right = expanded[nearest][1]
    return nearest, (_rational_text(left), _rational_text(right))


def describe_exact(value: str | int | float | sympy.Expr) -> ExactAnswer:
    expression = sympy.sympify(value)
    pi_answer = _affine_pi(expression)
    if pi_answer is not None and expression.has(sympy.pi):
        return pi_answer
    if expression.is_real is False or expression.is_algebraic is False:
        raise ValueError(f"answer is not a real algebraic or affine-pi value: {value}")
    polynomial_expression = sympy.minimal_polynomial(expression)
    generator = next(iter(polynomial_expression.free_symbols), sympy.Symbol("x"))
    polynomial = sympy.Poly(polynomial_expression, generator, domain=sympy.ZZ)
    primitive = polynomial.primitive()[1]
    if primitive.LC() < 0:
        primitive = -primitive
    root_index, interval = _root_interval(primitive, expression)
    return AlgebraicAnswer(
        minimal_polynomial=[str(coefficient) for coefficient in primitive.all_coeffs()],
        real_root_index=root_index,
        isolating_interval=interval,
        decimal=_decimal_text(expression),
    )


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
