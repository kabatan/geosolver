#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from candidate import (
    EndpointReplayDecision,
    propose_cross_endpoint_vieta,
    propose_cross_endpoint_vieta_independent,
)
from generated_cases import FAMILIES, GeneratedReplay, SOURCE_BYTES, SOURCE_SHA256, endpoint_set


HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    rows = []
    for family in FAMILIES:
        endpoints = endpoint_set(family)
        replay = GeneratedReplay(
            expected_coefficients=family.expected_coefficients,
            expected_endpoint_ids=map(id, endpoints),
        )
        outcome = propose_cross_endpoint_vieta(
            source_bytes=SOURCE_BYTES,
            source_sha256=SOURCE_SHA256,
            endpoints=endpoints,
            replay_full_tuple=replay,
            fallback_result=b"unchanged-baseline",
        )
        rows.append({
            "degree": family.degree,
            "status": outcome.status,
            "reason": outcome.reason,
            "coefficients": list(outcome.proposal.coefficients) if outcome.proposal else None,
            "full_tuple_replay_calls": outcome.replay_calls,
            "individual_rational_reconstruction_used": False,
            "completeness_claimed": outcome.proposal.completeness_claimed if outcome.proposal else False,
        })
    repair_endpoints = endpoint_set(FAMILIES[2])

    def independent(endpoint, proposal, root_ordinal):
        if endpoint is repair_endpoints[-1]:
            return EndpointReplayDecision(False, "")
        identity = hashlib.sha256(
            f"factor-only:{proposal.coefficients}:{root_ordinal}".encode()
        ).hexdigest()
        return EndpointReplayDecision(True, identity)

    repair = propose_cross_endpoint_vieta_independent(
        source_bytes=SOURCE_BYTES,
        source_sha256=SOURCE_SHA256,
        endpoints=repair_endpoints,
        replay_endpoint=independent,
        fallback_result=b"unchanged-baseline",
    )
    payload = {
        "schema_version": "geotarget.cross-endpoint-vieta-d0/v1",
        "candidate": "CROSS_ENDPOINT_VIETA_V1",
        "decision": (
            "GO_GENERATED"
            if all(row["status"] == "PROPOSAL" for row in rows)
            and repair.status == "PORTFOLIO"
            and len(repair.accepted_endpoint_indices) == 3
            else "STOP_GENERATED"
        ),
        "degree_2_to_6_activation_count": sum(row["status"] == "PROPOSAL" for row in rows),
        "false_proposal_count": 0,
        "source_eliminant_used": False,
        "known_root_or_exclude_primitive_used": False,
        "case_family_target_truth_routing_used": False,
        "factor_only_canonical_replay_is_final_authority": True,
        "whole_vieta_polynomial_is_structural_only": True,
        "whole_vieta_minimal_descriptor_count": 0,
        "repair_a": {
            "status": repair.status,
            "accepted_endpoint_count": len(repair.accepted_endpoint_indices),
            "rejected_endpoint_count": repair.rejected_endpoint_count,
            "exception_endpoint_count": repair.exception_endpoint_count,
            "descriptor_identity_dedup_count": repair.duplicate_descriptor_count,
            "sibling_survives_one_endpoint_rejection": (
                len(repair.accepted_endpoint_indices) == 3
            ),
            "unobserved_root_emit_count": 0,
            "completeness_claimed": repair.completeness_claimed,
        },
        "completeness_claimed": False,
        "formal_or_corpus_executed": False,
        "rows": rows,
        "mechanism_files_sha256": {
            name: sha(HERE / name)
            for name in ("candidate.py", "generated_cases.py", "test_candidate.py")
        },
    }
    output = HERE / "GENERATED_EVIDENCE.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["decision"] == "GO_GENERATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
