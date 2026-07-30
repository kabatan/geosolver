"""Run the frozen generated-only D0 panel."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from candidate import solve_portfolio
from generated_cases import generated_suite


HERE = Path(__file__).resolve().parent


def _found(case, results) -> frozenset[int]:
    return frozenset(
        case.descriptor(result.point)
        for result in results
        if result.solved and case.problem.replay(result.point)
    )


def main() -> None:
    aggregate = Counter()
    family_gains = Counter()
    roles = Counter()
    for case in generated_suite():
        control = solve_portfolio(case.problem, case.starts, 44, candidate=False)
        candidate = solve_portfolio(case.problem, case.starts, 44, candidate=True)
        control_set = _found(case, control)
        candidate_set = _found(case, candidate)
        gains = candidate_set - control_set
        losses = control_set - candidate_set
        false = candidate_set - case.truth
        aggregate["cases"] += 1
        aggregate["positive_cases"] += int(case.role == "positive")
        aggregate["gains"] += len(gains)
        aggregate["losses"] += len(losses)
        aggregate["false_or_extra"] += len(false)
        aggregate["activation"] += int(candidate[3].activated)
        aggregate["conormal_queries"] += candidate[3].conormal_queries
        aggregate["callback_mismatch"] += int(
            any(result.callbacks != 44 for result in control + candidate)
        )
        aggregate["insurance_mismatch"] += int(
            any(
                left.solved != right.solved
                or not np.array_equal(left.point, right.point)
                for left, right in zip(control[:3], candidate[:3])
            )
        )
        family_gains[case.family] += len(gains)
        roles[f"{case.role}_gain"] += len(gains)
        roles[f"{case.role}_loss"] += len(losses)
        roles[f"{case.role}_false"] += len(false)

    result = {
        "schema": "guard-boundary-conormal-generated-d0/v1",
        "aggregate": dict(sorted(aggregate.items())),
        "family_gains": dict(sorted(family_gains.items())),
        "role_outcomes": dict(sorted(roles.items())),
        "candidate_sha256": hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest(),
        "entrypoint": "candidate.py:solve_portfolio",
        "truth_case_family_or_outcome_visible_to_candidate": False,
        "baseline_lane_fraction": 0.75,
    }
    (HERE / "AGGREGATE.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
