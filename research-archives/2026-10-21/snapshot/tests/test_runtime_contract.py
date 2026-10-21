from __future__ import annotations

import time

import pytest

from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
from geosolver.runtime.protocol import WorkerRequest
from geosolver.runtime.worker import execute


def test_runtime_budget_uses_one_absolute_deadline_without_double_counting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 10.0}
    monkeypatch.setattr(
        "geosolver.engine.standard.contracts.runtime_budget.time.monotonic",
        lambda: clock["now"],
    )
    budget = RuntimeBudget(
        total_budget_sec=5.0,
        started_at_monotonic=10.0,
        deadline_monotonic=15.0,
    )

    budget.reserve_or_fail(4.0)
    assert budget.remaining_sec() == 5.0
    clock["now"] = 13.5
    assert budget.remaining_sec() == 1.5
    with pytest.raises(RuntimeError):
        budget.reserve_or_fail(2.0)


def test_worker_finishes_an_expired_inner_deadline_without_answers() -> None:
    artifact = execute(
        WorkerRequest(
            engine_document={},
            deadline_monotonic=time.monotonic() - 1,
            effective_cores=1,
        )
    )

    assert artifact.status == "completed"
    assert artifact.error is None
    assert artifact.termination_reason == "time_limit_reached"
    assert artifact.answers == []


def test_worker_protocol_v3_rejects_old_and_extra_fields() -> None:
    with pytest.raises(ValueError):
        WorkerRequest.model_validate(
            {
                "protocol_version": 1,
                "engine_document": {},
                "deadline_monotonic": time.monotonic() + 10,
            }
        )
    with pytest.raises(ValueError):
        WorkerRequest.model_validate(
            {
                "engine_document": {},
                "deadline_monotonic": time.monotonic() + 10,
                "prefer_fast": True,
            }
        )
