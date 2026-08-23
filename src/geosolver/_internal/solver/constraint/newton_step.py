"""Newton-step computations for constraint projection."""

from collections.abc import Sequence

import numpy as np
from mpmath import mp

from geosolver._internal.solver.precision.type_guards.ensure_mpf import ensure_mpf


def compute_newton_step(jacobian: Sequence[Sequence[float]], residuals: Sequence[float]) -> list[float]:
    """Solve least-squares Newton step ``J * step = -r`` in float mode."""
    matrix = np.asarray(jacobian, dtype=float)
    rhs = -np.asarray(residuals, dtype=float)
    step, *_ = np.linalg.lstsq(matrix, rhs, rcond=None)
    return [float(value) for value in step]


def compute_newton_step_hp(jacobian_diag: Sequence[object], residuals: Sequence[object]) -> list[object]:
    """Compute diagonal Newton step in high precision with strict mpf inputs."""
    safe_diag = [ensure_mpf(value, context="jacobian_diag") for value in jacobian_diag]
    safe_residuals = [ensure_mpf(value, context="residuals") for value in residuals]
    return [(-residual / diagonal) if diagonal != mp.mpf("0") else mp.mpf("0") for diagonal, residual in zip(safe_diag, safe_residuals)]
