"""Structured convergence status for solve/optimize results."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


@dataclass(frozen=True)
class ConvergenceStatus:
    """Result of convergence checking.

    Args:
        constraint_residual: L2 norm of constraint residual.
        constraint_converged: Whether residual is below threshold.
        stationarity_norm: KKT stationarity norm (optimize only).
        stationarity_converged: Whether stationarity is below threshold.
        family_stable: Whether solution family set is stable.
        overall_converged: Whether all active criteria are met.
    """

    constraint_residual: MPFloat
    constraint_converged: bool
    stationarity_norm: MPFloat | None = None
    stationarity_converged: bool | None = None
    family_stable: bool | None = None
    overall_converged: bool = False
