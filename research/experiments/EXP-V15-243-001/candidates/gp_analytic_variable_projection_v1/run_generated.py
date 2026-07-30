#!/usr/bin/env python3

from __future__ import annotations

from collections import Counter, defaultdict
import json
import time

from candidate import canonical_source_replay, run_portfolio
from generated_cases import generated_suite


def main() -> None:
    family: dict[str, Counter[str]] = defaultdict(Counter)
    wins = losses = false = extra = activation = 0
    recall_wins = recall_losses = inner_solve_wins = 0
    baseline_inner_solves = side_inner_solves = 0
    started = time.perf_counter()
    records: list[dict[str, object]] = []
    for case in generated_suite():
        result = run_portfolio(case.problem, case.start)
        baseline_safe = result.baseline.solved and canonical_source_replay(case.problem, result.baseline.point)
        side_safe = result.side.solved and canonical_source_replay(case.problem, result.side.point)
        case_recall_win = int(case.role == "positive" and side_safe and not baseline_safe)
        case_recall_loss = int(baseline_safe and not side_safe and result.side.activated)
        case_inner_win = int(
            case.role == "positive"
            and side_safe == baseline_safe
            and side_safe
            and result.side.inner_solves <= 0.8 * result.baseline.inner_solves
        )
        case_win = int(case_recall_win or case_inner_win)
        case_loss = case_recall_loss
        case_false = int(result.side.solved and not side_safe)
        case_extra = int(case.role in ("negative", "near_miss") and side_safe)
        wins += case_win
        losses += case_loss
        false += case_false
        extra += case_extra
        activation += int(result.side.activated)
        recall_wins += case_recall_win
        recall_losses += case_recall_loss
        inner_solve_wins += case_inner_win
        baseline_inner_solves += result.baseline.inner_solves
        side_inner_solves += result.side.inner_solves
        stats = family[case.family]
        stats["cases"] += 1
        stats["wins"] += case_win
        stats["losses"] += case_loss
        stats["false"] += case_false
        stats["extra"] += case_extra
        records.append(
            {
                "name": case.name,
                "family": case.family,
                "role": case.role,
                "baseline_solved": baseline_safe,
                "side_activated": result.side.activated,
                "side_solved": side_safe,
                "side_reason": result.side.reason,
                "baseline_iterations": result.baseline.iterations,
                "side_iterations": result.side.iterations,
                "side_inner_solves": result.side.inner_solves,
                "baseline_inner_solves": result.baseline.inner_solves,
                "analytic_reduced_jacobians": result.side.analytic_reduced_jacobians,
            }
        )
        if result.baseline_digest_before != result.baseline_digest_after:
            raise AssertionError("baseline start mutated")
    output = {
        "schema": "geotarget.exp-v15-243.gp-analytic-varpro.d0/v1",
        "cases": len(records),
        "families": len(family),
        "positive_families": sum(stats["wins"] > 0 for stats in family.values()),
        "wins": wins,
        "losses": losses,
        "false": false,
        "extra": extra,
        "activation": activation,
        "recall_wins": recall_wins,
        "recall_losses": recall_losses,
        "inner_solve_wins": inner_solve_wins,
        "baseline_inner_solves": baseline_inner_solves,
        "side_inner_solves": side_inner_solves,
        "inner_solve_ratio": side_inner_solves / baseline_inner_solves,
        "wall_seconds": time.perf_counter() - started,
        "quota": {"baseline": 0.75, "side": 0.25},
        "family_aggregate": {key: dict(value) for key, value in sorted(family.items())},
        "records": records,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
