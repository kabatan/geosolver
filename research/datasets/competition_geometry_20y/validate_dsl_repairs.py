#!/usr/bin/env python3
"""Validate the focused 180-second benchmark for repaired DSL cases.

This is deliberately a metadata-and-scoring check: it does not run the
solver.  The benchmark itself is the source of the raw Phase C values; this
script verifies that it covered exactly the repair set and that the reported
strict flags agree with the independent exact scorer.
"""
from __future__ import annotations

import json
from pathlib import Path

from exact_scoring import strict_answer_set_complete, strict_answer_set_exact

ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "benchmark_results_180s_1core_dsl_repairs.json"

REPAIR_CASES = (
    "AIME-2006-II-09",
    "AIME-2019-I-06",
    "AIME-2022-II-07",
    "HMMT-2007-FEB-GEO-04",
    "HMMT-2022-FEB-GEO-05",
    "HMMT-2024-FEB-GEO-10",
    "JMO-2019-MATHNET-08yk",
    "JMO-2019-PRE-08",
    "JMO-2022-MATHNET-08z4",
    "JMO-2022-PRE-12",
)


def main() -> int:
    data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    rows = list(data.get("results", []))
    case_filter = data.get("case_id_filter")
    if sorted(case_filter or []) != list(REPAIR_CASES):
        raise SystemExit(f"unexpected case_id_filter: {case_filter!r}")
    required_metadata = {
        "budget_sec": 180.0,
        "jobs": 1,
        "hard_timeout": True,
        "cpu_affinity": [0],
        "one_core_enforced": True,
        "seeds": [7],
        "runs": len(REPAIR_CASES),
    }
    for key, expected in required_metadata.items():
        if data.get(key) != expected:
            raise SystemExit(f"metadata mismatch for {key}: {data.get(key)!r} != {expected!r}")
    if len(rows) != len(REPAIR_CASES):
        raise SystemExit(f"expected {len(REPAIR_CASES)} result rows, got {len(rows)}")
    by_case: dict[str, dict[str, object]] = {}
    for row in rows:
        case_id = str(row.get("case_id"))
        if case_id in by_case:
            raise SystemExit(f"duplicate result row: {case_id}")
        by_case[case_id] = row
        values = list((row.get("phasec") or {}).get("answer_values") or [])
        expected = row.get("expected_answer")
        exact = strict_answer_set_exact(values, expected)
        complete = strict_answer_set_complete(values, expected)
        if row.get("answer_set_exact") is not exact:
            raise SystemExit(f"answer_set_exact mismatch for {case_id}")
        if row.get("answer_set_complete") is not complete:
            raise SystemExit(f"answer_set_complete mismatch for {case_id}")
    if sorted(by_case) != list(REPAIR_CASES):
        raise SystemExit(f"result cases differ: {sorted(by_case)}")
    exact_count = sum(bool(row.get("answer_set_exact")) for row in rows)
    complete_count = sum(bool(row.get("answer_set_complete")) for row in rows)
    summary = {
        "result_path": str(RESULT_PATH),
        "case_ids": list(REPAIR_CASES),
        "runs": len(rows),
        "strict_exact_runs": exact_count,
        "strict_complete_runs": complete_count,
        "status_counts": {
            status: sum(row.get("status") == status for row in rows)
            for status in sorted({str(row.get("status")) for row in rows})
        },
        "rows": [
            {
                "case_id": row["case_id"],
                "status": row.get("status"),
                "answer_set_exact": row.get("answer_set_exact"),
                "answer_set_complete": row.get("answer_set_complete"),
                "answer_values": (row.get("phasec") or {}).get("answer_values", []),
                "expected_answer": row.get("expected_answer"),
                "wall_sec": row.get("wall_sec"),
            }
            for row in rows
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
