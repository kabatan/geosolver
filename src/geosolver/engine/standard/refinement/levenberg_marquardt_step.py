"""Levenberg-Marquardt step solver."""

from __future__ import annotations

from collections.abc import Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


def compute_levenberg_marquardt_step(
    *,
    jacobian: Sequence[Sequence[MPFloat]],
    residual_vector: Sequence[MPFloat],
    damping: MPFloat,
) -> list[MPFloat]:
    """Solve LM linear system and return update vector."""
    rows = len(jacobian)
    cols = len(jacobian[0]) if rows else 0
    if rows == 0 or cols == 0:
        return []
    j_mat = mp.matrix(jacobian)
    jt = j_mat.T
    system = jt * j_mat
    for index in range(cols):
        system[index, index] += damping
    rhs = -(jt * mp.matrix(residual_vector))
    try:
        solution = mp.lu_solve(system, rhs)
    except Exception:
        return [mp.mpf("0") for _ in range(cols)]
    return [mp.mpf(solution[index]) for index in range(cols)]

