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


@pytest.mark.parametrize("value", [0, 179.999, float("inf"), float("nan")])
def test_time_limit_is_finite_and_at_least_180(value: float) -> None:
    with pytest.raises(ValidationError):
        SolveOptions(time_limit_seconds=value)
