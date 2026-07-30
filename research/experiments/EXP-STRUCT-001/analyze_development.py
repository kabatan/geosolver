#!/usr/bin/env python3
"""Aggregate truth-blind V15 structural applicability from a JSONL input set."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from block_structure import extract_v15_structure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    reasons = collections.Counter()
    block_counts = collections.Counter()
    maximum_blocks = collections.Counter()
    factor_ratios: list[float] = []
    polynomial_candidates = 0
    formulation_count = 0
    parse_failures = 0
    with args.input.open(encoding="utf-8") as source:
        for line in source:
            # Deliberately obtain only `formulation`; answer, target, problem ID,
            # source text, and every assessor-side field remain unobserved.
            document = json.loads(line)
            formulation = document.get("formulation")
            if not isinstance(formulation, dict):
                parse_failures += 1
                continue
            formulation_count += 1
            try:
                structure = extract_v15_structure(formulation)
            except (SyntaxError, TypeError, ValueError):
                parse_failures += 1
                continue
            plan = structure.plan
            reasons[plan.reason] += 1
            block_counts[str(len(plan.blocks))] += 1
            maximum_blocks[str(plan.maximum_block_size)] += 1
            if plan.applicable:
                factor_ratios.append(plan.factor_work_ratio)
            polynomial_candidates += structure.polynomial_scalar_candidate

    result = {
        "schema_version": "1.0.0",
        "experiment": "EXP-STRUCT-001-DEVELOPMENT-STATIC",
        "answer_or_target_used_for_routing": False,
        "formulations": formulation_count,
        "parse_failures": parse_failures,
        "applicable": reasons["decomposable"],
        "activation_rate": reasons["decomposable"] / formulation_count if formulation_count else 0.0,
        "reason_counts": dict(sorted(reasons.items())),
        "block_count_histogram": dict(sorted(block_counts.items(), key=lambda item: int(item[0]))),
        "maximum_block_size_histogram": dict(
            sorted(maximum_blocks.items(), key=lambda item: int(item[0]))
        ),
        "applicable_factor_work_ratio_mean": (
            sum(factor_ratios) / len(factor_ratios) if factor_ratios else None
        ),
        "polynomial_scalar_candidates": polynomial_candidates,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
