"""Full Gauss-Newton/LM local solver at multiprecision."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial

from mpmath import mp

from geosolver._internal.solver.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.optimization.mp.mp_residual_vector import mp_residual_vector
from geosolver._internal.solver.optimization.mp.mp_residual_norm import mp_residual_norm
from geosolver._internal.solver.optimization.mp.mp_jacobian import compute_mp_jacobian
from geosolver._internal.solver.optimization.mp.mp_gauss_newton_step import compute_gauss_newton_step
from geosolver._internal.solver.optimization.mp.mp_line_search import mp_backtracking_line_search
from geosolver._internal.solver.optimization.mp.mp_clamp_to_bounds import mp_clamp_to_bounds


_DEFAULT_MAX_ITERATIONS = 50
_DAMPING_INITIAL_EXPONENT = -6
_DAMPING_INCREASE_FACTOR = 4
_DAMPING_DECREASE_FACTOR = 3
_HIGH_DIGIT_TARGET_DPS = 100
_FINAL_HEADROOM_DPS = 120
_STAGE_HEADROOM_DIGITS = 8
_MIN_STAGE_ACCURACY_DIGITS = 20
_TARGET_HEADROOM_DIGITS = 20
_MIN_RELATIVE_IMPROVEMENT = mp.mpf("1e-120")
_MAX_STALL_STEPS = 30


@dataclass(frozen=True)
class MPLocalSolveDiagnostics:
    """Diagnostics for local MP solve convergence behavior."""

    plateau_detected: bool
    last_step_norm: MPFloat
    stationarity_norm: MPFloat


def _should_escalate_precision(
    *,
    best_norm: MPFloat,
    residual_threshold: MPFloat | None,
    stage_dps: int,
    target_dps: int,
) -> bool:
    if int(stage_dps) < int(target_dps):
        return True
    if int(target_dps) >= _HIGH_DIGIT_TARGET_DPS and int(stage_dps) < _FINAL_HEADROOM_DPS:
        return True
    if residual_threshold is None:
        return False
    return bool(best_norm > residual_threshold)


def _default_stage_residual_threshold(*, stage_dps: int, target_dps: int) -> MPFloat:
    """Return the default residual target for one precision stage."""
    stage_digits = int(stage_dps)
    target_digits = int(target_dps)
    if stage_digits < target_digits:
        effective_digits = stage_digits - _STAGE_HEADROOM_DIGITS
    else:
        effective_digits = target_digits + 2
    effective_digits = max(_MIN_STAGE_ACCURACY_DIGITS, effective_digits)
    return mp.power(mp.mpf("10"), -effective_digits)


def _resolve_stage_residual_threshold(
    *,
    stage_dps: int,
    target_dps: int,
    residual_threshold: MPFloat | None,
) -> MPFloat:
    """Blend the caller threshold with the stage default."""
    stage_default = _default_stage_residual_threshold(
        stage_dps=int(stage_dps),
        target_dps=int(target_dps),
    )
    if residual_threshold is None:
        return stage_default
    caller_threshold = mp.mpf(residual_threshold)
    if int(target_dps) >= _HIGH_DIGIT_TARGET_DPS and int(stage_dps) >= _FINAL_HEADROOM_DPS:
        return caller_threshold
    if int(target_dps) < _HIGH_DIGIT_TARGET_DPS and int(stage_dps) >= int(target_dps):
        return caller_threshold
    return max(stage_default, caller_threshold)


def _run_precision_substage(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    seed: list[MPFloat],
    dps: int,
    max_iterations: int,
    residual_threshold: MPFloat | None,
    bounds: list[tuple[MPFloat | None, MPFloat | None]] | None,
    deadline: float | None,
) -> tuple[list[MPFloat], MPFloat, MPLocalSolveDiagnostics]:
    old_dps = mp.dps
    mp.dps = max(int(dps), 15)
    try:
        with high_precision_mode():
            return _solve_inner(
                f=f,
                targets=targets,
                seed=seed,
                max_iterations=max_iterations,
                residual_threshold=residual_threshold,
                bounds=bounds,
                deadline=deadline,
            )
    finally:
        mp.dps = old_dps


def _build_precision_schedule(target_dps: int) -> list[int]:
    schedule: list[int] = []
    target = int(target_dps)
    for stage in (30, 60, 90, 120):
        if stage < target and stage not in schedule:
            schedule.append(stage)
    if target not in schedule:
        schedule.append(target)
    if target >= _HIGH_DIGIT_TARGET_DPS and _FINAL_HEADROOM_DPS not in schedule:
        schedule.append(_FINAL_HEADROOM_DPS)
    final_target = max(target + _TARGET_HEADROOM_DIGITS, target * 2)
    if target >= _HIGH_DIGIT_TARGET_DPS and final_target not in schedule:
        schedule.append(final_target)
    elif target >= _HIGH_DIGIT_TARGET_DPS and _FINAL_HEADROOM_DPS not in schedule:
        schedule.append(_FINAL_HEADROOM_DPS)
    return schedule


def _step_norm(current: list[MPFloat], trial: list[MPFloat]) -> MPFloat:
    return mp.sqrt(
        mp.fsum((trial_value - current_value) * (trial_value - current_value) for current_value, trial_value in zip(current, trial))
    )


def _stationarity_norm_from_jacobian(
    *,
    jacobian: list[list[MPFloat]],
    residual: list[MPFloat],
    n_variables: int,
) -> MPFloat:
    gradient_terms: list[MPFloat] = []
    row_count = len(jacobian)
    residual_count = len(residual)
    for col in range(n_variables):
        term = mp.fsum(
            jacobian[row][col] * residual[row]
            for row in range(min(row_count, residual_count))
        )
        gradient_terms.append(term)
    return mp.sqrt(mp.fsum(term * term for term in gradient_terms))


def _scalar_newton_step_if_available(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    x: list[MPFloat],
    residual: list[MPFloat],
    damping: MPFloat,
) -> list[MPFloat] | None:
    if len(x) != 1 or len(residual) != 1 or len(targets) != 1:
        return None
    x0 = x[0]
    target0 = targets[0]
    try:
        derivative = mp.diff(lambda t: f([t])[0] - target0, x0)
    except Exception:
        return None
    if derivative == mp.mpf("0"):
        return None
    denominator = derivative + damping
    if denominator == mp.mpf("0"):
        return None
    return [-(residual[0] / denominator)]


def _scalar_residual_value(
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    target: MPFloat,
    x_value: MPFloat,
) -> MPFloat:
    return mp.mpf(f([x_value])[0]) - target


def _scalar_findroot_polish_if_available(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    point: list[MPFloat],
    bounds: list[tuple[MPFloat | None, MPFloat | None]] | None,
) -> list[MPFloat] | None:
    if bounds is not None:
        return None
    if len(point) != 1 or len(targets) != 1:
        return None
    target0 = targets[0]
    x0 = point[0]
    residual_fn = partial(_scalar_residual_value, f, target0)
    try:
        root = mp.findroot(residual_fn, x0)
    except Exception:
        return None
    if not mp.isfinite(root):
        return None
    return [mp.mpf(root)]


def mp_local_solve(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    seed: list[MPFloat],
    dps: int,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    residual_threshold: MPFloat | None = None,
    bounds: list[tuple[MPFloat | None, MPFloat | None]] | None = None,
    deadline: float | None = None,
    return_diagnostics: bool = False,
) -> tuple[list[MPFloat], MPFloat] | tuple[list[MPFloat], MPFloat, MPLocalSolveDiagnostics]:
    """Run damped Gauss-Newton local solver at given multiprecision.

    Args:
        f: Constraint function.
        targets: Target values (m constraints).
        seed: Starting point (n variables).
        dps: Decimal precision (mpmath dps).
        max_iterations: Max GN iterations.
        residual_threshold: Early-exit threshold on residual norm.
        bounds: Per-variable box bounds.
        deadline: Wall-clock deadline (time.time() value).
        return_diagnostics: Whether to return MPLocalSolveDiagnostics.

    Returns:
        (best_point, best_residual_norm) or
        (best_point, best_residual_norm, diagnostics).
    """
    schedule = _build_precision_schedule(int(dps))
    current_seed = [mp.mpf(value) for value in seed]
    best_norm = mp.mpf("inf")
    last_diagnostics = MPLocalSolveDiagnostics(
        plateau_detected=False,
        last_step_norm=mp.mpf("0"),
        stationarity_norm=mp.mpf("inf"),
    )

    for stage_dps in schedule:
        stage_threshold = _resolve_stage_residual_threshold(
            stage_dps=int(stage_dps),
            target_dps=int(dps),
            residual_threshold=residual_threshold,
        )
        stage_result = _run_precision_substage(
            f=f,
            targets=targets,
            seed=current_seed,
            dps=stage_dps,
            max_iterations=max_iterations,
            residual_threshold=stage_threshold,
            bounds=bounds,
            deadline=deadline,
        )
        if len(stage_result) == 2:
            current_seed, best_norm = stage_result
            stage_diagnostics = MPLocalSolveDiagnostics(
                plateau_detected=False,
                last_step_norm=mp.mpf("0"),
                stationarity_norm=mp.mpf("inf"),
            )
        else:
            current_seed, best_norm, stage_diagnostics = stage_result
        last_diagnostics = stage_diagnostics
        if best_norm <= mp.power(mp.mpf("10"), -20):
            polished_seed = _scalar_findroot_polish_if_available(
                f=f,
                targets=targets,
                point=current_seed,
                bounds=bounds,
            )
            if polished_seed is not None:
                polished_residual = mp_residual_norm(
                    mp_residual_vector(f=f, targets=targets, x=polished_seed)
                )
                if polished_residual < best_norm:
                    current_seed = list(polished_seed)
                    best_norm = polished_residual
        if not _should_escalate_precision(
            best_norm=best_norm,
            residual_threshold=stage_threshold,
            stage_dps=stage_dps,
            target_dps=int(dps),
        ):
            break

    if return_diagnostics:
        return current_seed, best_norm, last_diagnostics
    return current_seed, best_norm


def _solve_inner(
    *,
    f: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    seed: list[MPFloat],
    max_iterations: int,
    residual_threshold: MPFloat | None,
    bounds: list[tuple[MPFloat | None, MPFloat | None]] | None,
    deadline: float | None,
) -> tuple[list[MPFloat], MPFloat, MPLocalSolveDiagnostics]:
    """Inner solve loop (assumes dps already set)."""
    x = mp_clamp_to_bounds([mp.mpf(v) for v in seed], bounds)
    r = mp_residual_vector(f=f, targets=targets, x=x)
    norm = mp_residual_norm(r)

    if not mp.isfinite(norm):
        return x, mp.mpf("inf"), MPLocalSolveDiagnostics(
            plateau_detected=True,
            last_step_norm=mp.mpf("0"),
            stationarity_norm=mp.mpf("inf"),
        )

    if residual_threshold is None:
        residual_threshold = mp.power(mp.mpf("10"), -max(_MIN_STAGE_ACCURACY_DIGITS, int(mp.dps) - _STAGE_HEADROOM_DIGITS))

    best_x = list(x)
    best_norm = norm
    n = len(x)
    m = len(r)
    damping = mp.power(mp.mpf("10"), _DAMPING_INITIAL_EXPONENT)
    stall_steps = 0
    last_step = mp.mpf("0")
    stationarity_norm = mp.mpf("inf")
    plateau_detected = False

    for _ in range(max_iterations):
        if deadline is not None and time.time() > deadline:
            break
        if best_norm <= residual_threshold:
            break

        jac = compute_mp_jacobian(f=f, x=x, targets=targets, target_dps=int(mp.dps))
        stationarity_norm = _stationarity_norm_from_jacobian(
            jacobian=jac,
            residual=r,
            n_variables=n,
        )
        if norm <= residual_threshold and stationarity_norm <= residual_threshold:
            best_x = list(x)
            best_norm = norm
            break
        step = _scalar_newton_step_if_available(
            f=f,
            targets=targets,
            x=x,
            residual=r,
            damping=damping,
        )
        if step is None:
            step = compute_gauss_newton_step(
                jacobian=jac, residual=r, damping=damping, n=n, m=m,
            )

        new_x, new_norm, improved = mp_backtracking_line_search(
            f=f, targets=targets, x=x, step=step,
            current_norm=norm, bounds=bounds,
        )

        if improved:
            step_norm = _step_norm(x, new_x)
            improvement_ratio = (norm - new_norm) / max(abs(norm), mp.power(mp.mpf("10"), -30))
            x = new_x
            r = mp_residual_vector(f=f, targets=targets, x=x)
            norm = new_norm
            damping = max(
                mp.power(mp.mpf("10"), _DAMPING_INITIAL_EXPONENT),
                damping / _DAMPING_DECREASE_FACTOR,
            )
            if norm < best_norm:
                best_x = list(x)
                best_norm = norm
            if improvement_ratio <= _MIN_RELATIVE_IMPROVEMENT:
                stall_steps += 1
            else:
                stall_steps = 0
            if stall_steps >= _MAX_STALL_STEPS:
                plateau_detected = True
                break
        else:
            damping *= _DAMPING_INCREASE_FACTOR
            stall_steps += 1
            if stall_steps >= _MAX_STALL_STEPS:
                plateau_detected = True
                break
        last_step = step_norm if improved else mp.mpf("0")

    return best_x, best_norm, MPLocalSolveDiagnostics(
        plateau_detected=bool(plateau_detected),
        last_step_norm=last_step,
        stationarity_norm=stationarity_norm,
    )
