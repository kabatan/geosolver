from __future__ import annotations

import pytest

from geosolver.problem.adapter import to_engine_document
from geosolver.problem.compiler import ProblemCompileError, compile_problem, predicate_guard_source
from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import validate


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
