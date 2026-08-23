"""Convergence checks for constraint projection."""

import math
from collections.abc import Sequence


def residual_norm(residuals: Sequence[float]) -> float:
    """Return L2 norm of residual vector."""
    if not residuals:
        return 0.0
    return math.sqrt(sum(v * v for v in residuals))


def is_converged(residuals: Sequence[float], tolerance: float) -> bool:
    """Check if residual norm is below tolerance."""
    return residual_norm(residuals) <= tolerance
