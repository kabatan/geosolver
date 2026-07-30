"""Disposable D0: noise-calibrated rank-deficient SQP polish.

This is intentionally one candidate, not a shared SQP framework.  Both arms
pay for the same repeated finite-difference stencil; the control ignores its
noise/rank state while the side arm may spend one of every four starts on a
normal/tangential rescue after a stable rank-deficient plateau.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
from scipy.linalg import qr


Array = np.ndarray
Residual = Callable[[Array], Array]
Guard = Callable[[Array], bool]


@dataclass(frozen=True)
class NoiseRankState:
    epsilon_f: float
    epsilon_j: float
    coarse_rank: int
    fine_rank: int
    rank_threshold: float
    residual_norm: float
    merit: float
    merit_noise_floor: float
    plateau_streak: int
    normal_norm: float
    tangential_norm: float
    model_reduction: float
    activated: bool
    reason: str


@dataclass(frozen=True)
class AttemptResult:
    endpoint: Array
    verified: bool
    residual_inf: float
    callbacks: int
    activations: int
    route: str
    fallback_reason: str | None
    states: tuple[NoiseRankState, ...]


@dataclass(frozen=True)
class _Probe:
    residual: Array
    coarse_jacobian: Array
    fine_jacobian: Array
    epsilon_f: float
    epsilon_j: float
    coarse_rank: int
    fine_rank: int
    rank_threshold: float
    row_scale: Array


def _safe_call(residual: Residual, x: Array) -> Array | None:
    try:
        value = np.asarray(residual(x), dtype=float).reshape(-1)
    except (ArithmeticError, FloatingPointError, OverflowError, ValueError):
        return None
    return value if value.size and np.all(np.isfinite(value)) else None


def _cpqr_rank(matrix: Array, threshold: float) -> tuple[int, Array]:
    if not matrix.size:
        return 0, np.arange(matrix.shape[0], dtype=int)
    try:
        _q, triangular, pivots = qr(matrix.T, mode="economic", pivoting=True)
    except (ValueError, np.linalg.LinAlgError):
        return -1, np.arange(matrix.shape[0], dtype=int)
    diagonal = np.abs(np.diag(triangular))
    rank = int(np.count_nonzero(diagonal > threshold))
    return rank, np.asarray(pivots, dtype=int)


def _probe_noise_rank(
    call: Callable[[Array], Array | None],
    z: Array,
    *,
    step: float,
) -> _Probe | None:
    first = call(z)
    second = call(z)
    if first is None or second is None or first.shape != second.shape:
        return None
    anchor = 0.5 * (first + second)
    m, n = anchor.size, z.size
    coarse = np.empty((m, n), dtype=float)
    fine = np.empty((m, n), dtype=float)
    for column in range(n):
        direction = np.zeros(n, dtype=float)
        direction[column] = step
        plus = call(z + direction)
        minus = call(z - direction)
        half_plus = call(z + 0.5 * direction)
        half_minus = call(z - 0.5 * direction)
        if any(value is None or value.shape != anchor.shape for value in (plus, minus, half_plus, half_minus)):
            return None
        coarse[:, column] = (plus - minus) / (2.0 * step)
        fine[:, column] = (half_plus - half_minus) / step

    raw_noise_f = 0.5 * np.abs(first - second)
    row_scale = np.maximum.reduce((
        np.abs(anchor),
        np.linalg.norm(coarse, axis=1),
        np.linalg.norm(fine, axis=1),
        8.0 * raw_noise_f,
        np.full(m, 1e-14),
    ))
    normalized_anchor = anchor / row_scale
    normalized_coarse = coarse / row_scale[:, None]
    normalized_fine = fine / row_scale[:, None]
    epsilon_f = float(np.linalg.norm(raw_noise_f / row_scale, ord=np.inf))
    epsilon_j = float(np.linalg.norm(normalized_fine - normalized_coarse, ord=2))
    scale = max(1.0, float(np.linalg.norm(normalized_fine, ord=2)))
    threshold = max(8.0 * epsilon_j, 64.0 * np.finfo(float).eps * (m + n) * scale)
    coarse_rank, _ = _cpqr_rank(normalized_coarse, threshold)
    fine_rank, _ = _cpqr_rank(normalized_fine, threshold)
    return _Probe(
        normalized_anchor,
        normalized_coarse,
        normalized_fine,
        epsilon_f,
        epsilon_j,
        coarse_rank,
        fine_rank,
        threshold,
        row_scale,
    )


def _bounded(vector: Array, radius: float) -> Array:
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm):
        return np.zeros_like(vector)
    return vector if norm <= radius or norm == 0.0 else vector * (radius / norm)


def _baseline_step(probe: _Probe, radius: float) -> Array:
    jacobian = probe.fine_jacobian
    try:
        left, singular, right = np.linalg.svd(jacobian, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.zeros(jacobian.shape[1], dtype=float)
    retained = singular > probe.rank_threshold
    if not np.any(retained):
        return np.zeros(jacobian.shape[1], dtype=float)
    step = -right[retained, :].T @ (
        (left[:, retained].T @ probe.residual) / singular[retained]
    )
    return _bounded(step, radius)


def _normal_tangential_step(probe: _Probe, radius: float) -> tuple[Array, Array, float]:
    """Byrd--Omojokun-style decomposition on independent/dependent rows.

    CPQR selects a noise-resolved independent constraint set.  The normal step
    reduces those rows.  Remaining rows define the tangential objective.  If
    its first-order projected gradient is itself below the measured Jacobian
    noise, a canonical null-space exploration step is used; its acceptance is
    still decided only by the original noise-relaxed merit replay.
    """
    jacobian = probe.fine_jacobian
    residual = probe.residual
    rank, pivots = _cpqr_rank(jacobian, probe.rank_threshold)
    if rank < 0:
        return np.zeros(jacobian.shape[1]), np.zeros(jacobian.shape[1]), 0.0
    independent = pivots[:rank]
    dependent = pivots[rank:]
    A = jacobian[independent, :]
    b = residual[independent]
    normal = (
        -np.linalg.pinv(A, rcond=max(probe.rank_threshold, 1e-14)) @ b
        if rank
        else np.zeros(jacobian.shape[1], dtype=float)
    )
    normal = _bounded(normal, 0.8 * radius)
    try:
        _u, _s, vh = np.linalg.svd(A, full_matrices=True)
    except np.linalg.LinAlgError:
        return normal, np.zeros_like(normal), 0.0
    nullspace = vh[rank:, :].T
    if nullspace.shape[1] == 0:
        return normal, np.zeros_like(normal), 0.0

    if dependent.size:
        gradient = jacobian[dependent, :].T @ residual[dependent]
        projected = nullspace @ (nullspace.T @ gradient)
    else:
        projected = np.zeros(jacobian.shape[1], dtype=float)
    projected_norm = float(np.linalg.norm(projected))
    noise_gradient = probe.epsilon_j * max(1.0, float(np.linalg.norm(residual)))
    if projected_norm > 4.0 * noise_gradient:
        tangential = -projected / projected_norm * (0.6 * radius)
    else:
        direction = nullspace[:, 0].copy()
        pivot = int(np.argmax(np.abs(direction)))
        if direction[pivot] < 0.0:
            direction *= -1.0
        tangential = direction * (0.8 * radius)
    combined = normal + tangential
    combined_norm = float(np.linalg.norm(combined))
    if combined_norm > radius:
        scale = radius / combined_norm
        normal *= scale
        tangential *= scale
    step = normal + tangential
    model_reduction = float(
        np.linalg.norm(residual) - np.linalg.norm(residual + jacobian @ step)
    )
    return normal, tangential, model_reduction


def _merit_noise_floor(
    epsilon_f: float,
    epsilon_j: float,
    residual_norm: float,
    applied_step_norm: float,
) -> float:
    return max(
        2.0 * epsilon_f * max(residual_norm, epsilon_f),
        epsilon_j * applied_step_norm * max(residual_norm, epsilon_f),
        64.0 * np.finfo(float).eps,
    )


def _trial_acceptable(
    *,
    merit: float,
    trial_merit: float,
    alpha: float,
    model_reduction: float,
    epsilon_f: float,
    epsilon_j: float,
    residual_norm: float,
    step_norm: float,
) -> tuple[bool, float]:
    floor = _merit_noise_floor(
        epsilon_f,
        epsilon_j,
        residual_norm,
        alpha * step_norm,
    )
    required = alpha * 1e-4 * max(model_reduction, 0.0)
    return trial_merit <= merit - required + 4.0 * floor, floor


def verify_endpoint(
    residual: Residual,
    x: Array,
    guards: Iterable[Guard] = (),
    tolerance: float = 1e-8,
) -> tuple[bool, float]:
    value = _safe_call(residual, x)
    if value is None:
        return False, float("inf")
    residual_inf = float(np.linalg.norm(value, ord=np.inf))
    try:
        guards_ok = all(bool(guard(x)) for guard in guards)
    except (ArithmeticError, FloatingPointError, OverflowError, ValueError):
        guards_ok = False
    return bool(guards_ok and residual_inf <= tolerance), residual_inf


def solve_attempt(
    residual: Residual,
    start: Array,
    *,
    route: str,
    smooth: bool = True,
    guards: Iterable[Guard] = (),
    variable_scale: Array | None = None,
    max_iterations: int = 8,
    fd_step: float = 1e-4,
    trust_radius: float = 1.0,
    tolerance: float = 1e-8,
) -> AttemptResult:
    if route not in {"baseline", "noise_sqp"}:
        raise ValueError(f"unknown route: {route}")
    start = np.asarray(start, dtype=float).reshape(-1)
    scale = np.ones_like(start) if variable_scale is None else np.asarray(variable_scale, dtype=float).reshape(-1)
    if scale.shape != start.shape or np.any(~np.isfinite(scale)) or np.any(scale <= 0.0):
        raise ValueError("finite positive variable scale required")
    z = start / scale
    callbacks = 0
    activations = 0
    fallback_reason: str | None = None
    states: list[NoiseRankState] = []
    previous_merit: float | None = None
    plateau_streak = 0

    def call(normalized: Array) -> Array | None:
        nonlocal callbacks
        callbacks += 1
        return _safe_call(residual, scale * normalized)

    for _iteration in range(max_iterations):
        probe = _probe_noise_rank(call, z, step=fd_step)
        if probe is None:
            fallback_reason = fallback_reason or "invalid_repeat_fd"
            # Equal-cost D0 cases never reach this path; fail closed.
            break
        residual_norm = float(np.linalg.norm(probe.residual))
        merit = 0.5 * residual_norm * residual_norm
        plateau_noise_floor = _merit_noise_floor(
            probe.epsilon_f,
            probe.epsilon_j,
            residual_norm,
            trust_radius,
        )
        if previous_merit is not None and abs(previous_merit - merit) <= 4.0 * plateau_noise_floor:
            plateau_streak += 1
        else:
            plateau_streak = 0
        previous_merit = merit

        current_verified = residual_norm <= tolerance
        stable_rank_deficient = (
            probe.coarse_rank == probe.fine_rank
            and 0 <= probe.fine_rank < z.size
        )
        eligible = (
            route == "noise_sqp"
            and smooth
            and stable_rank_deficient
            and plateau_streak >= 1
            and residual_norm > max(tolerance, 8.0 * probe.epsilon_f)
        )
        normal = np.zeros_like(z)
        tangential = np.zeros_like(z)
        model_reduction = 0.0
        if current_verified:
            step = np.zeros_like(z)
            reason = "noise_floor_or_verified_stop"
        elif eligible:
            normal, tangential, model_reduction = _normal_tangential_step(probe, trust_radius)
            step = _bounded(normal + tangential, trust_radius)
            activations += 1
            reason = "stable_rank_deficient_noise_plateau"
        else:
            step = _baseline_step(probe, trust_radius)
            if route == "noise_sqp" and fallback_reason is None:
                if not smooth:
                    fallback_reason = "opaque_or_nonsmooth"
                elif not stable_rank_deficient:
                    fallback_reason = "not_stable_rank_deficient"
                else:
                    fallback_reason = "not_noise_floor_plateau"
            reason = fallback_reason or "baseline_control"

        # Both arms evaluate every trial so callback work is exactly identical.
        alphas = (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125)
        trials: list[tuple[Array, Array | None, float]] = []
        for alpha in alphas:
            trial_z = z + alpha * step
            value = call(trial_z)
            if value is None:
                trials.append((trial_z, None, float("inf")))
                continue
            normalized = value / probe.row_scale
            trials.append((trial_z, value, 0.5 * float(normalized @ normalized)))
        if not current_verified:
            step_norm = float(np.linalg.norm(step))
            for alpha, (trial_z, value, trial_merit) in zip(alphas, trials):
                acceptable, _floor = _trial_acceptable(
                    merit=merit,
                    trial_merit=trial_merit,
                    alpha=alpha,
                    model_reduction=model_reduction,
                    epsilon_f=probe.epsilon_f,
                    epsilon_j=probe.epsilon_j,
                    residual_norm=residual_norm,
                    step_norm=step_norm,
                )
                if value is not None and acceptable:
                    z = trial_z
                    break

        merit_noise_floor = _merit_noise_floor(
            probe.epsilon_f,
            probe.epsilon_j,
            residual_norm,
            float(np.linalg.norm(step)),
        )

        states.append(NoiseRankState(
            probe.epsilon_f,
            probe.epsilon_j,
            probe.coarse_rank,
            probe.fine_rank,
            probe.rank_threshold,
            residual_norm,
            merit,
            merit_noise_floor,
            plateau_streak,
            float(np.linalg.norm(normal)),
            float(np.linalg.norm(tangential)),
            model_reduction,
            eligible,
            reason,
        ))

    fixed_callback_budget = max_iterations * (2 + 4 * z.size + 6) + 1
    while callbacks < fixed_callback_budget - 1:
        call(z)
    endpoint = scale * z
    verified, residual_inf = verify_endpoint(residual, endpoint, guards, tolerance)
    callbacks += 1
    if callbacks != fixed_callback_budget:
        raise RuntimeError("candidate-local callback accounting mismatch")
    return AttemptResult(
        endpoint,
        verified,
        residual_inf,
        callbacks,
        activations,
        route,
        fallback_reason,
        tuple(states),
    )


def route_for_start(start_index: int) -> str:
    return "noise_sqp" if start_index % 4 == 3 else "baseline"
