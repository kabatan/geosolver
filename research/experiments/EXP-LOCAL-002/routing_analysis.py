#!/usr/bin/env python3
"""Execute and evaluate the preregistered EXP-LOCAL-002 LM/TR route."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parent
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

import development_analysis as dev  # noqa: E402

from research.harness.bootstrap import PairedValue, make_bootstrap_plan  # noqa: E402


ROUTE_ID = "ROUTE-LMTR-A1"
ROUTE_WORKER = EXPERIMENT_ROOT / "run_routing_worker.jl"
AMENDMENT = EXPERIMENT_ROOT / "routing-amendment.json"
DEVELOPMENT_ATTEMPTS = (
    REPO_ROOT / "research" / "results" / "EXP-LOCAL-002" / "development-v0" / "attempts.csv.gz"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "research"
    / "results"
    / "EXP-LOCAL-002"
    / "routing-development-v0"
)
CONTROL_VARIANTS = ("NLS-TR", "NLS-LM", "LXR-LMQR")
ALL_VARIANTS = (ROUTE_ID, *CONTROL_VARIANTS)
BOOTSTRAP_SEED = 3_002
BOOTSTRAP_RESAMPLES = 10_000

ROUTING_BOOL_FIELDS = ("routing_diagnostic_computed", "routing_explicit_fallback")
ROUTING_INT_FIELDS = (
    "routing_dimension",
    "routing_numerical_rank",
    "routing_residual_calls",
    "routing_svd_count",
)
ROUTING_OPTIONAL_FLOAT_FIELDS = ("routing_condition_estimate", "routing_rank_cutoff")


def sha256_file(path: Path) -> str:
    return dev.sha256_file(path)


def load_amendment() -> dict[str, Any]:
    amendment = dev.load_json(AMENDMENT)
    if amendment.get("status") != "preregistered-before-routing-outcomes":
        raise dev.ArtifactValidationError("routing amendment is not preregistered")
    if amendment.get("selected_route", {}).get("id") != ROUTE_ID:
        raise dev.ArtifactValidationError("routing amendment route ID drift")
    tuning = amendment.get("tuning_round", {})
    if tuning != {"used": 1, "limit": 1, "post_amendment_retuning_allowed": False}:
        raise dev.ArtifactValidationError("single tuning round is not frozen")
    return amendment


def parse_route_row(raw: Mapping[str, str]) -> dict[str, Any]:
    row = dev.parse_row(raw)
    for field in ROUTING_BOOL_FIELDS:
        row[field] = dev.parse_bool(raw[field], field)
    for field in ROUTING_INT_FIELDS:
        row[field] = int(raw[field])
    for field in ROUTING_OPTIONAL_FLOAT_FIELDS:
        row[field] = float(raw[field]) if raw[field] else None
    row["routing_wall_seconds"] = float(raw["routing_wall_seconds"])
    return row


def load_route_worker(
    work_directory: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    csv_path = work_directory / "worker-route-lmtr-a1.csv"
    metadata_path = work_directory / "worker-route-lmtr-a1.json"
    if not csv_path.is_file() or not metadata_path.is_file():
        raise dev.ArtifactValidationError("routing worker artifacts are incomplete")
    metadata = dev.load_json(metadata_path)
    if metadata.get("route_id") != ROUTE_ID:
        raise dev.ArtifactValidationError("routing worker ID mismatch")
    if metadata.get("attempt_count") != dev.EXPECTED_INSTANCES * dev.EXPECTED_STARTS:
        raise dev.ArtifactValidationError("routing worker attempt count drift")
    if metadata.get("amendment_sha256") != sha256_file(AMENDMENT):
        raise dev.ArtifactValidationError("routing amendment checksum drift")
    if metadata.get("input_manifest_sha256") != sha256_file(dev.INPUT_MANIFEST):
        raise dev.ArtifactValidationError("routing input manifest checksum drift")
    if metadata.get("result_csv_sha256") != sha256_file(csv_path):
        raise dev.ArtifactValidationError("routing worker CSV checksum drift")
    source_commit = metadata.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise dev.ArtifactValidationError("routing source commit is unavailable")
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        raw_rows = list(csv.DictReader(stream))
    rows = [parse_route_row(row) for row in raw_rows]
    if len(rows) != dev.EXPECTED_INSTANCES * dev.EXPECTED_STARTS:
        raise dev.ArtifactValidationError("routing CSV row count drift")
    return rows, raw_rows, metadata


def load_control_rows() -> list[dict[str, Any]]:
    with gzip.open(DEVELOPMENT_ATTEMPTS, "rt", encoding="utf-8", newline="") as stream:
        rows = [dev.parse_row(row) for row in csv.DictReader(stream)]
    selected = [row for row in rows if row["variant"] in CONTROL_VARIANTS]
    expected = dev.EXPECTED_INSTANCES * dev.EXPECTED_STARTS * len(CONTROL_VARIANTS)
    if len(selected) != expected:
        raise dev.ArtifactValidationError("frozen control attempt count drift")
    return selected


def validate_route_pairs(
    route_rows: Sequence[Mapping[str, Any]],
    control_rows: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
) -> None:
    if any(row["variant"] != ROUTE_ID for row in route_rows):
        raise dev.ArtifactValidationError("route CSV contains an undeclared variant")
    if any(row["selected_variant"] not in ("NLS-TR", "NLS-LM") for row in route_rows):
        raise dev.ArtifactValidationError("route selected an undeclared local algorithm")
    route_map = {(row["instance_id"], row["start_index"]): row for row in route_rows}
    for variant in CONTROL_VARIANTS:
        control_map = {
            (row["instance_id"], row["start_index"]): row
            for row in control_rows
            if row["variant"] == variant
        }
        if set(route_map) != set(control_map):
            raise dev.ArtifactValidationError(f"route/control pairing drift for {variant}")
        for key, route in route_map.items():
            control = control_map[key]
            for field in (
                "family_id",
                "instance_id",
                "start_index",
                "start",
                "starts_checksum",
                "replay_checksum",
            ):
                if route[field] != control[field]:
                    raise dev.ArtifactValidationError(f"paired {field} drift at {key!r}")
            record = instances[key[0]]
            if route["replay_checksum"] != record["replay_checksum"]:
                raise dev.ArtifactValidationError("route replay checksum drift")
    for row in route_rows:
        if row["accepted"] != (row["canonical_valid"] and row["gold_matched"]):
            raise dev.ArtifactValidationError("route bypasses independent endpoint acceptance")
        if row["budget_exceeded"]:
            raise dev.ArtifactValidationError("route exceeds a solver budget")
        if row["routing_explicit_fallback"]:
            raise dev.ArtifactValidationError("route used a diagnostic fallback")


def charged_work(row: Mapping[str, Any]) -> int:
    return (
        int(row["callback_residual_calls"])
        + int(row["validation_residual_calls"])
        + int(row.get("routing_residual_calls", 0))
    )


def charged_wall(row: Mapping[str, Any]) -> float:
    return float(row["wall_seconds"]) + float(row.get("routing_wall_seconds", 0.0))


def metric_record(
    rows: Sequence[Mapping[str, Any]],
    *,
    variant: str,
    prefix: int,
    instance_ids: set[str],
    slice_kind: str,
    label: str,
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row["variant"] == variant
        and row["instance_id"] in instance_ids
        and row["start_index"] <= prefix
    ]
    checkpoints = [row for row in selected if row["start_index"] == prefix]
    if len(selected) != len(instance_ids) * prefix or len(checkpoints) != len(instance_ids):
        raise dev.ArtifactValidationError("routing metric slice is incomplete")
    accepted = sum(row["accepted"] for row in selected)
    full = sum(row["all_targets_prefix"] for row in checkpoints)
    bad = sum(row["false_candidate"] for row in selected)
    work = sum(charged_work(row) for row in selected)
    wall = sum(charged_wall(row) for row in selected)
    return {
        "variant": variant,
        "prefix": prefix,
        "slice_kind": slice_kind,
        "slice": label,
        "instance_count": len(instance_ids),
        "attempt_count": len(selected),
        "p_local_gold": accepted / len(selected),
        "p_full_target": full / len(checkpoints),
        "residual_qualified_non_gold_count": bad,
        "unsafe_accepted_count": sum(
            row["accepted"] and (not row["canonical_valid"] or not row["gold_matched"])
            for row in selected
        ),
        "fully_charged_work": work,
        "mean_fully_charged_work": work / len(selected),
        "fully_charged_wall_seconds": wall,
        "mean_fully_charged_wall_seconds": wall / len(selected),
        "budget_exhaustion_count": sum(row["budget_exhausted"] for row in selected),
        "budget_overrun_count": sum(row["budget_exceeded"] for row in selected),
        "nonbudget_exception_count": sum(
            row["exception"] is not None and not row["budget_exhausted"] for row in selected
        ),
        "routing_residual_calls": sum(int(row.get("routing_residual_calls", 0)) for row in selected),
        "routing_svd_count": sum(int(row.get("routing_svd_count", 0)) for row in selected),
        "lm_selected_count": sum(row.get("selected_variant") == "NLS-LM" for row in selected),
        "diagnostic_fallback_count": sum(row.get("routing_explicit_fallback", False) for row in selected),
    }


def aggregate_metrics(
    rows: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    slices: list[tuple[str, str, set[str]]] = [("overall", "overall", set(instances))]
    families = sorted({record["family_id"] for record in instances.values()})
    slices.extend(
        ("family", family, dev.instance_ids_for_slice(instances, "family", family))
        for family in families
    )
    slices.extend(
        ("stratum", stratum, dev.instance_ids_for_slice(instances, "stratum", stratum))
        for stratum in dev.STRATA
    )
    return [
        metric_record(
            rows,
            variant=variant,
            prefix=prefix,
            instance_ids=instance_ids,
            slice_kind=slice_kind,
            label=label,
        )
        for prefix in dev.PREFIXES
        for variant in ALL_VARIANTS
        for slice_kind, label, instance_ids in slices
    ]


def pair_maps(
    rows: Sequence[Mapping[str, Any]],
    variant: str,
    instance_ids: set[str],
    prefix: int,
) -> dict[tuple[str, int], Mapping[str, Any]]:
    return {
        (row["instance_id"], row["start_index"]): row
        for row in rows
        if row["variant"] == variant
        and row["instance_id"] in instance_ids
        and row["start_index"] <= prefix
    }


def paired_values(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate: str,
    control: str,
    metric: str,
    prefix: int,
    instance_ids: set[str],
) -> tuple[list[PairedValue], list[str]]:
    left = pair_maps(rows, candidate, instance_ids, prefix)
    right = pair_maps(rows, control, instance_ids, prefix)
    if set(left) != set(right):
        raise dev.ArtifactValidationError("routing bootstrap pair keys differ")
    values: list[PairedValue] = []
    evidence: list[str] = []
    if metric in ("p_local_gold", "bad_residual_reduction"):
        for key in sorted(left):
            candidate_row = left[key]
            control_row = right[key]
            if metric == "p_local_gold":
                candidate_value = float(candidate_row["accepted"])
                control_value = float(control_row["accepted"])
            else:
                candidate_value = -float(candidate_row["false_candidate"])
                control_value = -float(control_row["false_candidate"])
            pair_id = f"{key[0]}:start={key[1]}"
            values.append(
                PairedValue(candidate_row["family_id"], pair_id, candidate_value, control_value)
            )
            evidence.append(
                "|".join(
                    (
                        candidate_row["family_id"],
                        pair_id,
                        candidate_row["replay_checksum"],
                        candidate_row["starts_checksum"],
                        candidate_row["start"],
                    )
                )
            )
    elif metric == "p_full_target":
        for key in sorted(left):
            if key[1] != prefix:
                continue
            candidate_row = left[key]
            control_row = right[key]
            pair_id = f"{key[0]}:prefix={prefix}"
            values.append(
                PairedValue(
                    candidate_row["family_id"],
                    pair_id,
                    float(candidate_row["all_targets_prefix"]),
                    float(control_row["all_targets_prefix"]),
                )
            )
            evidence.append(
                "|".join(
                    (
                        candidate_row["family_id"],
                        pair_id,
                        candidate_row["replay_checksum"],
                        candidate_row["starts_checksum"],
                    )
                )
            )
    elif metric in ("relative_work_saving", "relative_wall_saving"):
        families = sorted({row["family_id"] for row in left.values()})
        for family in families:
            candidate_rows = [row for row in left.values() if row["family_id"] == family]
            control_rows = [row for row in right.values() if row["family_id"] == family]
            if metric == "relative_work_saving":
                candidate_total = sum(charged_work(row) for row in candidate_rows)
                control_total = sum(charged_work(row) for row in control_rows)
            else:
                candidate_total = sum(charged_wall(row) for row in candidate_rows)
                control_total = sum(charged_wall(row) for row in control_rows)
            saving = 1.0 - candidate_total / control_total
            values.append(PairedValue(family, "family-aggregate", saving, 0.0))
            evidence.extend(
                "|".join(
                    (
                        family,
                        row["instance_id"],
                        str(row["start_index"]),
                        row["replay_checksum"],
                        row["starts_checksum"],
                    )
                )
                for row in candidate_rows
            )
    else:
        raise ValueError(f"unknown routing paired metric {metric}")
    return values, evidence


def paired_reports(
    rows: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    plan_cache: dict[tuple[str, ...], Any] = {}

    def plan_for(instance_ids: set[str]) -> Any:
        families = tuple(sorted({instances[key]["family_id"] for key in instance_ids}))
        if families not in plan_cache:
            plan_cache[families] = make_bootstrap_plan(
                families,
                resamples=BOOTSTRAP_RESAMPLES,
                seed=BOOTSTRAP_SEED,
            )
        return plan_cache[families]

    reports: list[dict[str, Any]] = []
    overall_ids = set(instances)
    for prefix in dev.PREFIXES:
        for control in CONTROL_VARIANTS:
            for metric in (
                "p_local_gold",
                "p_full_target",
                "bad_residual_reduction",
                "relative_work_saving",
                "relative_wall_saving",
            ):
                values, evidence = paired_values(
                    rows,
                    candidate=ROUTE_ID,
                    control=control,
                    metric=metric,
                    prefix=prefix,
                    instance_ids=overall_ids,
                )
                report = dev.paired_interval(values, evidence, plan_for(overall_ids))
                report.update(
                    {
                        "candidate": ROUTE_ID,
                        "control": control,
                        "metric": metric,
                        "prefix": prefix,
                        "slice_kind": "overall",
                        "slice": "overall",
                    }
                )
                reports.append(report)

    for prefix in dev.PREFIXES:
        for stratum in dev.STRATA:
            instance_ids = dev.instance_ids_for_slice(instances, "stratum", stratum)
            for metric in ("p_local_gold", "p_full_target"):
                values, evidence = paired_values(
                    rows,
                    candidate=ROUTE_ID,
                    control="NLS-TR",
                    metric=metric,
                    prefix=prefix,
                    instance_ids=instance_ids,
                )
                report = dev.paired_interval(values, evidence, plan_for(instance_ids))
                report.update(
                    {
                        "candidate": ROUTE_ID,
                        "control": "NLS-TR",
                        "metric": metric,
                        "prefix": prefix,
                        "slice_kind": "stratum",
                        "slice": stratum,
                    }
                )
                reports.append(report)
    plans = {
        "schema_version": "routing-family-clustered-bootstrap-plan-set-v1",
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "plans": {
            ",".join(families): plan.to_dict()
            for families, plan in sorted(plan_cache.items())
        },
    }
    return reports, plans


def find_aggregate(
    aggregates: Sequence[Mapping[str, Any]],
    variant: str,
    prefix: int,
    slice_kind: str = "overall",
    label: str = "overall",
) -> Mapping[str, Any]:
    return next(
        item
        for item in aggregates
        if item["variant"] == variant
        and item["prefix"] == prefix
        and item["slice_kind"] == slice_kind
        and item["slice"] == label
    )


def find_paired(
    reports: Sequence[Mapping[str, Any]],
    control: str,
    metric: str,
    prefix: int = 32,
) -> Mapping[str, Any]:
    return next(
        item
        for item in reports
        if item["candidate"] == ROUTE_ID
        and item["control"] == control
        and item["metric"] == metric
        and item["prefix"] == prefix
        and item["slice_kind"] == "overall"
    )


def evaluate_development_freeze(
    aggregates: Sequence[Mapping[str, Any]],
    paired: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    prefix_checks: dict[str, Any] = {}
    prefixes_pass = True
    for prefix in dev.PREFIXES:
        route = find_aggregate(aggregates, ROUTE_ID, prefix)
        control = find_aggregate(aggregates, "NLS-TR", prefix)
        check = {
            "p_full_target_delta": route["p_full_target"] - control["p_full_target"],
            "residual_qualified_non_gold_delta": route[
                "residual_qualified_non_gold_count"
            ]
            - control["residual_qualified_non_gold_count"],
            "p_local_gold_delta": route["p_local_gold"] - control["p_local_gold"],
        }
        check["pass"] = (
            check["p_full_target_delta"] >= 0
            and check["residual_qualified_non_gold_delta"] <= 0
        )
        prefix_checks[str(prefix)] = check
        prefixes_pass = prefixes_pass and check["pass"]

    route = find_aggregate(aggregates, ROUTE_ID, 32)
    control = find_aggregate(aggregates, "NLS-TR", 32)
    local = find_paired(paired, "NLS-TR", "p_local_gold")
    work_ratio = route["fully_charged_work"] / control["fully_charged_work"]
    wall_ratio = route["fully_charged_wall_seconds"] / control["fully_charged_wall_seconds"]
    selection_fraction = route["lm_selected_count"] / route["attempt_count"]
    safety = {
        "unsafe_accepted_count": route["unsafe_accepted_count"],
        "budget_overrun_count": route["budget_overrun_count"],
        "nonbudget_exception_count": route["nonbudget_exception_count"],
        "diagnostic_fallback_count": route["diagnostic_fallback_count"],
    }
    criteria = {
        "safety_zero": all(value == 0 for value in safety.values()),
        "prefix_truth_nonregression": prefixes_pass,
        "prefix32_p_local_gain_at_least_0_005":
            prefix_checks["32"]["p_local_gold_delta"] >= 0.005,
        "paired_lower95_nonnegative": local["lower_95"] >= 0,
        "positive_family_count_at_least_one": local["positive_family_count"] >= 1,
        "fully_charged_work_ratio_at_most_1_05": work_ratio <= 1.05,
        "warm_wall_ratio_at_most_1_10": wall_ratio <= 1.10,
        "lm_selection_fraction_in_range": 0 < selection_fraction <= 0.25,
    }
    passed = all(criteria.values())
    return {
        "passed": passed,
        "criteria": criteria,
        "prefix_checks": prefix_checks,
        "safety": safety,
        "paired_p_local_gold": dict(local),
        "fully_charged_work_ratio": work_ratio,
        "warm_wall_ratio": wall_ratio,
        "lm_selection_fraction": selection_fraction,
        "on_failure": "stop-with-negative-result-no-locked-materialization",
        "on_pass": "materialize-preregistered-generator-disjoint-locked-inputs",
    }


def write_aggregate_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def report_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# EXP-LOCAL-002 diagnostic LM/TR routing development replay",
        "",
        "This is the single preregistered tuning round. It does not access locked inputs or authorize production changes.",
        "",
        "| Prefix | Variant | P_local_gold | P_full_target | Residual-qualified non-Gold | Fully charged work | Warm wall (s) |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    aggregates = summary["aggregates"]
    for prefix in dev.PREFIXES:
        for variant in (ROUTE_ID, "NLS-TR", "NLS-LM", "LXR-LMQR"):
            item = find_aggregate(aggregates, variant, prefix)
            lines.append(
                f"| {prefix} | {variant} | {item['p_local_gold']:.6f} | "
                f"{item['p_full_target']:.6f} | "
                f"{item['residual_qualified_non_gold_count']} | "
                f"{item['fully_charged_work']} | "
                f"{item['fully_charged_wall_seconds']:.6f} |"
            )
    decision = summary["development_freeze_decision"]
    lines.extend(
        [
            "",
            "## Preregistered decision",
            "",
            f"- Development freeze gate passed: **{decision['passed']}**.",
            f"- Prefix-32 P_local_gold delta vs NLS-TR: **{decision['prefix_checks']['32']['p_local_gold_delta']:.6f}**.",
            f"- Fully charged work ratio vs NLS-TR: **{decision['fully_charged_work_ratio']:.6f}**.",
            f"- LM selection fraction: **{decision['lm_selection_fraction']:.6f}**.",
            "- Locked inputs remain inaccessible unless every declared criterion passes.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_final_artifacts(output: Path) -> None:
    required = (
        "route-attempts.csv.gz",
        "aggregates.csv",
        "paired-bootstrap.json",
        "bootstrap-plans.json.gz",
        "environment.json",
        "summary.json",
        "development-freeze-decision.json",
        "routing-development-report.md",
    )
    for filename in required:
        if not (output / filename).is_file():
            raise dev.ArtifactValidationError(f"missing routing artifact {filename}")
    summary = dev.load_json(output / "summary.json")
    decision = dev.load_json(output / "development-freeze-decision.json")
    if summary.get("development_freeze_decision") != decision:
        raise dev.ArtifactValidationError("routing decision artifact drift")
    environment = dev.load_json(output / "environment.json")
    checksums = environment.get("checksums", {})
    for key, filename in {
        "route_attempts_csv_gz_sha256": "route-attempts.csv.gz",
        "aggregates_csv_sha256": "aggregates.csv",
        "paired_bootstrap_sha256": "paired-bootstrap.json",
        "bootstrap_plans_gz_sha256": "bootstrap-plans.json.gz",
        "decision_sha256": "development-freeze-decision.json",
    }.items():
        if checksums.get(key) != sha256_file(output / filename):
            raise dev.ArtifactValidationError(f"routing checksum drift for {filename}")
    with gzip.open(output / "route-attempts.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        route_rows = [parse_route_row(row) for row in csv.DictReader(stream)]
    manifest = dev.load_json(dev.INPUT_MANIFEST)
    instances = dev.validate_input_manifest(manifest)
    controls = load_control_rows()
    validate_route_pairs(route_rows, controls, instances)
    if len(route_rows) != dev.EXPECTED_INSTANCES * dev.EXPECTED_STARTS:
        raise dev.ArtifactValidationError("compressed routing attempts are incomplete")


def analyze(
    work_directory: Path,
    output: Path,
    *,
    command_seconds: float,
) -> dict[str, Any]:
    amendment = load_amendment()
    manifest = dev.load_json(dev.INPUT_MANIFEST)
    instances = dev.validate_input_manifest(manifest)
    route_rows, route_raw, worker_metadata = load_route_worker(work_directory)
    control_rows = load_control_rows()
    validate_route_pairs(route_rows, control_rows, instances)
    all_rows = [*route_rows, *control_rows]
    aggregates = aggregate_metrics(all_rows, instances)
    paired, plans = paired_reports(all_rows, instances)
    decision = evaluate_development_freeze(aggregates, paired)

    output.mkdir(parents=True, exist_ok=True)
    route_csv_path = work_directory / "worker-route-lmtr-a1.csv"
    dev.write_compressed_attempts(
        output / "route-attempts.csv.gz",
        [(route_csv_path, route_raw)],
    )
    write_aggregate_csv(output / "aggregates.csv", aggregates)
    dev.write_json(output / "paired-bootstrap.json", paired)
    dev.write_json_gzip(output / "bootstrap-plans.json.gz", plans)
    dev.write_json(output / "development-freeze-decision.json", decision)
    summary = {
        "schema_version": "exp-local-002-routing-development-summary-v1",
        "experiment_id": "EXP-LOCAL-002",
        "route_id": ROUTE_ID,
        "status": "development-freeze-passed" if decision["passed"] else "development-negative-stop",
        "locked_inputs_materialized": False,
        "post_amendment_retuning_performed": False,
        "attempt_count": len(route_rows),
        "prefixes": list(dev.PREFIXES),
        "aggregates": aggregates,
        "development_freeze_decision": decision,
        "production_dependency_change_allowed": False,
        "promotion_decision": "not-evaluated-development-routing",
    }
    dev.write_json(output / "summary.json", summary)
    (output / "routing-development-report.md").write_text(
        report_markdown(summary),
        encoding="utf-8",
        newline="\n",
    )
    environment = {
        "schema_version": "exp-local-002-routing-development-environment-v1",
        "experiment_id": "EXP-LOCAL-002",
        "route_id": ROUTE_ID,
        "command_seconds": command_seconds,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "worker_metadata": worker_metadata,
        "frozen_control_artifacts": amendment["frozen_parent_evidence"],
        "checksums": {
            "amendment_sha256": sha256_file(AMENDMENT),
            "development_input_manifest_sha256": sha256_file(dev.INPUT_MANIFEST),
            "frozen_control_attempts_sha256": sha256_file(DEVELOPMENT_ATTEMPTS),
            "route_attempts_csv_gz_sha256": sha256_file(output / "route-attempts.csv.gz"),
            "aggregates_csv_sha256": sha256_file(output / "aggregates.csv"),
            "paired_bootstrap_sha256": sha256_file(output / "paired-bootstrap.json"),
            "bootstrap_plans_gz_sha256": sha256_file(output / "bootstrap-plans.json.gz"),
            "decision_sha256": sha256_file(output / "development-freeze-decision.json"),
            "routing_analysis_source_sha256": sha256_file(Path(__file__)),
            "routing_policy_source_sha256": sha256_file(
                EXPERIMENT_ROOT / "src" / "routing_policy.jl"
            ),
            "routing_worker_source_sha256": sha256_file(
                EXPERIMENT_ROOT / "src" / "RoutingLocal002.jl"
            ),
        },
    }
    dev.write_json(output / "environment.json", environment)
    validate_final_artifacts(output)
    return summary


def run_worker(julia: str, work_directory: Path) -> None:
    subprocess.run(
        [
            julia,
            f"--project={EXPERIMENT_ROOT}",
            str(ROUTE_WORKER),
            "--out",
            str(work_directory),
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def orchestrate(julia: str, output: Path, force: bool, resume: bool) -> dict[str, Any]:
    load_amendment()
    if output.exists() and force:
        shutil.rmtree(output)
    if output.exists() and not force and not (output / ".work").is_dir():
        raise FileExistsError(f"routing output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    work = output / ".work"
    work.mkdir(parents=True, exist_ok=True)
    worker_complete = (work / "worker-route-lmtr-a1.csv").is_file() and (
        work / "worker-route-lmtr-a1.json"
    ).is_file()
    started = time.perf_counter()
    if resume and worker_complete:
        print("reusing completed routing worker", flush=True)
    else:
        print("starting fresh ROUTE-LMTR-A1 worker", flush=True)
        run_worker(julia, work)
    summary = analyze(work, output, command_seconds=time.perf_counter() - started)
    shutil.rmtree(work)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--julia", default=os.environ.get("JULIA", "julia"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    output = args.out.resolve()
    if args.validate_only:
        validate_final_artifacts(output)
        print(f"validated routing development artifacts at {output}")
        return 0
    summary = orchestrate(args.julia, output, args.force, args.resume)
    decision = summary["development_freeze_decision"]
    print(f"routing development freeze passed: {decision['passed']}")
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
