from __future__ import annotations

import json
import logging
import time
from typing import Any

from geosolver.engine import (
    EngineCancelled,
    EngineFailure,
    EngineResourceExhausted,
    EngineRunner,
    EngineTimedOut,
)
from geosolver.problem.models import (
    Completeness,
    EngineIdentity,
    GeometryProblem,
    ResourceUsage,
    ResultStatus,
    SolveError,
    SolveOptions,
    SolveResult,
    TerminationReason,
)
from geosolver.problem.validation import validate
from geosolver.runtime.integrity import engine_identity_hashes

LOGGER = logging.getLogger(__name__)


def canonical_problem_json(problem: GeometryProblem) -> str:
    return json.dumps(
        problem.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def problem_hash(problem: GeometryProblem) -> str:
    import hashlib

    return hashlib.sha256(canonical_problem_json(problem).encode("utf-8")).hexdigest()


def _resources(options: SolveOptions, cores: int) -> ResourceUsage:
    return ResourceUsage(
        time_limit_seconds=options.resolved_time_limit,
        cores=cores,
        seed=options.seed,
    )


def _base_result(
    *,
    status: ResultStatus,
    problem: GeometryProblem,
    options: SolveOptions,
    cores: int,
    elapsed: float,
    termination: TerminationReason,
    error: SolveError | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> SolveResult:
    return SolveResult(
        status=status,
        completeness=Completeness.UNKNOWN,
        engine=EngineIdentity(**engine_identity_hashes()),
        problem_hash=problem_hash(problem),
        requested_resources=_resources(options, options.resolved_cores),
        used_resources=_resources(options, cores),
        elapsed_seconds=elapsed,
        termination_reason=termination,
        error=error,
        diagnostics=diagnostics,
    )


def solve(
    problem: GeometryProblem | dict[str, Any],
    options: SolveOptions | dict[str, Any] | None = None,
    *,
    runner: EngineRunner | None = None,
) -> SolveResult:
    started = time.monotonic()
    parsed_options = (
        options if isinstance(options, SolveOptions) else SolveOptions.model_validate(options or {})
    )
    if isinstance(problem, GeometryProblem):
        parsed_problem = problem
    else:
        try:
            parsed_problem = GeometryProblem.model_validate(problem)
        except Exception:
            placeholder = GeometryProblem(
                id="invalid", variables=[], constructions=[], conditions=[], target="0"
            )
            return _base_result(
                status=ResultStatus.INVALID,
                problem=placeholder,
                options=parsed_options,
                cores=1,
                elapsed=0.0,
                termination=TerminationReason.ENGINE_FAILED,
                error=SolveError(code="invalid_problem", message="problem schema is invalid"),
            )
    report = validate(parsed_problem)
    if not report.valid:
        return _base_result(
            status=ResultStatus.INVALID,
            problem=parsed_problem,
            options=parsed_options,
            cores=1,
            elapsed=0.0,
            termination=TerminationReason.ENGINE_FAILED,
            error=SolveError(
                code="invalid_problem",
                message="; ".join(f"{issue.path}: {issue.message}" for issue in report.issues),
            ),
        )
    cores = 1  # The current solver executes one numerical stream per worker.
    active_runner = runner or EngineRunner()
    try:
        execution = active_runner.run(
            parsed_problem.engine_document(),
            seed=parsed_options.seed,
            cores=cores,
            time_limit_seconds=parsed_options.resolved_time_limit,
            deadline_monotonic=started + parsed_options.resolved_time_limit,
        )
    except EngineCancelled as error:
        return _base_result(
            status=ResultStatus.CANCELLED,
            problem=parsed_problem,
            options=parsed_options,
            cores=cores,
            elapsed=time.monotonic() - started,
            termination=TerminationReason.CANCELLED,
            error=SolveError(code=error.code, message=str(error)),
        )
    except EngineTimedOut as error:
        return _base_result(
            status=ResultStatus.RESOURCE_ERROR,
            problem=parsed_problem,
            options=parsed_options,
            cores=cores,
            elapsed=time.monotonic() - started,
            termination=TerminationReason.TIME_LIMIT,
            error=SolveError(code=error.code, message=str(error)),
        )
    except EngineResourceExhausted as error:
        return _base_result(
            status=ResultStatus.RESOURCE_ERROR,
            problem=parsed_problem,
            options=parsed_options,
            cores=cores,
            elapsed=time.monotonic() - started,
            termination=TerminationReason.ENGINE_FAILED,
            error=SolveError(code=error.code, message=str(error)),
        )
    except EngineFailure as error:
        return _base_result(
            status=ResultStatus.ENGINE_ERROR,
            problem=parsed_problem,
            options=parsed_options,
            cores=cores,
            elapsed=time.monotonic() - started,
            termination=(
                TerminationReason.NO_PROGRESS
                if error.code == "no_progress"
                else TerminationReason.ENGINE_FAILED
            ),
            error=SolveError(code=error.code, message=str(error)),
        )
    except Exception:
        LOGGER.exception("unexpected engine execution failure")
        return _base_result(
            status=ResultStatus.ENGINE_ERROR,
            problem=parsed_problem,
            options=parsed_options,
            cores=cores,
            elapsed=time.monotonic() - started,
            termination=TerminationReason.ENGINE_FAILED,
            error=SolveError(
                code="unexpected_engine_error",
                message="the engine stopped unexpectedly; see the local log",
            ),
        )
    try:
        answers, warnings = execution.artifact.answers, execution.artifact.warnings
    except Exception:
        LOGGER.exception("exact answer assembly failed")
        return _base_result(
            status=ResultStatus.ENGINE_ERROR,
            problem=parsed_problem,
            options=parsed_options,
            cores=cores,
            elapsed=time.monotonic() - started,
            termination=TerminationReason.ENGINE_FAILED,
            error=SolveError(
                code="exact_assembly_failed",
                message="exact answer assembly failed; see the local log",
            ),
        )
    elapsed = time.monotonic() - started
    # EngineRunner validates the completed save time, not subsequent read/cleanup time.
    base = _base_result(
        status=ResultStatus.SOLVED if answers else ResultStatus.NO_ANSWER,
        problem=parsed_problem,
        options=parsed_options,
        cores=cores,
        elapsed=elapsed,
        termination=(
            TerminationReason.TIME_LIMIT
            if execution.artifact.termination_reason == "time_limit_reached"
            else (TerminationReason.ANSWER_FOUND if answers else TerminationReason.NO_ANSWER_FOUND)
        ),
        diagnostics={
            **execution.artifact.diagnostics,
            "phase_timings": execution.artifact.phase_timings,
            "counters": execution.artifact.counters,
            "candidate_records": execution.artifact.candidate_records,
            "rejection_tags": execution.artifact.rejection_tags,
            "process_info": execution.artifact.process_info,
            "config_snapshot": execution.artifact.config_snapshot,
            "stdout": execution.artifact.stdout,
            "stderr": execution.artifact.stderr,
            "numeric_feasible": execution.artifact.numeric_feasible,
            "exact_identified": execution.artifact.exact_identified,
            "public_solved": bool(answers),
        },
    )
    base.answers = answers
    base.warnings = warnings
    base.completeness = Completeness.UNKNOWN
    return base
