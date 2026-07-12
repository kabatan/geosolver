#!/usr/bin/env python3
"""Run up to 16 independent T2 case shards and aggregate their raw records."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


EXPERIMENT = Path(__file__).resolve().parent
ROOT = EXPERIMENT.parents[2]
RUNNER = EXPERIMENT / "run_t2.jl"
PREREGISTRATION = EXPERIMENT / "t2-preregistration.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results" / "raw"
SHARD_COUNT = 48
MAX_JOBS = 16
PREFIXES = (8, 16, 32)
CALLBACK_WORK_CENSOR = 4800
VARIANTS = ("prod-tol-120x600", "prod-options-250x2000", "SCIPY-HYBR")
CANDIDATE = "SCIPY-HYBR"
CONTROL = "prod-tol-120x600"
NONSQUARE_FAMILY = "REDUNDANT-OVERDETERMINED"
FAMILIES = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    NONSQUARE_FAMILY,
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)
APPLICABLE_FAMILIES = tuple(f for f in FAMILIES if f != NONSQUARE_FAMILY)
CRITICAL = {
    "S1-regular-curved": ("CURVED-CHAIN",),
    "S2-S5-close-root-target-collision": ("MULTIROOT-WARPED",),
    "S3-singular-tangent-rank-deficient": (
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
    ),
    "S4-guard-boundary-domain": ("STRICT-GUARD-BOUNDARY",),
    "S6-opaque-transcendental": ("OPAQUE-TRANSCENDENTAL-C0",),
    "S8-extreme-scale": ("SCALE-LADDER",),
}
CAPS = {"prod-tol-120x600": 600, "prod-options-250x2000": 2000, CANDIDATE: 600}
CORPUS_SHA256 = "9b17d99a33b076833902b14d19c9b7a8f490f78d15e600c47fe068668d139e26"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shard_path(directory: Path, index: int) -> Path:
    return directory / f"exp-local-007-t2-shard-{index}-of-48.json"


def git_text(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *arguments], text=True
    ).strip()


def require_clean_worktree() -> str:
    if git_text("status", "--porcelain"):
        raise RuntimeError("T2 campaign requires a clean committed worktree")
    return git_text("rev-parse", "HEAD")


def shard_command(julia: str, output: Path, index: int, core: int) -> list[str]:
    command = [
        julia,
        "+1.12.6",
        "--startup-file=no",
        "--history-file=no",
        f"--project={EXPERIMENT}",
        str(RUNNER),
        f"--shard-index={index}",
        f"--shard-count={SHARD_COUNT}",
        f"--output={output}",
    ]
    taskset = shutil.which("taskset")
    return [taskset, "-c", str(core), *command] if taskset else command


def run_one(julia: str, output: Path, index: int, core: int) -> tuple[int, str]:
    environment = os.environ.copy()
    environment.update(
        JULIA_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    completed = subprocess.run(
        shard_command(julia, output, index, core),
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"shard {index} failed on core {core} (exit {completed.returncode})\n"
            f"{completed.stdout}"
        )
    return index, completed.stdout


def run_campaign(output_dir: Path, jobs: int, julia: str) -> None:
    require_clean_worktree()
    if not 1 <= jobs <= MAX_JOBS:
        raise ValueError(f"--jobs must be in 1:{MAX_JOBS}")
    output_dir.mkdir(parents=True, exist_ok=True)
    pending = [i for i in range(SHARD_COUNT) if not shard_path(output_dir, i).exists()]
    for batch_index, offset in enumerate(range(0, len(pending), jobs)):
        batch = pending[offset : offset + jobs]
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = {
                executor.submit(
                    run_one,
                    julia,
                    shard_path(output_dir, index),
                    index,
                    (slot + batch_index) % MAX_JOBS,
                ): index
                for slot, index in enumerate(batch)
            }
            for future in as_completed(futures):
                index, output = future.result()
                print(output, end="")
                print(f"completed shard {index + 1}/{SHARD_COUNT}")
    print(f"all {SHARD_COUNT} shard paths are present; run the aggregate command next")


def _attempt_violations(attempt: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    accepted = bool(attempt["reported_accepted"])
    if accepted and not attempt["canonical_valid"]:
        violations.append("reported-accepted-canonical-invalid")
    if accepted and not attempt["gold_matched"]:
        violations.append("reported-accepted-gold-inconsistent")
    if accepted and attempt["numeric_target_matched"] and not attempt["configuration_matched"]:
        violations.append("reported-accepted-numeric-target-only")
    if accepted and attempt["target_ambiguous"]:
        violations.append("reported-accepted-ambiguous")
    if attempt["assessor_qualified"] and (
        not attempt["assessor_gold_matched"]
        or attempt["assessor_target_ambiguous"]
    ):
        violations.append("assessor-qualified-gold-inconsistent")
    if attempt["evaluation_count_mismatch"]:
        violations.append("evaluation-count-mismatch")
    if attempt["evaluations"] > CAPS[attempt["variant"]] or attempt["budget_exhausted"]:
        violations.append("runner-cap-violation")
    if attempt["exception"] is not None:
        violations.append("unhandled-exception")
    return violations


def _nonsquare_violations(attempt: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if attempt["status"] != "INAPPLICABLE_NONSQUARE":
        violations.append("wrong-status")
    if attempt["evaluations"] != 0 or attempt["reported_evaluations"] != 0:
        violations.append("nonzero-callbacks")
    if attempt["endpoint"] is not None:
        violations.append("endpoint-returned")
    if attempt["reported_accepted"]:
        violations.append("reported-accepted")
    if attempt["reported_converged"]:
        violations.append("reported-converged")
    if attempt["budget_exhausted"]:
        violations.append("runner-cap-violation")
    if attempt["exception"] is not None:
        violations.append("exception")
    return violations


def validate_shard(document: dict[str, Any], index: int) -> None:
    if document["schema"] != "geotarget.exp-local-007.t2-case-start-prefix/v1":
        raise ValueError(f"shard {index}: wrong schema")
    if document["corpus"]["sha256"] != CORPUS_SHA256:
        raise ValueError(f"shard {index}: corpus drift")
    if document["shard"]["index"] != index or document["shard"]["count"] != SHARD_COUNT:
        raise ValueError(f"shard {index}: shard identity drift")
    if document["prefixes"] != list(PREFIXES) or tuple(document["variants"]) != VARIANTS:
        raise ValueError(f"shard {index}: prefix/variant drift")
    if len(document["problem_manifest"]) != 1:
        raise ValueError(f"shard {index}: expected one case")
    problem = document["problem_manifest"][0]
    attempts = document["attempts"]
    summaries = document["summaries"]
    if len(attempts) != 96 or len(summaries) != 9:
        raise ValueError(f"shard {index}: expected 96 attempts and 9 summaries")
    pairings = {(a["variant"], a["start_index"]) for a in attempts}
    expected_pairings = {(v, s) for v in VARIANTS for s in range(1, 33)}
    if pairings != expected_pairings or len(pairings) != len(attempts):
        raise ValueError(f"shard {index}: incomplete or duplicate paired starts")
    summary_keys = {(s["variant"], s["prefix"]) for s in summaries}
    if summary_keys != {(v, p) for v in VARIANTS for p in PREFIXES}:
        raise ValueError(f"shard {index}: incomplete summary grid")
    for summary in summaries:
        if summary["prefix"] != PREFIXES[-1]:
            if any(
                name in summary
                for name in (
                    "right_censored_assessor_safe_full_work",
                    "assessor_safe_full_event_by_4800",
                    "suffix_stable_evaluations_to_assessor_safe_full",
                )
            ):
                raise ValueError(f"shard {index}: work attached to non-primary prefix")
            continue
        work = summary.get("right_censored_assessor_safe_full_work")
        event = summary.get("assessor_safe_full_event_by_4800")
        suffix = summary.get("suffix_stable_evaluations_to_assessor_safe_full")
        if not isinstance(work, int) or not 0 <= work <= CALLBACK_WORK_CENSOR:
            raise ValueError(f"shard {index}: invalid right-censored callback work")
        if not isinstance(event, bool):
            raise ValueError(f"shard {index}: invalid right-censor event flag")
        if event:
            if not isinstance(suffix, int) or suffix != work:
                raise ValueError(f"shard {index}: inconsistent observed callback event")
        elif work != CALLBACK_WORK_CENSOR:
            raise ValueError(f"shard {index}: callback miss was not right-censored")
    for attempt in attempts:
        if attempt["instance_id"] != problem["instance_id"]:
            raise ValueError(f"shard {index}: attempt crossed case identity")
        if attempt["evaluations"] > CAPS[attempt["variant"]]:
            raise ValueError(f"shard {index}: callback cap exceeded")
        if attempt["evaluation_count_mismatch"]:
            raise ValueError(f"shard {index}: reported/observed callback mismatch")
        if attempt["budget_exhausted"]:
            raise ValueError(f"shard {index}: runner hard cap exhausted")
        if attempt["exception"] is not None:
            raise ValueError(f"shard {index}: unhandled variant exception")
    environment = document["environment"]
    if environment["julia_threads"] != 1 or environment["julia_blas_threads"] != 1:
        raise ValueError(f"shard {index}: Julia/BLAS thread count drift")
    if any(environment[name] != "1" for name in (
        "openblas_num_threads", "omp_num_threads", "mkl_num_threads"
    )):
        raise ValueError(f"shard {index}: native thread count drift")


def _assessor_snapshot(
    sequence: list[dict[str, Any]], target_count: int, prefix: int
) -> dict[str, Any]:
    selected = sequence[:prefix]
    qualified_targets = {
        attempt["assessor_matched_target_id"]
        for attempt in selected
        if attempt["assessor_qualified"] and attempt["assessor_gold_matched"]
    }
    if None in qualified_targets:
        raise ValueError("qualified Gold-consistent attempt lacks a target identity")
    inconsistent = sum(
        bool(attempt["assessor_qualified"])
        and (
            not attempt["assessor_gold_matched"]
            or attempt["assessor_target_ambiguous"]
        )
        for attempt in selected
    )
    all_targets = len(qualified_targets) == target_count
    return {
        "assessor_qualified_targets_found": len(qualified_targets),
        "assessor_qualified_gold_inconsistent": inconsistent,
        "assessor_safe_all_targets": all_targets and inconsistent == 0,
        "evaluations": sum(attempt["evaluations"] for attempt in selected),
    }


def _suffix_stable_assessor_work(
    sequence: list[dict[str, Any]], target_count: int
) -> int | None:
    def safe_attempt(attempt: dict[str, Any]) -> bool:
        return not attempt["assessor_qualified"] or (
            attempt["assessor_gold_matched"]
            and not attempt["assessor_target_ambiguous"]
        )

    for prefix in range(1, len(sequence) + 1):
        if not _assessor_snapshot(sequence, target_count, prefix)[
            "assessor_safe_all_targets"
        ]:
            continue
        if all(safe_attempt(attempt) for attempt in sequence[prefix:]):
            return sum(attempt["evaluations"] for attempt in sequence[:prefix])
    return None


def _raw_case_summaries(document: dict[str, Any]) -> list[dict[str, Any]]:
    problem = document["problem_manifest"][0]
    records: list[dict[str, Any]] = []
    for variant in VARIANTS:
        sequence = sorted(
            (a for a in document["attempts"] if a["variant"] == variant),
            key=lambda attempt: attempt["start_index"],
        )
        if [a["start_index"] for a in sequence] != list(range(1, 33)):
            raise ValueError("raw reaggregation received an incomplete start stream")
        suffix_work = _suffix_stable_assessor_work(sequence, problem["target_count"])
        event = suffix_work is not None and suffix_work <= CALLBACK_WORK_CENSOR
        censored_work = suffix_work if event else CALLBACK_WORK_CENSOR
        for prefix in PREFIXES:
            snapshot = _assessor_snapshot(sequence, problem["target_count"], prefix)
            record = {
                "variant": variant,
                "instance_id": problem["instance_id"],
                "family_id": problem["family_id"],
                "prefix": prefix,
                "target_count": problem["target_count"],
                **snapshot,
            }
            if prefix == PREFIXES[-1]:
                record.update(
                    suffix_stable_evaluations_to_assessor_safe_full=suffix_work,
                    right_censored_assessor_safe_full_work=censored_work,
                    assessor_safe_full_event_by_4800=event,
                )
            records.append(record)
    return records


def _raw_reaggregate(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = [record for document in documents for record in _raw_case_summaries(document)]
    recorded = {
        (summary["instance_id"], summary["variant"], summary["prefix"]): summary
        for document in documents
        for summary in document["summaries"]
    }
    comparison_fields = (
        "target_count",
        "assessor_qualified_targets_found",
        "assessor_qualified_gold_inconsistent",
        "assessor_safe_all_targets",
        "evaluations",
    )
    for record in raw:
        key = (record["instance_id"], record["variant"], record["prefix"])
        summary = recorded[key]
        if any(summary[field] != record[field] for field in comparison_fields):
            raise ValueError(f"raw attempt reaggregation disagrees with summary {key}")
        if record["prefix"] == PREFIXES[-1]:
            for field in (
                "suffix_stable_evaluations_to_assessor_safe_full",
                "right_censored_assessor_safe_full_work",
                "assessor_safe_full_event_by_4800",
            ):
                if summary[field] != record[field]:
                    raise ValueError(f"raw callback-work reaggregation disagrees at {key}")
    return raw


def _safe_rate(final: list[dict[str, Any]], variant: str, families: tuple[str, ...]) -> float:
    selected = [s for s in final if s["variant"] == variant and s["family_id"] in families]
    return sum(bool(s["assessor_safe_all_targets"]) for s in selected) / len(selected)


def _target_recall(summaries: list[dict[str, Any]]) -> float:
    targets = sum(s["target_count"] for s in summaries)
    return sum(s["assessor_qualified_targets_found"] for s in summaries) / targets


def _family_callback_work(
    final: list[dict[str, Any]], variant: str, family: str
) -> int:
    return sum(
        s["right_censored_assessor_safe_full_work"]
        for s in final
        if s["variant"] == variant and s["family_id"] == family
    )


def evaluate_gate(
    family_safe: dict[str, dict[str, float]],
    family_work: dict[str, dict[str, int]],
    critical_safe: dict[str, dict[str, float]],
    safety_count: int,
    nonsquare_count: int,
    truth_leak_audit: str,
) -> dict[str, Any]:
    control_equal = sum(family_safe[CONTROL].values()) / len(APPLICABLE_FAMILIES)
    candidate_equal = sum(family_safe[CANDIDATE].values()) / len(APPLICABLE_FAMILIES)
    delta = candidate_equal - control_equal
    control_work = sum(family_work[CONTROL].values())
    candidate_work = sum(family_work[CANDIDATE].values())
    ratio = candidate_work / control_work
    path_a = delta >= 0.05 - 1e-12 and ratio <= 1.2 + 1e-12
    path_b = delta >= -0.01 - 1e-12 and ratio <= 0.8 + 1e-12
    critical_deltas = {
        name: critical_safe[CANDIDATE][name] - critical_safe[CONTROL][name]
        for name in CRITICAL
    }
    supporting_a = [
        family for family in APPLICABLE_FAMILIES
        if family_safe[CANDIDATE][family] - family_safe[CONTROL][family] > 1e-12
    ]
    supporting_b = [
        family for family in APPLICABLE_FAMILIES
        if family_safe[CANDIDATE][family] - family_safe[CONTROL][family] >= -0.01 - 1e-12
        and family_work[CANDIDATE][family] / family_work[CONTROL][family] <= 0.8 + 1e-12
    ]
    generality = (path_a and len(supporting_a) >= 3) or (path_b and len(supporting_b) >= 3)
    critical_gate = all(value >= -0.02 - 1e-12 for value in critical_deltas.values())
    truth_gate = truth_leak_audit == "pass"
    passed = (
        (path_a or path_b)
        and generality
        and critical_gate
        and safety_count == 0
        and nonsquare_count == 0
        and truth_gate
    )
    return {
        "passed": passed,
        "performance_path_a": path_a,
        "performance_path_b": path_b,
        "family_equal_control_safe_full": control_equal,
        "family_equal_candidate_safe_full": candidate_equal,
        "family_equal_safe_full_delta": delta,
        "callback_work_ratio": ratio,
        "critical_deltas": critical_deltas,
        "critical_gate": critical_gate,
        "path_a_supporting_families": supporting_a,
        "path_b_supporting_families": supporting_b,
        "generality_gate": generality,
        "safety_gate": safety_count == 0,
        "nonsquare_gate": nonsquare_count == 0,
        "truth_leak_audit": truth_leak_audit,
        "truth_leak_gate": truth_gate,
    }


def aggregate(output_dir: Path, summary_path: Path, truth_leak_audit: str) -> dict[str, Any]:
    current_head = require_clean_worktree()
    preregistration_sha256 = sha256_file(PREREGISTRATION)
    documents: list[dict[str, Any]] = []
    for index in range(SHARD_COUNT):
        path = shard_path(output_dir, index)
        if not path.is_file():
            raise FileNotFoundError(f"missing T2 shard: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        validate_shard(document, index)
        documents.append(document)
    heads = {d["revision"]["git_head"] for d in documents}
    preregistrations = {d["preregistration"]["sha256"] for d in documents}
    case_ids = [d["problem_manifest"][0]["instance_id"] for d in documents]
    replay_ids = [d["problem_manifest"][0]["replay_checksum"] for d in documents]
    family_ids = [d["problem_manifest"][0]["family_id"] for d in documents]
    if heads != {current_head} or preregistrations != {preregistration_sha256}:
        raise ValueError("shards do not match the current clean commit/preregistration")
    if len(set(case_ids)) != SHARD_COUNT:
        raise ValueError("T2 shard set has duplicate cases")
    if len(set(replay_ids)) != SHARD_COUNT:
        raise ValueError("T2 shard set has duplicate replay material")
    if {family: family_ids.count(family) for family in FAMILIES} != {
        family: 6 for family in FAMILIES
    }:
        raise ValueError("T2 shard set is not the frozen 8-family by 6-case grid")
    environment_ids = {
        (
            d["environment"]["julia_version"],
            d["environment"]["python_version"],
            d["environment"]["scipy_version"],
            d["environment"]["machine"],
        )
        for d in documents
    }
    if len(environment_ids) != 1:
        raise ValueError("T2 shard runtime versions or machine identity disagree")

    attempts = [a for d in documents for a in d["attempts"]]
    recorded_summaries = [s for d in documents for s in d["summaries"]]
    summaries = _raw_reaggregate(documents)
    final = [s for s in summaries if s["prefix"] == 32 and s["family_id"] != NONSQUARE_FAMILY]
    family_safe = {
        variant: {
            family: _safe_rate(final, variant, (family,))
            for family in APPLICABLE_FAMILIES
        }
        for variant in (CONTROL, CANDIDATE)
    }
    family_work = {
        variant: {
            family: _family_callback_work(final, variant, family)
            for family in APPLICABLE_FAMILIES
        }
        for variant in (CONTROL, CANDIDATE)
    }
    critical_safe = {
        variant: {
            name: _safe_rate(final, variant, families)
            for name, families in CRITICAL.items()
        }
        for variant in (CONTROL, CANDIDATE)
    }
    candidate_violations: dict[str, int] = {}
    nonsquare_violations: dict[str, int] = {}
    for attempt in attempts:
        if attempt["variant"] != CANDIDATE:
            continue
        if attempt["family_id"] == NONSQUARE_FAMILY:
            violations = _nonsquare_violations(attempt)
            target = nonsquare_violations
        else:
            violations = _attempt_violations(attempt)
            target = candidate_violations
        for violation in violations:
            target[violation] = target.get(violation, 0) + 1
    safety_count = sum(candidate_violations.values())
    nonsquare_count = sum(nonsquare_violations.values())
    gate = evaluate_gate(
        family_safe,
        family_work,
        critical_safe,
        safety_count,
        nonsquare_count,
        truth_leak_audit,
    )
    recall = {
        variant: _target_recall([s for s in final if s["variant"] == variant])
        for variant in (CONTROL, CANDIDATE)
    }
    multiroot = {
        variant: {
            str(prefix): {
                "safe_full_rate": _safe_rate(
                    [s for s in summaries if s["prefix"] == prefix],
                    variant,
                    ("MULTIROOT-WARPED",),
                ),
                "target_recall": _target_recall([
                    s for s in summaries
                    if s["variant"] == variant
                    and s["family_id"] == "MULTIROOT-WARPED"
                    and s["prefix"] == prefix
                ]),
            }
            for prefix in PREFIXES
        }
        for variant in (CONTROL, CANDIDATE)
    }
    result = {
        "experiment_id": "EXP-LOCAL-007-T2",
        "state": "complete" if truth_leak_audit == "pass" else "awaiting-source-audit",
        "revision": current_head,
        "corpus_sha256": CORPUS_SHA256,
        "preregistration_sha256": preregistration_sha256,
        "shard_count": len(documents),
        "attempt_count": len(attempts),
        "summary_count": len(recorded_summaries),
        "raw_reaggregation_mismatches": 0,
        "family_safe_full": family_safe,
        "family_callback_work": family_work,
        "critical_safe_full": critical_safe,
        "target_recall": recall,
        "candidate_safety_violations": candidate_violations,
        "nonsquare_inapplicability_violations": nonsquare_violations,
        "multi_root_diagnostic": multiroot,
        "promotion_gate": gate,
    }
    if summary_path.exists():
        raise FileExistsError(f"refusing to replace T2 summary: {summary_path}")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_bytes(canonical_bytes(result) + b"\n")
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run missing one-case shards")
    run.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    run.add_argument("--jobs", type=int, default=MAX_JOBS)
    run.add_argument("--julia", default="julia")
    collect = subparsers.add_parser("aggregate", help="validate and aggregate all shards")
    collect.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    collect.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "exp-local-007-t2-summary.json",
    )
    collect.add_argument(
        "--truth-leak-audit",
        choices=("pending", "pass", "fail"),
        default="pending",
        help="independent source-audit result; only pass can promote the candidate",
    )
    return result


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "run":
        run_campaign(arguments.output_dir.resolve(), arguments.jobs, arguments.julia)
    else:
        result = aggregate(
            arguments.output_dir.resolve(),
            arguments.summary.resolve(),
            arguments.truth_leak_audit,
        )
        print(json.dumps(result["promotion_gate"], indent=2, sort_keys=True))
        print(f"summary={arguments.summary.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
