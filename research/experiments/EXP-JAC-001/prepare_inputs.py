from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parent
PROJECT = EXPERIMENT_ROOT
MATERIALIZER = EXPERIMENT_ROOT / "materialize_inputs.jl"
FROZEN_ROOT = EXPERIMENT_ROOT / "frozen"
PREREGISTRATION = FROZEN_ROOT / "EXP-JAC-001-preregistered.json"
CARD = REPO_ROOT / "research" / "experiments" / "EXP-JAC-001.json"
BENCHMARK_ROOT = REPO_ROOT / "benchmarks" / "manifests"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_bytes(canonical_json_bytes(value) + b"\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_gzip_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("wb") as binary:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=binary,
                compresslevel=9,
                mtime=0,
            ) as stream:
                stream.write(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("frozen input must be a JSON object")
    return value


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def input_manifest(
    document: dict[str, Any],
    artifact_path: Path,
    raw_sha256: str,
) -> dict[str, Any]:
    instances = document["instances"]
    return {
        "schema_version": "exp-jac-001-input-manifest/v1",
        "experiment_id": "EXP-JAC-001",
        "partition": document["partition"],
        "locked_validation": document["locked_validation"],
        "artifact": relative(artifact_path),
        "compression": "gzip-level-9-mtime-0",
        "compressed_sha256": sha256_file(artifact_path),
        "uncompressed_sha256": raw_sha256,
        "card_sha256": document["card_sha256"],
        "plugin_lock_sha256": document["plugin_lock_sha256"],
        "instance_count": document["instance_count"],
        "starts_per_instance": document["starts_per_instance"],
        "prefixes": document["prefixes"],
        "variants": document["variants"],
        "seed_namespaces": document["seed_namespaces"],
        "thresholds": document["thresholds"],
        "analysis_contract": document["analysis_contract"],
        "instances": [
            {
                "case_id": instance["case_id"],
                "family_id": instance["family_id"],
                "generator_id": instance["generator_id"],
                "instance_seed": instance["instance_seed"],
                "start_seed": instance["start_seed"],
                "problem_sha256": instance["problem_sha256"],
                "starts_sha256": instance["starts_sha256"],
                "truth_sha256": instance["truth_sha256"],
                "pattern_sha256": instance["pattern_sha256"],
                "dense_traces_sha256": instance["dense_traces_sha256"],
            }
            for instance in instances
        ],
    }


def benchmark_manifest(document: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    partition = document["partition"]
    development = partition == "development"
    return {
        "schema_version": "1.0.0",
        "benchmark_id": f"BENCH-EXP-JAC-001-{partition.upper()}",
        "manifest_version": "1.0.0",
        "status": "development" if development else "locked",
        "partition": "D1" if development else "V1",
        "access_policy": (
            "Development inputs are inspectable after checksum freeze."
            if development
            else "Locked inputs may be executed only after the preregistered development gate passes."
        ),
        "family_grouping_rule": (
            "Cluster by the exact family_id; starts remain paired within a materialized case."
        ),
        "truth_policy": (
            "Analytic roots and Jacobians are materialized independently of coloring and are unavailable to production routing."
        ),
        "tested_envelope_ref": "ENVELOPE-M0-M4-1",
        "budgets_seconds": [60, 180],
        "seed_count": 10 if development else 30,
        "metrics": [
            "oracle_work_per_local_attempt",
            "p_local_gold",
            "jacobian_callback_reduction",
            "warm_wall_per_attempt",
            "fallback_fraction",
            "dense_colored_mismatch_count",
            "false_candidate_count",
            "budget_overrun_count",
        ],
        "cases": [
            {
                "case_id": instance["case_id"],
                "family_id": instance["family_id"],
                "generator_id": instance["generator_id"],
                "instance_id": instance["case_id"],
                "problem_sha256": instance["problem_sha256"],
                "truth_level": "analytic",
                "truth_artifact": f"{relative(artifact_path)}#{instance['case_id']}",
                "truth_sha256": instance["truth_sha256"],
                "exact_eligible": False,
                "strata": instance["strata"],
                "unknown_level": "U1" if development else "U3",
            }
            for instance in document["instances"]
        ],
    }


def materialize(partition: str, *, force: bool = False) -> tuple[Path, Path, Path]:
    artifact_path = FROZEN_ROOT / f"{partition}-inputs.json.gz"
    manifest_path = EXPERIMENT_ROOT / f"{partition}-input-manifest.json"
    benchmark_path = BENCHMARK_ROOT / f"exp-jac-001-{partition}.json"
    outputs = (artifact_path, manifest_path, benchmark_path)
    if not force and any(path.exists() for path in outputs):
        raise FileExistsError(f"refusing to overwrite frozen {partition} inputs")
    if not PREREGISTRATION.exists():
        write_json_atomic(PREREGISTRATION, json.loads(CARD.read_text(encoding="utf-8")))
    elif json.loads(PREREGISTRATION.read_text(encoding="utf-8")) != json.loads(
        CARD.read_text(encoding="utf-8")
    ):
        raise ValueError(
            "current experiment card differs from the frozen preregistration"
        )

    with tempfile.TemporaryDirectory(prefix=f"exp-jac-001-{partition}-") as directory:
        raw_path = Path(directory) / "inputs.json"
        subprocess.run(
            [
                "julia",
                "+1.12.6",
                "--startup-file=no",
                "--history-file=no",
                f"--project={PROJECT}",
                str(MATERIALIZER),
                partition,
                str(raw_path),
            ],
            cwd=REPO_ROOT,
            check=True,
        )
        raw = raw_path.read_bytes()
        document = json.loads(raw)
        if document["partition"] != partition:
            raise ValueError("materializer returned the wrong partition")
        write_gzip_atomic(artifact_path, raw)
        replay = load_gzip_json(artifact_path)
        if replay != document:
            raise ValueError("deterministic gzip round trip changed the frozen input")
        write_json_atomic(
            manifest_path, input_manifest(document, artifact_path, sha256_bytes(raw))
        )
        write_json_atomic(benchmark_path, benchmark_manifest(document, artifact_path))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze EXP-JAC-001 inputs before outcomes"
    )
    parser.add_argument(
        "--partition",
        choices=("development", "locked", "all"),
        default="all",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    partitions = (
        ("development", "locked") if args.partition == "all" else (args.partition,)
    )
    for partition in partitions:
        outputs = materialize(partition, force=args.force)
        print(f"froze {partition}: " + ", ".join(relative(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
