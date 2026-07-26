"""Compute damped Gauss-Newton step via SVD at multiprecision."""

from __future__ import annotations

from mpmath import mp

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def compute_gauss_newton_step(
    *,
    jacobian: list[list[MPFloat]],
    residual: list[MPFloat],
    damping: MPFloat,
    n: int,
    m: int,
) -> list[MPFloat]:
    """Compute damped Gauss-Newton step: -(J^T J + damping*I)^-1 J^T r.

    Uses mpmath matrix operations for numerical stability.

    Args:
        jacobian: m-by-n Jacobian matrix.
        residual: m-element residual vector.
        damping: Levenberg-Marquardt damping parameter.
        n: Number of variables.
        m: Number of constraints.

    Returns:
        n-element step vector.
    """
    if n <= 0 or m <= 0:
        return [mp.mpf("0")] * max(0, int(n))

    j_mat = mp.matrix(jacobian)
    damping_mpf = mp.mpf(damping)

    try:
        u_mat, singular_values, v_mat = mp.svd_r(j_mat)
    except Exception:
        singular_values = []
        u_mat = None
        v_mat = None

    if u_mat is not None and v_mat is not None and singular_values:
        k = len(singular_values)
        projected: list[MPFloat] = []
        for index in range(k):
            component = mp.fsum(
                u_mat[row, index] * mp.mpf(residual[row])
                for row in range(m)
            )
            singular = mp.mpf(singular_values[index])
            denominator = singular * singular + damping_mpf
            if denominator == mp.mpf("0"):
                projected.append(mp.mpf("0"))
            else:
                projected.append(-(singular / denominator) * component)

        step: list[MPFloat] = []
        for column in range(n):
            value = mp.fsum(
                v_mat[index, column] * projected[index]
                for index in range(k)
            )
            step.append(value)
        return step

    jt = j_mat.T
    jtj = jt * j_mat
    for i in range(n):
        jtj[i, i] += damping_mpf
    jtr = jt * mp.matrix(residual)
    try:
        step_vec = mp.lu_solve(jtj, -jtr)
    except (ZeroDivisionError, ValueError, TypeError):
        return [mp.mpf("0")] * n
    return [step_vec[i] for i in range(n)]
