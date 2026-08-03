"""Exact post-processing for certified homotopy candidates.

The Julia worker is responsible for numerical path tracking and Krawczyk
certification.  This module never reconstructs a polynomial from a decimal
(``PSLQ`` is intentionally absent): it computes an exact Groebner elimination
from the rational compilation and uses the certified target witness only to
select an isolating interval of an irreducible factor.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import sympy as sp

from .ir import Compilation, Polynomial


class ExactEliminationError(RuntimeError):
    """The exact target certificate could not be constructed."""


def polynomial_expression(polynomial: Polynomial, variables: Sequence[sp.Symbol]) -> sp.Expr:
    expression: sp.Expr = sp.Integer(0)
    for term in polynomial.terms:
        if len(term.exponents) != len(variables):
            raise ExactEliminationError("polynomial exponent width does not match variables")
        monomial = sp.Integer(term.numerator) / sp.Integer(term.denominator)
        for variable, exponent in zip(variables, term.exponents, strict=True):
            monomial *= variable ** int(exponent)
        expression += monomial
    return sp.expand(expression)


def system_expressions(
    compilation: Compilation,
) -> tuple[list[sp.Symbol], list[sp.Expr], sp.Symbol]:
    variables = [sp.Symbol(name) for name in compilation.variables]
    equations = [polynomial_expression(item, variables) for item in compilation.equations]
    target = sp.Symbol(compilation.target_variable)
    return variables, equations, target


def elimination_polynomial(compilation: Compilation) -> sp.Poly:
    """Return the primitive square-free target polynomial from exact elimination."""

    variables, equations, target = system_expressions(compilation)
    if not equations:
        raise ExactEliminationError("empty polynomial system")
    try:
        basis = sp.groebner(equations, *variables, order="lex")
    except Exception as error:
        raise ExactEliminationError(f"groebner elimination failed: {error}") from error
    candidates = [
        sp.Poly(item, target, domain=sp.QQ)
        for item in basis.polys
        if item.as_expr() != 0 and item.as_expr().free_symbols <= {target}
    ]
    if not candidates:
        raise ExactEliminationError("target elimination polynomial is unavailable")
    # The lex basis can contain multiples of the same univariate polynomial;
    # selecting the lowest degree and square-free primitive representative is
    # deterministic and prevents a spurious product from becoming a claimed
    # minimal polynomial.
    selected = min(candidates, key=lambda item: (item.degree(), len(item.terms())))
    selected = sp.Poly(selected.as_expr(), target, domain=sp.QQ)
    selected = sp.Poly(sp.primitive(selected.as_expr())[1], target, domain=sp.QQ)
    selected = sp.Poly(sp.sqf_part(selected.as_expr()), target, domain=sp.QQ)
    if selected.LC() < 0:
        selected = -selected
    return selected


def primitive_integer_coefficients(polynomial: sp.Poly) -> list[int]:
    polynomial = sp.Poly(polynomial.as_expr(), polynomial.gens[0], domain=sp.QQ)
    denominator, integer_poly = polynomial.clear_denoms(convert=True)
    coefficients = [int(value) for value in integer_poly.all_coeffs()]
    if not coefficients:
        raise ExactEliminationError("zero target polynomial")
    gcd = 0
    for value in coefficients:
        gcd = sp.igcd(gcd, abs(value))
    coefficients = [value // int(gcd or 1) for value in coefficients]
    if coefficients[0] < 0:
        coefficients = [-value for value in coefficients]
    return coefficients


def _candidate_real_value(candidate: Mapping[str, Any], index: int) -> sp.Float | None:
    coordinates = candidate.get("coordinates") or candidate.get("solution")
    if not isinstance(coordinates, list) or index >= len(coordinates):
        return None
    value = coordinates[index]
    try:
        if isinstance(value, Mapping):
            real = value.get("re", value.get("real", 0))
            imaginary = value.get("im", value.get("imag", 0))
            real_value = sp.Float(str(real), 100)
            imag_value = sp.Float(str(imaginary), 100)
        elif isinstance(value, list) and len(value) == 2:
            real_value, imag_value = sp.Float(str(value[0]), 100), sp.Float(str(value[1]), 100)
        else:
            parsed = complex(value)
            real_value, imag_value = sp.Float(parsed.real, 100), sp.Float(parsed.imag, 100)
    except (TypeError, ValueError, ArithmeticError):
        return None
    if abs(imag_value) > sp.Float("1e-70"):
        return None
    return real_value


def _real_intervals(
    polynomial: sp.Poly, *, epsilon: sp.Rational | None = None
) -> list[tuple[sp.Rational, sp.Rational]]:
    if epsilon is None:
        epsilon = sp.Rational(1, 10**80)
    try:
        intervals = polynomial.intervals(eps=epsilon)
    except Exception as error:
        raise ExactEliminationError(f"real-root isolation failed: {error}") from error
    result: list[tuple[sp.Rational, sp.Rational]] = []
    for interval, multiplicity in intervals:
        if multiplicity != 1:
            raise ExactEliminationError("multiple real target root")
        left, right = interval
        result.append((sp.Rational(left), sp.Rational(right)))
    result.sort(key=lambda item: item[0])
    return result


def target_descriptor(
    polynomial: sp.Poly,
    candidate: Mapping[str, Any],
    *,
    target_index: int,
) -> dict[str, Any] | None:
    value = _candidate_real_value(candidate, target_index)
    if value is None:
        return None
    # HomotopyContinuation's ordinary solution accessor is Float64.  First
    # match that witness against a conservative coarse isolation, then refine
    # the same ordered root to a publication-quality rational interval.
    coarse_intervals = _real_intervals(polynomial, epsilon=sp.Rational(1, 10**12))
    containing = [
        item
        for item in coarse_intervals
        if item[0] < value < item[1] or bool(value.equals(item[0])) or bool(value.equals(item[1]))
    ]
    if len(containing) != 1:
        return None
    root_index = coarse_intervals.index(containing[0])
    factors = sp.factor_list(polynomial.as_expr())[1]
    selected_factor = polynomial
    if len(factors) > 1:
        factor_matches = []
        for factor, _multiplicity in factors:
            factor_poly = sp.Poly(factor, polynomial.gens[0], domain=sp.QQ)
            factor_intervals = _real_intervals(factor_poly, epsilon=sp.Rational(1, 10**12))
            if any(
                interval[0] < value < interval[1]
                or bool(value.equals(interval[0]))
                or bool(value.equals(interval[1]))
                for interval in factor_intervals
            ):
                factor_matches.append(factor_poly)
        if len(factor_matches) == 1:
            selected_factor = factor_matches[0]
            root_index = 0
    intervals = _real_intervals(selected_factor)
    if selected_factor != polynomial:
        coarse_factor_intervals = _real_intervals(selected_factor, epsilon=sp.Rational(1, 10**12))
        matching_factor_intervals = [
            interval
            for interval in coarse_factor_intervals
            if interval[0] < value < interval[1]
            or bool(value.equals(interval[0]))
            or bool(value.equals(interval[1]))
        ]
        if len(matching_factor_intervals) != 1:
            return None
        root_index = coarse_factor_intervals.index(matching_factor_intervals[0])
    if root_index >= len(intervals):
        return None
    interval = intervals[root_index]
    midpoint = (interval[0] + interval[1]) / 2
    coefficients = primitive_integer_coefficients(selected_factor)
    witness = {
        "target": str(value),
        "certificate": "homotopy_continuation_krawczyk",
    }
    if "certificate_interval" in candidate:
        witness["krawczyk_interval"] = candidate["certificate_interval"]
    if "path_index" in candidate:
        witness["path_index"] = candidate["path_index"]
    if "precision_bits" in candidate:
        witness["precision_bits"] = candidate["precision_bits"]
    return {
        "minimal_polynomial_high_to_low": coefficients,
        "selected_real_root_index": int(root_index),
        "isolating_interval": [str(interval[0]), str(interval[1])],
        "decimal": sp.N(midpoint, 60).__str__(),
        "exact_authority_kind": "HC_KRAWCZYK_PLUS_EXACT_GROEBNER_ROOT_ISOLATION",
        "approximate_witness": witness,
    }


def descriptors_from_candidates(
    compilation: Compilation,
    candidates: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], sp.Poly]:
    polynomial = elimination_polynomial(compilation)
    target_index = compilation.variables.index(compilation.target_variable)
    descriptors: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
    for candidate in candidates:
        descriptor = target_descriptor(polynomial, candidate, target_index=target_index)
        if descriptor is None:
            continue
        key = (
            tuple(int(value) for value in descriptor["minimal_polynomial_high_to_low"]),
            int(descriptor["selected_real_root_index"]),
        )
        descriptors[key] = descriptor
    ordered = sorted(
        descriptors.values(),
        key=lambda item: (
            int(item["selected_real_root_index"]),
            item["minimal_polynomial_high_to_low"],
        ),
    )
    return ordered, polynomial


def exact_degree(compilation: Compilation) -> int | None:
    """Compute the quotient-space dimension for a zero-dimensional ideal.

    SymPy's Groebner basis exposes standard monomials only indirectly; for the
    small comparison systems, ``vector_space_dimension`` is available.  If a
    backend version does not expose it we return ``None`` and the caller must
    keep completeness unknown.
    """

    variables, equations, _ = system_expressions(compilation)
    try:
        basis = sp.groebner(equations, *variables, order="grevlex")
        if not basis.is_zero_dimensional:
            return None
        leading_monomials = [
            tuple(int(value) for value in polynomial.LM(order="grevlex").exponents)
            for polynomial in basis.polys
            if polynomial != 0
        ]
        if not leading_monomials:
            return None
        bounds = [
            max(monomial[index] for monomial in leading_monomials)
            for index in range(len(variables))
        ]
        dimension = 0
        import itertools

        for monomial in itertools.product(*(range(bound + 1) for bound in bounds)):
            if any(
                all(value >= lead for value, lead in zip(monomial, generator, strict=True))
                for generator in leading_monomials
            ):
                continue
            dimension += 1
        return dimension
    except Exception:
        return None


__all__ = [
    "ExactEliminationError",
    "descriptors_from_candidates",
    "elimination_polynomial",
    "exact_degree",
    "polynomial_expression",
    "primitive_integer_coefficients",
    "system_expressions",
    "target_descriptor",
]
