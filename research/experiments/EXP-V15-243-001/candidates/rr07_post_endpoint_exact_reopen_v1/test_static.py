from __future__ import annotations

import ast
from pathlib import Path


HERE = Path(__file__).resolve().parent


def test_sources_parse() -> None:
    for name in ("candidate.py", "run_generated_d0.py", "run_real_gate.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_no_parser_compiler_expansion() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    for token in ("ast.parse", "compile_document", "case_id", "problem_id", "known_target_count"):
        assert token not in text


def test_two_reflections_are_explicit() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    assert "positive_y.negated()" in text
    assert '"both_reflections_enumerated": True' in text
