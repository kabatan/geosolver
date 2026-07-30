from __future__ import annotations

import numpy as np

from cached_sparsity import (
    cached_colored_forward_difference,
    cache_info,
    clear_cache,
    compile_plan,
)


SMOOTH = {
    "variables": {"names": ["x", "y", "z", "w"]},
    "construction": [
        {"name": "A", "expr": "Point(x, y)"},
        {"name": "B", "expr": "Point(z, w)"},
    ],
    "constraints": [
        {"def": "x * x + y", "value": 0},
        {"def": "z + w * w", "value": 0},
    ],
    "guards": [],
}


def _evaluate(point: np.ndarray) -> np.ndarray:
    x, y, z, w = point
    return np.asarray([x * x + y, z + w * w])


def test_cached_plan_activates_only_for_material_saving() -> None:
    clear_cache()
    first, first_hit = compile_plan(SMOOTH)
    second, second_hit = compile_plan(SMOOTH)
    assert first == second
    assert not first_hit and second_hit
    assert first.eligible
    assert first.direction_reduction_fraction == 0.5
    assert len(first.colors) == 2
    assert cache_info().misses == 1
    assert cache_info().hits == 1


def test_colored_jacobian_uses_two_instead_of_four_directions() -> None:
    point = np.asarray([2.0, 3.0, 4.0, 5.0])
    step = np.full(4, 1e-7)
    result = cached_colored_forward_difference(
        SMOOTH, _evaluate, point, _evaluate(point), step
    )
    expected = np.asarray([[4.0000001, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 10.0000001]])
    assert result.mode == "colored"
    assert result.direction_evaluations == 2
    assert result.dense_direction_evaluations == 4
    assert np.allclose(result.jacobian, expected, rtol=1e-7, atol=1e-8)


def test_nondifferentiable_source_falls_back_to_unchanged_dense_fd() -> None:
    document = {**SMOOTH, "constraints": [{"def": "Abs(x)", "value": 0}]}
    point = np.asarray([2.0, 3.0, 4.0, 5.0])
    current = np.asarray([2.0])

    def evaluate(value):
        return np.asarray([abs(value[0])])

    result = cached_colored_forward_difference(
        document, evaluate, point, current, np.full(4, 1e-7)
    )
    assert result.mode == "dense-fallback"
    assert result.direction_evaluations == 4
    assert "non-differentiable" in str(result.fallback_reason)


def test_branch_trace_change_discards_colored_probe_and_replays_dense() -> None:
    point = np.asarray([2.0, 3.0, 4.0, 5.0])
    step = np.full(4, 1e-7)

    def trace(value):
        return tuple(value > point)

    result = cached_colored_forward_difference(
        SMOOTH, _evaluate, point, _evaluate(point), step, trace=trace
    )
    assert result.mode == "dense-fallback"
    assert result.dense_direction_evaluations == 4
    assert result.direction_evaluations == 5
    assert "branch trace changed" in str(result.fallback_reason)


def test_dense_dependency_below_saving_gate_falls_back() -> None:
    document = {
        "variables": {"names": ["x", "y", "z"]},
        "construction": [],
        "constraints": [{"def": "x + y + z", "value": 0}],
        "guards": [],
    }
    plan, _hit = compile_plan(document)
    assert not plan.eligible
    assert plan.direction_reduction_fraction == 0.0
    assert "below 20 percent" in str(plan.fallback_reason)

