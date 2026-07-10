from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any, cast

from geotarget import ProblemSpecV1, validate_document

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "open_world_plugin"


def _example_namespace() -> dict[str, Any]:
    return runpy.run_path(str(EXAMPLE / "build_problem.py"), run_name="geotarget_sdk_example")


def test_open_world_example_matches_checked_in_canonical_problem() -> None:
    namespace = _example_namespace()
    problem = cast(ProblemSpecV1, namespace["build_problem"]())

    expected = (EXAMPLE / "problem.json").read_text(encoding="utf-8").rstrip("\n")
    assert problem.canonical_json() == expected
    assert validate_document(problem.to_dict()) == "geotarget.problem/v1"
    assert (
        problem.content_hash()
        == "sha256:17172c7ef28c0a4f3b3c9938247fa84113fc7b10e365359b2a379ab36cd9a14b"
    )


def test_open_world_example_cli_writes_the_same_artifact(tmp_path: Path) -> None:
    namespace = _example_namespace()
    output = tmp_path / "problem.json"

    assert namespace["main"](["--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == (EXAMPLE / "problem.json").read_text(
        encoding="utf-8"
    ).rstrip("\n")
