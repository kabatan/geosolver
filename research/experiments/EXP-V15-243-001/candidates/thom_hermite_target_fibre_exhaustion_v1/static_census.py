#!/usr/bin/env python3
"""Aggregate-only capability census for the Hermite target-fibre D0.

The root-owned producer must pass a sanitized feature panel.  This consumer
rejects unknown/per-record identity fields and emits counts only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "geotarget.thom-hermite-static-capability-panel/v1"
OUTPUT_SCHEMA = "geotarget.thom-hermite-static-census-counts/v1"
CAPS = {
    "source_variable_count": 3,
    "cover_variable_count": 8,
    "equation_count": 12,
    "max_total_degree": 6,
    "total_term_count": 512,
    "max_coefficient_bits": 2048,
    "predicate_count": 3,
    "global_upper_degree": 16,
    "target_root_count": 16,
    "max_target_factor_degree": 4,
    "max_specialized_quotient_dimension": 24,
}
BOOLEAN_FIELDS = {
    "complete_semantic_cover",
    "reversible_semantic_cover",
    "qq_coefficients",
    "exact_raw_target_ast",
    "complete_predicate_ledger",
    "global_upper_proof_producer_available",
    "global_upper_identity_provable",
    "all_specialized_fibres_finite",
    "ordered_field_sign_available",
}
INTEGER_FIELDS = set(CAPS)
RECORD_FIELDS = BOOLEAN_FIELDS | INTEGER_FIELDS


class CensusInputError(ValueError):
    """The root-owned aggregate panel violates the frozen input contract."""


def _record(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CensusInputError("panel record is not an object")
    if set(value) != RECORD_FIELDS:
        raise CensusInputError("panel record fields differ from frozen whitelist")
    result = dict(value)
    for field in BOOLEAN_FIELDS:
        if type(result[field]) is not bool:
            raise CensusInputError("panel Boolean field is malformed")
    for field in INTEGER_FIELDS:
        item = result[field]
        if type(item) is not int or item < 0:
            raise CensusInputError("panel integer field is malformed")
    return result


def _bucket(value: int, boundaries: Sequence[int]) -> int:
    for index, boundary in enumerate(boundaries):
        if value <= boundary:
            return index
    return len(boundaries)


def _eligible(record: Mapping[str, Any]) -> bool:
    if not all(record[field] for field in BOOLEAN_FIELDS):
        return False
    return all(record[field] <= cap for field, cap in CAPS.items())


def _signature(record: Mapping[str, Any]) -> tuple[int, ...]:
    shape_delta = int(record["equation_count"]) - int(record["cover_variable_count"])
    return (
        _bucket(int(record["source_variable_count"]), (0, 1, 2, 3)),
        _bucket(int(record["cover_variable_count"]), (1, 2, 4, 8)),
        -1 if shape_delta < 0 else (0 if shape_delta == 0 else 1),
        _bucket(int(record["max_total_degree"]), (1, 2, 4, 6)),
        _bucket(int(record["global_upper_degree"]), (1, 2, 4, 8, 16)),
        _bucket(int(record["max_specialized_quotient_dimension"]), (1, 2, 4, 8, 16, 24)),
        int(record["predicate_count"]),
    )


def summarize(document: Any) -> dict[str, Any]:
    if not isinstance(document, Mapping) or set(document) != {
        "schema_version",
        "records",
    }:
        raise CensusInputError("panel top-level contract is malformed")
    if document["schema_version"] != SCHEMA:
        raise CensusInputError("panel schema mismatch")
    raw_records = document["records"]
    if not isinstance(raw_records, list) or len(raw_records) > 10_000:
        raise CensusInputError("panel record list is malformed or over cap")
    records = [_record(value) for value in raw_records]
    eligible = [record for record in records if _eligible(record)]
    signature_count = len({_signature(record) for record in eligible})
    return {
        "schema_version": OUTPUT_SCHEMA,
        "candidate": "THOM_HERMITE_TARGET_FIBRE_EXHAUSTION_V1",
        "scope": "AGGREGATE_SOURCE_CAPABILITY_ONLY",
        "counts": {
            "input_count": len(records),
            "eligible_count": len(eligible),
            "ineligible_count": len(records) - len(eligible),
            "eligible_signature_count": signature_count,
        },
        "gate": {
            "minimum_eligible_count": 4,
            "minimum_signature_count": 2,
            "pass": len(eligible) >= 4 and signature_count >= 2,
        },
        "authority": False,
        "release": False,
        "individual_records_emitted": False,
        "identifiers_hashes_paths_polynomials_emitted": False,
    }


def _load(path: Path) -> Any:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise CensusInputError("panel exceeds 4 MiB cap")
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, result: Mapping[str, Any]) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        result = summarize(_load(arguments.panel))
        _write(arguments.output, result)
    except (CensusInputError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": type(error).__name__}))
        return 2
    print(json.dumps({"status": "COUNTS_WRITTEN", "gate_pass": result["gate"]["pass"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
