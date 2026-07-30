"""Resume only the frozen champion's explicitly deferred reservoir records."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geotarget.hp_wave_checkpoint import pending as wave_pending
from geotarget.hp_wave_checkpoint import validate as validate_wave_checkpoint
from geotarget.optimized_search import run_parallel_search
from geotarget.parallel import (
    AuthorityDeadlinePolicy,
    ParallelAuthorityAdapter,
    attempt_is_resource_busy,
    resume_candidates_parallel,
)
from geotarget.parallel import (
    install as install_parallel,
)
from geotarget.reservoir_checkpoint import (
    CandidateReservoirSnapshot,
    load_checkpoint,
    search_binding,
    write_checkpoint,
)

RESERVOIR_CHECKPOINT = "candidate-reservoir.json"
CONTROLLER_STATE = "controller-state.json"


@dataclass(frozen=True)
class ContinuationContext:
    """Immutable imports and source compilation shared by continuation windows."""

    base: Any
    source_document: dict[str, Any]
    authority: ParallelAuthorityAdapter | None = None


def prepare_context(
    *,
    runtime: Path,
    source: Path,
    source_sha256: str,
    cpus: tuple[int, ...],
) -> ContinuationContext:
    base = _load_frozen(runtime)
    base.HP_BRIDGE = Path(__file__).with_name("hp_slot_entrypoint.py")
    authority = install_parallel(
        base,
        cpus,
        deadline_policy=AuthorityDeadlinePolicy.outer_deadline(),
        install_compatibility_seam=False,
    )
    source_payload, source_document = base._source_contract(source, source_sha256)
    del source_payload
    return ContinuationContext(
        base=base,
        source_document=source_document,
        authority=authority,
    )


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_frozen(runtime: Path):
    entrypoint = (
        runtime
        / "solver/research/experiments/EXP-V15-243-001/repro_20260722/workers"
        / "champion_v2_poc_preloaded.py"
    )
    sys.path.insert(0, str(entrypoint.parent))
    specification = importlib.util.spec_from_file_location(
        "geotarget_product_continuation_frozen", entrypoint
    )
    if specification is None or specification.loader is None:
        raise ImportError(entrypoint)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module.CHAMPION.BASE


def _descriptor_key(descriptor: Mapping[str, Any]) -> str:
    polynomial = descriptor.get("minimal_polynomial_high_to_low")
    root = descriptor.get("selected_real_root_index")
    return json.dumps([polynomial, root], separators=(",", ":"), sort_keys=True)


def _existing_descriptors(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = result.get("distinct_exact_target_descriptors") or result.get("distinct_exact_targets")
    descriptors: dict[str, dict[str, Any]] = {}
    if isinstance(values, list):
        for value in values:
            if isinstance(value, Mapping):
                descriptor = dict(value)
                descriptors.setdefault(_descriptor_key(descriptor), descriptor)
    return descriptors


def _durable_wave(result: Mapping[str, Any]) -> dict[str, Any] | None:
    schedule = result.get("hp_schedule")
    if not isinstance(schedule, Mapping):
        return None
    direct = schedule.get("durable_wave_checkpoint")
    if direct is not None:
        return validate_wave_checkpoint(direct)
    batches = schedule.get("reservoir_batches")
    if isinstance(batches, list):
        for batch in reversed(batches):
            if isinstance(batch, Mapping) and batch.get("durable_wave_checkpoint") is not None:
                checkpoint = validate_wave_checkpoint(batch["durable_wave_checkpoint"])
                if checkpoint is not None and checkpoint["stage"] != "complete":
                    return checkpoint
    return None


def _all_candidates(
    base: Any,
    source_document: dict[str, Any],
    search: Mapping[str, Any],
    deadline: float,
    *,
    source_sha256: str | None = None,
    checkpoint_input: Path | None = None,
    checkpoint_output: Path | None = None,
):
    endpoints = search.get("endpoints")
    if not isinstance(endpoints, list):
        return ()
    binding = search_binding(source_sha256, search) if source_sha256 is not None else None
    reservoir = (
        load_checkpoint(
            checkpoint_input,
            expected_binding=binding,
            candidate_type=base.ReplayCandidate,
            reservoir_type=CandidateReservoirSnapshot,
        )
        if checkpoint_input is not None and binding is not None
        else None
    )
    if reservoir is None:
        reservoir = base._fresh_replay_candidates(
            source_document,
            endpoints,
            hard_deadline=min(deadline, time.monotonic() + base.SELECTION_RESERVE_SECONDS),
        )
    if checkpoint_output is not None and binding is not None:
        write_checkpoint(checkpoint_output, binding=binding, reservoir=reservoir)
    return reservoir


def _pending_candidates(
    base: Any,
    source_document: dict[str, Any],
    search: Mapping[str, Any],
    result: Mapping[str, Any],
    deadline: float,
    new_endpoints: set[tuple[float, ...]] | None = None,
    source_sha256: str | None = None,
    checkpoint_input: Path | None = None,
    checkpoint_output: Path | None = None,
):
    all_candidates = _all_candidates(
        base,
        source_document,
        search,
        deadline,
        source_sha256=source_sha256,
        checkpoint_input=checkpoint_input,
        checkpoint_output=checkpoint_output,
    )
    schedule = result.get("hp_schedule")
    deferred = schedule.get("deferred_record_ids") if isinstance(schedule, Mapping) else ()
    deferred_ids = {str(value) for value in deferred} if isinstance(deferred, list) else set()

    def wanted(candidate: Any) -> bool:
        if candidate.record_id in deferred_ids:
            return True
        endpoint = getattr(candidate, "endpoint", None)
        return new_endpoints is not None and tuple(endpoint or ()) in new_endpoints

    verified = tuple(candidate for candidate in all_candidates if wanted(candidate))
    backlog = tuple(
        candidate
        for candidate in getattr(all_candidates, "deadline_backlog", ())
        if wanted(candidate)
    )
    reservoir_type = type(all_candidates)
    try:
        return reservoir_type(verified, backlog)
    except TypeError:
        return verified + backlog


def continue_result(
    *,
    runtime: Path,
    source: Path,
    source_sha256: str,
    initial_output: Path,
    output: Path,
    seconds: float,
    cpu: int,
    cpus: tuple[int, ...],
    seed: int,
    context: ContinuationContext | None = None,
) -> dict[str, Any]:
    prepared = context or prepare_context(
        runtime=runtime,
        source=source,
        source_sha256=source_sha256,
        cpus=cpus,
    )
    base = prepared.base
    source_document = prepared.source_document
    result = json.loads((initial_output / "RESULT.json").read_text(encoding="utf-8"))
    search_path = initial_output / "search.json"
    if not search_path.is_file():
        return result
    search = json.loads(search_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + seconds
    previous_work = search.get("work") if isinstance(search.get("work"), Mapping) else {}
    start_offset = min(256, int(previous_work.get("lanes_started", 0)))
    callbacks_used = min(153600, int(previous_work.get("callbacks", 0)))
    new_endpoint_points: set[tuple[float, ...]] = set()
    if start_offset < 256 and callbacks_used < 153600:
        search_seconds = min(146.0, seconds * 146.0 / 180.0)
        _search_status, resumed = run_parallel_search(
            base=base,
            cpus=cpus,
            source=source,
            source_sha256=source_sha256,
            search_seconds=search_seconds,
            starts=256,
            callbacks_per_start=600,
            aggregate_callback_cap=(256 - start_offset) * 600,
            seed=seed,
            output=output / "resumed-search",
            ordinal_start=start_offset,
            ordinal_end=256,
        )
        resumed = resumed or {}
        resumed_endpoints = list(resumed.get("endpoints", ()))
        new_endpoint_points = {
            tuple(float(value) for value in endpoint.get("point", ()))
            for endpoint in resumed_endpoints
            if isinstance(endpoint, Mapping)
        }
        merged_endpoints = list(search.get("endpoints", ())) + resumed_endpoints
        merged_work = dict(previous_work)
        resumed_work = resumed.get("work") if isinstance(resumed.get("work"), Mapping) else {}
        merged_work["lanes_started"] = min(
            256, start_offset + int(resumed_work.get("lanes_started", 0))
        )
        for key in ("callbacks", "finite_callbacks", "invalid_callbacks", "guard_failed_callbacks"):
            merged_work[key] = int(previous_work.get(key, 0)) + int(resumed_work.get(key, 0))
        resumed_parallel = resumed.get("optimized_parallel_search")
        previous_parallel = search.get("optimized_parallel_search")
        previous_ordinals_source = (
            previous_parallel.get("completed_start_ordinals", ())
            if isinstance(previous_parallel, Mapping)
            else range(start_offset)
        )
        previous_ordinals = tuple(
            int(value)
            for value in previous_ordinals_source
            if isinstance(value, int) and 0 <= value < start_offset
        )
        if previous_ordinals != tuple(range(start_offset)):
            previous_ordinals = tuple(range(start_offset))
        resumed_ordinals = (
            resumed_parallel.get("completed_start_ordinals", ())
            if isinstance(resumed_parallel, Mapping)
            else ()
        )
        completed_ordinals = sorted(
            {
                int(value)
                for value in (*previous_ordinals, *resumed_ordinals)
                if isinstance(value, int) and 0 <= value < 256
            }
        )
        combined_parallel = {
            **(dict(resumed_parallel) if isinstance(resumed_parallel, Mapping) else {}),
            "ordinal_start": 0,
            "ordinal_end": 256,
            "accepted_prefix_end": len(completed_ordinals),
            "completed_start_ordinals": completed_ordinals,
            "all_requested_starts_completed": len(completed_ordinals) == 256,
        }
        search = {
            **search,
            "endpoints": merged_endpoints,
            "work": merged_work,
            "optimized_parallel_search": combined_parallel,
        }
        (output / "search.json").write_text(
            json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    checkpoint_input = initial_output / RESERVOIR_CHECKPOINT
    checkpoint_output = output / RESERVOIR_CHECKPOINT
    durable = _durable_wave(result)
    if durable is not None and wave_pending(durable):
        reservoir = _all_candidates(
            base,
            source_document,
            search,
            deadline,
            source_sha256=source_sha256,
            checkpoint_input=checkpoint_input,
            checkpoint_output=checkpoint_output,
        )
        # The frozen split reserves 34 seconds when search consumes its full
        # 146-second share.  If the fixed 0..255 search graph has already
        # finished (or finishes early), its unused time flows forward into HP
        # and restoration; it must not be thrown away by imposing a fresh
        # 34-second wall cap here.
        authority_started = time.monotonic()
        authority_budget = max(0.0, deadline - authority_started)
        authority_deadline = deadline
        resume_arguments = {
            "source": source,
            "source_sha256": source_sha256,
            "all_candidates": reservoir,
            "output": output / "resumed-wave",
            "hard_deadline": authority_deadline,
            "checkpoint": durable,
        }
        if prepared.authority is not None:
            attempts, new_descriptors, resumed = prepared.authority.resume_candidates(
                **resume_arguments
            )
        else:
            attempts, new_descriptors, resumed = resume_candidates_parallel(
                base=base,
                cpus=cpus,
                pool=getattr(base, "_geotarget_hp_pool", None),
                **resume_arguments,
            )
        next_wave = resumed["durable_wave_checkpoint"]
        descriptors = _existing_descriptors(result)
        for descriptor in new_descriptors.values():
            descriptors.setdefault(_descriptor_key(descriptor), dict(descriptor))
        ordered = [descriptors[key] for key in sorted(descriptors)]
        prior_attempts = result.get("hp_attempts")
        result["hp_attempts"] = (
            list(prior_attempts) if isinstance(prior_attempts, list) else []
        ) + list(attempts)
        result["hp_attempt_count"] = len(result["hp_attempts"])
        result["distinct_exact_targets"] = ordered
        result["distinct_exact_target_descriptors"] = ordered
        result["distinct_exact_target_count"] = len(ordered)
        prior_schedule = result.get("hp_schedule")
        prior_schedule = dict(prior_schedule) if isinstance(prior_schedule, Mapping) else {}
        before_primary = set(durable["pending_primary_record_ids"])
        after_primary = set(next_wave["pending_primary_record_ids"])
        consumed_primary = before_primary - after_primary
        old_deferred = prior_schedule.get("deferred_record_ids")
        deferred = (
            [str(value) for value in old_deferred if str(value) not in consumed_primary]
            if isinstance(old_deferred, list)
            else []
        )
        resource_busy_count = sum(attempt_is_resource_busy(attempt) for attempt in attempts)
        terminal_attempt_count = len(attempts) - resource_busy_count
        result["hp_schedule"] = {
            **prior_schedule,
            "deferred_record_ids": deferred,
            "durable_wave_checkpoint": next_wave,
        }
        result["continuation"] = {
            "schema_version": "geotarget.product-continuation/v1",
            "fixed_work_graph_only": True,
            "new_starts": 0,
            "new_seeds": 0,
            "seconds": seconds,
            "authority_cap_seconds": authority_budget,
            "nominal_authority_reserve_seconds": 34.0,
            "cpu": cpu,
            "no_progress": not terminal_attempt_count and not new_descriptors,
            "retryable_resource_contention": bool(
                resource_busy_count and not terminal_attempt_count and not new_descriptors
            ),
            "resource_busy_deferred_count": resource_busy_count,
            "deferred_record_ids": deferred,
            "pending_hp_wave_stage": next_wave["stage"],
            "pending_start_ordinals": list(
                range(int(search.get("work", {}).get("lanes_started", 0)), 256)
            ),
        }
        (output / "search.json").write_text(
            json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return result

    candidates = _pending_candidates(
        base,
        source_document,
        search,
        result,
        deadline,
        new_endpoints=new_endpoint_points,
        source_sha256=source_sha256,
        checkpoint_input=checkpoint_input,
        checkpoint_output=checkpoint_output,
    )
    if not candidates:
        schedule = result.get("hp_schedule")
        deferred_ids = (
            [str(value) for value in schedule.get("deferred_record_ids", ())]
            if isinstance(schedule, Mapping)
            else []
        )
        (output / "search.json").write_text(
            json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        result["continuation"] = {
            "schema_version": "geotarget.product-continuation/v1",
            "fixed_work_graph_only": True,
            "new_starts": max(
                0, int(search.get("work", {}).get("lanes_started", 0)) - start_offset
            ),
            "new_seeds": 0,
            "seconds": seconds,
            "cpu": cpu,
            "no_progress": True,
            "reason": "no deferred candidate could be reconstructed",
            # A missing candidate after the initial search is not a terminal
            # numerical outcome.  Under host contention the bounded semantic
            # replay may admit nothing; keep the unchanged frozen IDs pending
            # and let the controller retry while wall budget remains.
            "retryable_resource_contention": bool(deferred_ids),
            "resource_busy_deferred_count": len(deferred_ids),
            "deferred_record_ids": deferred_ids,
            "pending_start_ordinals": list(
                range(int(search.get("work", {}).get("lanes_started", 0)), 256)
            ),
        }
        return result

    authority_started = time.monotonic()
    authority_budget = max(0.0, deadline - authority_started)
    service_arguments = {
        "source": source,
        "source_sha256": source_sha256,
        "candidates": candidates,
        "cpu": cpu,
        "output": output,
        "hard_deadline": deadline,
    }
    if prepared.authority is not None:
        attempts, new_descriptors, schedule = prepared.authority.service_candidates(
            **service_arguments
        )
    else:
        attempts, new_descriptors, schedule = base._service_candidates(
            **service_arguments
        )
    descriptors = _existing_descriptors(result)
    for descriptor in new_descriptors.values():
        descriptors.setdefault(_descriptor_key(descriptor), dict(descriptor))
    ordered = [descriptors[key] for key in sorted(descriptors)]
    prior_attempts = result.get("hp_attempts")
    result["hp_attempts"] = (
        list(prior_attempts) if isinstance(prior_attempts, list) else []
    ) + list(attempts)
    result["hp_attempt_count"] = len(result["hp_attempts"])
    result["distinct_exact_targets"] = ordered
    result["distinct_exact_target_descriptors"] = ordered
    result["distinct_exact_target_count"] = len(ordered)
    result["hp_schedule"] = schedule
    resource_busy_count = sum(attempt_is_resource_busy(attempt) for attempt in attempts)
    terminal_attempt_count = len(attempts) - resource_busy_count
    result["continuation"] = {
        "schema_version": "geotarget.product-continuation/v1",
        "fixed_work_graph_only": True,
        "new_starts": max(0, int(search.get("work", {}).get("lanes_started", 0)) - start_offset),
        "new_seeds": 0,
        "seconds": seconds,
        "authority_cap_seconds": authority_budget,
        "nominal_authority_reserve_seconds": 34.0,
        "cpu": cpu,
        "no_progress": (
            not terminal_attempt_count and not new_descriptors and not new_endpoint_points
        ),
        "retryable_resource_contention": bool(
            resource_busy_count
            and not terminal_attempt_count
            and not new_descriptors
            and not new_endpoint_points
        ),
        "resource_busy_deferred_count": resource_busy_count,
        "deferred_record_ids": list(schedule.get("deferred_record_ids", ())),
        "pending_start_ordinals": list(
            range(int(search.get("work", {}).get("lanes_started", 0)), 256)
        ),
    }
    (output / "search.json").write_text(
        json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def _controller_state(path: Path) -> tuple[dict[str, Any], dict[str, Any], bool, bool]:
    result = json.loads((path / "RESULT.json").read_text(encoding="utf-8"))
    search_path = path / "search.json"
    search = json.loads(search_path.read_text(encoding="utf-8")) if search_path.is_file() else {}
    work = search.get("work") if isinstance(search, Mapping) else {}
    lanes = int(work.get("lanes_started", 0)) if isinstance(work, Mapping) else 0
    schedule = result.get("hp_schedule")
    deferred = isinstance(schedule, Mapping) and bool(schedule.get("deferred_record_ids"))
    deferred = deferred or wave_pending(_durable_wave(result))
    continuation = result.get("continuation")
    pending = isinstance(continuation, Mapping) and bool(continuation.get("pending_start_ordinals"))
    return result, search, deferred, pending or lanes < 256


def _progress_signature(
    result: Mapping[str, Any], search: Mapping[str, Any]
) -> tuple[int, int, tuple[str, ...], int, str]:
    work = search.get("work") if isinstance(search.get("work"), Mapping) else {}
    schedule = result.get("hp_schedule")
    deferred = tuple(
        str(value)
        for value in (
            schedule.get("deferred_record_ids", ()) if isinstance(schedule, Mapping) else ()
        )
    )
    descriptors = result.get("distinct_exact_target_descriptors") or result.get(
        "distinct_exact_targets"
    )
    durable = _durable_wave(result)
    return (
        int(work.get("lanes_started", 0)),
        int(work.get("callbacks", 0)),
        deferred,
        len(descriptors) if isinstance(descriptors, list) else 0,
        str(durable.get("content_sha256", "")) if durable is not None else "",
    )


def run_controller(
    *,
    runtime: Path,
    source: Path,
    source_sha256: str,
    initial_output: Path,
    output: Path,
    seconds: float,
    cpu: int,
    cpus: tuple[int, ...],
    seed: int,
) -> dict[str, Any]:
    """Run identical frozen continuation windows with one prepared runtime."""

    started = time.monotonic()
    deadline = started + seconds
    context = prepare_context(
        runtime=runtime,
        source=source,
        source_sha256=source_sha256,
        cpus=cpus,
    )
    active_output = initial_output
    windows: list[dict[str, Any]] = []
    stalled = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining < 12.0:
            break
        before_result, before_search, has_deferred, has_pending = _controller_state(active_output)
        if not has_deferred and not has_pending:
            break
        before_signature = _progress_signature(before_result, before_search)
        ordinal = len(windows) + 1
        window_output = output / f"window-{ordinal:03d}"
        window_output.mkdir(parents=True, exist_ok=False)
        window_seconds = min(180.0, remaining)
        result = continue_result(
            runtime=runtime,
            source=source,
            source_sha256=source_sha256,
            initial_output=active_output,
            output=window_output,
            seconds=window_seconds,
            cpu=cpu,
            cpus=cpus,
            seed=seed,
            context=context,
        )
        _atomic_json(window_output / "RESULT.json", result)
        after_result, after_search, _after_deferred, _after_pending = _controller_state(
            window_output
        )
        after_signature = _progress_signature(after_result, after_search)
        continuation = after_result.get("continuation")
        explicitly_stalled = isinstance(continuation, Mapping) and bool(
            continuation.get("no_progress")
        )
        retryable_contention = isinstance(continuation, Mapping) and bool(
            continuation.get("retryable_resource_contention")
        )
        stalled = (explicitly_stalled or after_signature == before_signature) and not (
            retryable_contention
        )
        active_output = window_output
        authority_budget = (
            float(continuation.get("authority_cap_seconds", 34.0))
            if isinstance(continuation, Mapping)
            else 34.0
        )
        windows.append(
            {
                "ordinal": ordinal,
                "requested_seconds": window_seconds,
                "post_search_cap_seconds": authority_budget,
                "nominal_post_search_reserve_seconds": 34.0,
                "before_lanes": before_signature[0],
                "after_lanes": after_signature[0],
                "before_callbacks": before_signature[1],
                "after_callbacks": after_signature[1],
                "before_deferred_record_ids": list(before_signature[2]),
                "after_deferred_record_ids": list(after_signature[2]),
                "before_descriptor_count": before_signature[3],
                "after_descriptor_count": after_signature[3],
                "pending_starts_before_window": has_pending,
                "retryable_resource_contention": retryable_contention,
                "stalled": stalled,
            }
        )
        state = {
            "schema_version": "geotarget.continuation-controller/v1",
            "status": "running",
            "initial_output": str(initial_output),
            "active_output": str(active_output),
            "windows_completed": len(windows),
            "windows": windows,
            "elapsed_seconds": time.monotonic() - started,
        }
        _atomic_json(output / CONTROLLER_STATE, state)
        if retryable_contention:
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic() - 12.0)))
        if stalled and not has_pending:
            break
    final_state = {
        "schema_version": "geotarget.continuation-controller/v1",
        "status": "completed",
        "initial_output": str(initial_output),
        "active_output": str(active_output),
        "windows_completed": len(windows),
        "windows": windows,
        "stalled": stalled,
        "elapsed_seconds": time.monotonic() - started,
    }
    _atomic_json(output / CONTROLLER_STATE, final_state)
    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--initial-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--controller", action="store_true")
    arguments = parser.parse_args()
    cpus = tuple(int(value) for value in arguments.cpus.split(","))
    if (
        not 0 < arguments.seconds <= 180
        or arguments.cpu not in range(16)
        or not cpus
        or cpus[0] != arguments.cpu
        or len(set(cpus)) != len(cpus)
        or any(cpu not in range(16) for cpu in cpus)
    ):
        raise SystemExit("invalid continuation window")
    if sorted(os.sched_getaffinity(0)) != [arguments.cpu]:
        raise SystemExit("continuation must be pinned to its declared CPU")
    arguments.output.mkdir(parents=True, exist_ok=True)
    if arguments.controller:
        run_controller(
            runtime=arguments.runtime.resolve(),
            source=arguments.source.resolve(),
            source_sha256=arguments.source_sha256,
            initial_output=arguments.initial_output.resolve(),
            output=arguments.output.resolve(),
            seconds=arguments.seconds,
            cpu=arguments.cpu,
            cpus=cpus,
            seed=arguments.seed,
        )
        return
    result = continue_result(
        runtime=arguments.runtime.resolve(),
        source=arguments.source.resolve(),
        source_sha256=arguments.source_sha256,
        initial_output=arguments.initial_output.resolve(),
        output=arguments.output.resolve(),
        seconds=arguments.seconds,
        cpu=arguments.cpu,
        cpus=cpus,
        seed=arguments.seed,
    )
    _atomic_json(arguments.output / "RESULT.json", result)


if __name__ == "__main__":
    main()
