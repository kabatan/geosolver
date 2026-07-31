#!/usr/bin/env python3
"""Disposable truth-blind screen24 AB runner for the portal Repair A."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Mapping


PYTHON = Path("/home/kabatan/work/solver/.venv/bin/python")
CONTROL = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/champion_v0/search_worker.py"
)
CANDIDATE = Path(__file__).resolve().parent / "portal_search_worker.py"
EXPECTED_CONTROL_SHA = "ce2dd5018037fbe5175fc63a2d20d9463243be58d4deeca3bc7cb1aed44e30bf"
EXPECTED_CANDIDATE_SHA = "ed2613b8ec0cb2ed2655310a321ec0dd532ba9bdf2b33503a216b6df9d9969c4"
ARM = "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm"
THREAD_ENV = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_one(
    worker: Path,
    source: Path,
    source_sha: str,
    output: Path,
    seed: int,
) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(THREAD_ENV)
    started = time.monotonic()
    completed = subprocess.run(
        [
            str(PYTHON),
            str(worker),
            "--case",
            str(source),
            "--case-sha256",
            source_sha,
            "--arm",
            ARM,
            "--seconds",
            "5",
            "--starts",
            "256",
            "--callbacks-per-start",
            "600",
            "--aggregate-callback-cap",
            "153600",
            "--seed",
            str(seed),
            "--output",
            str(output),
        ],
        cwd=worker.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=9.0,
    )
    wall = time.monotonic() - started
    if completed.returncode != 0 or not output.is_file():
        return {
            "ok": False,
            "returncode": completed.returncode,
            "wall": wall,
            "stderr_tail": completed.stderr[-300:],
        }
    document = json.loads(output.read_text(encoding="utf-8"))
    work = document.get("work") if isinstance(document, Mapping) else None
    safety = bool(
        isinstance(document, Mapping)
        and document.get("completed") is True
        and document.get("source_sha256") == source_sha
        and document.get("source_bytes_unchanged") is True
        and document.get("source_evaluator_compiled_from_original_document") is True
        and document.get("source_semantics_modified") is False
        and document.get("added_or_inferred_search_bounds") is False
        and document.get("gauge_or_symmetry_reduction") is False
        and document.get("candidate_received_case_id_family_truth_or_target_count") is False
        and document.get("truth_used") is False
        and document.get("completeness_claim") is False
    )
    return {
        "ok": safety,
        "wall": wall,
        "safe_endpoint_count": int(document.get("safe_endpoint_count", 0)),
        "diagnostic_distinct_target_count": int(
            document.get("diagnostic_distinct_target_count", 0)
        ),
        "callbacks": int(work.get("callbacks", 0)) if isinstance(work, Mapping) else 0,
        "lanes_started": int(work.get("lanes_started", 0)) if isinstance(work, Mapping) else 0,
        "worker_elapsed": float(document.get("elapsed_wall_seconds", math.nan)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    arguments = parser.parse_args()
    if sorted(os.sched_getaffinity(0)) != [14]:
        raise SystemExit("CPU14 required")
    if _sha(CONTROL) != EXPECTED_CONTROL_SHA or _sha(CANDIDATE) != EXPECTED_CANDIDATE_SHA:
        raise SystemExit("worker SHA mismatch")
    if _sha(arguments.manifest) != arguments.manifest_sha256:
        raise SystemExit("manifest SHA mismatch")
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    cases = manifest.get("cases") if isinstance(manifest, Mapping) else None
    if not isinstance(cases, list) or len(cases) != 24:
        raise SystemExit("fixed 24-case manifest required")

    counts = Counter()
    walls = {"control": [], "candidate": []}
    callbacks = Counter()
    lanes = Counter()
    safe_endpoints = Counter()
    diagnostic_targets = Counter()
    started = time.monotonic()
    for seed in (0, 1, 2):
        for ordinal, case in enumerate(cases):
            if not isinstance(case, Mapping):
                raise SystemExit("invalid case row")
            slug = case.get("slug")
            source_sha = case.get("source_sha256")
            if not isinstance(slug, str) or not isinstance(source_sha, str):
                raise SystemExit("invalid case binding")
            source = arguments.inputs / (slug + ".json")
            if _sha(source) != source_sha:
                raise SystemExit("source SHA mismatch")
            order = ("control", "candidate") if (seed + ordinal) % 2 == 0 else ("candidate", "control")
            row: dict[str, dict[str, object]] = {}
            for arm in order:
                worker = CONTROL if arm == "control" else CANDIDATE
                output = arguments.output_root / f"seed-{seed}" / slug / arm / "search.json"
                row[arm] = _run_one(worker, source, source_sha, output, seed)
            control = row["control"]
            candidate = row["candidate"]
            counts["pairs"] += 1
            if not control["ok"]:
                counts["control_invalid"] += 1
            if not candidate["ok"]:
                counts["candidate_invalid"] += 1
            control_solved = int(control.get("safe_endpoint_count", 0)) > 0
            candidate_solved = int(candidate.get("safe_endpoint_count", 0)) > 0
            counts["wins"] += int(candidate_solved and not control_solved)
            counts["losses"] += int(control_solved and not candidate_solved)
            counts["ties"] += int(control_solved == candidate_solved)
            for arm, result in row.items():
                walls[arm].append(float(result["wall"]))
                callbacks[arm] += int(result.get("callbacks", 0))
                lanes[arm] += int(result.get("lanes_started", 0))
                safe_endpoints[arm] += int(result.get("safe_endpoint_count", 0))
                diagnostic_targets[arm] += int(
                    result.get("diagnostic_distinct_target_count", 0)
                )
            sidecar = (
                arguments.output_root
                / f"seed-{seed}"
                / slug
                / "candidate"
                / "search.json.guard-merge-portal.json"
            )
            if sidecar.is_file():
                side = json.loads(sidecar.read_text(encoding="utf-8"))
                runtime = side.get("runtime") if isinstance(side, Mapping) else None
                if isinstance(runtime, Mapping):
                    counts["portal_activated"] += int(runtime.get("portal_activated") is True)
                    counts["portal_unknown"] += int(runtime.get("mode") == "UNKNOWN_FULL_BASELINE_FALLBACK")
                    counts["portal_censored"] += int(runtime.get("mode") == "BASELINE_CENSORED_NO_PORTAL")
    aggregate = {
        "schema_version": "geotarget.guard-merge-portal-screen24-direct/v1",
        "decision": (
            "D1_SIGNAL"
            if counts["wins"] > counts["losses"] and counts["candidate_invalid"] == 0
            else "D1_STOP_OR_REPAIR"
        ),
        "counts": dict(sorted(counts.items())),
        "safe_endpoint_count": dict(safe_endpoints),
        "diagnostic_distinct_target_count": dict(diagnostic_targets),
        "callbacks": dict(callbacks),
        "lanes_started": dict(lanes),
        "mean_wall_seconds": {
            arm: sum(values) / len(values) for arm, values in walls.items()
        },
        "total_elapsed_wall_seconds": time.monotonic() - started,
        "control_worker_sha256": EXPECTED_CONTROL_SHA,
        "candidate_worker_sha256": EXPECTED_CANDIDATE_SHA,
        "individual_results_emitted_in_public_aggregate": False,
        "truth_or_offline_score_read": False,
    }
    arguments.aggregate.parent.mkdir(parents=True, exist_ok=True)
    arguments.aggregate.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(aggregate, sort_keys=True))


if __name__ == "__main__":
    main()
