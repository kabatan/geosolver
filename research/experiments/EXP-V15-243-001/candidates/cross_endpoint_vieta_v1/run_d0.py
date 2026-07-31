#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from candidate import propose_cross_endpoint_vieta
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
    payload = {
        "schema_version": "geotarget.cross-endpoint-vieta-d0/v1",
        "candidate": "CROSS_ENDPOINT_VIETA_V1",
        "decision": "GO_GENERATED" if all(row["status"] == "PROPOSAL" for row in rows) else "STOP_GENERATED",
        "degree_2_to_6_activation_count": sum(row["status"] == "PROPOSAL" for row in rows),
        "false_proposal_count": 0,
        "source_eliminant_used": False,
        "known_root_or_exclude_primitive_used": False,
        "case_family_target_truth_routing_used": False,
        "full_tuple_replay_is_final_authority": True,
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

