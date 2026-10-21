"""Compact logical residuals preserve original branch choice and source literals."""

import itertools
import random
import time

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.logical_vectors import LogicalVector
from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.evaluation_trace import capture_calls
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.logical_equalities import LogicalEqualityPlan
from geosolver.runtime.deadline import runtime_session


def expanded_components(plan):
    """Independent reference: the old nested conditional, in its original order."""
    scores = [
        "max(" + ",".join(f"abs({s})" for s in clause) + ")"
        if len(clause) > 1
        else f"abs({clause[0]})"
        for clause in plan.clauses
    ]
    result = []
    for column in range(plan.width):
        source = plan.clauses[-1][column] if column < len(plan.clauses[-1]) else "0"
        for i in reversed(range(len(plan.clauses) - 1)):
            condition = " and ".join(f"({scores[i]})<=({other})" for other in scores[i + 1 :])
            value = plan.clauses[i][column] if column < len(plan.clauses[i]) else "0"
            source = f"({value}) if ({condition}) else ({source})"
        result.append(source)
    return result


@pytest.mark.parametrize("precision", [15, 80, 180])
def test_compact_residuals_match_conditional_reference_with_ties_and_padding(precision):
    plan = LogicalEqualityPlan((("x", "y"), ("-x",), ("y-x", "y+1e-110")))
    generator = random.Random(831)
    points = list(itertools.product((-1, 0, 1), repeat=2)) + [
        (generator.uniform(-3, 3), generator.uniform(-3, 3)) for _ in range(12)
    ]
    with mp.workdps(precision), high_precision_mode():
        context = _get_high_precision_context(precision)
        for x, y in points:
            context.update(x=mp.mpf(str(x)), y=mp.mpf(str(y)))
            vector = LogicalVector(plan, dict(context))
            expected = [safe_eval_expr_hp(source, context) for source in expanded_components(plan)]
            assert [vector[i] for i in range(plan.width)] == expected


@pytest.mark.parametrize("x,y", [("nan", "0"), ("0", "nan"), ("inf", "2")])
def test_nonfinite_comparison_order_is_preserved(x, y):
    plan = LogicalEqualityPlan((("x",), ("y",), ("2",)))
    with mp.workdps(80), high_precision_mode():
        context = {**_get_high_precision_context(80), "x": mp.mpf(x), "y": mp.mpf(y)}
        expected = safe_eval_expr_hp(expanded_components(plan)[0], context)
        actual = LogicalVector(plan, context)[0]
        assert actual == expected or (mp.isnan(actual) and mp.isnan(expected))


def test_logical_leaves_are_evaluated_once_and_evidence_is_stable():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(x,0)"},
                ],
                "guards": ["Or(And(Distance(A,B)==1,x==1),And(Distance(A,B)==2,x==2))"],
                "answer": "x",
            }
        )
    )
    with runtime_session(time.monotonic() + 5) as timings:
        first = ev.evaluate_float_residual([1.2])
        count = timings.counters["logical_leaf_evaluations"]
        assert count == len(ev.bundle.spec.logical_plans[0].leaves)
        with capture_calls() as calls1, capture_selection_trace() as trace1:
            assert ev.evaluate_float_residual([1.2]) == first
        with capture_calls() as calls2, capture_selection_trace() as trace2:
            assert ev.evaluate_float_residual([1.2]) == first
        assert timings.counters["logical_leaf_evaluations"] == count
        assert calls1 == calls2 and trace1 == trace2
        assert ev.evaluate_float_residual([1.3]).is_finite
        assert timings.counters["logical_leaf_evaluations"] == 2 * count


def test_logical_inline_intersections_keep_branch_trace_after_cache_hits():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "A", "expr": "Point(-2,x)"},
                    {"name": "B", "expr": "Point(2,x)"},
                    {"name": "omega", "expr": "Circle(Point(0,0),1)"},
                ],
                "guards": ["Or(Intersect(Line(A,B),omega,n=1).x==-1,x==1)"],
                "answer": "x",
            }
        )
    )
    with mp.workdps(120), high_precision_mode(), evaluation_session(ev):
        snap = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.1")], ev.bundle.base_context
        )
        context = snap.for_expressions(ev.bundle.spec.constraints)
        with capture_calls() as calls1, capture_selection_trace() as trace1:
            first = safe_eval_expr_hp(ev.bundle.spec.constraints[0], context)
        with capture_calls() as calls2, capture_selection_trace() as trace2:
            second = safe_eval_expr_hp(ev.bundle.spec.constraints[0], context)
        assert first == second
        assert trace1 and trace1 == trace2 and calls1 == calls2


def test_logical_dependencies_reach_bounds_and_angle_policy():
    from geosolver.engine.standard.refinement.mpmath_refiner import _problem_contains_call
    from geosolver.problem.domain_bounds import search_bounds

    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "construction": [
                    {"name": "A", "expr": "Point(x,0)"},
                    {"name": "B", "expr": "Point(0,1)"},
                    {"name": "C", "expr": "Point(0,0)"},
                ],
                "guards": ["Or(Angle(A,B,C)==45,x==-123)"],
                "answer": "y",
            }
        )
    )
    assert _problem_contains_call(ev.bundle.spec, "Angle")
    bounds = search_bounds(ev.bundle.spec)
    assert bounds[0] == (-246, 246) and bounds[1] == (-10, 10)
    assert ev.evaluation_store.plan.required(ev.bundle.spec.constraints) == ("A", "B", "C")
    with runtime_session(time.monotonic() + 5):
        assert all("x" in eq.names for eq in ev.verification_equations)


def test_single_logical_leaf_still_cancels_a_large_common_constant():
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate

    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "guards": ["x+1e600==x+1e600+1"],
                "answer": "x",
            }
        )
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 10):
        assert not verify_final_candidate(evaluator=ev, values=(mp.mpf(1),)).verified


def test_internal_logical_storage_does_not_shadow_a_legal_user_name():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["_logical_residuals"]},
                "guards": ["Or(_logical_residuals==1,_logical_residuals==2)"],
                "answer": "_logical_residuals",
            }
        )
    )
    for point in (1, 2):
        assert ev.evaluate_float_residual([point]).residual_vector == [0.0]
