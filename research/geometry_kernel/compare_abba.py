#!/usr/bin/env python3
"""Compare serial A1/B1/B2/A2 same-work callback measurements."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import geometric_mean
from typing import Any

_DIGEST_FIELDS = ("input_digest", "residual_digest", "callback_digest")
_PHASES = ("residual", "callback")
_METRICS = ("wall_ns", "cpu_ns")
_MAX_RUN_ORDER_DRIFT = 0.10


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"malformed measurement: {path}")
    return value


def _geometric_pair(first: float, second: float) -> float:
    if first <= 0 or second <= 0:
        raise ValueError("timings must be positive")
    return math.sqrt(first * second)


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile of an empty sequence")
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def compare_abba(
    a1: Mapping[str, Any],
    b1: Mapping[str, Any],
    b2: Mapping[str, Any],
    a2: Mapping[str, Any],
) -> dict[str, Any]:
    runs = {"a1": a1, "b1": b1, "b2": b2, "a2": a2}
    reference = a1
    for label, run in runs.items():
        for field in (
            "schema_version",
            "config",
            "input_stream_digest",
            "skipped_source_sha256",
        ):
            if run.get(field) != reference.get(field):
                raise ValueError(f"{label}: {field} differs from a1")

    indexed = {
        label: {row["source_sha256"]: row for row in run["rows"]}
        for label, run in runs.items()
    }
    sources = set(indexed["a1"])
    if any(set(rows) != sources for rows in indexed.values()):
        raise ValueError("case source sets differ")

    mismatches: list[dict[str, str]] = []
    case_ratios: dict[str, list[float]] = defaultdict(list)
    group_totals: dict[tuple[str, str, str], list[float]] = defaultdict(
        lambda: [0.0, 0.0]
    )
    drift: dict[str, list[float]] = defaultdict(list)
    routing_violations: list[dict[str, str]] = []

    for source in sorted(sources):
        rows = {label: values[source] for label, values in indexed.items()}
        expected = rows["a1"]
        for label, row in rows.items():
            for field in _DIGEST_FIELDS:
                if row[field] != expected[field]:
                    mismatches.append(
                        {"source_sha256": source, "run": label, "field": field}
                    )
            routing = row.get("routing", {})
            if any(
                routing.get(field) is not False
                for field in (
                    "case_specific",
                    "corpus_metadata_read",
                    "problem_identity_read",
                )
            ):
                routing_violations.append(
                    {"source_sha256": source, "run": label}
                )

        control_backend = str(expected["backend"])
        candidate_backend = str(rows["b1"]["backend"])
        backend_pair = f"{control_backend}->{candidate_backend}"
        for phase in _PHASES:
            for metric in _METRICS:
                control = _geometric_pair(
                    float(rows["a1"][phase][metric]),
                    float(rows["a2"][phase][metric]),
                )
                candidate = _geometric_pair(
                    float(rows["b1"][phase][metric]),
                    float(rows["b2"][phase][metric]),
                )
                ratio = candidate / control
                case_ratios[f"{phase}:{metric}"].append(ratio)
                totals = group_totals[(phase, metric, backend_pair)]
                totals[0] += control
                totals[1] += candidate

                drift[f"control:{phase}:{metric}"].append(
                    float(rows["a2"][phase][metric])
                    / float(rows["a1"][phase][metric])
                )
                drift[f"candidate:{phase}:{metric}"].append(
                    float(rows["b2"][phase][metric])
                    / float(rows["b1"][phase][metric])
                )

    aggregates: dict[str, Any] = {}
    for key, values in sorted(case_ratios.items()):
        phase, metric = key.split(":")
        aggregates.setdefault(phase, {})[metric] = {
            "case_geometric_mean_ratio": geometric_mean(values),
            "case_p95_ratio": _percentile(values, 0.95),
        }

    structural_groups: dict[str, dict[str, float]] = defaultdict(dict)
    for (phase, metric, backend_pair), (control, candidate) in sorted(
        group_totals.items()
    ):
        structural_groups[backend_pair][f"{phase}:{metric}"] = candidate / control

    all_group_ratios = [
        ratio for values in structural_groups.values() for ratio in values.values()
    ]
    drift_ratios = {
        key: geometric_mean(values) for key, values in sorted(drift.items())
    }
    return {
        "schema_version": 1,
        "same_work": not mismatches,
        "mismatches": mismatches,
        "routing_contract_satisfied": not routing_violations,
        "routing_violations": routing_violations,
        "case_count": len(sources),
        "aggregates": aggregates,
        "structural_group_total_ratios": dict(sorted(structural_groups.items())),
        "no_structural_group_regression": all(value <= 1.0 for value in all_group_ratios),
        "drift_geometric_mean_ratios": drift_ratios,
        "run_order_stable": all(
            1.0 - _MAX_RUN_ORDER_DRIFT <= value <= 1.0 + _MAX_RUN_ORDER_DRIFT
            for value in drift_ratios.values()
        ),
        "maximum_accepted_run_order_drift": _MAX_RUN_ORDER_DRIFT,
        "finite_positive_ratios": all(
            math.isfinite(value) and value > 0 for value in all_group_ratios
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a1", type=Path)
    parser.add_argument("b1", type=Path)
    parser.add_argument("b2", type=Path)
    parser.add_argument("a2", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    report = compare_abba(
        _load(arguments.a1),
        _load(arguments.b1),
        _load(arguments.b2),
        _load(arguments.a2),
    )
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
    return 0 if report["same_work"] and report["routing_contract_satisfied"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
