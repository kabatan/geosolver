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
import re
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
EXPECTED_CANDIDATE_SHA = "74236c96c4e4dd42fa9079435dbf41b824a9ecdd5baf1477e076da701833b4f7"
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
LEAF_RE = re.compile(r"^[0-9]{3}-[A-Za-z0-9_]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PORTAL_SIDECAR_SCHEMA = "geotarget.guard-relative-merge-tree-portal-repair/v2"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contained(root: Path, path: Path) -> Path:
    root = root.resolve()
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise SystemExit(f"path escapes frozen root: {path}") from None
    return path


def _portal_sidecar(output: Path) -> Mapping[str, object]:
    sidecar = output.with_name(output.name + ".guard-merge-portal.json")
    try:
        document = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"missing or malformed candidate sidecar: {error}") from None
    if (
        not isinstance(document, Mapping)
        or document.get("schema_version") != PORTAL_SIDECAR_SCHEMA
        or document.get("search_result_sha256") != _sha(output)
        or document.get("individual_observations_emitted") is not False
    ):
        raise ValueError("candidate sidecar/result binding mismatch")
    return document


def _run_one(
    worker: Path,
    source: Path,
    source_sha: str,
    output: Path,
    seed: int,
) -> dict[str, object]:
    if output.parent.exists():
        raise SystemExit(f"fresh per-pair output directory required: {output.parent}")
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(THREAD_ENV)
    started = time.monotonic()
    command = [
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
        ]
    try:
        completed = subprocess.run(
            command,
            cwd=worker.parent,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=20.0,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": "TIMEOUT", "wall": 20.0}
    wall = time.monotonic() - started
    if completed.returncode != 0 or not output.is_file():
        return {
            "ok": False,
            "returncode": completed.returncode,
            "wall": wall,
            "stderr_tail": completed.stderr[-300:],
        }
    result = _read_result(output, source_sha)
    if worker == CANDIDATE:
        try:
            _portal_sidecar(output)
        except ValueError:
            result["ok"] = False
            result["returncode"] = "SIDECAR_BINDING_INVALID"
    return result


def _read_result(output: Path, source_sha: str) -> dict[str, object]:
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
        "wall": float(document.get("elapsed_wall_seconds", math.nan)),
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
    if (
        not isinstance(cases, list)
        or len(cases) != 24
        or manifest.get("truth_or_known_target_count_influences_schedule") is not False
    ):
        raise SystemExit("fixed 24-case manifest required")
    inputs_root = arguments.inputs.resolve()
    output_root = arguments.output_root.resolve()
    if output_root.exists() or arguments.aggregate.resolve().exists():
        raise SystemExit("fresh output root and aggregate required")
    output_root.mkdir(parents=True, exist_ok=True)
    seen_slugs: set[str] = set()

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
            if (
                not isinstance(slug, str)
                or LEAF_RE.fullmatch(slug) is None
                or (seed == 0 and slug in seen_slugs)
                or not isinstance(source_sha, str)
                or SHA256_RE.fullmatch(source_sha) is None
            ):
                raise SystemExit("invalid case binding")
            if seed == 0:
                seen_slugs.add(slug)
            source = _contained(inputs_root, inputs_root / (slug + ".json"))
            if source.parent != inputs_root:
                raise SystemExit("source must be a direct frozen-root leaf")
            if _sha(source) != source_sha:
                raise SystemExit("source SHA mismatch")
            order = ("control", "candidate") if (seed + ordinal) % 2 == 0 else ("candidate", "control")
            row: dict[str, dict[str, object]] = {}
            for arm in order:
                worker = CONTROL if arm == "control" else CANDIDATE
                output = _contained(
                    output_root,
                    output_root / f"seed-{seed}" / slug / arm / "search.json",
                )
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
                output_root
                / f"seed-{seed}"
                / slug
                / "candidate"
                / "search.json.guard-merge-portal.json"
            )
            if sidecar.is_file():
                side = _portal_sidecar(sidecar.with_name("search.json"))
                runtime = side.get("runtime") if isinstance(side, Mapping) else None
                if isinstance(runtime, Mapping):
                    counts["portal_activated"] += int(runtime.get("portal_activated") is True)
                    counts["portal_unknown"] += int(runtime.get("mode") == "UNKNOWN_FULL_BASELINE_FALLBACK")
                    counts["portal_censored"] += int(runtime.get("mode") == "BASELINE_CENSORED_NO_PORTAL")
            if counts["pairs"] % 8 == 0:
                print(
                    json.dumps(
                        {
                            "progress_pairs": counts["pairs"],
                            "candidate_invalid": counts["candidate_invalid"],
                            "control_invalid": counts["control_invalid"],
                            "portal_activated": counts["portal_activated"],
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
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
