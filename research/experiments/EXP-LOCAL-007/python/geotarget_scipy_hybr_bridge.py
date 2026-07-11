"""Narrow SciPy MINPACK-HYBRD bridge for EXP-LOCAL-007.

The Julia residual callback is the only problem-dependent object crossing this
boundary. Benchmark identities, saved starts, and reference answers remain in
the outer runner.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import scipy
from scipy.optimize import root


SCIPY_VERSION = "1.18.0"


def package_version() -> str:
    return str(scipy.__version__)


def solve(
    residual_callback: Callable[[np.ndarray], object],
    initial: np.ndarray,
    *,
    maxfev: int,
    xtol: float,
    factor: float,
):
    """Run one square-system modified Powell hybrid solve."""

    def residual(point: np.ndarray) -> np.ndarray:
        value = residual_callback(np.asarray(point, dtype=np.float64))
        return np.asarray(value, dtype=np.float64)

    return root(
        residual,
        np.asarray(initial, dtype=np.float64),
        method="hybr",
        options={
            "maxfev": int(maxfev),
            "xtol": float(xtol),
            "factor": float(factor),
        },
    )
