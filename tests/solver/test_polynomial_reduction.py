"""Polynomial reduction contracts and numerical regressions."""

from itertools import product

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.search.algebraic_branches import (
    affine_polynomial_consequences,
    discover_polynomial_branches,
)
from geosolver.engine.standard.search.algebraic_sign_ledger import (
    NormSignCondition,
    proved_norm_sign_violation,
)
from geosolver.engine.standard.search.cartesian_polynomials import (
    CartesianPolynomials,
    exact_guard_value,
)
from geosolver.engine.standard.search.polynomial_zero_consequences import (
    quadratic_sos_zero_consequences,
    squarefree_zero_consequences,
)
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from tests.helpers.capabilities import requires_cpu_timer


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


@requires_cpu_timer
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


@requires_cpu_timer
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


@requires_cpu_timer
def test_absolute_value_norm_sign_filters_wrong_nonzero_target_sign():
    data = discover_polynomial_branches(
        {"variables": ["x"], "construction": [], "constraints": ["Abs(x)+x-2"], "targets": [0]}
    )
    assert data is not None
    assert [list(map(float, p)) for p in data["points"]] == [[1]]


@requires_cpu_timer
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


@requires_cpu_timer
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


@requires_cpu_timer
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


@requires_cpu_timer
def test_positive_definite_quadratic_certificate_correctly_proves_no_real_zeros():
    data = discover_polynomial_branches(
        {"variables": ["x", "y"], "construction": [], "constraints": ["x*x+y*y+1"], "targets": [0]}
    )
    assert data is not None
    assert data["points"] == []


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize(
    "template",
    [
        "Line({s}*2,{s}*-3,5).a",
        "Line({s}*2,{s}*-3,5).b",
        "Line({s}*2,{s}*-3,5).c",
        "Line(Point(2,3),Point({s}*4,-5)).a",
        "Line(Point(2,3),Point({s}*4,-5)).b",
        "Line(Point(2,3),Point({s}*4,-5)).c",
        "Dot(Line({s}*2,-3,5),Line(-4,7,3))",
        "Parallel(Line({s}*2,-3,5),Line(-4,7,3))",
        "Perpendicular(Line({s}*2,-3,5),Line(-4,7,3))",
        "Dot(Vector(Point(2,3),Point({s}*4,-5)),Point(-4,7))",
        "Collinear(Point({s}*1,2),Point(4,8),Point(-3,5))",
        "OnLine(Point({s}*1,2),Point(4,8),Point(-3,5))",
        "OnLine(Point({s}*1,2),Line(2,-3,5))",
        "Distance(Point({s}*1,2),Line(2,-3,5))",
        "Area(Point({s}*1,2),Point(4,8),Point(-3,5))",
        "Area(Point({s}*1,2),Point(4,8),Point(-3,5),Point(-7,2))",
        "PerpendicularLine(Line({s}*2,-3,5),Point(-4,7)).c",
        "ParallelLine(Point(-4,7),Line({s}*2,-3,5)).c",
        "PerpendicularBisector(Point({s}*1,2),Point(4,8)).c",
        "FootOfPerpendicular(Point({s}*1,2),Line(2,-3,5)).x",
        "Reflect(Point({s}*1,2),Line(2,-3,5)).y",
        "Reflect(Point({s}*1,2),Point(4,8)).x",
        "Intersect(Line({s}*2,-3,5),Line(-4,7,3)).x",
        "Circumcenter(Point({s}*1,2),Point(4,8),Point(-3,5)).y",
        "Radius(Circumcircle(Point({s}*1,2),Point(4,8),Point(-3,5)))",
        "Orthocenter(Point({s}*1,2),Point(4,8),Point(-3,5)).x",
        "Centroid(Point({s}*1,2),Point(4,8),Point(-3,5)).y",
    ],
)
def test_nonzero_measurements_match_original_high_precision_semantics(template, sign):
    source = template.format(s=sign)
    geometry = CartesianPolynomials({})
    exact = geometry.scalar(geometry.parse(source))
    with mp.workdps(100):
        original = safe_eval_expr_hp(source, _get_high_precision_context(100))
        proposal = mp.mpf(str(sp.N(exact, 100)))
        assert abs(original - proposal) < mp.mpf("1e-90")


@pytest.mark.parametrize(
    "source",
    [
        "AssumeEq(Dot(Line(1,0,0),Line(-1,0,0)),1)",
        "AssumeLt(Collinear(Point(1,2),Point(4,8),Point(-3,5)),0)",
        "AssumeEq(Area(Point(0,0),Point(2,0),Point(0,2)),3)",
        "AssumeEq(Distance(Point(0,0),Line(0,0,0)),0)",
        "AssumeEq((1/(x-x))*0,1)",
        "AssumeEq(sqrt(x-2)**2,0)",
        "AssumeEq((x-1)/(x-1),0)",
    ],
)
def test_geometry_and_undefined_arithmetic_guards_remain_unresolved(source):
    geometry = CartesianPolynomials({})
    assert exact_guard_value(source, geometry, {sp.Symbol("x", real=True): sp.Integer(1)}) is None


def test_scalar_alias_to_geometry_is_not_used_for_exclusion():
    geometry = CartesianPolynomials({"d": "Distance(Point(0,0),Point(1,0))"})
    assert exact_guard_value("AssumeEq(d,0)", geometry, {}) is None


def test_scalar_aliases_and_exact_arithmetic_can_prove_false_guard():
    geometry = CartesianPolynomials({"a": "x+1", "b": "sqrt(a)*2"})
    values = {sp.Symbol("x", real=True): sp.Integer(3)}
    assert exact_guard_value("AssumeLt(b,abs(-3))", geometry, values) is False


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


@requires_cpu_timer
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
