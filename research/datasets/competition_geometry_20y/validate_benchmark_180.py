#!/usr/bin/env python3
"""Validate the 180-second, one-core benchmark artifact."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from run_benchmark import _expected_parts, answer_set_exact, close_to_expected


ROOT = Path(__file__).resolve().parent


def main() -> None:
    result_path = ROOT / "benchmark_results_180s_1core_evaluated.json"
    summary = json.loads(result_path.read_text(encoding="utf-8"))
    cases = sorted((ROOT / "dsl").glob("*.json"))
    rows = summary["results"]
    case_ids = {case.stem for case in cases}

    assert summary["budget_sec"] == 180.0
    assert summary["jobs"] == 1
    assert summary["hard_timeout"] is True
    assert summary["subprocess_timeout_sec"] == 180.0
    assert summary["cpu_affinity"] == [0]
    assert summary["one_core_enforced"] is True
    assert summary["cases"] == summary["runs"] == len(cases) == 302
    assert summary["runnable_cases"] == 285
    assert summary["reference_only_cases"] == 17
    assert {row["case_id"] for row in rows} == case_ids
    assert all(row["seed"] == 7 for row in rows)

    status_counts = Counter(row.get("status") for row in rows)
    assert status_counts == Counter({
        "success": 218,
        "no_solution": 38,
        "reference_only": 17,
        "timeout": 25,
        "exception": 4,
    })
    assert summary["success_runs"] == status_counts["success"]
    assert summary["no_solution_runs"] == status_counts["no_solution"]
    assert summary["reference_only_runs"] == status_counts["reference_only"]
    assert summary["timeout_runs"] == status_counts["timeout"]
    assert summary["exception_runs"] == status_counts["exception"]
    assert all(row["wall_sec"] <= 181.0 for row in rows if row["status"] == "timeout")

    audits = {}
    for line in (ROOT / "manual_audit.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        audit = json.loads(line)
        keys = [audit.get("problem_id"), audit.get("dedupe_key")]
        if audit.get("dsl_path"):
            keys.append(Path(audit["dsl_path"]).stem)
        for key in keys:
            if key:
                audits[key] = audit

    reference_ids = {
        case.stem
        for case in cases
        if str(json.loads(case.read_text(encoding="utf-8")).get("solver_coverage", "")).startswith("reference_only")
    }
    assert {row["case_id"] for row in rows if row["status"] == "reference_only"} == reference_ids
    assert all(row["status"] != "reference_only" for row in rows if row["case_id"] not in reference_ids)

    for row in rows:
        expected = audits[row["case_id"]].get("published_answer")
        assert row.get("expected_answer") == expected
        assert row.get("answer_set_exact") == answer_set_exact(row.get("accepted_answers", []), expected)
        if expected and row.get("answer_match") is True:
            compared = row.get("reported_answer") or row.get("selected_answer")
            assert close_to_expected(compared, expected) is True

    assert summary["expected_answer_runs"] == 212
    assert summary["answer_set_covered_runs"] == 120
    assert summary["answer_set_exact_runs"] == 112
    assert summary["answer_set_covered_but_not_exact_runs"] == 8
    assert summary["correct_runs"] == 139
    print(json.dumps({
        "cases": len(cases),
        "status_counts": dict(status_counts),
        "expected_answer_runs": summary["expected_answer_runs"],
        "correct_runs": summary["correct_runs"],
        "answer_set_covered_runs": summary["answer_set_covered_runs"],
        "answer_set_exact_runs": summary["answer_set_exact_runs"],
        "cpu_affinity": summary["cpu_affinity"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
