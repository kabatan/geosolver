from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from candidate import solve_portfolio
from generated_cases import make_case, transformed_case


FAMILIES = ("sparse_chain", "dense_coupled", "strict_bound_scale")
ROLES = ("positive", "negative", "near_miss")
SEEDS = range(12)
CAP = 22


def _solved(results) -> bool:
    return any(item.solved for item in results)


def main() -> None:
    t0 = time.process_time()
    rows = []
    metamorphic_failures = 0
    for family in FAMILIES:
        for role in ROLES:
            for seed in SEEDS:
                case = make_case(family, role, seed)
                control = solve_portfolio(case.problem, case.starts, CAP, seed, False)
                candidate = solve_portfolio(case.problem, case.starts, CAP, seed, True)
                control_solved = _solved(control)
                candidate_solved = _solved(candidate)
                callbacks_equal = sum(x.callbacks for x in control) == sum(
                    x.callbacks for x in candidate
                )
                insurance_equal = all(
                    np.array_equal(control[i].point, candidate[i].point)
                    and control[i].solved == candidate[i].solved
                    for i in range(3)
                )
                rows.append(
                    {
                        "family": family,
                        "role": role,
                        "seed": seed,
                        "control_solved": control_solved,
                        "candidate_solved": candidate_solved,
                        "gain": candidate_solved and not control_solved,
                        "loss": control_solved and not candidate_solved,
                        "false": role != "positive" and candidate_solved,
                        "callbacks_equal": callbacks_equal,
                        "insurance_equal": insurance_equal,
                        "activated": candidate[3].activated,
                        "accepted_rows": candidate[3].accepted_rows,
                    }
                )

                if role == "positive" and seed < 4:
                    m = case.problem.observe(case.starts[0]).residual.size
                    cp = np.eye(case.starts[0].size)[::-1]
                    rp = np.eye(m)[np.roll(np.arange(m), 1)]
                    rs = np.where(np.arange(m) % 2, -7.0, 0.25)
                    transformed = transformed_case(case, cp, rp, rs)
                    transformed_result = solve_portfolio(
                        transformed.problem, transformed.starts, CAP, seed, True
                    )
                    if _solved(candidate) != _solved(transformed_result):
                        metamorphic_failures += 1

    aggregate = {
        "schema": "greedy-dual-bregman-kaczmarz-generated-d0/v1",
        "cases": len(rows),
        "positive_cases": sum(r["role"] == "positive" for r in rows),
        "gains": sum(r["gain"] for r in rows),
        "losses": sum(r["loss"] for r in rows),
        "false": sum(r["false"] for r in rows),
        "activation": sum(r["activated"] for r in rows),
        "accepted_rows": sum(r["accepted_rows"] for r in rows),
        "callback_mismatches": sum(not r["callbacks_equal"] for r in rows),
        "insurance_mismatches": sum(not r["insurance_equal"] for r in rows),
        "metamorphic_checks": len(FAMILIES) * 4,
        "metamorphic_failures": metamorphic_failures,
        "by_family": {
            family: {
                "positive_gain": sum(
                    r["gain"] and r["family"] == family and r["role"] == "positive"
                    for r in rows
                ),
                "positive_candidate_solved": sum(
                    r["candidate_solved"]
                    and r["family"] == family
                    and r["role"] == "positive"
                    for r in rows
                ),
                "negative_or_near_false": sum(
                    r["false"] and r["family"] == family for r in rows
                ),
            }
            for family in FAMILIES
        },
        "callback_cap_per_lane": CAP,
        "baseline_lane_fraction": 0.75,
        "candidate_lane_fraction": 0.25,
        "cpu_seconds": time.process_time() - t0,
    }
    path = Path(__file__).with_name("AGGREGATE.json")
    path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
