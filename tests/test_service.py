from __future__ import annotations

from geotarget.engine import OPTIMIZED_ENGINE_ID, EngineCancelled, optimized_engine_hash
from geotarget.models import SolveOptions, WorkCheckpoint
from geotarget.resources import ResourceReservation
from geotarget.service import solve


class FakeEngine:
    def cancel(self) -> None:
        return None

    def execute(self, problem, options, reservation):
        return (
            {
                "status": "EXACT_SYMBOLIC_TARGET_READY",
                "exact_target_descriptor": {
                    "minimal_polynomial_high_to_low": [1, -5],
                    "selected_real_root_index": 0,
                    "isolating_interval": ["5", "5"],
                    "target_1024": "5.0000000000",
                    "exact_authority_kind": "source_exact",
                },
            },
            0.01,
            WorkCheckpoint(completed_start_ordinals=list(range(256)), plan_sha256="a" * 64),
            [],
        )


class CancelledEngine(FakeEngine):
    def execute(self, problem, options, reservation):
        raise EngineCancelled("solve was cancelled")


class RecordingEngine(FakeEngine):
    received_problem = None
    received_options = None

    def execute(self, problem, options, reservation):
        self.received_problem = problem
        self.received_options = options
        return super().execute(problem, options, reservation)


class ReferenceEvaluatorFallbackEngine(FakeEngine):
    def execute(self, problem, options, reservation):
        raw, elapsed, checkpoint, warnings = super().execute(problem, options, reservation)
        raw["geotarget_product"] = {
            "evaluator_mode": "reference_full_problem_fallback",
            "typed_kernel_enabled": False,
            "typed_kernel_gate": "bitwise_equivalence_not_established",
        }
        return raw, elapsed, checkpoint, warnings


def test_python_service_normalizes_exact_result(problem: dict) -> None:
    result = solve(
        problem,
        SolveOptions(engine="optimized"),
        engine=FakeEngine(),
    )
    assert result.status == "exact_complete"
    assert result.engine_id == OPTIMIZED_ENGINE_ID
    assert result.engine_hash == optimized_engine_hash()
    assert result.answers[0].minimal_polynomial_high_to_low == [1, -5]
    assert result.answers[0].selected_real_root_index == 0


def test_supported_parallelism_is_reported_without_downgrade(problem: dict) -> None:
    result = solve(
        problem,
        SolveOptions(engine="optimized", cores=2),
        engine=FakeEngine(),
    )
    assert result.status == "exact_complete"
    assert result.requested_resources.cores == 2
    assert result.used_resources.cores == 2


def test_cancelled_engine_is_reported_as_cancelled(problem: dict) -> None:
    result = solve(problem, SolveOptions(), engine=CancelledEngine())
    assert result.status == "cancelled"
    assert result.detail == "solve was cancelled"


def test_service_passes_native_json_scalars_to_engine_unchanged(problem: dict) -> None:
    problem["constraints"].append({"def": "Distance(A, B)", "value": 4})
    engine = RecordingEngine()

    solve(problem, SolveOptions(), engine=engine)

    assert engine.received_problem == problem
    assert type(engine.received_problem["constraints"][0]["value"]) is int


def test_service_preserves_auto_request_and_passes_resolved_cores_to_engine(
    problem: dict, monkeypatch
) -> None:
    monkeypatch.setattr(
        "geotarget.service.reserve",
        lambda options: ResourceReservation((2, 4, 6), 20_000_000_000),
    )
    engine = RecordingEngine()

    result = solve(
        problem,
        SolveOptions(engine="optimized", cores="auto"),
        engine=engine,
    )

    assert result.requested_resources.cores == "auto"
    assert result.used_resources.cores == 3
    assert engine.received_options.cores == 3
    assert result.engine_variant == "optimized"
    assert result.termination_reason == "exact_complete"


def test_service_surfaces_legacy_time_limit_warning(problem: dict) -> None:
    result = solve(
        problem,
        {"time_limit_seconds": 180, "cores": 1},
        engine=FakeEngine(),
    )

    assert result.status == "exact_complete"
    assert result.requested_resources.max_time_seconds == 180
    assert any("time_limit_seconds is deprecated" in warning for warning in result.warnings)


def test_optimized_service_discloses_whole_problem_reference_evaluator_fallback(
    problem: dict,
) -> None:
    optimized = solve(
        problem,
        SolveOptions(engine="optimized"),
        engine=ReferenceEvaluatorFallbackEngine(),
    )
    reference = solve(
        problem,
        SolveOptions(
            engine="reference",
            run_mode="fixed_time",
            max_time_seconds=180,
            cores=1,
        ),
        engine=ReferenceEvaluatorFallbackEngine(),
    )

    assert any("frozen reference evaluator throughout" in warning for warning in optimized.warnings)
    assert not any(
        "frozen reference evaluator throughout" in warning
        for warning in reference.warnings
    )
