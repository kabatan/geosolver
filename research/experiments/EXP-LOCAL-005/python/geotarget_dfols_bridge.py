"""Narrow DFO-LS bridge for EXP-LOCAL-005.

The callback is an opaque Julia callable. Benchmark identities and reference
answers never cross this boundary.
"""

from __future__ import annotations

from collections.abc import Callable

import dfols
import numpy as np


DFOLS_VERSION = "1.6.5"


def package_version() -> str:
    return str(dfols.__version__)


def solve(
    residual_callback: Callable[[np.ndarray], object],
    initial: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    maxfun: int,
    rhobeg: float,
    rhoend: float,
    objective_tolerance: float,
):
    """Run one deterministic, bound-constrained DFO-LS local solve."""

    def objective(point: np.ndarray) -> np.ndarray:
        value = residual_callback(np.asarray(point, dtype=np.float64))
        return np.asarray(value, dtype=np.float64)

    parameters = {
        "init.random_initial_directions": False,
        "init.run_in_parallel": False,
        "restarts.use_restarts": False,
        "restarts.auto_detect": False,
        "model.abs_tol": objective_tolerance,
        "model.rel_tol": 0.0,
        "logging.save_diagnostic_info": False,
    }
    return dfols.solve(
        objective,
        np.asarray(initial, dtype=np.float64),
        bounds=(
            np.asarray(lower, dtype=np.float64),
            np.asarray(upper, dtype=np.float64),
        ),
        npt=len(initial) + 1,
        rhobeg=rhobeg,
        rhoend=rhoend,
        maxfun=maxfun,
        user_params=parameters,
        objfun_has_noise=False,
        scaling_within_bounds=False,
        do_logging=False,
        print_progress=False,
    )
