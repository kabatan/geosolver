"""Api contracts and numerical regressions."""

import json
from importlib.resources import files

import jsonschema
import pytest
from typer.testing import CliRunner

from geosolver import GeometryProblem, SolveOptions, solve, validate
from geosolver.application.cli import app
from geosolver.application.service import problem_hash
from geosolver.problem.catalog import runtime_contracts
from geosolver.problem.dsl_spec import dsl_spec, public_symbol_names


def test_dsl_spec_is_the_complete_public_name_source() -> None:
    spec = dsl_spec()
    names = public_symbol_names()

    assert spec.dsl_version == "1.1.0"
    assert names == frozenset(runtime_contracts())
    assert {"AreConcyclic", "Tangent", "Bound", "Midpoint", "midpoint"} <= names
    assert not any(name.startswith("MP_") for name in names)
    assert {"float", "int", "evalf"}.isdisjoint(names)


def test_every_macro_has_an_expansion_and_no_runtime_implementation() -> None:
    for symbol in dsl_spec().symbols:
        if symbol.symbol_kind != "macro":
            continue
        assert symbol.expands_to
        assert symbol.standard_implementation is None
        assert symbol.high_precision_implementation is None


def test_validate_cli_uses_new_problem_schema(tmp_path) -> None:
    path = tmp_path / "問題.json"
    path.write_text(
        json.dumps(
            {
                "id": "cli",
                "variables": ["x"],
                "constructions": [],
                "conditions": [{"left": "x", "operator": "=", "right": 1}],
                "target": "x",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["validate", str(path)])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["valid"] is True


def test_catalog_json_is_generated_from_dsl_spec() -> None:
    result = CliRunner().invoke(app, ["catalog", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dsl_version"] == "1.1.0"
    names = {tool["id"] for tool in payload["tools"]}
    assert {"AreConcyclic", "Tangent", "Bound"} <= names
    assert not any(name.startswith("MP_") for name in names)


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
    assert SolveOptions().time_limit_seconds == 180
    assert SolveOptions().cores == 1
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


def problem_with_value(value: int | float | str = 1) -> GeometryProblem:
    return GeometryProblem(
        id="positive-dimensional",
        variables=["x"],
        constructions=[],
        conditions=[{"left": "x", "operator": "=", "right": value}],
        target="x",
    )


def test_json_numbers_reject_boolean_and_preserve_int_float_identity() -> None:
    with pytest.raises(ValueError):
        problem_with_value(True)  # type: ignore[arg-type]

    integer = problem_with_value(1)
    floating = problem_with_value(1.0)
    assert integer.engine_document()["constraints"][0]["value"] == 1
    assert type(integer.engine_document()["constraints"][0]["value"]) is int
    assert type(floating.engine_document()["constraints"][0]["value"]) is float
    assert problem_hash(integer) != problem_hash(floating)
