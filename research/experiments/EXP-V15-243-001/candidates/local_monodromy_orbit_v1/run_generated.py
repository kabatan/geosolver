#!/usr/bin/env python3
"""Aggregate-only D0 runner; family labels never enter the candidate."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import time

import numpy as np

from candidate import canonical_source_replay, run_portfolio
from generated_cases import exact_local_witnesses, generated_suite


def _contains(points: tuple[np.ndarray, ...], target: np.ndarray) -> bool:
    return any(np.linalg.norm(point - target) <= 2.0e-8 for point in points)


def main() -> None:
    wins = losses = false = extra = 0
    activation = 0
    path_steps = 0
    family_stats: dict[str, Counter[str]] = defaultdict(Counter)
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for case in generated_suite():
        exact = exact_local_witnesses(case)
        if not exact:
            raise AssertionError(f"generated case has no safe local witness: {case.name}")
        baseline = (np.array(exact[0], copy=True),)
        result = run_portfolio(case.problem, baseline, starts=16)
        candidate = result.proposals
        activation += int(result.ledger.activated)
        path_steps += result.ledger.path_steps
        case_loss = int(any(not _contains(candidate, point) for point in baseline))
        case_extra = sum(not _contains(exact, point) for point in candidate)
        case_false = sum(not canonical_source_replay(case.problem, point) for point in candidate)
        case_win = int(
            case_loss == 0
            and case_extra == 0
            and len(candidate) > len(baseline)
        )
        wins += case_win
        losses += case_loss
        false += case_false
        extra += case_extra
        family_stats[case.family]["cases"] += 1
        family_stats[case.family]["wins"] += case_win
        family_stats[case.family]["losses"] += case_loss
        family_stats[case.family]["false"] += case_false
        family_stats[case.family]["extra"] += case_extra
        records.append(
            {
                "name": case.name,
                "family": case.family,
                "baseline": len(baseline),
                "candidate": len(candidate),
                "exact": len(exact),
                "activated": result.ledger.activated,
                "orbit_sizes": [len(orbit) for orbit in result.ledger.orbits],
                "permutations": [list(p) for p in result.ledger.permutations],
                "rejected_nonreal": result.ledger.rejected_nonreal,
                "rejected_replay": result.ledger.rejected_replay,
            }
        )
        if result.baseline_digest_before != result.baseline_digest_after:
            raise AssertionError("baseline prefix was mutated")
        if result.route_trace.count("baseline") != 12 or result.route_trace.count("local_monodromy") != 4:
            raise AssertionError("75/25 route quota changed")
    output = {
        "schema": "geotarget.exp-v15-243.local-monodromy-orbit.d0/v1",
        "cases": len(records),
        "families": len(family_stats),
        "wins": wins,
        "losses": losses,
        "false": false,
        "extra": extra,
        "activation": activation,
        "positive_families": sum(stats["wins"] > 0 for stats in family_stats.values()),
        "path_steps": path_steps,
        "wall_seconds": time.perf_counter() - started,
        "quota": {"baseline": 0.75, "side": 0.25},
        "family_aggregate": {key: dict(value) for key, value in sorted(family_stats.items())},
        "records": records,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
