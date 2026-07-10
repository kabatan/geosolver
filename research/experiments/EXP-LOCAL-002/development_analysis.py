#!/usr/bin/env python3
"""Run, aggregate, and validate the EXP-LOCAL-002 development experiment."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parent
INPUT_MANIFEST = EXPERIMENT_ROOT / "development-input-manifest.json"
WORKER_ENTRYPOINT = EXPERIMENT_ROOT / "run_development_worker.jl"
DEFAULT_OUTPUT = REPO_ROOT / "research" / "results" / "EXP-LOCAL-002" / "development-v0"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.harness.bootstrap import (  # noqa: E402
    BootstrapPlan,
    PairedValue,
    family_clustered_paired_bootstrap,
    make_bootstrap_plan,
    validate_bootstrap_plan,
)


VARIANTS = ("NLS-LM", "NLS-TR", "NLS-RMN", "NLS-TR-STRICT", "LXR-LMQR")
PREFIXES = (8, 16, 32)
STRATA = tuple(f"S{index}" for index in range(1, 9))
BOOTSTRAP_SEED = 2_002
BOOTSTRAP_RESAMPLES = 10_000
EXPECTED_INSTANCES = 48
EXPECTED_STARTS = 32
EXPECTED_ROWS = EXPECTED_INSTANCES * EXPECTED_STARTS * len(VARIANTS)

BOOL_FIELDS = (
    "pilot_non_gating",
    "package_reported_success",
    "budget_exhausted",
    "budget_exceeded",
    "residual_qualified",
    "bounds_valid",
    "strict_guard_valid",
    "canonical_valid",
    "gold_config_match",
    "target_match",
    "gold_matched",
    "accepted",
    "false_candidate",
    "all_targets_prefix",
)
INT_FIELDS = (
    "start_index",
    "solver_nf",
    "callback_residual_calls",
    "validation_residual_calls",
    "njacs",
    "nfactors",
    "nsolve",
    "iterations",
    "gold_config_index",
    "targets_seen",
    "target_count",
)
OPTIONAL_INT_FIELDS = ("linear_work",)
FLOAT_FIELDS = (
    "internal_residual_tolerance",
    "wall_seconds",
)
OPTIONAL_FLOAT_FIELDS = (
    "raw_residual_linf",
    "scaled_residual_linf",
    "gold_normalized_distance",
    "target",
    "target_reference",
    "target_error",
)


class ArtifactValidationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_strings(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(values):
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ArtifactValidationError(f"{path} does not contain a JSON object")
    return value


def load_json_gzip(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ArtifactValidationError(f"{path} does not contain a compressed JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=True)
        stream.write("\n")


def write_json_gzip(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )
    with path.open("wb") as binary:
        with gzip.GzipFile(filename="", mode="wb", fileobj=binary, compresslevel=9, mtime=0) as stream:
            stream.write(payload)


def validate_input_manifest(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if manifest.get("schema_version") != "exp-local-002-development-input-v1":
        raise ArtifactValidationError("unexpected development input schema")
    if manifest.get("partition") != "development" or manifest.get("locked_validation") is not False:
        raise ArtifactValidationError("input manifest is not development-only")
    if manifest.get("instance_count") != EXPECTED_INSTANCES:
        raise ArtifactValidationError("development instance count drift")
    if manifest.get("starts_per_instance") != EXPECTED_STARTS:
        raise ArtifactValidationError("development start count drift")
    if tuple(manifest.get("prefixes", ())) != PREFIXES:
        raise ArtifactValidationError("prefix checkpoints drift")
    if tuple(manifest.get("variants", ())) != VARIANTS:
        raise ArtifactValidationError("variant list drift")
    family_counts = manifest.get("family_counts")
    if not isinstance(family_counts, dict) or len(family_counts) != 8:
        raise ArtifactValidationError("expected eight development families")
    if set(family_counts.values()) != {6}:
        raise ArtifactValidationError("each development family must have six instances")
    stratum_counts = manifest.get("stratum_counts")
    if not isinstance(stratum_counts, dict) or any(stratum_counts.get(item, 0) < 6 for item in STRATA):
        raise ArtifactValidationError("every stratum needs at least six instances")
    instances = manifest.get("instances")
    if not isinstance(instances, list) or len(instances) != EXPECTED_INSTANCES:
        raise ArtifactValidationError("manifest instance records are incomplete")
    indexed: dict[str, dict[str, Any]] = {}
    replay_checksums: set[str] = set()
    starts_checksums: set[str] = set()
    for record in instances:
        if not isinstance(record, dict):
            raise ArtifactValidationError("instance record is not an object")
        instance_id = record.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id or instance_id in indexed:
            raise ArtifactValidationError("duplicate or malformed instance ID")
        if record.get("start_count") != EXPECTED_STARTS:
            raise ArtifactValidationError(f"wrong start count for {instance_id}")
        strata = record.get("strata")
        if not isinstance(strata, list) or not strata or any(item not in STRATA for item in strata):
            raise ArtifactValidationError(f"invalid strata for {instance_id}")
        replay = record.get("replay_checksum")
        starts = record.get("starts_checksum")
        if not isinstance(replay, str) or len(replay) != 64 or replay in replay_checksums:
            raise ArtifactValidationError(f"invalid replay checksum for {instance_id}")
        if not isinstance(starts, str) or len(starts) != 64:
            raise ArtifactValidationError(f"invalid starts checksum for {instance_id}")
        replay_checksums.add(replay)
        starts_checksums.add(starts)
        indexed[instance_id] = record
    if len(starts_checksums) != EXPECTED_INSTANCES:
        raise ArtifactValidationError("start material is not unique per instance")
    return indexed


def parse_bool(value: str, field: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ArtifactValidationError(f"{field} is not a CSV boolean: {value!r}")


def parse_row(raw: Mapping[str, str]) -> dict[str, Any]:
    row: dict[str, Any] = dict(raw)
    for field in BOOL_FIELDS:
        row[field] = parse_bool(raw[field], field)
    for field in INT_FIELDS:
        row[field] = int(raw[field])
    for field in OPTIONAL_INT_FIELDS:
        row[field] = int(raw[field]) if raw[field] else None
    for field in FLOAT_FIELDS:
        row[field] = float(raw[field])
    for field in OPTIONAL_FLOAT_FIELDS:
        row[field] = float(raw[field]) if raw[field] else None
    # The pilot writer historically serialized Tuple strata using Julia's tuple
    # display, while vector-backed rows use semicolons. Accept only explicit S1--S8
    # tokens from either representation and reject every other payload below.
    row["strata"] = tuple(re.findall(r"S[1-8]", raw["strata"]))
    row["exception"] = raw["exception"] or None
    return row


def worker_slug(variant: str) -> str:
    return variant.lower().replace("-", "_")


def load_worker_outputs(
    work_directory: Path,
    manifest_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[Path, list[dict[str, str]]]]]:
    input_checksum = sha256_file(manifest_path)
    parsed_rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    raw_files: list[tuple[Path, list[dict[str, str]]]] = []
    source_commits: set[str] = set()
    for variant in VARIANTS:
        slug = worker_slug(variant)
        csv_path = work_directory / f"worker-{slug}.csv"
        metadata_path = work_directory / f"worker-{slug}.json"
        if not csv_path.is_file() or not metadata_path.is_file():
            raise ArtifactValidationError(f"missing worker artifacts for {variant}")
        worker = load_json(metadata_path)
        if worker.get("variant") != variant:
            raise ArtifactValidationError(f"worker metadata variant mismatch for {variant}")
        if worker.get("input_manifest_sha256") != input_checksum:
            raise ArtifactValidationError(f"worker input checksum mismatch for {variant}")
        if worker.get("result_csv_sha256") != sha256_file(csv_path):
            raise ArtifactValidationError(f"worker CSV checksum mismatch for {variant}")
        if worker.get("attempt_count") != EXPECTED_INSTANCES * EXPECTED_STARTS:
            raise ArtifactValidationError(f"worker attempt count mismatch for {variant}")
        source_commit = worker.get("source_commit")
        if not isinstance(source_commit, str) or len(source_commit) != 40:
            raise ArtifactValidationError(f"worker source revision is unavailable for {variant}")
        source_commits.add(source_commit)
        with csv_path.open("r", encoding="utf-8", newline="") as stream:
            raw_rows = list(csv.DictReader(stream))
        if len(raw_rows) != EXPECTED_INSTANCES * EXPECTED_STARTS:
            raise ArtifactValidationError(f"worker CSV row count mismatch for {variant}")
        if any(row["variant"] != variant for row in raw_rows):
            raise ArtifactValidationError(f"worker CSV includes another variant for {variant}")
        parsed_rows.extend(parse_row(row) for row in raw_rows)
        raw_files.append((csv_path, raw_rows))
        metadata.append(worker)
    if len(source_commits) != 1:
        raise ArtifactValidationError("workers did not execute the same committed source revision")
    return parsed_rows, metadata, raw_files


def validate_attempt_rows(
    rows: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise ArtifactValidationError(f"expected {EXPECTED_ROWS} attempts, found {len(rows)}")
    combinations: set[tuple[str, str, int]] = set()
    starts: dict[tuple[str, int], str] = {}
    prefix_state: dict[tuple[str, str], tuple[int, bool, int]] = {}
    for row in rows:
        variant = row["variant"]
        instance_id = row["instance_id"]
        start_index = row["start_index"]
        if variant not in VARIANTS or instance_id not in instances:
            raise ArtifactValidationError("attempt references an unknown variant or instance")
        record = instances[instance_id]
        if row["family_id"] != record["family_id"] or tuple(row["strata"]) != tuple(record["strata"]):
            raise ArtifactValidationError(f"family/stratum drift for {instance_id}")
        if row["replay_checksum"] != record["replay_checksum"]:
            raise ArtifactValidationError(f"replay checksum drift for {instance_id}")
        if row["starts_checksum"] != record["starts_checksum"]:
            raise ArtifactValidationError(f"starts checksum drift for {instance_id}")
        if not 1 <= start_index <= EXPECTED_STARTS:
            raise ArtifactValidationError("start index is outside the frozen prefix")
        key = (variant, instance_id, start_index)
        if key in combinations:
            raise ArtifactValidationError(f"duplicate attempt {key!r}")
        combinations.add(key)
        start_key = (instance_id, start_index)
        if start_key in starts and starts[start_key] != row["start"]:
            raise ArtifactValidationError(f"paired start drift for {start_key!r}")
        starts[start_key] = row["start"]
        accepted_expected = row["canonical_valid"] and row["gold_matched"]
        if row["accepted"] != accepted_expected:
            raise ArtifactValidationError("package return code leaked into acceptance")
        false_expected = row["residual_qualified"] and not row["gold_matched"]
        if row["false_candidate"] != false_expected:
            raise ArtifactValidationError("residual-qualified non-Gold predicate drift")
        if row["accepted"] and (not row["canonical_valid"] or not row["gold_matched"]):
            raise ArtifactValidationError("unsafe answer was accepted")
        if row["callback_residual_calls"] > 2_000 or row["iterations"] > 250:
            raise ArtifactValidationError("declared local budget was exceeded")
        prefix_key = (variant, instance_id)
        previous_seen, previous_full, previous_start = prefix_state.get(prefix_key, (0, False, 0))
        if start_index != previous_start + 1:
            raise ArtifactValidationError(f"non-contiguous prefix for {prefix_key!r}")
        if row["targets_seen"] < previous_seen:
            raise ArtifactValidationError("target prefix is not monotone")
        if previous_full and not row["all_targets_prefix"]:
            raise ArtifactValidationError("full-target prefix reverted")
        if row["all_targets_prefix"] != (row["targets_seen"] == row["target_count"]):
            raise ArtifactValidationError("full-target prefix predicate drift")
        prefix_state[prefix_key] = (
            row["targets_seen"],
            row["all_targets_prefix"],
            start_index,
        )
    if len(combinations) != EXPECTED_ROWS:
        raise ArtifactValidationError("attempt grid is incomplete")


def write_compressed_attempts(
    output_path: Path,
    raw_files: Sequence[tuple[Path, list[dict[str, str]]]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    first_rows = raw_files[0][1]
    if not first_rows:
        raise ArtifactValidationError("cannot compress an empty worker CSV")
    fieldnames = list(first_rows[0])
    with output_path.open("wb") as binary:
        with gzip.GzipFile(filename="", mode="wb", fileobj=binary, compresslevel=9, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=fieldnames, lineterminator="\n")
                writer.writeheader()
                for _, rows in raw_files:
                    for row in rows:
                        writer.writerow(row)


def instance_ids_for_slice(
    instances: Mapping[str, Mapping[str, Any]],
    slice_kind: str,
    label: str,
) -> set[str]:
    if slice_kind == "overall":
        return set(instances)
    if slice_kind == "family":
        return {key for key, value in instances.items() if value["family_id"] == label}
    if slice_kind == "stratum":
        return {key for key, value in instances.items() if label in value["strata"]}
    raise ValueError(f"unknown slice kind {slice_kind!r}")


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
        raise ArtifactValidationError("metric slice has an incomplete prefix")
    accepted = sum(bool(row["accepted"]) for row in selected)
    full = sum(bool(row["all_targets_prefix"]) for row in checkpoints)
    residual_non_gold = sum(bool(row["false_candidate"]) for row in selected)
    unsafe = sum(
        bool(row["accepted"] and (not row["canonical_valid"] or not row["gold_matched"]))
        for row in selected
    )
    charged_work = sum(
        row["callback_residual_calls"] + row["validation_residual_calls"] for row in selected
    )
    callback_work = sum(row["callback_residual_calls"] for row in selected)
    wall = sum(row["wall_seconds"] for row in selected)
    budget_exhaustions = sum(bool(row["budget_exhausted"]) for row in selected)
    budget_overruns = sum(bool(row["budget_exceeded"]) for row in selected)
    exceptions = sum(row["exception"] is not None for row in selected)
    nonbudget_exceptions = sum(
        row["exception"] is not None and not row["budget_exhausted"] for row in selected
    )
    return {
        "variant": variant,
        "prefix": prefix,
        "slice_kind": slice_kind,
        "slice": label,
        "instance_count": len(instance_ids),
        "attempt_count": len(selected),
        "p_local_gold": accepted / len(selected),
        "p_full_target": full / len(checkpoints),
        "residual_qualified_non_gold_count": residual_non_gold,
        "residual_qualified_non_gold_rate": residual_non_gold / len(selected),
        "unsafe_accepted_count": unsafe,
        "callback_work": callback_work,
        "charged_work": charged_work,
        "mean_charged_work": charged_work / len(selected),
        "wall_seconds": wall,
        "mean_wall_seconds": wall / len(selected),
        "budget_exhaustion_count": budget_exhaustions,
        "budget_overrun_count": budget_overruns,
        "exception_count": exceptions,
        "nonbudget_exception_count": nonbudget_exceptions,
    }


def aggregate_metrics(
    rows: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    slices: list[tuple[str, str, set[str]]] = [
        ("overall", "overall", set(instances)),
    ]
    families = sorted({record["family_id"] for record in instances.values()})
    slices.extend(
        ("family", family, instance_ids_for_slice(instances, "family", family))
        for family in families
    )
    slices.extend(
        ("stratum", stratum, instance_ids_for_slice(instances, "stratum", stratum))
        for stratum in STRATA
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
        for prefix in PREFIXES
        for variant in VARIANTS
        for slice_kind, label, instance_ids in slices
    ]


def rows_by_pair(
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


def validate_pair_maps(
    candidate: Mapping[tuple[str, int], Mapping[str, Any]],
    control: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    if set(candidate) != set(control):
        raise ArtifactValidationError("paired variants have different observation keys")
    for key in candidate:
        left = candidate[key]
        right = control[key]
        for field in ("family_id", "instance_id", "start_index", "starts_checksum", "replay_checksum", "start"):
            if left[field] != right[field]:
                raise ArtifactValidationError(f"paired field {field} drift at {key!r}")


def paired_values_for_metric(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate_variant: str,
    control_variant: str,
    metric: str,
    prefix: int,
    instance_ids: set[str],
) -> tuple[list[PairedValue], list[str]]:
    candidate = rows_by_pair(rows, candidate_variant, instance_ids, prefix)
    control = rows_by_pair(rows, control_variant, instance_ids, prefix)
    validate_pair_maps(candidate, control)
    evidence: list[str] = []
    values: list[PairedValue] = []

    if metric in ("p_local_gold", "bad_residual_reduction"):
        for key in sorted(candidate):
            left = candidate[key]
            right = control[key]
            if metric == "p_local_gold":
                candidate_value = float(left["accepted"])
                control_value = float(right["accepted"])
            else:
                candidate_value = -float(left["false_candidate"])
                control_value = -float(right["false_candidate"])
            pair_id = f"{key[0]}:start={key[1]}"
            values.append(PairedValue(left["family_id"], pair_id, candidate_value, control_value))
            evidence.append(
                "|".join(
                    (
                        left["family_id"],
                        pair_id,
                        left["replay_checksum"],
                        left["starts_checksum"],
                        left["start"],
                    )
                )
            )
    elif metric == "p_full_target":
        for key in sorted(candidate):
            if key[1] != prefix:
                continue
            left = candidate[key]
            right = control[key]
            pair_id = f"{key[0]}:prefix={prefix}"
            values.append(
                PairedValue(
                    left["family_id"],
                    pair_id,
                    float(left["all_targets_prefix"]),
                    float(right["all_targets_prefix"]),
                )
            )
            evidence.append(
                "|".join(
                    (
                        left["family_id"],
                        pair_id,
                        left["replay_checksum"],
                        left["starts_checksum"],
                    )
                )
            )
    elif metric in ("relative_work_saving", "relative_wall_saving"):
        families = sorted({row["family_id"] for row in candidate.values()})
        for family in families:
            left_rows = [row for row in candidate.values() if row["family_id"] == family]
            right_rows = [row for row in control.values() if row["family_id"] == family]
            if metric == "relative_work_saving":
                left_total = sum(
                    row["callback_residual_calls"] + row["validation_residual_calls"]
                    for row in left_rows
                )
                right_total = sum(
                    row["callback_residual_calls"] + row["validation_residual_calls"]
                    for row in right_rows
                )
            else:
                left_total = sum(row["wall_seconds"] for row in left_rows)
                right_total = sum(row["wall_seconds"] for row in right_rows)
            saving = 1.0 - left_total / right_total
            values.append(PairedValue(family, "family-aggregate", saving, 0.0))
            for row in left_rows:
                evidence.append(
                    "|".join(
                        (
                            family,
                            row["instance_id"],
                            str(row["start_index"]),
                            row["replay_checksum"],
                            row["starts_checksum"],
                        )
                    )
                )
    else:
        raise ValueError(f"unknown paired metric {metric!r}")
    return values, evidence


def family_effects(values: Sequence[PairedValue]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for value in values:
        grouped.setdefault(value.family_id, []).append(value.candidate - value.control)
    return {family: sum(items) / len(items) for family, items in sorted(grouped.items())}


def paired_interval(
    values: Sequence[PairedValue],
    evidence: Sequence[str],
    plan: Any,
) -> dict[str, Any]:
    lower = family_clustered_paired_bootstrap(values, plan=plan, confidence=0.95)
    reversed_values = [
        PairedValue(value.family_id, value.pair_id, value.control, value.candidate)
        for value in values
    ]
    reverse_lower = family_clustered_paired_bootstrap(
        reversed_values,
        plan=plan,
        confidence=0.95,
    )
    central_lower = family_clustered_paired_bootstrap(values, plan=plan, confidence=0.975)
    reverse_central_lower = family_clustered_paired_bootstrap(
        reversed_values,
        plan=plan,
        confidence=0.975,
    )
    effects = family_effects(values)
    return {
        "estimate": lower.estimate,
        "lower_95": lower.lower_bound,
        "upper_95": -reverse_lower.lower_bound,
        "central_95_lower": central_lower.lower_bound,
        "central_95_upper": -reverse_central_lower.lower_bound,
        "confidence_kind": "one-sided-percentile-gate-plus-central-percentile-display",
        "confidence": 0.95,
        "resamples": lower.resample_count,
        "plan_checksum": lower.plan_checksum,
        "observation_key_checksum": sha256_strings(evidence),
        "pair_count": len(values),
        "family_count": len(effects),
        "inferential": len(effects) >= 2,
        "positive_family_count": sum(value > 0 for value in effects.values()),
        "family_effects": effects,
    }


def paired_reports(
    rows: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comparisons = (
        ("NLS-LM", "LXR-LMQR"),
        ("NLS-TR", "LXR-LMQR"),
        ("NLS-RMN", "LXR-LMQR"),
        ("NLS-TR-STRICT", "LXR-LMQR"),
        ("NLS-RMN", "NLS-TR"),
        ("NLS-TR-STRICT", "NLS-TR"),
    )
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
    overall_metrics = (
        "p_local_gold",
        "p_full_target",
        "bad_residual_reduction",
        "relative_work_saving",
        "relative_wall_saving",
    )
    for prefix in PREFIXES:
        for candidate, control in comparisons:
            for metric in overall_metrics:
                values, evidence = paired_values_for_metric(
                    rows,
                    candidate_variant=candidate,
                    control_variant=control,
                    metric=metric,
                    prefix=prefix,
                    instance_ids=overall_ids,
                )
                report = paired_interval(values, evidence, plan_for(overall_ids))
                report.update(
                    {
                        "candidate": candidate,
                        "control": control,
                        "metric": metric,
                        "effect_direction": (
                            "candidate-minus-control"
                            if metric in ("p_local_gold", "p_full_target")
                            else "positive-is-candidate-improvement"
                        ),
                        "prefix": prefix,
                        "slice_kind": "overall",
                        "slice": "overall",
                    }
                )
                reports.append(report)

    external_vs_control = comparisons[:4]
    for prefix in PREFIXES:
        for stratum in STRATA:
            instance_ids = instance_ids_for_slice(instances, "stratum", stratum)
            for candidate, control in external_vs_control:
                for metric in ("p_local_gold", "p_full_target"):
                    values, evidence = paired_values_for_metric(
                        rows,
                        candidate_variant=candidate,
                        control_variant=control,
                        metric=metric,
                        prefix=prefix,
                        instance_ids=instance_ids,
                    )
                    report = paired_interval(values, evidence, plan_for(instance_ids))
                    report.update(
                        {
                            "candidate": candidate,
                            "control": control,
                            "metric": metric,
                            "effect_direction": "candidate-minus-control",
                            "prefix": prefix,
                            "slice_kind": "stratum",
                            "slice": stratum,
                        }
                    )
                    reports.append(report)

    plans = {
        "schema_version": "family-clustered-bootstrap-plan-set-v1",
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
    matches = [
        item
        for item in aggregates
        if item["variant"] == variant
        and item["prefix"] == prefix
        and item["slice_kind"] == slice_kind
        and item["slice"] == label
    ]
    if len(matches) != 1:
        raise ArtifactValidationError("aggregate lookup is not unique")
    return matches[0]


def find_paired(
    reports: Sequence[Mapping[str, Any]],
    candidate: str,
    control: str,
    metric: str,
    prefix: int = 32,
    slice_kind: str = "overall",
    label: str = "overall",
) -> Mapping[str, Any]:
    matches = [
        item
        for item in reports
        if item["candidate"] == candidate
        and item["control"] == control
        and item["metric"] == metric
        and item["prefix"] == prefix
        and item["slice_kind"] == slice_kind
        and item["slice"] == label
    ]
    if len(matches) != 1:
        raise ArtifactValidationError("paired report lookup is not unique")
    return matches[0]


def mechanical_decisions(
    aggregates: Sequence[Mapping[str, Any]],
    paired: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rmn_local = find_paired(paired, "NLS-RMN", "NLS-TR", "p_local_gold")
    rmn_work = find_paired(paired, "NLS-RMN", "NLS-TR", "relative_work_saving")
    rmn_full = find_paired(paired, "NLS-RMN", "NLS-TR", "p_full_target")
    rmn_kill = (
        rmn_local["upper_95"] <= 0.05
        and rmn_work["upper_95"] <= 0.05
        and rmn_full["estimate"] >= -0.02
    )

    strict_metrics = {
        metric: find_paired(paired, "NLS-TR-STRICT", "NLS-TR", metric)
        for metric in (
            "p_local_gold",
            "p_full_target",
            "bad_residual_reduction",
            "relative_work_saving",
        )
    }
    strict_no_improvement = all(item["upper_95"] <= 0.0 for item in strict_metrics.values())

    tr_local = find_paired(paired, "NLS-TR", "LXR-LMQR", "p_local_gold")
    tr_overall = find_aggregate(aggregates, "NLS-TR", 32)
    lxr_overall = find_aggregate(aggregates, "LXR-LMQR", 32)
    near_tr = find_aggregate(aggregates, "NLS-TR", 32, "family", "NEAR-RANK-DEFICIENT")
    near_lxr = find_aggregate(aggregates, "LXR-LMQR", 32, "family", "NEAR-RANK-DEFICIENT")
    tangent_tr = find_aggregate(aggregates, "NLS-TR", 32, "family", "TANGENT-CIRCLE-LINE")
    tangent_lxr = find_aggregate(aggregates, "LXR-LMQR", 32, "family", "TANGENT-CIRCLE-LINE")
    multi_tr = find_aggregate(aggregates, "NLS-TR", 32, "family", "MULTIROOT-WARPED")
    multi_lxr = find_aggregate(aggregates, "LXR-LMQR", 32, "family", "MULTIROOT-WARPED")

    def family_gain(candidate: Mapping[str, Any], control: Mapping[str, Any]) -> dict[str, float]:
        return {
            "p_local_gold_delta": candidate["p_local_gold"] - control["p_local_gold"],
            "p_full_target_delta": candidate["p_full_target"] - control["p_full_target"],
            "charged_work_saving": 1.0 - candidate["charged_work"] / control["charged_work"],
        }

    near_gain = family_gain(near_tr, near_lxr)
    tangent_gain = family_gain(tangent_tr, tangent_lxr)
    multi_gain = family_gain(multi_tr, multi_lxr)
    tr_development_freeze = (
        tr_local["lower_95"] > 0.0
        and tr_local["positive_family_count"] >= 3
        and (near_gain["p_local_gold_delta"] >= 0.10 or near_gain["charged_work_saving"] >= 0.20)
        and (
            tangent_gain["p_local_gold_delta"] >= 0.10
            or tangent_gain["charged_work_saving"] >= 0.20
        )
        and multi_gain["p_full_target_delta"] >= -0.02
        and tr_overall["unsafe_accepted_count"] == 0
        and lxr_overall["unsafe_accepted_count"] == 0
    )
    return {
        "locked_validation_executed": False,
        "production_dependency_change_allowed": False,
        "rmn_kill_gate": {
            "triggered": rmn_kill,
            "rule": "upper95 recall advantage <=5%, upper95 charged-work saving <=5%, and no >2-point full-target loss",
            "p_local_gold": dict(rmn_local),
            "relative_work_saving": dict(rmn_work),
            "p_full_target": dict(rmn_full),
        },
        "strict_threshold": {
            "no_improvement": strict_no_improvement,
            "freeze_candidate": "NLS-TR" if strict_no_improvement else "NLS-TR-STRICT",
            "rule": "upper95 <=0 for recall, full-target, bad-residual reduction, and charged-work saving",
            "effects": {key: dict(value) for key, value in strict_metrics.items()},
        },
        "next_freeze_candidate": "NLS-TR" if tr_development_freeze else None,
        "development_freeze_gate_passed": tr_development_freeze,
        "promotion_decision": "not-evaluated-development-only",
        "critical_family_effects": {
            "near_rank": near_gain,
            "tangent": tangent_gain,
            "multiroot": multi_gain,
        },
    }


def write_aggregate_csv(path: Path, aggregates: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = list(aggregates[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(aggregates)


def markdown_report(summary: Mapping[str, Any]) -> str:
    aggregates = summary["aggregates"]
    decisions = summary["decisions"]
    lines = [
        "# EXP-LOCAL-002 development result",
        "",
        "Development-only execution: 48 frozen instances × 32 paired starts × five variants. Locked validation and promotion were not performed.",
        "",
        "## Prefix-32 overall",
        "",
        "| Variant | P_local_gold | P_full_target | Residual-qualified non-Gold | Budget exhausted | Charged work | Warm wall (s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        item = find_aggregate(aggregates, variant, 32)
        lines.append(
            f"| {variant} | {item['p_local_gold']:.4f} | {item['p_full_target']:.4f} | "
            f"{item['residual_qualified_non_gold_count']} | {item['budget_exhaustion_count']} | "
            f"{item['charged_work']} | "
            f"{item['wall_seconds']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Mechanical development decisions",
            "",
            f"- RMN kill gate: **{decisions['rmn_kill_gate']['triggered']}**.",
            f"- Strict threshold has no measured advantage: **{decisions['strict_threshold']['no_improvement']}**.",
            f"- Next locked-validation freeze candidate: **{decisions['next_freeze_candidate'] or 'none'}**.",
            "- Promotion/product dependency decision: **not evaluated**.",
            "",
            "## Confidence semantics",
            "",
            "Paired effects use the repository's equal-family-weighted clustered bootstrap. `lower_95` is the preregistered one-sided 95% percentile bound; `upper_95` is the mirrored one-sided bound using the same persisted resample plan. Starts and instances are paired before family averaging; there is no within-family resampling.",
            "",
            "## Cold protocol",
            "",
            "Each variant ran in a separate fresh Julia process. The process measured package/module load, then one identical ScaleLadder cold solve, then one unmeasured warm-up per family before all 1,536 measured attempts. The full harness is identical across variants; therefore the LXR cold number conservatively includes loading the research environment containing NonlinearSolve.",
            "",
            "Raw attempts are stored as deterministic-header `attempts.csv.gz`; input, start, replay, worker, bootstrap-plan, and result checksums are persisted alongside this report.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_final_artifacts(output_directory: Path, input_manifest_path: Path = INPUT_MANIFEST) -> None:
    required = (
        "attempts.csv.gz",
        "aggregates.csv",
        "bootstrap-plans.json.gz",
        "paired-bootstrap.json",
        "environment.json",
        "summary.json",
        "development-report.md",
        "cold.csv",
    )
    for name in required:
        if not (output_directory / name).is_file():
            raise ArtifactValidationError(f"missing final artifact {name}")
    manifest = load_json(input_manifest_path)
    instances = validate_input_manifest(manifest)
    with gzip.open(output_directory / "attempts.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        rows = [parse_row(row) for row in csv.DictReader(stream)]
    validate_attempt_rows(rows, instances)
    summary = load_json(output_directory / "summary.json")
    if summary.get("status") != "development-complete-locked-pending":
        raise ArtifactValidationError("summary status is not development-only")
    environment = load_json(output_directory / "environment.json")
    checksums = environment.get("checksums", {})
    if checksums.get("attempts_csv_gz_sha256") != sha256_file(output_directory / "attempts.csv.gz"):
        raise ArtifactValidationError("compressed attempt checksum mismatch")
    if checksums.get("input_manifest_sha256") != sha256_file(input_manifest_path):
        raise ArtifactValidationError("final input manifest checksum mismatch")
    artifact_checks = {
        "aggregates_csv_sha256": "aggregates.csv",
        "paired_bootstrap_sha256": "paired-bootstrap.json",
        "bootstrap_plans_gz_sha256": "bootstrap-plans.json.gz",
    }
    for checksum_key, filename in artifact_checks.items():
        if checksums.get(checksum_key) != sha256_file(output_directory / filename):
            raise ArtifactValidationError(f"final checksum mismatch for {filename}")
    if summary.get("attempt_count") != len(rows):
        raise ArtifactValidationError("summary attempt count does not match raw attempts")
    if summary.get("unsafe_accepted_count") != 0:
        raise ArtifactValidationError("summary reports an unsafe accepted endpoint")
    if summary.get("budget_overrun_count") != 0:
        raise ArtifactValidationError("summary reports an actual budget overrun")
    if summary.get("nonbudget_exception_count") != 0:
        raise ArtifactValidationError("summary reports a non-budget adapter exception")
    plan_set = load_json_gzip(output_directory / "bootstrap-plans.json.gz")
    for raw in plan_set.get("plans", {}).values():
        plan = BootstrapPlan(
            version=raw["version"],
            seed=raw["seed"],
            family_order=tuple(raw["family_order"]),
            resample_indices=tuple(tuple(row) for row in raw["resample_indices"]),
            checksum=raw["checksum"],
        )
        validate_bootstrap_plan(plan)


def analyze_worker_outputs(
    work_directory: Path,
    output_directory: Path,
    *,
    orchestrator_seconds: float,
) -> dict[str, Any]:
    manifest = load_json(INPUT_MANIFEST)
    instances = validate_input_manifest(manifest)
    rows, worker_metadata, raw_files = load_worker_outputs(work_directory, INPUT_MANIFEST)
    validate_attempt_rows(rows, instances)
    output_directory.mkdir(parents=True, exist_ok=True)

    attempts_path = output_directory / "attempts.csv.gz"
    write_compressed_attempts(attempts_path, raw_files)
    aggregates = aggregate_metrics(rows, instances)
    write_aggregate_csv(output_directory / "aggregates.csv", aggregates)
    paired, plans = paired_reports(rows, instances)
    write_json(output_directory / "paired-bootstrap.json", paired)
    write_json_gzip(output_directory / "bootstrap-plans.json.gz", plans)
    decisions = mechanical_decisions(aggregates, paired)

    with (output_directory / "cold.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = (
            "variant",
            "package_load_compile_seconds",
            "cold_probe_solve_seconds",
            "cold_total_seconds",
            "cold_probe_callback_residual_calls",
            "warmup_seconds",
            "measured_attempt_seconds",
            "worker_seconds",
        )
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(worker_metadata)

    environment = {
        "schema_version": "exp-local-002-development-environment-v1",
        "experiment_id": "EXP-LOCAL-002",
        "partition": "development",
        "locked_validation": False,
        "orchestrator_seconds": orchestrator_seconds,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "worker_metadata": worker_metadata,
        "cold_protocol": {
            "fresh_process_per_variant": True,
            "cold_probe_instance": manifest["instances"][0]["instance_id"],
            "cold_probe_start": 1,
            "warmup": "one start from one instance per family, excluded from measured attempts",
            "measured_attempts_are_warm": True,
            "limitation": "the common research harness imported the pinned environment for all variants",
        },
        "checksums": {
            "input_manifest_sha256": sha256_file(INPUT_MANIFEST),
            "attempts_csv_gz_sha256": sha256_file(attempts_path),
            "aggregates_csv_sha256": sha256_file(output_directory / "aggregates.csv"),
            "paired_bootstrap_sha256": sha256_file(output_directory / "paired-bootstrap.json"),
            "bootstrap_plans_gz_sha256": sha256_file(
                output_directory / "bootstrap-plans.json.gz"
            ),
            "analysis_source_sha256": sha256_file(Path(__file__)),
            "development_julia_source_sha256": sha256_file(
                EXPERIMENT_ROOT / "src" / "DevelopmentLocal002.jl"
            ),
            "base_runner_source_sha256": sha256_file(
                EXPERIMENT_ROOT / "src" / "ExperimentLocal002.jl"
            ),
            "project_sha256": sha256_file(EXPERIMENT_ROOT / "Project.toml"),
            "manifest_sha256": sha256_file(EXPERIMENT_ROOT / "Manifest.toml"),
            "experiment_card_sha256": sha256_file(
                REPO_ROOT / "research" / "experiments" / "EXP-LOCAL-002.json"
            ),
        },
    }
    write_json(output_directory / "environment.json", environment)
    summary = {
        "schema_version": "exp-local-002-development-summary-v1",
        "experiment_id": "EXP-LOCAL-002",
        "status": "development-complete-locked-pending",
        "instance_count": EXPECTED_INSTANCES,
        "starts_per_instance": EXPECTED_STARTS,
        "attempt_count": len(rows),
        "prefixes": list(PREFIXES),
        "variants": list(VARIANTS),
        "aggregates": aggregates,
        "decisions": decisions,
        "unsafe_accepted_count": sum(
            row["accepted"] and (not row["canonical_valid"] or not row["gold_matched"])
            for row in rows
        ),
        "budget_overrun_count": sum(row["budget_exceeded"] for row in rows),
        "budget_exhaustion_count": sum(row["budget_exhausted"] for row in rows),
        "exception_count": sum(row["exception"] is not None for row in rows),
        "nonbudget_exception_count": sum(
            row["exception"] is not None and not row["budget_exhausted"] for row in rows
        ),
        "promotion_decision": "not-evaluated-development-only",
    }
    write_json(output_directory / "summary.json", summary)
    (output_directory / "development-report.md").write_text(
        markdown_report(summary),
        encoding="utf-8",
        newline="\n",
    )
    validate_final_artifacts(output_directory)
    return summary


def run_worker(
    julia: str,
    variant: str,
    work_directory: Path,
) -> None:
    command = [
        julia,
        f"--project={EXPERIMENT_ROOT}",
        str(WORKER_ENTRYPOINT),
        "--variant",
        variant,
        "--out",
        str(work_directory),
        "--input-manifest",
        str(INPUT_MANIFEST),
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def orchestrate(
    *,
    julia: str,
    output_directory: Path,
    resume: bool,
    force: bool,
) -> dict[str, Any]:
    manifest = load_json(INPUT_MANIFEST)
    validate_input_manifest(manifest)
    if output_directory.exists() and not force and not (output_directory / ".work").is_dir():
        raise FileExistsError(f"output already exists: {output_directory}; pass --force to replace")
    if output_directory.exists() and force:
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    work_directory = output_directory / ".work"
    work_directory.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    for variant in VARIANTS:
        slug = worker_slug(variant)
        existing = (work_directory / f"worker-{slug}.csv").is_file() and (
            work_directory / f"worker-{slug}.json"
        ).is_file()
        if resume and existing:
            print(f"reusing completed fresh worker {variant}", flush=True)
            continue
        print(f"starting fresh worker {variant}", flush=True)
        run_worker(julia, variant, work_directory)
    elapsed = time.perf_counter() - start
    summary = analyze_worker_outputs(
        work_directory,
        output_directory,
        orchestrator_seconds=elapsed,
    )
    shutil.rmtree(work_directory)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--julia", default=os.environ.get("JULIA", "julia"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    output = args.out.resolve()
    if args.validate_only:
        validate_final_artifacts(output)
        print(f"validated development artifacts at {output}")
        return 0
    summary = orchestrate(
        julia=args.julia,
        output_directory=output,
        resume=args.resume,
        force=args.force,
    )
    print(f"completed {summary['attempt_count']} attempts at {output}")
    print(json.dumps(summary["decisions"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
