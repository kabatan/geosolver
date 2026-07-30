#!/usr/bin/env python3
"""Run generated S0 structure and numerical safety controls."""

from __future__ import annotations

import json
import math
import random

from block_structure import (
    allocate_portfolio,
    analyze_relation_supports,
    solve_candidate,
)


def decomposable_residual(point):
    values = [point[0] * point[0] - 1.0]
    for index in range(1, len(point)):
        values.append(point[index] - (0.25 * point[index - 1] + index))
    return tuple(values)


def canonical_decomposable(point):
    return all(math.isfinite(value) for value in point) and max(
        map(abs, decomposable_residual(point))
    ) <= 1.0e-8


def main() -> None:
    dimension = 8
    supports = [(0,)] + [(index - 1, index) for index in range(1, dimension)]
    plan = analyze_relation_supports(supports, dimension)
    generator = random.Random(0xB10C)
    starts = [tuple(generator.uniform(-4.0, 4.0) for _ in range(dimension)) for _ in range(32)]
    baseline = [
        solve_candidate(
            decomposable_residual, start, plan, canonical_decomposable, use_block_route=False
        )
        for start in starts
    ]
    candidate = [
        solve_candidate(
            decomposable_residual, start, plan, canonical_decomposable, use_block_route=True
        )
        for start in starts
    ]

    irreducible = analyze_relation_supports(
        tuple((index, (index + 1) % dimension) for index in range(dimension)), dimension
    )
    allocation = allocate_portfolio(plan, 256, baseline_quota=0.5)
    fallback_allocation = allocate_portfolio(irreducible, 256, baseline_quota=0.5)
    result = {
        "schema_version": "1.0.0",
        "experiment": "EXP-STRUCT-001-S0",
        "generated_only": True,
        "truth_routing": False,
        "decomposable": {
            "applicable": plan.applicable,
            "block_count": len(plan.blocks),
            "maximum_block_size": plan.maximum_block_size,
            "structural_factor_work_ratio": plan.factor_work_ratio,
            "baseline": {
                "accepted": sum(attempt.accepted for attempt in baseline),
                "residual_evaluations": sum(attempt.residual_evaluations for attempt in baseline),
                "linear_work": sum(attempt.linear_work for attempt in baseline),
            },
            "block_candidate": {
                "accepted": sum(attempt.accepted for attempt in candidate),
                "residual_evaluations": sum(attempt.residual_evaluations for attempt in candidate),
                "linear_work": sum(attempt.linear_work for attempt in candidate),
            },
        },
        "irreducible_control": {
            "applicable": irreducible.applicable,
            "reason": irreducible.reason,
            "fallback_baseline_starts": fallback_allocation.baseline_starts,
            "fallback_block_starts": fallback_allocation.block_starts,
        },
        "portfolio": {
            "total_starts": allocation.total_starts,
            "baseline_starts": allocation.baseline_starts,
            "block_starts": allocation.block_starts,
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
