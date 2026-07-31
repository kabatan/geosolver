#!/usr/bin/env python3.12
"""Generated S0 for complete ordinary proposal binding and fail-closed seams."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

import build_ordinary_binding_manifest as builder
import ordinary_proposal_binding as binding


HERE = Path(__file__).resolve().parent


def _descriptor(root: int) -> dict[str, object]:
    return {
        "minimal_polynomial_high_to_low": [1, -root],
        "selected_real_root_index": 0,
        "isolating_interval": {
            "left": str(root - 1),
            "right": str(root + 1),
            "multiplicity": 1,
            "real_root_index": 0,
        },
        "proposal_relation_low_to_high": [-root, 1],
        "confirmation_relation_low_to_high": [-root, 1],
        "target_768": str(root),
        "target_1024": str(root),
    }


def _write_fixture(
    source_root: Path,
    proposal_root: Path,
    original_root: Path,
    *,
    ordinal: int,
    source_document: dict[str, object],
    root: int,
) -> dict[str, object]:
    source = source_root / f"{ordinal:04d}.json"
    source.write_text(
        json.dumps(source_document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    endpoint = [float(root)]
    endpoint_sha256 = binding.endpoint_float64_sha256(endpoint)
    attempt = {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "endpoint_float64_sha256": endpoint_sha256,
        "descriptor": _descriptor(root),
        "case_family_truth_target_count_routing": False,
    }
    original_case_root = original_root / f"anonymous-{ordinal:04d}"
    original_case_root.mkdir()
    original_result = original_case_root / "RESULT.json"
    original_result.write_bytes(
        binding.canonical_bytes(
            {
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "hp_attempts": [attempt],
            }
        )
        + b"\n"
    )
    artifact = {
        "schema_version": binding.PROPOSAL_SCHEMA,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "endpoint_float64_sha256": endpoint_sha256,
        "original_result_sha256": hashlib.sha256(
            original_result.read_bytes()
        ).hexdigest(),
        "ordinary_attempt_sha256": binding.canonical_sha256(attempt),
        "ordinary_attempt": attempt,
        "truth_used": False,
        "case_family_target_count_routing": False,
    }
    proposal = proposal_root / f"{ordinal:04d}.json"
    proposal.write_bytes(binding.canonical_bytes(artifact) + b"\n")
    return {
        "source_rel": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "endpoint_float64_bits_hex": binding.endpoint_bits_hex(endpoint),
        "endpoint_float64_sha256": endpoint_sha256,
        "degree1_descriptor": {
            "minimal_polynomial_high_to_low": [1, -root],
            "selected_real_root_index": 0,
        },
        "proposal_result_rel": proposal.name,
        "proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
    }


def _direct_document(root: int) -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x", "value": str(root)}],
        "guards": [],
        "bounds": [[-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=HERE / "ORDINARY_BINDING_GENERATED_RESULT.json"
    )
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("generated binding S0 must be pinned to expected CPU")

    with tempfile.TemporaryDirectory(prefix="geotarget-nra-binding-") as temporary:
        root_path = Path(temporary)
        source_root = root_path / "sources"
        proposal_root = root_path / "proposals"
        original_root = root_path / "original-results"
        source_root.mkdir()
        proposal_root.mkdir()
        original_root.mkdir()
        binding.APPROVED_SOURCE_ROOT = source_root.resolve()
        binding.APPROVED_PROPOSAL_ROOT = proposal_root.resolve()
        binding.APPROVED_ORIGINAL_RESULT_ROOT = original_root.resolve()

        direct = _write_fixture(
            source_root,
            proposal_root,
            original_root,
            ordinal=0,
            source_document=_direct_document(3),
            root=3,
        )
        positive = binding.connect(
            direct,
            source_root=source_root,
            proposal_root=proposal_root,
            original_result_root=original_root,
            timeout_seconds=3.0,
        )

        tampered = []
        for role in ("source", "endpoint", "descriptor", "proposal"):
            row = deepcopy(direct)
            if role == "source":
                row["source_sha256"] = "0" * 64
            elif role == "endpoint":
                row["endpoint_float64_bits_hex"][0] = "4008000000000001"
            elif role == "descriptor":
                row["degree1_descriptor"]["minimal_polynomial_high_to_low"] = [1, -4]
            else:
                row["proposal_sha256"] = "0" * 64
            tampered.append(
                binding.connect(
                    row,
                    source_root=source_root,
                    proposal_root=proposal_root,
                    original_result_root=original_root,
                    timeout_seconds=3.0,
                )
            )

        attempt = {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "endpoint_float64_sha256": direct["endpoint_float64_sha256"],
            "descriptor": _descriptor(3),
        }
        duplicate_count = len(
            builder._matching_attempts(
                {
                    "source_sha256": direct["source_sha256"],
                    "hp_attempts": [attempt, deepcopy(attempt)],
                },
                source_sha256=str(direct["source_sha256"]),
                endpoint_sha256=str(direct["endpoint_float64_sha256"]),
                identity=((1, -3), 0),
            )
        )

        multitarget_document = {
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x*x", "value": "1"}],
            "guards": [],
            "bounds": [[-2, 2]],
            "answer": "x",
            "post_process": None,
        }
        multitarget_row = _write_fixture(
            source_root,
            proposal_root,
            original_root,
            ordinal=1,
            source_document=multitarget_document,
            root=1,
        )
        multitarget = binding.connect(
            multitarget_row,
            source_root=source_root,
            proposal_root=proposal_root,
            original_result_root=original_root,
            timeout_seconds=3.0,
        )

    tamper_reject_count = sum(
        item.get("binding_ready") is False and item.get("target_release") is False
        for item in tampered
    )
    decision = (
        "GO_AUDIT"
        if (
            positive.get("binding_ready") is True
            and positive.get("authority_pass") is False
            and positive.get("target_release") is False
            and tamper_reject_count == 4
            and duplicate_count == 2
            and multitarget.get("binding_ready") is True
            and multitarget.get("target_set_completeness_claim") is False
            and multitarget.get("target_release") is False
        )
        else "STOP"
    )
    result = {
        "schema_version": "geotarget.target-constrained-nra-ordinary-binding-generated/v1",
        "decision": decision,
        "positive_binding_ready_count": int(positive.get("binding_ready") is True),
        "positive_ordinary_binding_pass_count": int(
            positive.get("ordinary_binding_pass") is True
        ),
        "positive_exact_replay_pass_count": int(
            positive.get("exact_replay_pass") is True
        ),
        "positive_readiness_count": int(positive.get("readiness") is True),
        "positive_external_authority_pass_count": int(
            positive.get("authority_pass") is True
        ),
        "positive_target_release_count": int(positive.get("target_release") is True),
        "tamper_case_count": len(tampered),
        "tamper_reject_count": tamper_reject_count,
        "duplicate_match_count": duplicate_count,
        "duplicate_rejected_by_builder_cardinality_rule": duplicate_count != 1,
        "multitarget_binding_ready_count": int(
            multitarget.get("binding_ready") is True
        ),
        "multitarget_completeness_claim_count": int(
            multitarget.get("target_set_completeness_claim") is True
        ),
        "multitarget_target_release_count": int(
            multitarget.get("target_release") is True
        ),
        "canonical_source_replay_bypassed": False,
        "truth_used": False,
        "case_family_target_count_routing": False,
    }
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if decision == "GO_AUDIT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
