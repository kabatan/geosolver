"""Read-only access to current corpus rows and archived source-audit records.

This module cannot reapply historical repairs or restore removed problems.
The current cases.jsonl and DSL files are the operational source of truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parents[1] / "cases.jsonl"
BEFORE = HERE / "before.jsonl"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def _rows(path):
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows = {row["id"]: row for row in records}
    if len(rows) != len(records):
        raise ValueError(f"Duplicate case IDs in {path}")
    return rows


def removed_rows():
    """Historical evidence only; never supplied to a campaign run."""
    quarantined = _rows(HERE / "removed-cases.jsonl")
    aliases = _rows(HERE.parent / "dedup-20260830/removed-cases.jsonl")
    if quarantined.keys() & aliases.keys():
        raise ValueError("Duplicate removed case IDs")
    return quarantined | aliases


def repaired_rows(*, include_removed=False):
    original_ids = _rows(BEFORE).keys()
    current = _rows(CASES)
    removed = removed_rows()
    if current.keys() & removed.keys():
        raise ValueError("Archived case present in active corpus")
    if include_removed:
        current |= removed
    return {key: row for key, row in current.items() if key in original_ids}


def validate(rows):
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate as validate_problem

    for identifier, row in rows.items():
        report = validate_problem(GeometryProblem.model_validate(row["dsl"]))
        if not report.valid:
            raise ValueError(f"{identifier}: {report.issues}")
