from __future__ import annotations

from geotarget.engine import ENGINE_HASH, EngineCancelled
from geotarget.models import SolveOptions, WorkCheckpoint
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


def test_python_service_normalizes_exact_result(problem: dict) -> None:
    result = solve(problem, SolveOptions(), engine=FakeEngine())
    assert result.status == "exact_complete"
    assert result.engine_hash == ENGINE_HASH
    assert result.answers[0].minimal_polynomial_high_to_low == [1, -5]
    assert result.answers[0].selected_real_root_index == 0


def test_unsupported_parallelism_is_an_explicit_resource_error(problem: dict) -> None:
    result = solve(problem, SolveOptions(cores=2), engine=FakeEngine())
    assert result.status == "resource_error"
    assert "cores=1 only" in (result.detail or "")


def test_cancelled_engine_is_reported_as_cancelled(problem: dict) -> None:
    result = solve(problem, SolveOptions(), engine=CancelledEngine())
    assert result.status == "cancelled"
    assert result.detail == "solve was cancelled"
