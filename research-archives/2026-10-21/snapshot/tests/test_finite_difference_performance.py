from __future__ import annotations

from mpmath import mp

from geosolver.engine.standard.refinement.finite_difference_jacobian import (
    compute_finite_difference_jacobian,
)


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
