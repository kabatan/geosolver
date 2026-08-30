from __future__ import annotations

from mpmath import mp

from geosolver.engine.standard.interpreter.guards.compile import (
    compile_guard_expr,
    guard_hard_satisfied,
    guard_violation_value,
)
from geosolver.geometry.mp.mp_api_geometry import MP_IsInteger
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.domain_bounds import search_bounds
from geosolver.problem.ir.schema import IRSpec, IRVariableSpec
from geosolver.problem.models import GeometryProblem


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
