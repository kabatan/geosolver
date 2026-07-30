#!/usr/bin/env python3
"""Generated activation smoke against the actual frozen source-replay seam."""

from __future__ import annotations

import json
import time

import worker


FORMULATION = {
    "task": "solve",
    "variables": {"names": ["x", "y", "z", "w"]},
    "construction": [],
    "constraints": [
        {"def": "x**2", "value": 1},
        {"def": "y", "value": "x"},
        {"def": "sin(z)", "value": 0},
        {"def": "w", "value": "z"},
    ],
    "guards": [],
}


def main() -> None:
    frozen, replay_audit = worker.install_full_v15(FORMULATION)
    base = frozen.CHAMPION.BASE
    candidates = base._fresh_replay_candidates(
        FORMULATION,
        ({"point": [0.8, 1.0, 0.0, 0.0]},),
        hard_deadline=time.monotonic() + 3.0,
    )
    factory = dict(worker.LAST_FACTORY_AUDIT)
    result = {
        "schema_version": "geotarget.exp-struct-poly-001-full-v15-smoke/v1",
        "generated_only": True,
        "frozen_source_replay_called": True,
        "factory_status": factory.get("status"),
        "active_polynomial_blocks": factory.get("active_polynomial_blocks"),
        "proposal_count": factory.get("proposal_count"),
        "locally_verified_count": factory.get("locally_verified_count"),
        "within_two_second_cap": factory.get("within_two_second_cap"),
        "source_replay_candidate_count": len(candidates),
        "source_replay_candidate_endpoints": [
            list(candidate.endpoint) for candidate in candidates
        ],
        "replay_seam": replay_audit(),
        "canonical_verifier_bypassed": False,
        "hp_and_exact_descriptor_authority_invoked": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
