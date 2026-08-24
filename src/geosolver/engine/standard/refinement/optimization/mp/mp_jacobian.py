"""Compute central finite-difference Jacobian at multiprecision."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.refinement.optimization.mp.mp_residual_vector import mp_residual_vector

_MIN_DELTA_DIGITS = 8
_DEFAULT_DELTA_HEADROOM_DIGITS = 12
_DPS_SAFETY_DIGITS = 8
_CENTRAL_DENOMINATOR = mp.mpf("2")


def _resolve_default_delta(
    *,
    value: MPFloat,
    target_dps: int,
    delta_digits: int | None,
) -> MPFloat:
    """Build a scale-aware central-difference step."""
    scale = max(mp.mpf("1"), abs(value))
    if delta_digits is None:
        exponent = int(target_dps) + _DEFAULT_DELTA_HEADROOM_DIGITS
    else:
        exponent = int(delta_digits)
    max_effective_exponent = max(_MIN_DELTA_DIGITS, int(mp.dps // 3))
    exponent = max(_MIN_DELTA_DIGITS, min(exponent, max_effective_exponent))
    return scale * mp.power(mp.mpf("10"), -exponent)


def compute_mp_jacobian(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    x: list[MPFloat],
    targets: list[MPFloat],
    delta: MPFloat | None = None,
    target_dps: int | None = None,
    delta_digits: int | None = None,
) -> list[list[MPFloat]]:
    """Compute central finite-difference Jacobian of the residual.

    Args:
        f: Constraint function.
        x: Current point (n variables).
        targets: Target values (m constraints).
        delta: FD step size. When omitted, a scale-aware step is derived.
        target_dps: Requested target dps used for default FD step sizing.
        delta_digits: Explicit decimal digits for FD step exponent.

    Returns:
        m-by-n Jacobian matrix (list of rows).
    """
    n = len(x)
    r0 = mp_residual_vector(f=f, targets=targets, x=x)
    m = len(r0)

    jacobian: list[list[MPFloat]] = [[mp.mpf("0")] * n for _ in range(m)]
    effective_target_dps = int(mp.dps if target_dps is None else target_dps)
    for j in range(n):
        step = (
            _resolve_default_delta(
                value=x[j],
                target_dps=effective_target_dps,
                delta_digits=delta_digits,
            )
            if delta is None
            else mp.mpf(delta)
        )
        x_pert = list(x)
        x_pert[j] = x[j] + step
        r_plus = mp_residual_vector(f=f, targets=targets, x=x_pert)
        x_pert[j] = x[j] - step
        r_minus = mp_residual_vector(f=f, targets=targets, x=x_pert)
        inv_delta = mp.mpf("1") / (_CENTRAL_DENOMINATOR * step)
        for i in range(m):
            jacobian[i][j] = (r_plus[i] - r_minus[i]) * inv_delta
    return jacobian
