from __future__ import annotations

import json
from importlib.resources import files

import jsonschema

from geosolver import GeometryProblem, SolveOptions, solve, validate


def test_documented_public_imports_and_schema() -> None:
    problem = GeometryProblem(
        id="public",
        variables=["x"],
        constructions=[],
        conditions=[{"left": "x", "operator": "=", "right": 1}],
        target="x",
    )
    schema = json.loads(
        files("geosolver.schemas")
        .joinpath("geometry-problem.schema.json")
        .read_text(encoding="utf-8")
    )

    jsonschema.validate(problem.model_dump(mode="json"), schema)
    assert validate(problem).valid
    assert SolveOptions().engine == "standard"
    assert callable(solve)


def test_old_problem_and_option_fields_are_rejected() -> None:
    old_problem = {
        "task": "solve",
        "id": "old",
        "variables": {"names": ["x"]},
        "construction": [],
        "guards": [],
        "answer": "x",
    }

    assert not validate(old_problem).valid
    for payload in (
        {"engine": "opti" + "mized"},
        {"run_mode": "adaptive"},
        {"max_time_seconds": 900},
    ):
        try:
            SolveOptions.model_validate(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"legacy option was accepted: {payload}")
