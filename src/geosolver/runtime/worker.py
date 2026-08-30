from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from mpmath import mp

from geosolver.engine.standard.contracts.external_pipeline_config import (
    ExternalPipelineConfig,
)
from geosolver.engine.standard.orchestration.run_external_pipeline import run_external_pipeline
from geosolver.runtime.deadline import counters_snapshot, expired, runtime_session
from geosolver.runtime.integrity import engine_identity_hashes, installed_dependencies
from geosolver.runtime.protocol import WorkerArtifact, WorkerError, WorkerRequest

LOGGER = logging.getLogger(__name__)


def _apply_linux_memory_limit() -> None:
    if sys.platform != "linux":
        return
    configured = os.environ.get("GEOSOLVER_MEMORY_LIMIT_BYTES")
    if configured is None:
        return
    try:
        import resource

        limit = int(configured)
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, OSError, ValueError):
        LOGGER.warning("could not apply the optional Linux address-space limit")


def _atomic_write(path: Path, artifact: WorkerArtifact) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(artifact.model_dump(mode="json"), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def _string_candidates(values: Any) -> list[str]:
    if not isinstance(values, list | tuple):
        return []
    return [str(value) for value in values if value is not None]


def _json_value(value):
    if hasattr(value, "_mpf_"):
        # Candidate evidence may have been produced at 500 dps even though the
        # artifact is written outside that context. Preserve its working value.
        digits = max(550, value._mpf_[3] * 30103 // 100000 + 10)
        return mp.nstr(value, n=digits)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float) and mp.isfinite(value):
        return value
    return str(value)


def execute(request: WorkerRequest) -> WorkerArtifact:
    started = time.monotonic()
    try:
        solver_deadline = float(request.deadline_monotonic) - 2.0
        remaining = solver_deadline - time.monotonic()
        if remaining <= 0:
            return WorkerArtifact(
                status="completed",
                solver_status="no_answer_found",
                termination_reason="time_limit_reached",
                elapsed_seconds=time.monotonic() - started,
                rejection_tags=["startup_deadline_reached"],
                config_snapshot=dict(request.config_snapshot),
            )
        pipeline_config = ExternalPipelineConfig.production_baseline_tier(
            seed=int(request.seed),
            total_time_budget_sec=remaining,
        )
        with mp.workdps(max(180, mp.dps)), runtime_session(solver_deadline) as timings:
            result = run_external_pipeline(
                request.engine_document,
                seed=request.seed,
                pipeline_config=pipeline_config,
                deadline_monotonic=solver_deadline,
            )
            exact_candidates = [
                entry.selected_exact_value
                for entry in result.exact_results
                if entry.selected_exact_value is not None and entry.descriptor is not None
            ]
            assembly_started = time.monotonic()
            answers, warnings, seen = [], [], set()
            for entry in result.exact_results:
                answer = entry.descriptor
                if answer is not None and answer.canonical_key() not in seen:
                    seen.add(answer.canonical_key())
                    answers.append(answer)
            timings["descriptors"] = time.monotonic() - assembly_started
            metadata = _json_value(result.summary)
            candidate_records = [_json_value(candidate) for candidate in result.refined_candidates]
            for record in candidate_records:
                record["accepted"] = record["candidate_id"] in result.accepted_candidate_ids
            for candidate, record in zip(result.refined_candidates, candidate_records, strict=True):
                record["candidate_uid"] = candidate.candidate_uid
            metadata["exact_answer_attempt_count"] = len(result.exact_results)
            metadata["exact_answer_identified_count"] = len(exact_candidates)
            evaluation_counts = counters_snapshot()
            time_limited = expired() or any(
                "deadline" in str(tag)
                for tag in metadata.get("exact_assembly", {}).get("rejection_tags", [])
            )
        diagnostics: dict[str, Any] = {
            "exact_answer_attempt_count": int(metadata.get("exact_answer_attempt_count", 0)),
            "exact_answer_identified_count": int(metadata.get("exact_answer_identified_count", 0)),
            "pipeline_backend": str(metadata.get("pipeline_backend", "unknown")),
        }
        phase_timings = {
            key: float(value.get("elapsed_sec", 0.0))
            for key, value in metadata.items()
            if isinstance(value, dict) and "elapsed_sec" in value
        }
        phase_timings.update(timings)
        for phase in (
            "initial_probe",
            "search",
            "refinement",
            "rescue",
            "discrete_completion",
            "exact_assembly",
            "descriptors",
        ):
            phase_timings.setdefault(phase, 0.0)
        search = metadata.get("search")
        counters = {
            **evaluation_counts,
            "evaluation_count": int(search.get("evaluation_count", 0))
            if isinstance(search, dict)
            else 0,
            "exact_answer_attempt_count": diagnostics["exact_answer_attempt_count"],
            "exact_answer_identified_count": diagnostics["exact_answer_identified_count"],
        }
        exact_assembly = metadata.get("exact_assembly")
        numeric_feasible = bool(
            isinstance(exact_assembly, dict)
            and int(exact_assembly.get("numeric_feasible_count", 0)) > 0
        )
        rejection_tags = (
            [str(value) for value in exact_assembly.get("rejection_tags", [])]
            if isinstance(exact_assembly, dict)
            else []
        )
        return WorkerArtifact(
            status="completed",
            solver_status=result.status,
            termination_reason="time_limit_reached"
            if time_limited
            else ("answer_found" if answers else "no_answer_found"),
            execution_identity=engine_identity_hashes(),
            numeric_feasible=numeric_feasible,
            exact_identified=bool(exact_candidates),
            public_solved=bool(answers),
            exact_candidates=exact_candidates,
            answers=answers,
            warnings=warnings,
            numeric_candidates=_string_candidates(result.accepted_answers),
            elapsed_seconds=time.monotonic() - started,
            diagnostics={**diagnostics, "pipeline_summary": metadata},
            phase_timings=phase_timings,
            counters=counters,
            candidate_records=(
                list(candidate_records) if isinstance(candidate_records, list) else []
            ),
            rejection_tags=rejection_tags,
            process_info={
                "pid": os.getpid(),
                "effective_cores": int(request.effective_cores),
                "deadline_monotonic": float(request.deadline_monotonic),
                "installed_dependencies": installed_dependencies(),
                "import_root": str(Path(__file__).resolve().parents[1]),
                "cpu_affinity": _actual_affinity(),
                "cpu_seconds": time.process_time(),
            },
            config_snapshot={**request.config_snapshot, "pipeline": _json_value(pipeline_config)},
        )
    except TimeoutError:
        return WorkerArtifact(
            status="completed",
            solver_status="no_answer_found",
            termination_reason="time_limit_reached",
            execution_identity=engine_identity_hashes(),
            elapsed_seconds=time.monotonic() - started,
            rejection_tags=["deadline_before_completed_answer"],
            process_info={
                "import_root": str(Path(__file__).resolve().parents[1]),
                "cpu_affinity": _actual_affinity(),
                "installed_dependencies": installed_dependencies(),
                "cpu_seconds": time.process_time(),
            },
            config_snapshot=dict(request.config_snapshot),
        )
    except BaseException as error:
        LOGGER.exception("GeoSolver worker failed")
        return WorkerArtifact(
            status="failed",
            elapsed_seconds=time.monotonic() - started,
            error=WorkerError(
                code="time_limit_reached"
                if isinstance(error, TimeoutError)
                else "worker_exception",
                message=str(error) or type(error).__name__,
            ),
            diagnostics={"error_type": type(error).__name__},
            config_snapshot=dict(getattr(request, "config_snapshot", {})),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GeoSolver internal worker")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    _apply_linux_memory_limit()
    try:
        request = WorkerRequest.model_validate_json(arguments.input.read_text(encoding="utf-8"))
    except Exception as error:
        artifact = WorkerArtifact(
            status="failed",
            error=WorkerError(code="invalid_worker_request", message=str(error)),
        )
        _atomic_write(arguments.output, artifact)
        return 2
    from geosolver.platform.processes import set_affinity

    set_affinity(os.getpid(), int(request.effective_cores))
    artifact = execute(request)
    _atomic_write(arguments.output, artifact)
    return 0 if artifact.status == "completed" else 1


def _actual_affinity():
    import psutil

    process = psutil.Process()
    return process.cpu_affinity() if hasattr(process, "cpu_affinity") else None


if __name__ == "__main__":
    raise SystemExit(main())
