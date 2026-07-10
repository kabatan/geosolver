#!/usr/bin/env python3
"""Independent standard-library verifier for EXP-SINGULAR-001 development output."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


VARIANTS = (
    "S0-POINT-REPLAY",
    "S1-AP-LMQR",
    "SLB-ANALYTIC-DERIVATIVES",
)


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(result_root: Path, input_manifest: Path) -> dict[str, Any]:
    attempts_path = result_root / "attempts.json"
    environment_path = result_root / "environment.json"
    summary_path = result_root / "summary.json"
    attempts = _load(attempts_path)
    environment = _load(environment_path)
    reported = _load(summary_path)
    frozen_input = _load(input_manifest)
    rows = attempts["rows"]

    expected_cases = {
        entry["id"]: entry for entry in frozen_input["cases"]
    }
    expected_pairs = {
        (case_id, variant)
        for case_id in expected_cases
        for variant in VARIANTS
    }
    actual_pairs = {(row["case_id"], row["variant"]) for row in rows}
    if len(rows) != len(expected_pairs) or actual_pairs != expected_pairs:
        raise ValueError("attempt rows do not cover the frozen case/variant grid exactly once")
    if len(actual_pairs) != len(rows):
        raise ValueError("duplicate case/variant attempt row")
    for row in rows:
        expected = expected_cases[row["case_id"]]
        if row["case_checksum"] != expected["checksum"]:
            raise ValueError(f"case checksum mismatch for {row['case_id']}")
        if row["outcome"]["case_checksum"] != expected["checksum"]:
            raise ValueError(f"outcome checksum mismatch for {row['case_id']}")

    input_sha = _sha256(input_manifest)
    if environment["input_manifest_sha256"] != input_sha:
        raise ValueError("environment input-manifest hash mismatch")
    if attempts["input_manifest_sha256"] != input_sha:
        raise ValueError("attempt input-manifest hash mismatch")

    aggregates: dict[str, Any] = {}
    for variant in VARIANTS:
        selected = [row for row in rows if row["variant"] == variant]
        phase_a = [
            row
            for row in selected
            if row["gold_kind"] == "isolated_root"
            and row["capability"] == "C2"
            and row["family"] == "SING-NEAR-NULL-FULL-RANK"
        ]
        successes = sum(row["assessment"]["gold_success"] for row in phase_a)
        promoted = [row for row in selected if row["assessment"]["promoted"]]
        aggregates[variant] = {
            "phase_a_eligible": len(phase_a),
            "phase_a_gold_successes": successes,
            "phase_a_p_refinement_gold": successes / len(phase_a),
            "promoted": len(promoted),
            "false_promotions": sum(
                row["assessment"]["false_promotion"] for row in selected
            ),
            "configuration_coverage_failures": sum(
                not row["assessment"]["configuration_error_covered"]
                for row in promoted
            ),
            "target_coverage_failures": sum(
                not row["assessment"]["target_error_covered"] for row in promoted
            ),
            "callbacks": sum(row["outcome"]["work"]["callbacks"] for row in selected),
            "precision_equivalent_oracle_work": sum(
                row["outcome"]["work"]["precision_equivalent_oracle_work"]
                for row in selected
            ),
        }

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["variant"] != "S1-AP-LMQR":
            continue
        group = row["metamorphic_group"]
        if group.startswith("dev-near-"):
            groups.setdefault(group, []).append(row)
    disagreement_groups: list[str] = []
    for group, entries in sorted(groups.items()):
        decisions = {
            (
                row["outcome"]["status"],
                row["assessment"]["gold_success"],
                row["assessment"]["false_promotion"],
            )
            for row in entries
        }
        if len(decisions) != 1:
            disagreement_groups.append(group)

    semantic_only = sum(
        row["outcome"]["status"] == "promoted"
        and row["outcome"]["root_evidence"] is None
        for row in rows
    )
    false_promotions = sum(
        aggregate["false_promotions"] for aggregate in aggregates.values()
    )
    s0 = aggregates["S0-POINT-REPLAY"]
    s1 = aggregates["S1-AP-LMQR"]
    coverage_failures = (
        s1["configuration_coverage_failures"]
        + s1["target_coverage_failures"]
    )
    delta = (
        s1["phase_a_p_refinement_gold"] - s0["phase_a_p_refinement_gold"]
    )
    criteria = {
        "error_coverage_failures_zero": coverage_failures == 0,
        "false_promotions_zero": false_promotions == 0,
        "metamorphic_disagreements_zero": not disagreement_groups,
        "phase_a_gain_at_least_0_15": delta >= 0.15,
        "phase_a_s1_recall_at_least_0_90": (
            s1["phase_a_p_refinement_gold"] >= 0.90
        ),
        "semantic_replay_only_promotions_zero": semantic_only == 0,
    }
    passed = all(criteria.values())

    for variant, independent in aggregates.items():
        stated = reported["variants"][variant]
        for key in (
            "phase_a_eligible",
            "phase_a_gold_successes",
            "phase_a_p_refinement_gold",
            "promoted",
            "false_promotions",
            "callbacks",
            "precision_equivalent_oracle_work",
        ):
            if independent[key] != stated[key]:
                raise ValueError(f"summary mismatch for {variant}.{key}")
    if reported["advancement_criteria"] != criteria:
        raise ValueError("reported advancement criteria differ from independent analysis")
    if reported["development_advancement_passed"] != passed:
        raise ValueError("reported advancement decision differs from independent analysis")
    if reported["product_connected"] or reported["locked_validation"]:
        raise ValueError("development result claims forbidden product/locked status")

    return {
        "analyzer_sha256": _sha256(Path(__file__)),
        "artifact_sha256": {
            "attempts.json": _sha256(attempts_path),
            "environment.json": _sha256(environment_path),
            "summary.json": _sha256(summary_path),
        },
        "development_advancement_passed": passed,
        "experiment_id": "EXP-SINGULAR-001",
        "input_manifest_sha256": input_sha,
        "metamorphic_disagreement_groups": disagreement_groups,
        "product_connected": False,
        "recomputed_criteria": criteria,
        "recomputed_variants": aggregates,
        "schema": "geotarget.singular-independent-analysis/v1",
        "source_commit": environment["source_commit"],
        "summary_match": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_root", type=Path)
    parser.add_argument("input_manifest", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    document = analyze(arguments.result_root, arguments.input_manifest)
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
