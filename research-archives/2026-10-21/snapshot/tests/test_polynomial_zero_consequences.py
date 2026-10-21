"""Exact factorization/SOS receipts and independent real zero-set families."""

import pytest
import sympy as sp

from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from geosolver.engine.standard.search.polynomial_zero_consequences import (
    quadratic_sos_zero_consequences,
    squarefree_zero_consequences,
)


def polynomial(expression, variables):
    return sp.Poly(expression, *variables, extension=True, field=True)


@pytest.mark.parametrize("scale", [1, -13, sp.Rational(1, 17), 10**120])
def test_squarefree_factorization_receipt_keeps_every_zero_component(scale):
    x, y = sp.symbols("x y", real=True)
    original = polynomial(scale * (x - y) ** 2 * (x + y - 1) ** 3, (x, y))
    before = original.as_expr()
    consequences = squarefree_zero_consequences([original], (x, y))
    assert original.as_expr() == before
    assert len(consequences) == 1
    squarefree, coefficient, factors = consequences[0]
    assert polynomial(
        before - coefficient * sp.prod(p.as_expr() ** m for p, m in factors), (x, y)
    ).is_zero
    assert polynomial(
        squarefree.as_expr() - sp.prod(p.as_expr() for p, _ in factors), (x, y)
    ).is_zero
    assert squarefree.total_degree() == 2


def test_squarefree_algebraic_coefficient_field_uses_exact_identity():
    x, y = sp.symbols("x y", real=True)
    original = polynomial((x - sp.sqrt(2) * y) ** 2, (x, y))
    row, coefficient, factors = squarefree_zero_consequences([original], (x, y))[0]
    assert row.total_degree() == 1
    assert polynomial(
        original.as_expr() - coefficient * sp.prod(p.as_expr() ** m for p, m in factors), (x, y)
    ).is_zero


@pytest.mark.parametrize("sign,scale", [(1, 1), (-1, 1), (1, sp.Rational(1, 13)), (-1, 10**120)])
def test_rational_psd_sos_receipt_including_degenerate_rank_and_negative_orientation(sign, scale):
    x, y, z = sp.symbols("x y z", real=True)
    q = sign * scale * ((x + y - 1) ** 2 + 3 * (y - z + 2) ** 2)
    original = polynomial(q, (x, y, z))
    before = original.as_expr()
    certificates = quadratic_sos_zero_consequences([original], (x, y, z))
    assert original.as_expr() == before
    assert len(certificates) == 1
    _, orientation, terms = certificates[0]
    assert len(terms) == 2
    assert all(d > 0 and row.total_degree() <= 1 for d, row in terms)
    assert polynomial(
        orientation * q - sum(d * row.as_expr() ** 2 for d, row in terms), (x, y, z)
    ).is_zero


@pytest.mark.parametrize("expression", ["x*y", "x*x-y*y", "x*x+y*y-1", "x*x+2*y"])
def test_indefinite_or_unbounded_quadratics_never_produce_sos_zero_claim(expression):
    x, y = sp.symbols("x y", real=True)
    assert not quadratic_sos_zero_consequences(
        [polynomial(sp.sympify(expression, locals={"x": x, "y": y}), (x, y))], (x, y)
    )


def test_algebraic_field_and_huge_coefficients_decline_optional_sos_subset():
    x, y = sp.symbols("x y", real=True)
    assert not quadratic_sos_zero_consequences(
        [polynomial(x * x + sp.sqrt(2) * y * y, (x, y))], (x, y)
    )
    assert not quadratic_sos_zero_consequences(
        [polynomial(10**2000 * (x * x + y * y), (x, y))], (x, y)
    )


@pytest.mark.parametrize("scale,reverse", [(1, False), (-7, True)])
def test_real_quadratic_sos_makes_complex_positive_dimensional_relaxation_finite(scale, reverse):
    names = ["x", "y", "z"]
    equation = f"({scale})*((x+y-1)**2+3*(y-z+2)**2+5*(z-4)**2)"
    if reverse:
        names.reverse()
    data = discover_polynomial_branches(
        {"variables": names, "construction": [], "constraints": [equation], "targets": [0]}
    )
    assert data is not None
    expected = {"x": -1, "y": 2, "z": 4}
    assert list(map(float, data["points"][0])) == [expected[n] for n in names]
    assert data["sos_consequence_count"] >= 3
    assert len(data["branch_boxes"]) == 1


def test_zero_distance_expands_to_necessary_affine_coordinates_without_gauge_fixing():
    payload = {
        "variables": ["x", "y"],
        "construction": [],
        "constraints": ["Distance(Point(x,y),Point(3,-2))"],
        "targets": [0],
    }
    data = discover_polynomial_branches(payload)
    assert data is not None
    assert list(map(float, data["points"][0])) == [3, -2]
    free = {"variables": ["x", "y"], "construction": [], "constraints": ["x*x"], "targets": [0]}
    assert discover_polynomial_branches(free) is None


def test_positive_definite_quadratic_certificate_correctly_proves_no_real_zeros():
    data = discover_polynomial_branches(
        {"variables": ["x", "y"], "construction": [], "constraints": ["x*x+y*y+1"], "targets": [0]}
    )
    assert data is not None
    assert data["points"] == []
