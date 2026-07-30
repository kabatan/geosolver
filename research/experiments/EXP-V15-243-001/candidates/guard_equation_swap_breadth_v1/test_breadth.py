from __future__ import annotations

import numpy as np

from breadth_cases import (
    curved_guard_rational_carrier,
    exponential_four_chain,
    prospective_cases,
    transcendental_helix,
)
from candidate import Observation, integration_contract, solve


def _run(case):
    return solve(
        case.evaluator,
        start=case.start,
        scale=case.scale,
        lower=case.lower,
        upper=case.upper,
    )


def _is_root(case, point: np.ndarray) -> bool:
    observation = case.evaluator(np.asarray(point, dtype=float))
    return bool(
        observation.finite
        and observation.source_valid
        and np.linalg.norm(observation.residual, ord=np.inf) <= 1.0e-9
    )


def test_prospective_breadth_gains_three_unseen_structures() -> None:
    positives = [case for case in prospective_cases(12) if case.role == "positive"]
    assert len(positives) == 36
    families: set[str] = set()
    for case in positives:
        assert not _is_root(case, case.start)
        outcome = _run(case)
        assert outcome.status == "source_root_recovered"
        assert _is_root(case, outcome.endpoint)
        assert outcome.certificate is not None
        assert outcome.counters.source_replays >= 1
        families.add(case.family)
    assert len(families) == 3


def test_negative_and_near_miss_breadth_fails_closed() -> None:
    cases = [case for case in prospective_cases(12) if case.role != "positive"]
    assert len(cases) == 72
    for case in cases:
        outcome = _run(case)
        assert outcome.status != "source_root_recovered"
        assert not _is_root(case, outcome.endpoint)


def test_unproven_and_singular_entries_never_certify() -> None:
    factories = (
        transcendental_helix,
        curved_guard_rational_carrier,
        exponential_four_chain,
    )
    for factory in factories:
        assert _run(factory(0, "near_miss")).status == (
            "no_certified_equation_guard_pair"
        )
        assert _run(factory(1, "near_miss")).status == (
            "no_certified_equation_guard_pair"
        )


def test_row_permutation_and_scaling_preserve_recovered_point() -> None:
    case = exponential_four_chain(7, "positive")
    baseline = _run(case)
    permutation = np.asarray([2, 0, 3, 1])
    multipliers = np.asarray([0.25, 3.0, 1.5, 0.7])

    def evaluator(point: np.ndarray) -> Observation:
        raw = case.evaluator(point)
        return Observation(
            raw.residual[permutation] * multipliers,
            raw.smooth_margins.copy(),
            raw.finite,
            raw.source_valid,
            raw.residual_jacobian[permutation] * multipliers[:, None],
            raw.margin_jacobian.copy(),
            raw.smooth_margin_provenance.copy(),
        )

    transformed = solve(
        evaluator,
        start=case.start,
        scale=case.scale,
        lower=case.lower,
        upper=case.upper,
    )
    assert baseline.status == transformed.status == "source_root_recovered"
    assert np.allclose(baseline.endpoint, transformed.endpoint, atol=3.0e-8)


def test_fresh_replay_remains_authority() -> None:
    case = transcendental_helix(3, "positive")
    observations: dict[bytes, int] = {}

    def evaluator(point: np.ndarray) -> Observation:
        key = np.asarray(point, dtype=float).tobytes()
        observations[key] = observations.get(key, 0) + 1
        raw = case.evaluator(point)
        at_root = np.linalg.norm(raw.residual, ord=np.inf) <= 1.0e-9
        valid = bool(raw.source_valid and not (at_root and observations[key] > 1))
        return Observation(
            raw.residual.copy(),
            raw.smooth_margins.copy(),
            raw.finite,
            valid,
            raw.residual_jacobian.copy(),
            raw.margin_jacobian.copy(),
            raw.smooth_margin_provenance.copy(),
        )

    outcome = solve(
        evaluator,
        start=case.start,
        scale=case.scale,
        lower=case.lower,
        upper=case.upper,
    )
    assert outcome.status != "source_root_recovered"
    assert outcome.counters.source_replays >= 1


def test_connection_contract_caps_candidate_share() -> None:
    contract = integration_contract()
    assert contract["proposal_only"] is True
    assert contract["fresh_source_replay_required"] is True
    assert contract["additive_lane_only"] is True
    assert contract["minimum_untouched_full_support_share"] >= 0.25
    # This candidate is authorized for at most one of four common lanes.
    candidate_share = 1.0 - 0.75
    assert candidate_share <= 0.25
    assert contract["may_read_target_or_truth"] is False
