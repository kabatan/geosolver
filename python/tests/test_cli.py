from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_model import build_problem

from geotarget import __version__
from geotarget.cli import main


def test_version_and_empty_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert __version__ == "0.1.0.dev0"
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_build_info_is_explicit_about_missing_julia_wiring(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["build-info"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["julia_execution"] == "unsupported_not_wired"
    assert "geotarget.problem/v1" in info["schemas"]


def test_validate_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "problem.json"
    path.write_text(build_problem().canonical_json(), encoding="utf-8")
    assert main(["validate", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is True
    assert result["schema_version"] == "geotarget.problem/v1"


def test_validate_cli_returns_two_for_invalid_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"unknown"}', encoding="utf-8")
    assert main(["validate", str(path)]) == 2
    assert "validation failed" in capsys.readouterr().err
