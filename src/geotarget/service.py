from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import ValidationError

from geotarget.engine import (
    ENGINE_HASH,
    ENGINE_ID,
    ChampionSubprocessEngine,
    EngineCancelled,
    EngineFailure,
    SolverEngine,
    extract_answers,
)
from geotarget.models import (
    ResourceUsage,
    ResultStatus,
    SolveOptions,
    SolveResult,
    V15Problem,
    WorkCheckpoint,
)
from geotarget.resources import ResourceError, reserve
from geotarget.validation import validate


def _problem_hash(problem: dict[str, Any]) -> str:
    payload = json.dumps(
        problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def solve(
    problem: V15Problem | dict[str, Any],
    options: SolveOptions | dict[str, Any] | None = None,
    *,
    engine: SolverEngine | None = None,
) -> SolveResult:
    requested_payload = options or SolveOptions()
    try:
        parsed_options = (
            requested_payload
            if isinstance(requested_payload, SolveOptions)
            else SolveOptions.model_validate(requested_payload)
        )
    except ValidationError as error:
        fallback = ResourceUsage(time_limit_seconds=180, cores=1, seed=0)
        return SolveResult(
            status=ResultStatus.RESOURCE_ERROR,
            engine_id=ENGINE_ID,
            engine_hash=ENGINE_HASH,
            problem_sha256="",
            requested_resources=fallback,
            used_resources=fallback,
            elapsed_seconds=0,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
        )
    requested = ResourceUsage(**parsed_options.model_dump())
    report = validate(problem)
    if not report.valid or report.normalized_problem is None:
        return SolveResult(
            status=ResultStatus.INVALID,
            engine_id=ENGINE_ID,
            engine_hash=ENGINE_HASH,
            problem_sha256="",
            requested_resources=requested,
            used_resources=requested,
            elapsed_seconds=0,
            work_checkpoint=WorkCheckpoint(),
            detail="; ".join(f"{item.path}: {item.message}" for item in report.issues),
        )
    native = report.normalized_problem
    digest = _problem_hash(native)
    started = time.monotonic()
    try:
        reservation = reserve(parsed_options)
    except ResourceError as error:
        return SolveResult(
            status=ResultStatus.RESOURCE_ERROR,
            engine_id=ENGINE_ID,
            engine_hash=ENGINE_HASH,
            problem_sha256=digest,
            requested_resources=requested,
            used_resources=requested,
            elapsed_seconds=time.monotonic() - started,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
        )
    implementation = engine or ChampionSubprocessEngine()
    try:
        raw, elapsed, checkpoint, warnings = implementation.execute(
            native, parsed_options, reservation
        )
    except EngineCancelled as error:
        return SolveResult(
            status=ResultStatus.CANCELLED,
            engine_id=ENGINE_ID,
            engine_hash=ENGINE_HASH,
            problem_sha256=digest,
            requested_resources=requested,
            used_resources=requested,
            elapsed_seconds=time.monotonic() - started,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
        )
    except EngineFailure as error:
        return SolveResult(
            status=ResultStatus.ENGINE_ERROR,
            engine_id=ENGINE_ID,
            engine_hash=ENGINE_HASH,
            problem_sha256=digest,
            requested_resources=requested,
            used_resources=requested,
            elapsed_seconds=time.monotonic() - started,
            work_checkpoint=WorkCheckpoint(),
            detail=str(error),
        )
    answers = extract_answers(raw)
    raw_status = str(raw.get("status", ""))
    if answers and raw_status == "EXACT_SYMBOLIC_TARGET_READY":
        status = ResultStatus.EXACT_COMPLETE
    elif answers:
        status = ResultStatus.ANSWERS_FOUND
        warnings.append("発見済みの厳密値。全targetの完全性は未証明")
    else:
        status = ResultStatus.NO_ANSWER
        warnings.append("No accepted answer was found; this is not a proof that no solution exists")
    used = ResourceUsage(
        time_limit_seconds=min(180.0, parsed_options.time_limit_seconds),
        cores=1,
        seed=parsed_options.seed,
    )
    return SolveResult(
        status=status,
        engine_id=ENGINE_ID,
        engine_hash=ENGINE_HASH,
        problem_sha256=digest,
        requested_resources=requested,
        used_resources=used,
        elapsed_seconds=elapsed,
        work_checkpoint=checkpoint,
        warnings=warnings,
        answers=answers,
    )
