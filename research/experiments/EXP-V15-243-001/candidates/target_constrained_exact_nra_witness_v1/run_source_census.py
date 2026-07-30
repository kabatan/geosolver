#!/usr/bin/env python3
"""Anonymous development145 source-only applicability census."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from applicability import (
    DESCRIPTOR_GROEBNER_SECONDS,
    EXPECTED_LEGACY_COMPILER_SHA256,
    MAX_QUOTIENT_ENUMERATION,
    STATIC_GROEBNER_SECONDS,
    aggregate,
    assess_source_document,
)
import candidate as backend


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SPLIT_MANIFEST = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/benchmark/SPLIT_MANIFEST.json"
)
DEFAULT_DATASET = (
    RUNTIME_ROOT
    / "research/experiments/EXP-OMC-V15-MERGED5-EVAL-001/inputs/"
    "omc_v15_merged_5files.audit-canonical.jsonl"
)
EXPECTED_DATASET_SHA256 = frozenset(
    {
        # Original canonical order used by the frozen semantic-lift census.
        "e587c6ea3f315f270e13cae859bba947f52e59afb651b7485061fdc49be06b8f",
        # Same 247-row source corpus in the current audit-canonical key order.
        "2d6904cfbce214c35c71fc43be3f7799fa6072bb6d17c1930e128f76a00a1bdc",
    }
)
EXPECTED_SPLIT_SHA256 = "065b2602e515b16086768c5a60abf91248faee7ed0cb76b9d88d4c421bcbdf3f"
PROBLEM_ID_FIELD = re.compile(rb'"problem_id":"([^"\\]+)"')


def census(dataset: Path) -> dict[str, object]:
    payload = dataset.read_bytes()
    dataset_sha = hashlib.sha256(payload).hexdigest()
    if dataset_sha not in EXPECTED_DATASET_SHA256:
        raise ValueError(f"dataset digest mismatch: {dataset_sha}")
    split_payload = SPLIT_MANIFEST.read_bytes()
    split_sha = hashlib.sha256(split_payload).hexdigest()
    if split_sha != EXPECTED_SPLIT_SHA256:
        raise ValueError(f"split digest mismatch: {split_sha}")
    development = frozenset(
        json.loads(split_payload)["partitions"]["development"]["case_ids"]
    )
    rows = []
    skipped = 0
    started = time.monotonic()
    for line in payload.splitlines():
        if not line.strip():
            continue
        match = PROBLEM_ID_FIELD.search(line)
        if match is None:
            raise ValueError("noncanonical problem-id prefix")
        if match.group(1).decode("utf-8") not in development:
            skipped += 1
            continue
        outer = json.loads(line)
        formulation = outer["formulation"]
        # Only source semantics are projected.  No outer truth, expected
        # target, family, score or outcome is passed to the candidate.
        document = {
            key: formulation[key]
            for key in (
                "variables",
                "bounds",
                "construction",
                "constraints",
                "guards",
                "answer",
                "post_process",
            )
            if key in formulation
        }
        rows.append(assess_source_document(document, proposal=None))
    if len(rows) != 145 or skipped != 102:
        raise ValueError(f"custody mismatch: development={len(rows)} skipped={skipped}")
    summary = aggregate(rows)
    eligible_strata = summary["statically_admissible_stratum_count"]
    seam_count = summary["source_replay_and_target_link_seam_complete_count"]
    return {
        "schema_version": "geotarget.target-constrained-nra-source-census/v1",
        "authority": "TRUTH_FREE_SOURCE_ONLY_APPLICABILITY_NOT_SOLVED_OR_SCORED",
        "decision": "HOLD_DESCRIPTOR_SEAM",
        "decision_reason": (
            "Static admissibility is visible, but real solver-proposed squarefree "
            "polynomial/ordinal/isolator inputs are unavailable source-only; the "
            "legacy primitive cover also remains non-authoritative until canonical "
            "source replay is connected."
        ),
        "dataset_sha256": dataset_sha,
        "split_manifest_sha256": split_sha,
        "partition": "development",
        "nondevelopment_rows_skipped_without_deserializing": skipped,
        "validation_or_sealed_formulation_parsed": False,
        "outer_truth_expected_target_family_outcome_read_by_candidate": False,
        "case_identity_available_to_candidate": False,
        "individual_records_emitted": False,
        "real_proposal_descriptor_present": False,
        "anonymous_strata_gate_two_or_more": eligible_strata >= 2,
        "source_replay_target_link_seam_gate": seam_count > 0,
        "formal_execute_or_scorer_used": False,
        "backend_resource_caps": {
            "source_variables": backend.MAX_VARIABLES,
            "equations_including_target_link_and_descriptor": backend.MAX_EQUATIONS,
            "total_degree": backend.MAX_TOTAL_DEGREE,
            "terms_per_polynomial": backend.MAX_TERMS,
            "static_groebner_seconds_per_source": STATIC_GROEBNER_SECONDS,
            "descriptor_groebner_seconds_per_source": DESCRIPTOR_GROEBNER_SECONDS,
            "quotient_enumeration": MAX_QUOTIENT_ENUMERATION,
        },
        "digest_pinned_existing_primitive_compiler_sha256": (
            EXPECTED_LEGACY_COMPILER_SHA256
        ),
        "elapsed_seconds": time.monotonic() - started,
        **summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )
    parser.add_argument("--output", type=Path, default=HERE / "SOURCE_CENSUS.json")
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
