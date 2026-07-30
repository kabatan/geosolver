#!/usr/bin/env python3
"""Aggregate-only formulation audit for the BTF/polynomial combination."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import Mapping

from btf_polynomial_pipeline import detect_btf_polynomial_plan
from polynomial_side_route import detect_polynomial_plan
from audit_development_formulations import (
    EXPECTED_DEVELOPMENT_SHA256,
    EXPECTED_FORMULATION_COUNT,
    SourceBoundaryError,
    formulation_bytes,
)


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def audit(path: Path) -> dict[str, object]:
    container_digest = hashlib.sha256()
    formulation_digest = hashlib.sha256()
    structure_reasons = collections.Counter()
    block_gate_reasons = collections.Counter()
    active_blocks_per_case = collections.Counter()
    active_block_dimensions = collections.Counter()
    whole_activations = 0
    combined_activations = 0
    decomposable = 0
    parse_failures = 0
    count = 0
    detector_ns: list[int] = []

    with path.open("rb") as source:
        for raw_row in source:
            container_digest.update(raw_row)
            if not raw_row.strip():
                continue
            encoded = formulation_bytes(raw_row.rstrip(b"\r\n"))
            formulation_digest.update(len(encoded).to_bytes(8, "big"))
            formulation_digest.update(encoded)
            formulation = json.loads(encoded)
            if not isinstance(formulation, Mapping):
                raise SourceBoundaryError("formulation is not an object")
            started = time.perf_counter_ns()
            whole = detect_polynomial_plan(formulation)
            combined = detect_btf_polynomial_plan(formulation)
            detector_ns.append(time.perf_counter_ns() - started)
            whole_activations += whole.applicable
            if combined.structure_plan is None:
                parse_failures += 1
                structure_reasons[combined.reason] += 1
            else:
                structure_reasons[combined.structure_plan.reason] += 1
                if combined.structure_plan.applicable:
                    decomposable += 1
                    for gate in combined.block_gates:
                        block_gate_reasons[gate.polynomial_plan.reason] += 1
            active_count = len(combined.active_blocks)
            if active_count:
                combined_activations += 1
                active_blocks_per_case[str(active_count)] += 1
                for gate in combined.active_blocks:
                    active_block_dimensions[str(len(gate.variable_indices))] += 1
            count += 1

    observed_digest = container_digest.hexdigest()
    if observed_digest != EXPECTED_DEVELOPMENT_SHA256:
        raise SourceBoundaryError("development source SHA-256 mismatch")
    if count != EXPECTED_FORMULATION_COUNT:
        raise SourceBoundaryError("development formulation count mismatch")
    return {
        "schema_version": "geotarget.exp-struct-poly-001-static-audit/v1",
        "custody": {
            "verified_input_container_sha256": observed_digest,
            "formulation_stream_sha256": formulation_digest.hexdigest(),
            "formulation_count": count,
            "row_objects_deserialized": False,
            "sibling_values_deserialized": False,
            "problem_ids_retained_or_reported": False,
            "gold_scorer_expected_or_result_loaded": False,
            "formal_solver_run": False,
        },
        "activation": {
            "whole_system_strict_polynomial_cases": whole_activations,
            "btf_decomposable_cases": decomposable,
            "btf_then_strict_polynomial_cases": combined_activations,
            "btf_then_strict_polynomial_rate": combined_activations / count,
            "active_blocks_per_case_histogram": dict(sorted(active_blocks_per_case.items())),
            "active_block_dimension_histogram": dict(sorted(active_block_dimensions.items())),
        },
        "taxonomy": {
            "structure_reason_counts": dict(sorted(structure_reasons.items())),
            "decomposed_block_gate_reason_counts": dict(sorted(block_gate_reasons.items())),
            "structure_parse_failures": parse_failures,
        },
        "estimated_side_lane_cost": {
            "method": "static combined-gate timing plus two-second per-case route cap; symbolic solver was not run",
            "detector_total_ns": sum(detector_ns),
            "detector_median_ns": int(statistics.median(detector_ns)),
            "detector_p95_ns": _percentile(detector_ns, 0.95),
            "symbolic_process_cap_seconds_per_activated_case": 2.0,
            "aggregate_symbolic_cap_seconds": 2.0 * combined_activations,
            "baseline_minimum_share": 0.5,
            "baseline_default_share": 0.75,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    arguments.output.write_text(
        json.dumps(audit(arguments.dataset), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
