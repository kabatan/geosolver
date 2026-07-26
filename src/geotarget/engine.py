from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from geotarget.models import ExactAnswer, SolveOptions, WorkCheckpoint
from geotarget.resources import ResourceReservation

ENGINE_ID = "champion-v2-poc-preloaded-20260722"
ENGINE_HASH = "9fa23aecdb9372dfd961b46224b88937c3317eaeb56796a05142563f26078f15"


class EngineFailure(RuntimeError):
    pass


class EngineCancelled(EngineFailure):
    pass


class SolverEngine(Protocol):
    def execute(
        self,
        problem: Mapping[str, Any],
        options: SolveOptions,
        reservation: ResourceReservation,
    ) -> tuple[dict[str, Any], float, WorkCheckpoint, list[str]]: ...

    def cancel(self) -> None: ...


def engine_root() -> Path:
    return Path(__file__).resolve().parent / "_engine"


def verify_engine() -> list[str]:
    root = Path(__file__).resolve().parents[2]
    manifest_path = engine_root() / "product-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("engine_id") != ENGINE_ID or manifest.get("closure_sha256") != ENGINE_HASH:
        errors.append("product manifest identity does not match the compiled authority")
    for item in manifest.get("files", []):
        path = root / item["product_path"]
        if not path.is_file():
            errors.append(f"missing engine file: {item['product_path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["source_sha256"]:
            errors.append(f"engine hash mismatch: {item['product_path']}")
    return errors


def _walk(value: Any):
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def extract_answers(raw: Mapping[str, Any]) -> list[ExactAnswer]:
    answers: list[ExactAnswer] = []
    seen: set[tuple[str, int]] = set()
    witness = next(
        (
            dict(node)
            for node in _walk(raw)
            if isinstance(node, Mapping)
            and any(key in node for key in ("selected_endpoint", "endpoint_coordinates", "witness"))
        ),
        None,
    )
    for node in _walk(raw):
        if not isinstance(node, Mapping) or "minimal_polynomial_high_to_low" not in node:
            continue
        polynomial = list(node.get("minimal_polynomial_high_to_low") or [])
        root_index = int(node.get("selected_real_root_index", 0))
        key = (json.dumps(polynomial, separators=(",", ":")), root_index)
        if key in seen:
            continue
        seen.add(key)
        interval_value = node.get("isolating_interval") or []
        interval = (
            [str(part) for part in interval_value] if isinstance(interval_value, list) else []
        )
        decimal = str(
            node.get("target_1024")
            or node.get("target_768")
            or node.get("target_512")
            or node.get("decimal")
            or ""
        )
        answers.append(
            ExactAnswer(
                minimal_polynomial_high_to_low=polynomial,
                selected_real_root_index=root_index,
                isolating_interval=interval,
                decimal=decimal,
                exact_authority_kind=str(node.get("exact_authority_kind"))
                if node.get("exact_authority_kind")
                else None,
                approximate_witness=witness,
            )
        )
    return answers


class ChampionSubprocessEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = threading.Event()

    def cancel(self) -> None:
        self._cancel_requested.set()
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)

    def _invoke(
        self, command: list[str], environment: dict[str, str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(
            command,
            cwd=engine_root() / "runtime/solver",
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        with self._lock:
            self._process = process
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            raise EngineFailure("frozen engine exceeded its protected wall-time reserve") from error
        finally:
            with self._lock:
                self._process = None
        # `taskset` and the frozen worker do not preserve SIGTERM as -15 in every
        # exit path. The caller's cancellation intent is the reliable authority.
        if self._cancel_requested.is_set():
            raise EngineCancelled("solve was cancelled")
        if process.returncode:
            tail = stderr[-4000:] if stderr else stdout[-4000:]
            raise EngineFailure(f"frozen engine exited with code {process.returncode}: {tail}")
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def execute(
        self,
        problem: Mapping[str, Any],
        options: SolveOptions,
        reservation: ResourceReservation,
    ) -> tuple[dict[str, Any], float, WorkCheckpoint, list[str]]:
        self._cancel_requested.clear()
        errors = verify_engine()
        if errors:
            raise EngineFailure("; ".join(errors))
        started = time.monotonic()
        warnings: list[str] = []
        if options.time_limit_seconds > 180:
            warnings.append(
                "the frozen 2026-07-22 worker exposed no resumable pending-item checkpoint; "
                "the reference window completed without inventing additional work"
            )
        runtime = engine_root() / "runtime"
        worker = (
            runtime
            / "solver/research/experiments/EXP-V15-243-001"
            / "repro_20260722/workers/champion_v2_poc_preloaded.py"
        )
        environment = os.environ.copy()
        python_path = [str(runtime / "geosolver/src"), str(runtime / "solver")]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        environment["JULIA_PROJECT"] = str(Path(__file__).resolve().parents[2] / "julia")
        cpu = reservation.physical_cpus[0]
        with tempfile.TemporaryDirectory(prefix="geotarget-") as temp:
            directory = Path(temp)
            source = directory / "problem.json"
            payload = (
                json.dumps(problem, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
            source.write_text(payload, encoding="utf-8")
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            output = directory / "engine-output"
            base_command = [
                "taskset",
                "--cpu-list",
                str(cpu),
                sys.executable,
                str(worker),
                "--source",
                str(source),
                "--source-sha256",
                source_sha,
                "--total-seconds",
                "180",
                "--search-seconds",
                "146",
                "--starts",
                "256",
                "--callbacks-per-start",
                "600",
                "--aggregate-callback-cap",
                "153600",
                "--seed",
                str(options.seed),
                "--cpu",
                str(cpu),
                "--output",
                str(output),
            ]
            self._invoke(base_command, environment, timeout=60)
            plan_path = output / "PLAN.json"
            plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            self._invoke(
                [*base_command, "--execute", "--plan-sha256", plan_sha], environment, timeout=240
            )
            result_path = output / "RESULT.json"
            if not result_path.is_file():
                raise EngineFailure("frozen engine did not write RESULT.json")
            raw = json.loads(result_path.read_text(encoding="utf-8"))
        checkpoint = WorkCheckpoint(
            window=0,
            completed_start_ordinals=list(range(256)),
            plan_sha256=plan_sha,
        )
        return raw, time.monotonic() - started, checkpoint, warnings
