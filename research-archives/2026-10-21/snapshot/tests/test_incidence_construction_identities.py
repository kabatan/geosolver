import pytest

from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.incidence_residuals import necessary_incidence_residuals


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "point",
    [
        "ContactPoint(circle,line)",
        "ContactPoint(line,circle)",
        "FootOfPerpendicular(O,line)",
        "Midpoint(A,B)",
        "A",
    ],
)
def test_constructed_incidence_does_not_add_a_cancellation_noise_equation(point, reverse):
    definitions = (
        ("A", "Point(u,1)"),
        ("B", "Point(2,v)"),
        ("O", "Point(u,v)"),
        ("line", "Line(B,A)" if reverse else "Line(A,B)"),
        ("circle", "Circle(O,3)"),
        ("P", point),
        ("Q", "P"),
    )
    assert necessary_incidence_residuals("OnSegment(Q,A,B)", definitions) == ()


@pytest.mark.parametrize("logical", [False, True])
def test_lowering_keeps_original_endpoint_check_in_each_logical_branch(logical):
    constructions = [
        ("A", "Point(0,0)"),
        ("B", "Point(u,v)"),
        ("O", "Point(2,3)"),
        ("line", "Line(A,B)"),
        ("circle", "Circle(O,4)"),
        ("P", "ContactPoint(circle,line)"),
    ]
    condition = (
        {"predicate": "Or(OnSegment(P,A,B)==0,OnSegment(O,A,B)==0)"}
        if logical
        else {"left": "OnSegment(P,A,B)", "operator": "=", "right": 0}
    )
    problem = GeometryProblem.model_validate(
        {
            "id": "projection-incidence",
            "variables": ["u", "v"],
            "constructions": [{"name": a, "expression": b} for a, b in constructions],
            "conditions": [condition],
            "target": "Distance(O,P)",
        }
    )
    bundle = load_problem_bundle(problem.engine_document())
    if logical:
        clauses = bundle.spec.logical_plans[0].clauses
        assert len(clauses[0]) == 1
        assert len(clauses[1]) == 2
        assert "OnSegment(P" in clauses[0][0]
    else:
        assert len(bundle.spec.constraints) == 1
        assert "OnSegment" in bundle.spec.constraints[0]


def test_similar_decimal_endpoints_are_not_identified_after_float_rounding():
    definitions = (
        ("A", "Point(0,0)"),
        ("B", "Point(0.100000000000000000001,1)"),
        ("C", "Point(0.100000000000000000002,1)"),
        ("circle", "Circle(A,2)"),
        ("P", "ContactPoint(circle,Line(A,B))"),
    )
    assert necessary_incidence_residuals("OnSegment(P,A,C)", definitions)


def test_unrelated_line_and_unknown_contact_overload_keep_supplement():
    definitions = (
        ("A", "Point(0,0)"),
        ("B", "Point(1,1)"),
        ("C", "Point(2,3)"),
        ("P", "ContactPoint(C,Line(A,B))"),
    )
    assert necessary_incidence_residuals("OnSegment(P,A,B)", definitions)
    definitions = (
        *definitions[:-1],
        ("circle", "Circle(A,2)"),
        ("P", "ContactPoint(circle,Line(A,C))"),
    )
    assert necessary_incidence_residuals("OnSegment(P,A,B)", definitions)
