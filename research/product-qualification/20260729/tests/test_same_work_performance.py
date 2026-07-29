from __future__ import annotations

import time

import pytest

from geotarget.same_work_performance import (
    REQUIRED_SYNTHETIC_OPCODES,
    GateConfig,
    RunMeasurement,
    evaluate_measurements,
    run_same_work_gate,
    synthetic_workloads,
)


def _manifest() -> dict[str, bool]:
    return {
        "case_specific_routing": False,
        "problem_id_read": False,
        "corpus_metadata_read": False,
        "truth_read": False,
    }


def _measurement(workload, mode: str, wall: float, repetition: int = 0):
    return RunMeasurement(
        structural_class=workload.structural_class,
        work_sha256=workload.work_sha256,
        repetition=repetition,
        mode=mode,
        wall_seconds=wall,
        cpu_seconds=wall * 0.9,
        callbacks_completed=workload.callback_cap,
        callbacks_per_wall_second=workload.callback_cap / wall,
        input_prefix_sha256="b" * 64,
        output_observation_sha256="c" * 64,
        semantic_sha256="a" * 64,
    )


def test_synthetic_suite_is_structural_and_reproducible() -> None:
    from geotarget.production_same_work_adapter import structural_profile

    first = synthetic_workloads(starts=3, callbacks_per_start=7, width=12)
    second = synthetic_workloads(starts=3, callbacks_per_start=7, width=12)
    assert [work.structural_class for work in first] == [
        "deep_dag",
        "high_fanout",
        "wide_expression",
    ]
    assert [work.work_sha256 for work in first] == [work.work_sha256 for work in second]
    assert all(work.start_ordinals == (0, 1, 2) for work in first)
    assert all(work.callback_cap == 21 for work in first)
    assert all(len(work.proposals) == 21 for work in first)
    assert all(len(set(work.proposals)) == 21 for work in first)
    assert all(work.expression["kind"] == "v15" for work in first)
    for work in first:
        profile = structural_profile(work.expression["problem"])
        assert work.structural_class in profile["structural_class"].split("+")
        assert REQUIRED_SYNTHETIC_OPCODES[work.structural_class] <= set(
            profile["opcode_counts"]
        )
    assert all("case" not in work.__dict__ for work in first)


def test_any_structural_class_regression_rejects_promotion() -> None:
    workloads = synthetic_workloads(starts=2, callbacks_per_start=3, width=4)
    rows = []
    for workload in workloads:
        rows.append(_measurement(workload, "reference", 2.0))
        optimized_wall = 2.1 if workload.structural_class == "high_fanout" else 1.0
        rows.append(_measurement(workload, "optimized", optimized_wall))
    report = evaluate_measurements(
        rows,
        config=GateConfig(repetitions=1),
        executor_manifest=_manifest(),
        workloads=workloads,
    )
    assert report["promotion_allowed"] is False
    assert report["decision"] == "REJECT_PERFORMANCE_REGRESSION"
    assert "high_fanout: wall performance regressed" in report["failures"]
    assert report["full_solve_deadline_used"] is False
    assert report["executor_manifest"] == _manifest()


def test_aggregate_cpu_wall_p95_and_throughput_are_all_gates() -> None:
    workloads = synthetic_workloads(starts=2, callbacks_per_start=3, width=4)
    rows = []
    for workload in workloads:
        rows.extend(
            (
                _measurement(workload, "reference", 2.0),
                _measurement(workload, "optimized", 1.0),
            )
        )
    report = evaluate_measurements(
        rows,
        config=GateConfig(
            repetitions=1,
            minimum_median_wall_speedup=1.5,
            minimum_p95_wall_speedup=1.5,
            minimum_median_cpu_speedup=1.5,
            minimum_median_throughput_ratio=1.5,
            minimum_class_wall_speedup=1.0,
        ),
        executor_manifest=_manifest(),
        workloads=workloads,
    )
    assert report["promotion_allowed"] is True
    assert report["aggregate"] == {
        "median_wall_speedup": 2.0,
        "p95_wall_speedup": 2.0,
        "median_cpu_speedup": 2.0,
        "median_throughput_ratio": 2.0,
        "paired_work_repetition_count": 3,
    }


def test_p95_uses_paired_work_repetition_tail_not_pooled_latency() -> None:
    workloads = synthetic_workloads(starts=1, callbacks_per_start=2, width=4)
    rows = []
    for workload, speedup in zip(workloads, (2.0, 2.0, 1.3), strict=True):
        rows.extend(
            (
                _measurement(workload, "reference", 100.0),
                _measurement(workload, "optimized", 100.0 / speedup),
            )
        )
    report = evaluate_measurements(
        rows,
        config=GateConfig(
            repetitions=1,
            minimum_median_wall_speedup=1.5,
            minimum_p95_wall_speedup=1.5,
        ),
        executor_manifest=_manifest(),
        workloads=workloads,
    )
    assert report["aggregate"]["median_wall_speedup"] == 2.0
    assert report["aggregate"]["p95_wall_speedup"] == pytest.approx(1.37)
    assert "aggregate p95_wall_speedup below 1.5" in report["failures"]


class FakeClock:
    def __init__(self, readings):
        self.readings = iter(readings)

    def __call__(self):
        return next(self.readings)


class FakeExecutor:
    def __init__(self, *, alter: str | None = None) -> None:
        self.alter = alter
        self.calls = []

    def manifest(self):
        return _manifest()

    def callback(self, mode, workload, point):
        self.calls.append((mode, workload.work_sha256, point))
        return {
            "value": point,
            "semantic_marker": "altered" if mode == "optimized" and self.alter else "same",
        }


def _clock_readings(count: int):
    from geotarget.same_work_performance import _ClockReading

    # Every run takes exactly one wall and CPU second.
    return [_ClockReading(float(index), float(index)) for index in range(count)]


def test_runner_accepts_identity_free_semantically_equal_same_work() -> None:
    workloads = synthetic_workloads(starts=2, callbacks_per_start=3, width=4)
    report = run_same_work_gate(
        executor := FakeExecutor(),
        workloads,
        GateConfig(
            repetitions=1,
            minimum_median_wall_speedup=1.0,
            minimum_p95_wall_speedup=1.0,
            callback_timeout_seconds=None,
        ),
        clock=FakeClock(_clock_readings(16)),
    )
    assert report["promotion_allowed"] is True
    assert report["decision"] == "PROMOTE"
    assert len(report["measurements"]) == 6
    assert len(executor.calls) == 2 * sum(work.callback_cap for work in workloads)
    assert report["startup_untimed"] == {
        "cold_prepare": {"wall_seconds": 1.0, "cpu_seconds": 1.0},
        "warm_prepare": {"wall_seconds": 1.0, "cpu_seconds": 1.0},
    }
    assert report["executor_timing_or_count_trusted"] is False


def test_runner_rejects_nonidentical_semantics() -> None:
    workloads = synthetic_workloads(starts=2, callbacks_per_start=3, width=4)
    with pytest.raises(RuntimeError, match="semantic result"):
        run_same_work_gate(
            FakeExecutor(alter="semantic"),
            workloads,
            GateConfig(repetitions=1),
            clock=FakeClock(_clock_readings(16)),
        )


def test_hard_callback_timeout_is_killed_and_rejects_promotion() -> None:
    class SlowExecutor(FakeExecutor):
        def callback(self, mode, workload, point):
            time.sleep(10)
            return super().callback(mode, workload, point)

    report = run_same_work_gate(
        SlowExecutor(),
        synthetic_workloads(starts=1, callbacks_per_start=1, width=4),
        GateConfig(repetitions=1, callback_timeout_seconds=0.02),
    )
    assert report["decision"] == "REJECT_CALLBACK_TIMEOUT"
    assert report["promotion_allowed"] is False
    assert report["timeout"]["callback_ordinal"] == 0
    assert report["timeout"]["timeout_seconds"] == 0.02


def test_identity_reading_executor_is_rejected_before_benchmark() -> None:
    executor = FakeExecutor()
    executor.manifest = lambda: {**_manifest(), "problem_id_read": True}
    with pytest.raises(ValueError, match="identity-free"):
        run_same_work_gate(executor, synthetic_workloads(), GateConfig(repetitions=1))
