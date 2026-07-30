from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from candidate import solve_portfolio
from generated_cases import make_case, make_isolated_counter, make_opaque_counter, transformed_case


FAMILIES = ("curved_circle", "disconnected_ovals", "scaled_space_curve", "nonpolynomial_sheet")
ROLES = ("positive", "negative", "near_miss")
SEEDS = range(12)
CAP = 44


def _solved(results) -> bool:
    return any(item.solved for item in results)


def main() -> None:
    started = time.process_time()
    rows = []
    metamorphic_failures = 0
    for family in FAMILIES:
        for role in ROLES:
            for seed in SEEDS:
                case = make_case(family, role, seed)
                control = solve_portfolio(case.problem, case.starts, CAP, False)
                candidate = solve_portfolio(case.problem, case.starts, CAP, True)
                cs, ns = _solved(control), _solved(candidate)
                rows.append({
                    "family": family,
                    "role": role,
                    "gain": ns and not cs,
                    "loss": cs and not ns,
                    "false": role != "positive" and ns,
                    "activated": candidate[3].activated,
                    "ed_queries": candidate[3].ed_queries,
                    "slice_moves": candidate[3].slice_moves,
                    "same_callbacks": sum(x.callbacks for x in control) == sum(x.callbacks for x in candidate),
                    "same_insurance": all(
                        np.array_equal(control[i].point, candidate[i].point)
                        and control[i].solved == candidate[i].solved
                        for i in range(3)
                    ),
                })

                if role == "positive" and seed < 4:
                    n = case.starts[0].size
                    theta = 0.37
                    q = np.eye(n)
                    if n >= 2:
                        q[:2, :2] = [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]
                    scale = np.diag(np.geomspace(0.3, 3.0, n))
                    t = q @ scale @ np.eye(n)[::-1]
                    m = case.problem.observe(case.starts[0]).residual.size
                    rp = np.eye(m)[::-1]
                    rs = np.diag(np.where(np.arange(m) % 2, -5.0, 0.2))
                    changed = transformed_case(case, t, rs @ rp)
                    changed_result = solve_portfolio(changed.problem, changed.starts, CAP, True)
                    if _solved(candidate) != _solved(changed_result):
                        metamorphic_failures += 1

    fallback_rows = []
    for seed in SEEDS:
        for maker in (make_isolated_counter, make_opaque_counter):
            case = maker(seed)
            control = solve_portfolio(case.problem, case.starts, CAP, False)
            candidate = solve_portfolio(case.problem, case.starts, CAP, True)
            fallback_rows.append({
                "family": case.family,
                "false": _solved(candidate),
                "same_callbacks": sum(x.callbacks for x in control) == sum(x.callbacks for x in candidate),
                "same_insurance": all(
                    np.array_equal(control[i].point, candidate[i].point)
                    and control[i].solved == candidate[i].solved
                    for i in range(3)
                ),
                "candidate_status": candidate[3].status,
            })

    aggregate = {
        "schema": "ed-critical-moved-slice-generated-d0/v1",
        "cases": len(rows) + len(fallback_rows),
        "positive_cases": sum(r["role"] == "positive" for r in rows),
        "gains": sum(r["gain"] for r in rows),
        "losses": sum(r["loss"] for r in rows),
        "false": sum(r["false"] for r in rows) + sum(r["false"] for r in fallback_rows),
        "extra": 0,
        "activation": sum(r["activated"] for r in rows),
        "ed_queries": sum(r["ed_queries"] for r in rows),
        "slice_moves": sum(r["slice_moves"] for r in rows),
        "callback_mismatches": sum(not r["same_callbacks"] for r in rows + fallback_rows),
        "insurance_mismatches": sum(not r["same_insurance"] for r in rows + fallback_rows),
        "metamorphic_checks": len(FAMILIES) * 4,
        "metamorphic_failures": metamorphic_failures,
        "by_family": {
            family: {
                "positive_gains": sum(r["gain"] and r["family"] == family and r["role"] == "positive" for r in rows),
                "losses": sum(r["loss"] and r["family"] == family for r in rows),
                "false": sum(r["false"] and r["family"] == family for r in rows),
            }
            for family in FAMILIES
        },
        "fallback_statuses": sorted({r["candidate_status"] for r in fallback_rows}),
        "callback_cap_per_lane": CAP,
        "baseline_lane_fraction": 0.75,
        "candidate_lane_fraction": 0.25,
        "cpu_seconds": time.process_time() - started,
    }
    output = Path(__file__).with_name("AGGREGATE.json")
    output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
