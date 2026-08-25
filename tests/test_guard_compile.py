from __future__ import annotations

from mpmath import mp

from geosolver.engine.standard.interpreter.guards.compile import (
    compile_guard_expr,
    guard_hard_satisfied,
    guard_violation_value,
)
from geosolver.geometry.mp.mp_api_geometry import MP_IsInteger
from geosolver.problem.adapter import to_engine_document
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


def test_isinteger_guard_survives_predicate_adapter() -> None:
    problem = GeometryProblem(
        id="integer-guard",
        variables=["x"],
        constructions=[],
        conditions=[{"predicate": "IsInteger(x)"}],
        target="x",
    )

    document = to_engine_document(problem)
    assert document["guards"] == ["Assume(IsInteger(x))"]
    guard = compile_guard_expr(document["guards"][0])
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
