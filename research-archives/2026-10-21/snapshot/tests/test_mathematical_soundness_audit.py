"""Analytic counterexamples for optional geometric search proofs."""

from fractions import Fraction
from types import SimpleNamespace

import pytest

from geosolver.engine.standard.problem.positive_scale_chart import positive_scale_chart
from geosolver.engine.standard.search.discrete.lattice_segments import integer_segment_branches
from geosolver.engine.standard.search.discrete.square_difference import _square_root_points
from geosolver.geometry.entities import Point
from geosolver.geometry.operations.basic import AreConcyclic, OnLine

POINTS = (("O", "Point(0,0)"), ("A", "Point(x,0)"), ("B", "Point(0,x)"))


def chart(definitions=POINTS, equations=(), answer="x/x"):
    return positive_scale_chart(("x",), definitions, equations, ("AssumeGt(x,0)",), answer)


def test_three_point_on_line_is_quadratic_not_linear():
    # OnLine(O,A,B)=x^2. x^2=x selects x=1; scaling by two breaks it.
    assert OnLine(Point(0, 0), Point(1, 0), Point(0, 1)) == 1
    assert OnLine(Point(0, 0), Point(2, 0), Point(0, 2)) == 4
    assert chart(equations=(("OnLine(O,A,B)", "x"),)) is None


def test_concyclic_residual_is_distance_not_a_degree_four_determinant():
    definitions = POINTS + (("D", "Point(x/2,0)"),)
    value = AreConcyclic(Point(0, 0), Point(1, 0), Point(0, 1), Point(Fraction(1, 2), 0))
    scaled = AreConcyclic(Point(0, 0), Point(2, 0), Point(0, 2), Point(1, 0))
    assert scaled == 2 * value
    assert chart(definitions, (("AreConcyclic(O,A,B,D)", "-x**4"),)) is None


@pytest.mark.parametrize("selector", ["Point(1,0)", "Point(0,x)", "3", "x/x"])
def test_contact_selector_domain_must_be_proved_scale_equivariant(selector):
    definitions = POINTS + (("T", f"IncircleContactPoint(A,B,O,{selector})"),)
    # A fixed vertex selector matches only x=1. Conservative proof supports
    # only the discrete scalar selectors 0/1/2, never arbitrary geometric data.
    assert chart(definitions) is None


@pytest.mark.parametrize("selector", ["0", "1", "2", "1.0000000000000000000000000000000000000001"])
def test_contact_selector_uses_exact_discrete_scalar_values(selector):
    definitions = POINTS + (("T", f"IncircleContactPoint(A,B,O,{selector})"),)
    assert chart(definitions) == ("x" if selector in {"0", "1", "2"} else None)


@pytest.mark.parametrize(
    "expression,power",
    [
        ("Area(O,A,B)", 2),
        ("Collinear(O,A,B)", 2),
        ("OnLine(O,A,B)", 2),
        ("OnLine(B,Line(O,A))", 1),
        ("OnSegment(O,A,B)", 1),
        ("AreConcyclic(O,A,B,Point(x/2,0))", 1),
        ("OnCircle(A,Circle(O,x))", 1),
        ("IsTangent(Line(O,A),Circle(B,x))", 1),
        ("Dot(Vector(O,A),Vector(O,B))", 2),
    ],
)
def test_supported_geometric_residuals_have_their_implemented_degree(expression, power):
    assert chart(answer=f"({expression})/(x**{power})") == "x"


@pytest.mark.parametrize("expression", ["Angle(A,O,B)", "Perimeter(O,A,B)", "Area(Circle(O,x))"])
def test_unimplemented_typed_proofs_decline_instead_of_guessing(expression):
    assert chart(answer=f"({expression})/x") is None


@pytest.mark.parametrize(
    "definition",
    [
        "Point(x,1e-400)",
        "Circle(Point(x,0),1e-400)",
        "Line(Point(1e-400,0),Point(x,x))",
        "Point(x,x**1.0000000000000000000000000000000000000001)",
    ],
)
def test_extreme_nonzero_literals_are_never_polymorphic_zero(definition):
    assert chart(POINTS + (("bad", definition),)) is None


@pytest.mark.parametrize("rhs", ["y", "x", "-2", "-1.9999999999999999999999999999999999"])
def test_normalized_parallel_nonzero_rhs_cannot_exclude_lattice_displacements(rhs):
    definitions = (
        ("A", "Point(0,-2)"),
        ("D", "Point(1,-1)"),
        ("B", "Point(x,y)"),
        ("C", "Point(z,w)"),
        ("L", "Line(A,B)"),
        ("N", "Line(C,D)"),
        ("M", "Line(B,C)"),
        ("O", "Line(A,D)"),
    )
    bundle = SimpleNamespace(
        var_names=("x", "y", "z", "w"),
        spec=SimpleNamespace(
            construction=tuple(SimpleNamespace(name=n, expr=e) for n, e in definitions),
            constraints=tuple(f"IsInteger({v})" for v in ("x", "y", "z", "w"))
            + ("Parallel(L,N)", "Distance(A,D)"),
            v=(0, 0, 0, 0, 0, "Distance(B,C)"),
            guards=(f"AssumeNe(Parallel(M,O),{rhs})",),
            answer_expr="Slope(L)",
        ),
    )
    plan = integer_segment_branches(bundle)
    assert plan is not None
    assert plan.excluded_displacements == 0
    # BC=(-1,1), AB horizontal: Parallel(BC,AD)=-1 but raw cross=-2.
    assert any(
        p[1] == -2 and p[3] == -1 and p[2] == p[0] - 1 for branch in plan.branches for p in branch
    )
    # BC=AD leaves AB unconstrained; RHS=x may vary along that family.
    assert () in plan.branches


def test_quadratic_seed_formula_keeps_representable_small_root_after_cancellation():
    points = _square_root_points((Fraction(4), Fraction(10**100), Fraction(1)), 0)
    assert points is not None and len(points) == 2
    assert all(point != 0 for point in points)
    assert points[0] * points[1] == pytest.approx(4)


def test_identically_zero_root_polynomial_is_not_a_finite_empty_set():
    assert _square_root_points((Fraction(9),), 9) is None
    assert _square_root_points((Fraction(9),), 4) == ()


@pytest.mark.parametrize("exponent", [-400, 400])
def test_necessary_positive_radius_contact_equation_preserves_extreme_exact_scale(exponent):
    from geosolver.engine.standard.problem.positive_radius_contacts import (
        positive_radius_contact_plans,
    )

    # Source-proof portion only: large/small exact literals cannot become zero
    # or rounded coincident vertices during structural incidence comparison.
    scale = f"1e{exponent}"
    definitions = (
        ("P", f"Point(2*{scale},0)"),
        ("Q", f"Point(0,2*{scale})"),
        ("S", f"Point(-2*{scale},0)"),
        ("G", "Circumcircle(P,Q,S)"),
        ("B", f"Point(2*{scale}-2*r,r)"),
        ("C", "Circle(B,r)"),
    )
    equations = (("Distance(B,Center(G))", "Radius(G)-r"),)
    plans = positive_radius_contact_plans(("r",), definitions, equations)
    assert len(plans) == 1 and plans[0][0] == "r"
    altered = tuple(
        (n, f"Point(2*{scale}+1e-450,0)") if n == "P" else (n, e) for n, e in definitions
    )
    assert positive_radius_contact_plans(("r",), altered, equations) == ()


@pytest.mark.parametrize(
    "polynomial",
    [
        (Fraction(1), Fraction(10**400)),
        (Fraction(1, 10**200), Fraction(10**200), Fraction(1)),
    ],
)
def test_nonzero_root_float_underflow_declines_finite_enumeration(polynomial):
    assert _square_root_points(polynomial, 0) is None


def test_rational_root_boxes_bind_distinct_irrational_roots_exactly():
    from geosolver.engine.standard.search.discrete.square_difference import _root_boxes

    roots = {-(2**0.5): 2, 2**0.5: 2}
    boxes = _root_boxes((Fraction(0), Fraction(0), Fraction(1)), roots)
    assert boxes is not None and len(boxes) == 2
    intervals = [(Fraction(box[0][0]), Fraction(box[0][1])) for box in boxes]
    assert intervals[0][1] < intervals[1][0]
    for lower, upper in intervals:
        assert (lower * lower - 2) * (upper * upper - 2) <= 0
    assert _root_boxes((Fraction(0), Fraction(0), Fraction(1)), {0.0: 2}) is None


@pytest.mark.parametrize(
    "source",
    [
        "0/(x-1)",
        "0*sqrt(1-x)",
        "0*Distance(Point(x,0),Point(1,0))",
    ],
)
def test_zero_prefactors_never_erase_non_equivariant_domains(source):
    assert chart(answer=f"({source})+x/x") is None


def test_coincident_circle_contact_is_only_a_necessary_optimizer_equation():
    from mpmath import mp

    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source
    from geosolver.problem.adapter import to_engine_document

    definitions = (
        ("P", "Point(0,0)"),
        ("C", "Circle(Point(0,2),2)"),
        ("D", "Circle(Point(h,2),2)"),
    )
    equations = (("OnCircle(P,C)", "0"), ("OnCircle(P,D)", "0"), ("IsTangent(C,D)", "0"))
    assert contact_tangency_source("C", "D", definitions, equations) is not None
    problem = GeometryProblem.model_validate(
        {
            "id": "coincident-contact-counterexample",
            "variables": ["h"],
            "constructions": [{"name": n, "expression": e} for n, e in definitions],
            "conditions": [{"left": a, "operator": "=", "right": b} for a, b in equations],
            "target": "h",
        }
    )
    evaluator = build_ir_evaluator(load_problem_bundle(to_engine_document(problem)))
    assert not verify_final_candidate(evaluator=evaluator, values=(mp.mpf(0),)).verified


def test_unused_circle_still_excludes_zero_radius_in_original_final_domain():
    from mpmath import mp

    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.adapter import to_engine_document

    # The contact equality alone has both roots r=0 and r=1. The declared
    # Circle(B,r), even if unused by that equality, makes r=0 inadmissible.
    definitions = (
        ("P", "Point(2,0)"),
        ("Q", "Point(0,2)"),
        ("S", "Point(-2,0)"),
        ("G", "Circumcircle(P,Q,S)"),
        ("B", "Point(2-2*r,r)"),
        ("unused", "Circle(B,r)"),
    )
    problem = GeometryProblem.model_validate(
        {
            "id": "unused-positive-domain-counterexample",
            "variables": ["r"],
            "constructions": [{"name": n, "expression": e} for n, e in definitions],
            "conditions": [
                {"left": "Distance(B,Center(G))", "operator": "=", "right": "Radius(G)-r"}
            ],
            "target": "r",
        }
    )
    evaluator = build_ir_evaluator(load_problem_bundle(to_engine_document(problem)))
    assert not verify_final_candidate(evaluator=evaluator, values=(mp.mpf(0),)).verified
    assert verify_final_candidate(evaluator=evaluator, values=(mp.mpf(1),)).verified
