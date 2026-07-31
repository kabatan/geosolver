#!/usr/bin/env python3.12
"""Root-owned four-record ordinary/NRA binding runner.

Individual audit artifacts stay under the approved repository-external panel
root.  The public aggregate contains fixed counts and one order-sensitive
signature only; it contains no paths, identities, descriptors, targets, or
individual failure reasons.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Mapping

import ordinary_proposal_binding as binding


EXPECTED_REQUEST_COUNT = 4
FAILURE_CLASSES = (
    "CUSTODY_OR_DIGEST_REJECTED",
    "ENDPOINT_BINDING_REJECTED",
    "ORDINARY_DESCRIPTOR_BINDING_REJECTED",
    "EXISTING_COMPILER_SUBSET_REJECTED",
    "BACKEND_RESOURCE_OR_TIMEOUT",
    "BACKEND_UNSAT_OR_NO_WITNESS",
    "UNTOUCHED_REPLAY_REJECTED",
    "OTHER_FAIL_CLOSED",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--proposal-root", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--backend-timeout-seconds", type=float, default=3.0)
    return parser


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = binding.canonical_bytes(value) + b"\n"
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _approved_output_path(path: Path, *, role: str) -> Path:
    resolved_parent = path.parent.resolve()
    if resolved_parent != binding.APPROVED_PANEL_ROOT or path.suffix != ".json":
        raise SystemExit(f"{role} must be one JSON file in the approved panel root")
    return resolved_parent / path.name


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("ordinary proposal binding must be pinned to expected CPU")
    if (
        not math.isfinite(arguments.backend_timeout_seconds)
        or arguments.backend_timeout_seconds <= 0
    ):
        raise SystemExit("backend timeout must be finite and positive")
    source_root, proposal_root = binding.require_approved_roots(
        arguments.source_root, arguments.proposal_root
    )
    requests_path = arguments.requests.resolve()
    if (
        requests_path.parent != binding.APPROVED_PANEL_ROOT
        or requests_path.name != "requests.json"
        or not requests_path.is_file()
    ):
        raise SystemExit("requests manifest is outside approved custody")
    artifact_dir = arguments.artifact_dir.resolve()
    if artifact_dir != (binding.APPROVED_PANEL_ROOT / "connector-artifacts"):
        raise SystemExit("individual artifact directory is outside approved custody")
    output = _approved_output_path(arguments.output, role="aggregate output")

    payload = requests_path.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("requests SHA-256 mismatch")
    requests = json.loads(payload)
    if not isinstance(requests, list) or len(requests) != EXPECTED_REQUEST_COUNT:
        raise SystemExit("selected manifest must contain exactly four rows")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    if any(artifact_dir.iterdir()):
        raise SystemExit("individual artifact directory must start empty")
    counts: Counter[str] = Counter()
    signatures: list[str] = []
    for ordinal, row in enumerate(requests):
        if not isinstance(row, Mapping):
            raise SystemExit("selected manifest row is malformed")
        result = binding.connect(
            row,
            source_root=source_root,
            proposal_root=proposal_root,
            timeout_seconds=arguments.backend_timeout_seconds,
        )
        _atomic_write(artifact_dir / f"{ordinal:04d}.json", result)
        counts[
            "binding_ready" if result.get("binding_ready") else "binding_rejected"
        ] += 1
        counts[
            "authority_boundary_descriptor_ready"
            if result.get("authority_boundary_descriptor_ready")
            else "authority_boundary_descriptor_not_ready"
        ] += 1
        for signal in ("ordinary_binding_pass", "exact_replay_pass", "readiness"):
            if result.get(signal) is True:
                counts[signal] += 1
        failure = str(result.get("failure_class", "OTHER_FAIL_CLOSED"))
        if failure != "NONE":
            if failure not in FAILURE_CLASSES:
                failure = "OTHER_FAIL_CLOSED"
            counts[f"failure:{failure}"] += 1
        signature = result.get("binding_signature_sha256")
        if isinstance(signature, str):
            signatures.append(signature)

    aggregate_signature = hashlib.sha256(
        binding.canonical_bytes(signatures)
    ).hexdigest()
    aggregate = {
        "schema_version": "geotarget.target-constrained-nra-ordinary-binding-aggregate/v1",
        "request_count": len(requests),
        "requests_sha256": observed_sha256,
        "binding_ready_count": counts["binding_ready"],
        "binding_rejected_count": counts["binding_rejected"],
        "authority_boundary_descriptor_ready_count": counts[
            "authority_boundary_descriptor_ready"
        ],
        "authority_boundary_descriptor_not_ready_count": counts[
            "authority_boundary_descriptor_not_ready"
        ],
        "ordinary_binding_pass_count": counts["ordinary_binding_pass"],
        "exact_replay_pass_count": counts["exact_replay_pass"],
        "readiness_count": counts["readiness"],
        "fixed_failure_counts": {
            name: counts[f"failure:{name}"] for name in FAILURE_CLASSES
        },
        "ordered_binding_signature_sha256": aggregate_signature,
        "individual_artifact_count": len(requests),
        "individual_artifacts_repo_external": True,
        "individual_records_emitted_in_aggregate": False,
        "paths_or_descriptors_emitted_in_aggregate": False,
        "authority_pass": False,
        "target_release": False,
        "connector_audit_required_before_release": True,
        "target_set_completeness_claim": False,
        "canonical_source_replay_bypassed": False,
        "truth_used": False,
        "case_family_target_count_routing": False,
    }
    _atomic_write(output, aggregate)
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
