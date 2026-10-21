"""Norm signs exclude only exact arithmetic contradictions in proved domains."""

import pytest
import sympy as sp

from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from geosolver.engine.standard.search.algebraic_sign_ledger import (
    NormSignCondition,
    proved_norm_sign_violation,
)


def condition(a, b, c, absolute=False):
    return NormSignCondition(0, 0, sp.sympify(a), sp.sympify(b), sp.sympify(c), absolute)


def test_individually_complex_coefficients_never_rejected_by_positive_product():
    # i + (-i)*sqrt(1)=0, yet a*b=1. The real proof's premise fails.
    ledger = condition(sp.I, -sp.I, 1)
    assert ledger.a * ledger.b == 1
    assert proved_norm_sign_violation([ledger], {}) is None


@pytest.mark.parametrize("a,b,c,absolute", [(1, 2, 4, False), (-1, -3, 0, False), (1, 2, -4, True)])
def test_strict_positive_product_in_proved_real_domain_is_excluded(a, b, c, absolute):
    ledger = condition(a, b, c, absolute)
    assert proved_norm_sign_violation([ledger], {}) is ledger


@pytest.mark.parametrize(
    "a,b,c,absolute",
    [
        (0, 2, 1, False),
        (2, 0, 1, False),
        (1, -2, 1, False),
        (1, 2, -1, False),
        (sp.oo, 1, 1, False),
        (sp.nan, 1, 1, False),
        (1, 1, sp.I, True),
    ],
)
def test_unknown_nonfinite_boundary_or_wrong_sqrt_domain_is_retained(a, b, c, absolute):
    assert proved_norm_sign_violation([condition(a, b, c, absolute)], {}) is None


def test_uncanceled_pole_is_unknown():
    x = sp.Symbol("x", real=True)
    assert proved_norm_sign_violation([condition(1 / x, 1, 1)], {x: sp.S.Zero}) is None


def test_exact_rootof_sign_uses_isolating_intervals():
    x = sp.Symbol("x", real=True)
    roots = sp.Poly(x * x - 2, x).real_roots(radicals=False)
    ledger = condition(x, 1, 1)
    assert proved_norm_sign_violation([ledger], {x: roots[0]}) is None
    assert proved_norm_sign_violation([ledger], {x: roots[1]}) is ledger


def test_quadratic_norm_extraneous_branch_is_excluded_with_original_root_mapping():
    data = discover_polynomial_branches(
        {"variables": ["x"], "construction": [], "constraints": ["sqrt(x+1)+x-1"], "targets": [0]}
    )
    assert data is not None
    assert [list(map(float, p)) for p in data["points"]] == [[0]]
    assert data["original_root_count"] == 2
    assert data["retained_root_indices"] == [0]
    assert data["excluded_roots"] == [{"root_index": 1, "norm_constraint_index": 0, "norm_step": 0}]
    assert data["proved_norm_sign_exclusions"] == 1


def test_nested_radical_ledger_keeps_genuine_branch():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["sqrt(x+sqrt(x+1))-sqrt(2)"],
            "targets": [0],
        }
    )
    assert data is not None
    assert any(abs(float(p[0]) - (5 - 13**0.5) / 2) < 1e-12 for p in data["points"])


def test_absolute_value_norm_sign_filters_wrong_nonzero_target_sign():
    data = discover_polynomial_branches(
        {"variables": ["x"], "construction": [], "constraints": ["Abs(x)+x-2"], "targets": [0]}
    )
    assert data is not None
    assert [list(map(float, p)) for p in data["points"]] == [[1]]


@pytest.mark.parametrize(
    "root,radical,scale",
    [
        (-5, 0, 1),
        (-5, 2, -13),
        (-5, 5, 7),
        (0, 0, -3),
        (0, 2, 1),
        (0, 5, -11),
        (7, 0, 19),
        (7, 2, -17),
        (7, 5, 1),
    ],
)
def test_parameterized_rescaling_keeps_every_genuine_root_and_discards_only_wrong_sign(
    root, radical, scale
):
    offset = radical**2 - root
    constant = root + radical
    expression = f"({scale})*(sqrt(coordinate+({offset}))+coordinate-({constant}))"
    data = discover_polynomial_branches(
        {
            "variables": ["coordinate"],
            "construction": [],
            "constraints": [expression],
            "targets": [0],
        }
    )
    assert data is not None
    assert [list(map(float, p)) for p in data["points"]] == [[root]]
    assert data["proved_norm_sign_exclusions"] == 1


def test_tiny_rational_positive_product_is_an_exact_rejection():
    ledger = condition(sp.Rational(1, 10**300), 1, 0)
    assert proved_norm_sign_violation([ledger], {}) is ledger
