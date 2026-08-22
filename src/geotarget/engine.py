from __future__ import annotations

import atexit
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

import psutil

from geotarget.adaptive_continuation import (
    extension_batch_end,
    has_safe_extension_window,
    update_extension_stability,
)
from geotarget.hp_wave_checkpoint import validate as validate_wave_checkpoint
from geotarget.models import ExactAnswer, SolveOptions, TerminationReason, WorkCheckpoint
from geotarget.resources import ResourceReservation
from geotarget.runtime_broker import ProductRuntimeBroker

ENGINE_ID = "champion-v2-poc-preloaded-20260722"
ENGINE_HASH = "b3846de5a725abd32241616c637ba435b292f0a4cdd22a6bf105a2e995edf408"
OPTIMIZED_ENGINE_ID = "champion-v2-poc-preloaded-optimized-v1"
INITIAL_ALGORITHM_SECONDS = 180.0
# The frozen process establishes PROCESS_STARTED only after the interpreter and
# optimized adapter imports.  These are watchdog allowances, not algorithm
# work budgets; the frozen 180-second deadline remains unchanged.
OPTIMIZED_STARTUP_GRACE_SECONDS = 30.0
OPTIMIZED_FINALIZE_GRACE_SECONDS = 12.0


def _pending_hp_wave(schedule: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the integrity-checked unfinished product wave, if one exists."""

    if not isinstance(schedule, Mapping):
        return None
    direct = schedule.get("durable_wave_checkpoint")
    if direct is not None:
        checkpoint = validate_wave_checkpoint(direct)
        return checkpoint if checkpoint is not None and checkpoint["stage"] != "complete" else None
    batches = schedule.get("reservoir_batches")
    if isinstance(batches, list):
        for batch in reversed(batches):
            if isinstance(batch, Mapping) and batch.get("durable_wave_checkpoint") is not None:
                checkpoint = validate_wave_checkpoint(batch["durable_wave_checkpoint"])
                if checkpoint is not None and checkpoint["stage"] != "complete":
                    return checkpoint
    return None


def optimized_engine_hash() -> str:
    digest = hashlib.sha256()
    digest.update(ENGINE_HASH.encode("ascii"))
    for name in (
        "engine.py",
        "reference_entrypoint.py",
        "continuation.py",
        "hp_wave_checkpoint.py",
        "reservoir_checkpoint.py",
        "compiled_evaluator.py",
        "fused_evaluation.py",
        "lazy_symbolic_geometry.py",
        "typed_refnum_ir.py",
        "typed_refnum_intersections.py",
        "raw_libmp_backend.py",
        "flat_tape_backend.py",
        "deferred_scalar_tape.py",
        "resume_search_entrypoint.py",
        "optimized_entrypoint.py",
        "optimized_search.py",
        "search_full_prefix_entrypoint.py",
        "search_pool_worker_entrypoint.py",
        "adaptive_continuation.py",
        "parallel.py",
        "hp_slot_entrypoint.py",
        "hp_preloader.py",
        "hp_semantics.py",
        "runtime_broker.py",
    ):
        path = Path(__file__).resolve().parent / name
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def evaluator_execution_metadata(search: Mapping[str, Any], *, reference: bool) -> dict[str, Any]:
    """Describe the evaluator selected by the structural capability gate."""

    compiled = search.get("compiled_evaluator")
    compiled_record = dict(compiled) if isinstance(compiled, Mapping) else None
    enabled = bool(
        not reference and isinstance(compiled, Mapping) and compiled.get("enabled") is True
    )
    fused = bool(
        not reference
        and isinstance(compiled, Mapping)
        and isinstance(compiled.get("fused_evaluation"), Mapping)
        and compiled["fused_evaluation"].get("enabled") is True
    )
    if reference:
        mode = "frozen_reference"
        gate = "reference_engine_requested"
    elif enabled:
        mode = "typed_compiled_whole_problem"
        gate = "bitwise_equivalence_established"
    elif fused:
        mode = "fused_reference_semantics"
        gate = "bitwise_equivalent_callback_fusion"
    else:
        mode = "reference_full_problem_fallback"
        gate = (
            str(compiled.get("fallback_reason"))
            if isinstance(compiled, Mapping)
            else "compiled_evaluator_metadata_missing"
        )
    return {
        "evaluator_mode": mode,
        "typed_kernel_enabled": enabled,
        "fused_evaluation_enabled": fused,
        "typed_kernel_gate": gate,
        "compiled_evaluator": compiled_record,
    }


# This is part of the frozen 2026-07-22 execution contract, not a product
# tuning surface. Leaving native-library defaults inherited from the host
# changes how much of the fixed work order fits into the 146-second window.
FROZEN_THREAD_ENVIRONMENT = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_PRECOMPILE_TASKS": "1",
    "JULIA_PKG_PRECOMPILE_AUTO": "0",
    "RAYON_NUM_THREADS": "1",
    "CMAKE_BUILD_PARALLEL_LEVEL": "1",
    "MAKEFLAGS": "-j1",
    "MALLOC_ARENA_MAX": "2",
    "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * 1024**3),
}

_RUNTIME_BROKER: ProductRuntimeBroker | None = None
_RUNTIME_BROKER_LOCK = threading.Lock()


def _product_runtime_broker() -> ProductRuntimeBroker:
    """Create the optimized-only broker once for this API/CLI process."""
    global _RUNTIME_BROKER
    with _RUNTIME_BROKER_LOCK:
        if _RUNTIME_BROKER is not None:
            return _RUNTIME_BROKER
        runtime = engine_root() / "runtime"
        solver_root = runtime / "solver"
        hp_worker = (
            solver_root
            / "research/experiments/EXP-V15-243-001/candidates"
            / "point_on_circle_periodic_semantics/champion_composition_worker_no_1280.py"
        )
        cpus = tuple(sorted(cpu for cpu in os.sched_getaffinity(0) if 0 <= cpu < 16))
        if not cpus:
            raise EngineFailure("no frozen-compatible CPU is available for optimized runtime")
        _RUNTIME_BROKER = ProductRuntimeBroker(
            cpus=cpus,
            hp_worker=hp_worker,
            hp_environment=FROZEN_THREAD_ENVIRONMENT,
        )
        atexit.register(_RUNTIME_BROKER.close)
        return _RUNTIME_BROKER


class EngineFailure(RuntimeError):
    pass


class EngineCancelled(EngineFailure):
    pass


def _should_continue_initial_work(
    *, has_pending_starts: bool, has_deferred_candidates: bool, descriptor_count: int
) -> bool:
    """Finish the frozen prefix, but do not drain HP after it already answered."""

    return has_pending_starts or (has_deferred_candidates and descriptor_count == 0)


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
    optimized_manifest_path = package_root / "optimized-manifest.json"
    try:
        optimized_manifest = json.loads(optimized_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("optimized product manifest is missing or invalid")
        return errors
    if optimized_manifest.get("engine_id") != OPTIMIZED_ENGINE_ID:
        errors.append("optimized product manifest identity is invalid")
    if optimized_manifest.get("closure_sha256") != optimized_engine_hash():
        errors.append("optimized product manifest closure hash is stale")
    for item in optimized_manifest.get("files", []):
        path = root / str(item.get("product_path", ""))
        if not path.is_file():
            errors.append(f"missing optimized engine file: {item.get('product_path')}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            errors.append(f"optimized engine hash mismatch: {item.get('product_path')}")
    return errors


def _accepted_descriptor_nodes(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return only descriptors promoted by the frozen authority scheduler.

    HP attempt artifacts intentionally retain rejected numerical proposals and
    their provisional minpolys for auditability.  Those nested records are not
    answers.  The frozen worker's top-level distinct descriptor list is the
    authority boundary for positive-dimensional runs; the source-exact route
    exposes one explicitly accepted descriptor instead.
    """

    for field in ("distinct_exact_target_descriptors", "distinct_exact_targets"):
        if field not in raw:
            continue
        values = raw.get(field)
        if not isinstance(values, list):
            return []
        return [value for value in values if isinstance(value, Mapping)]

    descriptor = raw.get("exact_target_descriptor")
    if (
        raw.get("authority_pass") is True
        and raw.get("status") == "EXACT_SYMBOLIC_TARGET_READY"
        and isinstance(descriptor, Mapping)
    ):
        return [descriptor]
    return []


def extract_answers(raw: Mapping[str, Any]) -> list[ExactAnswer]:
    answers: list[ExactAnswer] = []
    seen: set[tuple[str, int]] = set()
    for node in _accepted_descriptor_nodes(raw):
        if "minimal_polynomial_high_to_low" not in node:
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
                # A descriptor is deliberately independent of rejected HP
                # attempt records.  Until the frozen result promotes a witness
                # alongside this exact descriptor, returning no witness is
                # safer than attaching an unrelated exploratory endpoint.
                approximate_witness=None,
            )
        )
    return answers


class ChampionSubprocessEngine:
    def __init__(self, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = threading.Event()
        self._progress_callback = progress_callback
        self._runtime_broker: ProductRuntimeBroker | None = None
        self._runtime_session: str | None = None
        self._runtime_environment: dict[str, str] = {}

    def _emit_progress(self, **payload: Any) -> None:
        if self._progress_callback is not None:
            self._progress_callback(dict(payload))

    def cancel(self) -> None:
        self._cancel_requested.set()
        if self._runtime_broker is not None and self._runtime_session is not None:
            with suppress(KeyError):
                self._runtime_broker.cancel_session(self._runtime_session)
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
        if options.engine == "reference":
            return self._execute(problem, options, reservation)
        broker = _product_runtime_broker()
        token = broker.begin_session(reservation.physical_cpus)
        self._runtime_broker = broker
        self._runtime_session = token
        self._runtime_environment = broker.session_environment(token)
        try:
            raw, elapsed, checkpoint, warnings = self._execute(problem, options, reservation)
            product = raw.setdefault("geotarget_product", {})
            if isinstance(product, dict):
                product["runtime_cache"] = broker.session_metadata(token)
            return raw, elapsed, checkpoint, warnings
        finally:
            broker.end_session(token)
            self._runtime_session = None
            self._runtime_environment = {}

    def _execute(
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
        phase_elapsed: dict[str, float] = {}
        runtime = engine_root() / "runtime"
        worker = (
            runtime
            / "solver/research/experiments/EXP-V15-243-001"
            / "repro_20260722/workers/champion_v2_poc_preloaded.py"
        )
        environment = {**os.environ, **FROZEN_THREAD_ENVIRONMENT}
        python_path = [str(runtime / "geosolver/src"), str(runtime / "solver")]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        environment["JULIA_PROJECT"] = str(julia_project_root())
        environment["GEOTARGET_PRODUCT_PYTHON"] = sys.executable
        cpus = reservation.physical_cpus
        cpu = cpus[0]
        reference = options.engine == "reference"
        if not reference:
            environment.update(self._runtime_environment)
        hard_limit = INITIAL_ALGORITHM_SECONDS if reference else options.max_time_seconds

        def invoke_phase(
            name: str, command: list[str], *, timeout: float
        ) -> subprocess.CompletedProcess[str]:
            phase_started = time.monotonic()
            self._emit_progress(
                phase=name,
                elapsed_seconds=time.monotonic() - started,
                max_time_seconds=hard_limit,
                used_cores=len(cpus),
            )
            try:
                return self._invoke(command, environment, timeout=timeout)
            finally:
                phase_elapsed[name] = phase_elapsed.get(name, 0.0) + (
                    time.monotonic() - phase_started
                )

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
                if reference
                else [
                    sys.executable,
                    "-m",
                    "geotarget.optimized_entrypoint",
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
                str(int(INITIAL_ALGORITHM_SECONDS)),
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
            dry_status = directory / "outer-dry-status.json"
            invoke_phase(
                "dry_plan",
                [
                    sys.executable,
                    "-m",
                    "geotarget.reference_entrypoint",
                    "--phase",
                    "dry",
                    "--status",
                    str(dry_status),
                    "--",
                    *base_command,
                ],
                timeout=60,
            )
            plan_path = output / "PLAN.json"
            plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            execute_status = directory / "outer-execute-status.json"
            execute_guard_options = (
                []
                if reference
                else [
                    "--rss-mib",
                    str(min(8192.0, max(512.0, len(cpus) * 384.0))),
                    "--algorithm-seconds",
                    str(INITIAL_ALGORITHM_SECONDS),
                    "--startup-grace-seconds",
                    str(OPTIMIZED_STARTUP_GRACE_SECONDS),
                    "--finalize-grace-seconds",
                    str(OPTIMIZED_FINALIZE_GRACE_SECONDS),
                    "--accept-committed-on-timeout",
                ]
            )
            # Setup/doctor/dry-plan telemetry is reported in total elapsed time,
            # but the declared solve budget begins once immediately before the
            # execute child and remains the sole authority for continuation.
            budget_started = time.monotonic()
            invoke_phase(
                "initial_champion",
                [
                    sys.executable,
                    "-m",
                    "geotarget.reference_entrypoint",
                    "--phase",
                    "execute",
                    "--status",
                    str(execute_status),
                    *execute_guard_options,
                    "--",
                    *base_command,
                    "--execute",
                    "--plan-sha256",
                    plan_sha,
                ],
                timeout=240,
            )
            active_output = output
            window = 0
            initial_result_path = output / "RESULT.json"
            initial_result = json.loads(initial_result_path.read_text(encoding="utf-8"))
            try:
                execute_guard = json.loads(execute_status.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                execute_guard = {}
            if execute_guard.get("classification") == "TIMEOUT":
                warnings.append(
                    "the process watchdog expired after an atomic engine result was committed; "
                    "the committed exact-authority checkpoint was retained"
                )
            zero_dimensional_complete = (
                initial_result.get("status") == "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE"
            )
            initial_descriptor_count = len(extract_answers(initial_result))
            initial_search_path = output / "search.json"
            initial_search = (
                json.loads(initial_search_path.read_text(encoding="utf-8"))
                if initial_search_path.is_file()
                else {}
            )
            initial_work = (
                initial_search.get("work")
                if isinstance(initial_search.get("work"), Mapping)
                else {}
            )
            self._emit_progress(
                phase="initial",
                completed_starts=int(initial_work.get("lanes_started", 0)),
                total_starts=256,
                extension_batches_completed=0,
                consecutive_empty_extension_batches=0,
                elapsed_seconds=time.monotonic() - started,
                max_time_seconds=hard_limit,
                used_cores=len(cpus),
            )
            reported_initial_elapsed = initial_result.get("elapsed_wall_seconds")
            initial_budget_elapsed = (
                max(0.0, float(reported_initial_elapsed))
                if isinstance(reported_initial_elapsed, int | float)
                else time.monotonic() - budget_started
            )
            post_initial_started = time.monotonic()

            def remaining_algorithm_budget() -> float:
                return (
                    hard_limit - initial_budget_elapsed - (time.monotonic() - post_initial_started)
                )

            def state(path: Path) -> tuple[dict[str, Any], dict[str, Any], bool, bool]:
                result = json.loads((path / "RESULT.json").read_text(encoding="utf-8"))
                search_path = path / "search.json"
                if not search_path.is_file():
                    search_path = output / "search.json"
                search = (
                    json.loads(search_path.read_text(encoding="utf-8"))
                    if search_path.is_file()
                    else {}
                )
                work = search.get("work") if isinstance(search, Mapping) else {}
                lanes = int(work.get("lanes_started", 0)) if isinstance(work, Mapping) else 0
                schedule = result.get("hp_schedule")
                deferred = isinstance(schedule, Mapping) and bool(
                    schedule.get("deferred_record_ids")
                )
                deferred = deferred or _pending_hp_wave(schedule) is not None
                continuation = result.get("continuation")
                pending = isinstance(continuation, Mapping) and bool(
                    continuation.get("pending_start_ordinals")
                )
                return result, search, deferred, pending or lanes < 256

            # Finish only work already belonging to the original 256-start graph.
            if not reference and not zero_dimensional_complete:
                controller_round = 0
                controller_stalled = False
                while True:
                    remaining = remaining_algorithm_budget()
                    before_raw, _before_search, has_deferred, has_pending_starts = state(
                        active_output
                    )
                    should_continue_initial = _should_continue_initial_work(
                        has_pending_starts=has_pending_starts,
                        has_deferred_candidates=has_deferred,
                        descriptor_count=len(extract_answers(before_raw)),
                    )
                    if remaining < 12.0 or not should_continue_initial or controller_stalled:
                        break
                    controller_round += 1
                    continuation_output = (
                        directory / f"continuation-controller-{controller_round:03d}"
                    )
                    invoke_phase(
                        "initial_continuation",
                        [
                            "taskset",
                            "--cpu-list",
                            str(cpu),
                            sys.executable,
                            "-m",
                            "geotarget.continuation",
                            "--controller",
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
                            str(min(180.0, remaining)),
                            "--cpu",
                            str(cpu),
                            "--cpus",
                            ",".join(str(value) for value in cpus),
                            "--seed",
                            str(options.seed),
                        ],
                        timeout=min(180.0, remaining) + 30.0,
                    )
                    controller_state_path = continuation_output / "controller-state.json"
                    controller_state = json.loads(controller_state_path.read_text(encoding="utf-8"))
                    if controller_state.get("status") != "completed":
                        raise EngineFailure("continuation controller did not commit completion")
                    candidate_output = Path(str(controller_state["active_output"])).resolve()
                    allowed_root = continuation_output.resolve()
                    if candidate_output != output.resolve() and not candidate_output.is_relative_to(
                        allowed_root
                    ):
                        raise EngineFailure("continuation controller output escaped its root")
                    if not (candidate_output / "RESULT.json").is_file():
                        raise EngineFailure("continuation controller checkpoint is incomplete")
                    active_output = candidate_output
                    window += int(controller_state.get("windows_completed", 0))
                    controller_stalled = bool(controller_state.get("stalled"))
                    controller_windows = controller_state.get("windows")
                    if isinstance(controller_windows, list):
                        stalled_pending = any(
                            isinstance(item, Mapping)
                            and bool(item.get("stalled"))
                            and bool(item.get("pending_starts_before_window"))
                            for item in controller_windows
                        )
                        stalled_deferred = any(
                            isinstance(item, Mapping)
                            and bool(item.get("stalled"))
                            and not bool(item.get("pending_starts_before_window"))
                            for item in controller_windows
                        )
                        if stalled_pending:
                            warnings.append(
                                "an unfinished start made no checkpoint progress in one window; "
                                "the same ordinal was retried within the safety cap"
                            )
                        if stalled_deferred:
                            warnings.append(
                                "the frozen candidate continuation made no progress; "
                                "the last consistent checkpoint was returned"
                            )
                    _after_raw, after_search, _after_deferred, _after_pending = state(active_output)
                    after_work = (
                        after_search.get("work")
                        if isinstance(after_search.get("work"), Mapping)
                        else {}
                    )
                    self._emit_progress(
                        phase="initial_continuation",
                        completed_starts=int(after_work.get("lanes_started", 0)),
                        total_starts=256,
                        continuation_windows=window,
                        elapsed_seconds=time.monotonic() - started,
                        max_time_seconds=hard_limit,
                        used_cores=len(cpus),
                    )
            raw, search, has_deferred, has_pending_starts = state(active_output)
            # "Initial" means the complete frozen 0..255 work graph, including
            # every checkpointed HP/alternate/restoration tranche—not merely
            # the first 180-second child process.
            initial_descriptor_count = len(extract_answers(raw))
            original_work = search.get("work") if isinstance(search, Mapping) else {}
            original_lanes_started = (
                int(original_work.get("lanes_started", 0))
                if isinstance(original_work, Mapping)
                else 0
            )
            extension_batches = 0
            empty_extension_batches = 0
            extension_found_answer = False
            extension_completed_ordinals: list[int] = []
            extension_pending_ordinals: list[int] = []
            next_start = 256
            termination = TerminationReason.SAFETY_CAP

            if zero_dimensional_complete:
                termination = TerminationReason.EXACT_COMPLETE
            elif (
                options.run_mode == "adaptive"
                and not has_deferred
                and not has_pending_starts
                and not extract_answers(raw)
            ):
                # The only permitted work-graph extension: zero accepted answers
                # after the complete frozen 256-start prefix.
                while True:
                    batch_start = next_start
                    batch_end = extension_batch_end(batch_start)
                    batch_cursor = batch_start
                    before_count = len(extract_answers(raw))
                    extension_window = 0
                    while batch_cursor < batch_end:
                        remaining = remaining_algorithm_budget()
                        if not has_safe_extension_window(remaining):
                            break
                        extension_window += 1
                        batch_output = directory / (
                            f"adaptive-{extension_batches + 1:03d}-window-{extension_window:03d}"
                        )
                        invoke_phase(
                            "adaptive_extension",
                            [
                                sys.executable,
                                "-m",
                                "geotarget.adaptive_continuation",
                                "--runtime",
                                str(runtime),
                                "--source",
                                str(source),
                                "--source-sha256",
                                source_sha,
                                "--initial-output",
                                str(active_output),
                                "--output",
                                str(batch_output),
                                "--seconds",
                                str(min(180.0, remaining)),
                                "--cpus",
                                ",".join(str(value) for value in cpus),
                                "--seed",
                                str(options.seed),
                                "--ordinal-start",
                                str(batch_cursor),
                                "--ordinal-end",
                                str(batch_end),
                            ],
                            timeout=min(180.0, remaining) + 30.0,
                        )
                        active_output = batch_output
                        raw, search, _deferred, _pending = state(active_output)
                        optimized_search = (
                            search.get("optimized_parallel_search")
                            if isinstance(search, Mapping)
                            else None
                        )
                        accepted_end = batch_cursor
                        if isinstance(optimized_search, Mapping):
                            accepted_end = int(
                                optimized_search.get("accepted_prefix_end", batch_cursor)
                            )
                            extension_completed_ordinals.extend(
                                int(value)
                                for value in optimized_search.get("completed_start_ordinals", ())
                                if isinstance(value, int)
                            )
                        if not batch_cursor < accepted_end <= batch_end:
                            break
                        batch_cursor = accepted_end
                    if batch_cursor != batch_end:
                        warnings.append(
                            "the safety cap interrupted an extension batch; "
                            "the last exact-authority checkpoint was returned"
                        )
                        next_start = batch_cursor
                        extension_pending_ordinals = list(range(batch_cursor, batch_end))
                        break
                    extension_batches += 1
                    next_start = batch_end
                    after_count = len(extract_answers(raw))
                    (
                        extension_found_answer,
                        empty_extension_batches,
                        extension_stable,
                    ) = update_extension_stability(
                        descriptors_before=before_count,
                        descriptors_after=after_count,
                        answer_found=extension_found_answer,
                        consecutive_empty_batches=empty_extension_batches,
                    )
                    self._emit_progress(
                        phase="extension",
                        completed_starts=256 + len(set(extension_completed_ordinals)),
                        total_starts=next_start,
                        extension_batches_completed=extension_batches,
                        consecutive_empty_extension_batches=empty_extension_batches,
                        elapsed_seconds=time.monotonic() - started,
                        max_time_seconds=hard_limit,
                        used_cores=len(cpus),
                    )
                    if extension_stable:
                        termination = TerminationReason.EXTENSION_STABLE
                        break
            elif extract_answers(raw):
                termination = (
                    TerminationReason.EXACT_COMPLETE
                    if raw.get("status") == "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE"
                    else TerminationReason.INITIAL_WORK_ANSWERED
                )

            remaining = remaining_algorithm_budget()
            if 0.0 < remaining < 12.0 and termination == TerminationReason.SAFETY_CAP:
                warnings.append(
                    "remaining time was below the HP/finalization safety reserve; "
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
            evaluator_metadata = evaluator_execution_metadata(search, reference=reference)
            raw["geotarget_product"] = {
                "engine_variant": "reference" if reference else "optimized",
                "engine_id": ENGINE_ID if reference else OPTIMIZED_ENGINE_ID,
                "engine_hash": ENGINE_HASH if reference else optimized_engine_hash(),
                "termination_reason": termination.value,
                "initial_descriptor_count": initial_descriptor_count,
                "extension_batches_completed": extension_batches,
                "consecutive_empty_extension_batches": empty_extension_batches,
                "phase_elapsed_seconds": phase_elapsed,
                "requested_max_time_seconds": hard_limit,
                "used_physical_cpus": list(cpus),
                **evaluator_metadata,
            }
        schedule = raw.get("hp_schedule")
        schedule = schedule if isinstance(schedule, Mapping) else {}
        pending_wave = _pending_hp_wave(schedule)
        zero_dimensional_complete = raw.get("status") == "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE"
        optimized_search_meta = (
            search.get("optimized_parallel_search") if isinstance(search, Mapping) else None
        )
        explicit_initial_ordinals = (
            sorted(
                {
                    int(value)
                    for value in optimized_search_meta.get("completed_start_ordinals", ())
                    if isinstance(value, int) and 0 <= value < 256
                }
            )
            if isinstance(optimized_search_meta, Mapping)
            else list(range(min(256, original_lanes_started)))
        )
        completed_starts = (
            []
            if zero_dimensional_complete
            else explicit_initial_ordinals + sorted(set(extension_completed_ordinals))
        )
        checkpoint = WorkCheckpoint(
            window=window,
            phase=("extension" if extension_batches else "initial"),
            completed_start_ordinals=completed_starts,
            pending_start_ordinals=(
                []
                if zero_dimensional_complete
                else (
                    sorted(set(range(256)) - set(explicit_initial_ordinals))
                    + extension_pending_ordinals
                )
            ),
            pending_reservoir_records=[
                str(value) for value in schedule.get("deferred_record_ids", ())
            ],
            pending_hp_alternates=(
                list(pending_wave["pending_alternate_record_ids"])
                if pending_wave is not None
                else []
            ),
            pending_restoration=(
                list(pending_wave["pending_restoration_record_ids"])
                if pending_wave is not None
                else []
            ),
            plan_sha256=plan_sha,
            extension_batches_completed=extension_batches,
            consecutive_empty_extension_batches=empty_extension_batches,
            descriptors_before_extension=initial_descriptor_count,
            descriptors_after_extension=len(extract_answers(raw)),
            termination_reason=termination,
            phase_elapsed_seconds=phase_elapsed,
        )
        return raw, time.monotonic() - started, checkpoint, warnings
