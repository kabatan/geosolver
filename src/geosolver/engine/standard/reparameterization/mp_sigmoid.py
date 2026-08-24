"""MP-safe sigmoid and inverse sigmoid functions."""

from __future__ import annotations

import mpmath as mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


def mp_sigmoid(u: MPFloat) -> MPFloat:
    """Compute sigmoid(u) = 1 / (1 + exp(-u)) in mpmath."""
    return mp.mpf(1) / (mp.mpf(1) + mp.exp(-u))


def mp_sigmoid_inverse(x: MPFloat) -> MPFloat:
    """Compute inverse sigmoid: u = log(x / (1 - x))."""
    return mp.log(x / (mp.mpf(1) - x))
