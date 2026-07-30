"""NumPy-only RHS patch for the frozen direct-Broyden/Ruiz seam."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TransformResult:
    residual: np.ndarray
    activated: bool
    reason: str
    direction_change: float
    maximum_coordinate: float


def transform_augmented_residual(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    *,
    reference_radius: float = 1.0,
    rank_rtol: float = float(np.sqrt(np.finfo(float).eps)),
) -> TransformResult:
    """Construct r' with J.T r' equal to the spectral-cosh normal RHS.

    Passing r' to the unchanged Ruiz/CPQR LM routine reuses its conditioning,
    damping, and SVD fallback.  Raw model prediction and endpoint replay remain
    based on the original residual in the caller.
    """
    J = np.asarray(jacobian, dtype=float)
    r = np.asarray(residual, dtype=float).reshape(-1)
    if J.ndim != 2 or r.shape != (J.shape[0],) or J.shape[1] == 0:
        return TransformResult(r.copy(), False, "shape", 0.0, 0.0)
    if not np.all(np.isfinite(J)) or not np.all(np.isfinite(r)):
        return TransformResult(r.copy(), False, "nonfinite", 0.0, 0.0)
    columns = J.shape[1]
    damping_value = max(float(damping), np.finfo(float).eps)
    H = J.T @ J + damping_value * np.eye(columns)
    g = J.T @ r
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(H)
    except np.linalg.LinAlgError:
        return TransformResult(r.copy(), False, "eigh", 0.0, 0.0)
    high = float(eigenvalues[-1])
    rank_floor = max(np.finfo(float).eps, float(rank_rtol) * high)
    if high <= 0.0 or float(eigenvalues[0]) <= rank_floor:
        return TransformResult(r.copy(), False, "rank", 0.0, 0.0)
    if columns > 1:
        relative_gaps = np.diff(eigenvalues) / np.maximum(eigenvalues[1:], rank_floor)
        if float(np.min(relative_gaps)) < 1e-9:
            return TransformResult(r.copy(), False, "eigenframe", 0.0, 0.0)

    radius = max(float(reference_radius), np.finfo(float).eps)
    coordinates = eigenvectors.T @ g
    scales = np.maximum(eigenvalues * radius, rank_floor * radius)
    z = coordinates / scales
    maximum_coordinate = float(np.max(np.abs(z)))
    if not np.all(np.isfinite(z)) or maximum_coordinate > 1e6:
        return TransformResult(r.copy(), False, "unstable_coordinate", 0.0, maximum_coordinate)
    if maximum_coordinate <= 0.25:
        return TransformResult(r.copy(), False, "small_coordinate", 0.0, maximum_coordinate)
    transformed = scales * np.sqrt(1.0 + z * z) * np.arcsinh(z)
    q = eigenvectors @ transformed
    change = float(np.linalg.norm(q - g)) / max(
        float(np.linalg.norm(g)), np.finfo(float).eps
    )
    if not np.all(np.isfinite(q)) or change <= 1e-5:
        return TransformResult(r.copy(), False, "negligible", change, maximum_coordinate)

    # Full column rank makes J.T surjective.  The minimum-norm lift changes
    # only the RHS seen by the already reviewed linear solver.
    try:
        lifted, *_ = np.linalg.lstsq(J.T, q, rcond=rank_rtol)
    except np.linalg.LinAlgError:
        return TransformResult(r.copy(), False, "lift", change, maximum_coordinate)
    defect = float(np.linalg.norm(J.T @ lifted - q)) / max(
        float(np.linalg.norm(q)), np.finfo(float).eps
    )
    if not np.all(np.isfinite(lifted)) or defect > 1e-8:
        return TransformResult(r.copy(), False, "lift_defect", change, maximum_coordinate)
    return TransformResult(
        np.asarray(lifted, dtype=float), True, "spectral_cosh", change, maximum_coordinate
    )

