import re

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.positive_radius_contacts import (
    positive_radius_contact_sources,
)
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.problem.adapter import to_engine_document


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


@pytest.mark.parametrize("scale", [1, 7, 19])
@pytest.mark.parametrize("renamed", [False, True])
@pytest.mark.parametrize("extra_equation", [False, True])
def test_radius_manifold_sampler_adds_contacts_and_preserves_original_starts(
    scale, renamed, extra_equation
):
    from geosolver.engine.standard.search.sampling.manifold import augment_with_manifold_samples
    from geosolver.engine.standard.search.sampling.positive_radius import (
        PositiveRadiusContactSampler,
    )

    radius, parameter = ("rho", "u") if renamed else ("r", "q")
    definitions = tuple(
        (name, re.sub(r"\br\b", radius, expression)) for name, expression in construction(scale)
    )
    definitions = tuple(
        (name, f"Point(B.x-2*{radius},B.y+{parameter}*{radius})")
        if name == "C"
        else (name, expression)
        for name, expression in definitions
    )
    problem = {
        "id": "varying-internal-contact-family",
        "variables": [parameter, radius],
        "constructions": [{"name": n, "expression": e} for n, e in definitions],
        "conditions": [
            {"left": "Distance(C,Center(G))", "operator": "=", "right": f"Radius(G)-{radius}"}
        ],
        "target": radius,
    }
    if extra_equation:
        problem["conditions"].append({"left": f"{parameter}**2", "operator": "=", "right": "2"})
    # Build original guards through the public condition schema.
    problem["conditions"].extend(
        [
            {"left": parameter, "operator": ">", "right": "1"},
            {"left": parameter, "operator": "<", "right": "2"},
        ]
    )
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    originals = tuple(
        FloatCandidate((q, 1e-8), 1, 1, False, EvaluationStatus.OK, 0, i, i)
        for i, q in enumerate((0.7, 1.3, 1.7))
    )
    merged, metrics = augment_with_manifold_samples(
        bundle=bundle,
        evaluator=evaluator,
        bounds=[(0.0, 3.0), (0.0, 2.0 * scale)],
        candidates=originals,
        metrics={},
        strategies=(PositiveRadiusContactSampler(),),
    )
    assert merged[: len(originals)] == originals
    assert len(merged) > len(originals)
    assert (
        metrics["manifold_sampling"]["positive_radius_contact_manifold"]["contact_plan_count"] == 1
    )
    for candidate in merged[len(originals) :]:
        q, r = candidate.x_float
        assert 1 < q < 2
        assert r == pytest.approx(4 * scale / (3 + q * q))
        assert (
            abs(evaluator.evaluate_float_residual(candidate.x_float).residual_vector[0])
            < 1e-10 * scale
        )
        assert evaluator.evaluate_guard(candidate.x_float)[0]

    if extra_equation:
        assert min(c.residual_norm_float for c in merged) < 1e-10
        best = min(merged, key=lambda c: c.residual_norm_float)
        assert best.x_float[0] == pytest.approx(2**0.5)
