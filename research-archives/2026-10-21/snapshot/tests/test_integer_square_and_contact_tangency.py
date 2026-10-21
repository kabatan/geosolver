"""General integer-square and constructed-contact counterexamples."""

import math

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source
from geosolver.engine.standard.problem.zero_test_source import zero_test_call
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.engine.standard.search.discrete.square_difference import finite_integer_square_roots
from geosolver.problem.adapter import to_engine_document


def bundle(problem):
    return load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))


@pytest.mark.parametrize("offsets", [(3, 1), (8, 5), (17, 4), (15, 6)])
@pytest.mark.parametrize("representation", [0, 1])
def test_integer_square_difference_finds_outlying_integer_lengths(offsets, representation):
    a, b = offsets
    variable = "t" if representation else "x"
    conditions = [
        {"left": f"IsInteger(sqrt({variable}**2+{a * a}))", "operator": "=", "right": 0},
        {"left": f"IsInteger(sqrt({variable}**2+{b * b}))", "operator": "=", "right": 0},
    ]
    if representation:
        conditions = [
            {"left": "-7*(" + c["left"] + ")", "operator": "=", "right": 0}
            for c in reversed(conditions)
        ]
        conditions.append({"left": "0", "operator": "=", "right": 0})
    problem = {
        "id": "general-square-pair",
        "variables": [variable],
        "constructions": [],
        "conditions": conditions,
        "target": variable,
    }
    roots, difference = finite_integer_square_roots(bundle(problem))
    assert abs(difference) == a * a - b * b
    # Enumerate a separately derived finite integer length range. m-n >= 1
    # implies m+n <= |N|, hence m <= (|N|+1)/2.
    expected = set()
    for m in range((a * a - b * b + 1) // 2 + 1):
        square = m * m - a * a
        if square < 0:
            continue
        n2 = square + b * b
        if math.isqrt(n2) ** 2 == n2:
            expected.update((-math.sqrt(square), math.sqrt(square)))
    assert {round(x[0], 10) for x in roots} == {round(x, 10) for x in expected}


def test_equal_integer_squares_do_not_claim_finite_enumeration():
    problem = {
        "id": "equal-squares",
        "variables": ["x"],
        "constructions": [],
        "conditions": [
            {"left": "IsInteger(x)", "operator": "=", "right": 0},
            {"left": "IsInteger(-x)", "operator": "=", "right": 0},
        ],
        "target": "x",
    }
    assert finite_integer_square_roots(bundle(problem)) is None


@pytest.mark.parametrize(
    "source", ["0*IsInteger(x)", "x*IsInteger(x)", "IsInteger(x)+1", "IsInteger(x)/x"]
)
def test_zero_wrappers_do_not_drop_additional_root_sets(source):
    assert zero_test_call(source) is None


@pytest.mark.parametrize("scale", [1, 3, 7])
@pytest.mark.parametrize("representation", [0, 1])
def test_known_contact_tangency_refines_to_high_precision(scale, representation):
    names = ("P", "Q", "S", "L", "C") if not representation else ("E", "F", "G", "N", "W")
    p, q, s, line, circle = names
    conditions = [{"left": f"IsTangent({line},{circle})", "operator": "=", "right": 0}]
    if representation:
        conditions = [
            {"left": "0", "operator": "=", "right": 0},
            {"left": f"-7*IsTangent({circle},{line})", "operator": "=", "right": 0},
        ]
    b = bundle(
        {
            "id": "contact-circle-family",
            "variables": ["t"],
            "constructions": [
                {"name": p, "expression": "Point(0,0)"},
                {"name": q, "expression": f"Point({3 * scale},{scale})"},
                {"name": s, "expression": f"Point({4 * scale},t)"},
                {"name": line, "expression": f"Line({p},Point({scale},0))"},
                {"name": circle, "expression": f"Circumcircle({p},{q},{s})"},
            ],
            "conditions": conditions,
            "target": "t",
        }
    )
    evaluator = build_ir_evaluator(b)
    candidate = FloatCandidate(
        (2.01 * scale,), 0, 0, True, EvaluationStatus.OK, 0, 0, 0, hard_feasible=True
    )
    refined = MpmathRefiner().refine_candidates(
        bundle=b, evaluator=evaluator, candidates=(candidate,)
    )
    assert len(refined.candidates) == 1
    c = refined.candidates[0]
    with mp.workdps(100):
        assert abs(c.answer_hp - 2 * scale) < mp.mpf("1e-80")
    verification = verify_final_candidate(evaluator=evaluator, values=c.x_hp)
    assert verification.verified
    assert verification.answer_uncertainty < mp.mpf("1e-60")


def test_unproven_incidence_is_not_rewritten():
    constructions = (
        ("P", "Point(0,0)"),
        ("Q", "Point(1,1)"),
        ("R", "Point(0,2)"),
        ("L", "Line(P,Q)"),
        ("C", "Circle(R,1)"),
    )
    assert contact_tangency_source("L", "C", constructions) is None


@pytest.mark.parametrize("scale", [1, 3, 11])
@pytest.mark.parametrize("incidence", ["on_circle", "distance"])
@pytest.mark.parametrize("contact_kind", ["line_circle", "circle_circle"])
def test_equality_proven_contacts_have_simple_refinement(scale, incidence, contact_kind):
    # Both circles pass through P at the true contact. The first circle's
    # incidence is constructed; the second circle's incidence is an equality.
    constructions = [
        {"name": "P", "expression": "Point(0,0)"},
        {
            "name": "C",
            "expression": f"Circumcircle(P,Point({2 * scale},{2 * scale}),Point(0,{4 * scale}))",
        },
        {"name": "O", "expression": f"Point(h,{3 * scale})"},
        {"name": "D", "expression": f"Circle(O,{3 * scale})"},
        {"name": "L", "expression": f"Line(P,Point({scale},0))"},
    ]
    if incidence == "distance":
        conditions = [{"left": "Distance(O,P)", "operator": "=", "right": 3 * scale}]
    else:
        conditions = [{"left": "-7*OnCircle(P,D)", "operator": "=", "right": 0}]
    if contact_kind == "circle_circle":
        conditions.append({"left": "-7*IsTangent(D,C)", "operator": "=", "right": 0})
    else:
        conditions.append({"left": "-7*IsTangent(D,L)", "operator": "=", "right": 0})
    conditions.reverse()
    b = bundle(
        {
            "id": "equality-contact-family",
            "variables": ["h"],
            "constructions": constructions,
            "conditions": conditions,
            "target": "h",
        }
    )
    evaluator = build_ir_evaluator(b)
    candidate = FloatCandidate(
        (0.01 * scale,), 0, 0, True, EvaluationStatus.OK, 0, 0, 0, hard_feasible=True
    )
    refined = MpmathRefiner().refine_candidates(
        bundle=b, evaluator=evaluator, candidates=(candidate,)
    )
    assert len(refined.candidates) == 1
    c = refined.candidates[0]
    with mp.workdps(100):
        assert abs(c.answer_hp) < mp.mpf("1e-80")
    assert verify_final_candidate(evaluator=evaluator, values=c.x_hp).verified


def test_intersection_and_line_equality_prove_a_contact_without_endpoint_matching():
    constructions = (
        ("C", "Circle(Point(0,2),2)"),
        ("P", "Intersect(C,Line(Point(0,0),Point(0,1)),near=Point(0,0))"),
        ("L", "Line(Point(-2,t),Point(2,t))"),
    )
    assert contact_tangency_source("L", "C", constructions, (("OnLine(P,L)", "0"),)) is not None
    assert contact_tangency_source("L", "C", constructions) is None


def test_a_shared_point_is_required_for_circle_circle_rewrite():
    constructions = (("C", "Circle(Point(0,2),2)"), ("D", "Circle(Point(h,3),3)"))
    assert contact_tangency_source("C", "D", constructions) is None


@pytest.mark.parametrize("scale", [1, 4, 13])
@pytest.mark.parametrize("reverse", [False, True])
def test_distance_to_line_radius_contact_refines_without_a_double_root(scale, reverse):
    constructions = [
        {"name": "P", "expression": "Point(0,0)"},
        {"name": "O", "expression": f"Point(h,{2 * scale})"},
        {"name": "C", "expression": f"Circle(O,{2 * scale})"},
        {"name": "L", "expression": f"Line(P,Point({scale},0))"},
    ]
    distance = "Distance(L,O)" if reverse else "Distance(O,L)"
    conditions = [
        {"left": "OnCircle(P,C)", "operator": "=", "right": 0},
        {"left": distance, "operator": "=", "right": 2 * scale},
    ]
    b = bundle(
        {
            "id": "distance-contact-family",
            "variables": ["h"],
            "constructions": constructions,
            "conditions": conditions,
            "target": "h",
        }
    )
    evaluator = build_ir_evaluator(b)
    candidate = FloatCandidate(
        (0.01 * scale,), 0, 0, True, EvaluationStatus.OK, 0, 0, 0, hard_feasible=True
    )
    refined = MpmathRefiner().refine_candidates(
        bundle=b, evaluator=evaluator, candidates=(candidate,)
    )
    assert len(refined.candidates) == 1
    c = refined.candidates[0]
    with mp.workdps(100):
        assert abs(c.answer_hp) < mp.mpf("1e-80")
    assert verify_final_candidate(evaluator=evaluator, values=c.x_hp).verified


def test_unrelated_radius_does_not_claim_a_distance_contact():
    from geosolver.engine.standard.problem.tangency_contacts import distance_contact_sources

    constructions = (
        ("P", "Point(0,0)"),
        ("O", "Point(h,2)"),
        ("C", "Circle(O,2)"),
        ("L", "Line(P,Point(1,0))"),
    )
    assert (
        distance_contact_sources(constructions, (("OnCircle(P,C)", "0"), ("Distance(O,L)", "3")))
        == {}
    )


@pytest.mark.parametrize("translation,offsets", [(10**100, (4, 1)), (10**400, (3, 1))])
def test_unrepresentable_distinct_integer_square_seeds_fall_back(translation, offsets):
    a, b = offsets
    shifted = f"(x-({translation}))"
    problem = {
        "id": "large-translation-family",
        "variables": ["x"],
        "constructions": [],
        "conditions": [
            {"left": f"IsInteger(sqrt({shifted}**2+{a * a}))", "operator": "=", "right": 0},
            {"left": f"IsInteger(sqrt({shifted}**2+{b * b}))", "operator": "=", "right": 0},
        ],
        "target": "x",
    }
    assert finite_integer_square_roots(bundle(problem)) is None
