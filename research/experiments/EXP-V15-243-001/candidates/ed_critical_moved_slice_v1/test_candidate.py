from __future__ import annotations

import numpy as np

from candidate import solve_portfolio
from generated_cases import make_case, make_isolated_counter, make_opaque_counter, transformed_case


def test_exact_budget_and_75_percent_insurance() -> None:
    case = make_case("curved_circle", "positive", 2)
    control = solve_portfolio(case.problem, case.starts, 36, False)
    candidate = solve_portfolio(case.problem, case.starts, 36, True)
    assert sum(x.callbacks for x in control) == sum(x.callbacks for x in candidate) == 144
    for ordinal in range(3):
        assert np.array_equal(control[ordinal].point, candidate[ordinal].point)
        assert control[ordinal].solved == candidate[ordinal].solved


def test_negative_and_near_miss_never_emit() -> None:
    for family in ("curved_circle", "disconnected_ovals", "scaled_space_curve", "nonpolynomial_sheet"):
        for role in ("negative", "near_miss"):
            case = make_case(family, role, 1)
            assert not any(x.solved for x in solve_portfolio(case.problem, case.starts, 44, True))


def test_isolated_and_opaque_fallbacks() -> None:
    isolated = make_isolated_counter(0)
    opaque = make_opaque_counter(0)
    isolated_result = solve_portfolio(isolated.problem, isolated.starts, 30, True)
    opaque_result = solve_portfolio(opaque.problem, opaque.starts, 30, True)
    opaque_control = solve_portfolio(opaque.problem, opaque.starts, 30, False)
    assert isolated_result[3].status in {"fallback_isolated", "fallback_no_manifold_anchor"}
    assert opaque_result[3].status == "fallback_opaque"
    assert np.array_equal(opaque_control[3].point, opaque_result[3].point)
    assert opaque_control[3].solved == opaque_result[3].solved
    assert not any(x.solved for x in isolated_result + opaque_result)


def test_coordinate_residual_transform_preserves_solved_set() -> None:
    case = make_case("scaled_space_curve", "positive", 3)
    original = solve_portfolio(case.problem, case.starts, 44, True)
    t = np.array([[0.0, -2.0, 0.0], [0.4, 0.0, 0.0], [0.0, 0.0, -3.0]])
    row_map = np.array([[0.0, -4.0], [0.25, 0.0]])
    changed = transformed_case(case, t, row_map)
    transformed = solve_portfolio(changed.problem, changed.starts, 44, True)
    assert any(x.solved for x in original) == any(x.solved for x in transformed)


def test_candidate_never_observes_labels_or_truth() -> None:
    import inspect
    import candidate

    source = inspect.getsource(candidate)
    assert "case_id" not in source
    assert "target_count" not in source
    assert "offline_truth" not in source
