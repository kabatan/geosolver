"""Least-squares optimizer wrapper."""

from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

import numpy as np
from mpmath import mp
from scipy.optimize import least_squares

from geosolver.engine.standard.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)


def _mp_value_to_float(value: object) -> float:
    if isinstance(value, float):
        converted = boundary_float_to_mpf(value, origin=BoundaryOrigin.RESIDUAL_NORM)
    else:
        converted = ensure_mpf(value, context="residual")
    return float(converted)


def _evaluate_residual(
    values: np.ndarray,
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
    high_precision: bool,
) -> np.ndarray:
    if high_precision:
        hp_values = [
            boundary_float_to_mpf(float(value), origin=BoundaryOrigin.SCIPY_OPTIMIZE)
            for value in values
        ]
        residuals = [_mp_value_to_float(value) for value in residual_fn(hp_values)]
    else:
        residuals = [float(value) for value in residual_fn(values.tolist())]
    return np.asarray(residuals, dtype=float)


def _evaluate_residual_mpf(
    values: Sequence[Any],
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
) -> list[Any]:
    residuals_raw = residual_fn(list(values))
    return [ensure_mpf(value, context="residual") for value in residuals_raw]


def _least_squares_objective_mpf(
    values: Sequence[Any],
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
) -> Any:
    residuals = _evaluate_residual_mpf(values, residual_fn)
    return mp.fsum([value * value for value in residuals])


def _finite_diff_gradient_mpf(
    values: list[Any],
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
    step: Any,
) -> list[Any]:
    gradient: list[Any] = []
    for index in range(len(values)):
        left = list(values)
        right = list(values)
        left[index] = values[index] - step
        right[index] = values[index] + step
        f_left = _least_squares_objective_mpf(left, residual_fn)
        f_right = _least_squares_objective_mpf(right, residual_fn)
        gradient.append((f_right - f_left) / (mp.mpf("2") * step))
    return gradient


def _run_mpmath_least_squares(
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
    initial: Sequence[object],
) -> list[object]:
    values = [ensure_mpf(value, context="initial") for value in initial]
    if not values:
        return []

    grad_step = mp.mpf("1e-8")
    improve_tol = mp.mpf("1e-20")
    residual_tol = mp.mpf("1e-20")
    learning_rate = mp.mpf("0.25")
    max_iterations = 64

    objective_value = _least_squares_objective_mpf(values, residual_fn)
    for _ in range(max_iterations):
        if objective_value <= residual_tol:
            break

        gradient = _finite_diff_gradient_mpf(values, residual_fn, grad_step)
        grad_norm = mp.sqrt(mp.fsum([entry * entry for entry in gradient]))
        if not mp.isfinite(grad_norm) or grad_norm <= improve_tol:
            break

        step_size = learning_rate
        updated = list(values)
        updated_objective = objective_value
        improved = False
        for _ in range(12):
            trial = [
                value - step_size * grad / (grad_norm + mp.mpf("1e-30"))
                for value, grad in zip(values, gradient)
            ]
            trial_objective = _least_squares_objective_mpf(trial, residual_fn)
            if mp.isfinite(trial_objective) and trial_objective + improve_tol < objective_value:
                updated = trial
                updated_objective = trial_objective
                improved = True
                break
            step_size *= mp.mpf("0.5")

        values = updated
        if not improved:
            break
        if objective_value - updated_objective <= improve_tol:
            objective_value = updated_objective
            break
        objective_value = updated_objective

    return [ensure_mpf(value, context="result") for value in values]


def run_least_squares(
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
    initial: Sequence[object],
    *,
    high_precision: bool = False,
) -> list[object]:
    """Run least-squares optimization and return optimized point."""
    if high_precision:
        return _run_mpmath_least_squares(residual_fn, initial)

    start = np.asarray(initial, dtype=float)
    result = least_squares(partial(_evaluate_residual, residual_fn=residual_fn, high_precision=False), start)
    return [float(value) for value in result.x]
