"""Lexicographic feasibility-restoration/filter trust-region prototype.

The kernel works only in the original source variables.  A caller supplies an
original-coordinate start, a positive per-start numerical scale, and the
literal source bounds.  Missing source bounds remain infinite.  No geometry
condition, variable, equation, guard, or branch is rewritten or removed.

The mechanism differs from the older scalar two-coordinate filter in three
ways.  It ranks states lexicographically by (1) whether the original evaluator
can construct a finite state, (2) the complete sorted vector of individual
signed-margin violations, and (3) the complete sorted vector of normalized
equation residuals.  At an infeasible point it first computes a rank-revealing
minimum-norm normal restoration step, then solves for equation progress in the
null space of the active restoration rows.  A small nondominance filter and a
trust region globalize the step.  CPQR is attempted first and a filtered SVD
is the rank-deficient fallback.

All endpoint authority remains with a fresh replay of the untouched original
evaluator in the experiment worker.  This file has no access to problem IDs,
families, historical outcomes, truth, or known target counts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np
from scipy import linalg


HERE = Path(__file__).resolve().parent
VECTOR_CORE = HERE.parent / "ad_vector_filter_kernel/candidate.py"
VECTOR_CORE_SHA256 = "021d90c5c46a8308b71cb04db1a6ae30577f018bc21c7556b0d372e7a0335dee"


def _load_vector_core():
    if hashlib.sha256(VECTOR_CORE.read_bytes()).hexdigest() != VECTOR_CORE_SHA256:
        raise RuntimeError("source-only vector-program core changed")
    name = "geotarget_exp008_dev41_restoration_filter_vector_core"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, VECTOR_CORE)
    if specification is None or specification.loader is None:
        raise ImportError(VECTOR_CORE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CORE = _load_vector_core()
MarginProgram = CORE.MarginProgram
compile_program = CORE.compile_program

CANDIDATE = "source_literal_lexicographic_restoration_filter_rrqr"


@dataclass(frozen=True)
class Configuration:
    name: str = CANDIDATE
    fd_relative_step: float = 2.0e-7
    initial_trust_radius: float = 1.0
    minimum_trust_radius: float = 1.0e-9
    maximum_trust_radius: float = 64.0
    maximum_iterations: int = 64
    rank_rtol: float = 3.0e-10
    equality_goal_inf: float = 1.0e-8
    margin_tolerance: float = 1.0e-12
    active_margin_band: float = 1.0e-6
    filter_relative_tolerance: float = 1.0e-5
    filter_absolute_tolerance: float = 1.0e-11
    parity_rtol: float = 2.0e-8
    parity_atol: float = 2.0e-10
    sufficient_decrease: float = 1.0e-4
    maximum_filter_entries: int = 32


CONFIGURATION = Configuration()
CONFIGURATIONS = {CANDIDATE: CONFIGURATION}


@dataclass(frozen=True)
class CandidateOutcome:
    endpoint: np.ndarray
    status: str
    counters: Mapping[str, int]


@dataclass
class _LexState:
    base: object
    finite_construction: bool
    normalized_equality: np.ndarray
    violation_vector: np.ndarray

    @property
    def x(self) -> np.ndarray:
        return np.asarray(self.base.x, dtype=float)

    @property
    def semantics_valid(self) -> bool:
        return bool(self.base.semantics_valid)

    @property
    def equality_inf(self) -> float:
        return float(self.base.equality_inf)


@dataclass(frozen=True)
class _FilterEntry:
    finite_rank: int
    violations: np.ndarray
    normalized_residual: np.ndarray


class _ObservationTracker:
    """Transparent evaluator proxy used to retain the charged observation."""

    def __init__(self, source: object) -> None:
        self._source = source
        self.last_observation: object | None = None

    def evaluate(self, point: Sequence[float]):
        observation = self._source.evaluate(np.asarray(point, dtype=float))
        self.last_observation = observation
        return observation

    def progressive_residual(self, point: Sequence[float]):
        return self._source.progressive_residual(np.asarray(point, dtype=float))

    def __getattr__(self, name: str):
        return getattr(self._source, name)


def _initial_counters() -> dict[str, int]:
    return {
        "starts_attempted": 1,
        "iterations": 0,
        "finite_construction_entries": 0,
        "restoration_steps": 0,
        "restoration_rows": 0,
        "nullspace_tangential_steps": 0,
        "construction_escape_steps": 0,
        "root_steps": 0,
        "accepted_steps": 0,
        "rejected_steps": 0,
        "filter_rejections": 0,
        "lexicographic_rejections": 0,
        "analytic_equality_rows": 0,
        "equality_fd_fallback_rows": 0,
        "analytic_guard_margin_rows": 0,
        "guard_margin_parity_fallback_rows": 0,
        "source_bound_margin_rows": 0,
        "analytic_hard_margin_rows": 0,
        "hard_margin_parity_fallback_rows": 0,
        "semantic_fallback_rows": 0,
        "progressive_equality_calls": 0,
        "fd_direction_evaluations": 0,
        "cpqr_steps": 0,
        "svd_steps": 0,
        "rank_deficient_steps": 0,
        "nullspace_svd_steps": 0,
        "linear_failures": 0,
        "fraction_to_boundary_steps": 0,
        "reported_safe_endpoint": 0,
        "budget_stops": 0,
        "deadline_stops": 0,
    }


def _same_source_array(left: np.ndarray, right: np.ndarray) -> bool:
    return bool(left.shape == right.shape and np.array_equal(left, right))


def _make_lex_state(
    tracker: _ObservationTracker,
    program: MarginProgram,
    point: np.ndarray,
    equality_scale: np.ndarray | None,
    configuration: Configuration,
    counters: dict[str, int],
) -> tuple[_LexState, np.ndarray]:
    base = CORE.CORE._make_state(
        tracker, program, np.asarray(point, dtype=float), configuration, counters
    )
    observation = tracker.last_observation
    finite = bool(observation is not None and getattr(observation, "finite", False))
    equality = np.asarray(base.equality, dtype=float)
    if equality_scale is None:
        equality_scale = np.maximum(1.0, np.abs(equality))
    normalized = np.abs(equality) / equality_scale
    normalized[~np.isfinite(normalized)] = math.inf
    violations = np.maximum(0.0, -np.asarray(base.margins, dtype=float))
    violations[~np.isfinite(violations)] = math.inf
    # Worst-first sorting makes the comparison independent of compiler row
    # order while retaining the entire violation/residual vectors.
    return (
        _LexState(
            base=base,
            finite_construction=finite,
            normalized_equality=np.sort(normalized)[::-1],
            violation_vector=np.sort(violations)[::-1],
        ),
        equality_scale,
    )


def _compare_vectors(
    left: np.ndarray,
    right: np.ndarray,
    configuration: Configuration,
) -> int:
    if left.shape != right.shape:
        raise ValueError("lexicographic vectors have different shapes")
    for candidate, incumbent in zip(left, right, strict=True):
        tolerance = configuration.filter_absolute_tolerance + (
            configuration.filter_relative_tolerance
            * max(1.0, abs(float(incumbent)))
        )
        if float(candidate) < float(incumbent) - tolerance:
            return -1
        if float(candidate) > float(incumbent) + tolerance:
            return 1
    return 0


def _lex_compare(
    left: _LexState,
    right: _LexState,
    configuration: Configuration,
) -> int:
    left_rank = int(not left.finite_construction)
    right_rank = int(not right.finite_construction)
    if left_rank != right_rank:
        return -1 if left_rank < right_rank else 1
    violation = _compare_vectors(
        left.violation_vector, right.violation_vector, configuration
    )
    if violation:
        return violation
    return _compare_vectors(
        left.normalized_equality, right.normalized_equality, configuration
    )


def _entry(state: _LexState) -> _FilterEntry:
    return _FilterEntry(
        int(not state.finite_construction),
        state.violation_vector.copy(),
        state.normalized_equality.copy(),
    )


def _weakly_leq(left: np.ndarray, right: np.ndarray, tolerance: float) -> bool:
    return bool(np.all(left <= right + tolerance))


def _filter_dominated(
    state: _LexState,
    entries: Sequence[_FilterEntry],
    configuration: Configuration,
) -> bool:
    rank = int(not state.finite_construction)
    tolerance = configuration.filter_absolute_tolerance
    for old in entries:
        if old.finite_rank > rank:
            continue
        if old.finite_rank < rank:
            return True
        if _weakly_leq(old.violations, state.violation_vector, tolerance) and _weakly_leq(
            old.normalized_residual, state.normalized_equality, tolerance
        ):
            strict = bool(
                np.any(old.violations < state.violation_vector - tolerance)
                or np.any(
                    old.normalized_residual
                    < state.normalized_equality - tolerance
                )
            )
            if strict:
                return True
    return False


def _insert_filter(
    entries: list[_FilterEntry],
    state: _LexState,
    configuration: Configuration,
) -> None:
    new = _entry(state)
    tolerance = configuration.filter_absolute_tolerance
    kept: list[_FilterEntry] = []
    for old in entries:
        new_dominates = False
        if new.finite_rank < old.finite_rank:
            new_dominates = True
        elif new.finite_rank == old.finite_rank:
            new_dominates = bool(
                _weakly_leq(new.violations, old.violations, tolerance)
                and _weakly_leq(
                    new.normalized_residual, old.normalized_residual, tolerance
                )
            )
        if not new_dominates:
            kept.append(old)
    kept.append(new)
    entries[:] = kept[-configuration.maximum_filter_entries :]


def _nullspace(
    matrix: np.ndarray,
    rank_rtol: float,
    counters: dict[str, int],
) -> np.ndarray:
    columns = int(matrix.shape[1])
    if matrix.shape[0] == 0:
        return np.eye(columns)
    try:
        _u, singular, vh = linalg.svd(
            matrix, full_matrices=True, check_finite=False
        )
        counters["nullspace_svd_steps"] += 1
        if singular.size:
            cutoff = rank_rtol * max(1.0, float(singular[0]))
            rank = int(np.count_nonzero(singular > cutoff))
        else:
            rank = 0
        return np.asarray(vh[rank:].T, dtype=float)
    except Exception:
        counters["linear_failures"] += 1
        return np.empty((columns, 0), dtype=float)


def _restoration_step(
    state: _LexState,
    equality_jacobian: np.ndarray,
    margin_jacobian: np.ndarray,
    equality_scale: np.ndarray,
    configuration: Configuration,
    counters: dict[str, int],
) -> np.ndarray:
    violations = np.maximum(0.0, -np.asarray(state.base.margins, dtype=float))
    active = np.flatnonzero(
        violations > configuration.margin_tolerance
    )
    if active.size == 0:
        active = np.flatnonzero(
            np.asarray(state.base.margins, dtype=float)
            < configuration.active_margin_band
        )
    normal = np.zeros(equality_jacobian.shape[1], dtype=float)
    active_matrix = np.empty((0, equality_jacobian.shape[1]), dtype=float)
    if active.size:
        active_matrix = np.asarray(margin_jacobian[active], dtype=float)
        row_norm = np.maximum(1.0, np.linalg.norm(active_matrix, axis=1))
        normal = CORE.CORE._minimum_norm_step(
            active_matrix / row_norm[:, None],
            violations[active] / row_norm,
            configuration.rank_rtol,
            counters,
        )
        counters["restoration_rows"] += int(active.size)

    scaled_jacobian = equality_jacobian / equality_scale[:, None]
    scaled_residual = np.asarray(state.base.equality, dtype=float) / equality_scale
    null = _nullspace(active_matrix, configuration.rank_rtol, counters)
    if null.shape[1]:
        tangential = CORE.CORE._minimum_norm_step(
            scaled_jacobian @ null,
            -scaled_residual - scaled_jacobian @ normal,
            configuration.rank_rtol,
            counters,
        )
        normal = normal + null @ tangential
        counters["nullspace_tangential_steps"] += 1

    if not np.any(np.isfinite(normal)) or float(np.linalg.norm(normal)) == 0.0:
        # Undefined constructions often expose no differentiable semantic row.
        # The source equation model is then the only general, answer-blind
        # direction available; the original evaluator still decides entry.
        normal = CORE.CORE._minimum_norm_step(
            scaled_jacobian,
            -scaled_residual,
            configuration.rank_rtol,
            counters,
        )
        counters["construction_escape_steps"] += 1
    counters["restoration_steps"] += 1
    return np.asarray(normal, dtype=float)


def solve_local(
    evaluator_case: object,
    program: MarginProgram,
    configuration: Configuration,
    start_original: Sequence[float],
    *,
    per_start_scale: Sequence[float],
    source_lower: Sequence[float],
    source_upper: Sequence[float],
    max_callbacks: int,
    deadline_monotonic: float,
) -> CandidateOutcome:
    """Run one original-coordinate lane with literal source bounds only."""

    dimension = int(program.dimension)
    start = np.asarray(start_original, dtype=float)
    scale = np.asarray(per_start_scale, dtype=float)
    lower = np.asarray(source_lower, dtype=float)
    upper = np.asarray(source_upper, dtype=float)
    shape = (dimension,)
    if any(array.shape != shape for array in (start, scale, lower, upper)):
        raise ValueError("start, scale, and source bounds must match source dimension")
    if not np.all(np.isfinite(start)):
        raise ValueError("original-coordinate start must be finite")
    if not np.all(np.isfinite(scale)) or np.any(scale <= 0.0):
        raise ValueError("per-start numerical scale must be finite and positive")
    if np.any(np.isnan(lower)) or np.any(np.isnan(upper)) or np.any(lower >= upper):
        raise ValueError("literal source bounds are malformed")
    if not _same_source_array(lower, np.asarray(program.lower, dtype=float)) or not _same_source_array(
        upper, np.asarray(program.upper, dtype=float)
    ):
        raise ValueError("caller bounds differ from literal source bounds")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")

    counters = _initial_counters()
    tracker = _ObservationTracker(evaluator_case)
    center = start.copy()
    lower_working = (lower - center) / scale
    upper_working = (upper - center) / scale
    initial = np.minimum(np.maximum(start, lower), upper)
    try:
        current, equality_scale = _make_lex_state(
            tracker, program, initial, None, configuration, counters
        )
    except Exception as error:
        if error.__class__.__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(initial.copy(), "budget_before_start", counters)
        raise

    best = current
    filter_entries = [_entry(current)]
    radius = configuration.initial_trust_radius
    stagnation = 0

    for _iteration in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if current.semantics_valid and current.equality_inf <= configuration.equality_goal_inf:
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1
        try:
            equality_jacobian, margin_jacobian = CORE.CORE._fill_fd_rows(
                tracker,
                program,
                current.base,
                center,
                scale,
                lower_working,
                upper_working,
                configuration,
                counters,
            )
        except Exception as error:
            if error.__class__.__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["linear_failures"] += 1
            break

        infeasible = bool(
            not current.finite_construction
            or not current.semantics_valid
            or np.any(
                np.asarray(current.base.margins, dtype=float)
                < -configuration.margin_tolerance
            )
        )
        if infeasible:
            step = _restoration_step(
                current,
                equality_jacobian,
                margin_jacobian,
                equality_scale,
                configuration,
                counters,
            )
        else:
            scaled_jacobian = equality_jacobian / equality_scale[:, None]
            scaled_residual = np.asarray(current.base.equality, dtype=float) / equality_scale
            step = CORE.CORE._minimum_norm_step(
                scaled_jacobian,
                -scaled_residual,
                configuration.rank_rtol,
                counters,
            )
            counters["root_steps"] += 1

        step_norm = float(np.linalg.norm(step))
        if not math.isfinite(step_norm) or step_norm == 0.0:
            radius *= 0.25
            stagnation += 1
            if radius < configuration.minimum_trust_radius or stagnation >= 6:
                break
            continue
        if step_norm > radius:
            step *= radius / step_norm
            step_norm = radius

        if not infeasible:
            directional = margin_jacobian @ step
            margins = np.asarray(current.base.margins, dtype=float)
            threatened = np.flatnonzero(
                (directional < 0.0) & (margins + directional < 0.0)
            )
            if threatened.size:
                fractions = 0.9 * margins[threatened] / -directional[threatened]
                alpha = max(0.0, min(1.0, float(np.min(fractions))))
                step *= alpha
                step_norm *= alpha
                counters["fraction_to_boundary_steps"] += 1

        current_working = (current.x - center) / scale
        accepted = False
        for fraction in (1.0, 0.5, 0.25, 0.125):
            trial_working = np.minimum(
                np.maximum(current_working + fraction * step, lower_working),
                upper_working,
            )
            trial_point = center + scale * trial_working
            try:
                trial, _same_scale = _make_lex_state(
                    tracker,
                    program,
                    trial_point,
                    equality_scale,
                    configuration,
                    counters,
                )
            except Exception as error:
                if error.__class__.__name__ == "BudgetExceeded":
                    counters["budget_stops"] += 1
                    break
                continue
            if _lex_compare(trial, best, configuration) < 0:
                best = trial
            lex_better = _lex_compare(trial, current, configuration) < 0
            filter_ok = not _filter_dominated(
                trial, filter_entries, configuration
            )
            if lex_better and filter_ok:
                finite_entry = trial.finite_construction and not current.finite_construction
                current = trial
                _insert_filter(filter_entries, trial, configuration)
                counters["accepted_steps"] += 1
                counters["finite_construction_entries"] += int(finite_entry)
                accepted = True
                stagnation = 0
                if fraction == 1.0:
                    radius = min(configuration.maximum_trust_radius, 1.8 * radius)
                else:
                    radius = max(
                        configuration.minimum_trust_radius,
                        max(fraction * step_norm, 0.7 * radius),
                    )
                break
            counters["lexicographic_rejections"] += int(not lex_better)
            counters["filter_rejections"] += int(not filter_ok)

        if not accepted:
            counters["rejected_steps"] += 1
            stagnation += 1
            radius *= 0.3
            if radius < configuration.minimum_trust_radius or stagnation >= 8:
                break

    if best.semantics_valid and best.equality_inf <= configuration.equality_goal_inf:
        counters["reported_safe_endpoint"] = 1
        status = "safe_root"
    elif time.monotonic() >= deadline_monotonic:
        status = "deadline"
    elif counters["budget_stops"]:
        status = "budget"
    else:
        status = "stalled"
    return CandidateOutcome(best.x.copy(), status, counters)


def kernel_manifest() -> Mapping[str, object]:
    return {
        "name": CANDIDATE,
        "mechanism": (
            "finite-construction then complete guard-vector then normalized-"
            "residual lexicographic filter trust region"
        ),
        "linear_solver": "rank-revealing CPQR with filtered-SVD fallback",
        "coordinates": "original source variables",
        "hard_bounds": "literal source bounds only",
        "proposal_generation": False,
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "gauge_or_symmetry_reduction": False,
        "case_identity_family_truth_target_count_inputs": False,
        "untouched_original_evaluator_final_authority": True,
        "vector_program_sha256": VECTOR_CORE_SHA256,
    }


__all__ = [
    "CANDIDATE",
    "CONFIGURATION",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "MarginProgram",
    "compile_program",
    "kernel_manifest",
    "solve_local",
]
