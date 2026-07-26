"""Backtracking line search at multiprecision."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.optimization.mp.mp_residual_vector import mp_residual_vector
from geosolver._internal.solver.optimization.mp.mp_residual_norm import mp_residual_norm
from geosolver._internal.solver.optimization.mp.mp_clamp_to_bounds import mp_clamp_to_bounds


def mp_backtracking_line_search(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    x: list[MPFloat],
    step: list[MPFloat],
    current_norm: MPFloat,
    bounds: list[tuple[MPFloat | None, MPFloat | None]] | None = None,
    max_steps: int = 10,
    shrink_factor: MPFloat | None = None,
    armijo_c: MPFloat | None = None,
    min_relative_decrease: MPFloat | None = None,
    min_alpha: MPFloat | None = None,
) -> tuple[list[MPFloat], MPFloat, bool]:
    """Backtracking line search to find step length reducing residual norm.

    Args:
        f: Constraint function.
        targets: Target values.
        x: Current point.
        step: Search direction.
        current_norm: Current residual norm.
        bounds: Box bounds.
        max_steps: Maximum backtracking iterations.
        shrink_factor: Step shrink factor per iteration (default 0.5).
        armijo_c: Armijo sufficient decrease parameter (default 1e-4).
        min_relative_decrease: Minimum relative decrease requirement.
        min_alpha: Minimum accepted alpha before declaring stall.

    Returns:
        (new_point, new_norm, improved) tuple.
    """
    if shrink_factor is None:
        shrink_factor = mp.mpf("0.5")
    if armijo_c is None:
        armijo_c = mp.mpf("1e-4")
    if min_relative_decrease is None:
        min_relative_decrease = mp.mpf("1e-12")
    if min_alpha is None:
        min_alpha = mp.power(mp.mpf("10"), -80)

    alpha = mp.mpf("1")
    base_scale = max(abs(current_norm), mp.power(mp.mpf("10"), -30))

    for _ in range(max_steps):
        candidate = [xi + alpha * si for xi, si in zip(x, step)]
        candidate = mp_clamp_to_bounds(candidate, bounds)
        r = mp_residual_vector(f=f, targets=targets, x=candidate)
        new_norm = mp_residual_norm(r)
        actual_decrease = current_norm - new_norm
        required_decrease = max(
            armijo_c * alpha * base_scale,
            min_relative_decrease * base_scale,
        )
        if (
            mp.isfinite(new_norm)
            and actual_decrease > mp.mpf("0")
            and actual_decrease >= required_decrease
        ):
            return candidate, new_norm, True
        alpha *= shrink_factor
        if alpha < min_alpha:
            break

    return list(x), current_norm, False
