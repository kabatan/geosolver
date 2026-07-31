"""Small static/D0 checks; no solver corpus or truth is read."""

from __future__ import annotations

import ast
from pathlib import Path


HERE = Path(__file__).resolve().parent


def test_candidate_sources_parse() -> None:
    for name in ("search_adapter.py", "search_worker.py", "scheduler_shim.py", "worker.py", "prejoin_aggregate.py", "run_generated_d0.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_no_identity_or_truth_routing_in_algorithm_files() -> None:
    forbidden = ("case_id", "problem_id", "known_target_count", "truth.json", "family_name")
    for name in ("search_adapter.py", "search_worker.py", "scheduler_shim.py", "worker.py"):
        text = (HERE / name).read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), name


def test_quota_is_explicit() -> None:
    text = (HERE / "search_adapter.py").read_text(encoding="utf-8")
    assert '"side_route_fraction_upper_bound": 0.25' in text
    assert '"baseline_fraction_lower_bound": 0.75' in text


def test_prejoin_accepts_source_answer_but_rejects_offline_truth() -> None:
    text = (HERE / "prejoin_aggregate.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "FORBIDDEN_KEYS" for target in node.targets)
    )
    values = ast.literal_eval(assignment.value.args[0])
    assert "answer" not in values
    assert {"truth", "score", "outcome", "id", "family"} <= set(values)
