from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import ValidationError

from geotarget.engine import (
    ENGINE_HASH,
    ENGINE_ID,
    OPTIMIZED_ENGINE_ID,
    ChampionSubprocessEngine,
    EngineCancelled,
    EngineFailure,
    SolverEngine,
    extract_answers,
    optimized_engine_hash,
)
from geotarget.models import (
    PhaseMetadata,
    ResourceUsage,
    ResultStatus,
    SolveOptions,
    SolveResult,
    TerminationReason,
    V15Problem,
    WorkCheckpoint,
    WorkMetadata,
)
from geotarget.problem_cache import validate_cached
from geotarget.resources import ResourceError, reserve


def _problem_hash(problem: dict[str, Any]) -> str:
    payload = json.dumps(
        problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _engine_identity(options: SolveOptions) -> tuple[str, str]:
    if options.engine == "optimized":
        return OPTIMIZED_ENGINE_ID, optimized_engine_hash()
    return ENGINE_ID, ENGINE_HASH


def unexpected_engine_error_result(
    problem: V15Problem | dict[str, Any],
    options: SolveOptions,
    *,
    elapsed_seconds: float,
) -> SolveResult:
    """Return the stable public failure shape for an unexpected service fault.

    The traceback belongs in the caller's log.  Keeping exception text out of
    the result avoids exposing implementation details while still letting API
    clients terminate their job polling through the normal ``engine_error``
    contract.
    """

    native = problem.native_document() if isinstance(problem, V15Problem) else problem
    engine_id, engine_hash = _engine_identity(options)
    requested = ResourceUsage(
        time_limit_seconds=options.max_time_seconds,
        max_time_seconds=options.max_time_seconds,
        cores=options.cores,
        seed=options.seed,
    )
    return SolveResult(
        status=ResultStatus.ENGINE_ERROR,
        engine_id=engine_id,
        engine_hash=engine_hash,
        problem_sha256=_problem_hash(native),
        requested_resources=requested,
        used_resources=ResourceUsage(
            time_limit_seconds=0,
            max_time_seconds=0,
            cores=0,
            seed=options.seed,
        ),
        elapsed_seconds=max(0.0, elapsed_seconds),
        work_checkpoint=WorkCheckpoint(),
        detail="内部エラーが発生しました。再実行してください。",
        engine_variant=options.engine,
        termination_reason=TerminationReason.ENGINE_ERROR,
        phase_metadata=PhaseMetadata(current="engine"),
    )


def solve(
    problem: V15Problem | dict[str, Any],
    options: SolveOptions | dict[str, Any] | None = None,
    *,
    engine: SolverEngine | None = None,
) -> SolveResult:
    requested_payload = SolveOptions() if options is None else options
    try:
        parsed_options = (
            requested_payload
            if isinstance(requested_payload, SolveOptions)
            else SolveOptions.model_validate(requested_payload)
        )
    except ValidationError as error:
        fallback_requested = ResourceUsage(
            time_limit_seconds=900,
            max_time_seconds=900,
            cores="auto",
            seed=0,
        )
        fallback_used = ResourceUsage(
            time_limit_seconds=0,
            max_time_seconds=0,
            cores=0,
            seed=0,
        )
        return SolveResult(
            status=ResultStatus.RESOURCE_ERROR,
            engine_id=ENGINE_ID,
            engine_hash=ENGINE_HASH,
            problem_sha256="",
            requested_resources=fallback_requested,
            used_resources=fallback_used,
            elapsed_seconds=0,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
        )
    requested = ResourceUsage(
        time_limit_seconds=parsed_options.max_time_seconds,
        max_time_seconds=parsed_options.max_time_seconds,
        cores=parsed_options.cores,
        seed=parsed_options.seed,
    )
    selected_engine_id, selected_engine_hash = _engine_identity(parsed_options)
    compatibility_warnings = (
        ["time_limit_seconds is deprecated; use max_time_seconds with run_mode='fixed_time'"]
        if parsed_options.compatibility_time_limit_used
        else []
    )
    report, validation_cache_hit = validate_cached(
        problem.native_document() if isinstance(problem, V15Problem) else problem
    )
    cache_counts = {
        "hits": int(validation_cache_hit),
        "misses": int(not validation_cache_hit),
        "writes": int(not validation_cache_hit),
    }
    if not report.valid or report.normalized_problem is None:
        return SolveResult(
            status=ResultStatus.INVALID,
            engine_id=selected_engine_id,
            engine_hash=selected_engine_hash,
            problem_sha256="",
            requested_resources=requested,
            used_resources=ResourceUsage(
                time_limit_seconds=0,
                max_time_seconds=0,
                cores=0,
                seed=parsed_options.seed,
            ),
            elapsed_seconds=0,
            work_checkpoint=WorkCheckpoint(),
            detail="; ".join(f"{item.path}: {item.message}" for item in report.issues),
            engine_variant=parsed_options.engine,
            phase_metadata=PhaseMetadata(current="validation"),
            warnings=compatibility_warnings,
            cache_metadata=cache_counts,
        )
    native = report.normalized_problem
    digest = _problem_hash(native)
    started = time.monotonic()
    try:
        reservation = reserve(parsed_options)
    except ResourceError as error:
        return SolveResult(
            status=ResultStatus.RESOURCE_ERROR,
            engine_id=selected_engine_id,
            engine_hash=selected_engine_hash,
            problem_sha256=digest,
            requested_resources=requested,
            used_resources=ResourceUsage(
                time_limit_seconds=0,
                max_time_seconds=0,
                cores=0,
                seed=parsed_options.seed,
            ),
            elapsed_seconds=time.monotonic() - started,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
            engine_variant=parsed_options.engine,
            phase_metadata=PhaseMetadata(current="resource_selection"),
            warnings=compatibility_warnings,
            cache_metadata=cache_counts,
        )
    resolved_cores = len(reservation.physical_cpus)
    execution_options = parsed_options.model_copy(update={"cores": resolved_cores})
    used_before_execution = ResourceUsage(
        time_limit_seconds=0,
        max_time_seconds=0,
        cores=resolved_cores,
        seed=parsed_options.seed,
    )
    implementation = engine or ChampionSubprocessEngine()
    try:
        raw, elapsed, checkpoint, warnings = implementation.execute(
            native, execution_options, reservation
        )
    except EngineCancelled as error:
        return SolveResult(
            status=ResultStatus.CANCELLED,
            engine_id=selected_engine_id,
            engine_hash=selected_engine_hash,
            problem_sha256=digest,
            requested_resources=requested,
            used_resources=used_before_execution,
            elapsed_seconds=time.monotonic() - started,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
            engine_variant=parsed_options.engine,
            termination_reason=TerminationReason.CANCELLED,
            phase_metadata=PhaseMetadata(current="cancelled"),
            warnings=compatibility_warnings,
            cache_metadata=cache_counts,
        )
    except EngineFailure as error:
        return SolveResult(
            status=ResultStatus.ENGINE_ERROR,
            engine_id=selected_engine_id,
            engine_hash=selected_engine_hash,
            problem_sha256=digest,
            requested_resources=requested,
            used_resources=used_before_execution,
            elapsed_seconds=time.monotonic() - started,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
            engine_variant=parsed_options.engine,
            termination_reason=TerminationReason.ENGINE_ERROR,
            phase_metadata=PhaseMetadata(current="engine"),
            warnings=compatibility_warnings,
            cache_metadata=cache_counts,
        )
    warnings = [*compatibility_warnings, *warnings]
    answers = extract_answers(raw)
    raw_status = str(raw.get("status", ""))
    if answers and raw_status in {
        "EXACT_SYMBOLIC_TARGET_READY",
        "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE",
    }:
        status = ResultStatus.EXACT_COMPLETE
    elif answers:
        status = ResultStatus.ANSWERS_FOUND
        warnings.append("発見済みの厳密値。全targetの完全性は未証明")
    else:
        status = ResultStatus.NO_ANSWER
        warnings.append("No accepted answer was found; this is not a proof that no solution exists")
    used = ResourceUsage(
        time_limit_seconds=min(parsed_options.max_time_seconds, elapsed),
        max_time_seconds=min(parsed_options.max_time_seconds, elapsed),
        cores=resolved_cores,
        seed=parsed_options.seed,
    )
    pending_items = sum(
        len(items)
        for items in (
            checkpoint.pending_start_ordinals,
            checkpoint.pending_reservoir_records,
            checkpoint.pending_hp_alternates,
            checkpoint.pending_restoration,
        )
    )
    termination_reason = checkpoint.termination_reason or (
        TerminationReason.EXACT_COMPLETE
        if status == ResultStatus.EXACT_COMPLETE
        else TerminationReason.SAFETY_CAP
    )
    product_metadata = raw.get("geotarget_product")
    runtime_cache: dict[str, Any] = {}
    if isinstance(product_metadata, dict):
        selected_engine_id = str(product_metadata.get("engine_id") or selected_engine_id)
        selected_engine_hash = str(product_metadata.get("engine_hash") or selected_engine_hash)
        raw_runtime_cache = product_metadata.get("runtime_cache")
        if isinstance(raw_runtime_cache, dict):
            runtime_cache = raw_runtime_cache
        if (
            parsed_options.engine == "optimized"
            and product_metadata.get("evaluator_mode") == "reference_full_problem_fallback"
            and product_metadata.get("typed_kernel_enabled") is False
        ):
            warnings.append(
                "The typed numeric kernel is disabled because bitwise equivalence was not "
                "established; this problem used the frozen reference evaluator throughout"
            )
    return SolveResult(
        status=status,
        engine_id=selected_engine_id,
        engine_hash=selected_engine_hash,
        problem_sha256=digest,
        requested_resources=requested,
        used_resources=used,
        elapsed_seconds=elapsed,
        work_checkpoint=checkpoint,
        warnings=warnings,
        answers=answers,
        engine_variant=parsed_options.engine,
        termination_reason=termination_reason,
        phase_metadata=PhaseMetadata(
            current="completed",
            completed=list(checkpoint.phase_elapsed_seconds),
            elapsed_seconds=checkpoint.phase_elapsed_seconds,
        ),
        work_metadata=WorkMetadata(
            completed_items=len(checkpoint.completed_start_ordinals),
            pending_items=pending_items,
            total_items=len(checkpoint.completed_start_ordinals) + pending_items,
        ),
        cache_metadata={
            **cache_counts,
            "runtime_generation": int(runtime_cache.get("solve_generation", 0)),
            "runtime_warm": bool(runtime_cache.get("hp_preloader_warm")),
            "hp_preloader_warm": bool(runtime_cache.get("hp_preloader_warm")),
        },
    )
