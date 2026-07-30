from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_progressive_adaptive_hybrid_candidate"
    specification = importlib.util.spec_from_file_location(name, HERE / "candidate.py")
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CANDIDATE = _load()


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def starts(count: int):
    sources = (
        CANDIDATE.INSURANCE_SOURCE,
        "source_literal_product_cauchy",
        "source_literal_log_symmetric",
        "source_literal_asinh_rational",
    )
    return tuple(
        CANDIDATE.StartSpec(
            ordinal,
            sources[ordinal % 4],
            np.asarray([float(ordinal), 2.0 * ordinal + 1.0]),
            ordinal % 4 == 0,
        )
        for ordinal in range(count)
    )


def test_all_start_probe_direct_original_depth_and_quotas() -> None:
    proposals = starts(32)
    digest = CANDIDATE.proposal_prefix_digest(proposals)
    clock = Clock()

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        residual = 1.0e-20 if spec.ordinal == 31 else 1.0e6 + 31 - spec.ordinal
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(True, True, residual, 0.0),
            min(allowance, 1),
            "GENERATED_NARROW_BASIN",
        )

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=100_000,
        hard_deadline=100.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )
    first = [
        record
        for record in result.records
        if record.phase == "ORDINAL_FIRST_SERVICE"
    ]
    assert tuple(record.start_ordinal for record in first) == tuple(range(32))
    assert all(record.rung_callback_cap == 64 for record in first)
    lane = [record for record in result.records if record.start_ordinal == 31]
    assert [record.rung_callback_cap for record in lane] == [64, 600]
    assert lane[-1].attempt_wall_cap_seconds > 4.0
    assert result.activation["handoff_selected_count"] == 16
    assert result.activation["baseline_handoff_selected"] == 4
    assert result.activation["insurance_handoff_selected"] == 4
    assert result.activation["counter_cauchy_service_floor_holds"] is True
    assert result.activation["uncapped_handoff_services"] == 16
    assert CANDIDATE.proposal_prefix_digest(proposals) == digest


def test_demonstrated_starvation_is_capped_but_later_starts_are_served() -> None:
    proposals = starts(16)
    clock = Clock()
    calls = {ordinal: 0 for ordinal in range(16)}

    def runner(spec, allowance, deadline, checkpoint):
        del checkpoint
        calls[spec.ordinal] += 1
        if spec.ordinal == 0 and calls[0] == 1:
            clock.now = deadline
            return CANDIDATE.RungOutcome(
                spec.point.copy(),
                CANDIDATE.Assessment(True, True, 1.0e-20, 0.0),
                min(allowance, 1),
                "PROBE_PREEMPTED_WITH_ENDPOINT",
                completed_before_deadline=False,
                endpoint_observed_before_deadline=True,
            )
        clock.now += 0.001
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(True, True, float(spec.ordinal + 1), 0.0),
            min(allowance, 1),
            "FAST",
        )

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=100_000,
        hard_deadline=30.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )
    assert result.activation["minimum_service_complete"] is True
    assert result.records[0].attempt_wall_cap_seconds == pytest.approx(3.75)
    assert result.records[0].status.startswith("INCOMPLETE_PREDEADLINE_EVIDENCE:")
    assert calls[15] >= 1
    starved_lane = [
        record for record in result.records if record.start_ordinal == 0
    ]
    assert [record.rung_callback_cap for record in starved_lane] == [64, 600]
    assert starved_lane[-1].attempt_wall_cap_seconds <= 4.0
    assert result.activation["starvation_capped_handoff_services"] >= 1


def test_small_prefix_quota_construction_is_well_formed() -> None:
    clock = Clock()

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(True, True, 1.0, 0.0),
            min(allowance, 1),
            "OK",
        )

    result = CANDIDATE.run_rung_scheduler(
        starts(2),
        callback_cap=10_000,
        hard_deadline=10.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )
    assert result.activation["handoff_selected_count"] == 1
    assert len([row for row in result.records if row.rung_callback_cap == 600]) == 1


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown adaptive hybrid profile"):
        CANDIDATE.set_active_profile("problem-specific")
