#!/usr/bin/env python3
"""Independently aggregate the frozen EXP-LOCAL-010/011 T0 shards."""

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
SVD_PREREGISTRATION = Path(__file__).parent.parent / "EXP-LOCAL-011" / "preregistration.json"
CRITICAL_FAMILIES = {
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
}


def _expected_cases() -> list[dict[str, Any]]:
    registration = json.loads(SVD_PREREGISTRATION.read_text(encoding="utf-8"))
    cases = registration["corpus"]["instances"]
    if len(cases) != CASE_COUNT or sum(int(case["target_count"]) for case in cases) != 16:
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


def _load(paths: list[Path]) -> tuple[list[dict[str, Any]], str]:
    if len(paths) != CASE_COUNT:
        raise ValueError(f"expected {CASE_COUNT} shard paths, got {len(paths)}")
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    indices = [int(document["case_index"]) for document in documents]
    if sorted(indices) != list(range(1, CASE_COUNT + 1)):
        raise ValueError(f"case indices must be exactly 1..{CASE_COUNT}: {indices}")
    revisions = {document["revision"]["git_head"] for document in documents}
    if len(revisions) != 1 or any(document["revision"]["git_dirty"] for document in documents):
        raise ValueError("all shards must come from one clean commit")
    expected_cases = _expected_cases()
    for document in documents:
        if document.get("schema") != "geotarget.local-correction-campaign/v1":
            raise ValueError("unexpected shard schema")
        if int(document.get("case_count", 0)) != CASE_COUNT:
            raise ValueError("case_count mismatch")
        names = tuple(entry["name"] for entry in document["variant_manifest"])
        if names != VARIANTS:
            raise ValueError(f"variant manifest mismatch: {names}")
        if len(document["problem_manifest"]) != 1 or len(document["terminals"]) != len(VARIANTS):
            raise ValueError("each shard must contain one case and five terminals")
        expected = expected_cases[int(document["case_index"]) - 1]
        observed = document["problem_manifest"][0]
        manifest_fields = {
            "instance_id": expected["instance_id"],
            "family_id": expected["family_id"],
            "replay_checksum": expected["replay_checksum"],
            "targets": int(expected["target_count"]),
        }
        if observed != manifest_fields:
            raise ValueError(
                f"case {document['case_index']} manifest differs from preregistration"
            )
    return documents, revisions.pop()


def aggregate(paths: list[Path]) -> dict[str, Any]:
    documents, revision = _load(paths)
    attempts_by_stream: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    target_counts: dict[str, int] = {}
    families: dict[str, str] = {}
    terminal_by_stream: dict[tuple[str, str], dict[str, Any]] = {}

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

    if len(target_counts) != CASE_COUNT or sum(target_counts.values()) != 16:
        raise ValueError("representative corpus must contain nine distinct cases and 16 targets")

    expected = {(variant, instance) for variant in VARIANTS for instance in target_counts}
    if set(attempts_by_stream) != expected or set(terminal_by_stream) != expected:
        raise ValueError("missing or extra variant/case stream")

    accounting = {
        "attempt_callback_cap_violations": 0,
        "evaluation_count_mismatches": 0,
        "exceptions": 0,
        "runner_budget_exhausted": 0,
        "stream_stop_violations": 0,
        "terminal_mismatches": 0,
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
            accounting["evaluation_count_mismatches"] += (
                observed != reported or bool(attempt["evaluation_count_mismatch"])
            )
            accounting["exceptions"] += attempt.get("exception") is not None
            reported_unsafe_by_variant[str(attempt["variant"])] += _reported_unsafe(attempt)
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
            or (len(attempts) < 64 and work < CASE_WORK_CAP)
            or len(attempts) > 64
        )
        suffix = _suffix_work(attempts, target_count)
        terminal = terminal_by_stream[key]
        censored = suffix if suffix is not None and suffix <= CASE_WORK_CAP else CASE_WORK_CAP
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
        rows = [stream_metrics[(variant, instance)] for instance in sorted(target_counts)]
        found = sum(len(row["targets"]) for row in rows)
        variant_metrics[variant] = {
            "assessor_safe_full_cases": sum(bool(row["safe_full"]) for row in rows),
            "assessor_targets_found": found,
            "assessor_target_count": total_targets,
            "assessor_target_recall": found / total_targets,
            "assessor_unsafe": sum(int(row["unsafe"]) for row in rows),
            "reported_unsafe": reported_unsafe_by_variant[variant],
            "right_censored_callback_work": sum(int(row["right_censored_work"]) for row in rows),
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
            family_metrics[variant][family] = {
                "targets_found": family_found,
                "target_count": family_total,
                "target_recall": family_found / family_total,
            }

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
                ):
                    callback_mismatches += 1
                changed = _endpoint_changed(left, right)
                safely_active = changed and (
                    (_unsafe(right) and not _unsafe(left) and left.get("endpoint") is None)
                    or _same_safe_target(left, right)
                )
                if safely_active:
                    support_families.add(families[instance])
                if changed or _unsafe(left) != _unsafe(right):
                    shadow_disagreements.append({
                        "candidate": candidate,
                        "family_id": families[instance],
                        "instance_id": instance,
                        "start_index": left["start_index"],
                        "candidate_endpoint_present": left.get("endpoint") is not None,
                        "shadow_endpoint_present": right.get("endpoint") is not None,
                        "candidate_target": left.get("assessor_matched_target_id"),
                        "shadow_target": right.get("assessor_matched_target_id"),
                        "candidate_unsafe": _unsafe(left),
                        "shadow_unsafe": _unsafe(right),
                    })
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
                cand["assessor_safe_full_cases"] >= own_shadow["assessor_safe_full_cases"]
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
        if left.get("endpoint") != right.get("endpoint") or _unsafe(left) != _unsafe(right):
            cross_disagreements.append({
                "instance_id": key[0],
                "start_index": key[1],
                "cpqr_endpoint_present": left.get("endpoint") is not None,
                "svd_endpoint_present": right.get("endpoint") is not None,
                "cpqr_unsafe": _unsafe(left),
                "svd_unsafe": _unsafe(right),
            })

    return {
        "schema": "geotarget.local-correction-aggregate/v1",
        "revision": revision,
        "accounting": accounting,
        "reported_unsafe_by_variant": reported_unsafe_by_variant,
        "variant_metrics": variant_metrics,
        "family_metrics": family_metrics,
        "candidate_gates": pair_metrics,
        "candidate_shadow_disagreements": shadow_disagreements,
        "cpqr_svd_disagreements": cross_disagreements,
    }


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
