#!/usr/bin/env python3
"""Generated truth-free trace showing strict baseline-before-side ordering."""

from __future__ import annotations

import json
from types import SimpleNamespace
import time

from leftover_overlay import install_leftover_only
import worker_v2


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


def complete_statistics(label):
    return {
        "trace_label": label,
        "all_discovered_primaries_served": True,
        "primary_wave_complete": True,
        "alternate_wave_complete": True,
        "restoration_wave_complete": True,
        "primary_deferred_unknown_count": 0,
        "deadline_backlog_unexamined_count": 0,
    }


def main() -> None:
    events = []
    baseline_candidates = ({"point": [0.8, 1.0, 0.0, 0.0]},)

    def fresh(_document, endpoints, *, hard_deadline):
        events.append("baseline_fresh" if endpoints is baseline_candidates else "side_fresh")
        return tuple(endpoints)

    def service(**kwargs):
        candidates = kwargs["candidates"]
        if candidates is baseline_candidates:
            events.append("baseline_service_complete")
            return ["baseline-attempt"], {"baseline": {"descriptor": 1}}, complete_statistics("baseline")
        events.append("side_service")
        return ["side-attempt"], {"side": {"descriptor": 2}}, complete_statistics("side")

    base = SimpleNamespace(
        _fresh_replay_candidates=fresh,
        _service_candidates=service,
        _plan=lambda **kwargs: {"base": True, **kwargs},
        _run_hp_candidate=lambda: None,
        _run_restoration_candidate=lambda: None,
        _authority_descriptor=lambda: None,
        _descriptor_key=lambda: None,
        FINALIZE_RESERVE_SECONDS=3.0,
        MIN_HP_ATTEMPT_SECONDS=0.25,
    )
    champion = SimpleNamespace(BASE=base)

    def proposal_factory(document, starts, budget):
        events.append("side_proposal_generation")
        return worker_v2._proposal_factory(document, starts, budget)

    audit = install_leftover_only(
        champion,
        proposal_factory=proposal_factory,
        mechanism_hash="generated-smoke",
    )
    candidates = base._fresh_replay_candidates(
        FORMULATION,
        baseline_candidates,
        hard_deadline=time.monotonic() + 3.0,
    )
    attempts, descriptors, statistics = base._service_candidates(
        source="generated",
        source_sha256="generated",
        candidates=candidates,
        cpu=0,
        output="generated",
        hard_deadline=time.monotonic() + 10.0,
    )
    result = {
        "schema_version": "geotarget.exp-struct-poly-001-v2-trace-smoke/v1",
        "generated_only": True,
        "events": events,
        "baseline_trace_prefix_preserved": attempts[0] == "baseline-attempt",
        "attempts": attempts,
        "descriptor_keys": sorted(descriptors),
        "baseline_statistics_preserved": statistics["trace_label"] == "baseline",
        "side_lane_statistics_present": "leftover_only_side_lane" in statistics,
        "audit": audit(),
        "factory": {
            key: value
            for key, value in worker_v2.LAST_FACTORY_AUDIT.items()
            if key != "elapsed_seconds"
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
