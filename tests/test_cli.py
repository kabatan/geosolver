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
