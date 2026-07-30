"""Disposable ED-critical and moved-affine-slice proposal lane."""

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
    center: Array
    chart: Array
    lower: Array
    upper: Array
    observe: Callable[[Array], Observation]
    replay: Callable[[Array], bool]
    in_bounds: Callable[[Array], bool]
    ed_capable: bool = True


@dataclass
class LaneResult:
    point: Array
    solved: bool
    callbacks: int
    activated: bool
    ed_queries: int
    slice_moves: int
    status: str
    residual_norm: float


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
            raw = self.problem.observe(np.asarray(point, dtype=float).copy())
            residual = np.asarray(raw.residual, dtype=float)
            jacobian = np.asarray(raw.jacobian, dtype=float)
        except Exception:
            return None
        if residual.ndim != 1 or jacobian.shape != (residual.size, point.size):
            return None
        if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(jacobian)):
            return None
        return Observation(residual, jacobian, bool(raw.semantic_valid))

    def pad(self, point: Array) -> None:
        while self.calls < self.cap:
            self.observe(point)


def _to_z(problem: Problem, point: Array) -> Array:
    return np.linalg.solve(problem.chart, point - problem.center)


def _from_z(problem: Problem, z: Array) -> Array:
    return problem.center + problem.chart @ z


def _normalized_rows(obs: Observation, problem: Problem) -> tuple[Array, Array]:
    a = obs.jacobian @ problem.chart
    norms = np.linalg.norm(a, axis=1)
    safe = np.maximum(norms, 1e-13)
    return obs.residual / safe, a / safe[:, None]


def _source_norm(obs: Observation | None, problem: Problem) -> float:
    if obs is None:
        return float("inf")
    residual, _ = _normalized_rows(obs, problem)
    return float(np.linalg.norm(residual, ord=np.inf)) if residual.size else 0.0


def _replayed(problem: Problem, point: Array, obs: Observation | None) -> bool:
    if obs is None or not obs.semantic_valid or not problem.in_bounds(point):
        return False
    try:
        return bool(problem.replay(np.asarray(point, dtype=float).copy()))
    except Exception:
        return False


def _solve_augmented(
    problem: Problem,
    meter: _Meter,
    start: Array,
    max_calls: int,
    slice_a: Array | None = None,
    slice_b: Array | None = None,
) -> tuple[Array, Observation | None]:
    """Row-equilibrated LM for F=0, optionally intersected by Az=b."""
    x = np.asarray(start, dtype=float).copy()
    obs = meter.observe(x)
    stop_at = min(meter.cap, meter.calls - 1 + int(max_calls))
    damping = 1e-5
    while meter.calls < stop_at and obs is not None:
        r, a = _normalized_rows(obs, problem)
        z = _to_z(problem, x)
        if slice_a is not None:
            h = np.concatenate([r, slice_a @ z - slice_b])
            j = np.vstack([a, slice_a])
        else:
            h, j = r, a
        merit = float(np.linalg.norm(h))
        if merit <= 2e-10:
            break
        try:
            step = np.linalg.solve(j.T @ j + damping * np.eye(z.size), -(j.T @ h))
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(j, -h, rcond=1e-11)[0]
        step_norm = float(np.linalg.norm(step))
        if not np.isfinite(step_norm):
            break
        if step_norm > 0.7:
            step *= 0.7 / step_norm

        accepted = False
        alpha = 1.0
        while meter.calls < stop_at and alpha >= 2.0**-10:
            trial = _from_z(problem, z + alpha * step)
            if not problem.in_bounds(trial):
                alpha *= 0.5
                continue
            trial_obs = meter.observe(trial)
            if trial_obs is None:
                break
            trial_r, _ = _normalized_rows(trial_obs, problem)
            trial_z = _to_z(problem, trial)
            trial_h = (
                np.concatenate([trial_r, slice_a @ trial_z - slice_b])
                if slice_a is not None
                else trial_r
            )
            if float(np.linalg.norm(trial_h)) < merit * (1.0 - 1e-8):
                x, obs = trial, trial_obs
                damping = max(1e-10, damping * 0.3)
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            damping *= 30.0
            if damping > 1e9:
                break
    return x, obs


def _rank_and_null(obs: Observation, problem: Problem) -> tuple[int, Array]:
    _, a = _normalized_rows(obs, problem)
    if a.size == 0:
        return 0, np.eye(problem.center.size)
    _, singular, vt = np.linalg.svd(a, full_matrices=True)
    threshold = max(a.shape) * np.finfo(float).eps * max(float(singular[0]), 1.0) * 64.0
    rank = int(np.count_nonzero(singular > threshold))
    return rank, vt[rank:].T


def baseline_lane(problem: Problem, start: Array, callback_cap: int) -> LaneResult:
    meter = _Meter(problem, callback_cap)
    x, obs = _solve_augmented(problem, meter, start, callback_cap)
    solved = _replayed(problem, x, obs)
    residual_norm = _source_norm(obs, problem)
    meter.pad(x)
    return LaneResult(
        x, solved, meter.calls, False, 0, 0, "baseline", residual_norm
    )


def critical_slice_lane(
    problem: Problem,
    start: Array,
    insurance_anchors: list[Array],
    callback_cap: int,
) -> LaneResult:
    if not problem.ed_capable:
        result = baseline_lane(problem, start, callback_cap)
        result.status = "fallback_opaque"
        return result

    meter = _Meter(problem, callback_cap)
    x, obs = _solve_augmented(problem, meter, start, max_calls=max(8, callback_cap // 3))
    if obs is None or _source_norm(obs, problem) > 1e-7:
        x, obs = _solve_augmented(problem, meter, x, max_calls=callback_cap)
        result = LaneResult(
            x,
            _replayed(problem, x, obs),
            meter.calls,
            False,
            0,
            0,
            "fallback_no_manifold_anchor",
            _source_norm(obs, problem),
        )
        meter.pad(x)
        result.callbacks = meter.calls
        return result

    rank, null = _rank_and_null(obs, problem)
    if rank >= x.size or null.shape[1] == 0:
        solved = _replayed(problem, x, obs)
        residual_norm = _source_norm(obs, problem)
        meter.pad(x)
        return LaneResult(
            x, solved, meter.calls, False, 0, 0, "fallback_isolated", residual_norm
        )

    if _replayed(problem, x, obs):
        meter.pad(x)
        return LaneResult(x, True, meter.calls, True, 0, 0, "initial_manifold_root", _source_norm(obs, problem))

    ed_queries = 0
    slice_moves = 0
    # Reflect already-owned full-support anchors through the source chart
    # center.  This is target-blind and commutes with affine chart transforms.
    query_points = [2.0 * problem.center - np.asarray(a, dtype=float) for a in insurance_anchors]
    best_x, best_obs = x, obs
    per_query = max(5, callback_cap // max(6, 2 * len(query_points)))
    for query in query_points:
        if meter.calls >= meter.cap - 2:
            break
        if not problem.in_bounds(query):
            continue
        # Local normal projection from a generic query is a numerical ED
        # critical-point proposal for the source zero set.
        ed_x, ed_obs = _solve_augmented(problem, meter, query, per_query)
        ed_queries += 1
        if ed_obs is not None and _source_norm(ed_obs, problem) < _source_norm(best_obs, problem):
            best_x, best_obs = ed_x, ed_obs
        if _replayed(problem, ed_x, ed_obs):
            best_x, best_obs = ed_x, ed_obs
            break
        if ed_obs is None or _source_norm(ed_obs, problem) > 1e-6:
            continue

        rank, null = _rank_and_null(ed_obs, problem)
        if rank >= ed_x.size or null.shape[1] == 0:
            continue
        current_z = _to_z(problem, ed_x)
        query_z = _to_z(problem, query)
        displacement = null.T @ (query_z - current_z)
        disp_norm = float(np.linalg.norm(displacement))
        if disp_norm <= 1e-10:
            continue
        if disp_norm > 0.45:
            displacement *= 0.45 / disp_norm
        slice_a = null.T
        slice_b = slice_a @ current_z + displacement
        moved_x, moved_obs = _solve_augmented(
            problem,
            meter,
            ed_x,
            per_query,
            slice_a=slice_a,
            slice_b=slice_b,
        )
        slice_moves += 1
        if moved_obs is not None and _source_norm(moved_obs, problem) < 1e-6:
            best_x, best_obs = moved_x, moved_obs
        if _replayed(problem, moved_x, moved_obs):
            break

    solved = _replayed(problem, best_x, best_obs)
    residual_norm = _source_norm(best_obs, problem)
    meter.pad(best_x)
    return LaneResult(
        best_x,
        solved,
        meter.calls,
        True,
        ed_queries,
        slice_moves,
        "ed_slice_then_replay",
        residual_norm,
    )


def solve_portfolio(
    problem: Problem,
    starts: list[Array],
    callback_cap_per_lane: int,
    candidate: bool,
) -> list[LaneResult]:
    results: list[LaneResult] = []
    for ordinal, start in enumerate(starts):
        if candidate and ordinal % 4 == 3:
            results.append(
                critical_slice_lane(
                    problem,
                    start,
                    [np.asarray(x, dtype=float) for x in starts[:3]],
                    callback_cap_per_lane,
                )
            )
        else:
            results.append(baseline_lane(problem, start, callback_cap_per_lane))
    return results
