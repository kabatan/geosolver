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

import psutil
from pydantic import ValidationError

from geosolver.platform.processes import (
    default_memory_limit_bytes,
    process_tree_memory_bytes,
    set_affinity,
    spawn_process,
    terminate_process_tree,
)
from geosolver.runtime.artifact_commit import read_receipt
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
        deadline_monotonic: float | None = None,
    ) -> EngineExecution:
        self._cancel_event.clear()
        deadline = (
            time.monotonic() + float(time_limit_seconds)
            if deadline_monotonic is None
            else deadline_monotonic
        )
        request = WorkerRequest(
            engine_document=engine_document,
            seed=seed,
            deadline_monotonic=deadline,
            effective_cores=cores,
            config_snapshot={
                "time_limit_seconds": float(time_limit_seconds),
                "cores": int(cores),
                "seed": int(seed),
            },
        )
        with tempfile.TemporaryDirectory(prefix="geosolver-") as temporary_directory:
            working_directory = Path(temporary_directory)
            input_path = working_directory / "request.json"
            output_path = working_directory / "artifact.json"
            stdout_path = working_directory / "stdout.log"
            stderr_path = working_directory / "stderr.log"
            input_path.write_text(
                request.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            environment = os.environ.copy()
            environment["GEOSOLVER_MEMORY_LIMIT_BYTES"] = str(self._memory_limit_bytes)
            thread_variables = (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
            for variable in thread_variables:
                environment[variable] = "1"
            command = [
                sys.executable,
                "-m",
                self._worker_module,
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ]
            stdout_stream = stdout_path.open("w", encoding="utf-8", newline="\n")
            stderr_stream = stderr_path.open("w", encoding="utf-8", newline="\n")
            try:
                process = spawn_process(
                    command,
                    cwd=working_directory,
                    env=environment,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                )
            except BaseException:
                stdout_stream.close()
                stderr_stream.close()
                raise
            set_affinity(process.pid, cores)
            with self._lock:
                self._process = process
            peak_rss = 0
            cpu_by_process = {}
            stopped_after_commit = False
            try:
                while process.poll() is None:
                    if self._cancel_event.is_set():
                        terminate_process_tree(process)
                        raise EngineCancelled
                    if time.monotonic() >= deadline:
                        receipt = read_receipt(output_path)
                        terminate_process_tree(process)
                        if receipt is None or not receipt.matches(request.request_id, deadline):
                            raise EngineTimedOut
                        # Saving finished on time; only worker cleanup remained.
                        stopped_after_commit = True
                        break
                    memory = process_tree_memory_bytes(process.pid)
                    peak_rss = max(peak_rss, memory)
                    try:
                        root = psutil.Process(process.pid)
                        for child in [root, *root.children(recursive=True)]:
                            with child.oneshot():
                                usage = child.cpu_times()
                                cpu_by_process[(child.pid, child.create_time())] = (
                                    usage.user + usage.system
                                )
                    except psutil.Error:
                        pass
                    if memory > self._memory_limit_bytes:
                        terminate_process_tree(process)
                        raise EngineResourceExhausted(
                            "memory_limit_exceeded",
                            "solve exceeded the worker memory limit",
                        )
                    self._cancel_event.wait(0.05)
                communicated_stdout, communicated_stderr = process.communicate()
            finally:
                if getattr(process, "_geosolver_owned_group", False):
                    terminate_process_tree(process, grace_seconds=0.1)
                stdout_stream.close()
                stderr_stream.close()
                with self._lock:
                    self._process = None

            stdout = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""
            stderr = stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else ""
            stdout = stdout or communicated_stdout or ""
            stderr = stderr or communicated_stderr or ""

            if self._cancel_event.is_set():
                raise EngineCancelled
            if not output_path.is_file():
                raise EngineFailure(
                    "artifact_missing",
                    f"worker exited with code {process.returncode} without an artifact",
                )
            try:
                payload = output_path.read_bytes()
                artifact = WorkerArtifact.model_validate_json(payload)
            except (OSError, ValidationError, ValueError, json.JSONDecodeError) as error:
                raise EngineFailure(
                    "artifact_invalid", f"invalid worker artifact: {error}"
                ) from error
            if (
                process.returncode != 0 and not stopped_after_commit
            ) or artifact.status != "completed":
                error = artifact.error
                code = error.code if error is not None else "worker_failed"
                message = error.message if error is not None else "worker did not complete"
                if code == "time_limit_reached":
                    raise EngineTimedOut
                raise EngineFailure(code, message)
            receipt = read_receipt(output_path)
            if (
                artifact.protocol_version != 4
                or artifact.request_id != request.request_id
                or receipt is None
                or receipt.request_id != request.request_id
                or not receipt.verify_bytes(payload)
            ):
                raise EngineFailure("artifact_invalid", "missing or inconsistent save receipt")
            if not receipt.matches(request.request_id, deadline):
                raise EngineTimedOut
            artifact = artifact.model_copy(
                update={
                    "stdout": stdout,
                    "stderr": stderr,
                    "process_info": {
                        **artifact.process_info,
                        "pid": int(process.pid),
                        "returncode": int(process.returncode),
                        "effective_cores": int(cores),
                        "peak_rss_bytes": peak_rss,
                        "cpu_seconds": max(
                            sum(cpu_by_process.values()),
                            artifact.process_info.get("cpu_seconds", 0),
                        ),
                        "resource_sampling_interval_seconds": 0.05,
                        "artifact_commit": receipt.model_dump(),
                    },
                }
            )
            return EngineExecution(artifact=artifact, stdout=stdout, stderr=stderr)
