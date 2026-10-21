from __future__ import annotations

import json

from typer.testing import CliRunner

from geosolver.application.cli import app


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
