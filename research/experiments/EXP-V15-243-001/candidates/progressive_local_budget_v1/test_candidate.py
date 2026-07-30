from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import sys

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_progressive_local_budget_candidate"
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


def starts(count: int) -> tuple[object, ...]:
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
            np.asarray([float(ordinal), -float(ordinal)]),
            ordinal % 4 == 0,
        )
        for ordinal in range(count)
    )


def outcome(spec, allowance: int, residual: float = 1.0):
    return CANDIDATE.RungOutcome(
        np.asarray(spec.point, dtype=float).copy(),
        CANDIDATE.Assessment(True, True, residual, 0.0),
        allowance,
        "OK",
        promotion_signals={"model_ratio": 0.8, "rank_stability": 1.0},
    )


@pytest.mark.parametrize(
    ("profile", "expected"),
    [("64-192-600", (64, 192, 600)), ("96-300-600", (96, 300, 600))],
)
def test_exact_profiles_and_dense_first_service(profile, expected) -> None:
    CANDIDATE.set_active_profile(profile)
    proposals = starts(16)
    digest = CANDIDATE.proposal_prefix_digest(proposals)
    clock = Clock()

    def runner(spec, allowance, deadline, checkpoint):
        assert deadline > clock.now
        assert checkpoint is None
        clock.now += 0.001
        return outcome(spec, allowance, residual=1.0 / (spec.ordinal + 1))

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=1_000_000,
        hard_deadline=1_000.0,
        run_rung=runner,
        clock=clock,
        finalize_reserve_seconds=0.0,
    )
    first = result.records[: len(proposals)]
    assert tuple(row.start_ordinal for row in first) == tuple(range(len(proposals)))
    assert all(row.phase == "ORDINAL_FIRST_SERVICE" for row in first)
    assert all(row.rung_callback_cap == expected[0] for row in first)
    assert result.activation["minimum_service_complete"] is True
    assert result.activation["rungs"] == list(expected)
    assert result.activation["counter_cauchy_service_floor_holds"] is True
    assert CANDIDATE.proposal_prefix_digest(proposals) == digest


def test_256_start_fair_cap_is_exact_and_slow_first_start_cannot_monopolize() -> None:
    CANDIDATE.set_active_profile("64-192-600")
    proposals = starts(256)
    clock = Clock()
    seen: list[int] = []

    def runner(spec, allowance, deadline, checkpoint):
        del checkpoint
        seen.append(spec.ordinal)
        # Simulate each opaque attempt consuming its complete admission window.
        clock.now = deadline
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(False, False, float("inf"), float("inf")),
            min(1, allowance),
            "PREEMPTED",
            completed_before_deadline=False,
            endpoint_observed_before_deadline=False,
        )

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=153_600,
        hard_deadline=146.0,
        run_rung=runner,
        clock=clock,
        finalize_reserve_seconds=0.0,
    )
    assert result.records[0].attempt_wall_cap_seconds == pytest.approx(2 * 146 / 256)
    assert len(seen) > 1
    assert seen[:3] == [0, 1, 2]
    assert max(row.attempt_wall_cap_seconds for row in result.records) <= 4.0
    assert all(row.attempt_wall_cap_seconds >= 0.5 for row in result.records)


def test_truth_blind_quality_promotes_good_lanes_and_retains_insurance_floor() -> None:
    CANDIDATE.set_active_profile("64-192-600")
    proposals = starts(20)
    clock = Clock()

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        residual = 1.0e-12 if spec.ordinal >= 10 else 1.0e3
        return outcome(spec, allowance, residual)

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=1_000_000,
        hard_deadline=100.0,
        run_rung=runner,
        clock=clock,
        finalize_reserve_seconds=0.0,
    )
    second = [row for row in result.records if row.rung_callback_cap == 192]
    assert len(second) == 10
    assert sum(row.insurance for row in second) >= 3
    assert sum(row.start_ordinal >= 10 for row in second) >= 7
    assert result.activation["permanent_pruning"] is False


def test_public_policy_signature_and_manifest_have_no_identity_or_truth_inputs() -> None:
    forbidden = {
        "case",
        "case_id",
        "family",
        "document",
        "truth",
        "target",
        "target_count",
        "answer",
    }
    assert forbidden.isdisjoint(
        inspect.signature(CANDIDATE.run_rung_scheduler).parameters
    )
    manifest = CANDIDATE.configuration_manifest()
    assert manifest["case_family_truth_target_or_previous_outcome_inputs"] is False
    assert manifest["canonical_verifier_modified"] is False


def test_bad_insurance_prefix_fails_closed() -> None:
    malformed = list(starts(4))
    malformed[0] = CANDIDATE.StartSpec(
        0, "not-insurance", malformed[0].point, True
    )
    with pytest.raises(ValueError, match="insurance"):
        CANDIDATE.run_rung_scheduler(
            malformed,
            callback_cap=10,
            hard_deadline=10.0,
            run_rung=lambda *_args: None,
        )


def test_telemetry_contains_dynamic_cap_and_promotion_signals() -> None:
    CANDIDATE.set_active_profile("96-300-600")
    clock = Clock()
    snapshots: list[dict[str, object]] = []

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.01
        return outcome(spec, allowance, 0.1)

    result = CANDIDATE.run_rung_scheduler(
        starts(4),
        callback_cap=100_000,
        hard_deadline=30.0,
        run_rung=runner,
        clock=clock,
        finalize_reserve_seconds=0.0,
        checkpoint_sink=lambda payload: snapshots.append(dict(payload)),
    )
    assert len(snapshots) == len(result.records) + 1
    row = snapshots[-1]["services"][0]
    assert row["attempt_wall_cap_seconds"] == 4.0
    assert row["model_ratio"] == 0.8
    assert row["rank_stability"] == 1.0
    assert snapshots[-1]["profile"] == [96, 300, 600]
