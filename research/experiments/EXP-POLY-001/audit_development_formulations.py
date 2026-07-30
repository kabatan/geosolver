#!/usr/bin/env python3
"""Truth-blind static applicability audit over formulation fields only.

The development JSONL may contain outcome-bearing sibling fields.  This parser
therefore does not deserialize a row.  It lexically slices the top-level
``formulation`` value, skips every sibling value without decoding it, and only
then invokes ``json.loads`` on the formulation bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import Mapping

from polynomial_side_route import PolynomialLimits, detect_polynomial_plan


EXPECTED_DEVELOPMENT_SHA256 = (
    "c150bb352fc905dc4eead8a56ec50125d6dd2409d2de14ccd91a502836ea8511"
)
EXPECTED_FORMULATION_COUNT = 145


class SourceBoundaryError(ValueError):
    pass


def _skip_space(data: bytes, offset: int) -> int:
    while offset < len(data) and data[offset] in b" \t\r\n":
        offset += 1
    return offset


def _string_end(data: bytes, offset: int) -> int:
    if offset >= len(data) or data[offset] != ord('"'):
        raise SourceBoundaryError("expected JSON string")
    offset += 1
    while offset < len(data):
        byte = data[offset]
        if byte == ord('"'):
            return offset + 1
        if byte == ord("\\"):
            offset += 2
        else:
            offset += 1
    raise SourceBoundaryError("unterminated JSON string")


def _value_end(data: bytes, offset: int) -> int:
    """Return the end of one JSON value without materializing its contents."""

    offset = _skip_space(data, offset)
    if offset >= len(data):
        raise SourceBoundaryError("missing JSON value")
    if data[offset] == ord('"'):
        return _string_end(data, offset)
    if data[offset] in (ord("{"), ord("[")):
        stack = [data[offset]]
        offset += 1
        while offset < len(data) and stack:
            byte = data[offset]
            if byte == ord('"'):
                offset = _string_end(data, offset)
                continue
            if byte in (ord("{"), ord("[")):
                stack.append(byte)
            elif byte == ord("}"):
                if stack.pop() != ord("{"):
                    raise SourceBoundaryError("mismatched JSON container")
            elif byte == ord("]"):
                if stack.pop() != ord("["):
                    raise SourceBoundaryError("mismatched JSON container")
            offset += 1
        if stack:
            raise SourceBoundaryError("unterminated JSON container")
        return offset
    while offset < len(data) and data[offset] not in b",}] \t\r\n":
        offset += 1
    if offset == 0:
        raise SourceBoundaryError("empty JSON scalar")
    return offset


def formulation_bytes(row: bytes) -> bytes:
    """Extract only the top-level formulation value from one JSON object."""

    offset = _skip_space(row, 0)
    if offset >= len(row) or row[offset] != ord("{"):
        raise SourceBoundaryError("row is not a JSON object")
    offset += 1
    found: bytes | None = None
    while True:
        offset = _skip_space(row, offset)
        if offset < len(row) and row[offset] == ord("}"):
            offset += 1
            break
        key_end = _string_end(row, offset)
        # Only the property name is decoded. Sibling values are never decoded.
        key = json.loads(row[offset:key_end])
        offset = _skip_space(row, key_end)
        if offset >= len(row) or row[offset] != ord(":"):
            raise SourceBoundaryError("missing property separator")
        start = _skip_space(row, offset + 1)
        end = _value_end(row, start)
        if key == "formulation":
            if found is not None:
                raise SourceBoundaryError("duplicate formulation property")
            found = row[start:end]
        offset = _skip_space(row, end)
        if offset < len(row) and row[offset] == ord(","):
            offset += 1
            continue
        if offset < len(row) and row[offset] == ord("}"):
            offset += 1
            break
        raise SourceBoundaryError("malformed top-level object")
    if _skip_space(row, offset) != len(row):
        raise SourceBoundaryError("trailing bytes after top-level object")
    if found is None:
        raise SourceBoundaryError("formulation property absent")
    return found


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))
    return ordered[index]


def audit(path: Path) -> dict[str, object]:
    classifications: dict[str, int] = {}
    activation_dimensions: dict[str, int] = {}
    activation_degrees: dict[str, int] = {}
    activation_terms: dict[str, int] = {}
    detector_ns: list[int] = []
    container_digest = hashlib.sha256()
    formulation_digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for raw_row in handle:
            container_digest.update(raw_row)
            if not raw_row.strip():
                continue
            source = formulation_bytes(raw_row.rstrip(b"\r\n"))
            formulation_digest.update(len(source).to_bytes(8, "big"))
            formulation_digest.update(source)
            formulation = json.loads(source)
            if not isinstance(formulation, Mapping):
                raise SourceBoundaryError("formulation is not an object")
            started = time.perf_counter_ns()
            plan = detect_polynomial_plan(formulation)
            detector_ns.append(time.perf_counter_ns() - started)
            reason = "applicable" if plan.applicable else plan.reason
            classifications[reason] = classifications.get(reason, 0) + 1
            if plan.applicable:
                for table, value in (
                    (activation_dimensions, len(plan.variable_names)),
                    (activation_degrees, plan.maximum_total_degree),
                    (activation_terms, plan.total_terms),
                ):
                    key = str(value)
                    table[key] = table.get(key, 0) + 1
            count += 1
    if count != EXPECTED_FORMULATION_COUNT:
        raise SourceBoundaryError("development formulation count mismatch")
    observed_container_digest = container_digest.hexdigest()
    if observed_container_digest != EXPECTED_DEVELOPMENT_SHA256:
        raise SourceBoundaryError("development source SHA-256 mismatch")

    applicable = classifications.get("applicable", 0)
    limits = PolynomialLimits()
    cap_reasons = (
        "dimension_cap",
        "degree_cap",
        "terms_per_equation_cap",
        "total_terms_cap",
        "coefficient_bits_cap",
        "solution_cap",
    )
    return {
        "schema_version": "geotarget.exp-poly-001-static-audit/v1",
        "custody": {
            "verified_input_container_sha256": observed_container_digest,
            "formulation_stream_sha256": formulation_digest.hexdigest(),
            "formulation_count": count,
            "row_objects_deserialized": False,
            "sibling_values_deserialized": False,
            "problem_ids_retained_or_reported": False,
            "gold_scorer_expected_or_result_loaded": False,
            "formal_solver_run": False,
        },
        "gate": {
            "limits": {
                "maximum_variables": limits.maximum_variables,
                "maximum_total_degree": limits.maximum_total_degree,
                "maximum_terms_per_equation": limits.maximum_terms_per_equation,
                "maximum_total_terms": limits.maximum_total_terms,
                "maximum_coefficient_bits": limits.maximum_coefficient_bits,
                "maximum_solutions": limits.maximum_solutions,
            },
            "activation_count": applicable,
            "activation_rate": applicable / count,
            "classification_counts": dict(sorted(classifications.items())),
            "cap_rejection_counts": {
                reason: classifications.get(reason, 0) for reason in cap_reasons
            },
            "applicable_dimension_counts": dict(sorted(activation_dimensions.items())),
            "applicable_degree_counts": dict(sorted(activation_degrees.items())),
            "applicable_total_term_counts": dict(sorted(activation_terms.items())),
        },
        "estimated_side_lane_cost": {
            "method": "static detector timing plus registered hard-cap envelope; symbolic solver was not run",
            "detector_total_ns": sum(detector_ns),
            "detector_median_ns": int(statistics.median(detector_ns)),
            "detector_p95_ns": _percentile(detector_ns, 0.95),
            "symbolic_process_cap_seconds_per_activated_case": 2.0,
            "aggregate_symbolic_cap_seconds": 2.0 * applicable,
            "default_symbolic_start_share": 0.25,
            "baseline_minimum_share": 0.5,
            "baseline_default_share": 0.75,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    report = audit(arguments.dataset)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
