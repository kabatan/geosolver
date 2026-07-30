#!/usr/bin/env python3
"""Generated work/coverage check for confirmed-identity caching."""

from __future__ import annotations

import json
from pathlib import Path


def run(sequence: list[tuple[str, bool]]) -> dict[str, object]:
    control_work = len(sequence)
    candidate_work = 0
    control_found: set[str] = set()
    candidate_found: set[str] = set()
    confirmed: set[str] = set()
    for identity, passes in sequence:
        if passes:
            control_found.add(identity)
        if identity in confirmed:
            continue
        candidate_work += 1
        if passes:
            confirmed.add(identity)
            candidate_found.add(identity)
    return {
        "control_work": control_work,
        "candidate_work": candidate_work,
        "control_found": sorted(control_found),
        "candidate_found": sorted(candidate_found),
        "sets_equal": control_found == candidate_found,
    }


def main() -> None:
    families = {
        "duplicate_dense_positive": [("a", True)] * 20 + [("b", True)] * 10,
        "all_unique_neutral": [(f"u{i}", True) for i in range(12)],
        "failed_first_alternate": [("a", False), ("a", True), ("a", True), ("b", True)],
        "mixed_near_miss": [("a", False), ("b", False), ("a", True), ("b", True)] * 5,
    }
    results = {name: run(rows) for name, rows in families.items()}
    permuted = {
        name: run(list(reversed(rows))) for name, rows in families.items()
    }
    gates = {
        "all_exact_sets_preserved": all(row["sets_equal"] for row in results.values()),
        "all_permuted_sets_preserved": all(row["sets_equal"] for row in permuted.values()),
        "strict_work_gain": results["duplicate_dense_positive"]["candidate_work"]
        < results["duplicate_dense_positive"]["control_work"],
        "neutral_unique_work": results["all_unique_neutral"]["candidate_work"]
        == results["all_unique_neutral"]["control_work"],
        "failed_confirmation_not_cached": results["failed_first_alternate"]["candidate_work"] == 3,
    }
    payload = {
        "schema_version": "geotarget.exp-global.exact-authority-cache-d0/v1",
        "results": results,
        "permuted": permuted,
        "gates": gates,
        "passed": all(gates.values()),
    }
    output = Path(__file__).with_name("D0_RESULT.json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(output)
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
