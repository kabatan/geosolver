#!/usr/bin/env python3
"""Validate the raw-exact benchmark artifact.

This validator recomputes every score from ``phasec.answer_values`` and the
source-audited ``exact_truth.jsonl``.  It intentionally never reads a
post-processed/presentation answer.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from exact_scoring import exact_target_is_valid, strict_answer_set_complete, strict_answer_set_exact


ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--benchmark",
        type=Path,
        default=ROOT / "benchmark_results_180s_1core_strict_raw.json",
    )
    args = ap.parse_args()

    truth = {
        row["case_id"]: row
        for line in (ROOT / "exact_truth.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    cases = sorted((ROOT / "dsl").glob("*.json"))
    rows = benchmark.get("results", [])
    errors: list[str] = []

    if benchmark.get("budget_sec") != 180.0:
        errors.append(f"budget_sec={benchmark.get('budget_sec')!r}")
    if benchmark.get("jobs") != 1 or benchmark.get("hard_timeout") is not True:
        errors.append("benchmark is not the 180-second hard-timeout, one-job run")
    if benchmark.get("cpu_affinity") != [0] or benchmark.get("one_core_enforced") is not True:
        errors.append("one-core affinity metadata mismatch")
    if benchmark.get("cases") != len(cases) or benchmark.get("runs") != len(cases):
        errors.append("benchmark case/run count mismatch")
    if len(rows) != len(cases) or {row.get("case_id") for row in rows} != {p.stem for p in cases}:
        errors.append("benchmark case coverage mismatch")
    if len({row.get("case_id") for row in rows}) != len(rows):
        errors.append("duplicate benchmark case_id")
    if any("reported_answer" in row for row in rows):
        errors.append("strict artifact contains legacy reported_answer")

    for row in rows:
        case_id = row.get("case_id")
        target = truth.get(case_id)
        if target is None:
            errors.append(f"{case_id}: missing exact truth")
            continue
        expected = target.get("exact_answer_set")
        values = (row.get("phasec") or {}).get("answer_values", [])
        expected_exact = strict_answer_set_exact(values, expected)
        expected_complete = strict_answer_set_complete(values, expected)
        if target.get("truth_status") == "verified" and not exact_target_is_valid(expected):
            errors.append(f"{case_id}: verified truth is not a nonempty exact set")
        if row.get("expected_answer") != expected:
            errors.append(f"{case_id}: expected_answer is not exact_truth")
        if row.get("presentation_answer") != target.get("presentation_answer"):
            errors.append(f"{case_id}: presentation_answer mismatch")
        if row.get("truth_status") != target.get("truth_status"):
            errors.append(f"{case_id}: truth_status mismatch")
        if row.get("solution_values") != [str(value) for value in values]:
            errors.append(f"{case_id}: solution_values mismatch")
        for key, actual, wanted in (
            ("answer_match", row.get("answer_match"), expected_exact),
            ("answer_set_exact", row.get("answer_set_exact"), expected_exact),
            ("strict_answer_set_exact", row.get("strict_answer_set_exact"), expected_exact),
            ("answer_set_complete", row.get("answer_set_complete"), expected_complete),
            ("strict_answer_set_complete", row.get("strict_answer_set_complete"), expected_complete),
        ):
            if actual != wanted:
                errors.append(f"{case_id}: {key}={actual!r}, recomputed={wanted!r}")
        if row.get("strict_answer_set_exact") is True and target.get("truth_status") != "verified":
            errors.append(f"{case_id}: strict true without verified truth")

    statuses = Counter(row.get("status") for row in rows)
    verified = sum(row.get("truth_status") == "verified" for row in rows)
    verified_runnable = sum(
        row.get("truth_status") == "verified" and row.get("status") != "reference_only"
        for row in rows
    )
    strict_correct = sum(row.get("strict_answer_set_exact") is True for row in rows)
    strict_complete = sum(row.get("strict_answer_set_complete") is True for row in rows)
    unknown = sum(row.get("strict_answer_set_exact") is None for row in rows)
    expected_summary = {
        "truth_verified_runs": verified,
        "truth_verified_runnable_runs": verified_runnable,
        "strict_correct_runs": strict_correct,
        "strict_complete_answer_set_runs": strict_complete,
        "strict_answer_set_unknown_runs": unknown,
        "correct_runs": strict_correct,
        "answer_set_exact_runs": strict_correct,
        "complete_answer_set_runs": strict_complete,
        "status_counts": dict(statuses),
    }
    for key, value in expected_summary.items():
        if benchmark.get(key) != value:
            errors.append(f"summary {key}={benchmark.get(key)!r}, recomputed={value!r}")

    result = {
        "cases": len(cases),
        "truth_verified_runs": verified,
        "truth_verified_runnable_runs": verified_runnable,
        "strict_correct_runs": strict_correct,
        "strict_complete_answer_set_runs": strict_complete,
        "strict_answer_set_unknown_runs": unknown,
        "status_counts": dict(statuses),
        "errors": len(errors),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if errors:
        for error in errors:
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
