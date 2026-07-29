from __future__ import annotations

import pytest
from pydantic import ValidationError

from geotarget import SolveOptions, validate


def test_v15_round_trip_preserves_native_shape(problem: dict) -> None:
    report = validate(problem)
    assert report.valid
    assert report.normalized_problem == problem


def test_point_on_circle_periodic_expression_is_preserved(problem: dict) -> None:
    problem["variables"]["names"] = ["t"]
    problem["construction"].append({"name": "C", "expr": "PointOnCircle(c, t)"})
    report = validate(problem)
    assert report.valid
    assert report.normalized_problem["construction"][-1]["expr"] == "PointOnCircle(c, t)"


def test_dangerous_expression_is_rejected(problem: dict) -> None:
    problem["answer"] = "__import__('os').system('id')"
    report = validate(problem)
    assert not report.valid
    assert any(issue.code == "unsafe_expression" for issue in report.issues)


def test_malformed_expression_and_cross_namespace_collision_are_rejected(problem: dict) -> None:
    problem["variables"]["names"] = ["A"]
    problem["construction"][0]["expr"] = "Point(,)"
    report = validate(problem)
    assert not report.valid
    assert {issue.code for issue in report.issues} >= {"expression_syntax", "name_collision"}


def test_string_constraint_value_is_syntax_checked(problem: dict) -> None:
    problem["constraints"].append({"def": "Distance(A, B)", "value": "Point(,)"})
    report = validate(problem)
    assert not report.valid
    assert any(issue.path == "constraints[0].value" for issue in report.issues)


def test_empty_expressions_are_reported_without_a_misleading_parser_column(problem: dict) -> None:
    problem["guards"] = ["   "]

    report = validate(problem)

    assert not report.valid
    issues = [issue for issue in report.issues if issue.path == "guards[0]"]
    assert [(issue.code, issue.message) for issue in issues] == [
        ("empty_expression", "expression must not be empty"),
    ]


@pytest.mark.parametrize("value", [0, 179.999, float("inf"), float("nan")])
def test_time_limit_is_finite_and_at_least_180(value: float) -> None:
    with pytest.raises(ValidationError):
        SolveOptions(time_limit_seconds=value)


def test_validation_preserves_native_json_scalar_types(problem: dict) -> None:
    problem["constraints"].append({"def": "Distance(A, B)", "value": 4})

    report = validate(problem)

    assert report.valid
    assert report.normalized_problem == problem
    assert type(report.normalized_problem["constraints"][0]["value"]) is int


def test_assume_eq_guard_is_preserved_but_diagnosed(problem: dict) -> None:
    problem["guards"] = [
        "AssumeEq(Distance(A, B), sqrt(17))",
        "AssumeLt(Distance(A, B), 10)",
    ]

    report = validate(problem)

    assert report.valid
    assert report.normalized_problem == problem
    assert [(warning.path, warning.code) for warning in report.warnings] == [
        ("guards[0]", "equation_as_guard")
    ]
