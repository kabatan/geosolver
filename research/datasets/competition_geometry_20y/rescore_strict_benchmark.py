#!/usr/bin/env python3
"""Re-score a completed solver run against raw exact solution sets."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from exact_scoring import strict_answer_set_complete, strict_answer_set_exact


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    truth = {
        row["case_id"]: row
        for line in (root / "exact_truth.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    summary = json.loads(args.input.read_text(encoding="utf-8"))
    old_summary = {
        key: summary.get(key)
        for key in (
            "correct_runs",
            "complete_answer_set_runs",
            "answer_set_exact_runs",
            "answer_set_covered_but_not_exact_runs",
        )
    }
    rows = summary.get("results", [])
    for row in rows:
        target = truth.get(row.get("case_id"), {})
        expected = target.get("exact_answer_set")
        values = (row.get("phasec") or {}).get("answer_values", [])
        row["presentation_answer"] = row.get("expected_answer")
        row["expected_answer"] = expected
        row["truth_status"] = target.get("truth_status")
        row["raw_selected_answer"] = row.get("selected_answer")
        # The input is a historical presentation-scored artifact.  Do not
        # carry its post-processed `reported_answer` into the strict result;
        # leaving it present would make it too easy to mistake that field for
        # the value used by the exact judge.
        row.pop("reported_answer", None)
        row["solution_values"] = [str(value) for value in values]
        row["answer_set_complete"] = strict_answer_set_complete(values, expected)
        row["answer_set_exact"] = strict_answer_set_exact(values, expected)
        # This field now has the same meaning as the user's definition of
        # correctness: exact equality of the raw solution set.
        row["answer_match"] = row["answer_set_exact"]
        row["strict_answer_set_complete"] = row["answer_set_complete"]
        row["strict_answer_set_exact"] = row["answer_set_exact"]

    summary["legacy_presentation_metrics"] = old_summary
    summary["scoring_definition"] = {
        "target": "DSL answer expression's raw exact geometric quantity",
        "comparison": "bidirectional symbolic set equality",
        "solver_values": "phasec.answer_values",
        "decimal_policy": "decimal-only values are not exact; a decimal paired with its symbolic duplicate is ignored",
        "presentation_post_process": "not used",
    }
    summary["truth_available_runs"] = sum(bool(truth.get(row.get("case_id"), {}).get("exact_answer_set")) for row in rows)
    summary["truth_verified_runs"] = sum(truth.get(row.get("case_id"), {}).get("truth_status") == "verified" for row in rows)
    summary["truth_verified_runnable_runs"] = sum(
        truth.get(row.get("case_id"), {}).get("truth_status") == "verified"
        and row.get("status") != "reference_only"
        for row in rows
    )
    summary["strict_correct_runs"] = sum(row.get("strict_answer_set_exact") is True for row in rows)
    summary["strict_complete_answer_set_runs"] = sum(row.get("strict_answer_set_complete") is True for row in rows)
    summary["strict_answer_set_unknown_runs"] = sum(row.get("strict_answer_set_exact") is None for row in rows)
    summary["correct_runs"] = summary["strict_correct_runs"]
    summary["complete_answer_set_runs"] = summary["strict_complete_answer_set_runs"]
    summary["answer_set_exact_runs"] = summary["strict_correct_runs"]
    summary["answer_set_covered_but_not_exact_runs"] = sum(
        row.get("strict_answer_set_complete") is True and row.get("strict_answer_set_exact") is False
        for row in rows
    )
    summary["status_counts"] = dict(Counter(row.get("status") for row in rows))
    summary["strict_verified_success_runs"] = sum(
        row.get("truth_status") == "verified"
        and row.get("status") == "success"
        for row in rows
    )
    summary["strict_verified_success_exact_runs"] = sum(
        row.get("truth_status") == "verified"
        and row.get("status") == "success"
        and row.get("strict_answer_set_exact") is True
        for row in rows
    )
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "runs": len(rows),
        "truth_available_runs": summary["truth_available_runs"],
        "strict_correct_runs": summary["strict_correct_runs"],
        "strict_complete_answer_set_runs": summary["strict_complete_answer_set_runs"],
        "strict_answer_set_unknown_runs": summary["strict_answer_set_unknown_runs"],
        "truth_verified_runnable_runs": summary["truth_verified_runnable_runs"],
        "legacy_presentation_metrics": old_summary,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
