#!/usr/bin/env python3
"""Add a proof-bearing spectral-cosh surplus tail to one progressive BASE."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Mapping


HERE = Path(__file__).resolve().parent
BASE_SCHEDULER = HERE.parent / "archive_progressive_hybrid_exact_outer_v1/scheduler_shim.py"
TAIL_WORKER = HERE / "tail_search_worker.py"
CURRENT_ROOT = HERE.parent / "progressive_adaptive_hybrid_v1"
CURRENT_ADAPTER = CURRENT_ROOT / "search_adapter.py"
CURRENT_CANDIDATE = CURRENT_ROOT / "candidate.py"
SPECTRAL_ROOT = HERE.parent / "spectral_cosh_preconditioned_gn_v1"
SPECTRAL_CANDIDATE = SPECTRAL_ROOT / "real_candidate.py"
SPECTRAL_SEAM = SPECTRAL_ROOT / "real_seam_patch.py"
EXPECTED_SHA256 = {
    BASE_SCHEDULER: "b3b9df6062dc0aa603fc5da02ae2eefa0947721eafe9069bf545af75747350e0",
    TAIL_WORKER: "98e26228fecf14846b95cbe91e962b9243bef72ed6c1e2ce7e7bc1bc0f6c1a33",
    CURRENT_ADAPTER: "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    CURRENT_CANDIDATE: "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972",
    SPECTRAL_CANDIDATE: "7ac6ece4e34fa790c10218a5e8fe59def5ca1086562dc98751939d17aa5e2677",
    SPECTRAL_SEAM: "4902ca1f628949563736c8ea3a1950245e0e8e6af9be7f4463f8d4e69639fbf6",
}
TAIL_ARM = "progressive_adaptive_hybrid_64_600"
MIN_TAIL_CALLBACKS = 512
MIN_TAIL_WALL_SECONDS = 7.0


class IntegrationError(RuntimeError):
    """The frozen progressive, spectral, or authority seam changed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(path.resolve()): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_SHA256
    }
    expected = {
        str(path.resolve()): digest for path, digest in EXPECTED_SHA256.items()
    }
    if observed != expected:
        raise IntegrationError("progressive/spectral dependency closure changed")
    return observed


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


UPSTREAM = _load("geotarget_spectral_tail_exact_upstream", BASE_SCHEDULER)
BASE = UPSTREAM.BASE
CONTROL = UPSTREAM.CONTROL
HISTORICAL = UPSTREAM.HISTORICAL
PROGRESSIVE = UPSTREAM.PROGRESSIVE
RESOURCE_BUSY_STATUSES = UPSTREAM.RESOURCE_BUSY_STATUSES
SEARCH_POLICY = UPSTREAM.SEARCH_POLICY
V1 = UPSTREAM.V1
ZERO = UPSTREAM.ZERO
adapter = UPSTREAM.adapter
_BASE_PLAN = BASE._plan


def _assert_binding() -> None:
    verify_dependencies()
    UPSTREAM._assert_binding()
    if BASE is not CONTROL.CHAMPION.BASE or HISTORICAL is not CONTROL:
        raise IntegrationError("spectral tail would target a second control stack")
    if ZERO is not CONTROL.CHAMPION.ZERO:
        raise IntegrationError("zero-dimensional authority changed")


def _plan(**kwargs) -> dict[str, object]:
    _assert_binding()
    plan = _BASE_PLAN(**kwargs)
    plan.update(
        {
            "spectral_cosh_surplus_tail": True,
            "spectral_cosh_tail_callback_fraction_cap": 0.25,
            "spectral_cosh_tail_wall_fraction_cap": 0.25,
            "spectral_cosh_baseline_combined_share_minimum": 0.75,
            "spectral_cosh_baseline_runs_to_completion_first": True,
            "spectral_cosh_ordinal_schedule": False,
            "spectral_cosh_tail_insurance_services_use_ordinary_fd": True,
            "spectral_cosh_guard_branch_selector_policy": "fail-closed ordinary",
            "spectral_cosh_nonfinite_model_disagreement_policy": "fail-closed ordinary",
            "spectral_cosh_tail_all_authorities_require_exact_outer": True,
            "spectral_cosh_baseline_descriptor_prefix_immutable": True,
            "spectral_cosh_search_endpoint_union_or_recluster": False,
            "spectral_cosh_zero_dimensional_route_changed": False,
            "spectral_cosh_dependency_sha256": verify_dependencies(),
            "case_family_truth_target_count_or_outcome_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def _zero_dimensional(source: Path) -> bool:
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        variables = document.get("variables") if isinstance(document, dict) else None
        names = variables.get("names") if isinstance(variables, dict) else None
        return isinstance(names, list) and len(names) == 0
    except (OSError, json.JSONDecodeError):
        return False


def _callbacks_used(output: Path) -> int | None:
    try:
        search = json.loads((output / "search.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    work = search.get("work") if isinstance(search, Mapping) else None
    value = work.get("callbacks") if isinstance(work, Mapping) else None
    return int(value) if isinstance(value, int) and value >= 0 else None


def _descriptor_prefix(result: Mapping[str, object]) -> list[dict[str, object]] | None:
    values = result.get("distinct_exact_target_descriptors")
    if not isinstance(values, list) or not all(isinstance(row, Mapping) for row in values):
        return None
    return [dict(row) for row in values]


def _run_tail(*, arguments, output: Path, hard_deadline: float, callback_cap: int) -> None:
    result_path = output / "RESULT.json"
    baseline_bytes = result_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    if not isinstance(baseline, Mapping) or baseline.get("completed") is not True:
        return
    prefix = _descriptor_prefix(baseline)
    if prefix is None or callback_cap < MIN_TAIL_CALLBACKS:
        return
    remaining_wall = hard_deadline - time.monotonic()
    if remaining_wall < MIN_TAIL_WALL_SECONDS:
        return

    tail_root = output / "spectral-cosh-tail"
    tail_root.mkdir(parents=True, exist_ok=True)
    tail_search_seconds = min(12.0, max(0.25, remaining_wall - 6.5))
    tail_starts = min(int(arguments.starts), 16)
    if tail_starts < 16:
        return
    tail_cap = min(callback_cap, tail_starts * int(arguments.callbacks_per_start))
    if tail_cap < MIN_TAIL_CALLBACKS:
        return

    old_binding = (
        BASE.SEARCH_WORKER,
        BASE.SEARCH_ADAPTER,
        BASE.SEARCH_CANDIDATE,
        BASE.SEARCH_ARM,
        BASE.EXPECTED_SEARCH_CANDIDATE_SHA256,
    )
    try:
        BASE.SEARCH_WORKER = TAIL_WORKER
        BASE.SEARCH_ADAPTER = CURRENT_ADAPTER
        BASE.SEARCH_CANDIDATE = CURRENT_CANDIDATE
        BASE.SEARCH_ARM = TAIL_ARM
        BASE.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED_SHA256[CURRENT_CANDIDATE]
        _guard, tail_search = BASE._run_search(
            source=arguments.source,
            source_sha256=arguments.source_sha256,
            search_seconds=tail_search_seconds,
            starts=tail_starts,
            callbacks_per_start=arguments.callbacks_per_start,
            aggregate_callback_cap=tail_cap,
            seed=arguments.seed + 130363,
            output=tail_root,
        )
    finally:
        (
            BASE.SEARCH_WORKER,
            BASE.SEARCH_ADAPTER,
            BASE.SEARCH_CANDIDATE,
            BASE.SEARCH_ARM,
            BASE.EXPECTED_SEARCH_CANDIDATE_SHA256,
        ) = old_binding
    if not isinstance(tail_search, Mapping):
        return
    endpoints = tail_search.get("endpoints")
    if not isinstance(endpoints, list):
        return

    replay_deadline = min(
        hard_deadline - BASE.FINALIZE_RESERVE_SECONDS,
        time.monotonic() + 0.75,
    )
    if replay_deadline <= time.monotonic():
        return
    candidates = BASE._fresh_replay_candidates(
        json.loads(arguments.source.read_text(encoding="utf-8")),
        endpoints,
        hard_deadline=replay_deadline,
    )
    if not candidates:
        return
    if not getattr(BASE, "_geotarget_exact_outer_installed", False):
        raise IntegrationError("spectral tail emission could bypass exact_outer")
    attempts, side_descriptors, schedule = BASE._service_candidates(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        candidates=candidates,
        cpu=arguments.cpu,
        output=tail_root / "authority",
        hard_deadline=hard_deadline,
    )
    if not side_descriptors:
        return
    baseline_keys = {BASE._descriptor_key(row) for row in prefix}
    novel = [
        dict(side_descriptors[key])
        for key in sorted(side_descriptors)
        if key not in baseline_keys
    ]
    if not novel:
        return

    write_started = time.monotonic()
    total_elapsed = write_started - BASE.PROCESS_STARTED
    if write_started + 0.1 >= hard_deadline or total_elapsed > float(arguments.total_seconds):
        return
    frozen_prefix = json.dumps(prefix, sort_keys=True, separators=(",", ":"))
    union = dict(baseline)
    combined = prefix + novel
    if json.dumps(combined[: len(prefix)], sort_keys=True, separators=(",", ":")) != frozen_prefix:
        raise IntegrationError("baseline descriptor prefix changed")
    union["distinct_exact_targets"] = combined
    union["distinct_exact_target_descriptors"] = combined
    union["distinct_exact_target_count"] = len(combined)
    union["elapsed_wall_seconds"] = total_elapsed
    union["within_total_wall_budget"] = True
    union["spectral_cosh_tail"] = {
        "status": "NOVEL_AUTHORITATIVE_DESCRIPTOR_UNION",
        "baseline_descriptor_count": len(prefix),
        "novel_descriptor_count": len(novel),
        "baseline_descriptor_prefix_immutable": True,
        "search_endpoint_union_or_recluster": False,
        "tail_callback_cap": tail_cap,
        "tail_search_seconds": tail_search_seconds,
        "fresh_replayed_candidate_count": len(candidates),
        "authority_attempts": attempts,
        "authority_schedule": schedule,
    }
    if _sha256(arguments.source) != arguments.source_sha256:
        raise IntegrationError("source changed during spectral tail")
    intended_bytes = (json.dumps(union, ensure_ascii=False, indent=2) + "\n").encode()
    try:
        BASE.atomic_write_json(result_path, union)
    except Exception:
        current_bytes = result_path.read_bytes()
        if current_bytes == intended_bytes:
            return
        if current_bytes == baseline_bytes:
            raise
        raise IntegrationError("spectral tail atomic commit had ambiguous bytes")


def _run_spectral_tail(*, arguments, hard_deadline: float) -> None:
    if _zero_dimensional(arguments.source):
        return
    output = arguments.output.resolve()
    used = _callbacks_used(output)
    if used is None:
        return
    total_cap = int(arguments.aggregate_callback_cap)
    remaining = max(0, total_cap - used)
    # Side <=25% of the original cap and <=1/3 of observed baseline work, so
    # the baseline remains at least 75% of combined callback work.
    side_cap = min(remaining, total_cap // 4, used // 3)
    baseline_elapsed = max(0.0, time.monotonic() - BASE.PROCESS_STARTED)
    side_wall = min(
        0.25 * float(arguments.total_seconds),
        baseline_elapsed / 3.0,
        max(0.0, hard_deadline - time.monotonic()),
    )
    if side_cap < MIN_TAIL_CALLBACKS or side_wall < MIN_TAIL_WALL_SECONDS:
        return
    _run_tail(
        arguments=copy.copy(arguments),
        output=output,
        hard_deadline=min(hard_deadline, time.monotonic() + side_wall),
        callback_cap=side_cap,
    )


def main() -> None:
    _assert_binding()
    arguments = CONTROL.CHAMPION.ORIGINAL_V2._parser().parse_args()
    hard_deadline = BASE.PROCESS_STARTED + float(arguments.total_seconds)
    HISTORICAL.main()
    if not arguments.execute:
        return
    try:
        _run_spectral_tail(arguments=arguments, hard_deadline=hard_deadline)
    except Exception:
        # The immutable proof-bearing baseline RESULT.json already exists.
        return


__all__ = [
    "BASE", "CONTROL", "HISTORICAL", "PROGRESSIVE", "RESOURCE_BUSY_STATUSES",
    "SEARCH_POLICY", "V1", "ZERO", "adapter", "main",
]


if __name__ == "__main__":
    main()
