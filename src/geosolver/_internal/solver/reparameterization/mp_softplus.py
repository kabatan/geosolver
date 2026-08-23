"""MP-safe softplus and inverse softplus functions."""

from __future__ import annotations

import mpmath as mp

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def mp_softplus(u: MPFloat) -> MPFloat:
    """Compute softplus(u) = log(1 + exp(u)) in mpmath."""
    return mp.log(mp.mpf(1) + mp.exp(u))


def mp_softplus_inverse(x: MPFloat) -> MPFloat:
    """Compute inverse softplus: u = log(exp(x) - 1)."""
    return mp.log(mp.exp(x) - mp.mpf(1))
