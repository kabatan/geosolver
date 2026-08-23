"""High-precision Jacobian helper compatible with legacy optimize implementation."""

from __future__ import annotations

from typing import Any, Callable

from geosolver._internal.solver.precision.adaptive_delta import _adaptive_delta
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf


def _to_mpf_for_jacobian(val: Any, *, dps: int) -> Any:
    from mpmath import mpf

    _ = dps
    if isinstance(val, mpf):
        return val
    return strict_to_mpf(val, context="constraint.jacobian_hp")


def compute_jacobian_hp(
    f: Callable[[list[Any]], list[Any]],
    x: list[Any],
    n: int,
    m: int,
    delta: Any,
    precision: int | None = None,
) -> list[list[Any]]:
    """Compute Jacobian columns using central differences (legacy-compatible)."""
    from mpmath import mp, mpf

    use_high_order = precision is not None and precision >= 80
    if precision is not None:
        relative_delta = _adaptive_delta(precision)
    else:
        relative_delta = delta if delta is not None else mpf(10) ** (-20)

    jacobian_columns: list[list[Any]] = []
    for j in range(n):
        x_j_abs = abs(_to_mpf_for_jacobian(x[j], dps=mp.dps))
        if x_j_abs < 1:
            x_j_abs = mpf(1)
        delta_j = x_j_abs * relative_delta

        try:
            if use_high_order:
                x_m2 = x[:]
                x_m1 = x[:]
                x_p1 = x[:]
                x_p2 = x[:]
                x_m2[j] = _to_mpf_for_jacobian(x_m2[j], dps=mp.dps) - 2 * delta_j
                x_m1[j] = _to_mpf_for_jacobian(x_m1[j], dps=mp.dps) - delta_j
                x_p1[j] = _to_mpf_for_jacobian(x_p1[j], dps=mp.dps) + delta_j
                x_p2[j] = _to_mpf_for_jacobian(x_p2[j], dps=mp.dps) + 2 * delta_j
                f_m2 = f(x_m2)
                f_m1 = f(x_m1)
                f_p1 = f(x_p1)
                f_p2 = f(x_p2)
                column = []
                for k in range(m):
                    fm2 = _to_mpf_for_jacobian(f_m2[k], dps=mp.dps)
                    fm1 = _to_mpf_for_jacobian(f_m1[k], dps=mp.dps)
                    fp1 = _to_mpf_for_jacobian(f_p1[k], dps=mp.dps)
                    fp2 = _to_mpf_for_jacobian(f_p2[k], dps=mp.dps)
                    column.append((fm2 - 8 * fm1 + 8 * fp1 - fp2) / (12 * delta_j))
            else:
                x_plus = x[:]
                x_plus[j] = _to_mpf_for_jacobian(x_plus[j], dps=mp.dps) + delta_j
                x_minus = x[:]
                x_minus[j] = _to_mpf_for_jacobian(x_minus[j], dps=mp.dps) - delta_j
                f_plus = f(x_plus)
                f_minus = f(x_minus)
                column = [
                    (
                        _to_mpf_for_jacobian(f_plus[k], dps=mp.dps)
                        - _to_mpf_for_jacobian(f_minus[k], dps=mp.dps)
                    )
                    / (2 * delta_j)
                    for k in range(m)
                ]
        except Exception:
            column = [mpf(0)] * m
        jacobian_columns.append(column)

    return jacobian_columns
