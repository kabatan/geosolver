from __future__ import annotations

import ast
from pathlib import Path


HERE = Path(__file__).resolve().parent


def test_sources_parse() -> None:
    for name in ("candidate.py", "run_g0.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_terminal_requires_exact_replay() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    for token in (
        "descriptor_exact", "source_constraints_exact", "canonical_guard_replay",
        "raw_target_link_exact", "not exact.approximate_endpoint_is_authority",
    ):
        assert token in text


def test_no_algorithm_parameter_tuning() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    assert "FROZEN.run_candidate" in text
    assert "path_length" not in text
    assert "step_length" not in text
