from __future__ import annotations

import ast
from pathlib import Path


HERE = Path(__file__).resolve().parent


def test_sources_parse() -> None:
    for name in ("candidate.py", "run_generated_d0.py", "run_real_gate.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_no_source_parser_or_routing() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    for token in ("ast.parse", "case_id", "problem_id", "known_target_count", "offline_truth"):
        assert token not in text


def test_both_reflections_are_explicit() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    assert "point.reflected()" in text
    assert '"both_reflections_enumerated": True' in text


def test_exact_gate_is_digest_distinct_outcome_blind_abba() -> None:
    text = (HERE / "run_real_gate.py").read_text(encoding="utf-8")
    for token in (
        "APPROVED_PYTHON_SHA256",
        "PANEL_PROVENANCE_SHA256",
        "candidate_endpoint_digest_equals_baseline",
        '("candidate", candidate_attempts[0])',
        '("baseline", endpoint)',
        '("candidate", candidate_attempts[1])',
        '"source_or_problem_modified"',
        '"source_raw_answer_exact"',
        '"target_link_exact"',
        '"all_precision_lanes_guard_and_hard_feasible"',
    ):
        assert token in text
    assert text.count('_run_exact(\n                        arguments.python.resolve()') == 1
