"""Bounded exact identification for values of the form ``A*pi + B``.

Both coefficients must be real algebraic numbers.  The search first handles
the common rational-coefficient case with a three-term PSLQ relation.  For
algebraic coefficients it searches a bounded bivariate integer relation in
``(value, pi)``, then solves exactly for algebraic ``A`` and ``B`` such that
substituting ``value = A*t + B`` makes the relation an identity in ``t``.

An integer-relation residual is never sufficient for acceptance.  The final
symbolic expression is evaluated independently and its direct distance from
the input must meet the requested precision tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from math import gcd
from typing import Any

import sympy as sp
from mpmath import mp, pslq

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat

_MAX_AFFINE_SOLUTIONS = 64
_AFFINE_RELATION_LENGTH = 3
_AFFINE_SOLUTION_LENGTH = 2


@dataclass(frozen=True)
class AffinePiIdentification:
    """One verified affine-in-pi exact expression."""

    exact_value: str
    verification_residual: MPFloat
    relation_total_degree: int
    method: str


def _verification_tolerance(precision_dps: int) -> MPFloat:
    return mp.power(mp.mpf("10"), -(max(int(precision_dps) - 20, 1)))


def _normalize_relation(relation: object) -> tuple[int, ...] | None:
    try:
        values = [int(value) for value in relation]
    except (TypeError, ValueError, OverflowError):
        return None
    if not values or not any(values):
        return None
    divisor = reduce(gcd, (abs(value) for value in values if value), 0)
    if divisor > 1:
        values = [value // divisor for value in values]
    first_nonzero = next((value for value in values if value), 0)
    if first_nonzero < 0:
        values = [-value for value in values]
    return tuple(values)


def _affine_coefficients(expression: Any) -> tuple[Any, Any] | None:
    """Return algebraic ``(A, B)`` only for an exact ``A*pi + B`` expression."""

    try:
        expr = sp.simplify(sp.sympify(expression))
        if expr.atoms(sp.Float):
            return None
        pi_symbol = sp.Dummy("affine_pi")
        polynomial = sp.Poly(sp.expand(expr.xreplace({sp.pi: pi_symbol})), pi_symbol)
        if polynomial.degree() != 1:
            return None
        coefficient, constant = polynomial.all_coeffs()
        coefficient = sp.simplify(coefficient)
        constant = sp.simplify(constant)
        if coefficient == 0:
            return None
        for value in (coefficient, constant):
            if value.has(pi_symbol) or value.has(sp.pi):
                return None
            if value.is_real is not True or value.is_algebraic is not True:
                return None
            # Force an exact algebraicity certificate rather than trusting a
            # merely heuristic expression property.
            sp.minimal_polynomial(value)
        return coefficient, constant
    except Exception:
        return None


def verify_affine_pi_expression(
    *,
    expression: Any,
    numeric_value: MPFloat,
    precision_dps: int,
) -> tuple[bool, MPFloat]:
    """Verify algebraic coefficients and direct expression-to-value distance."""

    coefficients = _affine_coefficients(expression)
    if coefficients is None:
        return False, mp.inf
    try:
        coefficient, constant = coefficients
        exact_expression = sp.simplify(coefficient * sp.pi + constant)
        work_dps = max(int(precision_dps) + 40, 80)
        with mp.workdps(work_dps):
            approximation = mp.mpf(str(sp.N(exact_expression, work_dps)))
            residual = abs(approximation - mp.mpf(numeric_value))
            tolerance = _verification_tolerance(int(precision_dps))
            verified = bool(mp.isfinite(residual) and residual <= tolerance)
        return verified, residual
    except Exception:
        return False, mp.inf


def _rational_affine_identification(
    *,
    numeric_value: MPFloat,
    precision_dps: int,
    max_coeff: int,
    max_steps: int,
) -> AffinePiIdentification | None:
    try:
        work_dps = max(int(precision_dps) + 40, 80)
        with mp.workdps(work_dps):
            relation = pslq(
                mp.matrix([mp.mpf(numeric_value), mp.pi, mp.mpf("1")]),
                tol=_verification_tolerance(int(precision_dps)),
                maxcoeff=int(max_coeff),
                maxsteps=int(max_steps),
            )
        normalized = _normalize_relation(relation)
        if normalized is None or len(normalized) != _AFFINE_RELATION_LENGTH:
            return None
        value_coefficient, pi_coefficient, constant = normalized
        # A zero pi coefficient is an ordinary algebraic/rational result and
        # belongs to the existing minimal-polynomial path.
        if value_coefficient == 0 or pi_coefficient == 0:
            return None
        expression = sp.simplify(
            -sp.Rational(pi_coefficient, value_coefficient) * sp.pi
            - sp.Rational(constant, value_coefficient)
        )
        verified, residual = verify_affine_pi_expression(
            expression=expression,
            numeric_value=numeric_value,
            precision_dps=int(precision_dps),
        )
        if not verified:
            return None
        return AffinePiIdentification(
            exact_value=str(expression),
            verification_residual=residual,
            relation_total_degree=1,
            method="pslq-affine-pi-rational",
        )
    except Exception:
        return None


def _monomial_exponents(total_degree: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (value_degree, degree - value_degree)
        for degree in range(int(total_degree) + 1)
        for value_degree in range(degree + 1)
    )


def _find_bivariate_relation(
    *,
    numeric_value: MPFloat,
    total_degree: int,
    precision_dps: int,
    max_coeff: int,
    max_steps: int,
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...]] | None:
    try:
        exponents = _monomial_exponents(int(total_degree))
        work_dps = max(int(precision_dps) + 40, 80)
        with mp.workdps(work_dps):
            value = mp.mpf(numeric_value)
            monomials = [
                value**value_degree * mp.pi**pi_degree
                for value_degree, pi_degree in exponents
            ]
            relation = pslq(
                mp.matrix(monomials),
                tol=_verification_tolerance(int(precision_dps)),
                maxcoeff=int(max_coeff),
                maxsteps=int(max_steps),
            )
        normalized = _normalize_relation(relation)
        if normalized is None or len(normalized) != len(exponents):
            return None
        return exponents, normalized
    except Exception:
        return None


def _relation_factors(
    exponents: tuple[tuple[int, int], ...],
    relation: tuple[int, ...],
) -> tuple[Any, ...]:
    """Return distinct irreducible bivariate factors involving both variables."""

    try:
        value_symbol, pi_symbol = sp.symbols("affine_value affine_pi")
        expression = sum(
            coefficient * value_symbol**value_degree * pi_symbol**pi_degree
            for (value_degree, pi_degree), coefficient in zip(
                exponents, relation, strict=True
            )
        )
        polynomial = sp.Poly(expression, value_symbol, pi_symbol, domain=sp.ZZ)
        _content, raw_factors = sp.factor_list(polynomial.as_expr())
        factors: list[Any] = []
        for factor, _multiplicity in raw_factors:
            candidate = sp.Poly(factor, value_symbol, pi_symbol, domain=sp.QQ)
            if candidate.degree(value_symbol) < 1 or candidate.degree(pi_symbol) < 1:
                continue
            factors.append(candidate.as_expr())
        return tuple(factors)
    except Exception:
        return ()


def _factor_affine_candidates(
    *,
    factor: Any,
    numeric_value: MPFloat,
    precision_dps: int,
) -> tuple[tuple[Any, MPFloat], ...]:
    """Solve exactly for all algebraic affine-in-pi roots of one factor."""

    try:
        value_symbol, pi_symbol = sp.symbols("affine_value affine_pi")
        coefficient_symbol, constant_symbol = sp.symbols(
            "affine_coefficient affine_constant"
        )
        substituted = sp.Poly(
            sp.expand(
                factor.subs(
                    value_symbol,
                    coefficient_symbol * pi_symbol + constant_symbol,
                )
            ),
            pi_symbol,
        )
        equations = [sp.expand(value) for value in substituted.all_coeffs() if value != 0]
        if not equations:
            return ()
        solutions = sp.solve_poly_system(
            equations,
            coefficient_symbol,
            constant_symbol,
        )
        if solutions is None or len(solutions) > _MAX_AFFINE_SOLUTIONS:
            return ()

        candidates: list[tuple[Any, MPFloat]] = []
        for solution in solutions:
            if len(solution) != _AFFINE_SOLUTION_LENGTH:
                continue
            coefficient, constant = (sp.simplify(value) for value in solution)
            expression = sp.simplify(coefficient * sp.pi + constant)
            if _affine_coefficients(expression) is None:
                continue
            identity = sp.Poly(
                sp.expand(
                    factor.subs(
                        value_symbol,
                        coefficient * pi_symbol + constant,
                    )
                ),
                pi_symbol,
            )
            if not identity.is_zero:
                continue
            verified, residual = verify_affine_pi_expression(
                expression=expression,
                numeric_value=numeric_value,
                precision_dps=int(precision_dps),
            )
            if verified:
                candidates.append((expression, residual))
        return tuple(candidates)
    except Exception:
        return ()


def _deduplicate_candidates(
    candidates: list[tuple[Any, MPFloat]],
) -> list[tuple[Any, MPFloat]]:
    try:
        result: list[tuple[Any, MPFloat]] = []
        for expression, residual in sorted(candidates, key=lambda item: item[1]):
            if any(sp.simplify(expression - old_expression) == 0 for old_expression, _ in result):
                continue
            result.append((expression, residual))
        return result
    except Exception:
        return []


def identify_affine_pi(
    *,
    numeric_value: MPFloat,
    precision_dps: int,
    max_total_degree: int,
    max_coeff: int,
    max_steps: int,
) -> AffinePiIdentification | None:
    """Identify a bounded-complexity exact value ``A*pi+B``.

    The representation is unique when ``A`` and ``B`` are algebraic and
    ``A != 0`` because pi is transcendental.  Numerical identification still
    needs explicit degree/height bounds, just like ordinary algebraic PSLQ;
    those bounds are supplied by the caller's exactification tier.
    """

    rational = _rational_affine_identification(
        numeric_value=numeric_value,
        precision_dps=int(precision_dps),
        max_coeff=int(max_coeff),
        max_steps=int(max_steps),
    )
    if rational is not None:
        return rational

    seen_relations: set[tuple[int, ...]] = set()
    for total_degree in range(2, max(1, int(max_total_degree)) + 1):
        relation_data = _find_bivariate_relation(
            numeric_value=numeric_value,
            total_degree=total_degree,
            precision_dps=int(precision_dps),
            max_coeff=int(max_coeff),
            max_steps=int(max_steps),
        )
        if relation_data is None:
            continue
        exponents, relation = relation_data
        if relation in seen_relations:
            continue
        seen_relations.add(relation)
        candidates: list[tuple[Any, MPFloat]] = []
        for factor in _relation_factors(exponents, relation):
            candidates.extend(
                _factor_affine_candidates(
                    factor=factor,
                    numeric_value=numeric_value,
                    precision_dps=int(precision_dps),
                )
            )
        unique = _deduplicate_candidates(candidates)
        # Multiple distinct algebraic affine expressions inside the direct
        # verification tolerance are numerically ambiguous; fail closed.
        if len(unique) != 1:
            continue
        expression, residual = unique[0]
        return AffinePiIdentification(
            exact_value=str(expression),
            verification_residual=residual,
            relation_total_degree=total_degree,
            method="pslq-affine-pi-algebraic",
        )
    return None
