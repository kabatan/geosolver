"""Check convergence for optimize-mode pipelines."""

from __future__ import annotations

from geosolver._internal.solver.convergence.convergence_criteria import ConvergenceCriteria
from geosolver._internal.solver.convergence.convergence_status import ConvergenceStatus
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.public.hp_residual_result import HPResidualResult


def check_optimize_convergence(
    *,
    residual_result: HPResidualResult,
    stationarity_norm: MPFloat,
    criteria: ConvergenceCriteria,
) -> ConvergenceStatus:
    """Check whether an optimize result meets convergence criteria.

    Args:
        residual_result: HP residual evaluation result.
        stationarity_norm: KKT stationarity norm.
        criteria: Convergence thresholds.

    Returns:
        ConvergenceStatus with per-criterion and overall results.
    """
    constraint_converged = (
        residual_result.is_finite
        and residual_result.residual_norm <= criteria.residual_threshold
    )

    stationarity_converged: bool | None = None
    if criteria.stationarity_threshold is not None:
        stationarity_converged = stationarity_norm <= criteria.stationarity_threshold

    overall = constraint_converged
    if stationarity_converged is not None:
        overall = overall and stationarity_converged

    return ConvergenceStatus(
        constraint_residual=residual_result.residual_norm,
        constraint_converged=constraint_converged,
        stationarity_norm=stationarity_norm,
        stationarity_converged=stationarity_converged,
        overall_converged=overall,
    )
