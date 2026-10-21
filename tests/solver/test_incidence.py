"""Incidence contracts and numerical regressions."""

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.incidence_residuals import (
    augment_incidence_clauses,
    lower_incidence_equalities,
    necessary_incidence_residuals,
)


def evaluator(scale="1", logical=False, rotate=False):
    def point(a, b):
        a, b = (-b, a) if rotate else (a, b)
        return f"Point(({a})*({scale}),({b})*({scale}))"

    constraints = [
        f"OnSegment(P,{point(-4, 2)},{point(5, 2)})",
        f"OnSegment(P,{point(1, -3)},{point(1, 6)})",
    ]
    conditions = (
        [{"predicate": "And(" + ",".join(f"({source})==0" for source in constraints) + ")"}]
        if logical
        else [{"left": source, "operator": "=", "right": 0} for source in constraints]
    )
    p = GeometryProblem.model_validate(
        {
            "id": "independent-incidence",
            "variables": ["u", "v"],
            "constructions": [{"name": "P", "expression": "Point(u,v)"}],
            "conditions": conditions,
            "target": "Distance(Point(0,0),P)",
        }
    )
    return build_ir_evaluator(load_problem_bundle(p.engine_document()))


@pytest.mark.parametrize("scale", ["1e-12", "1", "1e12"])
@pytest.mark.parametrize("logical", [False, True])
@pytest.mark.parametrize("rotate", [False, True])
def test_original_segment_residuals_remain_and_full_precision_verifies(scale, logical, rotate):
    ev = evaluator(scale, logical, rotate)
    if logical:
        assert any("OnSegment" in s for p in ev.bundle.spec.logical_plans for s in p.leaves)
        assert ev.bundle.spec.logical_plans[0].width == 4
    else:
        assert sum("OnSegment" in source for source in ev.bundle.spec.constraints) == 2
        assert len(ev.bundle.spec.constraints) == 4
    with mp.workdps(220):
        s = mp.mpf(scale)
        point = (mp.mpf(-2) * s, s) if rotate else (s, mp.mpf(2) * s)
        result = verify_final_candidate(evaluator=ev, values=point)
        assert result.verified


def test_collinearity_alone_cannot_admit_a_point_outside_the_segment():
    p = GeometryProblem.model_validate(
        {
            "id": "outside-segment",
            "variables": ["u"],
            "constructions": [{"name": "P", "expression": "Point(u,0)"}],
            "conditions": [
                {"left": "OnSegment(P,Point(0,0),Point(2,0))", "operator": "=", "right": 0},
                {"left": "u", "operator": ">", "right": 2},
            ],
            "target": "u",
        }
    )
    ev = build_ir_evaluator(load_problem_bundle(p.engine_document()))
    assert len(ev.bundle.spec.constraints) == 2
    with mp.workdps(220):
        assert not verify_final_candidate(evaluator=ev, values=(mp.mpf(3),)).verified


@pytest.mark.parametrize(
    "source", ["OnSegment(P,A,B)", "-7*(OnSegment(P,A,B)-0)", "(0-OnSegment(P,A,B))/3"]
)
def test_nonzero_rational_rewrites_produce_the_same_necessary_equation(source):
    assert necessary_incidence_residuals(source) == necessary_incidence_residuals(
        "OnSegment(P,A,B)"
    )


@pytest.mark.parametrize(
    "source", ["OnSegment(P,A,B)-1", "0*OnSegment(P,A,B)", "x*OnSegment(P,A,B)", "Distance(P,A)"]
)
def test_no_consequence_without_a_proven_segment_zero(source):
    assert necessary_incidence_residuals(source) == ()


def test_augmentation_is_idempotent_and_caps_optional_logical_growth():
    ev = evaluator()
    assert lower_incidence_equalities(ev.bundle.spec) == ev.bundle.spec
    clause = tuple(f"OnSegment(P{i},A,B)" for i in range(16))
    assert augment_incidence_clauses((clause,)) == (clause,)


def test_degenerate_segment_retains_original_point_distance():
    p = GeometryProblem.model_validate(
        {
            "id": "degenerate-segment",
            "variables": ["u"],
            "constructions": [{"name": "P", "expression": "Point(u,0)"}],
            "conditions": [
                {"left": "OnSegment(P,Point(0,0),Point(0,0))", "operator": "=", "right": 0}
            ],
            "target": "u",
        }
    )
    ev = build_ir_evaluator(load_problem_bundle(p.engine_document()))
    assert len(ev.bundle.spec.constraints) == 1
    with mp.workdps(220):
        assert not verify_final_candidate(evaluator=ev, values=(mp.mpf(1),)).verified


def test_original_long_decimal_tokens_survive_derived_equations():
    source = "OnSegment(Point(0.1000000000000000000000001,y), Point(0,0), Point(1,0))"
    (extra,) = necessary_incidence_residuals(source)
    assert "0.1000000000000000000000001" in extra
