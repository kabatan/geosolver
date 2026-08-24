from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from mpmath import mp

from geosolver.engine.standard.interpreter.public import run_ir
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


def execute(request: WorkerRequest) -> WorkerArtifact:
    started = time.monotonic()
    original_dps = mp.dps
    try:
        with mp.workdps(max(120, original_dps)):
            result = run_ir(
                request.engine_document,
                prefer_fast=request.prefer_fast,
                seed=request.seed,
            )
        metadata = result.metadata if isinstance(result.metadata, dict) else {}
        exact_candidates = _string_candidates(metadata.get("exact_answer_candidates"))
        if result.exact_answer is not None:
            exact_text = str(result.exact_answer)
            if exact_text not in exact_candidates:
                exact_candidates.append(exact_text)
        diagnostics: dict[str, Any] = {
            "exact_answer_attempt_count": int(metadata.get("exact_answer_attempt_count", 0)),
            "exact_answer_identified_count": int(metadata.get("exact_answer_identified_count", 0)),
            "pipeline_backend": str(metadata.get("pipeline_backend", "unknown")),
        }
        return WorkerArtifact(
            status="completed",
            solver_status=result.status.name.lower(),
            exact_candidates=exact_candidates,
            numeric_candidates=_string_candidates(result.answer_values),
            elapsed_seconds=time.monotonic() - started,
            diagnostics=diagnostics,
        )
    except BaseException as error:
        LOGGER.exception("GeoSolver worker failed")
        return WorkerArtifact(
            status="failed",
            elapsed_seconds=time.monotonic() - started,
            error=WorkerError(code="worker_exception", message=str(error) or type(error).__name__),
            diagnostics={"error_type": type(error).__name__},
        )
    finally:
        mp.dps = original_dps


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
    artifact = execute(request)
    _atomic_write(arguments.output, artifact)
    return 0 if artifact.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
