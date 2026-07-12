#!/usr/bin/env python3
"""Independently aggregate EXP-LOCAL-014 case shards from raw attempts."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[3]
EXP010 = ROOT / "research" / "experiments" / "EXP-LOCAL-010"
sys.path.insert(0, str(EXP010))
from aggregate_t0 import (  # noqa: E402
    _first_crossings,
    _reported_unsafe,
    _safe_full,
    _same_safe_target,
    _suffix_work,
    _targets,
    _unsafe,
)


SHARD_SCHEMA = "geotarget.local-successor-campaign/v1"
CALLBACK_CAP = 600
CALLBACK_THRESHOLDS = (600, 1_200, 2_400, 4_800)
CASE_WORK_CAP = 4_800
PRIMARY_CONTROL = "prod-tol-120x600"
WORK_COMPARATOR = "E1-FD2-CPQR3"
E3 = "E3-FD2-GUARD-CHART-CPQR3"
E4 = "E4-EXP-GUARD-SLACK-CPQR"
NEAR_RANK = "NEAR-RANK-DEFICIENT"
STRICT_GUARD = "STRICT-GUARD-BOUNDARY"
CRITICAL_FAMILIES = (
    "MULTIROOT-WARPED",
    NEAR_RANK,
    STRICT_GUARD,
    "TANGENT-CIRCLE-LINE",
)


@dataclass(frozen=True)
class StageSpec:
    stage: str
    expected_cases: tuple[dict[str, Any], ...]
    variants: tuple[str, ...]
    candidate_shadow_pairs: tuple[tuple[str, str], ...]
    maximum_starts: int
    registration_sha256: str
    frozen_inputs: dict[str, str]
    strict_target_requirement: int | None = None
    near_rank_shadow_unsafe_minimum: int = 0
    support_family_minimum: int = 0
    recall_delta_minimum: float = -0.01
    work_ratio_maximum: float = 1.2
    critical_family_recall_delta_minimum: float = -0.02
    preoutcome_evidence_ok: bool = True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_frozen_inputs(frozen_inputs: dict[str, str]) -> None:
    for relative, expected in frozen_inputs.items():
        path = ROOT.joinpath(*relative.split("/"))
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"frozen input drifted: {relative}")


def _expected_t2_cases(indices: Sequence[int]) -> tuple[dict[str, Any], ...]:
    path = ROOT / "research" / "experiments" / "EXP-LOCAL-004" / "t2-input-manifest.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    result: list[dict[str, Any]] = []
    for local_index, source_index in enumerate(indices, start=1):
        instance = document["instances"][source_index - 1]
        result.append(
            {
                "family_id": instance["family_id"],
                "instance_id": instance["instance_id"],
                "local_case_index": local_index,
                "replay_checksum": instance["replay_checksum"],
                "saved_starts_checksum": instance["saved_starts_checksum"],
                "saved_starts_shape": instance["saved_starts_shape"],
                "source_case_index": source_index,
                "targets": int(instance["target_count"]),
            }
        )
    return tuple(result)


def _expected_r1_cases(registration: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "family_id": instance["family_id"],
            "instance_id": instance["instance_id"],
            "local_case_index": index,
            "replay_checksum": instance["replay_checksum"],
            "saved_starts_checksum": instance["saved_starts_checksum"],
            "saved_starts_shape": instance["saved_starts_shape"],
            "source_case_index": index,
            "targets": int(instance["target_count"]),
        }
        for index, instance in enumerate(registration["stages"]["r1"]["instances"], start=1)
    )


def load_stage_spec(
    stage: str,
    registration_path: Path | None = None,
) -> StageSpec:
    registration_path = registration_path or Path(__file__).with_name("preregistration.json")
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    expected_runtime = registration["runtime_versions"]
    if platform.python_version() != expected_runtime["python"]:
        raise ValueError("Python version differs from preregistration")
    uv_version = subprocess.check_output(["uv", "--version"], text=True).split()[1]
    if uv_version != expected_runtime["uv"]:
        raise ValueError("uv version differs from preregistration")
    if registration["active_stage"] != stage:
        raise ValueError(f"{stage} is not the active preregistered stage")
    active = tuple(str(value) for value in registration["active_candidates"])
    pairs_by_name = registration["variants"]["candidate_pairs"]
    pairs = tuple((candidate, str(pairs_by_name[candidate])) for candidate in active)
    variants = (PRIMARY_CONTROL, WORK_COMPARATOR, *(name for pair in pairs for name in pair))
    stage_card = registration["stages"][stage]
    if stage == "g0":
        indices = tuple(int(value) for value in stage_card["source_case_indices"])
        cases = _expected_t2_cases(indices)
        strict_requirement = int(stage_card["strict_guard_target_count"])
        near_minimum = int(
            registration["g0_promotion_gates"]["near_rank_shadow_unsafe_minimum"]
        )
        support_minimum = 0
    elif stage == "r1":
        cases = _expected_r1_cases(registration)
        strict_requirement = None
        near_minimum = 0
        support_minimum = int(
            registration["r1_promotion_gates"][
                "minimum_unrelated_active_families_for_uniform_mechanism"
            ]
        )
    elif stage == "t2":
        cases = _expected_t2_cases(tuple(range(1, 49)))
        strict_requirement = sum(
            int(case["targets"]) for case in cases if case["family_id"] == STRICT_GUARD
        )
        near_minimum = 0
        support_minimum = 0
    else:
        raise ValueError("stage must be g0, r1, or t2")
    if len(cases) != int(stage_card["case_count"]):
        raise ValueError("preregistered stage case count does not match its corpus")
    frozen_inputs = {
        str(key): str(value) for key, value in registration["frozen_inputs"].items()
    }
    _validate_frozen_inputs(frozen_inputs)
    evidence_path = ROOT / "research" / "experiments" / "EXP-LOCAL-014" / "preoutcome-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_ok = (
        evidence.get("status") == "passed"
        and evidence.get("outcome_observed") is False
        and int(evidence.get("independent_static_audit_blockers", -1)) == 0
        and set(evidence.get("candidates", [])) == set(active)
    )
    comparison = registration["comparison_gates"]
    return StageSpec(
        stage=stage,
        expected_cases=cases,
        variants=variants,
        candidate_shadow_pairs=pairs,
        maximum_starts=int(stage_card["maximum_starts"]),
        registration_sha256=_sha256(registration_path),
        frozen_inputs=frozen_inputs,
        strict_target_requirement=strict_requirement,
        near_rank_shadow_unsafe_minimum=near_minimum,
        support_family_minimum=support_minimum,
        recall_delta_minimum=float(
            comparison["target_recall_delta_vs_primary_control_minimum"]
        ),
        work_ratio_maximum=float(
            comparison["right_censored_work_ratio_vs_e1_maximum"]
        ),
        critical_family_recall_delta_minimum=float(
            comparison["critical_family_target_recall_delta_minimum"]
        ),
        preoutcome_evidence_ok=evidence_ok,
    )


def _normalized_diagnostic(value: Any) -> tuple[tuple[str, str], ...]:
    fields: dict[str, str] = {}
    for entry in str(value or "").split(";"):
        key, separator, item = entry.partition("=")
        if separator and key != "shadow":
            fields[key] = item
    return tuple(sorted(fields.items()))


def _expected_snapshots(
    attempts: list[dict[str, Any]],
    target_count: int,
    *,
    variant: str,
    instance: str,
    family: str,
) -> list[dict[str, Any]]:
    rows = _first_crossings(attempts, target_count)
    for row in rows:
        row.update(variant=variant, instance_id=instance, family_id=family)
    return rows


def _snapshot_mismatches(
    observed: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> int:
    if len(observed) != len(expected):
        return 1
    fields = (
        "assessor_qualified",
        "assessor_safe_full",
        "assessor_target_recall",
        "assessor_targets_found",
        "assessor_unsafe",
        "callback_threshold",
        "crossing_callback_work",
        "crossing_start_index",
        "family_id",
        "instance_id",
        "variant",
    )
    return sum(
        any(left.get(field) != right.get(field) for field in fields)
        for left, right in zip(
            sorted(observed, key=lambda row: int(row["callback_threshold"])),
            expected,
            strict=True,
        )
    )


def _load_documents(paths: Sequence[Path], spec: StageSpec) -> tuple[list[dict[str, Any]], str]:
    if len(paths) != len(spec.expected_cases):
        raise ValueError(f"expected {len(spec.expected_cases)} shards, got {len(paths)}")
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    indices = [int(document["case_index"]) for document in documents]
    if sorted(indices) != list(range(1, len(spec.expected_cases) + 1)):
        raise ValueError("case indices are missing or duplicated")
    revisions = {str(document["revision"]["git_head"]) for document in documents}
    if len(revisions) != 1 or any(document["revision"]["git_dirty"] for document in documents):
        raise ValueError("all shards must come from one clean revision")
    for document in documents:
        index = int(document["case_index"])
        expected = spec.expected_cases[index - 1]
        if document.get("schema") != SHARD_SCHEMA or document.get("stage") != spec.stage:
            raise ValueError("unexpected shard schema or stage")
        if int(document.get("case_count", 0)) != len(spec.expected_cases):
            raise ValueError("shard case_count mismatch")
        if int(document.get("maximum_starts", 0)) != spec.maximum_starts:
            raise ValueError("shard maximum_starts mismatch")
        if document.get("callback_thresholds") != list(CALLBACK_THRESHOLDS):
            raise ValueError("callback thresholds mismatch")
        if int(document.get("case_callback_stop", 0)) != CASE_WORK_CAP:
            raise ValueError("case callback stop mismatch")
        names = tuple(row["name"] for row in document["variant_manifest"])
        if names != spec.variants:
            raise ValueError("ordered variant manifest mismatch")
        if len(document["problem_manifest"]) != 1:
            raise ValueError("each shard must contain one problem manifest")
        observed = document["problem_manifest"][0]
        for field, value in expected.items():
            if observed.get(field) != value:
                raise ValueError(f"case {index} problem manifest mismatch: {field}")
        authorization = document.get("authorization", {})
        if authorization.get("registration_sha256") != spec.registration_sha256:
            raise ValueError("shard registration hash mismatch")
        if authorization.get("frozen_inputs") != spec.frozen_inputs:
            raise ValueError("shard frozen input map mismatch")
        host = document.get("host_execution", {})
        expected_cpu = (index - 1) % 16
        if (
            int(host.get("assigned_cpu", -1)) != expected_cpu
            or host.get("cpus_allowed_list") != str(expected_cpu)
            or int(host.get("case_process_limit", 0)) != 16
            or int(host.get("solver_worker_count", 0)) != 1
        ):
            raise ValueError("host affinity/concurrency contract mismatch")
        environment = document.get("environment", {})
        if any(
            int(environment.get(name, 0)) != 1
            for name in ("julia_threads", "blas_threads")
        ) or any(
            environment.get(name) != "1"
            for name in ("openblas_num_threads", "omp_num_threads", "mkl_num_threads")
        ):
            raise ValueError("thread contract mismatch")
    return documents, revisions.pop()


def aggregate(paths: Sequence[Path], spec: StageSpec) -> dict[str, Any]:
    documents, revision = _load_documents(paths, spec)
    attempts_by_stream: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    terminals: dict[tuple[str, str], dict[str, Any]] = {}
    snapshots: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    target_counts: dict[str, int] = {}
    families: dict[str, str] = {}
    for document in documents:
        problem = document["problem_manifest"][0]
        instance = str(problem["instance_id"])
        target_counts[instance] = int(problem["targets"])
        families[instance] = str(problem["family_id"])
        for attempt in document["attempts"]:
            if attempt["instance_id"] != instance:
                raise ValueError("attempt belongs to the wrong shard")
            attempts_by_stream[(str(attempt["variant"]), instance)].append(attempt)
        for terminal in document["terminals"]:
            key = (str(terminal["variant"]), instance)
            if key in terminals:
                raise ValueError("duplicate terminal")
            terminals[key] = terminal
        for snapshot in document["threshold_snapshots"]:
            snapshots[(str(snapshot["variant"]), instance)].append(snapshot)
    expected_streams = {
        (variant, instance) for variant in spec.variants for instance in target_counts
    }
    if set(attempts_by_stream) != expected_streams or set(terminals) != expected_streams:
        raise ValueError("missing or extra variant/case stream")

    accounting = {
        "attempt_callback_cap_violations": 0,
        "evaluation_count_mismatches": 0,
        "exceptions": 0,
        "runner_budget_exhausted": 0,
        "stream_stop_violations": 0,
        "terminal_mismatches": 0,
        "threshold_snapshot_mismatches": 0,
    }
    reported_unsafe = {variant: 0 for variant in spec.variants}
    stream_metrics: dict[tuple[str, str], dict[str, Any]] = {}
    for key, attempts in attempts_by_stream.items():
        attempts.sort(key=lambda row: int(row["start_index"]))
        if [int(row["start_index"]) for row in attempts] != list(range(1, len(attempts) + 1)):
            raise ValueError(f"non-contiguous starts for {key}")
        for attempt in attempts:
            observed = int(attempt["observed_evaluations"])
            reported = int(attempt["reported_evaluations"])
            accounting["attempt_callback_cap_violations"] += observed > CALLBACK_CAP
            accounting["evaluation_count_mismatches"] += (
                observed != reported or bool(attempt["evaluation_count_mismatch"])
            )
            accounting["exceptions"] += attempt.get("exception") is not None
            accounting["runner_budget_exhausted"] += bool(attempt["budget_exhausted"])
            reported_unsafe[key[0]] += _reported_unsafe(attempt)
        work = sum(int(row["observed_evaluations"]) for row in attempts)
        prior_work = sum(int(row["observed_evaluations"]) for row in attempts[:-1])
        accounting["stream_stop_violations"] += (
            not attempts
            or prior_work >= CASE_WORK_CAP
            or (len(attempts) < spec.maximum_starts and work < CASE_WORK_CAP)
            or len(attempts) > spec.maximum_starts
        )
        instance = key[1]
        target_count = target_counts[instance]
        suffix = _suffix_work(attempts, target_count)
        censored = suffix if suffix is not None and suffix <= CASE_WORK_CAP else CASE_WORK_CAP
        expected_rows = _expected_snapshots(
            attempts,
            target_count,
            variant=key[0],
            instance=instance,
            family=families[instance],
        )
        accounting["threshold_snapshot_mismatches"] += _snapshot_mismatches(
            snapshots.get(key, []), expected_rows
        )
        terminal = terminals[key]
        accounting["terminal_mismatches"] += any(
            (
                int(terminal["attempt_count"]) != len(attempts),
                int(terminal["callback_work"]) != work,
                terminal.get("suffix_stable_work") != suffix,
                int(terminal["right_censored_suffix_stable_work"]) != censored,
            )
        )
        stream_metrics[key] = {
            "family_id": families[instance],
            "right_censored_work": censored,
            "safe_full": _safe_full(attempts, target_count),
            "target_count": target_count,
            "targets": sorted(_targets(attempts)),
            "unsafe": sum(_unsafe(row) for row in attempts),
        }

    variant_metrics: dict[str, dict[str, Any]] = {}
    family_metrics: dict[str, dict[str, Any]] = {}
    for variant in spec.variants:
        rows = [stream_metrics[(variant, instance)] for instance in sorted(target_counts)]
        found = sum(len(row["targets"]) for row in rows)
        total = sum(int(row["target_count"]) for row in rows)
        variant_metrics[variant] = {
            "assessor_safe_full_cases": sum(bool(row["safe_full"]) for row in rows),
            "assessor_target_count": total,
            "assessor_targets_found": found,
            "assessor_target_recall": found / total,
            "assessor_unsafe": sum(int(row["unsafe"]) for row in rows),
            "reported_unsafe": reported_unsafe[variant],
            "right_censored_callback_work": sum(
                int(row["right_censored_work"]) for row in rows
            ),
        }
        family_metrics[variant] = {}
        for family in sorted(set(families.values())):
            selected = [row for row in rows if row["family_id"] == family]
            family_found = sum(len(row["targets"]) for row in selected)
            family_total = sum(int(row["target_count"]) for row in selected)
            safe_cases = sum(bool(row["safe_full"]) for row in selected)
            family_metrics[variant][family] = {
                "case_count": len(selected),
                "safe_full_cases": safe_cases,
                "safe_full_rate": safe_cases / len(selected),
                "target_count": family_total,
                "targets_found": family_found,
                "target_recall": family_found / family_total,
                "unsafe": sum(int(row["unsafe"]) for row in selected),
            }
        variant_metrics[variant]["mean_family_safe_full_rate"] = sum(
            row["safe_full_rate"] for row in family_metrics[variant].values()
        ) / len(family_metrics[variant])

    pair_metrics: dict[str, dict[str, Any]] = {}
    primary = variant_metrics[PRIMARY_CONTROL]
    comparator = variant_metrics[WORK_COMPARATOR]
    for candidate, shadow in spec.candidate_shadow_pairs:
        callback_mismatches = 0
        trajectory_mismatches = 0
        support_families: set[str] = set()
        for instance in sorted(target_counts):
            left_rows = attempts_by_stream[(candidate, instance)]
            right_rows = attempts_by_stream[(shadow, instance)]
            if len(left_rows) != len(right_rows):
                callback_mismatches += 1
                trajectory_mismatches += 1
                continue
            for left, right in zip(left_rows, right_rows, strict=True):
                callback_mismatches += any(
                    (
                        left["start_index"] != right["start_index"],
                        left["start"] != right["start"],
                        left["observed_evaluations"] != right["observed_evaluations"],
                        left["reported_evaluations"] != right["reported_evaluations"],
                    )
                )
                trajectory_mismatches += any(
                    (
                        left["iterations"] != right["iterations"],
                        _normalized_diagnostic(left.get("diagnostic"))
                        != _normalized_diagnostic(right.get("diagnostic")),
                    )
                )
                changed = left.get("endpoint") != right.get("endpoint")
                safely_active = changed and (
                    (_unsafe(right) and not _unsafe(left) and left.get("endpoint") is None)
                    or _same_safe_target(left, right)
                )
                safely_active and support_families.add(families[instance])
        metrics = variant_metrics[candidate]
        strict_found = family_metrics[candidate].get(STRICT_GUARD, {}).get("targets_found", 0)
        near_candidate_unsafe = family_metrics[candidate].get(NEAR_RANK, {}).get("unsafe", 0)
        near_shadow_unsafe = family_metrics[shadow].get(NEAR_RANK, {}).get("unsafe", 0)
        gates = {
            "accounting": not any(accounting.values()),
            "preoutcome_evidence": spec.preoutcome_evidence_ok,
            "candidate_shadow_callback_identity": callback_mismatches == 0,
            "candidate_shadow_trajectory_identity": trajectory_mismatches == 0,
            "candidate_assessor_safe": metrics["assessor_unsafe"] == 0,
            "candidate_reported_safe": metrics["reported_unsafe"] == 0,
            "near_rank_candidate_safe": near_candidate_unsafe == 0,
            "near_rank_shadow_unsafe_minimum": (
                near_shadow_unsafe >= spec.near_rank_shadow_unsafe_minimum
            ),
            "strict_target_requirement": (
                spec.strict_target_requirement is None
                or strict_found == spec.strict_target_requirement
            ),
            "safe_full_noninferior_to_primary": (
                metrics["assessor_safe_full_cases"]
                >= primary["assessor_safe_full_cases"]
            ),
            "target_recall_delta": (
                metrics["assessor_target_recall"] - primary["assessor_target_recall"]
                >= spec.recall_delta_minimum
            ),
            "work_ratio_vs_e1": (
                metrics["right_censored_callback_work"]
                <= spec.work_ratio_maximum * comparator["right_censored_callback_work"]
            ),
            "critical_family_recall_noninferior": all(
                family not in family_metrics[candidate]
                or family_metrics[candidate][family]["target_recall"]
                - family_metrics[PRIMARY_CONTROL][family]["target_recall"]
                >= spec.critical_family_recall_delta_minimum
                for family in CRITICAL_FAMILIES
            ),
            "support_family_minimum": len(support_families) >= spec.support_family_minimum,
        }
        pair_metrics[candidate] = {
            "callback_mismatches": callback_mismatches,
            "gates": gates,
            "near_rank_candidate_unsafe": near_candidate_unsafe,
            "near_rank_shadow_unsafe": near_shadow_unsafe,
            "passes_stage": all(gates.values()),
            "right_censored_work_ratio_vs_e1": (
                metrics["right_censored_callback_work"]
                / comparator["right_censored_callback_work"]
            ),
            "strict_targets_found": strict_found,
            "support_families": sorted(support_families),
            "trajectory_mismatches": trajectory_mismatches,
        }

    survivors = [
        candidate for candidate, _ in spec.candidate_shadow_pairs
        if pair_metrics[candidate]["passes_stage"]
    ]
    selected_finalist = None
    if spec.stage == "r1" and survivors:
        selected_finalist = max(
            survivors,
            key=lambda candidate: (
                variant_metrics[candidate]["mean_family_safe_full_rate"],
                variant_metrics[candidate]["assessor_target_recall"],
                -variant_metrics[candidate]["right_censored_callback_work"],
                len(pair_metrics[candidate]["support_families"]),
                candidate == E3,
            ),
        )
    ordered_hashes = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in sorted(paths, key=lambda path: int(json.loads(path.read_text())["case_index"]))
    ]
    return {
        "accounting": accounting,
        "aggregator_environment": {"python": platform.python_version()},
        "freeze_provenance": {
            "frozen_inputs": spec.frozen_inputs,
            "registration_sha256": spec.registration_sha256,
        },
        "candidate_gates": pair_metrics,
        "family_metrics": family_metrics,
        "input_schema": SHARD_SCHEMA,
        "ordered_shard_hashes": ordered_hashes,
        "revision": revision,
        "schema": "geotarget.local-successor-aggregate/v1",
        "selected_finalist": selected_finalist,
        "stage": spec.stage,
        "survivors": survivors,
        "variant_metrics": variant_metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("g0", "r1", "t2"))
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("shards", nargs="+", type=Path)
    args = parser.parse_args()
    result = aggregate(args.shards, load_stage_spec(args.stage, args.registration))
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
