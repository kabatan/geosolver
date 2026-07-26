import json
from pathlib import Path

from geotarget import solve


def test_zero_variable_source_exact_route() -> None:
    problem_path = Path(__file__).resolve().parents[1] / "examples/problem.json"
    problem = json.loads(problem_path.read_text(encoding="utf-8"))

    result = solve(problem)

    assert result.status == "exact_complete"
    assert len(result.answers) == 1
    assert result.answers[0].minimal_polynomial_high_to_low == [1, -5]
    assert result.answers[0].decimal == "5"
