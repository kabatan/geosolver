from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import platform
import random
import subprocess
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

EXPERIMENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_ROOT.parents[2]
RESULT_ROOT = REPO_ROOT / "research" / "results" / "EXP-JAC-001"
PROJECT = EXPERIMENT_ROOT
WORKER = EXPERIMENT_ROOT / "run_variant.jl"

PREPARE_SPEC = importlib.util.spec_from_file_location(
    "exp_jac_prepare", EXPERIMENT_ROOT / "prepare_inputs.py"
)
assert PREPARE_SPEC is not None and PREPARE_SPEC.loader is not None
PREPARE = importlib.util.module_from_spec(PREPARE_SPEC)
PREPARE_SPEC.loader.exec_module(PREPARE)

VALIDATE_SPEC = importlib.util.spec_from_file_location(
    "research_validate", REPO_ROOT / "research" / "validate.py"
)
assert VALIDATE_SPEC is not None and VALIDATE_SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(VALIDATE_SPEC)
VALIDATE_SPEC.loader.exec_module(VALIDATE)

VARIANT_SLUGS = {
    "J0-DENSE-CENTRAL": "j0",
    "J1-GREEDY-COLOR": "j1",
    "J2-LARGEST-FIRST-COLOR": "j2",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def write_json_atomic(path: Path, value: Any) -> None:
    PREPARE.write_json_atomic(path, value)


def write_gzip_json_atomic(path: Path, value: Any) -> None:
    PREPARE.write_gzip_atomic(path, canonical_json_bytes(value))


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def load_gzip_json(path: Path) -> dict[str, Any]:
    return PREPARE.load_gzip_json(path)


def frozen_paths(partition: str) -> tuple[Path, Path, Path]:
    return (
        EXPERIMENT_ROOT / "frozen" / f"{partition}-inputs.json.gz",
        EXPERIMENT_ROOT / f"{partition}-input-manifest.json",
        REPO_ROOT / "benchmarks" / "manifests" / f"exp-jac-001-{partition}.json",
    )


def verify_frozen(partition: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    artifact, manifest_path, benchmark_path = frozen_paths(partition)
    manifest = load_json(manifest_path)
    if manifest["partition"] != partition:
        raise ValueError(f"{partition} input manifest has wrong partition")
    if sha256_file(artifact) != manifest["compressed_sha256"]:
        raise ValueError(f"{partition} compressed input checksum mismatch")
    raw = gzip.decompress(artifact.read_bytes())
    if sha256_bytes(raw) != manifest["uncompressed_sha256"]:
        raise ValueError(f"{partition} uncompressed input checksum mismatch")
    document = json.loads(raw)
    if document["partition"] != partition:
        raise ValueError(f"{partition} input payload has wrong partition")
    if document["card_sha256"] != manifest["card_sha256"]:
        raise ValueError(f"{partition} card checksum mismatch")
    benchmark = load_json(benchmark_path)
    schema = load_json(
        REPO_ROOT / "research" / "schemas" / "benchmark-manifest.schema.json"
    )
    errors = VALIDATE.validate_instance(benchmark, schema)
    if errors:
        raise ValueError("invalid benchmark manifest: " + "; ".join(errors))
    return document, manifest, artifact


def worker_paths(partition: str, variant: str) -> tuple[Path, Path, Path]:
    slug = VARIANT_SLUGS[variant]
    worker_root = RESULT_ROOT / "workers"
    return (
        worker_root / f"{partition}-{slug}.json.gz",
        worker_root / f"{partition}-{slug}.stdout.txt",
        worker_root / f"{partition}-{slug}.stderr.txt",
    )


def run_worker(
    partition: str,
    variant: str,
    artifact: Path,
    *,
    force: bool,
) -> tuple[dict[str, Any], dict[str, str]]:
    output_gzip, stdout_path, stderr_path = worker_paths(partition, variant)
    if output_gzip.exists() and not force:
        result = load_gzip_json(output_gzip)
        return result, {
            "started_at": "reused",
            "finished_at": "reused",
            "stdout": relative(stdout_path),
            "stderr": relative(stderr_path),
        }
    output_gzip.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    with tempfile.TemporaryDirectory(
        prefix=f"exp-jac-worker-{partition}-"
    ) as directory:
        raw_input = Path(directory) / "input.json"
        raw_output = Path(directory) / "output.json"
        raw_input.write_bytes(gzip.decompress(artifact.read_bytes()))
        environment = os.environ.copy()
        environment["JULIA_NUM_THREADS"] = "1"
        environment["OPENBLAS_NUM_THREADS"] = "1"
        process = subprocess.run(
            [
                "julia",
                "+1.12.6",
                "--startup-file=no",
                "--history-file=no",
                f"--project={PROJECT}",
                str(WORKER),
                str(raw_input),
                str(raw_output),
                variant,
            ],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        stdout_path.write_text(process.stdout, encoding="utf-8")
        stderr_path.write_text(process.stderr, encoding="utf-8")
        if process.returncode != 0:
            raise RuntimeError(
                f"{partition} {variant} worker failed; see {relative(stderr_path)}"
            )
        raw = raw_output.read_bytes()
        PREPARE.write_gzip_atomic(output_gzip, raw)
        result = json.loads(raw)
    return result, {
        "started_at": started,
        "finished_at": utc_now(),
        "stdout": relative(stdout_path),
        "stderr": relative(stderr_path),
    }


def paired_rows(
    control: dict[str, Any], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    controls = {
        (row["case_id"], row["start_index"]): row for row in control["attempts"]
    }
    candidates = {
        (row["case_id"], row["start_index"]): row for row in candidate["attempts"]
    }
    if controls.keys() != candidates.keys():
        raise ValueError("paired variant key sets differ")
    pairs: list[dict[str, Any]] = []
    for key in sorted(controls):
        j0 = controls[key]
        jx = candidates[key]
        if j0["family_id"] != jx["family_id"] or j0["factors"] != jx["factors"]:
            raise ValueError(f"paired metadata drift at {key}")
        work_reduction = (
            (j0["oracle_work"] - jx["oracle_work"]) / j0["oracle_work"]
            if j0["oracle_work"]
            else 0.0
        )
        jacobian_reduction = (
            (j0["jacobian_callbacks"] - jx["jacobian_callbacks"])
            / j0["jacobian_callbacks"]
            if j0["jacobian_callbacks"]
            else 0.0
        )
        wall_overhead = (
            (jx["wall_seconds"] - j0["wall_seconds"]) / j0["wall_seconds"]
            if j0["wall_seconds"]
            else 0.0
        )
        pairs.append(
            {
                "case_id": key[0],
                "start_index": key[1],
                "family_id": j0["family_id"],
                "factors": j0["factors"],
                "j0_gold": bool(j0["gold_valid"]),
                "candidate_gold": bool(jx["gold_valid"]),
                "j0_false": bool(j0["false_candidate"]),
                "candidate_false": bool(jx["false_candidate"]),
                "j0_budget_overrun": bool(j0["budget_overrun"]),
                "candidate_budget_overrun": bool(jx["budget_overrun"]),
                "j0_oracle_work": int(j0["oracle_work"]),
                "candidate_oracle_work": int(jx["oracle_work"]),
                "work_reduction": work_reduction,
                "j0_jacobian_callbacks": int(j0["jacobian_callbacks"]),
                "candidate_jacobian_callbacks": int(jx["jacobian_callbacks"]),
                "jacobian_callback_reduction": jacobian_reduction,
                "j0_wall_seconds": float(j0["wall_seconds"]),
                "candidate_wall_seconds": float(jx["wall_seconds"]),
                "wall_overhead": wall_overhead,
                "candidate_fallback_groups": int(jx["fallback_groups"]),
                "candidate_color_groups": int(jx["color_groups_evaluated"]),
            }
        )
    return pairs


def mean_bool(rows: list[dict[str, Any]], key: str) -> float:
    return fmean(float(bool(row[key])) for row in rows) if rows else 0.0


def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "attempts": len(rows),
        "mean_oracle_work_reduction": fmean(row["work_reduction"] for row in rows),
        "mean_jacobian_callback_reduction": fmean(
            row["jacobian_callback_reduction"] for row in rows
        ),
        "j0_p_local_gold": mean_bool(rows, "j0_gold"),
        "candidate_p_local_gold": mean_bool(rows, "candidate_gold"),
        "p_local_gold_delta": mean_bool(rows, "candidate_gold")
        - mean_bool(rows, "j0_gold"),
        "j0_false_candidate_count": sum(row["j0_false"] for row in rows),
        "candidate_false_candidate_count": sum(row["candidate_false"] for row in rows),
        "budget_overrun_count": sum(
            row["j0_budget_overrun"] or row["candidate_budget_overrun"] for row in rows
        ),
        "mean_warm_wall_overhead": fmean(row["wall_overhead"] for row in rows),
        "fallback_fraction": (
            sum(row["candidate_fallback_groups"] for row in rows)
            / max(1, sum(row["candidate_color_groups"] for row in rows))
        ),
    }


def family_summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["family_id"]].append(row)
    return {family: group_summary(grouped[family]) for family in sorted(grouped)}


def bootstrap_sparse_reduction(
    rows: list[dict[str, Any]], contract: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    sparse = set(contract["sparse_development_families"])
    selected = [row for row in rows if row["family_id"] in sparse]
    family_order = sorted({row["family_id"] for row in selected})
    case_order = {
        family: sorted(
            {row["case_id"] for row in selected if row["family_id"] == family}
        )
        for family in family_order
    }
    rows_by_case: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        rows_by_case[(row["family_id"], row["case_id"])].append(row)
    generator = random.Random(int(contract["bootstrap_seed"]))
    draws: list[dict[str, Any]] = []
    estimates: list[float] = []
    for _ in range(int(contract["bootstrap_resamples"])):
        family_draw = [generator.randrange(len(family_order)) for _ in family_order]
        case_draws: list[list[int]] = []
        values: list[float] = []
        for family_index in family_draw:
            family = family_order[family_index]
            cases = case_order[family]
            draw = [generator.randrange(len(cases)) for _ in cases]
            case_draws.append(draw)
            for case_index in draw:
                values.extend(
                    row["work_reduction"]
                    for row in rows_by_case[(family, cases[case_index])]
                )
        estimates.append(fmean(values))
        draws.append({"families": family_draw, "cases": case_draws})
    ordered = sorted(estimates)
    quantile = float(contract["one_sided_lower_quantile"])
    lower = ordered[math.floor(quantile * (len(ordered) - 1))]
    metric = {
        "point_estimate": fmean(row["work_reduction"] for row in selected),
        "one_sided_95_lower": lower,
        "resamples": len(estimates),
        "seed": int(contract["bootstrap_seed"]),
        "families": family_order,
    }
    plan = {
        "schema_version": "exp-jac-001-bootstrap/v1",
        "method": contract["bootstrap_method"],
        "seed": int(contract["bootstrap_seed"]),
        "family_order": family_order,
        "case_order": case_order,
        "draws": draws,
        "estimate_sha256": sha256_bytes(canonical_json_bytes(estimates)),
    }
    return metric, plan


def j2_trigger(preflight: dict[str, Any]) -> dict[str, Any]:
    gaps: dict[str, list[float]] = defaultdict(list)
    for row in preflight["per_instance"]:
        gaps[row["family_id"]].append(float(row["relative_gap"]))
    family_mean_gap = {family: fmean(values) for family, values in sorted(gaps.items())}
    triggered_families = [
        family for family, gap in family_mean_gap.items() if gap > 0.20
    ]
    return {
        "definition": "family mean natural-color gap above maximum-row-support lower bound",
        "threshold": 0.20,
        "required_family_count": 3,
        "family_mean_relative_gap": family_mean_gap,
        "triggered_families": triggered_families,
        "triggered": len(triggered_families) >= 3,
    }


def cold_coloring_fraction(
    candidate: dict[str, Any], rows: list[dict[str, Any]]
) -> float:
    wall_by_case: dict[str, float] = defaultdict(float)
    for row in rows:
        wall_by_case[row["case_id"]] += row["candidate_wall_seconds"]
    fractions = [
        float(record["coloring_seconds"]) / wall_by_case[record["case_id"]]
        for record in candidate["cold"]
        if wall_by_case[record["case_id"]] > 0
    ]
    return max(fractions, default=0.0)


def critical_recall_loss(rows: list[dict[str, Any]], dense_family: str) -> float:
    critical = [
        row
        for row in rows
        if row["family_id"] == dense_family
        and float(row["factors"].get("boundary_distance", 1.0)) in (0.0, 1.0e-8)
    ]
    if not critical:
        return 0.0
    return max(
        0.0, mean_bool(critical, "j0_gold") - mean_bool(critical, "candidate_gold")
    )


def evaluate_gate(
    control: dict[str, Any],
    candidate: dict[str, Any],
    input_document: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    rows = paired_rows(control, candidate)
    overall = group_summary(rows)
    families = family_summaries(rows)
    contract = input_document["analysis_contract"]
    bootstrap, plan = bootstrap_sparse_reduction(rows, contract)
    dense_family = contract["dense_development_family"]
    sparse_families = contract["sparse_development_families"]
    overall_recall_loss = max(0.0, -overall["p_local_gold_delta"])
    per_family_recall_loss = max(
        (max(0.0, -summary["p_local_gold_delta"]) for summary in families.values()),
        default=0.0,
    )
    boundary_recall_loss = critical_recall_loss(rows, dense_family)
    dense_overhead = families[dense_family]["mean_warm_wall_overhead"]
    cold_fraction = cold_coloring_fraction(candidate, rows)
    repeat_families = [
        family
        for family, summary in families.items()
        if summary["mean_oracle_work_reduction"] > 0
    ]
    family_false_delta_ok = all(
        summary["candidate_false_candidate_count"]
        <= summary["j0_false_candidate_count"]
        for summary in families.values()
    )
    sparse_reduction_min = min(
        families[family]["mean_oracle_work_reduction"] for family in sparse_families
    )
    safety_counts = {
        "dense_colored_mismatch_count": candidate["preflight"][
            "dense_colored_mismatch_count"
        ],
        "dense_outside_pattern_count": candidate["preflight"][
            "dense_outside_pattern_count"
        ],
        "fallback_control_failure_count": candidate["preflight"][
            "fallback_control_failure_count"
        ],
        "false_candidate_count": overall["candidate_false_candidate_count"],
        "budget_overrun_count": overall["budget_overrun_count"],
    }
    criteria = {
        "zero_safety_counts": all(value == 0 for value in safety_counts.values()),
        "sparse_work_reduction_at_least_20_percent": bootstrap["point_estimate"]
        >= 0.20,
        "sparse_family_clustered_lower_above_zero": bootstrap["one_sided_95_lower"] > 0,
        "overall_recall_loss_at_most_2_points": overall_recall_loss <= 0.02,
        "family_recall_loss_at_most_2_points": per_family_recall_loss <= 0.02,
        "critical_recall_loss_at_most_2_points": boundary_recall_loss <= 0.02,
        "dense_warm_overhead_at_most_5_percent": dense_overhead <= 0.05,
        "cold_coloring_below_1_percent": cold_fraction < 0.01,
        "work_reduction_in_three_families": len(repeat_families) >= 3,
        "no_positive_false_target_delta": family_false_delta_ok,
    }
    kill = {
        "omitted_dependency": safety_counts["dense_outside_pattern_count"] > 0,
        "fallback_retry_failure": safety_counts["fallback_control_failure_count"] > 0,
        "critical_recall_loss_over_2_points": boundary_recall_loss > 0.02,
        "sparse_reduction_below_10_percent": sparse_reduction_min < 0.10,
        "dense_overhead_over_5_without_recall_gain": dense_overhead > 0.05
        and families[dense_family]["p_local_gold_delta"] <= 0,
    }
    prefix = {
        str(limit): group_summary([row for row in rows if row["start_index"] <= limit])
        for limit in input_document["prefixes"]
    }
    gate = {
        "overall": overall,
        "families": families,
        "prefixes": prefix,
        "sparse_bootstrap": bootstrap,
        "safety_counts": safety_counts,
        "overall_recall_loss": overall_recall_loss,
        "maximum_family_recall_loss": per_family_recall_loss,
        "critical_boundary_recall_loss": boundary_recall_loss,
        "dense_mean_warm_overhead": dense_overhead,
        "maximum_cold_coloring_fraction": cold_fraction,
        "repeat_reduction_families": repeat_families,
        "promotion_criteria": criteria,
        "kill_criteria": kill,
        "promotion_gate_passed": all(criteria.values()),
        "kill_gate_fired": any(kill.values()),
    }
    return gate, rows, plan


def choose_candidate(
    j0: dict[str, Any],
    j1: dict[str, Any],
    j2: dict[str, Any] | None,
    input_document: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    gate1, rows1, plan1 = evaluate_gate(j0, j1, input_document)
    if j2 is None:
        return "J1-GREEDY-COLOR", j1, gate1, rows1, plan1
    gate2, rows2, plan2 = evaluate_gate(j0, j2, input_document)
    safe2 = all(value == 0 for value in gate2["safety_counts"].values())
    recall2 = gate2["maximum_family_recall_loss"] <= 0.02
    if (
        safe2
        and recall2
        and gate2["overall"]["mean_oracle_work_reduction"]
        > gate1["overall"]["mean_oracle_work_reduction"]
    ):
        return "J2-LARGEST-FIRST-COLOR", j2, gate2, rows2, plan2
    return "J1-GREEDY-COLOR", j1, gate1, rows1, plan1


def environment_record() -> dict[str, Any]:
    julia_version = subprocess.run(
        ["julia", "+1.12.6", "--startup-file=no", "-e", "print(VERSION)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "julia_version": julia_version,
        "python_version": platform.python_version(),
        "manifest_sha256": sha256_file(PROJECT / "Manifest.toml"),
        "os": platform.platform(),
        "architecture": platform.machine() or "unknown",
        "cpu": platform.processor()
        or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "julia_threads": 1,
        "blas_threads": 1,
    }


def run_manifest(
    partition: str,
    variant: str,
    input_manifest: dict[str, Any],
    benchmark_path: Path,
    timing: dict[str, str],
) -> dict[str, Any]:
    repository_commit = git("rev-parse", "HEAD")
    policy = {
        "variant": variant,
        "max_iterations": input_manifest["thresholds"]["max_iterations"],
        "max_evaluations": input_manifest["thresholds"]["max_evaluations"],
        "color_order": "largest_first" if variant.startswith("J2") else "natural",
    }
    output, stdout_path, stderr_path = worker_paths(partition, variant)
    return {
        "schema_version": "1.0.0",
        "run_id": f"RUN-EXP-JAC-001-{partition.upper()}-{VARIANT_SLUGS[variant].upper()}",
        "experiment_id": "EXP-JAC-001",
        "variant_id": variant,
        "started_at": timing["started_at"]
        if timing["started_at"] != "reused"
        else utc_now(),
        "finished_at": timing["finished_at"]
        if timing["finished_at"] != "reused"
        else utc_now(),
        "repository": {
            "commit": repository_commit,
            "dirty": False,
            "branch": git("branch", "--show-current"),
        },
        "environment": environment_record(),
        "problem": {
            "benchmark_manifest": relative(benchmark_path),
            "case_id": f"ALL-{partition.upper()}",
            "family_id": "ALL-FROZEN-FAMILIES",
            "problem_sha256": input_manifest["uncompressed_sha256"],
            "plugin_lock_sha256": input_manifest["plugin_lock_sha256"],
        },
        "policy": {
            "baseline_id": "RB0-IID-LMQR-1",
            "policy_id": variant,
            "policy_sha256": sha256_bytes(canonical_json_bytes(policy)),
            "card_sha256": input_manifest["card_sha256"],
        },
        "randomness": {
            "seed": 0,
            "generator": "frozen materialized starts; see input manifest seed namespaces",
            "proposal_artifact": input_manifest["artifact"],
            "proposal_sha256": input_manifest["compressed_sha256"],
        },
        "budget": {
            "wall_seconds": 60,
            "launch_limit": 32,
            "local_maxiters": input_manifest["thresholds"]["max_iterations"],
            "includes_compile": True,
            "includes_screening": False,
        },
        "artifacts": {
            "evidence_log": relative(output),
            "summary": "research/results/EXP-JAC-001/summary.json",
            "stdout": relative(stdout_path),
            "stderr": relative(stderr_path),
        },
        "status": "completed",
    }


def validate_run_manifest(manifest: dict[str, Any]) -> None:
    schema = load_json(REPO_ROOT / "research" / "schemas" / "run-manifest.schema.json")
    errors = VALIDATE.validate_instance(manifest, schema)
    if errors:
        raise ValueError("invalid run manifest: " + "; ".join(errors))


def write_attempts_csv(path: Path, worker_results: list[dict[str, Any]]) -> None:
    rows = [row for result in worker_results for row in result["attempts"]]
    fieldnames = [
        "partition",
        "variant",
        "case_id",
        "family_id",
        "generator_id",
        "start_index",
        "dimension",
        "status",
        "accepted",
        "canonical_valid",
        "gold_valid",
        "false_candidate",
        "budget_overrun",
        "iterations",
        "factorizations",
        "solver_callbacks",
        "validation_callbacks",
        "total_callbacks",
        "oracle_work",
        "jacobian_callbacks",
        "jacobian_constructions",
        "color_groups_evaluated",
        "fallback_groups",
        "fallback_callbacks",
        "color_count",
        "color_lower_bound",
        "structural_nonzeros",
        "wall_seconds",
        "allocated_bytes",
        "gc_seconds",
        "compile_seconds_in_attempt",
        "configuration_error",
        "target_error",
        "factors_json",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="exp-jac-csv-") as directory:
        raw_path = Path(directory) / "attempts.csv"
        with raw_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                output = {key: row.get(key) for key in fieldnames if key != "partition"}
                output["partition"] = next(
                    result["partition"]
                    for result in worker_results
                    if row in result["attempts"]
                )
                output["factors_json"] = canonical_json_bytes(row["factors"]).decode(
                    "utf-8"
                )
                writer.writerow(output)
        PREPARE.write_gzip_atomic(path, raw_path.read_bytes())


def report_text(summary: dict[str, Any]) -> str:
    development = summary["development"]
    gate = development["gate"]
    lines = [
        "# EXP-JAC-001 result",
        "",
        f"Decision: **{summary['decision']['state']}**.",
        "",
        f"Selected development candidate: `{development['selected_variant']}`.",
        f"J2 structural trigger: `{development['j2_trigger']['triggered']}`.",
        f"Promotion gate passed: `{gate['promotion_gate_passed']}`.",
        f"Kill gate fired: `{gate['kill_gate_fired']}`.",
        "",
        "## Key measurements",
        "",
        f"- Dense/colored mismatches: {gate['safety_counts']['dense_colored_mismatch_count']}",
        f"- False candidates: {gate['safety_counts']['false_candidate_count']}",
        f"- Budget overruns: {gate['safety_counts']['budget_overrun_count']}",
        f"- Sparse oracle-work reduction: {gate['sparse_bootstrap']['point_estimate']:.6f}",
        f"- One-sided family-clustered 95% lower bound: {gate['sparse_bootstrap']['one_sided_95_lower']:.6f}",
        f"- Dense warm overhead: {gate['dense_mean_warm_overhead']:.6f}",
        f"- Maximum cold coloring fraction: {gate['maximum_cold_coloring_fraction']:.6f}",
        "",
        "Production routing remains unchanged unless the complete locked gate is recorded as passed.",
        "",
    ]
    return "\n".join(lines)


def artifact_checksums(root: Path) -> dict[str, Any]:
    files = {
        relative(path): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact-checksums.json"
    }
    return {
        "schema_version": "exp-jac-001-artifact-checksums/v1",
        "algorithm": "SHA-256",
        "files": files,
    }


def run_partition(
    partition: str,
    variants: list[str],
    *,
    force: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, str]], dict[str, Any], dict[str, Any]]:
    document, manifest, artifact = verify_frozen(partition)
    results: dict[str, Any] = {}
    timings: dict[str, dict[str, str]] = {}
    for variant in variants:
        results[variant], timings[variant] = run_worker(
            partition,
            variant,
            artifact,
            force=force,
        )
    return results, timings, document, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute preregistered EXP-JAC-001")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if RESULT_ROOT.exists() and not args.force:
        raise FileExistsError("result directory already exists; pass --force to rerun")
    if args.force and RESULT_ROOT.exists():
        # Preserve frozen inputs outside the result directory; outcome artifacts
        # can be replaced only under an explicit force flag.
        import shutil

        shutil.rmtree(RESULT_ROOT)
    status = git("status", "--porcelain")
    if status:
        raise RuntimeError("experiment execution requires a clean committed worktree")
    RESULT_ROOT.mkdir(parents=True, exist_ok=False)

    (
        development_results,
        development_timings,
        development_input,
        development_manifest,
    ) = run_partition(
        "development",
        ["J0-DENSE-CENTRAL", "J1-GREEDY-COLOR"],
        force=args.force,
    )
    j0 = development_results["J0-DENSE-CENTRAL"]
    j1 = development_results["J1-GREEDY-COLOR"]
    trigger = j2_trigger(j1["preflight"])
    j2 = None
    if trigger["triggered"]:
        artifact = frozen_paths("development")[0]
        j2, development_timings["J2-LARGEST-FIRST-COLOR"] = run_worker(
            "development",
            "J2-LARGEST-FIRST-COLOR",
            artifact,
            force=args.force,
        )
        development_results["J2-LARGEST-FIRST-COLOR"] = j2
    selected_variant, selected_result, development_gate, paired, bootstrap_plan = (
        choose_candidate(j0, j1, j2, development_input)
    )
    write_gzip_json_atomic(RESULT_ROOT / "bootstrap-plan.json.gz", bootstrap_plan)

    locked_summary: dict[str, Any] | None = None
    all_worker_results = list(development_results.values())
    all_manifests: list[dict[str, Any]] = []
    development_benchmark = frozen_paths("development")[2]
    for variant, timing in development_timings.items():
        manifest = run_manifest(
            "development",
            variant,
            development_manifest,
            development_benchmark,
            timing,
        )
        validate_run_manifest(manifest)
        write_json_atomic(
            RESULT_ROOT / f"run-development-{VARIANT_SLUGS[variant]}.json",
            manifest,
        )
        all_manifests.append(manifest)

    if development_gate["promotion_gate_passed"]:
        locked_results, locked_timings, locked_input, locked_input_manifest = (
            run_partition(
                "locked",
                ["J0-DENSE-CENTRAL", selected_variant],
                force=args.force,
            )
        )
        locked_j0 = locked_results["J0-DENSE-CENTRAL"]
        locked_candidate = locked_results[selected_variant]
        locked_gate, locked_pairs, locked_bootstrap = evaluate_gate(
            locked_j0,
            locked_candidate,
            {
                **locked_input,
                "analysis_contract": {
                    **locked_input["analysis_contract"],
                    "sparse_development_families": sorted(
                        family
                        for family in {
                            row["family_id"] for row in locked_candidate["attempts"]
                        }
                        if "DENSE" not in family and "BRANCH" not in family
                    ),
                    "dense_development_family": "JAC-MIXED-BRANCH-LOCKED",
                },
            },
        )
        write_gzip_json_atomic(
            RESULT_ROOT / "locked-bootstrap-plan.json.gz", locked_bootstrap
        )
        locked_summary = {
            "selected_variant": selected_variant,
            "gate": locked_gate,
            "paired_attempt_count": len(locked_pairs),
            "family_disjoint_from_development": set(
                row["family_id"] for row in locked_candidate["attempts"]
            ).isdisjoint(row["family_id"] for row in selected_result["attempts"]),
        }
        all_worker_results.extend(locked_results.values())
        locked_benchmark = frozen_paths("locked")[2]
        for variant, timing in locked_timings.items():
            manifest = run_manifest(
                "locked",
                variant,
                locked_input_manifest,
                locked_benchmark,
                timing,
            )
            validate_run_manifest(manifest)
            write_json_atomic(
                RESULT_ROOT / f"run-locked-{VARIANT_SLUGS[variant]}.json",
                manifest,
            )
            all_manifests.append(manifest)
    write_attempts_csv(RESULT_ROOT / "attempts.csv.gz", all_worker_results)

    final_pass = (
        development_gate["promotion_gate_passed"]
        and locked_summary is not None
        and locked_summary["gate"]["promotion_gate_passed"]
    )
    decision = {
        "state": "promoted" if final_pass else "rejected",
        "selected_variant": selected_variant if final_pass else None,
        "production_connected": False,
        "rationale": (
            "Development and family-disjoint locked gates passed; production connection requires a separate reviewed change."
            if final_pass
            else "Development promotion gate did not pass; locked inputs were not inspected and production remains dense."
        ),
    }
    summary = {
        "schema_version": "exp-jac-001-summary/v1",
        "experiment_id": "EXP-JAC-001",
        "repository_commit": git("rev-parse", "HEAD"),
        "card_sha256": development_input["card_sha256"],
        "development_input_manifest_sha256": sha256_file(
            EXPERIMENT_ROOT / "development-input-manifest.json"
        ),
        "locked_input_opened": locked_summary is not None,
        "development": {
            "selected_variant": selected_variant,
            "j2_trigger": trigger,
            "gate": development_gate,
            "paired_attempt_count": len(paired),
        },
        "locked": locked_summary,
        "decision": decision,
        "run_manifest_count": len(all_manifests),
    }
    write_json_atomic(RESULT_ROOT / "summary.json", summary)
    (RESULT_ROOT / "report.md").write_text(report_text(summary), encoding="utf-8")
    write_json_atomic(
        RESULT_ROOT / "artifact-checksums.json", artifact_checksums(RESULT_ROOT)
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
