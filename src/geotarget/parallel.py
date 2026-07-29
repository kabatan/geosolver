"""Ordinal-stable multi-core scheduling for the frozen HP/restoration waves."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .hp_preloader import SOCKET_ENV, PersistentHpPool
from .hp_wave_checkpoint import create as create_wave_checkpoint
from .hp_wave_checkpoint import validate as validate_wave_checkpoint
from .reservoir_checkpoint import search_binding, write_checkpoint
from .runtime_broker import (
    BROKER_SESSION_ENV,
    BROKER_SOCKET_ENV,
    ensure_hp_via_broker,
)


class _BrokerOwnedHpPool:
    """Health-check a pool owned by the long-lived product process."""

    def __init__(self, cpus: Sequence[int], directory: Path) -> None:
        self.cpus = tuple(int(cpu) for cpu in cpus)
        self.directory = Path(directory)

    def ensure(self) -> None:
        observed = ensure_hp_via_broker(self.cpus)
        if observed.resolve() != self.directory.resolve():
            raise RuntimeError("runtime broker HP pool directory changed during a solve")


def attempt_is_resource_busy(attempt: Mapping[str, Any]) -> bool:
    """Return whether an HP attempt was deferred solely by resource admission."""

    return bool(attempt.get("resource_busy_deferred"))


def _run_batch(
    items: Sequence[tuple[int, Any]],
    cpus: Sequence[int],
    run: Callable[[int, Any, int, float], Mapping[str, Any]],
    *,
    base: Any,
    hard_deadline: float,
    cap_seconds: float,
) -> list[tuple[int, Any, dict[str, Any]]]:
    completed: list[tuple[int, Any, dict[str, Any]]] = []
    cursor = 0
    while cursor < len(items):
        batch = items[cursor : cursor + len(cpus)]
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
        virtual_remaining = remaining
        attempt_seconds: list[float] = []
        # Derive the timeout for each ordinal using the frozen recurrence.  A
        # whole CPU batch must not inherit the first candidate's larger budget.
        for offset in range(len(batch)):
            seconds = base._wave_attempt_seconds(
                virtual_remaining,
                len(items) - cursor - offset,
                cap_seconds,
            )
            attempt_seconds.append(seconds)
            virtual_remaining = max(0.0, virtual_remaining - seconds)
        runnable = tuple(
            (slot, item, seconds)
            for slot, (item, seconds) in enumerate(zip(batch, attempt_seconds, strict=True))
            if seconds > 0.0
        )
        if not runnable:
            break

        with ThreadPoolExecutor(max_workers=len(runnable)) as executor:
            futures = [
                executor.submit(run, ordinal, candidate, cpus[slot], seconds)
                for slot, (ordinal, candidate), seconds in runnable
            ]
            for (_slot, (ordinal, candidate), _seconds), future in zip(
                runnable, futures, strict=True
            ):
                completed.append((ordinal, candidate, dict(future.result())))
        cursor += len(runnable)
        if len(runnable) != len(batch):
            break
    return completed


def service_candidates_parallel(
    *,
    base: Any,
    source: Path,
    source_sha256: str,
    candidates: Sequence[Any],
    output: Path,
    hard_deadline: float,
    cpus: Sequence[int],
    pool: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Preserve the frozen three-wave policy while dispatching wave ordinals."""

    cpu_tuple = tuple(int(cpu) for cpu in cpus)
    if not cpu_tuple or len(set(cpu_tuple)) != len(cpu_tuple):
        raise ValueError("distinct physical CPUs are required")
    # Small protocol fakes used by scheduler unit tests deliberately omit the
    # frozen subprocess environment.  Keep the scheduling seam independently
    # testable; real champion modules always expose THREAD_ENVIRONMENT.
    if not hasattr(base, "THREAD_ENVIRONMENT"):

        class _AlreadyReady:
            @staticmethod
            def ensure() -> None:
                return None

        return _service_candidates_with_pool(
            base=base,
            source=source,
            source_sha256=source_sha256,
            candidates=candidates,
            output=output,
            hard_deadline=hard_deadline,
            cpu_tuple=cpu_tuple,
            pool=_AlreadyReady(),
        )
    if pool is not None:
        pool.ensure()
        return _service_candidates_with_pool(
            base=base,
            source=source,
            source_sha256=source_sha256,
            candidates=candidates,
            output=output,
            hard_deadline=hard_deadline,
            cpu_tuple=cpu_tuple,
            pool=pool,
        )
    hp_worker = _hp_worker_path()
    previous_preloader = base.THREAD_ENVIRONMENT.get(SOCKET_ENV)
    pool = PersistentHpPool(cpu_tuple, hp_worker, base.THREAD_ENVIRONMENT)
    pool.__enter__()
    base.THREAD_ENVIRONMENT[SOCKET_ENV] = str(pool.directory)
    try:
        return _service_candidates_with_pool(
            base=base,
            source=source,
            source_sha256=source_sha256,
            candidates=candidates,
            output=output,
            hard_deadline=hard_deadline,
            cpu_tuple=cpu_tuple,
            pool=pool,
        )
    finally:
        if previous_preloader is None:
            base.THREAD_ENVIRONMENT.pop(SOCKET_ENV, None)
        else:
            base.THREAD_ENVIRONMENT[SOCKET_ENV] = previous_preloader
        pool.__exit__(None, None, None)


def _service_candidates_with_pool(
    *,
    base: Any,
    source: Path,
    source_sha256: str,
    candidates: Sequence[Any],
    output: Path,
    hard_deadline: float,
    cpu_tuple: tuple[int, ...],
    pool: Any,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    indexed = tuple(enumerate(candidates))
    all_primaries = tuple(
        (ordinal, candidate) for ordinal, candidate in indexed if candidate.cluster_rank == 0
    )
    retained_alternates = tuple(
        (ordinal, candidate) for ordinal, candidate in indexed if candidate.cluster_rank == 1
    )
    initial_remaining = max(0.0, hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS)
    capacity = base._primary_tranche_capacity(initial_remaining, len(all_primaries))
    primaries, deferred = base._select_primary_tranche(all_primaries, capacity)
    attempts: list[dict[str, Any]] = []
    descriptors: dict[str, dict[str, Any]] = {}
    successful_clusters: set[int] = set()
    primary_authority_clusters: set[int] = set()
    failed: dict[int, tuple[int, Any, Path]] = {}
    busy_primaries: list[tuple[int, Any]] = []

    def record(candidate: Any, attempt: Mapping[str, Any]) -> bool:
        descriptor = attempt.get("descriptor")
        if attempt.get("authority_pass") is not True or not isinstance(descriptor, Mapping):
            return False
        descriptors.setdefault(base._descriptor_key(descriptor), dict(descriptor))
        successful_clusters.add(candidate.cluster_ordinal)
        return True

    def run_hp(ordinal: int, candidate: Any, cpu: int, seconds: float):
        target = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        return base._run_hp_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=target,
            timeout_seconds=seconds,
        )

    pool.ensure()
    primary_rows = _run_batch(
        primaries,
        cpu_tuple,
        run_hp,
        base=base,
        hard_deadline=hard_deadline,
        cap_seconds=base.MAX_HP_ATTEMPT_SECONDS,
    )
    for ordinal, candidate, attempt in primary_rows:
        attempts.append(attempt)
        hp_output = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        if attempt_is_resource_busy(attempt):
            busy_primaries.append((ordinal, candidate))
            continue
        if record(candidate, attempt):
            primary_authority_clusters.add(candidate.cluster_ordinal)
        else:
            failed[candidate.cluster_ordinal] = (ordinal, candidate, hp_output)
    selected_primary_complete = len(primary_rows) == len(primaries) and not busy_primaries
    primary_complete = selected_primary_complete and not deferred
    alternate_rows: list[tuple[int, Any, dict[str, Any]]] = []
    restoration_rows: list[tuple[int, Any, dict[str, Any]]] = []
    busy_alternates: list[tuple[int, Any]] = []
    busy_restorations: list[tuple[int, Any, Path]] = []
    eligible_alternates: tuple[tuple[int, Any], ...] = ()
    restorables: tuple[tuple[int, Any, Path], ...] = ()

    if selected_primary_complete:
        eligible_alternates = tuple(
            (ordinal, candidate)
            for ordinal, candidate in retained_alternates
            if candidate.cluster_ordinal in failed
            and not base._same_cluster_authority_exists(candidate, successful_clusters)
        )
        pool.ensure()
        alternate_rows = _run_batch(
            eligible_alternates,
            cpu_tuple,
            run_hp,
            base=base,
            hard_deadline=hard_deadline,
            cap_seconds=base.MAX_HP_ATTEMPT_SECONDS,
        )
        for ordinal, candidate, attempt in alternate_rows:
            attempts.append(attempt)
            if attempt_is_resource_busy(attempt):
                busy_alternates.append((ordinal, candidate))
                continue
            if record(candidate, attempt):
                failed.pop(candidate.cluster_ordinal, None)

    alternate_complete = (
        selected_primary_complete
        and len(alternate_rows) == len(eligible_alternates)
        and not busy_alternates
    )
    if alternate_complete:
        restorables = tuple(failed[key] for key in sorted(failed, key=lambda item: failed[item][0]))

        def run_restoration(ordinal: int, candidate: Any, cpu: int, seconds: float):
            failed_output = failed[candidate.cluster_ordinal][2]
            target = output / "restoration" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
            return base._run_restoration_candidate(
                source=source,
                source_sha256=source_sha256,
                candidate=candidate,
                cpu=cpu,
                failed_authority_artifact=failed_output / "authority.json",
                output=target,
                timeout_seconds=seconds,
            )

        restoration_items = tuple((ordinal, candidate) for ordinal, candidate, _ in restorables)
        pool.ensure()
        restoration_rows = _run_batch(
            restoration_items,
            cpu_tuple,
            run_restoration,
            base=base,
            hard_deadline=hard_deadline,
            cap_seconds=base.MAX_RESTORATION_ATTEMPT_SECONDS,
        )
        for ordinal, candidate, attempt in restoration_rows:
            attempts.append(attempt)
            if attempt_is_resource_busy(attempt):
                busy_restorations.append((ordinal, candidate, failed[candidate.cluster_ordinal][2]))
                continue
            if record(candidate, attempt):
                failed.pop(candidate.cluster_ordinal, None)

    restoration_complete = (
        alternate_complete and len(restoration_rows) == len(restorables) and not busy_restorations
    )
    pending_primary = (
        tuple(candidate.record_id for _ordinal, candidate in busy_primaries)
        + tuple(candidate.record_id for _ordinal, candidate in primaries[len(primary_rows) :])
        + tuple(candidate.record_id for _ordinal, candidate in deferred)
    )
    pending_alternate = tuple(
        candidate.record_id for _ordinal, candidate in busy_alternates
    ) + tuple(
        candidate.record_id for _ordinal, candidate in eligible_alternates[len(alternate_rows) :]
    )
    pending_restoration = tuple(
        candidate.record_id for _ordinal, candidate, _artifact in busy_restorations
    ) + tuple(
        candidate.record_id
        for _ordinal, candidate, _artifact in restorables[len(restoration_rows) :]
    )
    if pending_primary:
        wave_stage = "primary"
    elif pending_alternate:
        wave_stage = "alternate"
    elif pending_restoration:
        wave_stage = "restoration"
    else:
        wave_stage = "complete"
    failed_rows = [
        {
            "cluster_ordinal": int(cluster),
            "record_id": str(candidate.record_id),
            "ordinal": int(ordinal),
            "artifact_directory": str(artifact.resolve()),
        }
        for cluster, (ordinal, candidate, artifact) in sorted(
            failed.items(), key=lambda item: item[1][0]
        )
    ]
    wave_checkpoint = create_wave_checkpoint(
        stage=wave_stage,
        batch_record_ids=[candidate.record_id for candidate in candidates],
        pending_primary_record_ids=pending_primary,
        pending_alternate_record_ids=pending_alternate,
        pending_restoration_record_ids=pending_restoration,
        failed_primaries=failed_rows,
    )
    statistics = {
        "policy": "frozen primary, alternate, restoration waves; stable ordinal dispatch",
        "primary_total": len(all_primaries),
        "primary_tranche_capacity": capacity,
        "primary_selected_count": len(primaries),
        "primary_deferred_unknown_count": len(deferred),
        "unselected_primary_disposition": "DEFERRED_UNKNOWN_NOT_DISCARDED",
        "primary_attempted": len(primary_rows),
        "primary_wave_complete": primary_complete,
        "all_discovered_primaries_served": primary_complete and not deferred,
        "eligible_alternate_count": len(eligible_alternates),
        "alternate_attempted": len(alternate_rows),
        "alternate_wave_complete": alternate_complete,
        "same_cluster_alternates_skipped_after_authority": sum(
            candidate.cluster_ordinal in primary_authority_clusters
            for _ordinal, candidate in retained_alternates
        ),
        "eligible_restoration_count": len(restorables),
        "restoration_attempted": len(restoration_rows),
        "restoration_wave_complete": restoration_complete,
        "minimum_reserved_seconds_per_unserved_wave_candidate": base.MIN_HP_ATTEMPT_SECONDS,
        "maximum_primary_or_alternate_seconds": base.MAX_HP_ATTEMPT_SECONDS,
        "maximum_restoration_seconds": base.MAX_RESTORATION_ATTEMPT_SECONDS,
        "cross_cluster_candidate_suppression": False,
        "parallel_physical_cpus": list(cpu_tuple),
        "stable_attempt_merge": True,
        "durable_wave_checkpoint": wave_checkpoint,
    }
    return attempts, descriptors, statistics


def resume_candidates_parallel(
    *,
    base: Any,
    source: Path,
    source_sha256: str,
    all_candidates: Sequence[Any],
    output: Path,
    hard_deadline: float,
    cpus: Sequence[int],
    checkpoint: Mapping[str, Any],
    pool: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Resume the exact unfinished stage of a product-owned frozen wave."""

    state = validate_wave_checkpoint(checkpoint)
    if state is None:
        raise ValueError("an HP wave checkpoint is required")
    cpu_tuple = tuple(int(cpu) for cpu in cpus)
    if not cpu_tuple or len(set(cpu_tuple)) != len(cpu_tuple):
        raise ValueError("distinct physical CPUs are required")
    by_record = {
        str(candidate.record_id): candidate
        for candidate in (
            tuple(all_candidates) + tuple(getattr(all_candidates, "deadline_backlog", ()))
        )
    }

    def candidates_for(field: str) -> tuple[Any, ...]:
        identifiers = state[field]
        try:
            return tuple(by_record[identifier] for identifier in identifiers)
        except KeyError as error:
            raise RuntimeError("HP wave checkpoint references an unknown candidate") from error

    failed: dict[int, tuple[int, Any, Path]] = {}
    for row in state["failed_primaries"]:
        candidate = by_record.get(str(row["record_id"]))
        if candidate is None:
            raise RuntimeError("HP wave failed primary is absent from the reservoir")
        failed[int(row["cluster_ordinal"])] = (
            int(row["ordinal"]),
            candidate,
            Path(str(row["artifact_directory"])).resolve(),
        )

    own_pool = pool is None
    if pool is None:
        hp_worker = _hp_worker_path()
        pool = PersistentHpPool(cpu_tuple, hp_worker, base.THREAD_ENVIRONMENT)
        pool.__enter__()
    attempts: list[dict[str, Any]] = []
    descriptors: dict[str, dict[str, Any]] = {}
    pending_primary = list(candidates_for("pending_primary_record_ids"))
    pending_alternate = list(candidates_for("pending_alternate_record_ids"))
    pending_restoration = list(candidates_for("pending_restoration_record_ids"))
    stage = str(state["stage"])

    def record(candidate: Any, attempt: Mapping[str, Any]) -> bool:
        descriptor = attempt.get("descriptor")
        if attempt.get("authority_pass") is not True or not isinstance(descriptor, Mapping):
            return False
        descriptors.setdefault(base._descriptor_key(descriptor), dict(descriptor))
        return True

    def run_hp(ordinal: int, candidate: Any, cpu: int, seconds: float):
        target = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        return base._run_hp_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=target,
            timeout_seconds=seconds,
        )

    try:
        pool.ensure()
        if stage == "primary" and pending_primary:
            remaining = max(
                0.0,
                hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS,
            )
            capacity = base._primary_tranche_capacity(remaining, len(pending_primary))
            admitted_primary = pending_primary[:capacity]
            primary_items = tuple(
                (int(candidate.cluster_ordinal), candidate) for candidate in admitted_primary
            )
            rows = _run_batch(
                primary_items,
                cpu_tuple,
                run_hp,
                base=base,
                hard_deadline=hard_deadline,
                cap_seconds=base.MAX_HP_ATTEMPT_SECONDS,
            )
            attempts.extend(attempt for _ordinal, _candidate, attempt in rows)
            busy_candidates: list[Any] = []
            for ordinal, candidate, attempt in rows:
                if attempt_is_resource_busy(attempt):
                    busy_candidates.append(candidate)
                    continue
                artifact = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
                if not record(candidate, attempt):
                    failed[candidate.cluster_ordinal] = (ordinal, candidate, artifact.resolve())
            pending_primary = busy_candidates + pending_primary[len(rows) :]
            if not pending_primary:
                stage = "alternate"
                batch_ids = set(state["batch_record_ids"])
                successful = set(failed)
                pending_alternate = [
                    candidate
                    for candidate in by_record.values()
                    if candidate.record_id in batch_ids
                    and candidate.cluster_rank == 1
                    and candidate.cluster_ordinal in successful
                ]

        if stage == "alternate":
            alternate_items = tuple(
                (int(candidate.cluster_ordinal), candidate) for candidate in pending_alternate
            )
            pool.ensure()
            rows = _run_batch(
                alternate_items,
                cpu_tuple,
                run_hp,
                base=base,
                hard_deadline=hard_deadline,
                cap_seconds=base.MAX_HP_ATTEMPT_SECONDS,
            )
            attempts.extend(attempt for _ordinal, _candidate, attempt in rows)
            busy_candidates = []
            for _ordinal, candidate, attempt in rows:
                if attempt_is_resource_busy(attempt):
                    busy_candidates.append(candidate)
                    continue
                if record(candidate, attempt):
                    failed.pop(candidate.cluster_ordinal, None)
            pending_alternate = busy_candidates + pending_alternate[len(rows) :]
            if not pending_alternate:
                stage = "restoration"
                pending_restoration = [
                    candidate
                    for _cluster, (_ordinal, candidate, _artifact) in sorted(
                        failed.items(), key=lambda item: item[1][0]
                    )
                ]

        if stage == "restoration":

            def run_restoration(ordinal: int, candidate: Any, cpu: int, seconds: float):
                failed_output = failed[candidate.cluster_ordinal][2]
                target = (
                    output / "restoration" / (f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}")
                )
                return base._run_restoration_candidate(
                    source=source,
                    source_sha256=source_sha256,
                    candidate=candidate,
                    cpu=cpu,
                    failed_authority_artifact=failed_output / "authority.json",
                    output=target,
                    timeout_seconds=seconds,
                )

            restoration_items = tuple(
                (failed[candidate.cluster_ordinal][0], candidate)
                for candidate in pending_restoration
            )
            pool.ensure()
            rows = _run_batch(
                restoration_items,
                cpu_tuple,
                run_restoration,
                base=base,
                hard_deadline=hard_deadline,
                cap_seconds=base.MAX_RESTORATION_ATTEMPT_SECONDS,
            )
            attempts.extend(attempt for _ordinal, _candidate, attempt in rows)
            busy_candidates = []
            for _ordinal, candidate, attempt in rows:
                if attempt_is_resource_busy(attempt):
                    busy_candidates.append(candidate)
                    continue
                if record(candidate, attempt):
                    failed.pop(candidate.cluster_ordinal, None)
            pending_restoration = busy_candidates + pending_restoration[len(rows) :]
            if not pending_restoration:
                stage = "complete"
    finally:
        if own_pool:
            pool.__exit__(None, None, None)

    next_checkpoint = create_wave_checkpoint(
        stage=stage,
        batch_record_ids=state["batch_record_ids"],
        pending_primary_record_ids=[candidate.record_id for candidate in pending_primary],
        pending_alternate_record_ids=[candidate.record_id for candidate in pending_alternate],
        pending_restoration_record_ids=[candidate.record_id for candidate in pending_restoration],
        failed_primaries=[
            {
                "cluster_ordinal": int(cluster),
                "record_id": str(candidate.record_id),
                "ordinal": int(ordinal),
                "artifact_directory": str(artifact),
            }
            for cluster, (ordinal, candidate, artifact) in sorted(
                failed.items(), key=lambda item: item[1][0]
            )
        ],
    )
    return (
        attempts,
        descriptors,
        {
            "policy": "resume exact interrupted frozen HP wave stage",
            "primary_attempted": sum(
                attempt.get("attempt_kind") == "PRIMARY_NUMERICAL_V3" for attempt in attempts
            ),
            "durable_wave_checkpoint": next_checkpoint,
            "parallel_physical_cpus": list(cpu_tuple),
            "stable_attempt_merge": True,
        },
    )


def install(
    base: Any,
    cpus: Sequence[int],
    *,
    post_search_seconds: float = 34.0,
    reservoir_checkpoint_path: Path | None = None,
    source_sha256: str | None = None,
) -> None:
    """Install scheduling only at champion-v0's frozen batch-service seam.

    Each champion window retains the frozen 146:34 search/authority split.
    Product continuation consumes only the resulting checkpoint and may open
    another bounded window without changing per-candidate timeout semantics.
    """

    frozen_batch_service = base._service_candidates.__globals__.get("_ORIGINAL_SERVICE_CANDIDATES")
    if frozen_batch_service is None:
        raise RuntimeError("frozen batch-service seam is unavailable")

    cpu_tuple = tuple(int(cpu) for cpu in cpus)
    for name in (SOCKET_ENV, BROKER_SOCKET_ENV, BROKER_SESSION_ENV):
        if name in os.environ:
            base.THREAD_ENVIRONMENT[name] = os.environ[name]
    inherited_pool = base.THREAD_ENVIRONMENT.get(SOCKET_ENV)
    broker_owned = bool(
        inherited_pool
        and base.THREAD_ENVIRONMENT.get(BROKER_SOCKET_ENV)
        and base.THREAD_ENVIRONMENT.get(BROKER_SESSION_ENV)
    )
    if broker_owned:
        pool = _BrokerOwnedHpPool(cpu_tuple, Path(str(inherited_pool)))
        pool.ensure()
    else:
        pool = PersistentHpPool(cpu_tuple, _hp_worker_path(), base.THREAD_ENVIRONMENT)
        pool.close_at_process_exit()
        base.THREAD_ENVIRONMENT[SOCKET_ENV] = str(pool.directory)
    base._geotarget_hp_pool = pool
    base._geotarget_post_search_seconds = float(post_search_seconds)

    if reservoir_checkpoint_path is not None:
        if source_sha256 is None:
            raise ValueError("source SHA-256 is required for a reservoir checkpoint")
        install_reservoir_checkpoint(base, reservoir_checkpoint_path, source_sha256)

    def parallel_batch_service(**kwargs: Any):
        kwargs.pop("cpu", None)
        kwargs["hard_deadline"] = min(
            float(kwargs["hard_deadline"]), time.monotonic() + post_search_seconds
        )
        return service_candidates_parallel(base=base, cpus=cpu_tuple, pool=pool, **kwargs)

    base._service_candidates.__globals__["_ORIGINAL_SERVICE_CANDIDATES"] = parallel_batch_service


def install_reservoir_checkpoint(base: Any, checkpoint_path: Path, source_sha256: str) -> None:
    """Persist the exact initial reservoir before another process must resume it."""

    original_fresh = base._fresh_replay_candidates
    resolved = checkpoint_path.resolve()

    def checkpointing_fresh(*args: Any, **kwargs: Any):
        reservoir = original_fresh(*args, **kwargs)
        search_path = resolved.parent / "search.json"
        if not search_path.is_file():
            raise RuntimeError("search artifact is absent at reservoir commit")
        search = json.loads(search_path.read_text(encoding="utf-8"))
        write_checkpoint(
            resolved,
            binding=search_binding(source_sha256, search),
            reservoir=reservoir,
        )
        return reservoir

    base._fresh_replay_candidates = checkpointing_fresh


def _hp_worker_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "_engine/runtime/solver/research/experiments/EXP-V15-243-001/candidates"
        / "point_on_circle_periodic_semantics/champion_composition_worker_no_1280.py"
    )
