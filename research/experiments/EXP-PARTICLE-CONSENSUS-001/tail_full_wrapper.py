"""Repair A: immutable current-adaptive result plus a surplus-only particle tail.

The current adaptive solver finishes first.  Search endpoints are never mixed.
Only independently fresh-replayed particle endpoints may enter the unchanged HP
authority, after which newly authoritative descriptors are appended behind the
immutable baseline descriptor prefix.  Any no-budget, pre-commit error, or
no-novelty path leaves the baseline RESULT.json bytes untouched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
UPSTREAM_PATH = (
    HERE.parent / "EXP-V15-243-001/candidates/progressive_adaptive_hybrid_v1/full_wrapper.py"
)
UPSTREAM_SHA256 = "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"
PARTICLE_WORKER = HERE / "real_search_worker.py"
PARTICLE_ADAPTER = HERE / "real_adapter.py"
PARTICLE_CANDIDATE = HERE / "candidate.py"
EXPECTED_PARTICLE_SHA256 = {
    "real_search_worker.py": "91d7469ba3792e11d2c6b023178d50fc89859616f01293fe4fa72e423f778d00",
    "real_adapter.py": "e9e3600e1ba9830e70cbdad11886e3bca043f12c7d7c0441e23431bbdb2caaae",
    "candidate.py": "1d24ab131de635ef47c5f9f2230822f3d62a6d7b5787be95e26089d59c924a4e",
}
PARTICLE_ARM = "few_particle_equality_forced_prefix_25pct"
MIN_TAIL_CALLBACKS = 512
MIN_TAIL_WALL_SECONDS = 7.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_upstream():
    if _sha256(UPSTREAM_PATH) != UPSTREAM_SHA256:
        raise SystemExit("current adaptive full-wrapper SHA-256 mismatch")
    name = "geotarget_particle_tail_current_adaptive_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, UPSTREAM_PATH)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot load current adaptive full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _verify_particle() -> None:
    paths = {
        "real_search_worker.py": PARTICLE_WORKER,
        "real_adapter.py": PARTICLE_ADAPTER,
        "candidate.py": PARTICLE_CANDIDATE,
    }
    for name, path in paths.items():
        if not path.is_file() or _sha256(path) != EXPECTED_PARTICLE_SHA256[name]:
            raise SystemExit(f"particle tail SHA-256 mismatch: {name}")


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


def _install_plan_record(base) -> None:
    original = base._plan

    def plan(**kwargs):
        payload = original(**kwargs)
        payload.update({
            "particle_repair_a": "post-authority-surplus-only-descriptor-union",
            "particle_search_worker_sha256": EXPECTED_PARTICLE_SHA256["real_search_worker.py"],
            "particle_search_adapter_sha256": EXPECTED_PARTICLE_SHA256["real_adapter.py"],
            "particle_candidate_sha256": EXPECTED_PARTICLE_SHA256["candidate.py"],
            "particle_min_tail_callbacks": MIN_TAIL_CALLBACKS,
            "particle_min_tail_wall_seconds": MIN_TAIL_WALL_SECONDS,
            "baseline_result_immutable_on_no_surplus_precommit_error_or_no_novelty": True,
            "search_endpoint_union_or_recluster": False,
        })
        return payload

    base._plan = plan


def _run_tail(*, base, arguments, output: Path, hard_deadline: float) -> None:
    result_path = output / "RESULT.json"
    baseline_bytes = result_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    if not isinstance(baseline, Mapping) or baseline.get("completed") is not True:
        return
    prefix = _descriptor_prefix(baseline)
    callbacks_used = _callbacks_used(output)
    if prefix is None or callbacks_used is None:
        return
    remaining_callbacks = int(arguments.aggregate_callback_cap) - callbacks_used
    remaining_wall = hard_deadline - time.monotonic()
    if remaining_callbacks < MIN_TAIL_CALLBACKS or remaining_wall < MIN_TAIL_WALL_SECONDS:
        return

    tail_root = output / "particle-tail"
    tail_root.mkdir(parents=True, exist_ok=True)
    tail_search_seconds = min(2.0, max(0.25, remaining_wall - 6.5))
    tail_starts = min(int(arguments.starts), 16)
    if tail_starts < 16:
        return
    tail_cap = min(
        remaining_callbacks,
        tail_starts * int(arguments.callbacks_per_start),
    )
    if tail_cap < MIN_TAIL_CALLBACKS:
        return

    old_binding = (
        base.SEARCH_WORKER,
        base.SEARCH_ADAPTER,
        base.SEARCH_CANDIDATE,
        base.SEARCH_ARM,
        base.EXPECTED_SEARCH_CANDIDATE_SHA256,
    )
    try:
        base.SEARCH_WORKER = PARTICLE_WORKER
        base.SEARCH_ADAPTER = PARTICLE_ADAPTER
        base.SEARCH_CANDIDATE = PARTICLE_CANDIDATE
        base.SEARCH_ARM = PARTICLE_ARM
        base.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED_PARTICLE_SHA256["candidate.py"]
        _guard, tail_search = base._run_search(
            source=arguments.source,
            source_sha256=arguments.source_sha256,
            search_seconds=tail_search_seconds,
            starts=tail_starts,
            callbacks_per_start=arguments.callbacks_per_start,
            aggregate_callback_cap=tail_cap,
            seed=arguments.seed + 104729,
            output=tail_root,
        )
    finally:
        (
            base.SEARCH_WORKER,
            base.SEARCH_ADAPTER,
            base.SEARCH_CANDIDATE,
            base.SEARCH_ARM,
            base.EXPECTED_SEARCH_CANDIDATE_SHA256,
        ) = old_binding
    if not isinstance(tail_search, Mapping):
        return
    endpoints = tail_search.get("endpoints")
    if not isinstance(endpoints, list):
        return

    replay_deadline = min(hard_deadline - base.FINALIZE_RESERVE_SECONDS, time.monotonic() + 0.75)
    if replay_deadline <= time.monotonic():
        return
    candidates = base._fresh_replay_candidates(
        json.loads(arguments.source.read_text(encoding="utf-8")),
        endpoints,
        hard_deadline=replay_deadline,
    )
    if not candidates:
        return
    attempts, side_descriptors, schedule = base._service_candidates(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        candidates=candidates,
        cpu=arguments.cpu,
        output=tail_root / "authority",
        hard_deadline=hard_deadline,
    )
    if not side_descriptors:
        return

    baseline_keys = {base._descriptor_key(row) for row in prefix}
    novel = [
        dict(side_descriptors[key])
        for key in sorted(side_descriptors)
        if key not in baseline_keys
    ]
    if not novel:
        return
    write_started = time.monotonic()
    total_elapsed = write_started - base.PROCESS_STARTED
    if write_started + 0.1 >= hard_deadline or total_elapsed > float(arguments.total_seconds):
        return
    # Assert the exact baseline descriptor payload and order immediately before
    # writing the union.  No baseline attempt/search/reservoir field is changed.
    frozen_prefix = json.dumps(prefix, sort_keys=True, separators=(",", ":"))
    union = dict(baseline)
    combined = prefix + novel
    if json.dumps(combined[:len(prefix)], sort_keys=True, separators=(",", ":")) != frozen_prefix:
        raise RuntimeError("baseline descriptor prefix changed")
    union["distinct_exact_targets"] = combined
    union["distinct_exact_target_descriptors"] = combined
    union["distinct_exact_target_count"] = len(combined)
    baseline_elapsed = baseline.get("elapsed_wall_seconds")
    union["elapsed_wall_seconds"] = total_elapsed
    union["within_total_wall_budget"] = True
    union["particle_tail"] = {
        "status": "NOVEL_AUTHORITATIVE_DESCRIPTOR_UNION",
        "baseline_descriptor_count": len(prefix),
        "novel_descriptor_count": len(novel),
        "baseline_descriptor_prefix_immutable": True,
        "search_endpoint_union_or_recluster": False,
        "remaining_callbacks_before_tail": remaining_callbacks,
        "tail_callback_cap": tail_cap,
        "tail_search_seconds": tail_search_seconds,
        "fresh_replayed_candidate_count": len(candidates),
        "baseline_elapsed_wall_seconds": baseline_elapsed,
        "total_elapsed_wall_seconds": total_elapsed,
        "authority_attempts": attempts,
        "authority_schedule": schedule,
    }
    if _sha256(arguments.source) != arguments.source_sha256:
        raise RuntimeError("source changed during particle tail")
    intended_bytes = (
        json.dumps(union, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    try:
        base.atomic_write_json(result_path, union)
    except Exception:
        # atomic_write_json replaces RESULT before its directory fsync.  A
        # post-replace durability error is therefore a committed union, not a
        # tail failure.  A pre-replace error still has the exact baseline bytes.
        current_bytes = result_path.read_bytes()
        if current_bytes == intended_bytes:
            return
        if current_bytes == baseline_bytes:
            raise
        raise RuntimeError("particle tail atomic commit had ambiguous bytes")


def main() -> None:
    _verify_particle()
    upstream = _load_upstream()
    # The exact current adaptive arm, including its own search, HP, and final
    # descriptor map, is the immutable baseline.
    control = upstream.configure(
        frozen_root=Path(os.environ.get(
            "GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT)
        )).resolve(),
        enable_hybrid=True,
    )
    base = control.CHAMPION.BASE
    _install_plan_record(base)
    arguments = control.CHAMPION.ORIGINAL_V2._parser().parse_args()
    hard_deadline = base.PROCESS_STARTED + float(arguments.total_seconds)
    control.main()
    if not arguments.execute:
        return
    try:
        _run_tail(base=base, arguments=arguments, output=arguments.output.resolve(), hard_deadline=hard_deadline)
    except Exception:
        # The baseline RESULT already exists and is deliberately not rewritten.
        return


if __name__ == "__main__":
    main()
