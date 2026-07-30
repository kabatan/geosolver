"""Disposable D0 for a spectral-frame nonlinear-preconditioned GN lane.

This is deliberately not a solver framework.  It only tests whether replacing
one ordinary GN proposal by a cosh-reference proposal can rescue fast-growth
residuals while the ordinary lane keeps at least 75% of starts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np


Array = np.ndarray
Residual = Callable[[Array], Array]
Jacobian = Callable[[Array], Array]
Guard = Callable[[Array], bool]


@dataclass(frozen=True)
class AttemptResult:
    endpoint: Array
    verified: bool
    iterations: int
    callbacks: int
    activations: int
    route: str
    fallback_reason: str | None
    residual_inf: float


def _safe_residual(residual: Residual, x: Array) -> Array | None:
    try:
        value = np.asarray(residual(x), dtype=float).reshape(-1)
    except (ArithmeticError, FloatingPointError, OverflowError, ValueError):
        return None
    return value if value.size and np.all(np.isfinite(value)) else None


def verify_endpoint(
    residual: Residual,
    x: Array,
    guards: Iterable[Guard] = (),
    tolerance: float = 1e-9,
) -> tuple[bool, float]:
    """Canonical-replay stand-in: original residual and guards are mandatory."""
    value = _safe_residual(residual, x)
    if value is None:
        return False, float("inf")
    residual_inf = float(np.linalg.norm(value, ord=np.inf))
    try:
        guards_ok = all(bool(guard(x)) for guard in guards)
    except (ArithmeticError, FloatingPointError, OverflowError, ValueError):
        guards_ok = False
    return bool(guards_ok and residual_inf <= tolerance), residual_inf


def spectral_cosh_rhs(
    normal_matrix: Array,
    normal_gradient: Array,
    reference_radius: float,
) -> tuple[Array, bool, str | None]:
    """Return q for ``H d = -q`` using a cosh reference in H's eigenframe.

    If ``a = V.T @ g`` and ``w`` are H's eigenvalues, the local gradient scale
    for a reference-radius displacement is ``s_i = w_i * radius``.  Applying
    the separable cosh-reference Newton map gives

        q_i = s_i * sqrt(1 + (a_i/s_i)^2) * asinh(a_i/s_i).

    This scale choice makes the proposal invariant to a common residual scale.
    The odd scalar map also removes eigenvector sign ambiguity.  Near rank
    deficiency or an effectively multiple spectrum we fail closed to GN.
    """
    H = np.asarray(normal_matrix, dtype=float)
    g = np.asarray(normal_gradient, dtype=float).reshape(-1)
    if H.shape != (g.size, g.size) or not np.all(np.isfinite(H)) or not np.all(np.isfinite(g)):
        return g.copy(), False, "nonfinite_model"
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(H)
    except np.linalg.LinAlgError:
        return g.copy(), False, "eigh_failed"
    high = float(eigenvalues[-1]) if eigenvalues.size else 0.0
    if high <= 0.0:
        return g.copy(), False, "zero_model"
    rank_floor = max(1e-14, 1e-11 * high)
    if float(eigenvalues[0]) <= rank_floor:
        return g.copy(), False, "rank_deficient"

    # A repeated eigenspace has no canonical separable coordinate frame.
    if eigenvalues.size > 1:
        relative_gaps = np.diff(eigenvalues) / np.maximum(eigenvalues[1:], rank_floor)
        if float(np.min(relative_gaps)) < 1e-9:
            return g.copy(), False, "ambiguous_eigenframe"

    radius = max(float(reference_radius), np.finfo(float).eps)
    coordinates = eigenvectors.T @ g
    scales = np.maximum(eigenvalues * radius, rank_floor * radius)
    z = coordinates / scales
    if not np.all(np.isfinite(z)) or float(np.max(np.abs(z))) > 1e6:
        return g.copy(), False, "unstable_reference_coordinate"
    if float(np.max(np.abs(z))) <= 0.25:
        return g.copy(), False, "small_newton_coordinate"

    transformed = scales * np.sqrt(1.0 + z * z) * np.arcsinh(z)
    q = eigenvectors @ transformed
    if not np.all(np.isfinite(q)):
        return g.copy(), False, "nonfinite_preconditioned_rhs"
    direction_change = np.linalg.norm(q - g) / max(np.linalg.norm(g), np.finfo(float).eps)
    if direction_change <= 1e-5:
        return g.copy(), False, "negligible_direction_change"
    return q, True, None


def solve_attempt(
    residual: Residual,
    jacobian: Jacobian,
    start: Array,
    *,
    route: str,
    smooth: bool = True,
    guards: Iterable[Guard] = (),
    max_iterations: int = 11,
    reference_radius: float = 1.0,
    tolerance: float = 1e-9,
) -> AttemptResult:
    """Run equal-budget ordinary GN or the disposable proposal lane."""
    if route not in {"baseline", "spectral_cosh"}:
        raise ValueError(f"unknown route: {route}")
    x = np.asarray(start, dtype=float).reshape(-1).copy()
    callbacks = 0
    activations = 0
    fallback_reason: str | None = None

    for iteration in range(max_iterations + 1):
        r = _safe_residual(residual, x)
        callbacks += 1
        if r is None:
            break
        residual_inf = float(np.linalg.norm(r, ord=np.inf))
        if residual_inf <= tolerance:
            verified, replay_inf = verify_endpoint(residual, x, guards, tolerance)
            return AttemptResult(x, verified, iteration, callbacks, activations, route, fallback_reason, replay_inf)
        if iteration == max_iterations:
            break
        try:
            J = np.asarray(jacobian(x), dtype=float)
        except (ArithmeticError, FloatingPointError, OverflowError, ValueError):
            break
        if J.shape != (r.size, x.size) or not np.all(np.isfinite(J)):
            break
        callbacks += 1
        g = J.T @ r
        H0 = J.T @ J
        damping = max(1e-14, 1e-12 * max(1.0, float(np.linalg.norm(H0, ord=2))))
        H = H0 + damping * np.eye(x.size)
        q = g
        if route == "spectral_cosh" and smooth:
            q, activated, reason = spectral_cosh_rhs(H, g, reference_radius)
            activations += int(activated)
            if not activated and fallback_reason is None:
                fallback_reason = reason
        elif route == "spectral_cosh" and fallback_reason is None:
            fallback_reason = "unsupported_nonsmooth"

        try:
            step = np.linalg.solve(H, -q)
        except np.linalg.LinAlgError:
            step = -np.linalg.pinv(H) @ q
        if not np.all(np.isfinite(step)):
            break
        step_radius = max(reference_radius, 1.0 + 0.75 * float(np.linalg.norm(x)))
        step_norm = float(np.linalg.norm(step))
        if step_norm > step_radius:
            step *= step_radius / step_norm

        merit = 0.5 * float(r @ r)
        accepted = False
        for backtrack in range(20):
            alpha = 0.5**backtrack
            trial = x + alpha * step
            trial_r = _safe_residual(residual, trial)
            callbacks += 1
            if trial_r is None:
                continue
            trial_merit = 0.5 * float(trial_r @ trial_r)
            if trial_merit < merit * (1.0 - 1e-4 * alpha):
                x = trial
                accepted = True
                break
        if not accepted:
            break

    verified, replay_inf = verify_endpoint(residual, x, guards, tolerance)
    return AttemptResult(x, verified, min(max_iterations, iteration + 1), callbacks, activations, route, fallback_reason, replay_inf)


def route_for_start(start_index: int) -> str:
    """Exactly one in four attempts uses the side route; 75% stay baseline."""
    return "spectral_cosh" if start_index % 4 == 3 else "baseline"

