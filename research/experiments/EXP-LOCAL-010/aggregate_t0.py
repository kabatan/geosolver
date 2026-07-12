#!/usr/bin/env python3
"""Independently aggregate frozen local-correction campaign shards."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


CONTROL = "prod-tol-120x600"
CANDIDATE_SHADOW = {
    "E1-FD2-CPQR3": "E1-FD2-CPQR3-SHADOW",
    "E2-FD2-SVD3": "E2-FD2-SVD3-SHADOW",
}
VARIANTS = (CONTROL, *[name for pair in CANDIDATE_SHADOW.items() for name in pair])
CASE_COUNT = 9
CALLBACK_CAP = 600
CASE_WORK_CAP = 4_800
CALLBACK_THRESHOLDS = (600, 1_200, 2_400, 4_800)
CAMPAIGN_SCHEMA = "geotarget.local-correction-campaign/v1"
SVD_PREREGISTRATION = (
    Path(__file__).parent.parent / "EXP-LOCAL-011" / "preregistration.json"
)
CRITICAL_FAMILIES = {
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
}


def _expected_cases() -> list[dict[str, Any]]:
    registration = json.loads(SVD_PREREGISTRATION.read_text(encoding="utf-8"))
    cases = [
        {
            "instance_id": case["instance_id"],
            "family_id": case["family_id"],
            "replay_checksum": case["replay_checksum"],
            "targets": int(case["target_count"]),
        }
        for case in registration["corpus"]["instances"]
    ]
    if len(cases) != CASE_COUNT or sum(int(case["targets"]) for case in cases) != 16:
        raise ValueError("frozen SVD preregistration has an unexpected corpus")
    return cases


def _unsafe(attempt: dict[str, Any]) -> bool:
    return bool(attempt["assessor_qualified"]) and (
        not bool(attempt["assessor_gold_matched"])
        or bool(attempt["assessor_target_ambiguous"])
    )


def _reported_unsafe(attempt: dict[str, Any]) -> bool:
    return bool(attempt["reported_accepted"]) and (
        not bool(attempt["assessor_qualified"])
        or not bool(attempt["assessor_gold_matched"])
        or bool(attempt["assessor_target_ambiguous"])
    )


def _targets(attempts: list[dict[str, Any]]) -> set[str]:
    return {
        str(attempt["assessor_matched_target_id"])
        for attempt in attempts
        if attempt["assessor_qualified"]
        and attempt["assessor_gold_matched"]
        and not attempt["assessor_target_ambiguous"]
    }


def _safe_full(attempts: list[dict[str, Any]], target_count: int) -> bool:
    return len(_targets(attempts)) == target_count and not any(map(_unsafe, attempts))


def _suffix_work(attempts: list[dict[str, Any]], target_count: int) -> int | None:
    for index in range(len(attempts)):
        prefix = attempts[: index + 1]
        suffix = attempts[index + 1 :]
        if _safe_full(prefix, target_count) and not any(map(_unsafe, suffix)):
            return sum(int(attempt["observed_evaluations"]) for attempt in prefix)
    return None


def _endpoint_changed(candidate: dict[str, Any], shadow: dict[str, Any]) -> bool:
    return candidate.get("endpoint") != shadow.get("endpoint")


def _same_safe_target(candidate: dict[str, Any], shadow: dict[str, Any]) -> bool:
    return (
        candidate["assessor_qualified"]
        and candidate["assessor_gold_matched"]
        and not candidate["assessor_target_ambiguous"]
        and shadow["assessor_qualified"]
        and shadow["assessor_gold_matched"]
        and not shadow["assessor_target_ambiguous"]
        and candidate["assessor_matched_target_id"]
        == shadow["assessor_matched_target_id"]
    )


def _assessor_snapshot(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    targets = _targets(attempts)
    unsafe = sum(map(_unsafe, attempts))
    return {
        "assessor_qualified": sum(
            bool(attempt["assessor_qualified"]) for attempt in attempts
        ),
        "assessor_safe_full": False,
        "assessor_targets_found": len(targets),
        "assessor_unsafe": unsafe,
    }


def _first_crossings(
    attempts: list[dict[str, Any]], target_count: int
) -> list[dict[str, Any]]:
    crossings: list[dict[str, Any]] = []
    cumulative = 0
    next_threshold = 0
    for attempt_count, attempt in enumerate(attempts, start=1):
        cumulative += int(attempt["observed_evaluations"])
        while (
            next_threshold < len(CALLBACK_THRESHOLDS)
            and cumulative >= CALLBACK_THRESHOLDS[next_threshold]
        ):
            prefix = attempts[:attempt_count]
            metrics = _assessor_snapshot(prefix)
            metrics["assessor_safe_full"] = _safe_full(prefix, target_count)
            metrics["assessor_target_recall"] = (
                metrics["assessor_targets_found"] / target_count
            )
            metrics.update(
                {
                    "callback_threshold": CALLBACK_THRESHOLDS[next_threshold],
                    "crossing_callback_work": cumulative,
                    "crossing_start_index": attempt_count,
                }
            )
            crossings.append(metrics)
            next_threshold += 1
    return crossings


def _snapshot_mismatch_count(
    observed: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    *,
    variant: str,
    instance: str,
    family: str,
) -> int:
    if len(observed) != len(expected):
        return 1
    mismatches = 0
    fields = (
        "assessor_qualified",
        "assessor_safe_full",
        "assessor_target_recall",
        "assessor_targets_found",
        "assessor_unsafe",
        "callback_threshold",
        "crossing_callback_work",
        "crossing_start_index",
    )
    for actual, wanted in zip(
        sorted(observed, key=lambda row: int(row.get("callback_threshold", -1))),
        expected,
        strict=True,
    ):
        mismatches += (
            actual.get("variant") != variant
            or actual.get("instance_id") != instance
            or actual.get("family_id") != family
            or any(actual.get(field) != wanted[field] for field in fields)
        )
    return mismatches


def _load(
    paths: list[Path],
    expected_cases: list[dict[str, Any]],
    *,
    suite: str | None,
    schema: str,
) -> tuple[list[dict[str, Any]], str]:
    case_count = len(expected_cases)
    if case_count <= 0:
        raise ValueError("expected case manifest must be nonempty")
    if len(paths) != case_count:
        raise ValueError(f"expected {case_count} shard paths, got {len(paths)}")
    required = {"instance_id", "family_id", "replay_checksum", "targets"}
    if any(not required.issubset(case) for case in expected_cases):
        raise ValueError("expected case manifest record is missing a required field")
    instances = [str(case["instance_id"]) for case in expected_cases]
    if len(set(instances)) != case_count:
        raise ValueError("expected case manifest contains duplicate instances")
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    indices = [int(document["case_index"]) for document in documents]
    if sorted(indices) != list(range(1, case_count + 1)):
        raise ValueError(f"case indices must be exactly 1..{case_count}: {indices}")
    revisions = {document["revision"]["git_head"] for document in documents}
    if len(revisions) != 1 or any(
        document["revision"]["git_dirty"] for document in documents
    ):
        raise ValueError("all shards must come from one clean commit")
    for document in documents:
        if document.get("schema") != schema:
            raise ValueError("unexpected shard schema")
        if suite is not None and document.get("suite") != suite:
            raise ValueError("unexpected shard suite")
        if int(document.get("case_count", 0)) != case_count:
            raise ValueError("case_count mismatch")
        names = tuple(entry["name"] for entry in document["variant_manifest"])
        if names != VARIANTS:
            raise ValueError(f"variant manifest mismatch: {names}")
        if len(document["problem_manifest"]) != 1 or len(document["terminals"]) != len(
            VARIANTS
        ):
            raise ValueError("each shard must contain one case and five terminals")
        expected = expected_cases[int(document["case_index"]) - 1]
        observed = document["problem_manifest"][0]
        for field in required:
            expected_value = (
                int(expected[field]) if field == "targets" else expected[field]
            )
            observed_value = (
                int(observed.get(field, -1))
                if field == "targets"
                else observed.get(field)
            )
            if observed_value != expected_value:
                raise ValueError(
                    f"case {document['case_index']} manifest differs from preregistration"
                )
        if "saved_starts_checksum" in expected and (
            observed.get("saved_starts_checksum") != expected["saved_starts_checksum"]
        ):
            raise ValueError(
                f"case {document['case_index']} manifest differs from preregistration"
            )
    return documents, revisions.pop()


def aggregate_expected(
    paths: list[Path],
    expected_cases: list[dict[str, Any]],
    *,
    suite: str | None,
    schema: str,
) -> dict[str, Any]:
    documents, revision = _load(paths, expected_cases, suite=suite, schema=schema)
    case_count = len(expected_cases)
    maximum_starts = 32 if suite == "t2" else 64
    attempts_by_stream: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    target_counts: dict[str, int] = {}
    families: dict[str, str] = {}
    terminal_by_stream: dict[tuple[str, str], dict[str, Any]] = {}
    snapshots_by_stream: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for document in documents:
        problem = document["problem_manifest"][0]
        instance = str(problem["instance_id"])
        target_counts[instance] = int(problem["targets"])
        families[instance] = str(problem["family_id"])
        for attempt in document["attempts"]:
            if attempt["instance_id"] != instance:
                raise ValueError("attempt instance does not match its shard")
            attempts_by_stream[(str(attempt["variant"]), instance)].append(attempt)
        for terminal in document["terminals"]:
            key = (str(terminal["variant"]), instance)
            if key in terminal_by_stream:
                raise ValueError(f"duplicate terminal {key}")
            terminal_by_stream[key] = terminal
        for snapshot in document.get("threshold_snapshots", []):
            if snapshot.get("instance_id") != instance:
                raise ValueError("threshold snapshot instance does not match its shard")
            key = (str(snapshot["variant"]), instance)
            snapshots_by_stream[key].append(snapshot)

    if len(target_counts) != case_count:
        raise ValueError("campaign corpus contains missing or duplicate instances")

    expected = {
        (variant, instance) for variant in VARIANTS for instance in target_counts
    }
    if set(attempts_by_stream) != expected or set(terminal_by_stream) != expected:
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
    reported_unsafe_by_variant = {variant: 0 for variant in VARIANTS}
    stream_metrics: dict[tuple[str, str], dict[str, Any]] = {}
    for key, attempts in attempts_by_stream.items():
        attempts.sort(key=lambda attempt: int(attempt["start_index"]))
        starts = [int(attempt["start_index"]) for attempt in attempts]
        if starts != list(range(1, len(attempts) + 1)):
            raise ValueError(f"non-contiguous paired starts for {key}")
        for attempt in attempts:
            observed = int(attempt["observed_evaluations"])
            reported = int(attempt["reported_evaluations"])
            accounting["attempt_callback_cap_violations"] += observed > CALLBACK_CAP
            accounting["evaluation_count_mismatches"] += observed != reported or bool(
                attempt["evaluation_count_mismatch"]
            )
            accounting["exceptions"] += attempt.get("exception") is not None
            reported_unsafe_by_variant[str(attempt["variant"])] += _reported_unsafe(
                attempt
            )
            accounting["runner_budget_exhausted"] += bool(attempt["budget_exhausted"])
        _, instance = key
        target_count = target_counts[instance]
        work = sum(int(attempt["observed_evaluations"]) for attempt in attempts)
        work_before_last = sum(
            int(attempt["observed_evaluations"]) for attempt in attempts[:-1]
        )
        accounting["stream_stop_violations"] += (
            not attempts
            or work_before_last >= CASE_WORK_CAP
            or (len(attempts) < maximum_starts and work < CASE_WORK_CAP)
            or len(attempts) > maximum_starts
        )
        suffix = _suffix_work(attempts, target_count)
        accounting["threshold_snapshot_mismatches"] += _snapshot_mismatch_count(
            snapshots_by_stream.get(key, []),
            _first_crossings(attempts, target_count),
            variant=key[0],
            instance=instance,
            family=families[instance],
        )
        terminal = terminal_by_stream[key]
        censored = (
            suffix if suffix is not None and suffix <= CASE_WORK_CAP else CASE_WORK_CAP
        )
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
            "safe_full": _safe_full(attempts, target_count),
            "targets": sorted(_targets(attempts)),
            "target_count": target_count,
            "unsafe": sum(map(_unsafe, attempts)),
            "right_censored_work": censored,
        }

    variant_metrics: dict[str, dict[str, Any]] = {}
    family_metrics: dict[str, dict[str, Any]] = {}
    total_targets = sum(target_counts.values())
    for variant in VARIANTS:
        rows = [
            stream_metrics[(variant, instance)] for instance in sorted(target_counts)
        ]
        found = sum(len(row["targets"]) for row in rows)
        variant_metrics[variant] = {
            "assessor_safe_full_cases": sum(bool(row["safe_full"]) for row in rows),
            "assessor_targets_found": found,
            "assessor_target_count": total_targets,
            "assessor_target_recall": found / total_targets,
            "assessor_unsafe": sum(int(row["unsafe"]) for row in rows),
            "reported_unsafe": reported_unsafe_by_variant[variant],
            "right_censored_callback_work": sum(
                int(row["right_censored_work"]) for row in rows
            ),
        }
        family_metrics[variant] = {}
        for family in sorted(set(families.values())):
            family_rows = [
                stream_metrics[(variant, instance)]
                for instance in target_counts
                if families[instance] == family
            ]
            family_found = sum(len(row["targets"]) for row in family_rows)
            family_total = sum(int(row["target_count"]) for row in family_rows)
            family_safe_full = sum(bool(row["safe_full"]) for row in family_rows)
            family_metrics[variant][family] = {
                "safe_full_cases": family_safe_full,
                "case_count": len(family_rows),
                "safe_full_rate": family_safe_full / len(family_rows),
                "targets_found": family_found,
                "target_count": family_total,
                "target_recall": family_found / family_total,
            }
        variant_metrics[variant]["mean_family_safe_full_rate"] = sum(
            row["safe_full_rate"] for row in family_metrics[variant].values()
        ) / len(family_metrics[variant])

    pair_metrics: dict[str, Any] = {}
    shadow_disagreements: list[dict[str, Any]] = []
    for candidate, shadow in CANDIDATE_SHADOW.items():
        callback_mismatches = 0
        support_families: set[str] = set()
        for instance in sorted(target_counts):
            candidate_attempts = attempts_by_stream[(candidate, instance)]
            shadow_attempts = attempts_by_stream[(shadow, instance)]
            if len(candidate_attempts) != len(shadow_attempts):
                callback_mismatches += 1
                continue
            for left, right in zip(candidate_attempts, shadow_attempts, strict=True):
                if (
                    left["start_index"] != right["start_index"]
                    or left["start"] != right["start"]
                    or left["observed_evaluations"] != right["observed_evaluations"]
                    or left["reported_evaluations"] != right["reported_evaluations"]
                ):
                    callback_mismatches += 1
                changed = _endpoint_changed(left, right)
                safely_active = changed and (
                    (
                        _unsafe(right)
                        and not _unsafe(left)
                        and left.get("endpoint") is None
                    )
                    or _same_safe_target(left, right)
                )
                if safely_active:
                    support_families.add(families[instance])
                if changed or _unsafe(left) != _unsafe(right):
                    shadow_disagreements.append(
                        {
                            "candidate": candidate,
                            "family_id": families[instance],
                            "instance_id": instance,
                            "start_index": left["start_index"],
                            "candidate_endpoint_present": left.get("endpoint")
                            is not None,
                            "shadow_endpoint_present": right.get("endpoint")
                            is not None,
                            "candidate_target": left.get("assessor_matched_target_id"),
                            "shadow_target": right.get("assessor_matched_target_id"),
                            "candidate_unsafe": _unsafe(left),
                            "shadow_unsafe": _unsafe(right),
                        }
                    )
        cand = variant_metrics[candidate]
        base = variant_metrics[CONTROL]
        own_shadow = variant_metrics[shadow]
        if candidate == "E2-FD2-SVD3":
            safety_gate = cand["assessor_unsafe"] == 0 and (
                own_shadow["assessor_unsafe"] > cand["assessor_unsafe"]
            )
        else:
            safety_gate = cand["assessor_unsafe"] == 0 and (
                own_shadow["assessor_unsafe"] > cand["assessor_unsafe"]
                or own_shadow["assessor_unsafe"] == cand["assessor_unsafe"] == 0
            )
        gates = {
            "callback_identity": callback_mismatches == 0,
            "safety": safety_gate,
            "reported_acceptance_safe": cand["reported_unsafe"] == 0,
            "safe_full_noninferior_to_shadow": (
                cand["assessor_safe_full_cases"]
                >= own_shadow["assessor_safe_full_cases"]
            ),
            "target_recall_delta_at_least_minus_0_02": (
                cand["assessor_target_recall"] - base["assessor_target_recall"] >= -0.02
            ),
            "work_ratio_at_most_1_2": (
                cand["right_censored_callback_work"]
                <= 1.2 * base["right_censored_callback_work"]
            ),
            "critical_family_target_recall_delta_at_least_minus_0_02": all(
                family_metrics[candidate][family]["target_recall"]
                - family_metrics[CONTROL][family]["target_recall"]
                >= -0.02
                for family in CRITICAL_FAMILIES
            ),
            "three_unrelated_active_structures": len(support_families) >= 3,
        }
        pair_metrics[candidate] = {
            "callback_mismatches": callback_mismatches,
            "support_families": sorted(support_families),
            "mean_family_safe_full_rate": cand["mean_family_safe_full_rate"],
            "mean_family_safe_full_delta_vs_control": (
                cand["mean_family_safe_full_rate"] - base["mean_family_safe_full_rate"]
            ),
            "gates": gates,
            "passes_t0": all(gates.values()) and not any(accounting.values()),
        }

    cpqr, svd = CANDIDATE_SHADOW
    cpqr_attempts = {
        (instance, int(attempt["start_index"])): attempt
        for instance in target_counts
        for attempt in attempts_by_stream[(cpqr, instance)]
    }
    svd_attempts = {
        (instance, int(attempt["start_index"])): attempt
        for instance in target_counts
        for attempt in attempts_by_stream[(svd, instance)]
    }
    cross_disagreements = []
    for key in sorted(set(cpqr_attempts) & set(svd_attempts)):
        left, right = cpqr_attempts[key], svd_attempts[key]
        if (
            left.get("endpoint") != right.get("endpoint")
            or _unsafe(left) != _unsafe(right)
            or left.get("assessor_matched_target_id")
            != right.get("assessor_matched_target_id")
            or left.get("observed_evaluations") != right.get("observed_evaluations")
        ):
            cross_disagreements.append(
                {
                    "instance_id": key[0],
                    "start_index": key[1],
                    "cpqr_endpoint_present": left.get("endpoint") is not None,
                    "svd_endpoint_present": right.get("endpoint") is not None,
                    "cpqr_unsafe": _unsafe(left),
                    "svd_unsafe": _unsafe(right),
                    "cpqr_target": left.get("assessor_matched_target_id"),
                    "svd_target": right.get("assessor_matched_target_id"),
                    "cpqr_callbacks": left.get("observed_evaluations"),
                    "svd_callbacks": right.get("observed_evaluations"),
                }
            )

    return {
        "schema": "geotarget.local-correction-aggregate/v1",
        "input_schema": schema,
        "suite": suite,
        "revision": revision,
        "accounting": accounting,
        "reported_unsafe_by_variant": reported_unsafe_by_variant,
        "variant_metrics": variant_metrics,
        "family_metrics": family_metrics,
        "candidate_gates": pair_metrics,
        "candidate_shadow_disagreements": shadow_disagreements,
        "cpqr_svd_disagreements": cross_disagreements,
    }


def aggregate(paths: list[Path]) -> dict[str, Any]:
    """Aggregate the frozen nine-case T0 without changing its public wrapper."""
    return aggregate_expected(
        paths,
        _expected_cases(),
        suite=None,
        schema=CAMPAIGN_SCHEMA,
    )


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
