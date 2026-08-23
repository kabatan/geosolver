"""Check convergence for solve-mode pipelines."""

from __future__ import annotations

from geosolver._internal.solver.convergence.convergence_criteria import ConvergenceCriteria
from geosolver._internal.solver.convergence.convergence_status import ConvergenceStatus
from geosolver._internal.solver.public.hp_residual_result import HPResidualResult


def check_solve_convergence(
    *,
    residual_result: HPResidualResult,
    criteria: ConvergenceCriteria,
    family_stable: bool | None = None,
) -> ConvergenceStatus:
    """Check whether a solve result meets convergence criteria.

    Args:
        residual_result: HP residual evaluation result.
        criteria: Convergence thresholds.
        family_stable: Whether solution family set is stable (find_all).

    Returns:
        ConvergenceStatus with per-criterion and overall results.
    """
    constraint_converged = (
        residual_result.is_finite
        and residual_result.residual_norm <= criteria.residual_threshold
    )

    overall = constraint_converged
    if criteria.require_family_stability and family_stable is not None:
        overall = overall and family_stable

    return ConvergenceStatus(
        constraint_residual=residual_result.residual_norm,
        constraint_converged=constraint_converged,
        family_stable=family_stable,
        overall_converged=overall,
    )
