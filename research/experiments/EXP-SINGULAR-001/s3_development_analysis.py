#!/usr/bin/env python3
"""Independent standard-library verifier for the frozen S3 development gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


VARIANTS = (
    "S1-AP-LMQR",
    "S3-AP-BROYDEN",
    "S3-ANALYTIC-SECANT-CONTROL",
)


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decision(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["outcome"]["status"],
        row["assessment"]["gold_success"],
        row["assessment"]["false_promotion"],
    )


def _eligible(case: dict[str, Any]) -> bool:
    if case["gold_analysis_only"]["kind"] != "isolated_root":
        return False
    if case["family"] == "SING-ISOLATED-MULTIPLE":
        return True
    return (
        case["family"] == "SING-TANGENCY-AND-CLOSE-ROOTS"
        and case["parameters"]["separation"] == 0.0
    )


def analyze(result_root: Path, input_manifest: Path) -> dict[str, Any]:
    attempts_path = result_root / "attempts.json"
    environment_path = result_root / "environment.json"
    summary_path = result_root / "summary.json"
    attempts = _load(attempts_path)
    environment = _load(environment_path)
    reported = _load(summary_path)
    frozen_input = _load(input_manifest)
    rows = attempts["rows"]

    if tuple(frozen_input["variants"]) != VARIANTS:
        raise ValueError("frozen S3 variants differ from the independent analyzer")
    expected_cases = {entry["id"]: entry for entry in frozen_input["cases"]}
    expected_pairs = {
        (case_id, variant) for case_id in expected_cases for variant in VARIANTS
    }
    actual_pairs = [(row["case_id"], row["variant"]) for row in rows]
    if len(actual_pairs) != len(expected_pairs) or set(actual_pairs) != expected_pairs:
        raise ValueError("attempt rows do not cover the frozen S3 grid exactly once")
    if len(set(actual_pairs)) != len(actual_pairs):
        raise ValueError("duplicate S3 case/variant attempt row")
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
        eligible = [
            row for row in selected if _eligible(expected_cases[row["case_id"]])
        ]
        successes = sum(row["assessment"]["gold_success"] for row in eligible)
        promoted = [row for row in selected if row["assessment"]["promoted"]]
        aggregates[variant] = {
            "budget_exhaustions": sum(
                row["outcome"]["work"]["budget_exhausted"] for row in selected
            ),
            "callbacks": sum(row["outcome"]["work"]["callbacks"] for row in selected),
            "deadline_reached": sum(
                row["outcome"]["work"]["deadline_reached"] for row in selected
            ),
            "eligible": len(eligible),
            "eligible_gold_successes": successes,
            "elapsed_seconds_max": max(
                row["outcome"]["work"]["elapsed_seconds"] for row in selected
            ),
            "elapsed_seconds_sum": sum(
                row["outcome"]["work"]["elapsed_seconds"] for row in selected
            ),
            "false_promotions": sum(
                row["assessment"]["false_promotion"] for row in selected
            ),
            "p_refinement_gold": successes / len(eligible),
            "precision_equivalent_oracle_work": sum(
                row["outcome"]["work"]["precision_equivalent_oracle_work"]
                for row in selected
            ),
            "promoted": len(promoted),
            "promoted_configuration_coverage_failures": sum(
                not row["assessment"]["configuration_error_covered"] for row in promoted
            ),
            "promoted_target_coverage_failures": sum(
                not row["assessment"]["target_error_covered"] for row in promoted
            ),
            "status_counts": {
                status: sum(row["outcome"]["status"] == status for row in selected)
                for status in ("promoted", "diagnostic_only", "unknown")
            },
        }

    groups = sorted({entry["metamorphic_group"] for entry in expected_cases.values()})
    metamorphic_disagreements: list[str] = []
    for variant in VARIANTS:
        for group in groups:
            entries = [
                row
                for row in rows
                if row["variant"] == variant and row["metamorphic_group"] == group
            ]
            if len(entries) != 3:
                raise ValueError(f"metamorphic group {group} does not have three forms")
            if len({_decision(row) for row in entries}) != 1:
                metamorphic_disagreements.append(f"{variant}:{group}")

    control_disagreements: list[str] = []
    for case_id in sorted(expected_cases):
        candidate = next(
            row
            for row in rows
            if row["case_id"] == case_id and row["variant"] == "S3-AP-BROYDEN"
        )
        control = next(
            row
            for row in rows
            if row["case_id"] == case_id
            and row["variant"] == "S3-ANALYTIC-SECANT-CONTROL"
        )
        if _decision(candidate) != _decision(control):
            control_disagreements.append(case_id)

    options = frozen_input["options"]
    maximum_precision = max(options["precision_ladder"])
    budget_violations: list[str] = []
    hard_budget_failures: list[str] = []
    for row in rows:
        work = row["outcome"]["work"]
        label = f"{row['variant']}:{row['case_id']}"
        if (
            work["callbacks"] > options["maximum_callbacks"]
            or work["iterations"] > options["maximum_iterations"]
            or work["maximum_precision_bits"] > maximum_precision
        ):
            budget_violations.append(label)
        if work["budget_exhausted"] and not (
            row["outcome"]["status"] == "unknown"
            and row["outcome"]["root_evidence"] is None
            and work["iterations"] == options["maximum_iterations"]
            and row["outcome"]["reason"] == "iterations"
        ):
            hard_budget_failures.append(label)

    noneligible_promotions = sorted(
        row["case_id"]
        for row in rows
        if row["variant"] == "S3-AP-BROYDEN"
        and not _eligible(expected_cases[row["case_id"]])
        and row["assessment"]["promoted"]
    )
    evidence_gate_failures: list[str] = []
    for row in rows:
        if row["variant"] != "S3-AP-BROYDEN" or row["outcome"]["status"] != "promoted":
            continue
        evidence = row["outcome"]["root_evidence"]
        if not (
            evidence
            and evidence["rank_stable"]
            and evidence["independent_confirmations_passed"]
            and evidence["canonical_confirmations_passed"]
            and evidence["linear_trace_passed"]
            and evidence["nullity"] > 0
        ):
            evidence_gate_failures.append(row["case_id"])

    semantic_only = sum(
        row["outcome"]["status"] == "promoted"
        and row["outcome"]["root_evidence"] is None
        for row in rows
    )
    false_promotions = sum(
        aggregate["false_promotions"] for aggregate in aggregates.values()
    )
    s1 = aggregates["S1-AP-LMQR"]
    s3 = aggregates["S3-AP-BROYDEN"]
    control = aggregates["S3-ANALYTIC-SECANT-CONTROL"]
    coverage_failures = (
        s3["promoted_configuration_coverage_failures"]
        + s3["promoted_target_coverage_failures"]
    )
    recall_delta = s3["p_refinement_gold"] - s1["p_refinement_gold"]
    criteria = {
        "analytic_control_decisions_match": not control_disagreements,
        "budget_limit_violations_zero": not budget_violations,
        "candidate_control_recall_equal": (
            s3["p_refinement_gold"] == control["p_refinement_gold"]
        ),
        "error_coverage_failures_zero": coverage_failures == 0,
        "false_promotions_zero": false_promotions == 0,
        "metamorphic_disagreements_zero": not metamorphic_disagreements,
        "noneligible_s3_promotions_zero": not noneligible_promotions,
        "promoted_evidence_gate_failures_zero": not evidence_gate_failures,
        "recall_gain_at_least_0_50": recall_delta >= 0.50,
        "s3_singular_recall_at_least_0_75": s3["p_refinement_gold"] >= 0.75,
        "semantic_replay_only_promotions_zero": semantic_only == 0,
    }
    passed = all(criteria.values())

    compared_variant_keys = (
        "budget_exhaustions",
        "callbacks",
        "deadline_reached",
        "eligible",
        "eligible_gold_successes",
        "false_promotions",
        "p_refinement_gold",
        "precision_equivalent_oracle_work",
        "promoted",
        "promoted_configuration_coverage_failures",
        "promoted_target_coverage_failures",
        "status_counts",
    )
    for variant, independent in aggregates.items():
        stated = reported["variants"][variant]
        for key in compared_variant_keys:
            if independent[key] != stated[key]:
                raise ValueError(f"summary mismatch for {variant}.{key}")
    expected_top_level = {
        "advancement_criteria": criteria,
        "analytic_control_disagreement_cases": control_disagreements,
        "budget_limit_violation_rows": budget_violations,
        "development_advancement_passed": passed,
        "evidence_gate_failure_cases": evidence_gate_failures,
        "false_promotions": false_promotions,
        "metamorphic_group_count": len(groups),
        "metamorphic_disagreement_groups": metamorphic_disagreements,
        "next_route": "S4-AP-BORDERED-NULLSPACE" if passed else None,
        "noneligible_s3_promotion_cases": noneligible_promotions,
        "recall_delta_from_s1": recall_delta,
        "semantic_replay_only_promotions": semantic_only,
        "status": "development-advance-s4" if passed else "development-stop-s3",
    }
    for key, expected in expected_top_level.items():
        if reported[key] != expected:
            raise ValueError(f"summary mismatch for {key}")
    if hard_budget_failures:
        raise ValueError(f"hard-budget fail-closed mismatch: {hard_budget_failures}")
    if reported["product_connected"] or reported["locked_validation"]:
        raise ValueError("S3 development result claims forbidden product/locked status")

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
        "locked_validation": False,
        "product_connected": False,
        "recomputed_analytic_control_disagreement_cases": control_disagreements,
        "recomputed_budget_limit_violation_rows": budget_violations,
        "recomputed_criteria": criteria,
        "recomputed_hard_budget_failures": hard_budget_failures,
        "recomputed_metamorphic_disagreement_groups": metamorphic_disagreements,
        "recomputed_noneligible_s3_promotion_cases": noneligible_promotions,
        "recomputed_variants": aggregates,
        "schema": "geotarget.singular-s3-independent-analysis/v1",
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
