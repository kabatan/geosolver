#!/usr/bin/env python3
"""Run and independently aggregate the common EXP-LOCAL-008/009 T0 wave."""

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


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = ROOT / "benchmarks" / "results" / "raw"
PREFIXES = (600, 1200, 2400, 4800)
SHARDS = 6
MAX_JOBS = 12
CONTROL = "prod-tol-120x600"
SECONDARY = "prod-options-250x2000"
STRATA = (
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
)
CAPS = {CONTROL: 600, SECONDARY: 2000, "ORTHOMADS-EB": 600,
        "RESTORING-GN-CPQR": 600}
CONFIGS = {
    "008": {
        "directory": HERE,
        "runner": HERE / "run_t0.jl",
        "project": str(HERE),
        "schema": "geotarget.exp-local-008.callback-prefix/v1",
        "experiment_id": "EXP-LOCAL-008",
        "candidate": "ORTHOMADS-EB",
        "preregistration": HERE / "preregistration.json",
        "recovery_keys": ("extreme_barrier_callbacks",),
        "recovery_field": "qualified_extreme_barrier_recoveries",
    },
    "009": {
        "directory": HERE.parent / "EXP-LOCAL-009",
        "runner": HERE.parent / "EXP-LOCAL-009" / "run_t0.jl",
        "project": "julia",
        "schema": "geotarget.exp-local-009.callback-prefix/v1",
        "experiment_id": "EXP-LOCAL-009",
        "candidate": "RESTORING-GN-CPQR",
        "preregistration": HERE.parent / "EXP-LOCAL-009" / "t0-preregistration.json",
        "recovery_keys": (
            "restored_starts",
            "fd_sign_reversals",
            "fd_invalid_trials",
            "invalid_line_search_trials",
        ),
        "recovery_field": "qualified_invalid_trial_recoveries",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def require_clean() -> str:
    if _git("status", "--porcelain"):
        raise RuntimeError("T0 wave requires a clean committed worktree")
    return _git("rev-parse", "HEAD")


def shard_path(experiment: str, index: int, directory: Path = RAW) -> Path:
    return directory / f"exp-local-{experiment}-t0-shard-{index}-of-6.json"


def _command(julia: str, experiment: str, index: int, output: Path, core: int) -> list[str]:
    config = CONFIGS[experiment]
    command = [
        julia,
        "+1.12.6",
        "--startup-file=no",
        "--history-file=no",
        f"--project={config['project']}",
        str(config["runner"]),
        f"--shard-index={index}",
        f"--shard-count={SHARDS}",
        f"--output={output}",
    ]
    taskset = shutil.which("taskset")
    return [taskset, "-c", str(core), *command] if taskset else command


def _run_one(julia: str, experiment: str, index: int, output: Path, core: int) -> str:
    environment = os.environ.copy()
    environment.update(JULIA_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                       OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    result = subprocess.run(
        _command(julia, experiment, index, output, core),
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"EXP-LOCAL-{experiment} shard {index} failed on core {core}\n{result.stdout}"
        )
    return result.stdout


def run_wave(output_dir: Path, jobs: int, julia: str) -> None:
    require_clean()
    if not 1 <= jobs <= MAX_JOBS:
        raise ValueError(f"--jobs must be in 1:{MAX_JOBS}")
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (experiment, index)
        for experiment in CONFIGS
        for index in range(SHARDS)
        if not shard_path(experiment, index, output_dir).exists()
    ]
    with ThreadPoolExecutor(max_workers=min(jobs, len(tasks) or 1)) as executor:
        futures = {
            executor.submit(
                _run_one,
                julia,
                experiment,
                index,
                shard_path(experiment, index, output_dir),
                slot % MAX_JOBS,
            ): (experiment, index)
            for slot, (experiment, index) in enumerate(tasks)
        }
        for future in as_completed(futures):
            experiment, index = futures[future]
            print(future.result(), end="")
            print(f"completed EXP-LOCAL-{experiment} shard {index + 1}/{SHARDS}")


def _target_count(problem: dict[str, Any]) -> int:
    return int(problem.get("target_count", problem.get("targets")))


def assessor_snapshot(sequence: list[dict[str, Any]], target_count: int) -> dict[str, Any]:
    targets = {
        attempt["assessor_matched_target_id"]
        for attempt in sequence
        if attempt["assessor_qualified"] and attempt["assessor_gold_matched"]
    }
    if None in targets:
        raise ValueError("qualified Gold-consistent endpoint lacks target identity")
    inconsistent = sum(
        bool(attempt["assessor_qualified"])
        and (not attempt["assessor_gold_matched"] or attempt["assessor_target_ambiguous"])
        for attempt in sequence
    )
    return {
        "targets": len(targets),
        "safe_full": len(targets) == target_count and inconsistent == 0,
        "inconsistent": inconsistent,
        "evaluations": sum(attempt["evaluations"] for attempt in sequence),
    }


def suffix_stable_work(sequence: list[dict[str, Any]], target_count: int) -> int | None:
    def safe(attempt: dict[str, Any]) -> bool:
        return not attempt["assessor_qualified"] or (
            attempt["assessor_gold_matched"] and not attempt["assessor_target_ambiguous"]
        )

    for index in range(1, len(sequence) + 1):
        if not assessor_snapshot(sequence[:index], target_count)["safe_full"]:
            continue
        if all(safe(attempt) for attempt in sequence[index:]):
            return sum(attempt["evaluations"] for attempt in sequence[:index])
    return None


def _diagnostic_int(attempt: dict[str, Any], key: str) -> int:
    prefix = key + "="
    for field in (attempt.get("diagnostic") or "").split(";"):
        if field.startswith(prefix):
            return int(field[len(prefix):])
    return 0


def _recovery(attempt: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return (
        attempt["assessor_qualified"]
        and attempt["assessor_gold_matched"]
        and not attempt["assessor_target_ambiguous"]
        and any(_diagnostic_int(attempt, key) > 0 for key in keys)
    )


def _candidate_violations(attempt: dict[str, Any]) -> list[str]:
    result: list[str] = []
    if attempt["reported_accepted"] and not attempt["canonical_valid"]:
        result.append("reported-accepted-canonical-invalid")
    if attempt["reported_accepted"] and not attempt["gold_matched"]:
        result.append("reported-accepted-gold-inconsistent")
    if attempt["reported_accepted"] and attempt["numeric_target_matched"] \
            and not attempt["configuration_matched"]:
        result.append("reported-accepted-numeric-target-only")
    if attempt["reported_accepted"] and attempt["target_ambiguous"]:
        result.append("reported-accepted-ambiguous")
    if attempt["assessor_qualified"] and (
        not attempt["assessor_gold_matched"] or attempt["assessor_target_ambiguous"]
    ):
        result.append("assessor-qualified-gold-inconsistent")
    return result


def _gate(control: dict[str, Any], candidate: dict[str, Any], *,
          guard_safe: bool, recoveries: int, violations: int,
          integrity: int, truth_audit: str, mechanism_tests: str) -> dict[str, Any]:
    ratio = candidate["work"] / control["work"]
    target_noninferior = candidate["targets"] >= control["targets"]
    safe_noninferior = candidate["safe_full"] >= control["safe_full"]
    strict_gain = candidate["targets"] > control["targets"] or \
        candidate["safe_full"] > control["safe_full"]
    path_a = target_noninferior and safe_noninferior and strict_gain and ratio <= 1.2
    path_b = target_noninferior and safe_noninferior and ratio <= 0.8
    deltas = {
        stratum: candidate["stratum_targets"][stratum] - control["stratum_targets"][stratum]
        for stratum in STRATA
    }
    return {
        "passed": (path_a or path_b) and all(value >= 0 for value in deltas.values())
        and guard_safe and recoveries >= 1 and violations == 0 and integrity == 0
        and truth_audit == "pass" and mechanism_tests == "pass",
        "path_a": path_a,
        "path_b": path_b,
        "target_noninferior": target_noninferior,
        "safe_full_noninferior": safe_noninferior,
        "strict_gain": strict_gain,
        "right_censored_work_ratio": ratio,
        "stratum_target_deltas": deltas,
        "strict_guard_safe_full": guard_safe,
        "qualified_recoveries": recoveries,
        "candidate_safety_violations": violations,
        "all_variant_integrity_violations": integrity,
        "truth_leak_audit": truth_audit,
        "mechanism_tests": mechanism_tests,
    }


def _load_experiment(experiment: str, output_dir: Path, aggregation_head: str,
                     truth_audit: str, mechanism_tests: str) -> dict[str, Any]:
    config = CONFIGS[experiment]
    prereg_hash = _sha256(config["preregistration"])
    documents = []
    for index in range(SHARDS):
        document = json.loads(shard_path(experiment, index, output_dir).read_text())
        if document["schema"] != config["schema"]:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: schema drift")
        if document["shard"]["index"] != index or document["shard"]["count"] != SHARDS:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: identity drift")
        if tuple(document["callback_prefixes"]) != PREFIXES:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: prefix drift")
        if len(document["problem_manifest"]) != 1:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: expected one case")
        variants = tuple(item["name"] for item in document["variant_manifest"])
        expected_variants = (CONTROL, SECONDARY, config["candidate"])
        if variants != expected_variants:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: variant drift")
        summary_keys = [(item["variant"], item["callback_prefix"])
                        for item in document["summaries"]]
        if len(summary_keys) != 12 or set(summary_keys) != {
            (variant, prefix) for variant in expected_variants for prefix in PREFIXES
        }:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: summary grid drift")
        revision = document["revision"]
        if revision["preregistration_sha256"] != prereg_hash:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: preregistration drift")
        environment = document["environment"]
        if environment["julia_threads"] != 1 or environment.get(
            "julia_blas_threads", environment.get("blas_threads")
        ) != 1:
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: thread drift")
        if any(environment[name] != "1" for name in (
            "openblas_num_threads", "omp_num_threads", "mkl_num_threads"
        )):
            raise ValueError(f"EXP-LOCAL-{experiment} shard {index}: native thread drift")
        documents.append(document)

    execution_heads = {document["revision"]["git_head"] for document in documents}
    if len(execution_heads) != 1:
        raise ValueError(f"EXP-LOCAL-{experiment}: execution revisions disagree")
    execution_head = next(iter(execution_heads))
    ancestry = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
         execution_head, aggregation_head],
        check=False,
    )
    if ancestry.returncode != 0:
        raise ValueError(f"EXP-LOCAL-{experiment}: execution revision is not an ancestor")

    problems = [document["problem_manifest"][0] for document in documents]
    if len({problem["instance_id"] for problem in problems}) != SHARDS:
        raise ValueError(f"EXP-LOCAL-{experiment}: duplicate case shard")
    family_counts = {stratum: 0 for stratum in STRATA}
    for problem in problems:
        family_counts[problem["family_id"]] += 1
    expected_family_counts = {stratum: 1 for stratum in STRATA}
    expected_family_counts["MULTIROOT-WARPED"] = 2
    if family_counts != expected_family_counts:
        raise ValueError(f"EXP-LOCAL-{experiment}: frozen family grid drift")

    metrics: dict[str, dict[str, Any]] = {}
    safety: dict[str, int] = {}
    integrity: dict[str, int] = {}
    guard_safe = False
    recoveries = 0
    variants = (CONTROL, SECONDARY, config["candidate"])
    for variant in variants:
        metrics[variant] = {
            "targets": 0,
            "safe_full": 0,
            "work": 0,
            "stratum_targets": {stratum: 0 for stratum in STRATA},
        }
    for document in documents:
        problem = document["problem_manifest"][0]
        target_count = _target_count(problem)
        summaries = {(s["variant"], s["callback_prefix"]): s for s in document["summaries"]}
        for variant in variants:
            sequence = sorted(
                (a for a in document["attempts"] if a["variant"] == variant),
                key=lambda attempt: attempt["start_index"],
            )
            if [a["start_index"] for a in sequence] != list(range(1, len(sequence) + 1)):
                raise ValueError("attempt stream is incomplete or duplicated")
            for attempt in sequence:
                if attempt["instance_id"] != problem["instance_id"] or \
                        attempt["family_id"] != problem["family_id"]:
                    raise ValueError("attempt crossed its case shard")
                if attempt["evaluation_count_mismatch"]:
                    integrity["evaluation-count-mismatch"] = integrity.get(
                        "evaluation-count-mismatch", 0) + 1
                if attempt["budget_exhausted"] or attempt["evaluations"] > CAPS[variant]:
                    integrity["callback-cap"] = integrity.get("callback-cap", 0) + 1
                if attempt["exception"] is not None:
                    integrity["unhandled-exception"] = integrity.get(
                        "unhandled-exception", 0) + 1
                if variant == config["candidate"]:
                    for violation in _candidate_violations(attempt):
                        safety[violation] = safety.get(violation, 0) + 1
            observed = assessor_snapshot(sequence, target_count)
            suffix = suffix_stable_work(sequence, target_count)
            work = suffix if suffix is not None and suffix <= PREFIXES[-1] else PREFIXES[-1]
            recorded = summaries[(variant, PREFIXES[-1])]
            if (recorded["completed_attempts"] != len(sequence)
                    or recorded["assessor_qualified_targets_found"] != observed["targets"]
                    or recorded["assessor_safe_all_targets"] != observed["safe_full"]
                    or recorded["evaluations"] != observed["evaluations"]
                    or recorded["right_censored_assessor_safe_full_work"] != work):
                raise ValueError("raw attempt reaggregation disagrees with runner summary")
            metrics[variant]["targets"] += observed["targets"]
            metrics[variant]["safe_full"] += int(observed["safe_full"])
            metrics[variant]["work"] += work
            metrics[variant]["stratum_targets"][problem["family_id"]] += observed["targets"]
            if variant == config["candidate"] and problem["family_id"] == STRATA[-1]:
                guard_safe = observed["safe_full"]
                recoveries = sum(
                    _recovery(attempt, config["recovery_keys"]) for attempt in sequence
                )
                if recorded[config["recovery_field"]] != recoveries:
                    raise ValueError("raw StrictGuard recovery count disagrees with summary")

    gate = _gate(
        metrics[CONTROL],
        metrics[config["candidate"]],
        guard_safe=guard_safe,
        recoveries=recoveries,
        violations=sum(safety.values()),
        integrity=sum(integrity.values()),
        truth_audit=truth_audit,
        mechanism_tests=mechanism_tests,
    )
    return {
        "experiment_id": config["experiment_id"],
        "candidate": config["candidate"],
        "execution_revision": execution_head,
        "preregistration_sha256": prereg_hash,
        "shard_count": len(documents),
        "attempt_count": sum(len(document["attempts"]) for document in documents),
        "summary_count": sum(len(document["summaries"]) for document in documents),
        "raw_reaggregation_mismatches": 0,
        "metrics": metrics,
        "candidate_safety_violations": safety,
        "all_variant_integrity_violations": integrity,
        "strict_guard": {"safe_full": guard_safe, "qualified_recoveries": recoveries},
        "promotion_gate": gate,
    }


def aggregate(output_dir: Path, summary: Path, truth_audit: str,
              mechanism_tests: str) -> dict[str, Any]:
    head = require_clean()
    result = {
        "schema": "geotarget.local-t0-wave-008-009/v1",
        "execution_revision": head,
        "experiments": {
            experiment: _load_experiment(
                experiment, output_dir, head, truth_audit, mechanism_tests
            )
            for experiment in CONFIGS
        },
    }
    for control in (CONTROL, SECONDARY):
        controls = [
            value["metrics"][control] for value in result["experiments"].values()
        ]
        if controls[0] != controls[1]:
            raise ValueError(f"paired control metrics disagree for {control}")
    result["paired_control_agreement"] = True
    if summary.exists():
        raise FileExistsError(f"refusing to replace summary: {summary}")
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--output-dir", type=Path, default=RAW)
    run.add_argument("--jobs", type=int, default=MAX_JOBS)
    run.add_argument("--julia", default="julia")
    collect = commands.add_parser("aggregate")
    collect.add_argument("--output-dir", type=Path, default=RAW)
    collect.add_argument(
        "--summary", type=Path, default=RAW / "exp-local-008-009-t0-summary.json"
    )
    collect.add_argument("--truth-leak-audit", choices=("pending", "pass", "fail"),
                         default="pending")
    collect.add_argument("--mechanism-tests", choices=("pending", "pass", "fail"),
                         default="pending")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "run":
        run_wave(args.output_dir.resolve(), args.jobs, args.julia)
    else:
        result = aggregate(args.output_dir.resolve(), args.summary.resolve(),
                           args.truth_leak_audit, args.mechanism_tests)
        for experiment, value in result["experiments"].items():
            print(f"EXP-LOCAL-{experiment}: " + json.dumps(value["promotion_gate"],
                                                              sort_keys=True))
        print(f"summary={args.summary.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
