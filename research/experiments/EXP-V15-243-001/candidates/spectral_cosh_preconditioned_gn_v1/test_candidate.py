from __future__ import annotations

import numpy as np

from candidate import route_for_start, solve_attempt, spectral_cosh_rhs
from generated_cases import near_miss_cases, positive_cases, rotation


def test_common_residual_scale_equivariance() -> None:
    H = np.diag([2.0, 7.0])
    g = np.array([3.0, -20.0])
    q, active, _ = spectral_cosh_rhs(H, g, 1.0)
    scaled, scaled_active, _ = spectral_cosh_rhs(9.0 * H, 9.0 * g, 1.0)
    assert active and scaled_active
    np.testing.assert_allclose(scaled, 9.0 * q, rtol=2e-13, atol=2e-13)


def test_orthogonal_variable_and_residual_invariance() -> None:
    case = positive_cases()[9]
    original = solve_attempt(case.residual, case.jacobian, case.start, route="spectral_cosh")
    Q = rotation(0.73)
    R = rotation(-0.41)

    def residual(y: np.ndarray) -> np.ndarray:
        return R @ case.residual(Q @ y)

    def jacobian(y: np.ndarray) -> np.ndarray:
        return R @ case.jacobian(Q @ y) @ Q

    transformed = solve_attempt(residual, jacobian, Q.T @ case.start, route="spectral_cosh")
    assert original.verified and transformed.verified
    np.testing.assert_allclose(Q @ transformed.endpoint, original.endpoint, rtol=1e-8, atol=1e-8)


def test_rank_deficiency_and_nonsmooth_fail_closed() -> None:
    def residual(x: np.ndarray) -> np.ndarray:
        return np.array([x[0] ** 2 - 1.0, 0.0])

    def jacobian(x: np.ndarray) -> np.ndarray:
        return np.array([[2.0 * x[0], 0.0], [0.0, 0.0]])

    rank = solve_attempt(residual, jacobian, np.array([3.0, 2.0]), route="spectral_cosh")
    assert rank.activations == 0
    assert rank.fallback_reason == "rank_deficient"

    branch = near_miss_cases()[-1]
    nonsmooth = solve_attempt(
        branch.residual, branch.jacobian, branch.start, route="spectral_cosh", smooth=False,
    )
    assert nonsmooth.activations == 0
    assert nonsmooth.fallback_reason == "unsupported_nonsmooth"
    assert not nonsmooth.verified


def test_inconsistent_near_miss_never_publishes() -> None:
    for case in near_miss_cases():
        result = solve_attempt(
            case.residual, case.jacobian, case.start, route="spectral_cosh", smooth=case.smooth,
        )
        assert not result.verified


def test_portfolio_keeps_exactly_75_percent_baseline() -> None:
    routes = [route_for_start(index) for index in range(100)]
    assert routes.count("baseline") == 75
    assert routes.count("spectral_cosh") == 25

