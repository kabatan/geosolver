"""Narrow SciPy TRF bridge for EXP-LOCAL-006.

Both callables remain opaque Julia functions. Benchmark identities, routing
labels, and reference answers never cross this boundary.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import scipy
from scipy.optimize import least_squares


SCIPY_VERSION = "1.18.0"


def package_version() -> str:
    return str(scipy.__version__)


def solve(
    residual_callback: Callable[[np.ndarray], object],
    jacobian_callback: Callable[[np.ndarray], object],
    initial: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    max_nfev: int,
    ftol: float,
    xtol: float,
    gtol: float,
):
    """Run one dense, bound-constrained TRF least-squares solve."""

    def residual(point: np.ndarray) -> np.ndarray:
        value = residual_callback(np.asarray(point, dtype=np.float64))
        return np.asarray(value, dtype=np.float64)

    def jacobian(point: np.ndarray) -> np.ndarray:
        value = jacobian_callback(np.asarray(point, dtype=np.float64))
        return np.asarray(value, dtype=np.float64)

    return least_squares(
        residual,
        np.asarray(initial, dtype=np.float64),
        jac=jacobian,
        bounds=(
            np.asarray(lower, dtype=np.float64),
            np.asarray(upper, dtype=np.float64),
        ),
        method="trf",
        tr_solver="exact",
        ftol=ftol,
        xtol=xtol,
        gtol=gtol,
        x_scale=1.0,
        loss="linear",
        max_nfev=max_nfev,
        verbose=0,
    )
