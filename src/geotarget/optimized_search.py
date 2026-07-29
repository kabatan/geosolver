"""Deterministic process-parallel scheduling for champion search starts."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEARCH_ARM = (
    "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm"
)
FROZEN_SEARCH_THREAD_KEYS = {
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
}


def _sha256_text(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class OptimizedSearchStatus:
    classification: str
    accepted_output: bool
    elapsed_seconds: float
    shard_count: int
    failed_shards: tuple[tuple[int, int], ...]


def _chunks(start: int, end: int, slots: int) -> tuple[tuple[int, int], ...]:
    count = end - start
    if count < 1:
        raise ValueError("search range must contain at least one start")
    slots = max(1, min(count, slots))
    quotient, remainder = divmod(count, slots)
    chunks: list[tuple[int, int]] = []
    cursor = start
    for slot in range(slots):
        width = quotient + (1 if slot < remainder else 0)
        chunks.append((cursor, cursor + width))
        cursor += width
    return tuple(chunks)


def _checkpoint_chunks(
    start: int, end: int, width: int = 16
) -> tuple[tuple[int, int], ...]:
    """Return the smallest independently recoverable champion work items.

    A start is the algorithm's unit of independence.  Each graceful chunk
    artifact records its completed start prefix; a crashed chunk is discarded
    and retried from its first uncommitted ordinal in the next window.
    """

    if start < 0 or end <= start or width < 1:
        raise ValueError("search range must contain at least one start")
    return tuple(
        (ordinal, min(end, ordinal + width)) for ordinal in range(start, end, width)
    )


def _accepted(
    artifact: Any,
    source_sha256: str,
    *,
    seed: int,
    chunk: tuple[int, int],
    starts: int,
    callbacks_per_start: int,
    cpus: Sequence[int],
) -> bool:
    shard = artifact.get("optimized_shard") if isinstance(artifact, Mapping) else None
    budget = artifact.get("budget") if isinstance(artifact, Mapping) else None
    work = artifact.get("work") if isinstance(artifact, Mapping) else None
    completed = (
        artifact.get("completed_start_ordinals")
        if isinstance(artifact, Mapping)
        else None
    )
    endpoints = artifact.get("endpoints") if isinstance(artifact, Mapping) else None
    affinity = artifact.get("cpu_affinity") if isinstance(artifact, Mapping) else None
    literal = artifact.get("literal_prefix") if isinstance(artifact, Mapping) else None
    thread_environment = (
        artifact.get("thread_environment") if isinstance(artifact, Mapping) else None
    )
    completed_valid = isinstance(completed, list) and all(
        isinstance(value, int) and not isinstance(value, bool) for value in completed
    )
    completed_set = set(completed) if completed_valid else set()
    count_names = (
        "callbacks",
        "finite_callbacks",
        "invalid_callbacks",
        "guard_failed_callbacks",
        "lanes_started",
        "lane_callbacks_min",
        "lane_callbacks_max",
    )
    work_counts_valid = isinstance(work, Mapping) and all(
        isinstance(work.get(name), int)
        and not isinstance(work.get(name), bool)
        and work[name] >= 0
        for name in count_names
    )
    return bool(
        isinstance(artifact, Mapping)
        and artifact.get("completed") is True
        and artifact.get("arm") == SEARCH_ARM
        and artifact.get("source_sha256") == source_sha256
        and artifact.get("source_bytes_unchanged") is True
        and artifact.get("source_evaluator_compiled_from_original_document") is True
        and artifact.get("source_semantics_modified") is False
        and artifact.get("all_source_variables_and_equations_retained") is True
        and artifact.get("explicit_source_bounds_only") is True
        and artifact.get("added_or_inferred_search_bounds") is False
        and artifact.get("gauge_or_symmetry_reduction") is False
        and artifact.get("candidate_received_case_id_family_truth_or_target_count") is False
        and artifact.get("truth_used") is False
        and artifact.get("completeness_claim") is False
        and artifact.get("seed") == seed
        and isinstance(shard, Mapping)
        and shard.get("ordinal_start") == chunk[0]
        and shard.get("ordinal_end") == chunk[1]
        and shard.get("total_prefix_starts") == starts
        and shard.get("callbacks_per_start") == callbacks_per_start
        and shard.get("persistent_worker") is True
        and shard.get("stable_ordinal_replay") is True
        and isinstance(budget, Mapping)
        and budget.get("starts") == starts
        and budget.get("callbacks_per_start") == callbacks_per_start
        and budget.get("aggregate_callback_cap")
        == (chunk[1] - chunk[0]) * callbacks_per_start
        and work_counts_valid
        and work.get("lanes_started") == len(completed_set)
        and work["callbacks"] <= len(completed_set) * callbacks_per_start
        and work["finite_callbacks"] + work["invalid_callbacks"]
        == work["callbacks"]
        and work["guard_failed_callbacks"] <= work["finite_callbacks"]
        and work["lane_callbacks_min"] <= work["lane_callbacks_max"]
        <= callbacks_per_start
        and isinstance(literal, Mapping)
        and isinstance(literal.get("sources"), list)
        and isinstance(literal.get("scale_exponents"), list)
        and len(literal["sources"]) == len(completed_set)
        and len(literal["scale_exponents"]) == len(completed_set)
        and isinstance(endpoints, list)
        and all(
            isinstance(endpoint, Mapping)
            and isinstance(endpoint.get("lane"), int)
            and not isinstance(endpoint.get("lane"), bool)
            and endpoint["lane"] in completed_set
            for endpoint in endpoints
        )
        and artifact.get("endpoints_validated") == len(endpoints)
        and isinstance(artifact.get("safe_endpoint_count"), int)
        and not isinstance(artifact.get("safe_endpoint_count"), bool)
        and 0 <= artifact["safe_endpoint_count"] <= len(endpoints)
        and isinstance(affinity, list)
        and len(affinity) == 1
        and affinity[0] in cpus
        and isinstance(thread_environment, Mapping)
        and set(thread_environment) == FROZEN_SEARCH_THREAD_KEYS
        and all(thread_environment[key] == "1" for key in FROZEN_SEARCH_THREAD_KEYS)
        and "_unvalidated_endpoint_points" not in artifact
        and _sha256_text(literal.get("full_prefix_sha256"))
        and _sha256_text(literal.get("selected_proposal_points_sha256"))
    )


def _run_shard(command: list[str], timeout: float) -> tuple[float, str]:
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
        raise
    if process.returncode:
        tail = (stderr or stdout)[-4000:]
        raise RuntimeError(f"optimized search shard exited {process.returncode}: {tail}")
    return time.monotonic() - started, stderr[-4000:]


def _run_full_prefix(
    *,
    base: Any,
    cpu: int,
    source: Path,
    source_sha256: str,
    search_seconds: float,
    starts: int,
    callbacks_per_start: int,
    aggregate_callback_cap: int,
    seed: int,
    output: Path,
) -> tuple[OptimizedSearchStatus, dict[str, Any] | None]:
    """Run the exact frozen work graph when a single worker owns the prefix."""

    started = time.monotonic()
    artifact_path = output / "search.json"
    artifact_path.unlink(missing_ok=True)
    command = [
        "taskset",
        "--cpu-list",
        str(cpu),
        str(base.PYTHON),
        str(Path(__file__).with_name("search_full_prefix_entrypoint.py")),
        "--worker",
        str(Path(base.SEARCH_WORKER)),
        "--case",
        str(source.resolve()),
        "--case-sha256",
        source_sha256,
        "--arm",
        SEARCH_ARM,
        "--seconds",
        str(search_seconds),
        "--starts",
        str(starts),
        "--callbacks-per-start",
        str(callbacks_per_start),
        "--aggregate-callback-cap",
        str(aggregate_callback_cap),
        "--seed",
        str(seed),
        "--output",
        str(artifact_path),
        "--compiled-evaluator",
    ]
    try:
        _run_shard(command, search_seconds + 8.0)
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return (
            OptimizedSearchStatus(
                classification="OPTIMIZED_FULL_PREFIX_FAILED",
                accepted_output=False,
                elapsed_seconds=time.monotonic() - started,
                shard_count=1,
                failed_shards=((0, starts),),
            ),
            None,
        )
    accepted = bool(
        isinstance(artifact, Mapping)
        and artifact.get("completed") is True
        and artifact.get("arm") == SEARCH_ARM
        and artifact.get("source_sha256") == source_sha256
        and artifact.get("source_bytes_unchanged") is True
        and artifact.get("source_semantics_modified") is False
        and artifact.get("all_source_variables_and_equations_retained") is True
        and artifact.get("truth_used") is False
        and artifact.get("completeness_claim") is False
        and isinstance(artifact.get("optimized_full_prefix"), Mapping)
        and artifact["optimized_full_prefix"].get("frozen_work_graph_preserved") is True
        and artifact["optimized_full_prefix"].get("case_specific_routing") is False
    )
    return (
        OptimizedSearchStatus(
            classification=(
                "OPTIMIZED_FULL_PREFIX_ACCEPTED"
                if accepted
                else "OPTIMIZED_FULL_PREFIX_REJECTED"
            ),
            accepted_output=accepted,
            elapsed_seconds=time.monotonic() - started,
            shard_count=1,
            failed_shards=() if accepted else ((0, starts),),
        ),
        artifact if accepted else None,
    )


def _requeue_crashed_lease(queue_path: Path, worker_id: int) -> bool:
    with queue_path.open("r+", encoding="ascii") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        state = json.loads(stream.read())
        leased = {str(key): int(value) for key, value in state.get("leased", {}).items()}
        ordinal = leased.pop(str(worker_id), None)
        if ordinal is None:
            return False
        retries = {int(value) for value in state.get("retry", ())}
        retries.add(ordinal)
        state["retry"] = sorted(retries)
        state["leased"] = leased
        stream.seek(0)
        stream.truncate()
        stream.write(json.dumps(state, separators=(",", ":")))
        stream.flush()
        os.fsync(stream.fileno())
    return True


def _sum_mapping(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, Mapping):
            counter.update(
                {
                    str(name): int(amount)
                    for name, amount in value.items()
                    if isinstance(amount, int)
                }
            )
    return dict(sorted(counter.items()))


def _merge(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
    chunks: Sequence[tuple[int, int]],
    cpus: Sequence[int],
    failed: Sequence[tuple[int, int]],
    elapsed: float,
    ordinal_start: int,
    accepted_prefix_end: int,
    requested_ordinal_end: int,
    total_starts: int,
) -> dict[str, Any]:
    first = dict(artifacts[0])
    literal_rows = [
        artifact.get("literal_prefix")
        for artifact in artifacts
        if isinstance(artifact.get("literal_prefix"), Mapping)
    ]
    full_prefix_hashes = {
        str(row.get("full_prefix_sha256") or row.get("sha256"))
        for row in literal_rows
    }
    if len(literal_rows) != len(artifacts) or len(full_prefix_hashes) != 1:
        raise ValueError("search shards disagree about the full proposal prefix")
    literal_prefix = dict(literal_rows[0])
    literal_prefix["sources"] = [
        value for row in literal_rows for value in row.get("sources", ())
    ]
    literal_prefix["scale_exponents"] = [
        value for row in literal_rows for value in row.get("scale_exponents", ())
    ]
    literal_prefix["selected_shard_proposal_sha256"] = [
        row.get("selected_proposal_points_sha256") for row in literal_rows
    ]
    literal_prefix["sources_scope"] = "completed_ordinal_prefix"
    literal_prefix["completed_prefix_end"] = accepted_prefix_end
    literal_prefix.pop("selected_proposal_points_sha256", None)
    endpoints = sorted(
        (
            dict(endpoint)
            for artifact in artifacts
            for endpoint in artifact.get("endpoints", ())
            if isinstance(endpoint, Mapping) and isinstance(endpoint.get("lane"), int)
        ),
        key=lambda endpoint: int(endpoint["lane"]),
    )
    work_rows = [
        artifact.get("work")
        for artifact in artifacts
        if isinstance(artifact.get("work"), Mapping)
    ]
    numeric_work_keys = (
        "callbacks",
        "finite_callbacks",
        "invalid_callbacks",
        "guard_failed_callbacks",
        "lanes_started",
    )
    work = {
        key: sum(int(row.get(key, 0)) for row in work_rows)
        for key in numeric_work_keys
    }
    lane_mins = [int(row.get("lane_callbacks_min", 0)) for row in work_rows]
    lane_maxes = [int(row.get("lane_callbacks_max", 0)) for row in work_rows]
    work["lane_callbacks_min"] = min(lane_mins, default=0)
    work["lane_callbacks_max"] = max(lane_maxes, default=0)
    best = [
        float(row["best_residual_inf"])
        for row in work_rows
        if isinstance(row.get("best_residual_inf"), int | float)
    ]
    work["best_residual_inf"] = min(best) if best else None
    completed_ordinals = sorted(
        {
            int(ordinal)
            for artifact in artifacts
            for ordinal in artifact.get("completed_start_ordinals", ())
            if isinstance(ordinal, int)
        }
    )
    activation_rows = [
        artifact.get("activation")
        for artifact in artifacts
        if isinstance(artifact.get("activation"), Mapping)
    ]
    first.update(
        {
            "source_sha256": source_sha256,
            "literal_prefix": literal_prefix,
            "completed": not failed,
            "endpoints": endpoints,
            "endpoints_validated": sum(
                int(artifact.get("endpoints_validated", 0)) for artifact in artifacts
            ),
            "safe_endpoint_count": sum(
                int(artifact.get("safe_endpoint_count", 0)) for artifact in artifacts
            ),
            "work": work,
            "budget": {
                "seconds": max(
                    float(artifact.get("budget", {}).get("seconds", 0.0))
                    for artifact in artifacts
                ),
                "starts": total_starts,
                "callbacks_per_start": 600,
                "aggregate_callback_cap": (
                    requested_ordinal_end - ordinal_start
                ) * 600,
            },
            "completed_start_ordinals": completed_ordinals,
            "cpu_affinity": list(cpus),
            "activation": {
                "status_counts": _sum_mapping(activation_rows, "status_counts"),
                "counter_sums": _sum_mapping(activation_rows, "counter_sums"),
            },
            "elapsed_wall_seconds": elapsed,
            "optimized_parallel_search": {
                "schema_version": "geotarget.optimized-parallel-search/v1",
                "stable_ordinal_merge": True,
                "chunks": [list(chunk) for chunk in chunks],
                "cpus": list(cpus),
                "failed_chunks": [list(chunk) for chunk in failed],
                "source_sha256": source_sha256,
                "ordinal_start": ordinal_start,
                "ordinal_end": requested_ordinal_end,
                "accepted_prefix_end": accepted_prefix_end,
                "completed_start_ordinals": completed_ordinals,
                "all_requested_starts_completed": completed_ordinals
                == list(range(ordinal_start, requested_ordinal_end)),
                "proposal_slice_sha256": [
                    artifact.get("literal_prefix", {}).get(
                        "selected_proposal_points_sha256"
                    )
                    for artifact in artifacts
                    if isinstance(artifact.get("literal_prefix"), Mapping)
                ],
            },
        }
    )
    return first


def run_parallel_search(
    *,
    base: Any,
    cpus: Sequence[int],
    source: Path,
    source_sha256: str,
    search_seconds: float,
    starts: int,
    callbacks_per_start: int,
    aggregate_callback_cap: int,
    seed: int,
    output: Path,
    ordinal_start: int = 0,
    ordinal_end: int | None = None,
) -> tuple[OptimizedSearchStatus, dict[str, Any] | None]:
    started = time.monotonic()
    range_end = starts if ordinal_end is None else ordinal_end
    if not 0 <= ordinal_start < range_end <= starts:
        raise ValueError("optimized search range must lie within the proposal prefix")
    if callbacks_per_start != 600:
        raise ValueError("the qualified optimized search requires 600 callbacks per start")
    if aggregate_callback_cap != (range_end - ordinal_start) * callbacks_per_start:
        raise ValueError("aggregate callback cap must equal the selected ordinal work")
    if len(cpus) == 1 and ordinal_start == 0 and range_end == starts:
        return _run_full_prefix(
            base=base,
            cpu=int(cpus[0]),
            source=source,
            source_sha256=source_sha256,
            search_seconds=search_seconds,
            starts=starts,
            callbacks_per_start=callbacks_per_start,
            aggregate_callback_cap=aggregate_callback_cap,
            seed=seed,
            output=output,
        )
    chunks = _checkpoint_chunks(ordinal_start, range_end, width=1)
    shard_root = output / "optimized-search-shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    worker = Path(base.SEARCH_WORKER)
    outputs = [shard_root / f"{start:06d}-{end:06d}.json" for start, end in chunks]
    for path in outputs:
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".tmp").unlink(missing_ok=True)
    queue_path = shard_root / "next-ordinal.txt"
    queue_path.write_text(
        json.dumps(
            {"next": ordinal_start, "retry": [], "leased": {}},
            separators=(",", ":"),
        ),
        encoding="ascii",
    )
    failed: list[tuple[int, int]] = []
    commands = [
        [
                "taskset",
                "--cpu-list",
                str(cpu),
                str(base.PYTHON),
                str(Path(__file__).with_name("search_pool_worker_entrypoint.py")),
                "--worker",
                str(worker),
                "--source",
                str(source.resolve()),
                "--source-sha256",
                source_sha256,
                "--seconds",
                str(search_seconds),
                "--process-started",
                str(started),
                "--total-starts",
                str(starts),
                "--ordinal-start",
                str(ordinal_start),
                "--ordinal-end",
                str(range_end),
                "--callbacks-per-start",
                str(callbacks_per_start),
                "--seed",
                str(seed),
                "--queue",
                str(queue_path),
                "--output",
                str(shard_root),
                "--worker-id",
                str(worker_id),
                "--worker-count",
                str(len(cpus)),
                *(["--coordinator"] if worker_id == 0 else []),
                "--compiled-evaluator",
        ]
        for worker_id, cpu in enumerate(cpus)
    ]

    def run_pool_worker(worker_id: int, command: list[str]) -> None:
        try:
            _run_shard(command, search_seconds + 8.0)
            return
        except Exception:
            _requeue_crashed_lease(queue_path, worker_id)
        remaining = started + search_seconds - time.monotonic()
        if remaining > 1.0:
            _run_shard(command, remaining + 8.0)

    with ThreadPoolExecutor(max_workers=len(commands)) as executor:
        futures = [
            executor.submit(run_pool_worker, worker_id, command)
            for worker_id, command in enumerate(commands)
        ]
        for future in futures:
            with suppress(Exception):
                future.result()
    artifacts: list[dict[str, Any]] = []
    accepted_chunks: list[tuple[int, int]] = []
    prefix_open = True
    for chunk, path in zip(chunks, outputs, strict=True):
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            if chunk not in failed:
                failed.append(chunk)
            prefix_open = False
            continue
        completed = artifact.get("completed_start_ordinals")
        completed_prefix = (
            isinstance(completed, list)
            and bool(completed)
            and completed == list(range(chunk[0], chunk[0] + len(completed)))
            and len(completed) <= chunk[1] - chunk[0]
        )
        if (
            prefix_open
            and _accepted(
                artifact,
                source_sha256,
                seed=seed,
                chunk=chunk,
                starts=starts,
                callbacks_per_start=callbacks_per_start,
                cpus=cpus,
            )
            and completed_prefix
        ):
            artifacts.append(artifact)
            accepted_chunks.append((chunk[0], chunk[0] + len(completed)))
            if len(completed) != chunk[1] - chunk[0]:
                prefix_open = False
        else:
            prefix_open = False
            if chunk not in failed:
                failed.append(chunk)
    failed.sort()
    elapsed = time.monotonic() - started
    if not artifacts:
        return (
            OptimizedSearchStatus(
                classification="OPTIMIZED_PARALLEL_SEARCH_FAILED",
                accepted_output=False,
                elapsed_seconds=elapsed,
                shard_count=len(chunks),
                failed_shards=tuple(failed or chunks),
            ),
            None,
        )
    effective_end = accepted_chunks[-1][1]
    merged = _merge(
        artifacts,
        source_sha256=source_sha256,
        chunks=accepted_chunks,
        cpus=cpus,
        failed=failed,
        elapsed=elapsed,
        ordinal_start=ordinal_start,
        accepted_prefix_end=effective_end,
        requested_ordinal_end=range_end,
        total_starts=starts,
    )
    artifact_path = output / "search.json"
    artifact_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return (
        OptimizedSearchStatus(
            classification=(
                "OPTIMIZED_PARALLEL_SEARCH_ACCEPTED"
                if not failed
                else "OPTIMIZED_PARALLEL_SEARCH_PARTIAL"
            ),
            accepted_output=True,
            elapsed_seconds=elapsed,
            shard_count=len(chunks),
            failed_shards=tuple(failed),
        ),
        merged,
    )


def install(base: Any, cpus: Sequence[int]) -> None:
    """Install the optimized search adapter at the frozen subprocess seam."""

    cpu_tuple = tuple(int(cpu) for cpu in cpus)
    if not cpu_tuple or len(set(cpu_tuple)) != len(cpu_tuple):
        raise ValueError("distinct physical CPUs are required")
    original_plan = base._plan

    def optimized_plan(**kwargs: Any) -> dict[str, Any]:
        plan = dict(original_plan(**kwargs))
        plan.update(
            {
                "engine_variant": "optimized",
                "optimized_search_adapter_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
                "optimized_search_physical_cpus": list(cpu_tuple),
                "search_start_partition": (
                    "frozen full-prefix protocol on one core; complete-start map items "
                    "with contiguous ordinal-prefix reduction on multiple cores"
                ),
                "frozen_search_worker_bytes_unchanged": True,
                "frozen_full_prefix_protocol_on_single_core": len(cpu_tuple) == 1,
                "deadline_terminal_parallel_starts_committed": False,
                "case_or_corpus_specific_routing": False,
            }
        )
        return plan

    def optimized_run_search(**kwargs: Any):
        try:
            status, artifact = run_parallel_search(base=base, cpus=cpu_tuple, **kwargs)
        except Exception as error:
            raise RuntimeError(
                "optimized search adapter failed before a safe checkpoint"
            ) from error
        return status, artifact

    base._plan = optimized_plan
    base._run_search = optimized_run_search
