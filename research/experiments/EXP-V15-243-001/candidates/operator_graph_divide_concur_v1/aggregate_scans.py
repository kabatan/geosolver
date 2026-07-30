#!/usr/bin/env python3
"""Aggregate only anonymous source-gate records for the recurrence gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


MINIMUM_ATTEMPTS = 4
MINIMUM_ANONYMOUS_HASHES = 2


def aggregate(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [record for record in records if record.get("eligible") is True]
    hashes = {
        record.get("anonymous_structural_fingerprint_sha256")
        for record in eligible
        if isinstance(record.get("anonymous_structural_fingerprint_sha256"), str)
    }
    recurrence = len(eligible) >= MINIMUM_ATTEMPTS and len(hashes) >= MINIMUM_ANONYMOUS_HASHES
    return {
        "candidate": "OPERATOR_GRAPH_DIVIDE_CONCUR_V1",
        "decision": "REAL_SOURCE_GATE_PASS" if recurrence else "HOLD_RECURRENCE_GATE",
        "scan_count": len(records),
        "eligible_attempt_count": len(eligible),
        "anonymous_eligible_hash_count": len(hashes),
        "minimum_eligible_attempts": MINIMUM_ATTEMPTS,
        "minimum_anonymous_hashes": MINIMUM_ANONYMOUS_HASHES,
        "recurrence_gate_pass": recurrence,
        "individual_source_rows_emitted": False,
        "truth_case_family_target_or_result_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", type=Path, action="append", required=True)
    arguments = parser.parse_args()
    records = []
    for path in arguments.scan:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise SystemExit("scan record is not an object")
        records.append(value)
    print(json.dumps(aggregate(records), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
