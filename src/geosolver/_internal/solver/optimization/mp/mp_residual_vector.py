"""Compute MP constraint residual vector r_i = f_i(x) - target_i."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def mp_residual_vector(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    x: list[MPFloat],
) -> list[MPFloat]:
    """Compute constraint residual vector at multiprecision.

    Args:
        f: Constraint function returning m values.
        targets: Target values for each constraint.
        x: Current point (n variables).

    Returns:
        List of residuals r_i = f_i(x) - target_i.
    """
    values = f(list(x))
    return [val - tgt for val, tgt in zip(values, targets)]
