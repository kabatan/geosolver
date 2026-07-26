#!/usr/bin/env python3
"""Cold-process saved-endpoint probe for one preloaded reproduction arm."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import time


HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
RUN = EXP / "results/current-baseline-development145-180s-seed0-20260722-v2"
CASE = RUN / "inputs/005-OMCB055_G.json"
SEARCH = RUN / "artifacts/005-OMCB055_G/search.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("baseline", "champion_v1"), required=True)
    arguments = parser.parse_args()
    wrapper = importlib.import_module(f"{arguments.arm}_preloaded")
    if arguments.arm == "baseline":
        fresh = wrapper.BASE._fresh_replay_candidates
        reserve = 1.0
    else:
        fresh = wrapper.V0._fresh_replay_candidates
        reserve = 3.0
    document = json.loads(CASE.read_text(encoding="utf-8"))
    endpoints = json.loads(SEARCH.read_text(encoding="utf-8")).get("endpoints", [])
    started = time.monotonic()
    candidates = fresh(document, endpoints, hard_deadline=started + reserve)
    print(
        json.dumps(
            {
                "arm": arguments.arm,
                "reserve_seconds": reserve,
                "endpoint_count": len(endpoints),
                "candidate_count": len(candidates),
                "deadline_backlog_count": len(getattr(candidates, "deadline_backlog", ())),
                "selection_elapsed_seconds": time.monotonic() - started,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
