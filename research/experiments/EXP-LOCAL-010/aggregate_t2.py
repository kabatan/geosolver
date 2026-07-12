#!/usr/bin/env python3
"""Aggregate the preregistered 48-case local-correction T2 shards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aggregate_t0 import (
    CAMPAIGN_SCHEMA,
    CANDIDATE_SHADOW,
    CONTROL,
    CRITICAL_FAMILIES,
    aggregate_expected,
)


CASE_COUNT = 48
T2_SUITE = "t2"
T2_INPUT_MANIFEST = (
    Path(__file__).parent.parent / "EXP-LOCAL-004" / "t2-input-manifest.json"
)


def expected_cases() -> list[dict[str, Any]]:
    document = json.loads(T2_INPUT_MANIFEST.read_text(encoding="utf-8"))
    instances = document.get("instances", [])
    if (
        document.get("suite") != T2_SUITE
        or int(document.get("instance_count", 0)) != CASE_COUNT
        or len(instances) != CASE_COUNT
        or int(document.get("starts_per_instance", 0)) != 32
    ):
        raise ValueError(
            "committed EXP-LOCAL-004 T2 manifest has an unexpected contract"
        )
    cases = [
        {
            "instance_id": instance["instance_id"],
            "family_id": instance["family_id"],
            "replay_checksum": instance["replay_checksum"],
            "targets": int(instance["target_count"]),
            "saved_starts_checksum": instance["saved_starts_checksum"],
        }
        for instance in instances
    ]
    if sum(case["targets"] for case in cases) != 88:
        raise ValueError("committed T2 manifest must contain 88 targets")
    return cases


def aggregate(paths: list[Path]) -> dict[str, Any]:
    result = aggregate_expected(
        paths,
        expected_cases(),
        suite=T2_SUITE,
        schema=CAMPAIGN_SCHEMA,
    )
    control = result["variant_metrics"][CONTROL]
    if control["right_censored_callback_work"] <= 0:
        raise ValueError("T2 control callback work must be positive")
    t2_gates: dict[str, Any] = {}
    for candidate in CANDIDATE_SHADOW:
        metrics = result["variant_metrics"][candidate]
        pair = result["candidate_gates"][candidate]
        recall_delta = (
            metrics["assessor_target_recall"] - control["assessor_target_recall"]
        )
        work_ratio = (
            metrics["right_censored_callback_work"]
            / control["right_censored_callback_work"]
        )
        critical_deltas = {
            family: (
                result["family_metrics"][candidate][family]["target_recall"]
                - result["family_metrics"][CONTROL][family]["target_recall"]
            )
            for family in sorted(CRITICAL_FAMILIES)
        }
        gates = {
            "accounting_and_caps": not any(result["accounting"].values()),
            "candidate_shadow_callback_identity": pair["callback_mismatches"] == 0,
            "candidate_assessor_safe": metrics["assessor_unsafe"] == 0,
            "candidate_reported_acceptance_safe": metrics["reported_unsafe"] == 0,
            "safe_full_cases_noninferior_to_control": (
                metrics["assessor_safe_full_cases"]
                >= control["assessor_safe_full_cases"]
            ),
            "target_recall_delta_at_least_minus_0_01": recall_delta >= -0.01,
            "work_ratio_at_most_1_2": work_ratio <= 1.2,
            "critical_family_target_recall_delta_at_least_minus_0_02": all(
                delta >= -0.02 for delta in critical_deltas.values()
            ),
            "three_unrelated_active_families": len(pair["support_families"]) >= 3,
        }
        t2_gates[candidate] = {
            "gates": gates,
            "passes_t2": all(gates.values()),
            "target_recall_delta_vs_control": recall_delta,
            "right_censored_work_ratio_vs_control": work_ratio,
            "critical_family_target_recall_deltas": critical_deltas,
            "active_family_count": len(pair["support_families"]),
            "mean_family_safe_full_rate": metrics["mean_family_safe_full_rate"],
        }
    result["t2_candidate_gates"] = t2_gates

    survivors = [
        candidate for candidate in CANDIDATE_SHADOW if t2_gates[candidate]["passes_t2"]
    ]
    selected = None
    if survivors:
        selected = max(
            survivors,
            key=lambda candidate: (
                result["variant_metrics"][candidate]["mean_family_safe_full_rate"],
                result["variant_metrics"][candidate]["assessor_target_recall"],
                -result["variant_metrics"][candidate]["right_censored_callback_work"],
                t2_gates[candidate]["active_family_count"],
                candidate == "E1-FD2-CPQR3",
            ),
        )
    result["selected_finalist"] = selected
    result["finalist_tie_break"] = [
        "higher-mean-family-safe-full-rate",
        "higher-total-target-recall",
        "lower-total-right-censored-callback-work",
        "larger-active-family-count",
        "cpqr-on-exact-tie",
    ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("shards", nargs=CASE_COUNT, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = aggregate(args.shards)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
