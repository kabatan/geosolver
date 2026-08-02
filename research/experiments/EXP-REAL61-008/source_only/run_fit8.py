#!/usr/bin/env python3
"""Memory-safe paired fit8 for the frozen source-only policy packet."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Queue
import sys
from typing import Mapping, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    Limits,
    atomic_write_json,
    run_guarded,
)


MANIFEST = ROOT / "research/corpora/real-geometry-61/development-v3/manifest.json"
MANIFEST_SHA256 = "18971c481f44cdcccf7cfc800efe7d59aeaf378ee2b74b413feb1c139c02a53d"
SPLIT = ROOT / "research/experiments/EXP-REAL61-005/t0_runner/development_v3_fit8_confirm12.json"
SPLIT_SHA256 = "24ead28b27d4333ed543866418e0450336f4f8a26a7cd4da2241240b4eabf92a"
FIT8 = (
    "P09-6d4cb1acfa",
    "P15-a16eb27b4f",
    "P06-40bef653a3",
    "P14-8cfa9166a0",
    "P05-3c32a7ea69",
    "P10-70ba249255",
    "P20-ef367dd757",
    "P04-34a25a7218",
)
CONTROL = "analytic_forward_ad_cpqr"
CANDIDATE = "analytic_forward_ad_lsmr"
ARMS = (CONTROL, CANDIDATE)
TRIAL_SCHEMA = "geotarget.exp-real61-008.source-only-trial/v1"
SECONDS = 10.0
STARTS = 16
CALLBACKS_PER_START = 600
SEED = 0
ONE_GIB = 1024**3


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verify_freeze() -> dict[str, object]:
    packet = json.loads((HERE / "FREEZE.json").read_text(encoding="utf-8"))
    for relative, expected in packet["file_sha256"].items():
        path = HERE / relative
        if _sha256(path.read_bytes()) != expected:
            raise RuntimeError(f"frozen source-only file drift: {relative}")
    return packet


def _bindings() -> dict[str, dict[str, object]]:
    if _sha256(MANIFEST.read_bytes()) != MANIFEST_SHA256:
        raise RuntimeError("development-v3 manifest changed")
    if _sha256(SPLIT.read_bytes()) != SPLIT_SHA256:
        raise RuntimeError("fit8 split changed")
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    if tuple(row["case_id"] for row in split["partitions"]["fit"]) != FIT8:
        raise RuntimeError("fit8 case order changed")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = {row["case_id"]: row for row in manifest["cases"]}
    result: dict[str, dict[str, object]] = {}
    for case_id in FIT8:
        row = rows[case_id]
        path = (MANIFEST.parent / row["dsl"]["path"]).resolve()
        digest = str(row["dsl"]["sha256"])
        if _sha256(path.read_bytes()) != digest:
            raise RuntimeError(f"source digest mismatch: {case_id}")
        result[case_id] = {"path": path, "sha256": digest}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--cpus", default="4,5")
    parser.add_argument(
        "--output", type=Path, default=HERE / "results/fit8-source-only-paired10s-seed0"
    )
    arguments = parser.parse_args()
    cpus = tuple(int(item) for item in arguments.cpus.split(",") if item.strip())
    if arguments.jobs < 1 or arguments.jobs > 4 or len(cpus) < arguments.jobs:
        raise SystemExit("jobs must be 1..4 and have one listed CPU each")
    if len(set(cpus[: arguments.jobs])) != arguments.jobs:
        raise SystemExit("worker CPU list contains duplicates")
    freeze = _verify_freeze()
    bindings = _bindings()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    queue: Queue[int] = Queue()
    for cpu in cpus[: arguments.jobs]:
        queue.put(cpu)
    limits = Limits(
        timeout_seconds=SECONDS + 3.0,
        rss_bytes=256 * 1024**2,
        address_space_bytes=3 * ONE_GIB,
        data_bytes=3 * ONE_GIB,
        output_bytes=64 * 1024,
        tail_bytes=8 * 1024,
    )

    def run_one(case_id: str, arm: str, cap: int | None) -> dict[str, object]:
        cpu = queue.get()
        binding = bindings[case_id]
        try:
            result_path = output / arm / f"{case_id}.json"
            status_path = output / "process-status" / arm / f"{case_id}.json"
            result_path.unlink(missing_ok=True)
            command = [
                "taskset",
                "-c",
                str(cpu),
                sys.executable,
                str(HERE / "worker.py"),
                "--case",
                str(binding["path"]),
                "--case-sha256",
                str(binding["sha256"]),
                "--arm",
                arm,
                "--seconds",
                str(SECONDS),
                "--starts",
                str(STARTS),
                "--callbacks-per-start",
                str(CALLBACKS_PER_START),
                "--seed",
                str(SEED),
                "--output",
                str(result_path),
            ]
            if cap is not None:
                command.extend(("--aggregate-callback-cap", str(max(1, cap))))
            guarded = run_guarded(
                command,
                limits=limits,
                environment={"PYTHONHASHSEED": "0"},
                status_path=status_path,
            )
            result = None
            if guarded.accepted_output and result_path.is_file():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    result = None
            accepted = bool(
                guarded.accepted_output
                and isinstance(result, Mapping)
                and result.get("schema_version") == TRIAL_SCHEMA
                and result.get("completed") is True
                and result.get("arm") == arm
                and result.get("source_sha256") == binding["sha256"]
                and result.get("source_bytes_unchanged") is True
                and result.get("explicit_source_bounds_only") is True
                and result.get("source_semantics_modified") is False
                and result.get("gauge_or_symmetry_reduction") is False
                and result.get("truth_used") is False
                and float(result.get("elapsed_wall_seconds", math.inf)) <= SECONDS + 0.25
                and _sha256(Path(binding["path"]).read_bytes()) == binding["sha256"]
            )
            return {
                "case_id": case_id,
                "arm": arm,
                "actual_callback_cap": cap,
                "accepted": accepted,
                "process_classification": guarded.classification,
                "peak_rss_bytes": guarded.peak_process_group_rss_bytes,
                "result": result,
            }
        finally:
            queue.put(cpu)

    def wave(items: Sequence[tuple[str, str, int | None]]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=arguments.jobs) as executor:
            futures = [executor.submit(run_one, *item) for item in items]
            for future in as_completed(futures):
                rows.append(future.result())
        return sorted(rows, key=lambda row: (str(row["case_id"]), str(row["arm"])))

    controls = wave([(case_id, CONTROL, None) for case_id in FIT8])
    caps = {
        str(row["case_id"]): max(
            1,
            int(row["result"].get("work", {}).get("callbacks", 0))
            if row["accepted"] and isinstance(row["result"], Mapping)
            else 1,
        )
        for row in controls
    }
    candidates = wave([(case_id, CANDIDATE, caps[case_id]) for case_id in FIT8])
    rows = controls + candidates
    aggregate = {
        arm: {
            "trials": len(FIT8),
            "accepted": 0,
            "safe_cases": 0,
            "safe_endpoints": 0,
            "diagnostic_clusters": 0,
            "callbacks": 0,
            "peak_rss_bytes": 0,
        }
        for arm in ARMS
    }
    compact = []
    for row in sorted(rows, key=lambda item: (str(item["case_id"]), str(item["arm"]))):
        totals = aggregate[str(row["arm"])]
        totals["peak_rss_bytes"] = max(
            int(totals["peak_rss_bytes"]), int(row["peak_rss_bytes"])
        )
        result = row["result"]
        if row["accepted"] and isinstance(result, Mapping):
            safe = int(result.get("safe_endpoint_count", 0))
            totals["accepted"] += 1
            totals["safe_cases"] += int(safe > 0)
            totals["safe_endpoints"] += safe
            totals["diagnostic_clusters"] += int(
                result.get("diagnostic_distinct_target_count", 0)
            )
            totals["callbacks"] += int(result.get("work", {}).get("callbacks", 0))
        compact.append(
            {
                "case_id": row["case_id"],
                "arm": row["arm"],
                "accepted": row["accepted"],
                "actual_callback_cap": row["actual_callback_cap"],
                "process_classification": row["process_classification"],
                "peak_rss_bytes": row["peak_rss_bytes"],
                "work": result.get("work") if isinstance(result, Mapping) else None,
                "safe_endpoint_count": (
                    result.get("safe_endpoint_count") if isinstance(result, Mapping) else 0
                ),
                "policy_packet": (
                    result.get("policy_packet") if isinstance(result, Mapping) else None
                ),
                "activation": (
                    result.get("activation") if isinstance(result, Mapping) else None
                ),
            }
        )
    for case_id in FIT8:
        pair = [
            row for row in rows if row["case_id"] == case_id and row["accepted"] is True
        ]
        if len(pair) == 2:
            digests = {row["result"]["policy_packet"]["prefix_sha256"] for row in pair}
            if len(digests) != 1:
                raise RuntimeError(f"paired prefix mismatch: {case_id}")
    summary = {
        "schema_version": "geotarget.exp-real61-008.source-only-fit8/v1",
        "status": "COMPLETE",
        "formal_authority": False,
        "truth_used_by_workers": False,
        "source_cases_modified": False,
        "freeze": freeze,
        "configuration": {
            "seconds": SECONDS,
            "starts": STARTS,
            "callbacks_per_start": CALLBACKS_PER_START,
            "seed": SEED,
            "jobs": arguments.jobs,
            "cpus": list(cpus[: arguments.jobs]),
            "paired_candidate_caps_from_control_actual_callbacks": True,
        },
        "aggregate": aggregate,
        "rows": compact,
    }
    atomic_write_json(HERE / "FIT8_RESULT.json", summary)


if __name__ == "__main__":
    main()
