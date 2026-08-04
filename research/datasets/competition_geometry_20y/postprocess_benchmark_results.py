#!/usr/bin/env python3
"""Add bidirectional answer-set metrics to a completed benchmark JSON.

The benchmark runner historically called the expected-value coverage check
``answer_set_complete``.  That field is intentionally preserved for
backward compatibility; this postprocessor adds an exact-set check that also
rejects accepted candidates not present in the published answer set.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_benchmark import _expected_parts, answer_set_exact, close_to_expected


def _annotate(row: dict) -> None:
    expected = row.get("expected_answer")
    accepted = row.get("accepted_answers") or []
    parts = _expected_parts(expected)
    row["answer_set_covered"] = row.get("answer_set_complete")
    row["answer_set_exact"] = answer_set_exact(accepted, expected)
    if not parts:
        row["extra_accepted_answers"] = []
        row["missing_expected_answers"] = []
        return
    row["extra_accepted_answers"] = [
        str(value)
        for value in accepted
        if not any(close_to_expected(str(value), part) is True for part in parts)
    ]
    row["missing_expected_answers"] = [
        part
        for part in parts
        if not any(close_to_expected(str(value), part) is True for value in accepted)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    summary = json.loads(args.input.read_text(encoding="utf-8"))
    for row in summary.get("results", []):
        _annotate(row)
    rows = summary.get("results", [])
    summary["expected_answer_runs"] = sum(bool(_expected_parts(row.get("expected_answer"))) for row in rows)
    summary["answer_set_covered_runs"] = sum(row.get("answer_set_exact") is not None and row.get("answer_set_covered") is True for row in rows)
    summary["answer_set_exact_runs"] = sum(row.get("answer_set_exact") is True for row in rows)
    summary["answer_set_covered_but_not_exact_runs"] = sum(
        row.get("answer_set_covered") is True and row.get("answer_set_exact") is False
        for row in rows
    )
    summary["answer_set_evaluation"] = {
        "answer_set_complete": "expected-set coverage (historical field; extra candidates are allowed)",
        "answer_set_exact": "bidirectional equality under close_to_expected tolerance",
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "expected_answer_runs": summary["expected_answer_runs"],
        "answer_set_covered_runs": summary["answer_set_covered_runs"],
        "answer_set_exact_runs": summary["answer_set_exact_runs"],
        "answer_set_covered_but_not_exact_runs": summary["answer_set_covered_but_not_exact_runs"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
