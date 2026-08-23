from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from geosolver.platform.processes import (
    default_memory_limit_bytes,
    process_tree_memory_bytes,
    set_affinity,
    spawn_process,
    terminate_process_tree,
)
from geosolver.runtime.protocol import WorkerArtifact, WorkerRequest


class EngineFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EngineCancelled(EngineFailure):
    def __init__(self) -> None:
        super().__init__("cancelled", "solve was cancelled")


class EngineTimedOut(EngineFailure):
    def __init__(self) -> None:
        super().__init__("time_limit_reached", "solve exceeded its time limit")


class EngineResourceExhausted(EngineFailure):
    pass


@dataclass(frozen=True)
class EngineExecution:
    artifact: WorkerArtifact
    stdout: str
    stderr: str


class EngineRunner:
    """Owns exactly one worker process; cancellation never touches another session."""

    def __init__(
        self,
        *,
        worker_module: str = "geosolver.runtime.worker",
        memory_limit_bytes: int | None = None,
    ) -> None:
        self._worker_module = worker_module
        self._memory_limit_bytes = memory_limit_bytes or default_memory_limit_bytes()
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def cancel(self) -> None:
        self._cancel_event.set()
        with self._lock:
            process = self._process
        if process is not None:
            terminate_process_tree(process)

    def run(
        self,
        engine_document: dict[str, object],
        *,
        seed: int,
        cores: int,
        time_limit_seconds: float,
        prefer_fast: bool,
    ) -> EngineExecution:
        self._cancel_event.clear()
        request = WorkerRequest(
            engine_document=engine_document,
            seed=seed,
            prefer_fast=prefer_fast,
        )
        with tempfile.TemporaryDirectory(prefix="geosolver-") as temporary_directory:
            working_directory = Path(temporary_directory)
            input_path = working_directory / "request.json"
            output_path = working_directory / "artifact.json"
            input_path.write_text(
                request.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            environment = os.environ.copy()
            environment["GEOSOLVER_NUM_WORKERS"] = str(cores)
            environment["GEOSOLVER_MEMORY_LIMIT_BYTES"] = str(self._memory_limit_bytes)
            command = [
                sys.executable,
                "-m",
                self._worker_module,
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ]
            process = spawn_process(command, cwd=working_directory, env=environment)
            set_affinity(process.pid, cores)
            with self._lock:
                self._process = process
            deadline = time.monotonic() + time_limit_seconds
            try:
                while process.poll() is None:
                    if self._cancel_event.is_set():
                        terminate_process_tree(process)
                        raise EngineCancelled
                    if time.monotonic() >= deadline:
                        terminate_process_tree(process)
                        raise EngineTimedOut
                    if process_tree_memory_bytes(process.pid) > self._memory_limit_bytes:
                        terminate_process_tree(process)
                        raise EngineResourceExhausted(
                            "memory_limit_exceeded",
                            "solve exceeded the worker memory limit",
                        )
                    self._cancel_event.wait(0.05)
                stdout, stderr = process.communicate()
            finally:
                with self._lock:
                    self._process = None

            if self._cancel_event.is_set():
                raise EngineCancelled
            if not output_path.is_file():
                raise EngineFailure(
                    "artifact_missing",
                    f"worker exited with code {process.returncode} without an artifact",
                )
            try:
                artifact = WorkerArtifact.model_validate_json(
                    output_path.read_text(encoding="utf-8")
                )
            except (OSError, ValidationError, ValueError, json.JSONDecodeError) as error:
                raise EngineFailure(
                    "artifact_invalid", f"invalid worker artifact: {error}"
                ) from error
            if process.returncode != 0 or artifact.status != "completed":
                error = artifact.error
                code = error.code if error is not None else "worker_failed"
                message = error.message if error is not None else "worker did not complete"
                raise EngineFailure(code, message)
            return EngineExecution(artifact=artifact, stdout=stdout, stderr=stderr)
