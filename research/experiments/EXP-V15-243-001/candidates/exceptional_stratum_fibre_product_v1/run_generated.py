#!/usr/bin/env python3
"""Aggregate-only D0 runner; labels and truth never enter candidate calls."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import time

import numpy as np

from candidate import canonical_source_replay, run_portfolio
from generated_cases import assert_truth_safe, generated_suite, truth_contains


def _contains(problem, points, target, tolerance: float = 3.0e-6) -> bool:
    return any(
        np.linalg.norm((np.asarray(point) - target) / problem.point_scale) <= tolerance
        for point in points
    )


def main() -> None:
    wins = losses = false = extra = activation = 0
    role_family_stats: dict[str, set[str]] = defaultdict(set)
    family_stats: dict[str, Counter[str]] = defaultdict(Counter)
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for case in generated_suite():
        assert_truth_safe(case)
        result = run_portfolio(case.problem, case.baseline, case.unstable_cluster, starts=16)
        candidate = result.proposals
        case_loss = int(any(not _contains(case.problem, candidate, point) for point in case.baseline))
        case_false = sum(not canonical_source_replay(case.problem, point) for point in candidate)
        case_extra = sum(not truth_contains(case, point) for point in candidate)
        case_win = int(
            case_loss == 0
            and case_false == 0
            and case_extra == 0
            and len(candidate) > len(case.baseline)
        )
        wins += case_win
        losses += case_loss
        false += case_false
        extra += case_extra
        activation += int(result.evidence.activated)
        role_family_stats[case.role].add(case.family)
        stats = family_stats[case.family]
        stats["cases"] += 1
        stats["wins"] += case_win
        stats["losses"] += case_loss
        stats["false"] += case_false
        stats["extra"] += case_extra
        stats["activation"] += int(result.evidence.activated)
        if result.baseline_digest_before != result.baseline_digest_after:
            raise AssertionError("baseline was mutated")
        if result.route_trace.count("baseline") != 12:
            raise AssertionError("75 percent baseline quota changed")
        if result.route_trace.count("exceptional_stratum") != 4:
            raise AssertionError("25 percent side quota changed")
        records.append(
            {
                "name": case.name,
                "family": case.family,
                "role": case.role,
                "baseline": len(case.baseline),
                "candidate": len(candidate),
                "exact": len(case.exact),
                "win": case_win,
                "loss": case_loss,
                "false": case_false,
                "extra": case_extra,
                "activated": result.evidence.activated,
                "reason": result.evidence.reason,
                "signatures": list(result.evidence.signatures),
                "exceptional_offset": result.evidence.exceptional_offset,
                "samples": result.evidence.samples,
                "fibre_endpoints": result.evidence.fibre_endpoints,
                "projected": result.evidence.projected,
                "rejected_projection": result.evidence.rejected_projection,
                "rejected_replay": result.evidence.rejected_replay,
            }
        )
    output = {
        "schema": "geotarget.exp-v15-243.exceptional-stratum-fibre-product.d0/v1",
        "cases": len(records),
        "families": len(family_stats),
        "role_family_counts": {role: len(families) for role, families in sorted(role_family_stats.items())},
        "wins": wins,
        "losses": losses,
        "false": false,
        "extra": extra,
        "activation": activation,
        "positive_families_with_wins": sum(
            family_stats[family]["wins"] > 0 for family in role_family_stats["positive"]
        ),
        "quota": {"baseline": 0.75, "side": 0.25},
        "wall_seconds": time.perf_counter() - started,
        "family_aggregate": {family: dict(stats) for family, stats in sorted(family_stats.items())},
        "records": records,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
