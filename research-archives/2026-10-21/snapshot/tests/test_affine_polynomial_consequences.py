"""Exact row-combination receipts for sparse quadratic geometry reduction."""

from itertools import product

import pytest
import sympy as sp

from geosolver.engine.standard.search.algebraic_branches import (
    affine_polynomial_consequences,
    discover_polynomial_branches,
)


def rows(expressions, variables):
    return [
        sp.Poly(expression, *variables, extension=True, field=True) for expression in expressions
    ]


def check_receipts(equations, variables):
    before = [p.as_expr() for p in equations]
    consequences = affine_polynomial_consequences(equations, variables)
    assert [p.as_expr() for p in equations] == before
    for poly, weights in consequences:
        assert poly.total_degree() <= 1
        assert len(weights) == len(equations)
        difference = poly.as_expr() - sum(
            weight * p.as_expr() for weight, p in zip(weights, equations, strict=True)
        )
        assert sp.Poly(sp.expand(difference), *variables, extension=True).is_zero
    return consequences


@pytest.mark.parametrize(
    "scales", [(1, 1, 1), (-7, 11, 13), (10**120, sp.Rational(1, 7), -(10**80))]
)
def test_exact_affine_combinations_under_scaling_and_huge_finite_coefficients(scales):
    x, y = sp.symbols("x y", real=True)
    q = x * x + y * y
    equations = rows(
        [scales[0] * (q - 5), scales[1] * (q + 2 * x - 9), scales[2] * (q - 3 * y - 2)], (x, y)
    )
    consequences = check_receipts(equations, (x, y))
    assert len(consequences) == 2
    assert sp.groebner([p.as_expr() for p, _ in consequences], x, y) == sp.groebner(
        [x - 2, y - 1], x, y
    )


def test_degenerate_rank_and_redundant_rows_have_valid_constant_receipts():
    x, y = sp.symbols("x y", real=True)
    q = x * x + y * y
    equations = rows([q - 5, 2 * (q - 5), q + 2 * x - 9, 3 * (q + 2 * x - 9), 0], (x, y))
    consequences = check_receipts(equations, (x, y))
    assert len(consequences) == 1
    assert sp.Poly(consequences[0][0].as_expr(), x, y).monic().as_expr() == x - 2
    assert not check_receipts(rows([q - 5, 2 * (q - 5), 0], (x, y)), (x, y))


def test_exact_algebraic_coefficient_fields_are_unified_without_fuzzy_pivots():
    x, y = sp.symbols("x y", real=True)
    q = x * x + y * y
    equations = rows([q - 5, q + sp.sqrt(2) * (x - 2) - 5, q + sp.sqrt(3) * (y - 1) - 5], (x, y))
    consequences = check_receipts(equations, (x, y))
    assert len(consequences) == 2
    assert sp.groebner([p.as_expr() for p, _ in consequences], x, y) == sp.groebner(
        [x - 2, y - 1], x, y
    )


@pytest.mark.parametrize(
    "count,radius_squared,reverse", [(4, 7, False), (5, 11, True), (6, 13, False)]
)
def test_affine_differences_reduce_larger_quadratic_families_without_losing_branches(
    count, radius_squared, reverse
):
    names = [f"coordinate_{i}" for i in range(count)]
    fixed = list(range(1, count))
    squared_norm = "+".join(f"{v}**2" for v in names)
    total = sum(v * v for v in fixed) + radius_squared
    equations = [f"({squared_norm})-{total}"]
    equations += [
        f"({i + 2})*(({squared_norm})+({i + 3})*{name}-({total + (i + 3) * value}))"
        for i, (name, value) in enumerate(zip(names[:-1], fixed, strict=True))
    ]
    if reverse:
        names.reverse()
        equations.reverse()
    data = discover_polynomial_branches(
        {
            "variables": names,
            "construction": [],
            "constraints": equations,
            "targets": [0] * len(equations),
        }
    )
    assert data is not None
    assert data["affine_consequence_count"] == count - 1
    expected = [[*fixed, -(radius_squared**0.5)], [*fixed, radius_squared**0.5]]
    if reverse:
        expected = [list(reversed(p)) for p in expected]
    assert sorted(tuple(map(float, p)) for p in data["points"]) == pytest.approx(
        sorted(map(tuple, expected))
    )


def test_row_and_coefficient_limits_decline_only_optional_reduction():
    x, y = sp.symbols("x y", real=True)
    q = x * x + y * y
    assert not affine_polynomial_consequences(rows([q - 1] * 33, (x, y)), (x, y))
    assert not affine_polynomial_consequences(
        rows([(10**2000) * (q - 1), q + x - 2], (x, y)), (x, y)
    )


def test_monomial_budget_is_checked_before_row_reduction():
    variables = sp.symbols("a b c d e", real=True)
    monomials = [
        sp.prod(v**power for v, power in zip(variables, powers, strict=True))
        for powers in product(range(3), repeat=5)
        if sum(powers) <= 5
    ][:120]
    assert len(monomials) == 120
    equations = rows([sum(monomials[:60]), sum(monomials[60:])], variables)
    assert not affine_polynomial_consequences(equations, variables)


def test_transcendental_coefficient_field_is_not_treated_as_exact_algebraic():
    x, y = sp.symbols("x y", real=True)
    assert not affine_polynomial_consequences(
        rows([x * x + y * y - 1, x * x + y * y + sp.pi * x - 1], (x, y)), (x, y)
    )
