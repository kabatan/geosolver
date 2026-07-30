#!/usr/bin/env python3
"""Three-family generated D0; no corpus, scorer, target, or truth."""

from __future__ import annotations

import json
import os

import candidate
from test_candidate import three_families


def main() -> int:
    pools = three_families()
    gate = candidate.dynamic_gate(pools)
    proposals = [candidate.select_portal(pool, gate) for pool in pools]
    allocations = [
        candidate.callback_allocation(400, portal_available=proposal is not None)
        for proposal in proposals
    ]
    allocation = {
        key: sum(item[key] for item in allocations)
        for key in allocations[0]
    }
    total_callbacks = 400 * len(pools)
    result = {
        "candidate": candidate.CANDIDATE,
        "scope": "generated charged finite observations only",
        "families": 3,
        "dynamic_gate_pass": gate.get("gate_pass") is True,
        "low_residual_invalid_endpoints": gate.get("low_residual_invalid_endpoint_count"),
        "anonymous_hashes": gate.get("anonymous_hash_count_with_low_invalid_endpoint"),
        "existing_interior_portals": sum(
            proposal is not None
            and proposal.point in {
                tuple(item["point"])
                for item in pool["observations"]
                if item["guard_state"] == "INTERIOR"
            }
            for proposal, pool in zip(proposals, pools, strict=True)
        ),
        "midpoint_probes_planned": sum(proposal is not None for proposal in proposals),
        "baseline_callbacks": allocation["baseline_callbacks"],
        "side_callbacks_including_midpoints": allocation["side_callbacks"],
        "midpoint_callbacks": allocation["midpoint_evaluation_callbacks"],
        "threshold_or_persistence_sweep": False,
        "proposal_authority": False,
        "canonical_replay_required": True,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "corpus_scorer_truth_98_validation_or_sealed_used": False,
    }
    result["d0_pass"] = bool(
        result["dynamic_gate_pass"]
        and result["existing_interior_portals"] == 3
        and result["midpoint_callbacks"] == 3
        and 4 * result["baseline_callbacks"] >= 3 * total_callbacks
        and 4 * result["side_callbacks_including_midpoints"] <= total_callbacks
        and os.sched_getaffinity(0) == {14}
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["d0_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
