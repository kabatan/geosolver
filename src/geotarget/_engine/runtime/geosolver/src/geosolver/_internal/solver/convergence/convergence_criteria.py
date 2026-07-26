"""Convergence criteria configuration."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


@dataclass(frozen=True)
class ConvergenceCriteria:
    """Thresholds for convergence checking.

    Args:
        residual_threshold: Maximum acceptable constraint residual norm.
        stationarity_threshold: Maximum acceptable stationarity norm (optimize).
        require_family_stability: Whether family stability is required.
    """

    residual_threshold: MPFloat
    stationarity_threshold: MPFloat | None = None
    require_family_stability: bool = False
