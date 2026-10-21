"""Compilation contracts and numerical regressions."""

import itertools
import random
import time

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.logical_vectors import LogicalVector
from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.interpreter.guards.compile import (
    compile_guard_expr,
    guard_hard_satisfied,
    guard_violation_value,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.geometry.mp.mp_api_geometry import MP_IsInteger
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.compiler import ProblemCompileError, compile_problem, predicate_guard_source
from geosolver.problem.domain_bounds import search_bounds
from geosolver.problem.evaluation_trace import capture_calls
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.errors import IRValidationError
from geosolver.problem.ir.schema import IRSpec, IRVariableSpec
from geosolver.problem.logical_equalities import LogicalEqualityPlan
from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import validate
from geosolver.runtime.deadline import runtime_session
from tests.paths import REPO_ROOT


def _precision_evaluator(constraints, *, construction=(), guards=(), answer="x"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": list(construction),
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


def test_irrational_guard_limits_constrain_search_without_changing_exact_guards():
    import math

    import sympy as sp

    from geosolver.problem.domain_bounds import mathematical_bounds, search_bounds

    ev = _precision_evaluator(["sin(x)-12*pi/180"], guards=["x>0", "Not(x>=pi/4)"])
    domain = mathematical_bounds(ev.bundle.spec)["x"]
    assert domain.upper == sp.pi / 4 and not domain.upper_closed
    lo, hi = search_bounds(ev.bundle.spec)[0]
    assert lo == 0 and math.pi / 4 <= hi < math.pi / 4 + 1e-15
    ev = _precision_evaluator(["x*x-2"], guards=["x/(-sqrt(2))>-1", "x>0"])
    assert mathematical_bounds(ev.bundle.spec)["x"].upper == sp.sqrt(2)


def test_aime_2015_search_box_does_not_discard_pi_bounds():
    import math

    from geosolver.problem.domain_bounds import search_bounds

    path = REPO_ROOT / "benchmarks/dsl/AIME-2015-I-06.json"
    problem = GeometryProblem.model_validate_json(path.read_text())
    ev = build_ir_evaluator(load_problem_bundle(problem.engine_document()))
    bounds = search_bounds(ev.bundle.spec)
    assert bounds[0][0] == bounds[1][0] == 0
    assert abs(bounds[0][1] - math.pi / 4) < 1e-15
    assert abs(bounds[1][1] - math.pi / 5) < 1e-15
    from geosolver.engine.standard.refinement.mpmath_refiner import _convert_problem_bounds

    hp_bounds = _convert_problem_bounds(ev.bundle)
    with mp.workdps(500):
        assert abs(hp_bounds[0][1] - mp.pi / 4) < mp.mpf("1e-490")
        assert abs(hp_bounds[1][1] - mp.pi / 5) < mp.mpf("1e-490")


def test_public_solve_carries_irrational_bounds_through_refinement():
    from geosolver import solve

    problem = GeometryProblem(
        id="irrational-bound-pipeline",
        variables=["x"],
        constructions=[],
        conditions=[
            {"left": "x", "operator": "=", "right": "pi/6"},
            {"left": "x", "operator": ">", "right": 0},
            {"left": "x", "operator": "<", "right": "pi/4"},
        ],
        target="6*x/pi",
    )
    result = solve(problem)
    assert result.status == "solved", result.error
    assert result.answers[0].value.minimal_polynomial == ["1", "-1"]


def _problem(predicate: str, *, target: str = "x") -> GeometryProblem:
    return GeometryProblem(
        id="compile",
        variables=["x"],
        constructions=[],
        conditions=[{"predicate": predicate}],
        target=target,
    )


def test_chained_comparison_is_lowered_to_explicit_and() -> None:
    compiled = compile_problem(_problem("0 < x < 1"))
    condition = compiled.conditions[0]
    source = predicate_guard_source(condition.expression)  # type: ignore[union-attr]

    assert source == "And(0 < x, x < 1)"
    assert to_engine_document(_problem("0 < x < 1"))["guards"] == ["Assume(And(0 < x, x < 1))"]


def test_residual_function_cannot_be_used_as_boolean_predicate() -> None:
    with pytest.raises(ProblemCompileError) as caught:
        compile_problem(_problem("OnLine(Point(0, 0), Line(Point(0, 0), Point(1, 0)))"))

    assert caught.value.code == "predicate_not_boolean"
    report = validate(_problem("OnLine(Point(0, 0), Line(Point(0, 0), Point(1, 0)))"))
    assert not report.valid
    assert report.issues[-1].code == "predicate_not_boolean"


def test_macros_are_expanded_before_engine_execution() -> None:
    problem = GeometryProblem(
        id="macro",
        variables=[],
        constructions=[
            {"name": "A", "expression": "Point(0, 0)"},
            {"name": "B", "expression": "Point(1, 0)"},
            {"name": "C", "expression": "Point(0, 0)"},
            {"name": "D", "expression": "Point(2, 0)"},
        ],
        conditions=[],
        target="Ratio(A, B, C, D)",
    )

    assert to_engine_document(problem)["answer"] == "Distance(A, B) / Distance(C, D)"


def test_intersection_selectors_are_mutually_exclusive_and_one_based() -> None:
    invalid = GeometryProblem(
        id="selectors",
        variables=[],
        constructions=[
            {"name": "A", "expression": "Point(0, 0)"},
            {"name": "B", "expression": "Point(1, 0)"},
            {"name": "line", "expression": "Line(A, B)"},
            {"name": "circle", "expression": "Circle(A, 1)"},
            {
                "name": "P",
                "expression": "Intersect(line, circle, n=0, near=A)",
            },
        ],
        conditions=[],
        target="Distance(A, B)",
    )

    report = validate(invalid)
    assert {issue.code for issue in report.issues} >= {
        "conflicting_selectors",
        "invalid_selector",
    }


def _integer_context(value: str) -> dict[str, object]:
    return {
        "IsInteger": MP_IsInteger,
        "mpf": mp.mpf,
        "x": mp.mpf(value),
    }


def test_isinteger_assume_is_compiled_as_a_residual_guard() -> None:
    guard = compile_guard_expr("Assume(IsInteger(x))")

    assert guard.kind == "residual"
    assert guard.residual_expr == "IsInteger(x)"
    assert guard_hard_satisfied(guard, _integer_context("2"))
    assert not guard_hard_satisfied(guard, _integer_context("2.5"))
    assert guard_violation_value(guard, _integer_context("2.5")) > 0


def test_isinteger_residual_survives_relation_adapter() -> None:
    problem = GeometryProblem(
        id="integer-guard",
        variables=["x"],
        constructions=[],
        conditions=[{"left": "IsInteger(x)", "operator": "=", "right": 0}],
        target="x",
    )

    document = to_engine_document(problem)
    assert document["constraints"] == [{"def": "IsInteger(x)", "value": 0}]
    guard = compile_guard_expr("IsInteger(x)")
    assert not guard_hard_satisfied(guard, _integer_context("2.5"))


def test_isinteger_direct_guard_is_compiled_as_a_residual_guard() -> None:
    guard = compile_guard_expr("IsInteger(x)")

    assert guard.kind == "residual"
    assert not guard_hard_satisfied(guard, _integer_context("0.25"))


def _bound_context(value: str) -> dict[str, object]:
    return {"mpf": mp.mpf, "x": mp.mpf(value)}


def test_bound_nested_under_assume_is_compiled_as_a_closed_bound() -> None:
    guard = compile_guard_expr("Assume(Bound(x, (0, 1)))")

    assert guard.kind == "bound"
    assert guard_hard_satisfied(guard, _bound_context("0"))
    assert guard_hard_satisfied(guard, _bound_context("1"))
    assert not guard_hard_satisfied(guard, _bound_context("1.1"))


def test_bound_nested_under_assume_preserves_open_interval() -> None:
    guard = compile_guard_expr("Assume(Bound(x, (0, 1), inclusive=False))")

    assert guard.kind == "bound_open"
    assert not guard_hard_satisfied(guard, _bound_context("0"))
    assert not guard_hard_satisfied(guard, _bound_context("1"))
    assert guard_hard_satisfied(guard, _bound_context("0.5"))


def test_bound_predicate_adapter_emits_a_native_bound_guard() -> None:
    problem = GeometryProblem(
        id="bound-guard",
        variables=["x"],
        constructions=[],
        conditions=[{"predicate": "Bound(x, (0, 1))"}],
        target="x",
    )

    document = to_engine_document(problem)
    assert document["guards"] == ["Bound(x, (0, 1))"]
    guard = compile_guard_expr(document["guards"][0])
    assert guard.kind == "bound"
    assert guard_hard_satisfied(guard, _bound_context("0.5"))


def test_wrapped_multi_argument_residual_guard_preserves_all_arguments() -> None:
    guard = compile_guard_expr("Assume(AssumeParallel(line_a, line_b))")

    assert guard.kind == "residual"
    assert guard.residual_expr == "Parallel(line_a, line_b)"


def test_chained_comparison_compiles_both_sides_and_rejects_outside_values() -> None:
    guard = compile_guard_expr("0 < x < 1")

    assert guard.kind == "logical_and"
    assert len(guard.children) == 2
    assert not guard_hard_satisfied(guard, _bound_context("-1"))
    assert guard_hard_satisfied(guard, _bound_context("0.5"))
    assert not guard_hard_satisfied(guard, _bound_context("2"))


def test_bound_supports_one_sided_and_keyword_arguments() -> None:
    lower = compile_guard_expr("Bound(value=x, bounds=(0, None), inclusive=False)")
    upper = compile_guard_expr("Bound(x, (None, 1))")

    assert lower.lower_expr == "0" and lower.upper_expr is None
    assert upper.lower_expr is None and upper.upper_expr == "1"
    assert not guard_hard_satisfied(lower, _bound_context("0"))
    assert guard_hard_satisfied(lower, _bound_context("1e-100"))
    assert guard_hard_satisfied(upper, _bound_context("1"))
    assert not guard_hard_satisfied(upper, _bound_context("2"))


def test_and_conditions_tighten_search_bounds() -> None:
    spec = IRSpec(
        task="solve",
        variables=IRVariableSpec(names=["x"]),
        guards=["And(x > 0, x < 1)"],
    )

    assert search_bounds(spec) == [(0.0, 1.0)]


def test_keyword_parameter_uses_keyword_value_as_variable() -> None:
    spec = IRSpec(
        task="solve",
        variables=IRVariableSpec(names=["t"]),
        construction=[],
    )
    from geosolver.problem.ir.schema import IRConstruction

    spec.construction = [IRConstruction(name="P", expr="PointOnSegment(A, B, t=t)")]
    assert search_bounds(spec) == [(0.0, 1.0)]

    spec.construction = [IRConstruction(name="P", expr="PointOnCircle(omega, t=t)")]
    assert search_bounds(spec) == [(-10.0, 10.0)]


@pytest.mark.parametrize("point", [1, 2, 3])
def test_logical_equality_lowering_keeps_all_disjuncts(point):
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [],
                "constraints": [],
                "guards": ["Or(x==1,And(x==2,2*x==4),x==3)"],
                "answer": "x",
            }
        )
    )
    with mp.workdps(180), runtime_session(None):
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf(point),))
        assert result.verified and result.answer_hp == point
        with high_precision_mode():
            residual = ev.evaluate_hp_residual((mp.mpf("1.5"),), precision=180)
        assert residual.residual_norm_hp > 0


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


def _domain_evaluator(constraints, *, construction=(), guards=(), variables=("x",), answer="7"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "id": "second-audit",
                "task": "solve",
                "variables": {"names": list(variables)},
                "construction": list(construction),
                "constraints": [{"def": text, "value": 0} for text in constraints],
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


@pytest.mark.parametrize("source", ["1.000000000000000000000000000001", "1e1000"])
def test_public_compiler_keeps_numeric_lexemes(source):
    problem = GeometryProblem(
        id="lexeme", variables=[], constructions=[], conditions=[], target=source
    )
    compiled = compile_problem(problem)
    with mp.workdps(150):
        assert safe_eval_expr_hp(compiled.target.source, {"mpf": mp.mpf}) == mp.mpf(source)


def test_internal_power_compatibility_preserves_source_offsets():
    assert safe_eval_expr_hp("2^3+4", {"mpf": mp.mpf}) == 12


@pytest.mark.parametrize(
    "changes",
    [
        {"variables": {"names": ["x", "x"]}},
        {"v": []},
        {"m": 2},
        {"bounds": []},
        {"task": "optimize"},
        {"maximize": True},
    ],
)
def test_explicit_malformed_ir_is_not_silently_repaired(changes):
    from geosolver.problem.ir.parser import load_ir

    document = {
        "task": "solve",
        "variables": {"names": ["x"]},
        "constraints": ["x-1"],
        **changes,
    }
    with pytest.raises(IRValidationError):
        load_ir(document)


@pytest.mark.parametrize("bounds", [[[100, 200]], [[100, None]], [[2, 2]]])
def test_explicit_bounds_are_not_replaced_by_search_heuristics(bounds):
    from geosolver.problem.domain_bounds import mathematical_bounds, search_bounds
    from geosolver.problem.ir.parser import load_ir

    spec = load_ir({"task": "solve", "variables": {"names": ["x"]}, "bounds": bounds})
    axis = mathematical_bounds(spec)["x"]
    assert axis.lower == bounds[0][0]
    assert search_bounds(spec)[0][0] == bounds[0][0]
    if bounds[0][1] is not None:
        assert search_bounds(spec)[0][1] == bounds[0][1]


def test_negative_scale_is_local_to_dependent_axes():
    from geosolver.problem.domain_bounds import search_bounds

    for value in (-100, 100):
        ev = _domain_evaluator([f"x-({value})"], variables=("x", "y"))
        assert search_bounds(ev.bundle.spec) == [(-200, 200), (-10, 10)]


def test_closed_singleton_is_eliminated_as_a_fixed_variable():
    ev = _domain_evaluator(["x-2"], guards=["Bound(x,(2,2))"], answer="x")
    assert ev.bundle.var_names == ()
    assert verify_final_candidate(evaluator=ev, values=()).answer_hp == 2


def test_affine_parameter_domain_is_projected_but_nonlinear_is_not():
    from geosolver.problem.domain_bounds import mathematical_bounds
    from geosolver.problem.ir.schema import IRConstruction, IRSpec, IRVariableSpec

    for expression, expected in (("x/120", 120), ("x*x", None)):
        spec = IRSpec(
            task="solve",
            variables=IRVariableSpec(names=["x"]),
            construction=[IRConstruction("P", f"PointOnSegment(A,B,{expression})")],
        )
        assert mathematical_bounds(spec)["x"].upper == expected
