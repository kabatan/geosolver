"""QR/SVD-based damped least-squares helpers."""

from __future__ import annotations

from collections.abc import Sequence

from mpmath import mp
import numpy as np

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def compute_qr_svd_damped_step(
    *,
    jacobian: Sequence[Sequence[MPFloat]],
    residual_vector: Sequence[MPFloat],
    damping: MPFloat,
) -> list[MPFloat]:
    """Return damped least-squares step without forming normal equations."""

    rows = len(jacobian)
    cols = len(jacobian[0]) if rows else 0
    if rows == 0 or cols == 0:
        return []
    j_array = np.array([[float(value) for value in row] for row in jacobian], dtype=float)
    residual = np.array([float(value) for value in residual_vector], dtype=float)
    if not np.all(np.isfinite(j_array)) or not np.all(np.isfinite(residual)):
        return [mp.mpf("0") for _ in range(cols)]
    damping_float = max(0.0, float(damping))
    if damping_float > 0.0:
        augmented_a = np.vstack([j_array, np.sqrt(damping_float) * np.eye(cols)])
        augmented_b = np.concatenate([-residual, np.zeros(cols)])
    else:
        augmented_a = j_array
        augmented_b = -residual
    try:
        step, *_ = np.linalg.lstsq(augmented_a, augmented_b, rcond=None)
    except np.linalg.LinAlgError:
        try:
            u_mat, singular_values, vt_mat = np.linalg.svd(augmented_a, full_matrices=False)
            cutoff = np.finfo(float).eps * max(augmented_a.shape) * singular_values[0]
            inverse = np.array(
                [0.0 if value <= cutoff else 1.0 / value for value in singular_values],
                dtype=float,
            )
            step = vt_mat.T @ (inverse * (u_mat.T @ augmented_b))
        except np.linalg.LinAlgError:
            return [mp.mpf("0") for _ in range(cols)]
    if not np.all(np.isfinite(step)):
        return [mp.mpf("0") for _ in range(cols)]
    return [mp.mpf(str(value)) for value in step]
