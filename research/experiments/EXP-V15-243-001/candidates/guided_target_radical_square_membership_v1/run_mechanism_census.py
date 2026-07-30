#!/usr/bin/env python3
"""Aggregate-only direct-vs-radical-square membership mechanism census."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Mapping

from radical_square_membership import BASE, prove_radical_square_identity


HERE = Path(__file__).resolve().parent
DIRECT_DIR = HERE.parent / "guided_target_ideal_membership_v1"
if str(DIRECT_DIR) not in sys.path:
    sys.path.insert(0, str(DIRECT_DIR))
from typed_join import prepare_typed_regular_job  # noqa: E402


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
DIRECT_FAILURE_CLASSES = (
    "EXACT_REMAINDER_NONZERO",
    "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM",
    "INCONSISTENT_UNIT_IDEAL",
    "DEGREE_ONE_PROPOSAL_REJECTED",
    "SOURCE_EQUALITIES_OUTSIDE_SAFE_SUBSET",
    "TARGET_OUTSIDE_SAFE_POLYNOMIAL_SUBSET",
    "PROOF_DEADLINE",
    "OTHER_FAIL_CLOSED",
)
SQUARE_FAILURE_CLASSES = (
    "POWERED_REMAINDER_NONZERO",
    "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM",
    "INCONSISTENT_UNIT_IDEAL",
    "COFACTOR_WITNESS_UNAVAILABLE",
    "PROOF_DEADLINE",
    "TARGET_OUTSIDE_SAFE_POLYNOMIAL_SUBSET",
    "SOURCE_EQUALITIES_OUTSIDE_SAFE_SUBSET",
    "DEGREE_ONE_PROPOSAL_REJECTED",
    "POWERED_POLYNOMIAL_CAP",
    "OTHER_FAIL_CLOSED",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--proof-timeout-seconds", type=float, default=3.0)
    return parser


def _fraction_text(value: Fraction) -> str:
    return (
        str(value.numerator)
        if value.denominator == 1
        else f"{value.numerator}/{value.denominator}"
    )


def _proposal(coefficients: object) -> dict[str, object]:
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
    }
    BASE.rational_candidate_from_descriptor(proposal["descriptor"])
    return proposal


def _endpoint(value: object) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("endpoint must be a nonempty list")
    endpoint = [float(item) for item in value]
    if any(not float("-inf") < item < float("inf") for item in endpoint):
        raise ValueError("endpoint must be finite")
    return endpoint


def _direct_failure_class(reason: object) -> str:
    text = str(reason)
    if "remainder is nonzero" in text:
        return "EXACT_REMAINDER_NONZERO"
    if "post-process" in text:
        return "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM"
    if "unit" in text or "inconsistent" in text:
        return "INCONSISTENT_UNIT_IDEAL"
    if "descriptor" in text or "proposal" in text or "isolator" in text:
        return "DEGREE_ONE_PROPOSAL_REJECTED"
    if "equality count" in text or "constraint" in text:
        return "SOURCE_EQUALITIES_OUTSIDE_SAFE_SUBSET"
    if "target" in text:
        return "TARGET_OUTSIDE_SAFE_POLYNOMIAL_SUBSET"
    if "deadline" in text:
        return "PROOF_DEADLINE"
    return "OTHER_FAIL_CLOSED"


def _signature(job: Mapping[str, object], proof: Mapping[str, object]) -> str:
    system = job.get("system")
    proof_signature = proof.get("anonymous_structure_signature")
    if not isinstance(system, Mapping) or not isinstance(proof_signature, Mapping):
        raise ValueError("structural signature unavailable")
    value = {
        "typed_variables": len(system.get("variables", [])),
        "typed_equations": len(system.get("equations", [])),
        "typed_predicates": len(system.get("predicates", [])),
        "membership": dict(proof_signature),
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("mechanism census must be pinned to exactly the expected CPU")
    if arguments.proof_timeout_seconds <= 0:
        raise SystemExit("proof timeout must be positive")
    payload = arguments.requests.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("requests SHA-256 mismatch")
    requests = json.loads(payload)
    if not isinstance(requests, list):
        raise SystemExit("requests must be an array")

    counts = {
        "descriptor_accepted": 0,
        "descriptor_rejected": 0,
        "typed_job_ready": 0,
        "typed_job_rejected": 0,
        "direct_identity_ready": 0,
        "direct_identity_not_proved": 0,
        "radical_square_attempted_on_direct_miss": 0,
        "radical_square_incremental_ready": 0,
        "direct_typed_prejoin_ready": 0,
        "radical_square_typed_prejoin_ready": 0,
        "union_typed_prejoin_ready": 0,
        "unexpected_authority_event": 0,
        "unexpected_target_release_event": 0,
    }
    direct_failures = {key: 0 for key in DIRECT_FAILURE_CLASSES}
    square_failures = {key: 0 for key in SQUARE_FAILURE_CLASSES}
    direct_signatures: set[str] = set()
    square_signatures: set[str] = set()

    for request in requests:
        if not isinstance(request, Mapping) or FORBIDDEN_KEYS & set(request):
            raise SystemExit("request crossed the identity/truth boundary")
        if set(request) != REQUEST_KEYS:
            raise SystemExit("request has unexpected keys")
        try:
            proposal = _proposal(request["candidate_relation_high_to_low"])
            counts["descriptor_accepted"] += 1
        except Exception:
            counts["descriptor_rejected"] += 1
            continue
        source_path = Path(str(request["source_path"]))
        job = None
        try:
            job = prepare_typed_regular_job(source_path, _endpoint(request["endpoint"]))
            counts["typed_job_ready"] += 1
        except Exception:
            counts["typed_job_rejected"] += 1

        direct = BASE.prove_subset_identity(
            source_path,
            ordinary_proposal=proposal,
            timeout_seconds=arguments.proof_timeout_seconds,
        )
        if direct.get("authority_pass") is not False:
            counts["unexpected_authority_event"] += 1
        if direct.get("target_release") is not False:
            counts["unexpected_target_release_event"] += 1
        if direct.get("status") == "SUBSET_IDENTITY_PROVED_HOLD":
            counts["direct_identity_ready"] += 1
            if job is not None:
                counts["direct_typed_prejoin_ready"] += 1
                counts["union_typed_prejoin_ready"] += 1
                direct_signatures.add(_signature(job, direct))
            continue

        counts["direct_identity_not_proved"] += 1
        direct_failures[_direct_failure_class(direct.get("reason"))] += 1
        counts["radical_square_attempted_on_direct_miss"] += 1
        repaired = prove_radical_square_identity(
            source_path,
            ordinary_proposal=proposal,
            timeout_seconds=arguments.proof_timeout_seconds,
        )
        if repaired.get("authority_pass") is not False:
            counts["unexpected_authority_event"] += 1
        if repaired.get("target_release") is not False:
            counts["unexpected_target_release_event"] += 1
        if repaired.get("status") == "RADICAL_SQUARE_IDENTITY_PROVED_HOLD":
            counts["radical_square_incremental_ready"] += 1
            if job is not None:
                counts["radical_square_typed_prejoin_ready"] += 1
                counts["union_typed_prejoin_ready"] += 1
                square_signatures.add(_signature(job, repaired))
        else:
            failure_class = str(repaired.get("failure_class"))
            if failure_class not in square_failures:
                failure_class = "OTHER_FAIL_CLOSED"
            square_failures[failure_class] += 1

    aggregate = {
        "schema_version": "geotarget.guided-target-membership-mechanism-census/v1",
        "requests_sha256": observed_sha256,
        "request_count": len(requests),
        **counts,
        "direct_failure_taxonomy": direct_failures,
        "radical_square_failure_taxonomy": square_failures,
        "direct_typed_prejoin_signature_count": len(direct_signatures),
        "radical_square_typed_prejoin_signature_count": len(square_signatures),
        "individual_records_emitted": False,
        "structural_signatures_emitted": False,
        "ordinary_full_proposal_binding": False,
        "projection_only": True,
        "authority_pass": False,
        "target_release": False,
        "common_worker_integration": "HOLD",
        "truth_used": False,
        "formal_scorer_used": False,
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
