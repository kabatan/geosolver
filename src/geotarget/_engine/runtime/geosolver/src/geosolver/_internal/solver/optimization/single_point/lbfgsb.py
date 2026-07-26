"""L-BFGS-B optimizer wrapper."""

from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

import numpy as np
from mpmath import mp
from scipy.optimize import minimize

from geosolver._internal.solver.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)


def _evaluate_objective(
    values: np.ndarray,
    objective: Callable[[Sequence[object]], object],
    high_precision: bool,
) -> float:
    if high_precision:
        hp_values = [
            boundary_float_to_mpf(float(value), origin=BoundaryOrigin.SCIPY_OPTIMIZE)
            for value in values
        ]
        objective_raw = objective(hp_values)
        objective_value = (
            boundary_float_to_mpf(objective_raw, origin=BoundaryOrigin.OBJECTIVE_VALUE)
            if isinstance(objective_raw, float)
            else ensure_mpf(objective_raw, context="objective_high_precision")
        )
        return float(objective_value)
    return float(objective(values.tolist()))


def _to_float_bounds(
    bounds: Sequence[tuple[object, object]],
    high_precision: bool,
) -> list[tuple[float, float]]:
    if not high_precision:
        return [(float(low), float(high)) for low, high in bounds]
    safe_bounds = [
        (ensure_mpf(low, context="bounds.low"), ensure_mpf(high, context="bounds.high"))
        for low, high in bounds
    ]
    return [(float(low), float(high)) for low, high in safe_bounds]


def _normalize_mpf_bounds(
    bounds: Sequence[tuple[object, object]],
) -> list[tuple[Any, Any]]:
    normalized: list[tuple[Any, Any]] = []
    for low, high in bounds:
        normalized.append(
            (
                ensure_mpf(low, context="bounds.low"),
                ensure_mpf(high, context="bounds.high"),
            )
        )
    return normalized


def _project_to_bounds_mpf(
    values: list[Any],
    bounds: Sequence[tuple[Any, Any]],
) -> list[Any]:
    projected: list[Any] = []
    for value, bound in zip(values, bounds):
        low, high = bound
        projected.append(min(max(value, low), high))
    return projected


def _objective_mpf(
    values: Sequence[Any],
    objective: Callable[[Sequence[object]], object],
) -> Any:
    return ensure_mpf(objective(list(values)), context="objective")


def _finite_diff_gradient_mpf(
    values: list[Any],
    objective: Callable[[Sequence[object]], object],
    step: Any,
) -> list[Any]:
    gradient: list[Any] = []
    for index in range(len(values)):
        left = list(values)
        right = list(values)
        left[index] = values[index] - step
        right[index] = values[index] + step
        f_left = _objective_mpf(left, objective)
        f_right = _objective_mpf(right, objective)
        gradient.append((f_right - f_left) / (mp.mpf("2") * step))
    return gradient


def _run_mpmath_lbfgsb(
    objective: Callable[[Sequence[object]], object],
    initial: Sequence[object],
    bounds: Sequence[tuple[object, object]],
) -> list[object]:
    values = [ensure_mpf(value, context="initial") for value in initial]
    if not values:
        return []
    mp_bounds = _normalize_mpf_bounds(bounds)
    values = _project_to_bounds_mpf(values, mp_bounds)

    grad_step = mp.mpf("1e-8")
    improve_tol = mp.mpf("1e-20")
    learning_rate = mp.mpf("0.25")
    max_iterations = 64

    objective_value = _objective_mpf(values, objective)
    for _ in range(max_iterations):
        gradient = _finite_diff_gradient_mpf(values, objective, grad_step)
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
            trial = _project_to_bounds_mpf(trial, mp_bounds)
            trial_objective = _objective_mpf(trial, objective)
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


def run_lbfgsb(
    objective: Callable[[Sequence[object]], object],
    initial: Sequence[object],
    bounds: Sequence[tuple[object, object]],
    *,
    high_precision: bool = False,
) -> list[object]:
    """Run L-BFGS-B and return optimized point."""
    if high_precision:
        return _run_mpmath_lbfgsb(objective, initial, bounds)

    start = np.asarray(initial, dtype=float)
    result = minimize(
        partial(_evaluate_objective, objective=objective, high_precision=False),
        start,
        method="L-BFGS-B",
        bounds=_to_float_bounds(bounds, False),
    )
    return [float(value) for value in result.x]
