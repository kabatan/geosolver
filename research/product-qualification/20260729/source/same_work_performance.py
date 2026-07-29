"""Identity-free, same-work performance qualification for solver kernels.

The full solver's deadline is deliberately absent from this module.  Each
reference/candidate pair receives the same immutable proposal prefix, start
ordinals, and callback quota.  Promotion is possible only when the executor
attests that the work and semantic result digests match and no measured
structural class regresses.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import multiprocessing
import resource
import struct
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from geotarget.kernel_qualification import _canonical_record

REPORT_SCHEMA = "geotarget.same-work-performance/v1"
REQUIRED_SYNTHETIC_CLASSES = ("deep_dag", "high_fanout", "wide_expression")
REQUIRED_SYNTHETIC_OPCODES = {
    "deep_dag": frozenset(
        {"PointOnCircle", "Line", "Intersect", "Distance", "Angle"}
    ),
    "high_fanout": frozenset(
        {"PointOnCircle", "Distance", "Area", "OnCircle"}
    ),
    "wide_expression": frozenset({"Area"}),
}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _proposal_sha256(proposals: Sequence[Sequence[float]]) -> str:
    digest = hashlib.sha256()
    for point in proposals:
        digest.update(struct.pack(">Q", len(point)))
        for coordinate in point:
            digest.update(struct.pack(">d", float(coordinate)))
    return digest.hexdigest()


@dataclass(frozen=True)
class SameWorkload:
    """A structural workload; deliberately has no problem/corpus identifier."""

    structural_class: str
    start_ordinals: tuple[int, ...]
    callbacks_per_start: int
    proposals: tuple[tuple[float, ...], ...]
    expression: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.structural_class or self.structural_class == "case_id":
            raise ValueError("a structural class is required")
        normalized_ordinals = tuple(sorted(set(self.start_ordinals)))
        if not self.start_ordinals or normalized_ordinals != self.start_ordinals:
            raise ValueError("start ordinals must be non-empty, unique, and ordered")
        if self.start_ordinals[0] < 0 or self.callbacks_per_start < 1:
            raise ValueError("work bounds must be positive")
        if len(self.proposals) != self.callback_cap:
            raise ValueError("the proposal prefix must cover every callback exactly once")
        if len(set(self.proposals)) != len(self.proposals):
            raise ValueError("proposal points must not be repeated")
        if any(not point for point in self.proposals):
            raise ValueError("proposal points must be non-empty")
        if any(not math.isfinite(value) for point in self.proposals for value in point):
            raise ValueError("proposal coordinates must be finite")

    @property
    def callback_cap(self) -> int:
        return len(self.start_ordinals) * self.callbacks_per_start

    @property
    def proposal_sha256(self) -> str:
        return _proposal_sha256(self.proposals)

    @property
    def work_sha256(self) -> str:
        return _canonical_sha256(
            {
                "structural_class": self.structural_class,
                "start_ordinals": self.start_ordinals,
                "callbacks_per_start": self.callbacks_per_start,
                "proposal_sha256": self.proposal_sha256,
                "expression": self.expression,
            }
        )


@dataclass(frozen=True)
class WorkReceipt:
    start_ordinals: tuple[int, ...]
    callbacks_per_start: int
    callbacks_completed: int
    proposal_sha256: str
    input_prefix_sha256: str
    output_observation_sha256: str
    semantic_sha256: str


class SameWorkExecutor(Protocol):
    def manifest(self) -> Mapping[str, Any]: ...

    def callback(
        self,
        mode: Literal["reference", "optimized"],
        workload: SameWorkload,
        point: tuple[float, ...],
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class GateConfig:
    repetitions: int = 5
    minimum_median_wall_speedup: float = 1.5
    minimum_p95_wall_speedup: float = 1.25
    minimum_median_cpu_speedup: float = 1.0
    minimum_median_throughput_ratio: float = 1.0
    minimum_class_wall_speedup: float = 1.0
    callback_timeout_seconds: float | None = 30.0

    def __post_init__(self) -> None:
        if self.repetitions < 1:
            raise ValueError("at least one repetition is required")
        for name, value in asdict(self).items():
            if name == "callback_timeout_seconds" and value is None:
                continue
            if name != "repetitions" and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class Timing:
    wall_seconds: float
    cpu_seconds: float


@dataclass(frozen=True)
class RunMeasurement:
    structural_class: str
    work_sha256: str
    repetition: int
    mode: str
    wall_seconds: float
    cpu_seconds: float
    callbacks_completed: int
    callbacks_per_wall_second: float
    input_prefix_sha256: str
    output_observation_sha256: str
    semantic_sha256: str


@dataclass(frozen=True)
class _ClockReading:
    wall: float
    cpu: float


def _clock() -> _ClockReading:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return _ClockReading(
        wall=time.perf_counter(),
        cpu=own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime,
    )


def _elapsed(before: _ClockReading, after: _ClockReading) -> Timing:
    return Timing(
        wall_seconds=max(after.wall - before.wall, 1e-12),
        cpu_seconds=max(after.cpu - before.cpu, 1e-12),
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot summarize an empty sample")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _median(values: Sequence[float]) -> float:
    return _percentile(values, 0.5)


def _speedup(reference: float, optimized: float) -> float:
    return reference / optimized if optimized > 0 else math.inf


def _validate_executor_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "case_specific_routing": False,
        "problem_id_read": False,
        "corpus_metadata_read": False,
        "truth_read": False,
    }
    mismatches = [name for name, expected in required.items() if manifest.get(name) is not expected]
    if mismatches:
        raise ValueError("executor is not identity-free: " + ", ".join(mismatches))


def _structural_support_failures(
    manifest: Mapping[str, Any], workloads: Sequence[SameWorkload]
) -> list[str]:
    if not str(manifest.get("adapter", "")).startswith("geotarget.production-same-work/"):
        return []
    rows = {
        str(row.get("work_sha256")): row
        for row in manifest.get("prepared_support", ())
        if isinstance(row, Mapping)
    }
    failures = []
    for workload in workloads:
        row = rows.get(workload.work_sha256)
        if row is None:
            failures.append(f"{workload.structural_class}: missing production support row")
            continue
        profile = row.get("structural_profile", {})
        actual_classes = set(str(profile.get("structural_class", "")).split("+"))
        if (
            workload.structural_class in REQUIRED_SYNTHETIC_CLASSES
            and workload.structural_class not in actual_classes
        ):
            failures.append(
                f"{workload.structural_class}: declared class differs from actual V15 DAG"
            )
        trace = row.get("support_decision_trace", {})
        support_key = str(trace.get("support_key_sha256", ""))
        if len(support_key) != 64:
            failures.append(f"{workload.structural_class}: invalid support-key hash")
        actual_opcodes = set(trace.get("ast_opcode_set", ()))
        profiled_opcodes = set(profile.get("opcode_counts", {}))
        if not profiled_opcodes or not profiled_opcodes <= actual_opcodes:
            failures.append(f"{workload.structural_class}: opcode/profile mismatch")
        required_opcodes = REQUIRED_SYNTHETIC_OPCODES.get(workload.structural_class)
        if required_opcodes is not None and not required_opcodes <= actual_opcodes:
            missing = ",".join(sorted(required_opcodes - actual_opcodes))
            failures.append(
                f"{workload.structural_class}: required primitive chain missing {missing}"
            )
        problem = workload.expression.get("problem")
        if not isinstance(problem, Mapping) or row.get(
            "problem_sha256"
        ) != _canonical_sha256(problem):
            failures.append(f"{workload.structural_class}: V15 problem hash mismatch")
    return failures


def _runner_digests(
    workload: SameWorkload,
    observations: Sequence[tuple[int, int, tuple[float, ...], Mapping[str, Any]]],
) -> tuple[str, str, str]:
    inputs = hashlib.sha256()
    outputs = hashlib.sha256()
    for ordinal, callback, point, observation in observations:
        inputs.update(struct.pack(">QQ", ordinal, callback))
        inputs.update(b"".join(struct.pack(">d", value) for value in point))
        outputs.update(_canonical_record(observation))
    semantic = hashlib.sha256(
        workload.work_sha256.encode("ascii")
        + b"\0"
        + inputs.digest()
        + outputs.digest()
    ).hexdigest()
    return inputs.hexdigest(), outputs.hexdigest(), semantic


class CallbackTimeoutError(RuntimeError):
    def __init__(
        self,
        *,
        structural_class: str,
        mode: str,
        repetition: int,
        ordinal: int,
        callback_ordinal: int,
        timeout_seconds: float,
    ) -> None:
        super().__init__(f"{structural_class} {mode} callback exceeded hard timeout")
        self.detail = {
            "structural_class": structural_class,
            "mode": mode,
            "repetition": repetition,
            "start_ordinal": ordinal,
            "callback_ordinal": callback_ordinal,
            "timeout_seconds": timeout_seconds,
        }


def _callback_worker(connection: Any, executor: Any, mode: str, workload: SameWorkload) -> None:
    try:
        while True:
            message = connection.recv()
            if message is None:
                return
            before_wall = time.perf_counter()
            before_cpu = time.process_time()
            observation = executor.callback(mode, workload, message)
            elapsed_cpu = max(time.process_time() - before_cpu, 1e-12)
            elapsed_wall = max(time.perf_counter() - before_wall, 1e-12)
            connection.send((observation, elapsed_wall, elapsed_cpu))
    finally:
        connection.close()


def _stop_worker(process: Any, connection: Any) -> None:
    try:
        connection.close()
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)


def _measure(
    executor: SameWorkExecutor,
    workload: SameWorkload,
    mode: Literal["reference", "optimized"],
    repetition: int,
    *,
    clock: Any,
    timeout_seconds: float | None,
) -> tuple[RunMeasurement, WorkReceipt]:
    observations: list[tuple[int, int, tuple[float, ...], Mapping[str, Any]]] = []
    proposal_index = 0
    isolated = timeout_seconds is not None
    process = None
    parent_connection = None
    measured_wall = 0.0
    measured_cpu = 0.0
    before = clock()
    if isolated:
        context = multiprocessing.get_context("fork")
        parent_connection, child_connection = context.Pipe()
        process = context.Process(
            target=_callback_worker,
            args=(child_connection, executor, mode, workload),
            daemon=True,
        )
        process.start()
        child_connection.close()
    try:
        for ordinal in workload.start_ordinals:
            for callback_ordinal in range(workload.callbacks_per_start):
                point = workload.proposals[proposal_index]
                proposal_index += 1
                if isolated:
                    parent_connection.send(point)
                    if not parent_connection.poll(timeout_seconds):
                        raise CallbackTimeoutError(
                            structural_class=workload.structural_class,
                            mode=mode,
                            repetition=repetition,
                            ordinal=ordinal,
                            callback_ordinal=callback_ordinal,
                            timeout_seconds=timeout_seconds,
                        )
                    observation, callback_wall, callback_cpu = parent_connection.recv()
                    measured_wall += callback_wall
                    measured_cpu += callback_cpu
                else:
                    observation = executor.callback(mode, workload, point)
                if not isinstance(observation, Mapping):
                    raise RuntimeError("callback must return a semantic observation mapping")
                observations.append((ordinal, callback_ordinal, point, observation))
    finally:
        if process is not None:
            _stop_worker(process, parent_connection)
    after = clock()
    if proposal_index != workload.callback_cap:
        raise RuntimeError("runner callback accounting did not equal the cap")
    timing = (
        Timing(wall_seconds=measured_wall, cpu_seconds=measured_cpu)
        if isolated
        else _elapsed(before, after)
    )
    input_sha256, output_sha256, semantic_sha256 = _runner_digests(
        workload, observations
    )
    receipt = WorkReceipt(
        start_ordinals=workload.start_ordinals,
        callbacks_per_start=workload.callbacks_per_start,
        callbacks_completed=proposal_index,
        proposal_sha256=workload.proposal_sha256,
        input_prefix_sha256=input_sha256,
        output_observation_sha256=output_sha256,
        semantic_sha256=semantic_sha256,
    )
    return (
        RunMeasurement(
            structural_class=workload.structural_class,
            work_sha256=workload.work_sha256,
            repetition=repetition,
            mode=mode,
            wall_seconds=timing.wall_seconds,
            cpu_seconds=timing.cpu_seconds,
            callbacks_completed=receipt.callbacks_completed,
            callbacks_per_wall_second=receipt.callbacks_completed / timing.wall_seconds,
            input_prefix_sha256=receipt.input_prefix_sha256,
            output_observation_sha256=receipt.output_observation_sha256,
            semantic_sha256=receipt.semantic_sha256,
        ),
        receipt,
    )


def evaluate_measurements(
    measurements: Sequence[RunMeasurement],
    *,
    config: GateConfig,
    executor_manifest: Mapping[str, Any],
    workloads: Sequence[SameWorkload],
) -> dict[str, Any]:
    _validate_executor_manifest(executor_manifest)
    required_missing = sorted(
        set(REQUIRED_SYNTHETIC_CLASSES)
        - {workload.structural_class for workload in workloads}
    )
    failures: list[str] = []
    failures.extend(_structural_support_failures(executor_manifest, workloads))
    if required_missing:
        failures.append("missing synthetic classes: " + ", ".join(required_missing))

    summaries: list[dict[str, Any]] = []
    for workload in workloads:
        rows = [row for row in measurements if row.work_sha256 == workload.work_sha256]
        reference = [row for row in rows if row.mode == "reference"]
        optimized = [row for row in rows if row.mode == "optimized"]
        if len(reference) != config.repetitions or len(optimized) != config.repetitions:
            failures.append(f"{workload.structural_class}: incomplete repetitions")
            continue
        reference_wall = _median([row.wall_seconds for row in reference])
        optimized_wall = _median([row.wall_seconds for row in optimized])
        reference_cpu = _median([row.cpu_seconds for row in reference])
        optimized_cpu = _median([row.cpu_seconds for row in optimized])
        wall_speedup = _speedup(reference_wall, optimized_wall)
        cpu_speedup = _speedup(reference_cpu, optimized_cpu)
        throughput_ratio = _median(
            [row.callbacks_per_wall_second for row in optimized]
        ) / _median([row.callbacks_per_wall_second for row in reference])
        semantic_match = {
            row.semantic_sha256 for row in reference
        } == {row.semantic_sha256 for row in optimized} and len(
            {row.semantic_sha256 for row in reference}
        ) == 1
        input_match = {
            row.input_prefix_sha256 for row in reference
        } == {row.input_prefix_sha256 for row in optimized} and len(
            {row.input_prefix_sha256 for row in reference}
        ) == 1
        output_match = {
            row.output_observation_sha256 for row in reference
        } == {row.output_observation_sha256 for row in optimized} and len(
            {row.output_observation_sha256 for row in reference}
        ) == 1
        if not input_match:
            failures.append(f"{workload.structural_class}: input prefix mismatch")
        if not output_match:
            failures.append(f"{workload.structural_class}: output observation mismatch")
        if not semantic_match:
            failures.append(f"{workload.structural_class}: semantic digest mismatch")
        if wall_speedup < config.minimum_class_wall_speedup:
            failures.append(f"{workload.structural_class}: wall performance regressed")
        if cpu_speedup < config.minimum_median_cpu_speedup:
            failures.append(f"{workload.structural_class}: CPU performance regressed")
        if throughput_ratio < config.minimum_median_throughput_ratio:
            failures.append(f"{workload.structural_class}: throughput regressed")
        summaries.append(
            {
                "structural_class": workload.structural_class,
                "work_sha256": workload.work_sha256,
                "callback_cap": workload.callback_cap,
                "proposal_sha256": workload.proposal_sha256,
                "reference_median_wall_seconds": reference_wall,
                "optimized_median_wall_seconds": optimized_wall,
                "median_wall_speedup": wall_speedup,
                "median_cpu_speedup": cpu_speedup,
                "median_throughput_ratio": throughput_ratio,
                "input_prefix_match": input_match,
                "output_observation_match": output_match,
                "semantic_match": semantic_match,
            }
        )

    reference_rows = [row for row in measurements if row.mode == "reference"]
    optimized_rows = [row for row in measurements if row.mode == "optimized"]
    reference_by_pair = {
        (row.work_sha256, row.repetition): row for row in reference_rows
    }
    optimized_by_pair = {
        (row.work_sha256, row.repetition): row for row in optimized_rows
    }
    pair_keys = sorted(set(reference_by_pair) & set(optimized_by_pair))
    paired_wall_speedups = [
        _speedup(
            reference_by_pair[key].wall_seconds,
            optimized_by_pair[key].wall_seconds,
        )
        for key in pair_keys
    ]
    aggregate = {
        "median_wall_speedup": _median(paired_wall_speedups),
        # The p95 latency tail is the slowest five percent of paired speedups.
        "p95_wall_speedup": _percentile(paired_wall_speedups, 0.05),
        "median_cpu_speedup": _speedup(
            _median([row.cpu_seconds for row in reference_rows]),
            _median([row.cpu_seconds for row in optimized_rows]),
        ),
        "median_throughput_ratio": _median(
            [row.callbacks_per_wall_second for row in optimized_rows]
        )
        / _median([row.callbacks_per_wall_second for row in reference_rows]),
        "paired_work_repetition_count": len(paired_wall_speedups),
    }
    thresholds = {
        "median_wall_speedup": config.minimum_median_wall_speedup,
        "p95_wall_speedup": config.minimum_p95_wall_speedup,
        "median_cpu_speedup": config.minimum_median_cpu_speedup,
        "median_throughput_ratio": config.minimum_median_throughput_ratio,
    }
    for metric, minimum in thresholds.items():
        if aggregate[metric] < minimum:
            failures.append(f"aggregate {metric} below {minimum}")

    return {
        "schema": REPORT_SCHEMA,
        "promotion_allowed": not failures,
        "decision": "PROMOTE" if not failures else "REJECT_PERFORMANCE_REGRESSION",
        "identity_free_admission": True,
        "runner_owned_callback_wrapper": True,
        "executor_timing_or_count_trusted": False,
        "callback_cap_complete_required": True,
        "proposal_scope": "unique_point_per_start_callback_full_prefix",
        "required_synthetic_opcode_sets": {
            name: sorted(opcodes) for name, opcodes in REQUIRED_SYNTHETIC_OPCODES.items()
        },
        "full_solve_deadline_used": False,
        "config": asdict(config),
        "executor_manifest": dict(executor_manifest),
        "executor_manifest_sha256": _canonical_sha256(executor_manifest),
        "aggregate": aggregate,
        "structural_classes": summaries,
        "failures": failures,
        "measurements": [asdict(row) for row in measurements],
    }


def run_same_work_gate(
    executor: SameWorkExecutor,
    workloads: Sequence[SameWorkload],
    config: GateConfig | None = None,
    *,
    clock: Any = _clock,
) -> dict[str, Any]:
    if config is None:
        config = GateConfig()
    manifest = executor.manifest()
    _validate_executor_manifest(manifest)
    prepare = getattr(executor, "prepare", None)
    startup_before = clock()
    if callable(prepare):
        # Compilation and source validation are setup costs, not callback work.
        # Prepare both evaluator paths before either side is timed.
        prepare(workloads)
    startup_after = clock()
    cold_startup = _elapsed(startup_before, startup_after)
    warm_before = clock()
    if callable(prepare):
        prepare(workloads)
        manifest = executor.manifest()
        _validate_executor_manifest(manifest)
    warm_after = clock()
    warm_startup = _elapsed(warm_before, warm_after)
    support_failures = _structural_support_failures(manifest, workloads)
    if support_failures:
        return {
            "schema": REPORT_SCHEMA,
            "promotion_allowed": False,
            "decision": "REJECT_STRUCTURAL_CONTRACT",
            "identity_free_admission": True,
            "runner_owned_callback_wrapper": True,
            "executor_timing_or_count_trusted": False,
            "required_synthetic_opcode_sets": {
                name: sorted(opcodes)
                for name, opcodes in REQUIRED_SYNTHETIC_OPCODES.items()
            },
            "executor_manifest": dict(manifest),
            "failures": support_failures,
            "startup_untimed": {
                "cold_prepare": asdict(cold_startup),
                "warm_prepare": asdict(warm_startup),
            },
        }
    measurements: list[RunMeasurement] = []
    for repetition in range(config.repetitions):
        # Reverse order on alternate repetitions to avoid consistently assigning
        # warm-cache advantage to one implementation.
        modes: tuple[Literal["reference", "optimized"], ...] = (
            ("reference", "optimized")
            if repetition % 2 == 0
            else ("optimized", "reference")
        )
        for workload in workloads:
            receipts: dict[str, WorkReceipt] = {}
            for mode in modes:
                try:
                    measurement, receipt = _measure(
                        executor,
                        workload,
                        mode,
                        repetition,
                        clock=clock,
                        timeout_seconds=config.callback_timeout_seconds,
                    )
                except CallbackTimeoutError as error:
                    return {
                        "schema": REPORT_SCHEMA,
                        "promotion_allowed": False,
                        "decision": "REJECT_CALLBACK_TIMEOUT",
                        "identity_free_admission": True,
                        "runner_owned_callback_wrapper": True,
                        "executor_timing_or_count_trusted": False,
                        "callback_cap_complete_required": True,
                        "proposal_scope": "unique_point_per_start_callback_full_prefix",
                        "full_solve_deadline_used": False,
                        "config": asdict(config),
                        "structural_support_validated": True,
                        "required_synthetic_opcode_sets": {
                            name: sorted(opcodes)
                            for name, opcodes in REQUIRED_SYNTHETIC_OPCODES.items()
                        },
                        "executor_manifest": dict(manifest),
                        "executor_manifest_sha256": _canonical_sha256(manifest),
                        "timeout": error.detail,
                        "failures": [str(error)],
                        "measurements": [asdict(row) for row in measurements],
                        "startup_untimed": {
                            "cold_prepare": asdict(cold_startup),
                            "warm_prepare": asdict(warm_startup),
                        },
                    }
                measurements.append(measurement)
                receipts[mode] = receipt
            if receipts["reference"].semantic_sha256 != receipts["optimized"].semantic_sha256:
                raise RuntimeError("candidate changed the semantic result for identical work")
            if (
                receipts["reference"].callbacks_completed
                != receipts["optimized"].callbacks_completed
            ):
                raise RuntimeError("candidate changed the completed callback work")
    report = evaluate_measurements(
        measurements, config=config, executor_manifest=manifest, workloads=workloads
    )
    report["startup_untimed"] = {
        "cold_prepare": asdict(cold_startup),
        "warm_prepare": asdict(warm_startup),
    }
    return report


def synthetic_workloads(
    *, starts: int = 8, callbacks_per_start: int = 64, width: int = 96
) -> tuple[SameWorkload, ...]:
    """Return deterministic structural probes for the known broad tail classes."""

    if starts < 1 or callbacks_per_start < 1 or width < 4:
        raise ValueError("synthetic workload dimensions are too small")
    ordinals = tuple(range(starts))
    proposals = tuple(
        tuple(
            (((callback + 1) * (axis + 3) * 2654435761) % 104729) / 52364.5 - 1.0
            for axis in range(4)
        )
        for callback in range(starts * callbacks_per_start)
    )
    problems: dict[str, dict[str, Any]] = {}
    for structural_class in REQUIRED_SYNTHETIC_CLASSES:
        problem: dict[str, Any] = {
            "task": "solve",
            "id": "same-work-structural-synthetic",
            "variables": {"names": ["ax", "ay", "bx", "by"]},
            "construction": [
                {"name": "A", "expr": "Point(ax,ay)"},
                {"name": "B", "expr": "Point(bx,by)"},
            ],
            "constraints": [],
            "guards": [],
            "answer": "Distance(A,B)",
            "post_process": "",
        }
        if structural_class == "deep_dag":
            problem["variables"] = {"names": ["t", "ax", "ay", "radius"]}
            problem["construction"] = [
                {"name": "O", "expr": "Point(0,0)"},
                {"name": "A", "expr": "Point(ax,ay)"},
                {"name": "B", "expr": "Point(5,0)"},
                {"name": "gamma", "expr": "Circle(O,abs(radius)+1)"},
                {"name": "Q", "expr": "PointOnCircle(gamma,t)"},
                {"name": "ell", "expr": "Line(Q,A)"},
                {"name": "perp", "expr": "PerpendicularLine(Q,ell)"},
                {"name": "omega", "expr": "Circle(B,abs(radius)+2)"},
                {"name": "P", "expr": "Intersect(perp,omega,n=1)"},
                {"name": "R", "expr": "Reflect(P,ell)"},
                {"name": "T", "expr": "Midpoint(R,Q)"},
            ]
            problem["constraints"] = [
                {"def": "Distance(T,P)", "value": "Distance(Q,R)"},
                {"def": "Angle(P,Q,T)", "value": "Angle(A,Q,B)"},
                {"def": "OnCircle(P,omega)", "value": 0},
            ]
        elif structural_class == "high_fanout":
            problem["variables"] = {"names": ["t", "ax", "ay", "radius"]}
            problem["construction"] = [
                {"name": "O", "expr": "Point(0,0)"},
                {"name": "A", "expr": "Point(ax,ay)"},
                {"name": "gamma", "expr": "Circle(O,abs(radius)+1)"},
                {"name": "Q", "expr": "PointOnCircle(gamma,t)"},
            ]
            for index in range(width):
                name = f"F{index}"
                problem["construction"].append(
                    {
                        "name": name,
                        "expr": f"Point(A.x+{index + 1}/100,A.y-{index + 1}/100)",
                    }
                )
                problem["constraints"].extend(
                    [
                        {"def": f"Distance(Q,{name})", "value": index + 1},
                        {"def": f"Area(O,Q,{name})", "value": index + 1},
                        {"def": "OnCircle(Q,gamma)", "value": 0},
                    ]
                )
        else:
            point_names = ["A", "B"]
            for index in range(width - 2):
                name = f"W{index}"
                problem["construction"].append(
                    {
                        "name": name,
                        "expr": f"Point(ax+{index + 1}/100,by-{index + 1}/100)",
                    }
                )
                point_names.append(name)
            problem["constraints"] = [
                {"def": f"Area({','.join(point_names)})", "value": "Distance(A,B)"}
            ]
        problems[structural_class] = problem
    return tuple(
        SameWorkload(
            structural_class=name,
            start_ordinals=ordinals,
            callbacks_per_start=callbacks_per_start,
            proposals=proposals,
            expression={
                "kind": "v15",
                "declared_structural_class": name,
                "problem": problem,
            },
        )
        for name, problem in problems.items()
    )


def write_report(report: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_executor(specification: str) -> SameWorkExecutor:
    module_name, separator, factory_name = specification.partition(":")
    if not separator:
        raise ValueError("executor must use module:factory syntax")
    factory = getattr(importlib.import_module(module_name), factory_name)
    return factory()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executor", required=True, help="identity-free module:factory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--problem", action="append", type=Path, default=[])
    parser.add_argument("--starts", type=int, default=8)
    parser.add_argument("--callbacks-per-start", type=int, default=64)
    parser.add_argument("--synthetic-width", type=int, default=96)
    parser.add_argument("--minimum-median-wall-speedup", type=float, default=1.5)
    parser.add_argument("--minimum-p95-wall-speedup", type=float, default=1.25)
    parser.add_argument("--callback-timeout", type=float, default=30.0)
    arguments = parser.parse_args(argv)
    workloads: tuple[SameWorkload, ...] = synthetic_workloads(
        starts=arguments.starts,
        callbacks_per_start=arguments.callbacks_per_start,
        width=arguments.synthetic_width,
    )
    if arguments.problem:
        from geotarget.production_same_work_adapter import workloads_from_v15_paths

        workloads += workloads_from_v15_paths(
            arguments.problem,
            starts=arguments.starts,
            callbacks_per_start=arguments.callbacks_per_start,
        )
    report = run_same_work_gate(
        _load_executor(arguments.executor),
        workloads,
        GateConfig(
            repetitions=arguments.repetitions,
            minimum_median_wall_speedup=arguments.minimum_median_wall_speedup,
            minimum_p95_wall_speedup=arguments.minimum_p95_wall_speedup,
            callback_timeout_seconds=arguments.callback_timeout,
        ),
    )
    write_report(report, arguments.output)
    return 0 if report["promotion_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
