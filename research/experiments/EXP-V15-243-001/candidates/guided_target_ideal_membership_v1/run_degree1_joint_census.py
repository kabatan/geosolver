#!/usr/bin/env python3
"""Aggregate-only degree-one three-way-join viability census.

The input is a root-owned, outcome-blind projection.  In particular it does
not contain the complete ordinary proposal.  Consequently this runner may
measure experimental viability, but it can never emit target authority.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Mapping, Sequence

from ideal_membership import prove_subset_identity, rational_candidate_from_descriptor
from typed_join import prepare_typed_regular_job, verify_three_way_join


RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
JULIA = Path("/home/kabatan/.juliaup/bin/julia")
WORKER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/local_validated_witness/worker.jl"
)
PROJECT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-002/interval_completeness"
)
REQUEST_KEYS = frozenset(
    {"source_path", "endpoint", "candidate_relation_high_to_low"}
)
FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "family",
        "truth",
        "answer",
        "target",
        "outcome",
        "result",
        "score",
        "known_count",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--proof-timeout-seconds", type=float, default=3.0)
    parser.add_argument("--worker-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--run-workers", action="store_true")
    return parser


def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _projection_proposal(coefficients: object) -> dict[str, object]:
    if (
        not isinstance(coefficients, list)
        or len(coefficients) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in coefficients)
    ):
        raise ValueError("candidate relation is not an integer degree-one relation")
    leading, constant = coefficients
    if leading == 0:
        raise ValueError("candidate relation is not degree one")
    root = Fraction(-constant, leading)
    root_text = _fraction_text(root)
    proposal = {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": {
            "minimal_polynomial_high_to_low": list(coefficients),
            "selected_real_root_index": 0,
            "isolating_interval": {
                "left": root_text,
                "right": root_text,
                "multiplicity": 1,
                "real_root_index": 0,
            },
        },
        "census_projection_only": True,
        "complete_ordinary_proposal_available": False,
        "case_family_truth_target_count_routing": False,
    }
    # Reuse the frozen primitive/leading-positive/ordinal-zero validator.
    rational_candidate_from_descriptor(proposal["descriptor"])
    return proposal


def _endpoint(value: object) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("endpoint must be a nonempty list")
    endpoint = [float(item) for item in value]
    if any(not float("-inf") < item < float("inf") for item in endpoint):
        raise ValueError("endpoint must be finite")
    return endpoint


def _anonymous_signature(job: Mapping[str, object], proof: Mapping[str, object]) -> str:
    system = job.get("system")
    structure = proof.get("anonymous_structure_signature")
    if not isinstance(system, Mapping) or not isinstance(structure, Mapping):
        raise ValueError("anonymous structure is absent")
    signature = {
        "typed_variable_count": len(system.get("variables", [])),
        "typed_equation_count": len(system.get("equations", [])),
        "typed_predicate_count": len(system.get("predicates", [])),
        "subset_structure": dict(structure),
    }
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def _run_worker(
    job: Mapping[str, object],
    root: Path,
    ordinal: int,
    *,
    expected_cpu: int,
    timeout_seconds: float,
) -> tuple[int, dict[str, object]]:
    job_path = root / f"job-{ordinal:04d}.json"
    result_path = root / f"certificate-{ordinal:04d}.json"
    job_path.write_text(
        json.dumps(job, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
    )
    completed = subprocess.run(
        [
            "taskset",
            "-c",
            str(expected_cpu),
            str(JULIA),
            f"--project={PROJECT}",
            str(WORKER),
            str(job_path),
            str(result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=environment,
    )
    certificate: dict[str, object] = {}
    if result_path.is_file():
        value = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            certificate = value
    return completed.returncode, certificate


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("joint census must be pinned to exactly the expected CPU")
    if arguments.proof_timeout_seconds <= 0 or arguments.worker_timeout_seconds <= 0:
        raise SystemExit("timeouts must be positive")

    payload = arguments.requests.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("requests SHA-256 mismatch")
    requests = json.loads(payload)
    if not isinstance(requests, list):
        raise SystemExit("requests must be an array")

    counts: dict[str, int] = {
        "descriptor_accepted": 0,
        "descriptor_rejected": 0,
        "typed_job_ready": 0,
        "typed_job_rejected": 0,
        "subset_identity_ready": 0,
        "subset_identity_not_proved": 0,
        "prejoin_ready": 0,
        "worker_attempted": 0,
        "worker_process_failed": 0,
        "worker_certificate_not_verified": 0,
        "experimental_join_ready": 0,
        "experimental_join_hold": 0,
        "unexpected_authority_event": 0,
        "unexpected_target_release_event": 0,
    }
    signatures: dict[str, int] = {}

    with tempfile.TemporaryDirectory(prefix="guided-target-degree1-census-") as name:
        temporary_root = Path(name)
        for ordinal, request in enumerate(requests):
            if not isinstance(request, Mapping) or FORBIDDEN_KEYS & set(request):
                raise SystemExit("request crossed the identity/truth boundary")
            if set(request) != REQUEST_KEYS:
                raise SystemExit("request has unexpected keys")
            try:
                proposal = _projection_proposal(
                    request["candidate_relation_high_to_low"]
                )
                _increment(counts, "descriptor_accepted")
            except Exception:
                _increment(counts, "descriptor_rejected")
                continue

            source_path = Path(str(request["source_path"]))
            job = None
            proof = None
            try:
                job = prepare_typed_regular_job(source_path, _endpoint(request["endpoint"]))
                _increment(counts, "typed_job_ready")
            except Exception:
                _increment(counts, "typed_job_rejected")
            try:
                proof = prove_subset_identity(
                    source_path,
                    ordinary_proposal=proposal,
                    timeout_seconds=arguments.proof_timeout_seconds,
                )
                if proof.get("status") == "SUBSET_IDENTITY_PROVED_HOLD":
                    _increment(counts, "subset_identity_ready")
                else:
                    proof = None
                    _increment(counts, "subset_identity_not_proved")
            except Exception:
                proof = None
                _increment(counts, "subset_identity_not_proved")

            if job is None or proof is None:
                continue
            _increment(counts, "prejoin_ready")
            signature = _anonymous_signature(job, proof)
            signatures[signature] = signatures.get(signature, 0) + 1
            if not arguments.run_workers:
                continue

            _increment(counts, "worker_attempted")
            try:
                returncode, certificate = _run_worker(
                    job,
                    temporary_root,
                    ordinal,
                    expected_cpu=arguments.expected_cpu,
                    timeout_seconds=arguments.worker_timeout_seconds,
                )
            except Exception:
                _increment(counts, "worker_process_failed")
                continue
            if returncode != 0:
                _increment(counts, "worker_process_failed")
                continue
            if certificate.get("status") != "VERIFIED":
                _increment(counts, "worker_certificate_not_verified")
                continue
            join = verify_three_way_join(
                source_path=source_path,
                job=job,
                certificate=certificate,
                subset_proof=proof,
                ordinary_proposal=proposal,
            )
            if join.get("authority_pass") is not False:
                _increment(counts, "unexpected_authority_event")
            if join.get("target_release") is not False:
                _increment(counts, "unexpected_target_release_event")
            if join.get("status") == "THREE_WAY_JOIN_READY_EXPERIMENTAL":
                _increment(counts, "experimental_join_ready")
            else:
                _increment(counts, "experimental_join_hold")

    gate_pass = (
        counts["experimental_join_ready"] >= 10
        and len(signatures) >= 2
        if arguments.run_workers
        else counts["prejoin_ready"] >= 10 and len(signatures) >= 2
    )
    gate_pass = bool(
        gate_pass
        and counts["unexpected_authority_event"] == 0
        and counts["unexpected_target_release_event"] == 0
    )
    aggregate = {
        "schema_version": "geotarget.guided-target-degree1-joint-census/v1",
        "requests_sha256": observed_sha256,
        "request_count": len(requests),
        **counts,
        "anonymous_prejoin_signature_count": len(signatures),
        "anonymous_prejoin_signature_histogram": signatures,
        "workers_enabled": arguments.run_workers,
        "gate_minimum_ready": 10,
        "gate_minimum_signatures": 2,
        "viability_gate_pass": gate_pass,
        "ordinary_full_proposal_binding": False,
        "projection_only": True,
        "authority_pass": False,
        "target_release": False,
        "common_worker_integration": "HOLD",
        "truth_used": False,
        "formal_scorer_used": False,
        "individual_records_emitted": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
