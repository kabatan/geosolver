"""Ordinal-stable multi-core scheduling for the frozen HP/restoration waves."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


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
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(items) - cursor,
            cap_seconds,
        )
        if attempt_seconds == 0.0:
            break
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = [
                executor.submit(run, ordinal, candidate, cpus[slot], attempt_seconds)
                for slot, (ordinal, candidate) in enumerate(batch)
            ]
            for (ordinal, candidate), future in zip(batch, futures, strict=True):
                completed.append((ordinal, candidate, dict(future.result())))
        cursor += len(batch)
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
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Preserve the frozen three-wave policy while dispatching wave ordinals."""

    cpu_tuple = tuple(int(cpu) for cpu in cpus)
    if not cpu_tuple or len(set(cpu_tuple)) != len(cpu_tuple):
        raise ValueError("distinct physical CPUs are required")
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
        if record(candidate, attempt):
            primary_authority_clusters.add(candidate.cluster_ordinal)
        else:
            failed[candidate.cluster_ordinal] = (ordinal, candidate, hp_output)
    primary_complete = len(primary_rows) == len(primaries)
    alternate_rows: list[tuple[int, Any, dict[str, Any]]] = []
    restoration_rows: list[tuple[int, Any, dict[str, Any]]] = []
    eligible_alternates: tuple[tuple[int, Any], ...] = ()
    restorables: tuple[tuple[int, Any, Path], ...] = ()

    if primary_complete:
        eligible_alternates = tuple(
            (ordinal, candidate)
            for ordinal, candidate in retained_alternates
            if candidate.cluster_ordinal in failed
            and not base._same_cluster_authority_exists(candidate, successful_clusters)
        )
        alternate_rows = _run_batch(
            eligible_alternates,
            cpu_tuple,
            run_hp,
            base=base,
            hard_deadline=hard_deadline,
            cap_seconds=base.MAX_HP_ATTEMPT_SECONDS,
        )
        for _ordinal, candidate, attempt in alternate_rows:
            attempts.append(attempt)
            if record(candidate, attempt):
                failed.pop(candidate.cluster_ordinal, None)

    alternate_complete = primary_complete and len(alternate_rows) == len(eligible_alternates)
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
        restoration_rows = _run_batch(
            restoration_items,
            cpu_tuple,
            run_restoration,
            base=base,
            hard_deadline=hard_deadline,
            cap_seconds=base.MAX_RESTORATION_ATTEMPT_SECONDS,
        )
        for _ordinal, candidate, attempt in restoration_rows:
            attempts.append(attempt)
            if record(candidate, attempt):
                failed.pop(candidate.cluster_ordinal, None)

    restoration_complete = alternate_complete and len(restoration_rows) == len(restorables)
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
    }
    return attempts, descriptors, statistics


def install(base: Any, cpus: Sequence[int]) -> None:
    """Install scheduling only at champion-v0's frozen batch-service seam."""

    frozen_batch_service = base._service_candidates.__globals__.get("_ORIGINAL_SERVICE_CANDIDATES")
    if frozen_batch_service is None:
        raise RuntimeError("frozen batch-service seam is unavailable")

    def parallel_batch_service(**kwargs: Any):
        kwargs.pop("cpu", None)
        return service_candidates_parallel(base=base, cpus=cpus, **kwargs)

    base._service_candidates.__globals__["_ORIGINAL_SERVICE_CANDIDATES"] = parallel_batch_service
