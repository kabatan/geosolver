from __future__ import annotations

import numpy as np

from candidate import (
    _Probe,
    _cpqr_rank,
    _normal_tangential_step,
    _trial_acceptable,
    route_for_start,
    solve_attempt,
)
from generated_cases import negative_cases, positive_cases


def _solve(case, route="noise_sqp"):
    return solve_attempt(
        case.residual_factory(),
        case.start,
        route=route,
        smooth=case.smooth,
        variable_scale=case.variable_scale,
    )


def test_positive_signal_and_complete_causal_state() -> None:
    wins = 0
    for case in positive_cases():
        baseline = _solve(case, "baseline")
        candidate = _solve(case)
        wins += int(candidate.verified and not baseline.verified)
        assert baseline.callbacks == candidate.callbacks
        if candidate.activations:
            active = [state for state in candidate.states if state.activated]
            assert all(state.coarse_rank == state.fine_rank for state in active)
            assert all(state.tangential_norm > 0.0 for state in active)
            assert all(state.merit_noise_floor > 0.0 for state in active)
    assert wins >= 16


def test_noise_probe_is_empirical_and_changes_rank_floor() -> None:
    noisy = positive_cases()[-1]
    result = _solve(noisy)
    assert result.activations > 0
    assert any(state.epsilon_f > 0.0 for state in result.states)
    assert any(state.epsilon_j > 0.0 for state in result.states)
    assert any(state.rank_threshold >= 8.0 * state.epsilon_j for state in result.states)

    # Hold the mean Jacobian fixed and change only the empirically calibrated
    # epsilon_J cutoff across its weak singular direction.
    mean_jacobian = np.diag([1.0, 1e-4])
    low_noise_rank, _ = _cpqr_rank(mean_jacobian, 8.0 * 1e-6)
    high_noise_rank, _ = _cpqr_rank(mean_jacobian, 8.0 * 2e-5)
    assert low_noise_rank == 2
    assert high_noise_rank == 1


def test_joint_rank_step_and_noise_merit_causal_chain() -> None:
    jacobian = np.array([[1.0, 0.0], [2.0, 0.0], [0.0, 0.0]])
    probe = _Probe(
        residual=np.array([0.5, 1.0, -1.0]),
        coarse_jacobian=jacobian,
        fine_jacobian=jacobian,
        epsilon_f=1e-6,
        epsilon_j=1e-5,
        coarse_rank=1,
        fine_rank=1,
        rank_threshold=8e-5,
        row_scale=np.ones(3),
    )
    normal, tangential, _model = _normal_tangential_step(probe, 1.0)
    assert np.linalg.norm(normal) > 0.0
    assert np.linalg.norm(tangential) > 0.0
    assert np.linalg.norm(normal + tangential) <= 1.0 + 1e-15
    np.testing.assert_allclose(jacobian @ tangential, 0.0, rtol=0.0, atol=1e-14)

    common = dict(
        merit=1.0,
        trial_merit=0.99995,
        alpha=1.0,
        model_reduction=1.0,
        residual_norm=1.0,
        step_norm=float(np.linalg.norm(normal + tangential)),
    )
    rejected, low_floor = _trial_acceptable(epsilon_f=0.0, epsilon_j=0.0, **common)
    accepted, high_floor = _trial_acceptable(epsilon_f=1e-3, epsilon_j=1e-3, **common)
    assert not rejected and accepted
    assert high_floor > low_floor


def test_full_rank_opaque_and_inconsistent_fail_closed() -> None:
    for case in negative_cases():
        baseline = _solve(case, "baseline")
        candidate = _solve(case)
        assert baseline.callbacks == candidate.callbacks
        if case.family in {"full_rank_control", "opaque_negative", "opaque_shape_negative"}:
            np.testing.assert_allclose(candidate.endpoint, baseline.endpoint, rtol=0.0, atol=0.0)
            assert candidate.activations == 0
        if case.family == "inconsistent_negative":
            np.testing.assert_allclose(candidate.endpoint, baseline.endpoint, rtol=0.0, atol=0.0)
            assert candidate.activations == 0
        if not case.exact_roots:
            assert not candidate.verified


def test_residual_permutation_and_scale_metamorphic() -> None:
    case = positive_cases()[2]
    original = _solve(case)
    permutation = np.array([2, 0, 1])
    row_scale = np.array([7.0, 0.25, 3.0])
    base = case.residual_factory()

    def transformed(x: np.ndarray) -> np.ndarray:
        return row_scale * base(x)[permutation]

    result = solve_attempt(
        transformed,
        case.start,
        route="noise_sqp",
        variable_scale=case.variable_scale,
    )
    assert original.verified and result.verified
    np.testing.assert_allclose(result.endpoint, original.endpoint, rtol=2e-7, atol=2e-7)
    assert result.callbacks == original.callbacks
    assert [(s.coarse_rank, s.fine_rank, s.activated) for s in result.states] == [
        (s.coarse_rank, s.fine_rank, s.activated) for s in original.states
    ]
    np.testing.assert_allclose(
        [s.tangential_norm for s in result.states],
        [s.tangential_norm for s in original.states],
        rtol=2e-7,
        atol=2e-7,
    )


def test_variable_permutation_and_scale_metamorphic() -> None:
    case = positive_cases()[17]
    original = _solve(case)
    permutation = np.array([[0.0, 1.0], [1.0, 0.0]])
    diagonal = np.diag([3.0, 0.2])
    transform = permutation @ diagonal
    inverse = np.linalg.inv(transform)
    base = case.residual_factory()

    def transformed(y: np.ndarray) -> np.ndarray:
        return base(transform @ y)

    result = solve_attempt(
        transformed,
        inverse @ case.start,
        route="noise_sqp",
        variable_scale=np.array([1.0 / 3.0, 1.0 / 0.2]),
    )
    assert original.verified and result.verified
    np.testing.assert_allclose(transform @ result.endpoint, original.endpoint, rtol=3e-6, atol=3e-6)
    assert result.callbacks == original.callbacks
    assert [(s.coarse_rank, s.fine_rank, s.activated) for s in result.states] == [
        (s.coarse_rank, s.fine_rank, s.activated) for s in original.states
    ]
    np.testing.assert_allclose(
        [s.tangential_norm for s in result.states],
        [s.tangential_norm for s in original.states],
        rtol=3e-6,
        atol=3e-6,
    )


def test_portfolio_is_exactly_75_percent_immutable_baseline() -> None:
    routes = [route_for_start(index) for index in range(100)]
    assert routes.count("baseline") == 75
    assert routes.count("noise_sqp") == 25
