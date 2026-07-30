#!/usr/bin/env python3
"""Repair B: immutable baseline authority followed by a surplus-only DiGS service.

The ordinary champion is allowed to finish, including all numerical HP work,
exact confirmation, descriptor construction, and its atomic RESULT write.  The
written bytes are the frozen fallback.  Only then may this candidate spend
wall and callback budget that the baseline did not use.  A side descriptor is
released only when the already-installed exact-outer authority confirms it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Callable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CANDIDATES = HERE.parent
FROZEN_ROOT = Path(os.environ.get(
    "GEOTARGET_FROZEN_SOLVER_ROOT",
    "/home/kabatan/work/solver-experiment-runtime/solver",
)).resolve()
FROZEN_EXPERIMENT = FROZEN_ROOT / "research/experiments/EXP-V15-243-001"
FROZEN_CANDIDATES = FROZEN_EXPERIMENT / "candidates"
CHAMPION_WORKER = FROZEN_EXPERIMENT / "champion_v2/worker.py"
HP_SCHEDULER = FROZEN_CANDIDATES / "hp_scheduler_preserve_binding/worker.py"
EXACT_OUTER = FROZEN_CANDIDATES / "exact_outer_decorator/worker.py"
PRELOAD = FROZEN_EXPERIMENT / "repro_20260722/workers/precision_runtime_preload.py"
DIGS_ROOT = CANDIDATES / "diffusive_gibbs_portal_additive_v2"
DIGS_FULL_WRAPPER = DIGS_ROOT / "full_wrapper.py"
DIGS_SEARCH_WORKER = DIGS_ROOT / "search_worker.py"
DIGS_SEARCH_ADAPTER = DIGS_ROOT / "search_adapter.py"
DIGS_CANDIDATE = CANDIDATES / "progressive_adaptive_hybrid_v1/candidate.py"
DIGS_ARM = "progressive_adaptive_hybrid_plus_additive_digs_tail"

EXPECTED = {
    CHAMPION_WORKER: "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    HP_SCHEDULER: "5453a30c46d3050c0520a6492f149595bf93d4f2794e3e1fa86d7d60c2365702",
    EXACT_OUTER: "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7",
    PRELOAD: "1139fa3ae5f4805b4791bc3f99fb6dd89b38f0cdc778c29871eb7d3469e3c403",
    DIGS_FULL_WRAPPER: "e2a64742bd2c10f3feb983ed2d7a3ca068d5505a738e3124ea6b56f2229c2135",
    DIGS_SEARCH_WORKER: "b5f7fb6c431346458a06a0893789e5f9012e3178b54ac57efeead423cea4de7d",
    DIGS_SEARCH_ADAPTER: "856602efd5d1ac96464fa1a83dfad0f8f936b8dcd16ba5a95d0fad67371c22eb",
    DIGS_CANDIDATE: "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972",
}

MIN_SIDE_CALLBACKS = 16
MIN_SIDE_WALL_SECONDS = 12.5
FINAL_WRITE_RESERVE_SECONDS = 0.25
MAX_SIDE_SEARCH_SECONDS = 8.0


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def descriptor_key(descriptor: Mapping[str, object]) -> str:
    identity = {
        "minimal_polynomial_high_to_low": descriptor.get(
            "minimal_polynomial_high_to_low"
        ),
        "selected_real_root_index": descriptor.get("selected_real_root_index"),
    }
    return sha256_bytes(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    )


def merge_frozen_baseline(
    baseline: dict[str, object], side_descriptors: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Return baseline itself on an empty/duplicate side; otherwise prefix-union."""

    baseline_targets = baseline.get("distinct_exact_target_descriptors")
    if not isinstance(baseline_targets, list):
        raise ValueError("baseline exact descriptor list is unavailable")
    seen = {
        descriptor_key(item)
        for item in baseline_targets
        if isinstance(item, Mapping)
    }
    accepted: list[dict[str, object]] = []
    for raw in side_descriptors:
        if not isinstance(raw, Mapping):
            continue
        item = copy.deepcopy(dict(raw))
        key = descriptor_key(item)
        if key in seen:
            continue
        seen.add(key)
        accepted.append(item)
    if not accepted:
        return baseline

    merged = copy.deepcopy(baseline)
    descriptors = merged["distinct_exact_target_descriptors"]
    if not isinstance(descriptors, list):
        raise AssertionError("deep copy changed baseline descriptor type")
    descriptors.extend(copy.deepcopy(accepted))
    targets = merged.get("distinct_exact_targets")
    if not isinstance(targets, list):
        raise ValueError("baseline exact target list is unavailable")
    if targets is not descriptors:
        targets.extend(copy.deepcopy(accepted))
    merged["distinct_exact_target_count"] = len(descriptors)
    merged["repair_b_side_exact_descriptor_count"] = len(accepted)
    merged["repair_b_baseline_descriptor_prefix_count"] = len(baseline_targets)
    return merged


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, required=False, default=180.0)
    parser.add_argument("--starts", type=int, default=256)
    parser.add_argument("--callbacks-per-start", type=int, default=600)
    parser.add_argument("--aggregate-callback-cap", type=int, default=153600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    arguments, _unknown = parser.parse_known_args(argv)
    return arguments


def _verify_closure() -> None:
    for path, expected in EXPECTED.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"Repair B closure mismatch: {path}")


def _side_search(base, arguments, *, wall_seconds: float, callback_cap: int, root: Path):
    artifact = root / "search.json"
    status = root / "search-process-status.json"
    root.mkdir(parents=True, exist_ok=True)
    starts = max(4, min(arguments.starts, callback_cap // 2))
    callbacks_per_start = max(2, min(arguments.callbacks_per_start, callback_cap))
    command = [
        str(base.PYTHON), str(DIGS_SEARCH_WORKER),
        "--case", str(arguments.source.resolve()),
        "--case-sha256", arguments.source_sha256,
        "--arm", DIGS_ARM,
        "--seconds", str(wall_seconds),
        "--starts", str(starts),
        "--callbacks-per-start", str(callbacks_per_start),
        "--aggregate-callback-cap", str(callback_cap),
        "--seed", str(arguments.seed),
        "--output", str(artifact),
    ]
    guarded = base.run_guarded(
        command,
        limits=base.Limits(
            timeout_seconds=wall_seconds + 0.25,
            rss_bytes=768 * 1024**2,
            address_space_bytes=3072 * 1024**2,
            data_bytes=2048 * 1024**2,
            output_bytes=1024**2,
            tail_bytes=16 * 1024,
        ),
        environment=base.THREAD_ENVIRONMENT,
        cwd=ROOT,
        status_path=status,
    )
    if not guarded.accepted_output or not artifact.is_file():
        return None
    document = json.loads(artifact.read_text(encoding="utf-8"))
    required = (
        document.get("completed") is True,
        document.get("arm") == DIGS_ARM,
        document.get("source_sha256") == arguments.source_sha256,
        document.get("source_bytes_unchanged") is True,
        document.get("source_semantics_modified") is False,
        document.get("truth_used") is False,
    )
    return document if all(required) else None


def _run_side(base, arguments, baseline: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    if getattr(base, "_geotarget_exact_outer_installed", False) is not True:
        return [], {
            "schema_version": "geotarget.exp-v15-243.digs-repair-b-side/v1",
            "status": "EXACT_OUTER_UNAVAILABLE_BASELINE_ONLY",
            "truth_used": False,
        }
    hard_deadline = base.PROCESS_STARTED + arguments.total_seconds
    search = arguments.output.resolve() / "search.json"
    baseline_search = json.loads(search.read_text(encoding="utf-8"))
    work = baseline_search.get("work")
    used = int(work.get("callbacks")) if isinstance(work, Mapping) else arguments.aggregate_callback_cap
    effective_cap = min(
        arguments.aggregate_callback_cap,
        arguments.starts * arguments.callbacks_per_start,
    )
    callback_surplus = max(0, effective_cap - used)
    wall_surplus = hard_deadline - time.monotonic()
    telemetry: dict[str, object] = {
        "schema_version": "geotarget.exp-v15-243.digs-repair-b-side/v1",
        "baseline_result_sha256": sha256_file(arguments.output / "RESULT.json"),
        "baseline_callback_count": used,
        "callback_surplus": callback_surplus,
        "wall_surplus_before_side_seconds": wall_surplus,
        "exact_outer_required": True,
        "truth_used": False,
    }
    if callback_surplus < MIN_SIDE_CALLBACKS or wall_surplus < MIN_SIDE_WALL_SECONDS:
        telemetry["status"] = "ZERO_ADMISSIBLE_SURPLUS"
        return [], telemetry

    side_search_seconds = min(
        MAX_SIDE_SEARCH_SECONDS,
        max(4.0, wall_surplus - 8.0),
    )
    tail_root = arguments.output.resolve() / "repair-b-side"
    document = _side_search(
        base,
        arguments,
        wall_seconds=side_search_seconds,
        callback_cap=callback_surplus,
        root=tail_root,
    )
    if not isinstance(document, Mapping):
        telemetry["status"] = "SIDE_SEARCH_REJECTED"
        return [], telemetry
    activation = document.get("activation")
    counters = activation.get("counter_sums") if isinstance(activation, Mapping) else None
    baseline_endpoint_count = (
        int(counters.get("digs_additive_baseline_endpoints", 0))
        if isinstance(counters, Mapping)
        else 0
    )
    endpoints = document.get("endpoints")
    if not isinstance(endpoints, list) or baseline_endpoint_count <= 0:
        telemetry["status"] = "SIDE_DIGS_SUFFIX_UNAVAILABLE"
        return [], telemetry
    side_endpoints = endpoints[baseline_endpoint_count:]
    if not side_endpoints:
        telemetry["status"] = "SIDE_DIGS_SUFFIX_EMPTY"
        return [], telemetry

    _source_payload, source_document = base._source_contract(
        arguments.source, arguments.source_sha256
    )
    candidates = base._fresh_replay_candidates(
        source_document,
        side_endpoints,
        hard_deadline=min(hard_deadline - 0.5, time.monotonic() + 0.75),
    )
    descriptors: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []
    for ordinal, candidate in enumerate(candidates):
        remaining = hard_deadline - time.monotonic() - FINAL_WRITE_RESERVE_SECONDS
        if remaining < 7.5:
            break
        attempt = base._run_hp_candidate(
            source=arguments.source,
            source_sha256=arguments.source_sha256,
            candidate=candidate,
            cpu=arguments.cpu,
            output=tail_root / "exact" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}",
            timeout_seconds=remaining,
        )
        if isinstance(attempt, Mapping):
            attempts.append(dict(attempt))
            descriptor = attempt.get("descriptor")
            if (
                attempt.get("authority_pass") is True
                and attempt.get("ordinary_and_exact_descriptor_identity_match") is True
                and isinstance(descriptor, Mapping)
            ):
                descriptors.append(dict(descriptor))
    telemetry.update({
        "status": "SIDE_AUTHORITY_COMPLETE",
        "side_endpoint_count": len(side_endpoints),
        "side_replay_candidate_count": len(candidates),
        "side_hp_attempt_count": len(attempts),
        "side_exact_confirmed_count": len(descriptors),
    })
    return descriptors, telemetry


def install_result_seam(base, arguments) -> Callable[..., object]:
    original_write = base.atomic_write_json
    original_plan = base._plan

    def plan(**kwargs):
        document = original_plan(**kwargs)
        document.update({
            "repair_b_policy": "baseline complete and frozen before surplus-only DiGS",
            "repair_b_worker_sha256": sha256_file(Path(__file__)),
            "repair_b_closure": {
                str(path.resolve()): expected for path, expected in EXPECTED.items()
            },
            "repair_b_exact_outer_required": True,
            "repair_b_exact_outer_mode": "CONFIRM_ALL_AUTHORITIES",
            "repair_b_truth_routing": False,
        })
        return document

    def write(path: Path, document: object) -> None:
        original_write(path, document)
        if path.name != "RESULT.json" or not isinstance(document, dict):
            return
        frozen_bytes = path.read_bytes()
        frozen_sha = sha256_bytes(frozen_bytes)
        shutil.copyfile(path, path.with_name("FROZEN_BASELINE_RESULT.json"))
        try:
            descriptors, telemetry = _run_side(base, arguments, document)
            merged = merge_frozen_baseline(document, descriptors)
            telemetry["baseline_bytes_sha256"] = frozen_sha
            telemetry["baseline_descriptor_payload_sha256"] = sha256_bytes(
                json.dumps(
                    document.get("distinct_exact_target_descriptors"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            telemetry["baseline_descriptor_prefix_immutable"] = True
            if merged is not document:
                merged["elapsed_wall_seconds"] = time.monotonic() - base.PROCESS_STARTED
                merged["within_total_wall_budget"] = (
                    merged["elapsed_wall_seconds"] <= arguments.total_seconds
                )
                original_write(path, merged)
            original_write(path.with_name("REPAIR_B_TELEMETRY.json"), telemetry)
        except Exception as error:
            # The already-written baseline is the fail-closed result.  Restore
            # exact bytes in case a future writer implementation mutates early.
            if path.read_bytes() != frozen_bytes:
                path.write_bytes(frozen_bytes)
            original_write(path.with_name("REPAIR_B_TELEMETRY.json"), {
                "schema_version": "geotarget.exp-v15-243.digs-repair-b-side/v1",
                "status": "SIDE_EXCEPTION_BASELINE_RESTORED",
                "exception_type": type(error).__name__,
                "baseline_bytes_sha256": frozen_sha,
                "truth_used": False,
            })

    base._plan = plan
    base.atomic_write_json = write
    return original_write


def configure():
    _verify_closure()
    os.environ["GEOTARGET_HP_PRESERVE_CHAMPION_WORKER"] = str(
        CHAMPION_WORKER.resolve()
    )
    os.environ["GEOTARGET_HP_PRESERVE_BINDING_ARM"] = "ADAPTIVE_NO_1280_POC"
    os.environ["GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER"] = str(HP_SCHEDULER.resolve())
    os.environ["GEOTARGET_EXACT_OUTER_MODE"] = "CONFIRM_ALL_AUTHORITIES"
    exact = _load("geotarget_digs_repair_b_exact_outer", EXACT_OUTER)
    preload = _load("geotarget_digs_repair_b_precision_preload", PRELOAD)
    preload.install(exact.BASE, "geotarget_digs_repair_b_precision_runtime")
    return exact


def main() -> None:
    arguments = _arguments(sys.argv[1:])
    exact = configure()
    install_result_seam(exact.BASE, arguments)
    exact.main()


if __name__ == "__main__":
    main()
