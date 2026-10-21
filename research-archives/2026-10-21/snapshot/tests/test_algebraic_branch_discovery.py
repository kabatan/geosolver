"""Analytical families and failure boundaries for finite branch proposals."""

import pytest

from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches


def discover(names, equations, targets=None, constructions=()):
    return discover_polynomial_branches(
        {
            "variables": names,
            "construction": constructions,
            "constraints": equations,
            "targets": [0] * len(equations) if targets is None else targets,
        }
    )


@pytest.mark.parametrize("r,s,scale", [(2, -3, 1), (5, -7, -11), (-11, 4, 1000)])
def test_repeated_roots_are_all_preserved_under_equation_scaling(r, s, scale):
    data = discover(["z"], [f"{scale}*(z-({r}))**2*(z-({s}))**2", "0"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == sorted([r, s])


@pytest.mark.parametrize("offset,radius", [(1, 5), (4, 10), (-2, 13)])
def test_affine_elimination_preserves_both_circle_line_branches(offset, radius):
    data = discover(["u", "v"], [f"u-v-{offset}", f"u*u+v*v-{radius}"])
    assert data is not None
    import sympy as sp

    t = sp.Symbol("t")
    expected = sorted(float(r) for r in sp.real_roots((t - offset) ** 2 + t * t - radius))
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx(expected)


def test_distance_squaring_retains_both_signs_as_proposals():
    data = discover(["x"], ["Distance(A,B)"], ["7"], [("A", "Point(x,0)"), ("B", "Point(0,0)")])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-7, 7]


def test_radical_norm_sign_proves_extra_branch_invalid():
    data = discover(["x"], ["sqrt(x+1)+x-1"])
    assert data is not None
    # x=3 violates the necessary real norm sign a*b<=0.
    assert sorted(float(p[0]) for p in data["points"]) == [0]
    assert data["proved_norm_sign_exclusions"] == 1


def test_denominator_clearing_never_promises_original_domain_validity():
    data = discover(["x"], ["(x*x-1)/(x-1)"])
    assert data is not None
    # SymPy may cancel x=1. Either conservative superset is permitted.
    assert -1 in [float(p[0]) for p in data["points"]]


def test_shape_position_division_does_not_lose_a_singular_branch():
    # At y=0, xy=0 leaves a continuum; dividing by y would lose it.
    assert discover(["x", "y"], ["x*y", "y*(y-1)"]) is None


def test_positive_dimensional_system_keeps_numerical_search():
    assert discover(["x", "y"], ["x+y-1"]) is None


def test_unsupported_transcendental_keeps_numerical_search():
    assert discover(["x"], ["sin(x)"]) is None


def test_close_roots_keep_distinct_high_precision_starting_coordinates():
    data = discover(["x"], ["(x-1)**2*(x-1-1/100000000000000000000)**2"])
    assert data is not None
    assert len(data["points"]) == 2
    assert data["points"][0] != data["points"][1]


def test_area_shoelace_retains_both_orientation_branches():
    data = discover(["h"], ["Area(Point(0,0),Point(6,0),Point(1,h))"], [12])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-4, 4]


def test_circle_incidence_has_exact_quadratic_relaxation():
    data = discover(["h"], ["OnCircle(Point(3,h),Circle(Point(0,0),5))"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-4, 4]


def test_exact_algebraic_constant_coefficients():
    data = discover(["x"], ["x*x-sqrt(2)"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx([-(2**0.25), 2**0.25])


def test_line_intersection_coordinates_are_rational():
    constructions = [
        ("L", "Line(Point(0,0),Point(4,2))"),
        ("M", "Line(Point(0,3),Point(3,0))"),
        ("P", "Intersect(L,M)"),
    ]
    data = discover(["x"], ["x-P.x"], constructions=constructions)
    assert data is not None
    assert float(data["points"][0][0]) == 2


def test_circumcenter_uses_exact_translated_cartesian_coordinates():
    data = discover(
        ["x", "y"],
        ["x-O.x", "y-O.y"],
        constructions=[("O", "Circumcenter(Point(0,0),Point(6,0),Point(0,8))")],
    )
    assert data is not None
    assert list(map(float, data["points"][0])) == [3, 4]


def test_nonzero_perpendicular_measure_retains_normalization():
    data = discover(["x"], ["Perpendicular(Line(1,0,0),Line(1,x,0))"], ["1/sqrt(2)"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-1, 1]


def test_internal_and_external_circle_tangencies_all_survive_relaxation():
    data = discover(["x"], ["IsTangent(Circle(Point(x,0),2),Circle(Point(0,0),3))"])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-5, -1, 1, 5]


def test_only_proved_false_original_guards_exclude_relaxation_roots():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["x*x-1"],
            "targets": [0],
            "guards": ["AssumeGt(x,0)", "UnknownPrimitive(x)"],
        }
    )
    assert data is not None
    assert [float(p[0]) for p in data["points"]] == [1]
    assert data["proved_guard_exclusions"] == 1
    assert data["false_original_guard_counts"] == {"0": 1}


def test_undefined_guard_expression_stays_unresolved():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["x*x-1"],
            "targets": [0],
            "guards": ["AssumeEq(1/(x-1),0)"],
        }
    )
    assert data is not None
    # The pole at 1 is unresolved, not misclassified as a false equality.
    assert [float(p[0]) for p in data["points"]] == [1]
    assert data["false_original_guard_counts"] == {"0": 1}


def test_optional_symbolic_timeout_does_not_become_a_geometry_failure(monkeypatch):
    from geosolver.engine.standard.search.algebraic_branches import AlgebraicWorkLimit
    from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials

    def interrupted(*_):
        raise AlgebraicWorkLimit("test timeout")

    monkeypatch.setattr(CartesianPolynomials, "scalar", interrupted)
    assert discover(["x"], ["x*x-1"]) is None


@pytest.mark.parametrize("shift,scale", [(0, 1), (3, -7), (-5, 13)])
def test_two_radical_sum_keeps_unique_real_domain_root_under_transformations(shift, scale):
    # sqrt(z)+sqrt(z+1)=3 has exactly z=16/9 on its real domain.
    z = f"(x-({shift}))"
    data = discover(["x"], [f"{scale}*(sqrt({z})+sqrt({z}+1)-3)"])
    assert data is not None
    assert [float(p[0]) for p in data["points"]] == pytest.approx([shift + 16 / 9])


def test_two_distance_radicals_retain_both_geometric_branches():
    data = discover(["x"], ["sqrt(x*x+1)+sqrt(x*x+4)"], [5])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx(
        [-4 * 6**0.5 / 5, 4 * 6**0.5 / 5]
    )


def test_two_absolute_values_retain_both_exterior_branches():
    data = discover(["x"], ["abs(x-2)+abs(x+3)"], [9])
    assert data is not None
    assert sorted(float(p[0]) for p in data["points"]) == [-5, 4]


def test_nested_radical_norm_sign_keeps_original_domain_branch():
    data = discover(["x"], ["sqrt(x+sqrt(x+1))"], [2])
    assert data is not None
    # The other root contradicts an exactly proved necessary norm sign.
    assert sorted(float(p[0]) for p in data["points"]) == pytest.approx(
        [(9 - 21**0.5) / 2]
    )


def test_three_radical_sum_never_loses_original_root():
    data = discover(["x"], ["sqrt(x+1)+sqrt(x+4)+sqrt(x+9)"], [6])
    assert data is not None
    assert any(abs(float(p[0])) < 1e-30 for p in data["points"])


def test_multiradical_denominator_pole_does_not_lose_valid_root():
    data = discover(["x"], ["sqrt(x+1)/(x-1)+sqrt(x+4)"], [1])
    assert data is not None
    assert any(abs(float(p[0])) < 1e-30 for p in data["points"])


def test_multiradical_identity_retains_numerical_fallback():
    assert discover(["x"], ["sqrt(x*x)-abs(x)"]) is None


@pytest.mark.parametrize("scale,reverse", [(1, False), (-7, True), (1000, False)])
def test_disconnected_univariate_components_preserve_full_cartesian_product(scale, reverse):
    equations = [f"{scale}*(x*x-4)", "y*y-9"]
    if reverse:
        equations.reverse()
    data = discover(["x", "y"], equations)
    assert data is not None
    assert data["method"] == "cartesian_component_univariate_isolation"
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-2, -3),
        (-2, 3),
        (2, -3),
        (2, 3),
    ]


def test_disconnected_bivariate_components_avoid_global_variable_gate():
    data = discover(["a", "b", "c", "d"], ["a*b-1", "b*b-4", "c-d*d", "d*d-9"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-0.5, -2, 9, -3),
        (-0.5, -2, 9, 3),
        (0.5, 2, 9, -3),
        (0.5, 2, 9, 3),
    ]


def test_components_are_found_after_coupling_affine_elimination():
    data = discover(["x", "y", "u", "v"], ["x+y-1", "u-v-2", "x*x-4", "u*u-9"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-2, 3, -3, -5),
        (-2, 3, 3, 1),
        (2, -1, -3, -5),
        (2, -1, 3, 1),
    ]


def test_original_guard_couples_components_only_after_complete_product():
    data = discover_polynomial_branches(
        {
            "variables": ["x", "y"],
            "construction": [],
            "constraints": ["x*x-4", "y*y-9"],
            "targets": [0, 0],
            "guards": ["AssumeGt(x*y,0)"],
        }
    )
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [(-2, -3), (2, 3)]
    assert data["proved_guard_exclusions"] == 2


def test_any_positive_dimensional_component_retains_baseline():
    assert discover(["x", "y", "z"], ["x*x-4", "y*z-1"]) is None


def test_unused_coordinate_is_not_arbitrarily_fixed_even_if_target_could_be_invariant():
    assert discover(["x", "unused"], ["x*x-4"]) is None


def test_component_product_budget_declines_without_truncating_root_set():
    names = ["a", "b", "c", "d", "e"]
    assert discover(names, [f"{v}*{v}-1" for v in names]) is None


def test_boundary_product_budget_retains_all_sixteen_configurations():
    names = ["a", "b", "c", "d"]
    data = discover(names, [f"{v}*{v}-1" for v in names])
    assert data is not None
    assert len(data["points"]) == 16
    assert len({tuple(p) for p in data["points"]}) == 16


def test_basis_can_expose_components_hidden_by_equation_mixing():
    data = discover(["x", "y"], ["x*x+y*y-5", "x*x-y*y-3"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-2, -1),
        (-2, 1),
        (2, -1),
        (2, 1),
    ]


def test_hidden_component_product_over_budget_keeps_baseline():
    # Mixing preserves the same 5x5 independent root set, exceeding16 candidates.
    a = "(x-1)*(x-2)*(x-3)*(x-4)*(x-5)"
    b = "(y-1)*(y-2)*(y-3)*(y-4)*(y-5)"
    assert discover(["x", "y"], [f"{a}+{b}", f"{a}-{b}"]) is None


@pytest.mark.parametrize("scale,ordering", [(1, ["x", "y"]), (-11, ["y", "x"])])
def test_separating_form_recovers_all_axis_intersections(scale, ordering):
    data = discover(ordering, [f"{scale}*(x*x+y*y-1)", "x*y"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-1, 0),
        (0, -1),
        (0, 1),
        (1, 0),
    ]


def test_squarefree_parameter_constraint_removes_multiplicity_without_losing_roots():
    data = discover(["x", "y"], ["(x*x+y*y-1)**2", "x*y"])
    assert data is not None
    assert sorted(tuple(map(float, p)) for p in data["points"]) == [
        (-1, 0),
        (0, -1),
        (0, 1),
        (1, 0),
    ]


def test_nonseparating_all_bounded_forms_declines_without_root_truncation():
    # Four roots: (1,0),(2,0),(3,0),(0,1). Every tried T=x+k*y,
    # k=1,2,3, aliases two configurations; no partial parametrization is valid.
    assert discover(["x", "y"], ["x*y", "(x-1)*(x-2)*(x-3)+6*y"]) is None


def test_exact_squarefree_consequences_remove_noncyclic_nilpotents():
    data = discover(["x", "y"], ["x*x", "x*y", "y*y"])
    assert data is not None
    assert [list(map(float, point)) for point in data["points"]] == [[0, 0]]


def test_separating_form_does_not_make_positive_dimensional_system_finite():
    assert discover(["x", "y"], ["x*x+y*y-1"]) is None


def test_complex_only_variety_never_generates_real_coordinate_proposals():
    data = discover(["x", "y"], ["x*x+y*y+1", "x*y"])
    assert data is not None
    assert data["points"] == []


def test_distinct_roots_below_decimal_proposal_resolution_keep_baseline():
    assert discover(["x"], ["(x-1)*(x-1-1/10**200)"]) is None
