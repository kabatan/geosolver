"""Guard-directed equation-swap continuation from an invalid source root.

This module is deliberately independent of the shared v15 worker.  It is a
proposal generator, never a source-solution authority.  At a regular square
root rejected by a *proven differentiable* strict guard it removes exactly one
residual row, follows the resulting one-dimensional level set with a
pseudo-arclength predictor/corrector, solves a square system in which the
removed row is replaced by a positive guard-margin equation, and finally
restores every original residual row.  Only an untouched source replay may
promote the restored endpoint.

The removed row is selected solely from scaled numerical rank, conditioning,
guard tangent slope, and dropped-row transversality.  No case identity,
geometry name, target value, inferred coordinate bound, or offline outcome is
accepted by the API.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Sequence

import numpy as np
from scipy.linalg import qr as pivoted_qr


Array = np.ndarray


@dataclass(frozen=True, slots=True)
class Observation:
    """One evaluation of the unchanged source problem.

    ``smooth_margins`` use the strict convention ``margin > 0``.  A margin
    row may guide continuation only when the corresponding provenance flag is
    true and its analytic gradient is finite.  Unsupported semantic branches
    remain visible only through ``source_valid`` and therefore cannot become
    a fabricated descent direction.
    """

    residual: Array
    smooth_margins: Array
    finite: bool
    source_valid: bool
    residual_jacobian: Array | None
    margin_jacobian: Array | None
    smooth_margin_provenance: Array


Evaluator = Callable[[Array], Observation]


@dataclass(frozen=True, slots=True)
class Configuration:
    maximum_callbacks: int = 256
    root_entry_tolerance: float = 1.0e-9
    root_success_tolerance: float = 1.0e-9
    strict_margin_tolerance: float = 1.0e-11
    rank_relative_tolerance: float = 1.0e-9
    slope_relative_tolerance: float = 2.0e-8
    minimum_pair_score: float = 1.0e-11
    initial_arclength_step: float = 0.16
    minimum_arclength_step: float = 2.0e-5
    maximum_arclength_step: float = 0.55
    step_growth: float = 1.35
    step_shrink: float = 0.5
    maximum_path_steps: int = 48
    maximum_corrector_steps: int = 9
    maximum_restore_steps: int = 24
    maximum_restore_attempts: int = 5
    maximum_line_search_steps: int = 10
    guard_goal_fraction: float = 0.30
    guard_goal_floor: float = 2.0e-6

    def __post_init__(self) -> None:
        if self.maximum_callbacks < 2:
            raise ValueError("maximum_callbacks must be at least two")
        if not 0 < self.root_success_tolerance <= self.root_entry_tolerance:
            raise ValueError("root tolerances are inconsistent")
        if self.strict_margin_tolerance < 0:
            raise ValueError("strict margin tolerance cannot be negative")
        if self.rank_relative_tolerance <= 0 or self.slope_relative_tolerance <= 0:
            raise ValueError("rank and slope tolerances must be positive")
        if self.minimum_pair_score <= 0:
            raise ValueError("minimum pair score must be positive")
        if not (
            0
            < self.minimum_arclength_step
            <= self.initial_arclength_step
            <= self.maximum_arclength_step
        ):
            raise ValueError("arclength steps are inconsistent")
        if not 0 < self.step_shrink < 1 or self.step_growth <= 1:
            raise ValueError("step adaptation factors are invalid")
        if min(
            self.maximum_path_steps,
            self.maximum_corrector_steps,
            self.maximum_restore_steps,
            self.maximum_restore_attempts,
            self.maximum_line_search_steps,
        ) < 1:
            raise ValueError("all iteration caps must be positive")
        if not 0 < self.guard_goal_fraction <= 1 or self.guard_goal_floor <= 0:
            raise ValueError("guard goal parameters are invalid")


@dataclass(slots=True)
class Counters:
    callbacks: int = 0
    pair_rank_tests: int = 0
    eligible_pairs: int = 0
    path_predictors: int = 0
    corrector_iterations: int = 0
    accepted_path_steps: int = 0
    rejected_path_steps: int = 0
    swapped_endpoint_solves: int = 0
    restore_attempts: int = 0
    restore_iterations: int = 0
    source_replays: int = 0
    bound_rejections: int = 0
    rank_failures: int = 0
    linear_failures: int = 0


@dataclass(frozen=True, slots=True)
class PairCertificate:
    dropped_row: int
    guard_row: int
    kept_rank: int
    kept_rcond: float
    swapped_rcond: float
    guard_tangent_slope: float
    dropped_row_slope: float
    score: float


@dataclass(frozen=True, slots=True)
class Outcome:
    endpoint: Array
    status: str
    residual_inf: float
    source_valid: bool
    certificate: PairCertificate | None
    initial_guard_margin: float
    final_guard_margin: float
    counters: Counters


@dataclass(frozen=True, slots=True)
class _State:
    point: Array
    residual: Array
    margins: Array
    finite: bool
    source_valid: bool
    jacobian: Array | None
    margin_jacobian: Array | None
    provenance: Array


class _Runtime:
    def __init__(
        self,
        evaluator: Evaluator,
        dimension: int,
        counters: Counters,
        maximum_callbacks: int,
    ) -> None:
        self.evaluator = evaluator
        self.dimension = dimension
        self.counters = counters
        self.maximum_callbacks = maximum_callbacks
        self.expected_margin_dimension: int | None = None
        self.cache: dict[bytes, _State] = {}

    def bind_margin_dimension(self, dimension: int) -> None:
        if dimension < 1:
            raise ValueError("at least one smooth margin is required")
        if self.expected_margin_dimension is not None:
            raise RuntimeError("margin dimension is already bound")
        self.expected_margin_dimension = dimension

    def observe(self, point: Array, *, fresh: bool = False) -> _State:
        x = np.asarray(point, dtype=float)
        if x.shape != (self.dimension,):
            raise ValueError("point dimension mismatch")
        key = x.tobytes()
        cached = self.cache.get(key)
        if cached is not None and not fresh:
            return cached
        if self.counters.callbacks >= self.maximum_callbacks:
            return _State(
                x.copy(),
                np.full(self.dimension, math.nan),
                np.asarray([], dtype=float),
                False,
                False,
                None,
                None,
                np.asarray([], dtype=bool),
            )
        self.counters.callbacks += 1
        try:
            raw = self.evaluator(x.copy())
            residual = np.asarray(raw.residual, dtype=float)
            margins = np.asarray(raw.smooth_margins, dtype=float)
            provenance = np.asarray(raw.smooth_margin_provenance, dtype=bool)
            jacobian = (
                None
                if raw.residual_jacobian is None
                else np.asarray(raw.residual_jacobian, dtype=float)
            )
            margin_jacobian = (
                None
                if raw.margin_jacobian is None
                else np.asarray(raw.margin_jacobian, dtype=float)
            )
            finite = bool(
                raw.finite
                and residual.shape == (self.dimension,)
                and margins.ndim == 1
                and (
                    self.expected_margin_dimension is None
                    or margins.shape == (self.expected_margin_dimension,)
                )
                and provenance.shape == margins.shape
                and np.all(np.isfinite(residual))
                and np.all(np.isfinite(margins))
            )
            if jacobian is not None and jacobian.shape != (
                self.dimension,
                self.dimension,
            ):
                jacobian = None
            if margin_jacobian is not None and margin_jacobian.shape != (
                margins.size,
                self.dimension,
            ):
                margin_jacobian = None
            if jacobian is not None and not np.all(np.isfinite(jacobian)):
                jacobian = None
            if margin_jacobian is not None and not np.all(
                np.isfinite(margin_jacobian)
            ):
                margin_jacobian = None
        except Exception:
            residual = np.full(self.dimension, math.nan)
            margins = np.asarray([], dtype=float)
            provenance = np.asarray([], dtype=bool)
            jacobian = None
            margin_jacobian = None
            finite = False
            raw = None
        state = _State(
            x.copy(),
            residual.copy(),
            margins.copy(),
            finite,
            bool(finite and raw is not None and raw.source_valid),
            None if jacobian is None else jacobian.copy(),
            None if margin_jacobian is None else margin_jacobian.copy(),
            provenance.copy(),
        )
        self.cache[key] = state
        return state


def integration_contract() -> dict[str, object]:
    """Return the non-negotiable future-worker integration constraints."""

    return {
        "proposal_only": True,
        "fresh_source_replay_required": True,
        "additive_lane_only": True,
        "minimum_untouched_full_support_share": 0.25,
        "may_infer_coordinate_bounds": False,
        "may_read_target_or_truth": False,
    }


def _coordinate_inputs(
    start: Sequence[float],
    scale: Sequence[float],
    lower: Sequence[float],
    upper: Sequence[float],
) -> tuple[Array, Array, Array, Array]:
    x = np.asarray(start, dtype=float).copy()
    metric = np.asarray(scale, dtype=float).copy()
    lo = np.asarray(lower, dtype=float).copy()
    hi = np.asarray(upper, dtype=float).copy()
    if x.ndim != 1 or x.size == 0:
        raise ValueError("start must be a non-empty vector")
    if metric.shape != x.shape or lo.shape != x.shape or hi.shape != x.shape:
        raise ValueError("coordinate vector shape mismatch")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(metric)):
        raise ValueError("start and scale must be finite")
    if np.any(metric <= 0) or np.any(lo > hi):
        raise ValueError("invalid scale or source bounds")
    if np.any(x < lo) or np.any(x > hi):
        raise ValueError("start violates literal source bounds")
    return x, metric, lo, hi


def _inside(point: Array, lower: Array, upper: Array) -> bool:
    return bool(np.all(point >= lower) and np.all(point <= upper))


def _rank_and_rcond(matrix: Array, tolerance: float) -> tuple[int, float]:
    if matrix.size == 0:
        return 0, 0.0
    try:
        _q, triangular, _pivots = pivoted_qr(
            matrix,
            mode="economic",
            pivoting=True,
            check_finite=False,
        )
    except Exception:
        return 0, 0.0
    diagonal = np.abs(np.diag(triangular))
    if diagonal.size == 0 or not np.all(np.isfinite(diagonal)):
        return 0, 0.0
    lead = float(np.max(diagonal))
    if lead <= 0:
        return 0, 0.0
    threshold = tolerance * lead
    rank = int(np.count_nonzero(diagonal > threshold))
    positive = diagonal[diagonal > threshold]
    rcond = float(np.min(positive) / lead) if positive.size else 0.0
    return rank, rcond


def _null_tangent(matrix: Array, tolerance: float) -> tuple[Array | None, int, float]:
    if matrix.shape == (0, 1):
        # Dropping the sole equation of a scalar square system leaves the
        # one-dimensional ambient line.  Its tangent and conditioning are
        # exact; treating the empty singular-value list as failure would make
        # the generic codimension-exchange rule arbitrarily exclude n=1.
        return np.ones(1), 0, 1.0
    try:
        _u, singular, vt = np.linalg.svd(matrix, full_matrices=True)
    except np.linalg.LinAlgError:
        return None, 0, 0.0
    if singular.size == 0 or not np.all(np.isfinite(singular)):
        return None, 0, 0.0
    lead = max(float(singular[0]), np.finfo(float).tiny)
    rank = int(np.count_nonzero(singular > tolerance * lead))
    rcond = float(singular[-1] / lead) if singular[-1] > 0 else 0.0
    if rank != matrix.shape[0] or vt.shape[0] <= rank:
        return None, rank, rcond
    tangent = vt[-1].copy()
    norm = float(np.linalg.norm(tangent))
    if not math.isfinite(norm) or norm <= 0:
        return None, rank, rcond
    return tangent / norm, rank, rcond


def _select_pair(
    state: _State,
    scale: Array,
    configuration: Configuration,
    counters: Counters,
) -> tuple[PairCertificate, Array, Array, Array] | None:
    dimension = state.point.size
    if (
        state.residual.shape != (dimension,)
        or state.jacobian is None
        or state.jacobian.shape != (dimension, dimension)
        or state.margin_jacobian is None
        or not state.margins.size
    ):
        return None
    jacobian_z = state.jacobian * scale[None, :]
    row_scale = np.linalg.norm(jacobian_z, axis=1)
    if np.any(~np.isfinite(row_scale)) or np.any(row_scale <= 1.0e-14):
        return None
    normalized_j = jacobian_z / row_scale[:, None]
    full_rank, _ = _rank_and_rcond(
        normalized_j, configuration.rank_relative_tolerance
    )
    if full_rank != dimension:
        counters.rank_failures += 1
        return None
    gradient_z = state.margin_jacobian * scale[None, :]
    candidates: list[tuple[float, PairCertificate, Array, Array]] = []
    violated = np.flatnonzero(
        state.provenance
        & (state.margins <= configuration.strict_margin_tolerance)
    )
    for guard_row in violated:
        gradient = gradient_z[guard_row]
        gradient_norm = float(np.linalg.norm(gradient))
        if not math.isfinite(gradient_norm) or gradient_norm <= 1.0e-14:
            continue
        normalized_gradient = gradient / gradient_norm
        for dropped_row in range(dimension):
            counters.pair_rank_tests += 1
            keep = np.delete(normalized_j, dropped_row, axis=0)
            tangent, kept_rank, kept_rcond = _null_tangent(
                keep, configuration.rank_relative_tolerance
            )
            if tangent is None or kept_rank != dimension - 1:
                continue
            guard_slope = abs(float(normalized_gradient @ tangent))
            dropped_slope = abs(float(normalized_j[dropped_row] @ tangent))
            if (
                guard_slope <= configuration.slope_relative_tolerance
                or dropped_slope <= configuration.slope_relative_tolerance
            ):
                continue
            swapped = np.vstack((keep, normalized_gradient))
            swapped_rank, swapped_rcond = _rank_and_rcond(
                swapped, configuration.rank_relative_tolerance
            )
            if swapped_rank != dimension or swapped_rcond <= 0:
                continue
            score = float(
                guard_slope
                * dropped_slope
                * math.sqrt(max(kept_rcond, 0.0) * swapped_rcond)
            )
            if score < configuration.minimum_pair_score:
                continue
            certificate = PairCertificate(
                dropped_row=dropped_row,
                guard_row=int(guard_row),
                kept_rank=kept_rank,
                kept_rcond=kept_rcond,
                swapped_rcond=swapped_rcond,
                guard_tangent_slope=guard_slope,
                dropped_row_slope=dropped_slope,
                score=score,
            )
            candidates.append((score, certificate, tangent, row_scale))
    counters.eligible_pairs += len(candidates)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[0]
    if len(candidates) > 1 and math.isclose(
        best[0], candidates[1][0], rel_tol=1.0e-12, abs_tol=1.0e-14
    ):
        # Numerical ties are representation-sensitive.  Failing closed is
        # safer than silently using residual declaration order as a router.
        return None
    certificate = best[1]
    tangent = best[2]
    if float(gradient_z[certificate.guard_row] @ tangent) < 0:
        tangent = -tangent
    keep_rows = np.asarray(
        [index for index in range(dimension) if index != certificate.dropped_row],
        dtype=int,
    )
    return certificate, tangent, best[3], keep_rows


def _linear_step(jacobian: Array, rhs: Array, counters: Counters) -> Array | None:
    try:
        step, _residuals, _rank, _singular = np.linalg.lstsq(
            jacobian, rhs, rcond=None
        )
    except np.linalg.LinAlgError:
        counters.linear_failures += 1
        return None
    if not np.all(np.isfinite(step)):
        counters.linear_failures += 1
        return None
    return step


def _correct_arclength(
    runtime: _Runtime,
    predicted_z: Array,
    tangent: Array,
    keep_rows: Array,
    scale: Array,
    row_scale: Array,
    lower: Array,
    upper: Array,
    configuration: Configuration,
    counters: Counters,
) -> tuple[Array | None, _State | None, int]:
    z = predicted_z.copy()
    for iteration in range(configuration.maximum_corrector_steps):
        point = scale * z
        if not _inside(point, lower, upper):
            counters.bound_rejections += 1
            return None, None, iteration
        state = runtime.observe(point)
        if not state.finite or state.jacobian is None:
            return None, None, iteration
        residual = np.concatenate(
            (
                state.residual[keep_rows] / row_scale[keep_rows],
                [float(tangent @ (z - predicted_z))],
            )
        )
        norm = float(np.linalg.norm(residual, ord=np.inf))
        if norm <= configuration.root_success_tolerance:
            return z, state, iteration + 1
        jacobian = np.vstack(
            (
                (state.jacobian[keep_rows] * scale[None, :])
                / row_scale[keep_rows, None],
                tangent,
            )
        )
        delta = _linear_step(jacobian, -residual, counters)
        if delta is None:
            return None, None, iteration + 1
        accepted = False
        alpha = 1.0
        for _ in range(configuration.maximum_line_search_steps):
            trial_z = z + alpha * delta
            trial_point = scale * trial_z
            if not _inside(trial_point, lower, upper):
                alpha *= 0.5
                continue
            trial = runtime.observe(trial_point)
            if not trial.finite:
                alpha *= 0.5
                continue
            trial_residual = np.concatenate(
                (
                    trial.residual[keep_rows] / row_scale[keep_rows],
                    [float(tangent @ (trial_z - predicted_z))],
                )
            )
            if np.linalg.norm(trial_residual) < np.linalg.norm(residual):
                z = trial_z
                accepted = True
                break
            alpha *= 0.5
        counters.corrector_iterations += 1
        if not accepted:
            return None, None, iteration + 1
    return None, None, configuration.maximum_corrector_steps


def _solve_square(
    runtime: _Runtime,
    initial_z: Array,
    residual_and_jacobian: Callable[[_State], tuple[Array, Array]],
    scale: Array,
    lower: Array,
    upper: Array,
    tolerance: float,
    maximum_steps: int,
    configuration: Configuration,
    counters: Counters,
    restore: bool,
) -> tuple[Array | None, _State | None]:
    z = initial_z.copy()
    for _ in range(maximum_steps):
        point = scale * z
        if not _inside(point, lower, upper):
            counters.bound_rejections += 1
            return None, None
        state = runtime.observe(point)
        if not state.finite or state.jacobian is None:
            return None, None
        residual, jacobian = residual_and_jacobian(state)
        if restore:
            counters.restore_iterations += 1
        if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(jacobian)):
            return None, None
        if np.linalg.norm(residual, ord=np.inf) <= tolerance:
            return z, state
        delta = _linear_step(jacobian, -residual, counters)
        if delta is None:
            return None, None
        accepted = False
        alpha = 1.0
        base_norm = float(np.linalg.norm(residual))
        for _line in range(configuration.maximum_line_search_steps):
            trial_z = z + alpha * delta
            trial_point = scale * trial_z
            if not _inside(trial_point, lower, upper):
                alpha *= 0.5
                continue
            trial = runtime.observe(trial_point)
            if not trial.finite or trial.jacobian is None:
                alpha *= 0.5
                continue
            trial_residual, _trial_jacobian = residual_and_jacobian(trial)
            if np.all(np.isfinite(trial_residual)) and np.linalg.norm(
                trial_residual
            ) < base_norm:
                z = trial_z
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            return None, None
    return None, None


def _outcome(
    state: _State,
    status: str,
    certificate: PairCertificate | None,
    initial_guard: float,
    guard_row: int | None,
    counters: Counters,
) -> Outcome:
    residual_inf = (
        float(np.linalg.norm(state.residual, ord=np.inf))
        if state.residual.size and np.all(np.isfinite(state.residual))
        else math.inf
    )
    final_guard = (
        float(state.margins[guard_row])
        if guard_row is not None and guard_row < state.margins.size
        else math.nan
    )
    return Outcome(
        state.point.copy(),
        status,
        residual_inf,
        bool(state.source_valid),
        certificate,
        initial_guard,
        final_guard,
        counters,
    )


def solve(
    evaluator: Evaluator,
    *,
    start: Sequence[float],
    scale: Sequence[float],
    lower: Sequence[float],
    upper: Sequence[float],
    configuration: Configuration | None = None,
) -> Outcome:
    """Run one proposal-only equation-swap continuation attempt."""

    config = configuration or Configuration()
    point, metric, lo, hi = _coordinate_inputs(start, scale, lower, upper)
    counters = Counters()
    runtime = _Runtime(evaluator, point.size, counters, config.maximum_callbacks)
    initial = runtime.observe(point)
    initial_guard = (
        float(np.min(initial.margins)) if initial.margins.size else math.nan
    )
    if not initial.finite:
        return _outcome(
            initial, "nonfinite_start", None, initial_guard, None, counters
        )
    if not initial.margins.size:
        return _outcome(
            initial, "no_smooth_guard_rows", None, initial_guard, None, counters
        )
    runtime.bind_margin_dimension(initial.margins.size)
    if np.linalg.norm(initial.residual, ord=np.inf) > config.root_entry_tolerance:
        return _outcome(
            initial, "not_at_source_root", None, initial_guard, None, counters
        )
    if initial.source_valid:
        return _outcome(
            initial, "already_source_valid", None, initial_guard, None, counters
        )
    selected = _select_pair(initial, metric, config, counters)
    if selected is None:
        return _outcome(
            initial,
            "no_certified_equation_guard_pair",
            None,
            initial_guard,
            None,
            counters,
        )
    certificate, tangent, row_scale, keep_rows = selected
    guard_row = certificate.guard_row
    margin_scale = max(
        abs(float(initial.margins[guard_row])),
        float(np.linalg.norm(initial.margin_jacobian[guard_row] * metric)),
        np.finfo(float).tiny,
    )
    initial_normalized_deficit = max(
        -float(initial.margins[guard_row]) / margin_scale, 0.0
    )
    goal_normalized = max(
        config.guard_goal_floor,
        config.guard_goal_fraction * max(initial_normalized_deficit, 1.0e-6),
    )
    goal_margin = goal_normalized * margin_scale
    current_z = point / metric
    current_state = initial
    step = config.initial_arclength_step
    restore_attempts = 0
    swapped_ready = False

    def swapped_system(state: _State) -> tuple[Array, Array]:
        if (
            state.margin_jacobian is None
            or guard_row >= state.provenance.size
            or not state.provenance[guard_row]
        ):
            return np.full(point.size, math.nan), np.full(
                (point.size, point.size), math.nan
            )
        residual = np.concatenate(
            (
                state.residual[keep_rows] / row_scale[keep_rows],
                [(state.margins[guard_row] - goal_margin) / margin_scale],
            )
        )
        jacobian = np.vstack(
            (
                (state.jacobian[keep_rows] * metric[None, :])
                / row_scale[keep_rows, None],
                (state.margin_jacobian[guard_row] * metric) / margin_scale,
            )
        )
        return residual, jacobian

    def original_system(state: _State) -> tuple[Array, Array]:
        residual = state.residual / row_scale
        jacobian = (state.jacobian * metric[None, :]) / row_scale[:, None]
        return residual, jacobian

    for _path_index in range(config.maximum_path_steps):
        counters.path_predictors += 1
        predicted_z = current_z + step * tangent
        corrected_z, corrected_state, iterations = _correct_arclength(
            runtime,
            predicted_z,
            tangent,
            keep_rows,
            metric,
            row_scale,
            lo,
            hi,
            config,
            counters,
        )
        if corrected_z is None or corrected_state is None:
            counters.rejected_path_steps += 1
            step *= config.step_shrink
            if step < config.minimum_arclength_step:
                return _outcome(
                    current_state,
                    "path_corrector_stalled",
                    certificate,
                    initial_guard,
                    guard_row,
                    counters,
                )
            continue
        counters.accepted_path_steps += 1
        current_z = corrected_z
        current_state = corrected_state
        normalized_keep = (
            current_state.jacobian[keep_rows] * metric[None, :]
        ) / row_scale[keep_rows, None]
        next_tangent, rank, _rcond = _null_tangent(
            normalized_keep, config.rank_relative_tolerance
        )
        if next_tangent is None or rank != point.size - 1:
            counters.rank_failures += 1
            return _outcome(
                current_state,
                "path_rank_lost",
                certificate,
                initial_guard,
                guard_row,
                counters,
            )
        if float(next_tangent @ tangent) < 0:
            next_tangent = -next_tangent
        tangent = next_tangent
        if iterations <= 3:
            step = min(config.maximum_arclength_step, step * config.step_growth)
        elif iterations >= config.maximum_corrector_steps - 1:
            step = max(config.minimum_arclength_step, step * config.step_shrink)

        if current_state.margins[guard_row] < goal_margin:
            continue
        if not swapped_ready:
            counters.swapped_endpoint_solves += 1
            swapped_z, swapped_state = _solve_square(
                runtime,
                current_z,
                swapped_system,
                metric,
                lo,
                hi,
                config.root_success_tolerance,
                config.maximum_corrector_steps,
                config,
                counters,
                restore=False,
            )
            if swapped_z is not None and swapped_state is not None:
                current_z = swapped_z
                current_state = swapped_state
                swapped_ready = True
            else:
                # The proposal is specifically an equation swap.  If the
                # replacement system cannot be solved, do not silently turn
                # this into an unrelated dropped-row warm start.
                continue
        if restore_attempts >= config.maximum_restore_attempts:
            continue
        restore_attempts += 1
        counters.restore_attempts += 1
        restored_z, restored_state = _solve_square(
            runtime,
            current_z,
            original_system,
            metric,
            lo,
            hi,
            config.root_success_tolerance,
            config.maximum_restore_steps,
            config,
            counters,
            restore=True,
        )
        if restored_z is None or restored_state is None:
            continue
        # Mandatory untouched source replay.  The swapped or restored systems
        # are never answer authority.
        counters.source_replays += 1
        replay = runtime.observe(metric * restored_z, fresh=True)
        residual_inf = float(np.linalg.norm(replay.residual, ord=np.inf))
        if (
            replay.finite
            and replay.source_valid
            and replay.residual.shape == (point.size,)
            and residual_inf <= config.root_success_tolerance
        ):
            return _outcome(
                replay,
                "source_root_recovered",
                certificate,
                initial_guard,
                guard_row,
                counters,
            )
    return _outcome(
        current_state,
        "no_source_root_recovered",
        certificate,
        initial_guard,
        guard_row,
        counters,
    )
