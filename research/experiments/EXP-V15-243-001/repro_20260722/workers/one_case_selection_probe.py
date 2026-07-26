#!/usr/bin/env python3
"""Outcome-blind replay-window probe using one saved real-case search result."""

from __future__ import annotations

import json
from pathlib import Path
import time

import baseline_fixed_selection as baseline_fixed
import champion_v1_fixed_selection as champion_fixed


HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
RUN = EXP / "results/current-baseline-development145-180s-seed0-20260722-v2"
CASE = RUN / "inputs/005-OMCB055_G.json"
SEARCH = RUN / "artifacts/005-OMCB055_G/search.json"


def probe(name, fresh, reserve, document, endpoints):
    started = time.monotonic()
    candidates = fresh(
        document,
        endpoints,
        hard_deadline=started + reserve,
    )
    return {
        "arm": name,
        "reserve_seconds": reserve,
        "endpoint_count": len(endpoints),
        "candidate_count": len(candidates),
        "deadline_backlog_count": len(getattr(candidates, "deadline_backlog", ())),
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> None:
    document = json.loads(CASE.read_text(encoding="utf-8"))
    search = json.loads(SEARCH.read_text(encoding="utf-8"))
    endpoints = search.get("endpoints", [])
    rows = [
        probe("baseline_original_window", baseline_fixed.BASE._fresh_replay_candidates, 1.0, document, endpoints),
        probe("baseline_fixed_window", baseline_fixed.BASE._fresh_replay_candidates, 5.0, document, endpoints),
        probe("champion_v1_original_window", champion_fixed.V0._fresh_replay_candidates, 3.0, document, endpoints),
        probe("champion_v1_fixed_window", champion_fixed.V0._fresh_replay_candidates, 5.0, document, endpoints),
    ]
    print(json.dumps({"case_source_sha256": baseline_fixed.BASE._sha256(CASE.read_bytes()), "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
