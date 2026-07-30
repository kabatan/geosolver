"""Disposable persistent-dual greedy Bregman--Kaczmarz D0 prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class Observation:
    residual: Array
    jacobian: Array
    semantic_valid: bool = True


@dataclass(frozen=True)
class Problem:
    lower: Array
    upper: Array
    scale: Array
    observe: Callable[[Array], Observation]
    replay: Callable[[Array], bool]


@dataclass
class LaneResult:
    point: Array
    solved: bool
    callbacks: int
    activated: bool
    accepted_rows: int
    status: str
    best_merit: float


class _Meter:
    def __init__(self, problem: Problem, cap: int):
        self.problem = problem
        self.cap = int(cap)
        self.calls = 0

    def observe(self, point: Array) -> Observation | None:
        if self.calls >= self.cap:
            return None
        self.calls += 1
        try:
            obs = self.problem.observe(np.asarray(point, dtype=float).copy())
        except Exception:
            return None
        residual = np.asarray(obs.residual, dtype=float)
        jacobian = np.asarray(obs.jacobian, dtype=float)
        if residual.ndim != 1 or jacobian.shape != (residual.size, point.size):
            return None
        if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(jacobian)):
            return None
        return Observation(residual, jacobian, bool(obs.semantic_valid))

    def pad(self, point: Array) -> None:
        while self.calls < self.cap:
            self.observe(point)


def _row_units(obs: Observation, scale: Array) -> tuple[Array, Array, Array]:
    a = obs.jacobian * scale[None, :]
    row_norm = np.linalg.norm(a, axis=1)
    safe = np.maximum(row_norm, 1e-14)
    return obs.residual / safe, a / safe[:, None], row_norm


def _merit(obs: Observation, scale: Array) -> float:
    r, _, row_norm = _row_units(obs, scale)
    if np.any(row_norm <= 1e-14):
        bad = np.abs(obs.residual[row_norm <= 1e-14])
        if np.any(bad > 1e-10):
            return float("inf")
    return float(np.linalg.norm(r, ord=np.inf)) if r.size else 0.0


def _inside(point: Array, lower: Array, upper: Array) -> bool:
    return bool(np.all(point > lower) and np.all(point < upper))


def _replayed(problem: Problem, point: Array, obs: Observation | None) -> bool:
    if obs is None or not obs.semantic_valid:
        return False
    try:
        return bool(problem.replay(np.asarray(point, dtype=float).copy()))
    except Exception:
        return False


def _lm_tail(
    problem: Problem,
    meter: _Meter,
    point: Array,
    obs: Observation | None = None,
) -> tuple[Array, Observation | None, float]:
    x = np.asarray(point, dtype=float).copy()
    current = obs if obs is not None else meter.observe(x)
    best = _merit(current, problem.scale) if current is not None else float("inf")
    damping = 1e-3
    while meter.calls < meter.cap and current is not None:
        if _replayed(problem, x, current):
            break
        r, a, _ = _row_units(current, problem.scale)
        h = a.T @ a + damping * np.eye(x.size)
        try:
            dz = np.linalg.solve(h, -(a.T @ r))
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(dz)):
            break
        accepted = False
        alpha = 1.0
        while meter.calls < meter.cap and alpha >= 2.0**-12:
            trial = x + alpha * problem.scale * dz
            if not _inside(trial, problem.lower, problem.upper):
                alpha *= 0.5
                continue
            trial_obs = meter.observe(trial)
            if trial_obs is None:
                break
            trial_merit = _merit(trial_obs, problem.scale)
            if trial_merit < best * (1.0 - 1e-8) or trial_merit < 1e-11:
                x, current, best = trial, trial_obs, trial_merit
                damping = max(1e-9, damping * 0.35)
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            damping *= 16.0
            if damping > 1e10:
                break
    return x, current, best


def _logit(q: Array) -> Array:
    q = np.clip(q, 1e-12, 1.0 - 1e-12)
    return np.log(q) - np.log1p(-q)


def _sigmoid(z: Array) -> Array:
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def _linearized_bregman_multiplier(f: float, grad: Array, z: Array) -> float | None:
    """Solve f + g.(sigmoid(z-t*g)-sigmoid(z)) = 0 in dual space."""
    q0 = _sigmoid(z)
    denom = float(np.dot(grad * grad, q0 * (1.0 - q0)))
    if not np.isfinite(denom) or denom <= 1e-18:
        return None
    t = float(np.clip(f / denom, -32.0, 32.0))
    for _ in range(14):
        q = _sigmoid(z - t * grad)
        h = float(f + np.dot(grad, q - q0))
        dh = -float(np.dot(grad * grad, q * (1.0 - q)))
        if abs(h) <= 1e-11 * (1.0 + abs(f)):
            return t
        if not np.isfinite(dh) or abs(dh) <= 1e-18:
            break
        t = float(np.clip(t - h / dh, -64.0, 64.0))
    return t if np.isfinite(t) else None


def baseline_lane(problem: Problem, start: Array, callback_cap: int) -> LaneResult:
    meter = _Meter(problem, callback_cap)
    x, obs, merit = _lm_tail(problem, meter, np.asarray(start, dtype=float))
    solved = _replayed(problem, x, obs)
    meter.pad(x)
    return LaneResult(x, solved, meter.calls, False, 0, "baseline", merit)


def bregman_lane(
    problem: Problem,
    start: Array,
    callback_cap: int,
    seed: int,
    max_row_steps: int = 8,
) -> LaneResult:
    lower = np.asarray(problem.lower, dtype=float)
    upper = np.asarray(problem.upper, dtype=float)
    scale = np.asarray(problem.scale, dtype=float)
    x = np.asarray(start, dtype=float).copy()

    eligible = (
        x.ndim == 1
        and lower.shape == x.shape
        and upper.shape == x.shape
        and scale.shape == x.shape
        and np.all(np.isfinite(lower))
        and np.all(np.isfinite(upper))
        and np.all(np.isfinite(scale))
        and np.all(upper > lower)
        and np.all(scale > 0)
        and _inside(x, lower, upper)
    )
    if not eligible:
        result = baseline_lane(problem, x, callback_cap)
        result.status = "fallback_ineligible"
        return result

    meter = _Meter(problem, callback_cap)
    obs = meter.observe(x)
    if obs is None:
        meter.pad(x)
        return LaneResult(x, False, meter.calls, False, 0, "fallback_opaque", float("inf"))

    width = upper - lower
    q = (x - lower) / width
    z = _logit(q)
    merit = _merit(obs, scale)
    rng = np.random.default_rng(int(seed))
    accepted_rows = 0
    dual_memory = np.zeros_like(z)

    for _ in range(max_row_steps):
        if meter.calls >= max(1, meter.cap - 2) or _replayed(problem, x, obs):
            break
        grad_q = obs.jacobian * width[None, :]
        grad_norm = np.linalg.norm(grad_q, axis=1)
        score = np.abs(obs.residual) / np.maximum(grad_norm, 1e-14)
        usable = np.flatnonzero((grad_norm > 1e-14) & np.isfinite(score))
        if usable.size == 0:
            break
        peak = float(np.max(score[usable]))
        active = usable[score[usable] >= 0.55 * peak]
        weights = np.square(score[active])
        weights = weights / np.sum(weights) if np.sum(weights) > 0 else None
        sample_size = min(2, active.size)
        sampled = np.atleast_1d(
            rng.choice(active, size=sample_size, replace=False, p=weights)
        )
        projected: list[Array] = []
        projected_weights: list[float] = []
        for sampled_row in sampled:
            row = int(sampled_row)
            multiplier = _linearized_bregman_multiplier(
                float(obs.residual[row]), grad_q[row], z
            )
            if multiplier is None:
                continue
            delta = -multiplier * grad_q[row]
            delta_norm = float(np.linalg.norm(delta))
            if not np.isfinite(delta_norm) or delta_norm <= 1e-15:
                continue
            # Repair A: a dual trust cap prevents a saturated nonlinear row
            # from sending the entropy primal map straight to a box face.
            # Averaging two residual-informed row projections and persistent
            # dual memory lets coupled rows cooperate without a full J^+f
            # block step.
            if delta_norm > 2.25:
                delta = delta * (2.25 / delta_norm)
            projected.append(delta)
            projected_weights.append(float(score[row] ** 2))
        if not projected:
            break

        blend_weights = np.asarray(projected_weights, dtype=float)
        blend_weights /= np.sum(blend_weights)
        dual_proposal = np.sum(
            np.stack(projected, axis=0) * blend_weights[:, None], axis=0
        )
        dual_proposal = dual_proposal + 0.35 * dual_memory
        proposal_norm = float(np.linalg.norm(dual_proposal))
        if proposal_norm > 2.75:
            dual_proposal *= 2.75 / proposal_norm

        accepted = False
        alpha = 0.9
        while meter.calls < meter.cap - 1 and alpha >= 2.0**-8:
            z_trial = z + alpha * dual_proposal
            q_trial = _sigmoid(z_trial)
            trial = lower + width * q_trial
            trial_obs = meter.observe(trial)
            if trial_obs is None:
                break
            trial_merit = _merit(trial_obs, scale)
            if trial_merit < merit * (1.0 - 1e-7) or trial_merit < 1e-11:
                x, obs, merit, z = trial, trial_obs, trial_merit, z_trial
                dual_memory = 0.55 * dual_memory + 0.45 * alpha * dual_proposal
                accepted_rows += len(projected)
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            break

    x, obs, merit = _lm_tail(problem, meter, x, obs)
    solved = _replayed(problem, x, obs)
    meter.pad(x)
    return LaneResult(
        x, solved, meter.calls, True, accepted_rows, "bregman_then_lm", merit
    )


def solve_portfolio(
    problem: Problem,
    starts: list[Array],
    callback_cap_per_lane: int,
    seed: int,
    candidate: bool,
) -> list[LaneResult]:
    """Keep three of four lanes byte-identical; replace only ordinal 3."""
    results: list[LaneResult] = []
    for ordinal, start in enumerate(starts):
        if candidate and ordinal % 4 == 3:
            results.append(
                bregman_lane(
                    problem,
                    start,
                    callback_cap_per_lane,
                    seed=(int(seed) << 16) ^ ordinal,
                )
            )
        else:
            results.append(baseline_lane(problem, start, callback_cap_per_lane))
    return results
