"""Build convergence criteria from precision and mode."""

from __future__ import annotations

from mpmath import mp

from geosolver._internal.solver.convergence.convergence_criteria import ConvergenceCriteria
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def build_convergence_criteria(
    *,
    precision: int,
    mode: str,
) -> ConvergenceCriteria:
    """Build convergence criteria appropriate for the given precision and mode.

    Args:
        precision: Working precision in decimal digits.
        mode: One of "solve", "optimize", "find_all".

    Returns:
        ConvergenceCriteria with appropriate thresholds.
    """
    residual_threshold: MPFloat = mp.power(mp.mpf("10"), -precision)

    stationarity_threshold: MPFloat | None = None
    if mode == "optimize":
        stationarity_threshold = mp.power(mp.mpf("10"), -precision)

    require_family_stability = mode == "find_all"

    return ConvergenceCriteria(
        residual_threshold=residual_threshold,
        stationarity_threshold=stationarity_threshold,
        require_family_stability=require_family_stability,
    )
