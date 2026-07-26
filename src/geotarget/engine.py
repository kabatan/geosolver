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

import psutil

from geotarget.models import ExactAnswer, SolveOptions, WorkCheckpoint
from geotarget.resources import ResourceReservation

ENGINE_ID = "champion-v2-poc-preloaded-20260722"
ENGINE_HASH = "9fa23aecdb9372dfd961b46224b88937c3317eaeb56796a05142563f26078f15"


class EngineFailure(RuntimeError):
    pass


class EngineCancelled(EngineFailure):
    pass


def _terminate_process_tree(pid: int) -> None:
    """Terminate descendants even when the frozen runtime created new sessions."""

    try:
        root = psutil.Process(pid)
        descendants = root.children(recursive=True)
    except psutil.Error:
        descendants = []
    for process in reversed(descendants):
        with suppress(psutil.Error):
            process.terminate()
    with suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGTERM)
    _gone, alive = psutil.wait_procs(descendants, timeout=5)
    for process in alive:
        with suppress(psutil.Error):
            process.kill()


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


def julia_project_root() -> Path:
    packaged = Path(__file__).resolve().parent / "_julia"
    return packaged if packaged.is_dir() else Path(__file__).resolve().parents[2] / "julia"


def verify_engine() -> list[str]:
    root = Path(__file__).resolve().parents[2]
    package_root = Path(__file__).resolve().parent
    manifest_path = engine_root() / "product-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("engine_id") != ENGINE_ID or manifest.get("closure_sha256") != ENGINE_HASH:
        errors.append("product manifest identity does not match the compiled authority")
    for item in manifest.get("files", []):
        path = root / item["product_path"]
        if not path.is_file():
            relative = Path(item["product_path"]).relative_to("src/geotarget")
            path = package_root / relative
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
        if isinstance(interval_value, list):
            interval = [str(part) for part in interval_value]
        elif isinstance(interval_value, Mapping):
            left = interval_value.get("left")
            right = interval_value.get("right")
            interval = [str(left), str(right)] if left is not None and right is not None else []
        else:
            interval = []
        exact_rational = (
            interval_value.get("exact_rational_root")
            if isinstance(interval_value, Mapping)
            else None
        )
        decimal = str(
            node.get("target_1024")
            or node.get("target_768")
            or node.get("target_512")
            or node.get("decimal")
            or exact_rational
            or ""
        )
        answers.append(
            ExactAnswer(
                minimal_polynomial_high_to_low=polynomial,
                selected_real_root_index=root_index,
                isolating_interval=interval,
                decimal=decimal,
                exact_authority_kind=str(
                    node.get("exact_authority_kind") or node.get("authority_kind")
                )
                if node.get("exact_authority_kind") or node.get("authority_kind")
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
            _terminate_process_tree(process.pid)

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
            _terminate_process_tree(process.pid)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            raise EngineFailure("frozen engine exceeded its protected wall-time reserve") from error
        except BaseException:
            if process.poll() is None:
                _terminate_process_tree(process.pid)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
            raise
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
        environment["JULIA_PROJECT"] = str(julia_project_root())
        environment["GEOTARGET_PRODUCT_PYTHON"] = sys.executable
        cpus = reservation.physical_cpus
        cpu = cpus[0]
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
            worker_command = (
                [sys.executable, str(worker)]
                if len(cpus) == 1
                else [
                    sys.executable,
                    "-m",
                    "geotarget.parallel_entrypoint",
                    "--product-cpus",
                    ",".join(str(value) for value in cpus),
                ]
            )
            base_command = [
                "taskset",
                "--cpu-list",
                str(cpu),
                *worker_command,
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
            active_output = output
            remaining = options.time_limit_seconds - 180.0
            window = 0
            initial_result_path = output / "RESULT.json"
            initial_result = json.loads(initial_result_path.read_text(encoding="utf-8"))
            zero_dimensional_complete = (
                initial_result.get("status") == "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE"
            )
            while remaining >= 6.0 and not zero_dimensional_complete:
                window += 1
                window_seconds = min(180.0, remaining)
                continuation_output = directory / f"continuation-{window:03d}"
                self._invoke(
                    [
                        "taskset",
                        "--cpu-list",
                        str(cpu),
                        sys.executable,
                        "-m",
                        "geotarget.continuation",
                        "--runtime",
                        str(runtime),
                        "--source",
                        str(source),
                        "--source-sha256",
                        source_sha,
                        "--initial-output",
                        str(active_output),
                        "--output",
                        str(continuation_output),
                        "--seconds",
                        str(window_seconds),
                        "--cpu",
                        str(cpu),
                        "--cpus",
                        ",".join(str(value) for value in cpus),
                        "--seed",
                        str(options.seed),
                    ],
                    environment,
                    timeout=window_seconds + 30.0,
                )
                active_output = continuation_output
                remaining -= window_seconds
                continued = json.loads((active_output / "RESULT.json").read_text(encoding="utf-8"))
                schedule = continued.get("hp_schedule")
                continuation = continued.get("continuation")
                has_deferred = isinstance(schedule, Mapping) and bool(
                    schedule.get("deferred_record_ids")
                )
                has_pending_starts = isinstance(continuation, Mapping) and bool(
                    continuation.get("pending_start_ordinals")
                )
                if not has_deferred and not has_pending_starts:
                    break
            if 0 < remaining < 6.0:
                warnings.append(
                    "remaining time was below the frozen HP/finalization safety reserve; "
                    "the last consistent checkpoint was returned"
                )
            result_path = active_output / "RESULT.json"
            if not result_path.is_file():
                raise EngineFailure("frozen engine did not write RESULT.json")
            raw = json.loads(result_path.read_text(encoding="utf-8"))
            search_path = active_output / "search.json"
            if not search_path.is_file():
                search_path = output / "search.json"
            search = (
                json.loads(search_path.read_text(encoding="utf-8")) if search_path.is_file() else {}
            )
        schedule = raw.get("hp_schedule")
        schedule = schedule if isinstance(schedule, Mapping) else {}
        work = search.get("work") if isinstance(search, Mapping) else {}
        lanes_started = int(work.get("lanes_started", 0)) if isinstance(work, Mapping) else 0
        zero_dimensional_complete = raw.get("status") == "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE"
        completed_starts = [] if zero_dimensional_complete else list(range(min(256, lanes_started)))
        checkpoint = WorkCheckpoint(
            window=window,
            completed_start_ordinals=completed_starts,
            pending_start_ordinals=(
                [] if zero_dimensional_complete else list(range(len(completed_starts), 256))
            ),
            pending_reservoir_records=[
                str(value) for value in schedule.get("deferred_record_ids", ())
            ],
            plan_sha256=plan_sha,
        )
        return raw, time.monotonic() - started, checkpoint, warnings
