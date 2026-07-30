"""Disposable guard-boundary conormal critical-point proposal lane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class Observation:
    residual: Array
    jacobian: Array
    guard_margins: Array
    guard_gradients: Array
    semantic_valid: bool = True
    supported_strict_guards: bool = True


@dataclass(frozen=True)
class Problem:
    center: Array
    chart: Array
    lower: Array
    upper: Array
    observe: Callable[[Array], Observation]
    replay: Callable[[Array], bool]
    in_bounds: Callable[[Array], bool]


@dataclass
class LaneResult:
    point: Array
    solved: bool
    callbacks: int
    activated: bool
    conormal_queries: int
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
            margins = np.asarray(raw.guard_margins, dtype=float)
            gradients = np.asarray(raw.guard_gradients, dtype=float)
        except Exception:
            return None
        n = point.size
        if residual.ndim != 1 or jacobian.shape != (residual.size, n):
            return None
        if margins.ndim != 1 or gradients.shape != (margins.size, n):
            return None
        arrays = (residual, jacobian, margins, gradients)
        if any(not np.all(np.isfinite(value)) for value in arrays):
            return None
        return Observation(
            residual,
            jacobian,
            margins,
            gradients,
            bool(raw.semantic_valid),
            bool(raw.supported_strict_guards),
        )

    def pad(self, point: Array) -> None:
        while self.calls < self.cap:
            self.observe(point)


def _to_z(problem: Problem, point: Array) -> Array:
    return np.linalg.solve(problem.chart, point - problem.center)


def _from_z(problem: Problem, z: Array) -> Array:
    return problem.center + problem.chart @ z


def _source_rows(problem: Problem, obs: Observation) -> tuple[Array, Array]:
    jacobian = obs.jacobian @ problem.chart
    scales = np.maximum(np.linalg.norm(jacobian, axis=1), 1e-12)
    return obs.residual / scales, jacobian / scales[:, None]


def _source_norm(problem: Problem, obs: Observation | None) -> float:
    if obs is None:
        return float("inf")
    residual, _ = _source_rows(problem, obs)
    return float(np.linalg.norm(residual, ord=np.inf)) if residual.size else 0.0


def _replayed(problem: Problem, point: Array, obs: Observation | None) -> bool:
    if obs is None or not obs.semantic_valid or not problem.in_bounds(point):
        return False
    try:
        return bool(problem.replay(np.asarray(point, dtype=float).copy()))
    except Exception:
        return False


def _solve_source(
    problem: Problem, meter: _Meter, start: Array, allowance: int
) -> tuple[Array, Observation | None]:
    x = np.asarray(start, dtype=float).copy()
    obs = meter.observe(x)
    stop = min(meter.cap, meter.calls - 1 + max(1, int(allowance)))
    damping = 1e-5
    while obs is not None and meter.calls < stop:
        residual, jacobian = _source_rows(problem, obs)
        if np.linalg.norm(residual, ord=np.inf) <= 2e-10:
            break
        try:
            step = np.linalg.solve(
                jacobian.T @ jacobian + damping * np.eye(x.size),
                -(jacobian.T @ residual),
            )
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(jacobian, -residual, rcond=1e-11)[0]
        norm = float(np.linalg.norm(step))
        if not np.isfinite(norm):
            break
        if norm > 0.8:
            step *= 0.8 / norm
        z = _to_z(problem, x)
        merit = float(np.linalg.norm(residual))
        accepted = False
        for alpha in (1.0, 0.5, 0.25, 0.125):
            trial = _from_z(problem, z + alpha * step)
            if not problem.in_bounds(trial) or meter.calls >= stop:
                continue
            trial_obs = meter.observe(trial)
            if trial_obs is None:
                break
            trial_residual, _ = _source_rows(problem, trial_obs)
            if float(np.linalg.norm(trial_residual)) < merit * (1.0 - 1e-9):
                x, obs = trial, trial_obs
                damping = max(1e-10, damping * 0.3)
                accepted = True
                break
        if not accepted:
            damping *= 30.0
            if damping > 1e8:
                break
    return x, obs


def _rank(problem: Problem, obs: Observation) -> int:
    _, jacobian = _source_rows(problem, obs)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    if singular.size == 0:
        return 0
    threshold = max(jacobian.shape) * np.finfo(float).eps * max(1.0, float(singular[0])) * 64
    return int(np.count_nonzero(singular > threshold))


def _guard_rows(problem: Problem, obs: Observation) -> tuple[Array, Array]:
    gradients = obs.guard_gradients @ problem.chart
    scales = np.maximum(np.linalg.norm(gradients, axis=1), 1e-12)
    return obs.guard_margins / scales, gradients / scales[:, None]


def _conormal_vector(
    problem: Problem,
    obs: Observation,
    point: Array,
    query_z: Array,
    guard_index: int,
    interior_epsilon: float,
) -> Array | None:
    residual, source_jacobian = _source_rows(problem, obs)
    margins, guard_jacobian = _guard_rows(problem, obs)
    if guard_index >= margins.size:
        return None
    guard_normal = guard_jacobian[guard_index]
    normals = np.column_stack([source_jacobian.T, guard_normal])
    displacement = _to_z(problem, point) - query_z
    try:
        coefficients = np.linalg.lstsq(normals, displacement, rcond=1e-11)[0]
    except np.linalg.LinAlgError:
        return None
    tangent = displacement - normals @ coefficients
    return np.concatenate(
        [residual, [margins[guard_index] - interior_epsilon], tangent]
    )


def _solve_conormal(
    problem: Problem,
    meter: _Meter,
    start: Array,
    query: Array,
    guard_index: int,
    interior_epsilon: float,
) -> tuple[Array, Observation | None]:
    x = np.asarray(start, dtype=float).copy()
    query_z = _to_z(problem, np.asarray(query, dtype=float))
    obs = meter.observe(x)
    damping = 1e-5
    while obs is not None and meter.calls + x.size + 1 < meter.cap:
        vector = _conormal_vector(
            problem, obs, x, query_z, guard_index, interior_epsilon
        )
        if vector is None:
            break
        merit = float(np.linalg.norm(vector))
        if merit <= 3e-8 and _source_norm(problem, obs) <= 1e-8:
            break
        z = _to_z(problem, x)
        columns = []
        for column in range(x.size):
            step = 2e-5 * max(1.0, abs(float(z[column])))
            trial_z = z.copy()
            trial_z[column] += step
            trial = _from_z(problem, trial_z)
            trial_obs = meter.observe(trial) if problem.in_bounds(trial) else None
            trial_vector = (
                _conormal_vector(
                    problem,
                    trial_obs,
                    trial,
                    query_z,
                    guard_index,
                    interior_epsilon,
                )
                if trial_obs is not None
                else None
            )
            if trial_vector is None or trial_vector.shape != vector.shape:
                return x, obs
            columns.append((trial_vector - vector) / step)
        jacobian = np.column_stack(columns)
        try:
            step = np.linalg.solve(
                jacobian.T @ jacobian + damping * np.eye(x.size),
                -(jacobian.T @ vector),
            )
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(jacobian, -vector, rcond=1e-10)[0]
        norm = float(np.linalg.norm(step))
        if not np.isfinite(norm):
            break
        if norm > 0.9:
            step *= 0.9 / norm
        accepted = False
        for alpha in (1.0, 0.5, 0.25, 0.125):
            if meter.calls >= meter.cap:
                break
            trial = _from_z(problem, z + alpha * step)
            if not problem.in_bounds(trial):
                continue
            trial_obs = meter.observe(trial)
            if trial_obs is None:
                break
            trial_vector = _conormal_vector(
                problem,
                trial_obs,
                trial,
                query_z,
                guard_index,
                interior_epsilon,
            )
            if trial_vector is not None and float(np.linalg.norm(trial_vector)) < merit:
                x, obs = trial, trial_obs
                damping = max(1e-10, damping * 0.25)
                accepted = True
                break
        if not accepted:
            damping *= 25.0
            if damping > 1e8:
                break
    return x, obs


def baseline_lane(problem: Problem, start: Array, callback_cap: int) -> LaneResult:
    meter = _Meter(problem, callback_cap)
    point, obs = _solve_source(problem, meter, start, callback_cap)
    solved = _replayed(problem, point, obs)
    norm = _source_norm(problem, obs)
    meter.pad(point)
    return LaneResult(point, solved, meter.calls, False, 0, "baseline", norm)


def conormal_lane(
    problem: Problem,
    start: Array,
    insurance_anchors: list[Array],
    callback_cap: int,
) -> LaneResult:
    meter = _Meter(problem, callback_cap)
    anchor, anchor_obs = _solve_source(
        problem, meter, start, max(8, callback_cap // 3)
    )
    fallback_solved = _replayed(problem, anchor, anchor_obs)
    if (
        anchor_obs is None
        or _source_norm(problem, anchor_obs) > 1e-7
        or not anchor_obs.supported_strict_guards
        or anchor_obs.guard_margins.size == 0
        or _rank(problem, anchor_obs) >= anchor.size
    ):
        meter.pad(anchor)
        return LaneResult(
            anchor,
            fallback_solved,
            meter.calls,
            False,
            0,
            "fallback_no_supported_boundary_stratum",
            _source_norm(problem, anchor_obs),
        )

    normalized_margins, _ = _guard_rows(problem, anchor_obs)
    guard_index = int(np.argmin(np.abs(normalized_margins)))
    activated = True
    queries = [
        2.0 * problem.center - np.asarray(point, dtype=float)
        for point in insurance_anchors
    ]
    best_point, best_obs = anchor, anchor_obs
    conormal_queries = 0
    for query in queries:
        if meter.calls + anchor.size + 2 >= meter.cap or not problem.in_bounds(query):
            continue
        point, obs = _solve_conormal(
            problem,
            meter,
            query,
            query,
            guard_index,
            interior_epsilon=0.02,
        )
        conormal_queries += 1
        if _replayed(problem, point, obs):
            best_point, best_obs = point, obs
            break

    solved = _replayed(problem, best_point, best_obs)
    norm = _source_norm(problem, best_obs)
    meter.pad(best_point)
    return LaneResult(
        best_point,
        solved,
        meter.calls,
        activated,
        conormal_queries,
        "interior_guard_conormal_then_replay",
        norm,
    )


def solve_portfolio(
    problem: Problem,
    starts: list[Array],
    callback_cap_per_lane: int,
    candidate: bool,
) -> list[LaneResult]:
    results = []
    for ordinal, start in enumerate(starts):
        if candidate and ordinal % 4 == 3:
            results.append(
                conormal_lane(
                    problem,
                    start,
                    [np.asarray(point, dtype=float) for point in starts[:3]],
                    callback_cap_per_lane,
                )
            )
        else:
            results.append(baseline_lane(problem, start, callback_cap_per_lane))
    return results
