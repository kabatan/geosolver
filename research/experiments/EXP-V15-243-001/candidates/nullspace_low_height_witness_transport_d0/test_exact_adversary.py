"""Minimal exact-authority regression for Repair A."""

import sympy as sp

import exact_adversary as adversary


def test_nearly_dependent_float_claim_falls_back_exactly() -> None:
    x, y = adversary.X, adversary.Y
    first = x + y
    system = adversary._make(
        (first, first + sp.Rational(1, 10**12) * x),
        (x > -2, x < 2, y > -2, y < 2),
        ((-2.0, 2.0), (-2.0, 2.0)),
        (1e-6, -1e-6),
        adversary.TRANSFORMS["identity"],
    )
    result = adversary._run_repair(system, 17)
    assert result[3] is True
    assert result[4] == 1
    assert result[5] == 0
