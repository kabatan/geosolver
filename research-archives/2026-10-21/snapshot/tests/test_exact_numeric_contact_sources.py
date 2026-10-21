"""A proof must distinguish decimal tokens that collapse to one float."""

import ast
from fractions import Fraction

import pytest

from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_plans
from geosolver.engine.standard.problem.tangency_contacts import (
    contact_tangency_source,
    distance_contact_sources,
)
from geosolver.engine.standard.problem.zero_test_source import rational_constant, zero_test_call
from geosolver.engine.standard.search.discrete.lattice_segments import _segment_branches
from geosolver.problem.expression_source import annotate_source
from geosolver.problem.incidence_residuals import necessary_incidence_residuals


def parse(source):
    return annotate_source(ast.parse(source, mode="eval"), source).body


@pytest.mark.parametrize(
    "small", ["1e-400", "0.00000000000000000000001", "0.10000000000000000000001-0.1"]
)
def test_nonzero_decimal_offsets_cannot_be_removed_from_a_zero_test(small):
    source = f"OnSegment(P,A,B)+({small})"
    assert rational_constant(parse(small)) != 0
    assert zero_test_call(source) is None
    assert necessary_incidence_residuals(source) == ()
    # A genuinely nonzero change of equation units is still allowed.
    assert zero_test_call(f"({small})*OnSegment(P,A,B)") is not None


def test_rational_proofs_decline_unannotated_python_floats():
    with pytest.raises(ValueError):
        rational_constant(ast.parse("0.1", mode="eval").body)
    assert rational_constant(parse("0.10000000000000000000001-0.1")) == Fraction(1, 10**23)
    assert rational_constant(ast.Constant(value=3)) == 3


@pytest.mark.parametrize("first,second", [("0.1", "0.10000000000000000000001"), ("0", "1e-400")])
def test_float_coincident_points_do_not_prove_contact_incidence(first, second):
    definitions = (
        ("G", f"Circumcircle(Point({first},0),Point(1,1),Point(2,0))"),
        ("L", f"Line(Point({second},0),Point({second},1))"),
    )
    assert contact_tangency_source("L", "G", definitions) is None


def test_tiny_nonzero_rhs_does_not_prove_incidence():
    definitions = (("P", "Point(0,0)"), ("L", "Line(P,Point(1,0))"), ("G", "Circle(Point(0,1),1)"))
    assert contact_tangency_source("L", "G", definitions, (("OnCircle(P,G)", "1e-400"),)) is None


def test_contact_rewrite_preserves_every_endpoint_decimal_token():
    token = "0.10000000000000000000001"
    line = f"Line(Point({token},0),Point({token},1))"
    definitions = (("G", f"Circumcircle(Point({token},0),Point(1,1),Point(2,0))"),)
    source = contact_tangency_source(line, "G", definitions)
    assert source is not None and token in source


def test_distance_contact_match_does_not_merge_distinct_decimal_radii():
    token = "1.00000000000000000000001"
    definitions = (
        ("P", "Point(0,0)"),
        ("C", "Point(0,1)"),
        ("L", "Line(P,Point(1,0))"),
        ("G", "Circle(C,1.0)"),
    )
    equalities = (("Distance(C,L)", token), ("OnCircle(P,G)", "0"))
    assert distance_contact_sources(definitions, equalities) == {}


@pytest.mark.parametrize("base,vertex", [("0.10000000000000000000001", "0.1"), ("1e-400", "0")])
def test_distinct_zero_radius_base_cannot_be_treated_as_an_outer_vertex(base, vertex):
    definitions = (
        ("B", f"Point({vertex},0)"),
        ("P", "Point(0,2)"),
        ("Q", "Point(-2,0)"),
        ("G", "Circumcircle(B,P,Q)"),
        ("C", f"Point({base}-2*r,r)"),
        ("D", "Circle(C,r)"),
    )
    assert (
        positive_radius_contact_plans(
            ("r",), definitions, (("Distance(C,Center(G))", "Radius(G)-r"),)
        )
        == ()
    )


def test_radius_closure_keeps_tiny_nonzero_center_coefficients():
    token = "0.10000000000000000000001"
    tiny = "1e-400"
    definitions = (
        ("B", f"Point({token},0)"),
        ("P", "Point(0,2)"),
        ("Q", "Point(-2,0)"),
        ("G", "Circumcircle(B,P,Q)"),
        ("C", f"Point({token}-2*r,{tiny}*r)"),
        ("D", "Circle(C,r)"),
    )
    plans = positive_radius_contact_plans(
        ("r",), definitions, (("Distance(C,Center(G))", "Radius(G)-r"),)
    )
    assert len(plans) == 1
    assert token in plans[0][1] and tiny in plans[0][1]


def test_lattice_anchor_with_tiny_exact_offset_is_not_rounded_to_an_integer():
    epsilon = "0.00000000000000000000001"
    definitions = (
        ("A", f"Point({epsilon},0)"),
        ("D", f"Point(1+{epsilon},7)"),
        ("B", "Point(x,y)"),
        ("C", "Point(z,w)"),
    )
    constraints = (
        "IsInteger(x)",
        "IsInteger(y)",
        "IsInteger(z)",
        "IsInteger(w)",
        "Parallel(Line(A,B),Line(C,D))",
        "Distance(B,C)",
    )
    targets = ("0", "0", "0", "0", "0", "Distance(A,D)")
    # Exclude every horizontal line, plus the unconstrained zero-direction
    # parallelogram family. Most other integer lines are impossible only
    # because the anchor's tiny rational denominator was retained exactly.
    guards = ("AssumeNe(B.y,A.y)", "AssumeNe(Parallel(Line(B,C),Line(A,D)),0)")
    plan = _segment_branches(
        ("x", "y", "z", "w"), definitions, constraints, targets, guards, "Slope(Line(A,B))"
    )
    assert plan is not None
    assert plan.total_displacements == 12
    assert plan.excluded_displacements == 12
    assert plan.branches == ()
