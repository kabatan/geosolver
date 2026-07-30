"""Disposable analytic Golub--Pereyra variable-projection D0."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Callable, Sequence

import numpy as np


BASELINE_PERIOD = 4
MAX_LINEAR_CONDITION = 1.0e8
SOURCE_TOL = 2.0e-8
MAX_ITERATIONS = 7
MAX_STEP_NORM = 1.5


@dataclass(frozen=True)
class OperatorState:
    matrix: np.ndarray             # A(x), shape (m,p)
    matrix_derivative: np.ndarray  # dA/dx, shape (m,p,q)
    rhs: np.ndarray                # b(x), shape (m,)
    rhs_derivative: np.ndarray     # db/dx, shape (m,q)
    outer_residual: np.ndarray     # g(x), shape (s,)
    outer_jacobian: np.ndarray     # dg/dx, shape (s,q)


Operator = Callable[[np.ndarray], OperatorState]
FullResidual = Callable[[np.ndarray], np.ndarray]
FullJacobian = Callable[[np.ndarray], np.ndarray]
Guard = Callable[[np.ndarray], bool]


@dataclass(frozen=True)
class SeparableProblem:
    nonlinear_dimension: int
    linear_dimension: int
    operator: Operator
    full_residual: FullResidual
    full_jacobian: FullJacobian
    guard: Guard
    affine_certified: bool = True
    opaque: bool = False


@dataclass(frozen=True)
class ReducedModel:
    nonlinear: np.ndarray
    linear: np.ndarray
    residual: np.ndarray
    jacobian: np.ndarray
    condition: float


@dataclass(frozen=True)
class SolveResult:
    activated: bool
    solved: bool
    reason: str
    point: np.ndarray
    residual_inf: float
    iterations: int
    full_evaluations: int
    inner_solves: int
    analytic_reduced_jacobians: int


@dataclass(frozen=True)
class PortfolioResult:
    baseline: SolveResult
    side: SolveResult
    proposals: tuple[np.ndarray, ...]
    route_trace: tuple[str, ...]
    baseline_digest_before: str
    baseline_digest_after: str


def route_trace(starts: int = 16) -> tuple[str, ...]:
    if starts < 4 or starts % 4:
        raise ValueError("starts must be a positive multiple of four")
    return tuple("analytic_varpro" if i % 4 == 3 else "baseline" for i in range(starts))


def _digest(point: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(point, dtype="<f8").tobytes()).hexdigest()


def _safe_guard(problem: SeparableProblem, point: np.ndarray) -> bool:
    try:
        return bool(problem.guard(np.asarray(point, dtype=float)))
    except Exception:
        return False


def canonical_source_replay(problem: SeparableProblem, point: np.ndarray) -> bool:
    point = np.asarray(point, dtype=float)
    if point.ndim != 1 or point.size != problem.nonlinear_dimension + problem.linear_dimension:
        return False
    if not np.all(np.isfinite(point)) or not _safe_guard(problem, point):
        return False
    try:
        residual = np.asarray(problem.full_residual(point), dtype=float)
    except Exception:
        return False
    return residual.ndim == 1 and residual.size > 0 and np.all(np.isfinite(residual)) and float(np.max(np.abs(residual))) <= SOURCE_TOL


def _validate_state(problem: SeparableProblem, nonlinear: np.ndarray) -> OperatorState:
    state = problem.operator(np.asarray(nonlinear, dtype=float))
    q = problem.nonlinear_dimension
    p = problem.linear_dimension
    matrix = np.asarray(state.matrix, dtype=float)
    derivative = np.asarray(state.matrix_derivative, dtype=float)
    rhs = np.asarray(state.rhs, dtype=float)
    rhs_derivative = np.asarray(state.rhs_derivative, dtype=float)
    outer = np.asarray(state.outer_residual, dtype=float)
    outer_jacobian = np.asarray(state.outer_jacobian, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != p or matrix.shape[0] < p:
        raise ValueError("bad affine matrix shape")
    rows = matrix.shape[0]
    if derivative.shape != (rows, p, q) or rhs.shape != (rows,) or rhs_derivative.shape != (rows, q):
        raise ValueError("bad affine derivative shape")
    if outer.ndim != 1 or outer_jacobian.shape != (outer.size, q):
        raise ValueError("bad outer residual shape")
    arrays = (matrix, derivative, rhs, rhs_derivative, outer, outer_jacobian)
    if any(not np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("non-finite operator state")
    return OperatorState(matrix, derivative, rhs, rhs_derivative, outer, outer_jacobian)


def analytic_reduced_model(problem: SeparableProblem, nonlinear: np.ndarray) -> ReducedModel:
    """Differentiate the full-rank LS normal equations; no FD inner solves."""

    state = _validate_state(problem, nonlinear)
    matrix = state.matrix
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    if singular_values.size < problem.linear_dimension or singular_values[-1] <= 0.0:
        raise np.linalg.LinAlgError("rank-deficient affine block")
    condition = float(singular_values[0] / singular_values[-1])
    if not math.isfinite(condition) or condition > MAX_LINEAR_CONDITION:
        raise np.linalg.LinAlgError("ill-conditioned affine block")
    linear, _, rank, _ = np.linalg.lstsq(matrix, state.rhs, rcond=None)
    if rank != problem.linear_dimension:
        raise np.linalg.LinAlgError("rank-deficient LS solve")
    fibre_residual = matrix @ linear - state.rhs
    normal = matrix.T @ matrix
    q = problem.nonlinear_dimension
    fibre_jacobian = np.empty((matrix.shape[0], q), dtype=float)
    for axis in range(q):
        dmatrix = state.matrix_derivative[:, :, axis]
        drhs = state.rhs_derivative[:, axis]
        # Exact derivative of A(x)^T(A(x)y(x)-b(x)) = 0.
        derivative_rhs = (
            dmatrix.T @ state.rhs
            + matrix.T @ drhs
            - (dmatrix.T @ matrix + matrix.T @ dmatrix) @ linear
        )
        dlinear = np.linalg.solve(normal, derivative_rhs)
        fibre_jacobian[:, axis] = dmatrix @ linear + matrix @ dlinear - drhs
    residual = np.concatenate((fibre_residual, state.outer_residual))
    jacobian = np.vstack((fibre_jacobian, state.outer_jacobian))
    return ReducedModel(np.array(nonlinear, copy=True), linear, residual, jacobian, condition)


def projected_residual(problem: SeparableProblem, nonlinear: np.ndarray) -> ReducedModel:
    """The same exact affine block, without using its analytic derivatives."""

    state = _validate_state(problem, nonlinear)
    singular_values = np.linalg.svd(state.matrix, compute_uv=False)
    if singular_values.size < problem.linear_dimension or singular_values[-1] <= 0.0:
        raise np.linalg.LinAlgError("rank-deficient affine block")
    condition = float(singular_values[0] / singular_values[-1])
    if not math.isfinite(condition) or condition > MAX_LINEAR_CONDITION:
        raise np.linalg.LinAlgError("ill-conditioned affine block")
    linear, _, rank, _ = np.linalg.lstsq(state.matrix, state.rhs, rcond=None)
    if rank != problem.linear_dimension:
        raise np.linalg.LinAlgError("rank-deficient LS solve")
    residual = np.concatenate((state.matrix @ linear - state.rhs, state.outer_residual))
    return ReducedModel(
        np.array(nonlinear, copy=True),
        linear,
        residual,
        np.empty((residual.size, 0)),
        condition,
    )


def _clip(step: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(step))
    if norm > MAX_STEP_NORM:
        return step * (MAX_STEP_NORM / norm)
    return step


def _inactive(start: np.ndarray, reason: str) -> SolveResult:
    return SolveResult(False, False, reason, np.array(start, copy=True), math.inf, 0, 0, 0, 0)


def solve_analytic_varpro(problem: SeparableProblem, start: np.ndarray) -> SolveResult:
    start = np.asarray(start, dtype=float)
    if problem.opaque:
        return _inactive(start, "opaque_fallback")
    if not problem.affine_certified:
        return _inactive(start, "nonaffine_fallback")
    if start.shape != (problem.nonlinear_dimension + problem.linear_dimension,) or not np.all(np.isfinite(start)):
        return _inactive(start, "invalid_start")
    nonlinear = np.array(start[: problem.nonlinear_dimension], copy=True)
    inner_solves = jacobians = evaluations = 0
    best_point = np.array(start, copy=True)
    best_norm = math.inf
    for iteration in range(MAX_ITERATIONS + 1):
        try:
            model = analytic_reduced_model(problem, nonlinear)
        except Exception as error:
            return _inactive(start, f"linear_block_fallback:{type(error).__name__}")
        inner_solves += 1
        jacobians += 1
        point = np.concatenate((nonlinear, model.linear))
        evaluations += 1
        residual_inf = float(np.max(np.abs(model.residual))) if model.residual.size else 0.0
        if residual_inf < best_norm and _safe_guard(problem, point):
            best_point = point
            best_norm = residual_inf
        if residual_inf <= SOURCE_TOL and canonical_source_replay(problem, point):
            return SolveResult(True, True, "source_replayed", point, residual_inf, iteration, evaluations, inner_solves, jacobians)
        if iteration == MAX_ITERATIONS:
            break
        try:
            step, _, _, _ = np.linalg.lstsq(model.jacobian, -model.residual, rcond=None)
        except Exception:
            break
        step = _clip(step)
        merit = float(model.residual @ model.residual)
        accepted = False
        for power in range(9):
            trial_nonlinear = nonlinear + (0.5**power) * step
            try:
                trial = analytic_reduced_model(problem, trial_nonlinear)
            except Exception:
                continue
            inner_solves += 1
            trial_point = np.concatenate((trial_nonlinear, trial.linear))
            evaluations += 1
            trial_merit = float(trial.residual @ trial.residual)
            if _safe_guard(problem, trial_point) and trial_merit < merit * (1.0 - 1.0e-4 * 0.5**power):
                nonlinear = trial_nonlinear
                accepted = True
                break
        if not accepted:
            break
    solved = canonical_source_replay(problem, best_point)
    return SolveResult(True, solved, "budget_or_stall", best_point, best_norm, MAX_ITERATIONS, evaluations, inner_solves, jacobians)


def solve_fd_projected_varpro(problem: SeparableProblem, start: np.ndarray) -> SolveResult:
    """Causal control: identical VarPro/globalization, FD projected derivative."""

    start = np.asarray(start, dtype=float)
    if problem.opaque:
        return _inactive(start, "opaque_fallback")
    if not problem.affine_certified:
        return _inactive(start, "nonaffine_fallback")
    if start.shape != (problem.nonlinear_dimension + problem.linear_dimension,) or not np.all(np.isfinite(start)):
        return _inactive(start, "invalid_start")
    nonlinear = np.array(start[: problem.nonlinear_dimension], copy=True)
    inner_solves = evaluations = 0
    best_point = np.array(start, copy=True)
    best_norm = math.inf
    for iteration in range(MAX_ITERATIONS + 1):
        try:
            model = projected_residual(problem, nonlinear)
        except Exception as error:
            return _inactive(start, f"linear_block_fallback:{type(error).__name__}")
        inner_solves += 1
        evaluations += 1
        point = np.concatenate((nonlinear, model.linear))
        residual_inf = float(np.max(np.abs(model.residual))) if model.residual.size else 0.0
        if residual_inf < best_norm and _safe_guard(problem, point):
            best_point = point
            best_norm = residual_inf
        if residual_inf <= SOURCE_TOL and canonical_source_replay(problem, point):
            return SolveResult(True, True, "source_replayed", point, residual_inf, iteration, evaluations, inner_solves, 0)
        if iteration == MAX_ITERATIONS:
            break
        jacobian = np.empty((model.residual.size, problem.nonlinear_dimension), dtype=float)
        try:
            for axis in range(problem.nonlinear_dimension):
                step_size = 2.0e-6 * max(1.0, abs(nonlinear[axis]))
                offset = np.zeros_like(nonlinear)
                offset[axis] = step_size
                plus = projected_residual(problem, nonlinear + offset)
                minus = projected_residual(problem, nonlinear - offset)
                inner_solves += 2
                evaluations += 2
                jacobian[:, axis] = (plus.residual - minus.residual) / (2.0 * step_size)
            step, _, _, _ = np.linalg.lstsq(jacobian, -model.residual, rcond=None)
        except Exception:
            break
        step = _clip(step)
        merit = float(model.residual @ model.residual)
        accepted = False
        for power in range(9):
            trial_nonlinear = nonlinear + (0.5**power) * step
            try:
                trial = projected_residual(problem, trial_nonlinear)
            except Exception:
                continue
            inner_solves += 1
            evaluations += 1
            trial_point = np.concatenate((trial_nonlinear, trial.linear))
            trial_merit = float(trial.residual @ trial.residual)
            if _safe_guard(problem, trial_point) and trial_merit < merit * (1.0 - 1.0e-4 * 0.5**power):
                nonlinear = trial_nonlinear
                accepted = True
                break
        if not accepted:
            break
    solved = canonical_source_replay(problem, best_point)
    return SolveResult(True, solved, "budget_or_stall", best_point, best_norm, MAX_ITERATIONS, evaluations, inner_solves, 0)


def solve_full_space_baseline(problem: SeparableProblem, start: np.ndarray) -> SolveResult:
    point = np.asarray(start, dtype=float).copy()
    best = point.copy()
    best_norm = math.inf
    evaluations = 0
    for iteration in range(MAX_ITERATIONS + 1):
        try:
            residual = np.asarray(problem.full_residual(point), dtype=float)
            jacobian = np.asarray(problem.full_jacobian(point), dtype=float)
        except Exception:
            break
        evaluations += 1
        if residual.ndim != 1 or jacobian.shape != (residual.size, point.size):
            break
        if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(jacobian)):
            break
        residual_inf = float(np.max(np.abs(residual)))
        if residual_inf < best_norm and _safe_guard(problem, point):
            best = point.copy()
            best_norm = residual_inf
        if residual_inf <= SOURCE_TOL and canonical_source_replay(problem, point):
            return SolveResult(True, True, "source_replayed", point, residual_inf, iteration, evaluations, 0, 0)
        if iteration == MAX_ITERATIONS:
            break
        step, _, _, _ = np.linalg.lstsq(jacobian, -residual, rcond=None)
        step = _clip(step)
        merit = float(residual @ residual)
        accepted = False
        for power in range(9):
            trial = point + (0.5**power) * step
            try:
                trial_residual = np.asarray(problem.full_residual(trial), dtype=float)
            except Exception:
                continue
            evaluations += 1
            if np.all(np.isfinite(trial_residual)) and _safe_guard(problem, trial) and float(trial_residual @ trial_residual) < merit * (1.0 - 1.0e-4 * 0.5**power):
                point = trial
                accepted = True
                break
        if not accepted:
            break
    solved = canonical_source_replay(problem, best)
    return SolveResult(True, solved, "budget_or_stall", best, best_norm, MAX_ITERATIONS, evaluations, 0, 0)


def run_portfolio(problem: SeparableProblem, start: np.ndarray, *, starts: int = 16) -> PortfolioResult:
    immutable_start = np.asarray(start, dtype=float).copy()
    before = _digest(immutable_start)
    baseline = solve_fd_projected_varpro(problem, immutable_start)
    side = solve_analytic_varpro(problem, immutable_start)
    proposals: list[np.ndarray] = []
    for result in (baseline, side):
        if result.solved and not any(np.linalg.norm(result.point - prior) <= 1.0e-8 for prior in proposals):
            proposals.append(np.array(result.point, copy=True))
    return PortfolioResult(baseline, side, tuple(proposals), route_trace(starts), before, _digest(immutable_start))
