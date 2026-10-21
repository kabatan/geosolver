"""Jacobian contracts and numerical regressions."""

from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.refinement.finite_difference_jacobian import (
    compute_finite_difference_jacobian,
)


def test_jacobian_base_evaluation_uses_requested_precision():
    observed = []

    def residual(point, dps):
        observed.append(mp.dps)
        return [point[0] ** 2]

    with mp.workdps(15):
        jacobian = compute_finite_difference_jacobian(
            point=[mp.mpf(2)],
            dps=100,
            residual_fn=residual,
        )
    assert min(observed) == 100
    with mp.workdps(100):
        assert abs(jacobian[0][0] - 4) < mp.mpf("1e-65")


@pytest.mark.parametrize("sign", [-1, 1])
def test_one_sided_jacobian_at_domain_boundary(sign):
    def residual(point, dps):
        x = point[0]
        return None if sign * x < 0 else [3 * x + x * x]

    jacobian = compute_finite_difference_jacobian(
        point=[mp.mpf(0)],
        dps=100,
        residual_fn=residual,
    )
    assert jacobian is not None
    with mp.workdps(100):
        assert abs(jacobian[0][0] - 3) < mp.mpf("1e-65")


def test_rank_selection_is_invariant_to_equation_and_coordinate_units():
    from geosolver.engine.standard.refinement.mpmath_refiner import (
        _select_rank_revealing_subsystem,
    )

    with mp.workdps(100):
        matrix = [[mp.mpf("1e-80"), 0], [0, mp.mpf("1e80")]]
    rows, columns = _select_rank_revealing_subsystem(matrix, dps=100)
    assert set(rows) == set(columns) == {0, 1}


def test_sparse_differences_reduce_evaluations_without_changing_derivatives():
    calls = []

    def residual(point, dps):
        calls.append(tuple(point))
        return [value * value for value in point]

    point = [mp.mpf(i + 1) for i in range(8)]
    grouped = compute_finite_difference_jacobian(
        point=point,
        dps=100,
        residual_fn=residual,
        row_dependencies=tuple(frozenset((i,)) for i in range(8)),
    )
    assert len(calls) == 3
    calls.clear()
    dense = compute_finite_difference_jacobian(point=point, dps=100, residual_fn=residual)
    assert len(calls) == 17
    assert grouped == dense


def test_sparse_differences_fall_back_at_one_sided_boundaries():
    def residual(point, dps):
        return [3 * point[0], 5 * point[1]] if point[0] >= 0 else None

    result = compute_finite_difference_jacobian(
        point=[mp.mpf(0), mp.mpf(1)],
        dps=100,
        residual_fn=residual,
        row_dependencies=(frozenset((0,)), frozenset((1,))),
    )
    assert result is not None
    with mp.workdps(100):
        assert abs(result[0][0] - 3) < mp.mpf("1e-65")
        assert abs(result[1][1] - 5) < mp.mpf("1e-65")
        assert result[0][1] == result[1][0] == 0


@pytest.mark.parametrize("move_first", [False, True])
def test_jacobian_reuse_invalidates_when_the_point_changes(monkeypatch, move_first):
    from geosolver.engine.standard.refinement import mpmath_refiner as module
    from geosolver.engine.standard.refinement.refiner_config import RefinerConfig

    jacobian_points, trial_count = [], 0

    def jacobian(*, point, **kwargs):
        jacobian_points.append(tuple(point))
        return [[mp.mpf(1)]]

    def trial(*, point, **kwargs):
        nonlocal trial_count
        trial_count += 1
        if move_first and trial_count == 1:
            return [mp.mpf(1)], [mp.mpf(1)], True
        return point, [point[0]], False

    monkeypatch.setattr(module, "compute_finite_difference_jacobian", jacobian)
    monkeypatch.setattr(module, "run_line_search", trial)
    monkeypatch.setattr(module, "_problem_contains_call", lambda spec, name: False)
    refiner = module.MpmathRefiner(RefinerConfig(line_search_failure_limit=3))
    refiner._run_stage(
        bundle=SimpleNamespace(spec=None),
        evaluator=None,
        start_point=[mp.mpf(2)],
        bounds=((None, None),),
        dps=100,
        target_residual=mp.mpf("1e-50"),
        preserve_hard_feasibility=False,
        residual_fn=lambda point, dps: list(point),
    )
    assert jacobian_points == ([(mp.mpf(2),), (mp.mpf(1),)] if move_first else [(mp.mpf(2),)])


def test_finite_difference_reuses_supplied_base_residual() -> None:
    calls = 0

    def residual(point: list[mp.mpf], _dps: int) -> list[mp.mpf]:
        nonlocal calls
        calls += 1
        return [point[0] ** 2 + point[1]]

    point = [mp.mpf("2"), mp.mpf("3")]
    base = residual(point, 40)
    calls = 0
    jacobian = compute_finite_difference_jacobian(
        point=point,
        dps=40,
        residual_fn=residual,
        base_residual=base,
    )

    assert jacobian is not None
    assert calls == 2 * len(point)
