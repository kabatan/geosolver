#!/usr/bin/env python3
"""Truth-free aggregate of Repair B's actual compile/backend cap seam."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping

from repair_adapter import (
    AdapterFailure,
    build_problem,
    load_pinned_algebraic_compiler,
    load_pinned_semantic_lift,
)


ARCHIVE_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
DEFAULT_DATASET = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-OMC-V15-MERGED5-EVAL-001/inputs/omc_v15_merged_5files.audit-canonical.jsonl"
)
SPLIT_MANIFEST = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-V15-243-001/benchmark/SPLIT_MANIFEST.json"
)
EXPECTED_SPLIT_SHA256 = "065b2602e515b16086768c5a60abf91248faee7ed0cb76b9d88d4c421bcbdf3f"
PROBLEM_ID = re.compile(rb'"problem_id":"([^"\\]+)"')

# Current exact_outer caps recognition at degree eight. This dense, square-free
# placeholder exercises the target-equation degree/term overhead without using
# a target value or any outcome. It has roots -1 and 0; (-1/2,1/2) isolates 0.
WORST_STATIC_DESCRIPTOR = {
    "minimal_polynomial_high_to_low": [1, 1, 1, 1, 1, 1, 1, 1, 0],
    "selected_real_root_index": 1,
    "isolating_interval": {
        "left": "-1/2",
        "right": "1/2",
        "multiplicity": 1,
        "real_root_index": 1,
    },
    "proposal_relation_low_to_high": [0, 1, 1, 1, 1, 1, 1, 1, 1],
    "confirmation_relation_low_to_high": [0, 1, 1, 1, 1, 1, 1, 1, 1],
    "target_768": "static-no-target-value",
    "target_1024": "static-no-target-value",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document(formulation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        # The executable source compilers require these envelope fields. They
        # are constant and carry neither corpus identity nor outcome.
        "id": "anonymous-static-development-source",
        "task": "solve",
        **{
        key: value
        for key, value in formulation.items()
        if key
        in {
            "variables",
            "bounds",
            "construction",
            "constraints",
            "guards",
            "answer",
            "post_process",
        }
        },
    }


def census(dataset: Path) -> dict[str, Any]:
    split_bytes = SPLIT_MANIFEST.read_bytes()
    if hashlib.sha256(split_bytes).hexdigest() != EXPECTED_SPLIT_SHA256:
        raise RuntimeError("split-manifest-digest-mismatch")
    development_ids = frozenset(json.loads(split_bytes)["partitions"]["development"]["case_ids"])
    if len(development_ids) != 145:
        raise RuntimeError("development-partition-size-mismatch")

    selected: list[dict[str, Any]] = []
    skipped_without_json_deserialization = 0
    dataset_bytes = dataset.read_bytes()
    for line in dataset_bytes.splitlines():
        if not line.strip():
            continue
        match = PROBLEM_ID.search(line)
        if match is None:
            raise RuntimeError("row-missing-problem-id")
        if match.group(1).decode("utf-8") not in development_ids:
            skipped_without_json_deserialization += 1
            continue
        # Only open-development rows cross JSON deserialization. Outer answer
        # is never indexed or copied; only the source formulation is retained.
        row = json.loads(line)
        selected.append(_document(row["formulation"]))
    if len(selected) != 145 or skipped_without_json_deserialization != 102:
        raise RuntimeError("partition-custody-mismatch")

    semantic = load_pinned_semantic_lift(fresh_name="geotarget_repair_b_applicability_semantic")
    algebraic = load_pinned_algebraic_compiler(fresh_name="geotarget_repair_b_applicability_algebraic")
    stages: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    maximum_terms = []
    total_terms = []
    maximum_degrees = []
    started = time.monotonic()
    for document in selected:
        try:
            semantic_artifact = semantic.compile_document(document)
            stages["semantic_compile_pass"] += 1
        except Exception:  # noqa: BLE001 - aggregate fixed taxonomy only
            reasons["semantic_compile_rejected"] += 1
            continue
        try:
            algebraic_artifact = algebraic.compile_document(document)
            stages["algebraic_compile_pass"] += 1
        except Exception:  # noqa: BLE001
            reasons["algebraic_compile_rejected"] += 1
            continue
        try:
            _problem, binding = build_problem(
                algebraic_artifact,
                semantic_artifact,
                WORST_STATIC_DESCRIPTOR,
            )
            stages["actual_backend_caps_pass_with_dense_degree8_target"] += 1
            terms = binding["actual_terms"]
            maximum_terms.append(int(terms["maximum_per_polynomial"]))
            total_terms.append(int(terms["total_all_d0_polynomials"]))
            maximum_degrees.append(int(terms["maximum_total_degree"]))
        except AdapterFailure as error:
            # Adapter reasons are mechanism taxonomy, not case identity/result.
            reasons[error.reason] += 1
        except Exception:  # noqa: BLE001
            reasons["unexpected_backend_rejection"] += 1

    return {
        "schema": "geotarget.target-hermite-repair-b-static-applicability/v1",
        "authority": "TRUTH_FREE_STATIC_DEVELOPMENT_COMPILE_AND_BACKEND_CAPS_ONLY",
        "partition": "development",
        "case_count": 145,
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "split_manifest_sha256": EXPECTED_SPLIT_SHA256,
        "nondevelopment_rows_skipped_without_json_deserialization": skipped_without_json_deserialization,
        "validation_or_sealed_formulation_parsed": False,
        "outer_truth_indexed_or_copied": False,
        "individual_case_records_emitted": False,
        "formal_execute_or_scorer_used": False,
        "ordinary_descriptor_or_endpoint_used": False,
        "static_target_descriptor": "dense-square-free-degree8-cap-probe",
        "stage_counts": dict(sorted(stages.items())),
        "rejection_reason_histogram": dict(sorted(reasons.items())),
        "passing_term_aggregate": {
            "case_count": len(total_terms),
            "maximum_per_polynomial": max(maximum_terms, default=None),
            "maximum_total_terms": max(total_terms, default=None),
            "maximum_total_degree": max(maximum_degrees, default=None),
        },
        "interpretation_limit": (
            "This is a source-only applicability aggregate through the exact pinned compilers and Repair B "
            "backend caps. It is not an activation, solved, recall, authority, or affordability count. A real "
            "ordinary square-free descriptor and hard-child certificate are still mandatory."
        ),
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
