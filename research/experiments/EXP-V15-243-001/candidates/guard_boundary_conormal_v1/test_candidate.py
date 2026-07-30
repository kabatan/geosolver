from __future__ import annotations

from dataclasses import replace

import numpy as np

from candidate import Observation, Problem, solve_portfolio
from generated_cases import make_case


def _found(case, results, mapping=None):
    mapping = (lambda point: point) if mapping is None else mapping
    return frozenset(
        case.descriptor(mapping(result.point))
        for result in results
        if result.solved
    )


def test_three_independent_positive_families_gain_without_loss_or_false():
    for family in ("twin_circles", "cassini_ovals", "clipped_hyperbola"):
        case = make_case(family, "positive", 3)
        control = solve_portfolio(case.problem, case.starts, 44, False)
        candidate = solve_portfolio(case.problem, case.starts, 44, True)
        control_set, candidate_set = _found(case, control), _found(case, candidate)
        assert candidate_set == case.truth
        assert control_set < candidate_set
        assert all(result.callbacks == 44 for result in control + candidate)
        for left, right in zip(control[:3], candidate[:3]):
            assert left.solved == right.solved
            assert np.array_equal(left.point, right.point)


def test_inconsistent_and_strict_guard_near_miss_fail_closed():
    for role in ("inconsistent_negative", "semantic_near_miss"):
        case = make_case("twin_circles", role, 5)
        results = solve_portfolio(case.problem, case.starts, 44, True)
        assert _found(case, results) <= case.truth


def test_unsupported_guard_falls_back_without_endpoint_change():
    case = make_case("clipped_hyperbola", "positive", 2)
    original_observe = case.problem.observe

    def unsupported(point):
        observation = original_observe(point)
        return replace(observation, supported_strict_guards=False)

    problem = replace(case.problem, observe=unsupported)
    control = solve_portfolio(problem, case.starts, 44, False)
    candidate = solve_portfolio(problem, case.starts, 44, True)
    assert not candidate[3].activated
    assert candidate[3].solved == control[3].solved
    assert np.array_equal(candidate[3].point, control[3].point)


def test_signed_permutation_and_affine_scale_commute_with_discovery():
    case = make_case("cassini_ovals", "positive", 7)
    matrix = np.array([[0.0, 2.0], [-0.5, 0.0]])
    inverse = np.linalg.inv(matrix)

    def observe(transformed_point):
        point = matrix @ np.asarray(transformed_point, dtype=float)
        raw = case.problem.observe(point)
        return Observation(
            raw.residual,
            raw.jacobian @ matrix,
            raw.guard_margins,
            raw.guard_gradients @ matrix,
            raw.semantic_valid,
            raw.supported_strict_guards,
        )

    def replay(transformed_point):
        return case.problem.replay(matrix @ np.asarray(transformed_point, dtype=float))

    def in_bounds(transformed_point):
        return case.problem.in_bounds(matrix @ np.asarray(transformed_point, dtype=float))

    transformed = Problem(
        center=inverse @ case.problem.center,
        chart=inverse @ case.problem.chart,
        lower=np.full(2, -8.0),
        upper=np.full(2, 8.0),
        observe=observe,
        replay=replay,
        in_bounds=in_bounds,
    )
    starts = [inverse @ point for point in case.starts]
    original_results = solve_portfolio(case.problem, case.starts, 44, True)
    transformed_results = solve_portfolio(transformed, starts, 44, True)
    assert _found(case, original_results) == _found(
        case, transformed_results, lambda point: matrix @ point
    )


def test_residual_row_permutation_does_not_create_a_solution():
    case = make_case("clipped_hyperbola", "inconsistent_negative", 1)
    original_observe = case.problem.observe

    def permuted(point):
        raw = original_observe(point)
        return Observation(
            raw.residual[::-1],
            raw.jacobian[::-1],
            raw.guard_margins,
            raw.guard_gradients,
            raw.semantic_valid,
            raw.supported_strict_guards,
        )

    results = solve_portfolio(replace(case.problem, observe=permuted), case.starts, 44, True)
    assert not any(result.solved for result in results)
