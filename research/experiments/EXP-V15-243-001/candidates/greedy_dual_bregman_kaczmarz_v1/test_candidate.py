from __future__ import annotations

import numpy as np

from candidate import Observation, Problem, bregman_lane, solve_portfolio
from generated_cases import make_case, transformed_case


def test_budget_and_insurance_are_exact() -> None:
    case = make_case("sparse_chain", "positive", 2)
    control = solve_portfolio(case.problem, case.starts, 18, 2, False)
    candidate = solve_portfolio(case.problem, case.starts, 18, 2, True)
    assert sum(x.callbacks for x in control) == sum(x.callbacks for x in candidate) == 72
    for ordinal in range(3):
        assert np.array_equal(control[ordinal].point, candidate[ordinal].point)
        assert control[ordinal].solved == candidate[ordinal].solved


def test_unbounded_problem_falls_back_byte_identically() -> None:
    def observe(x: np.ndarray) -> Observation:
        return Observation(np.array([x[0] - 0.25]), np.array([[1.0]]))

    problem = Problem(
        np.array([-np.inf]),
        np.array([np.inf]),
        np.ones(1),
        observe,
        lambda x: abs(x[0] - 0.25) < 1e-10,
    )
    from candidate import baseline_lane

    control = baseline_lane(problem, np.array([0.8]), 12)
    candidate = bregman_lane(problem, np.array([0.8]), 12, 0)
    assert candidate.status == "fallback_ineligible"
    assert np.array_equal(control.point, candidate.point)
    assert control.solved == candidate.solved


def test_opaque_observation_fails_closed() -> None:
    def observe(_: np.ndarray) -> Observation:
        return Observation(np.array([np.nan]), np.array([[np.nan]]), False)

    problem = Problem(
        np.array([-1.0]), np.array([1.0]), np.ones(1), observe, lambda _: False
    )
    result = bregman_lane(problem, np.array([0.0]), 9, 0)
    assert not result.solved
    assert not result.activated
    assert result.callbacks == 9


def test_negative_and_near_miss_never_emit() -> None:
    for family in ("sparse_chain", "dense_coupled", "strict_bound_scale"):
        for role in ("negative", "near_miss"):
            case = make_case(family, role, 1)
            result = solve_portfolio(case.problem, case.starts, 22, 1, True)
            assert not any(x.solved for x in result)


def test_permutation_and_scale_preserve_solved_set() -> None:
    case = make_case("dense_coupled", "positive", 3)
    original = solve_portfolio(case.problem, case.starts, 22, 3, True)
    n = case.starts[0].size
    m = case.problem.observe(case.starts[0]).residual.size
    cp = np.eye(n)[::-1]
    rp = np.eye(m)[np.roll(np.arange(m), 1)]
    transformed = transformed_case(case, cp, rp, np.linspace(-3.0, 5.0, m))
    changed = solve_portfolio(transformed.problem, transformed.starts, 22, 3, True)
    assert any(x.solved for x in original) == any(x.solved for x in changed)
