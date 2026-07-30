#!/usr/bin/env python3
"""Compare two geometry-kernel measurements after enforcing same work."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import geometric_mean
from typing import Any


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"malformed measurement: {path}")
    return value


def compare(control: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    if control.get("schema_version") != candidate.get("schema_version"):
        raise ValueError("measurement schemas differ")
    if control.get("config") != candidate.get("config"):
        raise ValueError("measurement configs differ")
    if control.get("input_stream_digest") != candidate.get("input_stream_digest"):
        raise ValueError("input streams differ")
    control_rows = {row["source_sha256"]: row for row in control["rows"]}
    candidate_rows = {row["source_sha256"]: row for row in candidate["rows"]}
    if set(control_rows) != set(candidate_rows):
        raise ValueError("case source sets differ")
    mismatches: list[dict[str, str]] = []
    ratios: dict[str, list[float]] = defaultdict(list)
    regressions: list[dict[str, Any]] = []
    for source_sha256 in sorted(control_rows):
        left = control_rows[source_sha256]
        right = candidate_rows[source_sha256]
        for field in ("input_digest", "residual_digest", "callback_digest"):
            if left[field] != right[field]:
                mismatches.append({"source_sha256": source_sha256, "field": field})
        family = str(left["structural_family"])
        for phase in ("residual", "callback"):
            ratio = right[phase]["wall_ns"] / left[phase]["wall_ns"]
            ratios[f"{phase}:{family}"].append(ratio)
            if ratio > 1.0:
                regressions.append(
                    {"source_sha256": source_sha256, "phase": phase, "wall_ratio": ratio}
                )
    family_ratios = {family: geometric_mean(values) for family, values in sorted(ratios.items())}
    overall = geometric_mean(value for values in ratios.values() for value in values)
    return {
        "same_work": not mismatches,
        "mismatches": mismatches,
        "overall_geometric_mean_wall_ratio": overall,
        "family_geometric_mean_wall_ratios": family_ratios,
        "case_phase_regressions": regressions,
        "no_structural_family_regression": all(value <= 1.0 for value in family_ratios.values()),
        "finite_ratios": all(
            math.isfinite(value) and value > 0 for value in family_ratios.values()
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    report = compare(_load(arguments.control), _load(arguments.candidate))
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        output = arguments.output.expanduser().resolve()
        if output.exists():
            raise SystemExit(f"refusing to overwrite existing output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    return 0 if report["same_work"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
