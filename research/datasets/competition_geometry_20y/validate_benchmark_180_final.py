#!/usr/bin/env python3
"""Validate the final 180-second/one-core benchmark artifact."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from run_benchmark import _expected_parts, answer_set_exact, close_to_expected


ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "benchmark_results_180s_1core_final.json"


def main() -> None:
    summary = json.loads(RESULT.read_text(encoding="utf-8"))
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
        "success": 232,
        "no_solution": 36,
        "reference_only": 17,
        "timeout": 13,
        "exception": 4,
    })
    assert summary["correct_runs"] == 165
    assert summary["complete_answer_set_runs"] == 128
    assert summary["answer_set_exact_runs"] == 115
    assert summary["answer_set_covered_but_not_exact_runs"] == 13

    audits = {}
    for line in (ROOT / "manual_audit.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for key in (row.get("problem_id"), row.get("dedupe_key")):
            if key:
                audits[key] = row
        if row.get("dsl_path"):
            audits[Path(row["dsl_path"]).stem] = row

    for row in rows:
        case_id = row["case_id"]
        expected = audits[case_id].get("published_answer")
        assert row.get("expected_answer") == expected
        assert row.get("answer_set_exact") == answer_set_exact(row.get("accepted_answers", []), expected)
        if row.get("answer_match") is True:
            compared = row.get("reported_answer") or row.get("selected_answer")
            assert close_to_expected(compared, expected) is True

    assert all(row.get("status") == "reference_only" for row in rows if row["case_id"] in {
        case.stem for case in cases
        if str(json.loads(case.read_text(encoding="utf-8")).get("solver_coverage", "")).startswith("reference_only")
    })
    print(json.dumps({
        "cases": len(cases),
        "status_counts": dict(status_counts),
        "correct_runs": summary["correct_runs"],
        "answer_set_exact_runs": summary["answer_set_exact_runs"],
        "cpu_affinity": summary["cpu_affinity"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
