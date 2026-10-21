"""Contacts contracts and numerical regressions."""

import ast
import time
from fractions import Fraction

import pytest
from mpmath import mp

from geosolver import GeometryProblem, solve
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.positive_radius_contacts import (
    positive_radius_contact_plans,
    positive_radius_contact_sources,
)
from geosolver.engine.standard.problem.tangency_contacts import (
    contact_tangency_source,
    distance_contact_sources,
)
from geosolver.engine.standard.problem.zero_test_source import rational_constant, zero_test_call
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.expression_source import annotate_source
from geosolver.problem.incidence_residuals import necessary_incidence_residuals
from geosolver.runtime.deadline import runtime_session


def test_inner_tangent_public_answer():
    problem = GeometryProblem(
        id="inner-tangent",
        variables=[],
        conditions=[],
        constructions=[
            {"name": "P", "expression": "Intersect(Circle(Point(0,0),1),Circle(Point(1,0),2))"}
        ],
        target="Distance(P,Point(1,0))",
    )
    result = solve(problem)
    assert result.answers[0].minimal_polynomial == ["1", "-2"]


def construction(scale):
    return (
        ("B", f"Point({2 * scale},0)"),
        ("P", f"Point(0,{2 * scale})"),
        ("Q", f"Point({-2 * scale},0)"),
        ("G", "Circumcircle(B,P,Q)"),
        ("C", "Point(B.x-2*r,B.y+r)"),
        ("D", "Circle(C,r)"),
    )


@pytest.mark.parametrize("scale", [1, 3, 9])
def test_positive_radius_deflation_escapes_zero_radius_branch(scale):
    definitions = construction(scale)
    equalities = (("Distance(C,Center(G))", "Radius(G)-r"),)
    assert len(positive_radius_contact_sources(("r",), definitions, equalities)) == 1
    problem = {
        "id": "internal-contact-family",
        "variables": ["r"],
        "constructions": [{"name": n, "expression": e} for n, e in definitions],
        "conditions": [{"left": a, "operator": "=", "right": b} for a, b in equalities],
        "target": "r",
    }
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    candidate = FloatCandidate(
        (1e-8,), 0, 0, True, EvaluationStatus.OK, 0, 0, 0, hard_feasible=True
    )
    result = MpmathRefiner().refine_candidates(
        bundle=bundle, evaluator=evaluator, candidates=(candidate,)
    )
    assert len(result.candidates) == 1
    refined = result.candidates[0]
    with mp.workdps(100):
        assert abs(refined.answer_hp - scale) < mp.mpf("1e-70")
    assert verify_final_candidate(evaluator=evaluator, values=refined.x_hp).verified


@pytest.mark.parametrize(
    "change",
    [
        ("C", "Point(B.x-2*r*r,B.y+r)"),
        ("C", "Point(B.x+1-2*r,B.y+r)"),
        ("D", "Circle(C,0)"),
        ("D", "CircleThroughPoint(C,B)"),
        ("G", "Circumcircle(Point(B.x+r,B.y),P,Q)"),
    ],
)
def test_unproven_affinity_positive_radius_or_incidence_does_not_add_equations(change):
    definitions = tuple(change if n == change[0] else (n, e) for n, e in construction(2))
    assert (
        positive_radius_contact_sources(
            ("r",), definitions, (("Distance(C,Center(G))", "Radius(G)-r"),)
        )
        == ()
    )


def test_tangency_without_the_explicit_internal_gap_is_not_deflated():
    assert (
        positive_radius_contact_sources(("r",), construction(2), (("IsTangent(D,G)", "0"),)) == ()
    )


def bundle(problem):
    return load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))


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


def test_circle_circle_tangency_has_a_resolved_refinement_derivative():
    from geosolver.engine.standard.refinement.finite_difference_jacobian import (
        compute_finite_difference_jacobian,
    )
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner

    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "c1", "expr": "Circle(Point(0,0),1)"},
                    {"name": "c2", "expr": "Circle(Point(x,0),1)"},
                ],
                "constraints": ["IsTangent(c1,c2)"],
                "answer": "x",
            }
        )
    )
    refiner = MpmathRefiner()
    with mp.workdps(180), runtime_session(time.monotonic() + 5):
        point = [mp.mpf(2) + mp.mpf("1e-50")]

        def residual(values, dps):
            return refiner._residual_vector_for_stage(
                ev.bundle, ev, values, dps, smooth_zero_constraints=True
            )

        jacobian = compute_finite_difference_jacobian(point=point, dps=120, residual_fn=residual)
        assert abs(jacobian[0][0] - 1) < mp.mpf("1e-70")


@pytest.mark.parametrize("precision", [40, 120, 250])
def test_native_tangent_uses_constructed_incidence_not_a_numeric_tolerance(precision):
    from geosolver.errors import NoIntersectionError
    from geosolver.geometry.mp.mp_api_common_wrappers import MP_Circumcircle
    from geosolver.geometry.mp.mp_api_geometry import MP_Tangent
    from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint
    from geosolver.geometry.mp.mp_parametric_points import mp_point_on_circle

    with mp.workdps(precision):
        vertices = [MPPoint(0, 0), MPPoint(3, 0), MPPoint(1, 2)]
        circle = MP_Circumcircle(*vertices)
        for point in (*vertices, mp_point_on_circle(circle, mp.mpf("0.123"))):
            first, second = (MP_Tangent(point, circle, branch) for branch in (True, False))
            assert (first.a, first.b, first.c) == (second.a, second.b, second.c)
        unit = MPCircle(MPPoint(0, 0), 1)
        near_inside = MPPoint(1 - mp.power(10, -precision + 10), 0)
        with pytest.raises(NoIntersectionError):
            MP_Tangent(near_inside, unit)
        point = mp_point_on_circle(unit, 0)
        point.x -= mp.power(10, -precision + 10)
        with pytest.raises(NoIntersectionError):
            MP_Tangent(point, unit)  # Mutation invalidates the incidence witness.


def test_numeric_contact_selector_has_float_hp_parity_and_rejects_unknown_side():
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )

    with mp.workdps(80):
        for context, index in [
            (_get_geometry_context(), 0),
            (_get_high_precision_context(80), mp.mpf(0)),
        ]:
            vertices = [context["Point"](0, 0), context["Point"](4, 0), context["Point"](0, 3)]
            named = context["IncircleContactPoint"](*vertices, "BC")
            numeric = context["IncircleContactPoint"](*vertices, index)
            assert named.x == numeric.x and named.y == numeric.y
            for invalid in [True, 3, "not-a-side"]:
                with pytest.raises(ValueError):
                    context["IncircleContactPoint"](*vertices, invalid)


def test_exclude_lowering_requires_an_incidence_proof():
    from geosolver.problem.construction_contracts import _lower

    items = (
        ("A", "Point(0,0)"),
        ("B", "Point(2,0)"),
        ("P", "Point(3,0)"),
        ("omega", "Circle(A,1)"),
        ("ell", "Line(A,B)"),
        ("Q", "Intersect(ell,omega,exclude=P)"),
    )
    lowered, guards, evidence = _lower(items, ())
    assert not guards and not evidence
    assert "exclude" in lowered[-1][1]


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
