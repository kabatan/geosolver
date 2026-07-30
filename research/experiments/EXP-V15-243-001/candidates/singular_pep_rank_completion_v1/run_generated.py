#!/usr/bin/env python3
"""Short single-process D0 aggregate; generated truth never reaches candidate."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import time

from candidate import canonical_source_replay, ordinary_regular_proposals, run_portfolio
from generated_cases import generated_suite


def _matches(value: float, expected: tuple[float, ...]) -> bool:
    return any(abs(value - target) <= 8.0e-6 * max(1.0, abs(target)) for target in expected)


def main() -> None:
    family: dict[str, Counter[str]] = defaultdict(Counter)
    wins = losses = false = extra = missing = activation = 0
    finite = rejected_fake = 0
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for case in generated_suite():
        # The ordinary regular-PEP baseline refuses structurally singular
        # determinants but remains active and immutable on regular inputs.
        baseline = ordinary_regular_proposals(case.problem)
        result = run_portfolio(case.problem, baseline, starts=16)
        proposals = result.proposals
        case_extra = sum(not _matches(value, case.expected_real) for value in proposals)
        case_missing = sum(not _matches(target, proposals) for target in case.expected_real)
        case_false = sum(
            not canonical_source_replay(case.problem, value, result.side.normal_rank)
            for value in result.side.proposals
        )
        case_loss = int(any(not _matches(value, proposals) for value in baseline))
        case_win = int(case.role == "positive" and case_extra == 0 and len(proposals) > len(baseline))
        wins += case_win
        losses += case_loss
        false += case_false
        extra += case_extra
        missing += case_missing
        activation += int(result.side.activated)
        finite += result.side.finite_completed_eigenvalues
        rejected_fake += result.side.rejected_fake
        stats = family[case.family]
        stats["cases"] += 1
        stats["wins"] += case_win
        stats["losses"] += case_loss
        stats["false"] += case_false
        stats["extra"] += case_extra
        stats["missing"] += case_missing
        records.append(
            {
                "name": case.name,
                "family": case.family,
                "role": case.role,
                "activated": result.side.activated,
                "reason": result.side.reason,
                "normal_rank": result.side.normal_rank,
                "corank": result.side.corank,
                "expected_count": len(case.expected_real),
                "proposal_count": len(proposals),
                "missing": case_missing,
                "extra": case_extra,
                "rejected_fake": result.side.rejected_fake,
            }
        )
        if result.baseline_digest_before != result.baseline_digest_after:
            raise AssertionError("baseline mutated")
        if result.route_trace.count("baseline") != 12:
            raise AssertionError("baseline quota changed")
    output = {
        "schema": "geotarget.exp-v15-243.singular-pep-rank-completion.d0/v1",
        "cases": len(records),
        "families": len(family),
        "positive_families": sum(stats["wins"] > 0 for stats in family.values()),
        "wins": wins,
        "losses": losses,
        "false": false,
        "extra": extra,
        "missing": missing,
        "activation": activation,
        "finite_completed_eigenvalues": finite,
        "rejected_fake": rejected_fake,
        "wall_seconds": time.perf_counter() - started,
        "quota": {"baseline": 0.75, "side": 0.25},
        "family_aggregate": {key: dict(value) for key, value in sorted(family.items())},
        "records": records,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
