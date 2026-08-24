"""Legacy-compatible helper functions for solver public orchestration."""

from __future__ import annotations

LEGACY_BACKEND_COMPAT_ONLY = True

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
import inspect
import math
from typing import Any

import time
from mpmath import mp

from geosolver.engine.standard.interpreter.guards.compile import GuardIR
from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    CandidateEval,
)
from geosolver.engine.standard.config.search_budget import SearchBudget
from geosolver.engine.standard.deduplication.remove_solutions import remove_duplicate_solutions
from geosolver.engine.standard.bounds.normalize import normalize_bounds
from geosolver.exact.identify_batch import identify_exact_answers
from geosolver.engine.standard.optimization.single_point.lbfgsb import run_lbfgsb
from geosolver.engine.standard.optimization.single_point.least_squares import run_least_squares

from geosolver.engine.standard.refinement.high_precision_compat_helpers import (
    _auto_high_precision_wrapper,
)
from geosolver.engine.standard.refinement.high_precision_projection import project_high_precision
from geosolver.engine.standard.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ensure_high_precision_mode,
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    high_precision_mode,
    precision_policy_context,
    get_current_precision_audit,
)
from geosolver.engine.standard.precision.audit.precision_audit import PrecisionAudit
from geosolver.engine.standard.precision.audit.precision_policy import default_precision_policy
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.engine.standard.precision.type_guards.should_use_mpmath import (
    mpmath_precision_threshold,
    precision_backend_name,
    should_use_mpmath,
)
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    boundary_float_to_mpf,
    BoundaryOrigin,
)
from geosolver.engine.standard.solve.legacy_solve_tolerances import (
    solve_residual_tolerance,
)
from geosolver.engine.standard.solve.apply_solve_candidate_evaluator import (
    apply_solve_candidate_evaluator,
)
from geosolver.engine.standard.solve.build_solve_candidate_ledger import (
    build_solve_candidate_ledger,
)
from geosolver.engine.standard.solve.evaluate_hp_residual import (
    evaluate_hp_residual,
)
from geosolver.engine.standard.convergence.build_convergence_criteria import (
    build_convergence_criteria,
)
from geosolver.engine.standard.convergence.check_solve_convergence import (
    check_solve_convergence,
)
from geosolver.engine.standard.solve.normalize_solutions_to_mpf import (
    normalize_solutions_to_mpf,
)
from geosolver.engine.standard.solve.boundary_normalize_solutions import (
    boundary_normalize_solutions,
)
from geosolver.engine.standard.solve.solve_boundary_convert import (
    solve_boundary_mpf,
)
from geosolver.engine.standard.solve.legacy_candidate_ops import (
    dedupe_refined_solutions,
    pick_best_solution,
    safe_objective_value,
    safe_optimize_candidate,
    safe_refine_candidate,
    select_best_candidates,
)
from geosolver.engine.standard.optimization.mp.mp_local_solve import mp_local_solve
from geosolver.engine.standard.families.cluster_solutions import (
    cluster_solutions_into_families,
)
from geosolver.engine.standard.families.check_family_set_stability import (
    check_family_set_stability,
)
from geosolver.engine.standard.families.select_family_representatives import (
    select_family_representatives,
)
from geosolver.engine.standard.families.solution_family import SolutionFamily
from geosolver.engine.standard.branches.extract_branch_signature import (
    extract_branch_signature,
)
from geosolver.engine.standard.reparameterization.build_transforms_from_guards import (
    build_transforms_from_guards,
    _count_deferred_open_bounds,
)
from geosolver.engine.standard.reparameterization.variable_transform import (
    VariableTransform,
)
from geosolver.engine.standard.solve.tracked_candidate import (
    TrackedCandidate,
    make_tracked,
    tracked_from_pool,
    tracked_values,
)
try:
    import numpy as np
    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()
_normalize_solutions_to_mpf = normalize_solutions_to_mpf

_REPARAM_SEARCH_BOUND_LOW = -8.0
_REPARAM_SEARCH_BOUND_HIGH = 8.0


def _reparameterized_search_bounds(
    transforms: Sequence[VariableTransform],
    original_bounds: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Build solver-space bounds from variable transforms."""
    bounds: list[tuple[float, float]] = []
    for transform, (lower, upper) in zip(transforms, original_bounds):
        if transform.transform_kind == "identity":
            bounds.append((float(lower), float(upper)))
        else:
            bounds.append((_REPARAM_SEARCH_BOUND_LOW, _REPARAM_SEARCH_BOUND_HIGH))
    return bounds


def _forward_transform_values(
    values: Sequence[Any],
    transforms: Sequence[VariableTransform],
) -> list[Any]:
    """Map solver-space values to original variable space."""
    mapped: list[Any] = []
    for index, (value, transform) in enumerate(zip(values, transforms)):
        mp_value = _strict_boundary_mpf(value, context=f"reparam_forward[{index}]")
        mapped.append(transform.forward(mp_value))
    return mapped


def _inverse_transform_values(
    values: Sequence[Any],
    transforms: Sequence[VariableTransform],
) -> list[Any]:
    """Map original-space values to solver variable space."""
    mapped: list[Any] = []
    for index, (value, transform) in enumerate(zip(values, transforms)):
        mp_value = _strict_boundary_mpf(value, context=f"reparam_inverse[{index}]")
        mapped.append(transform.inverse(mp_value))
    return mapped


def _forward_transform_values_float(
    values: Sequence[Any],
    transforms: Sequence[VariableTransform],
) -> list[float]:
    """Map solver-space values to original-space float values."""
    return [float(value) for value in _forward_transform_values(values, transforms)]


def _wrap_vector_function_for_solver_space(
    values: list[Any],
    *,
    func: Callable[[list[Any]], Sequence[Any]],
    transforms: Sequence[VariableTransform],
) -> list[Any]:
    """Evaluate a vector-valued function on original-space values."""
    original_values = _forward_transform_values(values, transforms)
    return list(func(original_values))


def _wrap_float_vector_function_for_solver_space(
    values: list[Any],
    *,
    func: Callable[[list[float]], Sequence[float]],
    transforms: Sequence[VariableTransform],
) -> list[float]:
    """Evaluate a float vector-valued function on original-space values."""
    original_values = _forward_transform_values_float(values, transforms)
    return [float(entry) for entry in func(original_values)]


def _wrap_answer_for_solver_space(
    values: list[Any],
    *,
    ans: Callable[[list[Any]], Any],
    transforms: Sequence[VariableTransform],
) -> Any:
    """Evaluate answer function on original-space values."""
    original_values = _forward_transform_values(values, transforms)
    return ans(original_values)


def _wrap_scalar_function_for_solver_space(
    values: list[Any],
    *,
    func: Callable[[list[Any]], Any],
    transforms: Sequence[VariableTransform],
) -> Any:
    """Evaluate a scalar function on original-space values."""
    original_values = _forward_transform_values(values, transforms)
    return func(original_values)


def _wrap_predicate_for_solver_space(
    values: list[Any],
    *,
    predicate: Callable[[list[Any]], bool],
    transforms: Sequence[VariableTransform],
) -> bool:
    """Evaluate a predicate on original-space values."""
    original_values = _forward_transform_values(values, transforms)
    return bool(predicate(original_values))


def _wrap_candidate_evaluator_for_solver_space(
    values: list[Any],
    *,
    candidate_evaluator: Callable[[list[Any]], CandidateEval],
    transforms: Sequence[VariableTransform],
) -> CandidateEval:
    """Evaluate candidate evaluator on original-space values."""
    original_values = _forward_transform_values(values, transforms)
    return candidate_evaluator(list(original_values))


def _build_solve_candidate_ledger(
    *,
    ordered: Sequence[Sequence[Any] | TrackedCandidate],
    residual_norms: Sequence[Any],
    candidate_evaluator: Callable[[list[Any]], Any] | None,
    hp_function: Callable[[list[Any]], Sequence[Any]] | None,
    hp_path_enabled: bool,
    target: Sequence[Any],
    max_items: int = 5,
) -> list[dict[str, Any]]:
    """Build candidate ledger using unified HP residual evaluator (FIX-0)."""
    return build_solve_candidate_ledger(
        ordered=ordered,
        residual_norms=residual_norms,
        candidate_evaluator=candidate_evaluator,
        hp_path_enabled=hp_path_enabled,
        f_hp=hp_function,
        hp_targets=target if hp_path_enabled and callable(hp_function) else None,
        max_items=int(max_items),
    )


_SOLVE_SEARCH_BASE_SAMPLES_MAIN = 3600
_SOLVE_SEARCH_SAMPLES_PER_DIM_MAIN = 700
_SOLVE_SEARCH_MAX_SAMPLES_MAIN = 8000
_PHASE_TIME_FLOOR_SECONDS = 1.0
_PHASE1_BUDGET_SHARE = 0.55
_PHASE2_BUDGET_SHARE = 0.45
_MIN_PHASE_BUDGET_RATIO_FLOOR = 0.1
_MIN_PHASE_FULL_EVALUATION_THRESHOLD = 3
_PHASE2_SHRINK_STRONG = 0.35
_HP_REFINE_STAGE_EXTRA_DIGITS: tuple[int, ...] = (0, 40, 80)
_PHASE2_SHRINK_MILD = 0.6
_PHASE2_SHRINK_NONE = 1.0
_PASS2_WIDE_POINTS_MIN = 20
_PASS2_WIDE_POINTS_MAX = 80
_PASS2_CANDIDATE_CAP_SMALL_N = 220
_PASS2_CANDIDATE_CAP_LARGE_N = 600
_EXTRA_BATCH_POINTS_MIN = 40
_EXTRA_BATCH_POINTS_MAX = 120
_HP_VERBOSE_MAX_SOLUTIONS = 4
_HP_VERBOSE_MAX_VALUE_CHARS = 64
_HP_REFINE_RESERVED_MIN_SECONDS = 15.0
_HP_REFINE_RESERVED_MAX_SECONDS = 90.0
_HP_REFINE_RESERVED_PER_VAR_SECONDS = 6.0
_HP_REFINE_RESERVED_MAX_TIME_RATIO = 0.45
_FINITE_SOLUTION_DEDUPE_MIN_CANDIDATES = 64
_FINITE_SOLUTION_DEDUPE_PER_SOLUTION = 16
_FINITE_SOLUTION_DEDUPE_PER_DIMENSION = 16


@contextmanager
def _temporary_override_global(fn: Callable[..., Any], name: str, value: Any) -> Iterator[None]:
    globals_dict = getattr(fn, "__globals__", None)
    if not isinstance(globals_dict, dict) or name not in globals_dict:
        yield
        return
    old_value = globals_dict[name]
    globals_dict[name] = value
    try:
        yield
    finally:
        globals_dict[name] = old_value
def _create_fast_wrapper(
    f_fast: Callable[[list[float]], list[float]] | None,
    f: Callable[[list[float]], list[float]],
) -> Callable[[list[float]], list[float]]:
    return f_fast if callable(f_fast) else f
def _auto_create_fast_function(
    f: Callable[[list[float]], list[float]],
    f_fast: Callable[[list[float]], list[float]] | None,
) -> Callable[[list[float]], list[float]]:
    return _create_fast_wrapper(f_fast, f)

def _create_sympy_precision_wrapper(
    f: Callable[[list[float]], list[float]],
    precision: int,
) -> Callable[[list[float]], list[float]]:
    wrapped = partial(_call_with_precision, f=f, precision=int(precision))
    return wrapped

def _call_with_precision(
    values: list[float],
    *,
    f: Callable[[list[float]], list[float]],
    precision: int,
) -> list[float]:
    with _temporary_override_global(f, "precision", int(precision)):
        return list(f(values))

def resolve_high_precision_function(
    f: Callable[[list[float]], list[float]],
    f_mp: Callable[[list[float]], list[float]] | None,
    precision: int,
) -> Callable[[list[float]], list[float]]:
    if callable(f_mp):
        return f_mp
    return _auto_high_precision_wrapper(f, int(precision))

def _print_high_precision_solutions(
    solutions: Sequence[Sequence[float]],
    *,
    verbose: bool,
) -> None:
    if not verbose:
        return
    if not solutions:
        return
    shown = min(len(solutions), int(_HP_VERBOSE_MAX_SOLUTIONS))
    for index, solution in enumerate(solutions[:shown], start=1):
        rendered = [_truncate_log_value(value) for value in solution]
        print(f"[solve] hp_solution[{index}] = {rendered}")
    omitted = len(solutions) - shown
    if omitted > 0:
        print(f"[solve] hp_solution: omitted {omitted} additional solutions for brevity")


def _truncate_log_value(value: Any) -> str:
    text = str(value)
    if len(text) <= int(_HP_VERBOSE_MAX_VALUE_CHARS):
        return text
    limit = max(4, int(_HP_VERBOSE_MAX_VALUE_CHARS))
    return text[: limit - 3] + "..."

def _residual_vector(
    f: Callable[[list[float]], Sequence[float]],
    v: Sequence[float],
    x: Sequence[float],
) -> list[float]:
    values = f([float(value) for value in x])
    return [float(lhs) - float(rhs) for lhs, rhs in zip(values, v)]

def _residual_objective(
    f: Callable[[list[float]], Sequence[float]],
    v: Sequence[float],
    x: Sequence[float],
) -> float:
    try:
        residuals = _residual_vector(f, v, x)
    except Exception:
        return float("inf")
    return float(sum(value * value for value in residuals))

# _strict_boundary_mpf was extracted to solve_boundary_convert.solve_boundary_mpf (WP4)
_strict_boundary_mpf = solve_boundary_mpf

def _solve_search_budget(
    n: int,
    max_solutions: int,
    find_all: bool,
) -> SearchBudget:
    _ = (max_solutions, find_all, n)
    return SearchBudget(
        base_samples=int(_SOLVE_SEARCH_BASE_SAMPLES_MAIN),
        samples_per_dimension=int(_SOLVE_SEARCH_SAMPLES_PER_DIM_MAIN),
        max_samples_with_exact=int(_SOLVE_SEARCH_MAX_SAMPLES_MAIN),
        max_samples_without_exact=int(_SOLVE_SEARCH_MAX_SAMPLES_MAIN),
    )

def _sample_count(
    n: int,
    *,
    search_budget: SearchBudget,
    has_exact: bool,
    phase_multiplier: float,
) -> int:
    base_count = int(search_budget.compute_sample_size(dimension=int(n), has_exact=bool(has_exact)))
    scaled = int(math.ceil(float(base_count) * max(0.1, float(phase_multiplier))))
    return max(1, scaled)

def _time_exceeded(started_at: float, time_limit: float | None) -> bool:
    if time_limit is None:
        return False
    return (time.time() - started_at) >= max(0.0, float(time_limit))


def _hp_refine_reserved_seconds(
    *,
    n: int,
    hp_path_enabled: bool,
    time_limit: float | None,
) -> float:
    if (not hp_path_enabled) or time_limit is None:
        return 0.0
    base = max(
        float(_HP_REFINE_RESERVED_MIN_SECONDS),
        float(_HP_REFINE_RESERVED_PER_VAR_SECONDS) * max(1.0, float(n)),
    )
    capped = min(float(_HP_REFINE_RESERVED_MAX_SECONDS), base)
    return min(capped, max(0.0, float(time_limit) * float(_HP_REFINE_RESERVED_MAX_TIME_RATIO)))


def _search_time_limit_for_refine_reservation(
    *,
    time_limit: float | None,
    reserved_seconds: float,
) -> float | None:
    if time_limit is None:
        return None
    return max(0.0, float(time_limit) - max(0.0, float(reserved_seconds)))


def _optimization_budget(
    *,
    total_candidates: int,
    started_at: float,
    time_limit: float | None,
    phase_time_share: float,
    seconds_per_candidate: float,
) -> int:
    if int(total_candidates) <= 0:
        return 0
    if time_limit is None:
        return int(total_candidates)
    elapsed = max(0.0, time.time() - float(started_at))
    remaining = max(0.0, float(time_limit) - elapsed)
    if remaining <= 0.0:
        return 0
    allocated = remaining * max(0.0, min(1.0, float(phase_time_share)))
    estimate = max(0.01, float(seconds_per_candidate))
    budget = int(max(1, allocated / estimate))
    return min(int(total_candidates), budget)


def _minimum_phase_optimization_budget(
    *,
    total_candidates: int,
    n: int,
    find_all: bool,
    max_solutions: int,
    phase: str,
) -> int:
    if int(total_candidates) <= 0:
        return 0
    if int(total_candidates) <= int(_MIN_PHASE_FULL_EVALUATION_THRESHOLD):
        return int(total_candidates)
    phase_share = _PHASE1_BUDGET_SHARE if phase == "phase1" else _PHASE2_BUDGET_SHARE
    solution_pressure = min(1.0, max(0.0, float(max_solutions) / max(1.0, float(n) * 2.0)))
    find_all_bonus = 0.1 if bool(find_all) else 0.0
    ratio = max(
        _MIN_PHASE_BUDGET_RATIO_FLOOR,
        min(1.0, float(phase_share) + solution_pressure * 0.1 + find_all_bonus),
    )
    return min(int(total_candidates), max(1, int(math.ceil(float(total_candidates) * ratio))))

def _time_budget_candidate_cap(
    *,
    total_candidates: int,
    n: int,
    started_at: float,
    time_limit: float | None,
    phase_time_share: float,
    seconds_per_candidate: float,
) -> int:
    if int(total_candidates) <= 0:
        return 0
    if time_limit is None:
        return int(total_candidates)
    elapsed = max(0.0, time.time() - float(started_at))
    remaining = max(0.0, float(time_limit) - elapsed)
    if remaining <= 0.0:
        return 0
    allocated = max(_PHASE_TIME_FLOOR_SECONDS, remaining * max(0.0, min(1.0, float(phase_time_share))))
    per_candidate = max(0.05, float(seconds_per_candidate) * max(1.0, float(n) / 3.0))
    return min(int(total_candidates), max(1, int(allocated / per_candidate)))

def _compute_improvement_rate(
    *,
    objective: Callable[[Sequence[float]], float],
    original_candidates: Sequence[Sequence[float]],
    optimized_candidates: Sequence[Sequence[float]],
) -> float:
    baseline_values = [safe_objective_value(objective, point) for point in original_candidates]
    improved_values = [safe_objective_value(objective, point) for point in optimized_candidates]
    baseline = min(value for value in baseline_values if value is not None) if any(value is not None for value in baseline_values) else None
    improved = min(value for value in improved_values if value is not None) if any(value is not None for value in improved_values) else None
    if baseline is None or improved is None or not math.isfinite(baseline) or not math.isfinite(improved):
        return 0.0
    scale = max(1.0, abs(baseline))
    raw = (baseline - improved) / scale
    if not math.isfinite(raw):
        return 0.0
    return max(0.0, min(1.0, raw))


def _dedupe_input_limit(
    *,
    n: int,
    find_all: bool,
    max_solutions: int,
) -> int | None:
    """Bound expensive post-search dedupe when the caller requested finite output."""

    if int(max_solutions) <= 0:
        return None
    solution_target = 1 if not bool(find_all) else max(1, int(max_solutions))
    return max(
        int(_FINITE_SOLUTION_DEDUPE_MIN_CANDIDATES),
        int(solution_target) * int(_FINITE_SOLUTION_DEDUPE_PER_SOLUTION),
        max(1, int(n)) * int(_FINITE_SOLUTION_DEDUPE_PER_DIMENSION),
    )


def _limit_dedupe_input(
    *,
    points: Sequence[Sequence[float]],
    objective: Callable[[Sequence[float]], float],
    n: int,
    find_all: bool,
    max_solutions: int,
) -> list[list[float]]:
    limit = _dedupe_input_limit(n=n, find_all=find_all, max_solutions=max_solutions)
    normalized = [[float(value) for value in point] for point in points]
    if limit is None or len(normalized) <= limit:
        return normalized

    def _sort_key(point: Sequence[float]) -> tuple[int, float]:
        score = safe_objective_value(objective, point)
        if score is None or not math.isfinite(float(score)):
            return (1, float("inf"))
        return (0, float(score))

    return sorted(normalized, key=_sort_key)[:limit]


def _rerank_ordered_candidates_mp(
    ordered: list[list[Any]],
    residual_norms: list[Any],
    solution_residuals_hp: list[Any],
) -> tuple[list[list[Any]], list[Any], list[Any]]:
    if not ordered or len(solution_residuals_hp) != len(ordered):
        return ordered, residual_norms, solution_residuals_hp

    ranked_indices = sorted(
        range(len(ordered)),
        key=lambda idx: (
            mp.mpf("0") if mp.isfinite(solution_residuals_hp[idx]) else mp.mpf("1"),
            solution_residuals_hp[idx],
        ),
    )
    ranked_ordered = [ordered[idx] for idx in ranked_indices]
    ranked_residual_norms = [residual_norms[idx] for idx in ranked_indices]
    ranked_hp = [solution_residuals_hp[idx] for idx in ranked_indices]
    return ranked_ordered, ranked_residual_norms, ranked_hp

def _phase2_multiplier(
    *,
    n: int,
    started_at: float,
    time_limit: float | None,
    improvement_rate: float,
) -> float:
    if improvement_rate < 0.01:
        base = _PHASE2_SHRINK_STRONG
    elif improvement_rate < 0.05:
        base = _PHASE2_SHRINK_MILD
    else:
        base = _PHASE2_SHRINK_NONE

    if time_limit is None:
        return base

    elapsed = max(0.0, time.time() - float(started_at))
    remaining = max(0.0, float(time_limit) - elapsed)
    remaining_ratio = remaining / max(1.0, float(time_limit))
    dimension_pressure = min(1.0, max(0.0, float(n) / 10.0))
    pressure = (1.0 - remaining_ratio) * (0.5 + 0.5 * dimension_pressure)
    scaled = base * max(0.2, 1.0 - pressure)
    return max(0.15, min(1.0, scaled))

def _tighten_bounds_around_point(
    bounds: Sequence[tuple[float, float]],
    point: Sequence[float],
    *,
    margin_scale: float,
    margin_min: float,
) -> list[tuple[float, float]]:
    tightened: list[tuple[float, float]] = []
    for value, (lower, upper) in zip(point, bounds):
        margin = abs(float(value)) * margin_scale + margin_min
        next_lower = max(float(lower), float(value) - margin)
        next_upper = min(float(upper), float(value) + margin)
        if next_lower >= next_upper:
            tightened.append((float(lower), float(upper)))
        else:
            tightened.append((next_lower, next_upper))
    return tightened


def _dedupe_points_by_rounding(
    points: Sequence[Sequence[float]],
    *,
    decimals: int = 10,
) -> list[list[float]]:
    unique: list[list[float]] = []
    seen: set[tuple[float, ...]] = set()
    for point in points:
        try:
            key = tuple(round(float(value), int(decimals)) for value in point)
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append([float(value) for value in point])
    return unique

def _optimize_candidate(
    objective: Callable[[Sequence[float]], float],
    residual_fn: Callable[[Sequence[object]], Sequence[object]],
    bounds: Sequence[tuple[float, float]],
    candidate: Sequence[float],
) -> list[float]:
    seed = [float(value) for value in candidate]
    lbfgsb_solution = seed
    ls_solution = seed

    try:
        lbfgsb_solution = [float(value) for value in run_lbfgsb(objective, seed, bounds)]
    except Exception:
        lbfgsb_solution = seed

    try:
        ls_solution = [
            float(value)
            for value in run_least_squares(
                residual_fn,
                lbfgsb_solution,
                high_precision=False,
            )
        ]
    except Exception:
        ls_solution = lbfgsb_solution

    lbfgsb_score = safe_objective_value(objective, lbfgsb_solution)
    ls_score = safe_objective_value(objective, ls_solution)

    if lbfgsb_score is None and ls_score is None:
        return seed
    if lbfgsb_score is None:
        return ls_solution
    if ls_score is None:
        return lbfgsb_solution
    if ls_score <= lbfgsb_score:
        return ls_solution
    return lbfgsb_solution

def _deduplicate_points(
    points: Sequence[Sequence[Any]],
    *,
    tolerance: float,
) -> list[list[Any]]:
    unique: list[list[Any]] = []
    tolerance_mpf = boundary_float_to_mpf(tolerance, origin=BoundaryOrigin.DEDUPE_TOLERANCE)
    for point in points:
        candidate = list(point)
        is_duplicate = False
        for accepted in unique:
            if len(candidate) != len(accepted):
                continue
            distance_sq = mp.mpf("0")
            comparable = True
            for left, right in zip(candidate, accepted):
                try:
                    left_mpf = _strict_boundary_mpf(left, context="legacy_solve.dedupe_left")
                    right_mpf = _strict_boundary_mpf(right, context="legacy_solve.dedupe_right")
                    delta = left_mpf - right_mpf
                    distance_sq += delta * delta
                except Exception:
                    comparable = False
                    break
            if not comparable:
                continue
            distance = mp.sqrt(distance_sq)
            if distance <= tolerance_mpf:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(candidate)
    return unique

def _refine_high_precision_candidates(
    f_hp: Callable[[list[Any]], Sequence[Any]],
    v: Sequence[Any],
    candidates: Sequence[Sequence[Any]],
    *,
    precision: int = 100,
) -> list[list[Any]]:
    refined: list[list[Any]] = []
    target = [_strict_boundary_mpf(value, context="legacy_solve.refine_target") for value in v]
    ensure_no_float(target, context="legacy_solve.refine_target")
    for candidate in candidates:
        seed = [_strict_boundary_mpf(value, context="legacy_solve.refine_seed") for value in candidate]
        ensure_no_float(seed, context="legacy_solve.refine_seed")
        try:
            hp_solution = project_high_precision(
                f_hp,
                target,
                seed,
                len(seed),
                len(target),
                int(precision),
            )
            refined.append([
                strict_to_mpf(value, context="legacy_solve.refine_solution") for value in hp_solution
            ])
        except HighPrecisionContaminationError:
            raise
        except Exception:
            refined.append(seed)
    return refined

def _refine_one_high_precision_solution(
    solution: Sequence[object],
    *,
    f_hp: Callable[[list[Any]], Sequence[Any]],
    v: Sequence[Any],
    precision: int,
    deadline: float | None = None,
    refine_state: dict[str, bool] | None = None,
) -> list[object]:
    ensure_high_precision_mode(context="legacy_solve.refine_one_high_precision_solution")
    seed = [_strict_boundary_mpf(value, context="legacy_solve.refine_one_seed") for value in solution]
    target = [_strict_boundary_mpf(value, context="legacy_solve.refine_one_target") for value in v]
    ensure_no_float(seed, context="legacy_solve.refine_one_seed")
    ensure_no_float(target, context="legacy_solve.refine_one_target")
    try:
        refined = list(seed)
        for extra_digits in _HP_REFINE_STAGE_EXTRA_DIGITS:
            if deadline is not None and time.time() >= deadline:
                break
            stage_precision = max(int(precision), int(precision) + int(extra_digits))
            hp_solution = project_high_precision(
                f_hp,
                target,
                refined,
                len(refined),
                len(target),
                int(stage_precision),
                deadline=deadline,
            )
            refined = [
                strict_to_mpf(value, context="legacy_solve.refine_one_solution") for value in hp_solution
            ]
            ensure_no_float(refined, context="legacy_solve.refine_one_solution")
        return list(refined)
    except HighPrecisionContaminationError:
        raise
    except Exception:
        if isinstance(refine_state, dict):
            refine_state["failed"] = True
        return seed

def _high_precision_residual_vector(
    solution: list[Any],
    *,
    f_hp: Callable[[list[Any]], Sequence[Any]],
    v: Sequence[Any],
) -> list[Any]:
    hp_values = f_hp([_strict_boundary_mpf(value, context="hp_point") for value in solution])
    ensure_no_float(hp_values, context="legacy_solve.hp_values")
    hp_targets = [_strict_boundary_mpf(value, context="hp_target") for value in v]
    ensure_no_float(hp_targets, context="legacy_solve.hp_targets")
    return [
        ensure_mpf(value, context="hp_residual_value") - target
        for value, target in zip(hp_values, hp_targets)
    ]

def _exact_answer_metadata(
    *,
    ans: Callable[[list[Any]], Any] | None,
    solutions: Sequence[Sequence[Any]],
    precision: int,
    residual_norms: Sequence[float],
    residual_norms_hp: Sequence[Any] | None,
    residual_tolerance: Any,
    selected_candidate_id: int | None = None,
    tracked_candidates: Sequence[Any] | None = None,
) -> tuple[list[Any], list[dict[str, object]], Any | None, Any | None]:
    if not callable(ans):
        return [], [], None, None

    answer_values: list[Any] = []
    for solution in solutions:
        try:
            solution_mpf = [
                _strict_boundary_mpf(value, context="answer_solution")
                for value in solution
            ]
            answer_values.append(ans(solution_mpf))
        except Exception:
            answer_values.append(None)

    exact_answers: list[dict[str, object]] = [
        {
            "value": str(value),
            "pslq": None,
            "minimal_polynomial": None,
            "exact": None,
            "verified": False,
            "error": "unconverged_solution",
        }
        for value in answer_values
    ]

    converged_indices: list[int] = []
    hp_norms = list(residual_norms_hp) if isinstance(residual_norms_hp, Sequence) else []
    tolerance_mpf = strict_to_mpf(residual_tolerance, context="exact_answer_tolerance") if not isinstance(residual_tolerance, mp.mpf) else residual_tolerance
    if hp_norms:
        for index, residual_norm in enumerate(hp_norms):
            try:
                normalized = strict_to_mpf(residual_norm, context=f"exact_answer_hp_residual[{index}]")
            except Exception:
                continue
            if mp.isfinite(normalized) and normalized <= tolerance_mpf:
                converged_indices.append(index)
    else:
        for index, residual_norm in enumerate(residual_norms):
            try:
                normalized = _strict_boundary_mpf(residual_norm, context=f"exact_answer_residual[{index}]")
            except Exception:
                continue
            if mp.isfinite(normalized) and normalized <= tolerance_mpf:
                converged_indices.append(index)

    # PHASE-6: If selected_candidate_id is given, restrict exact identification
    # to only the candidate with that ID (prevents wrong candidate's residual
    # from blocking exact identification of the correct answer).
    if selected_candidate_id is not None and tracked_candidates is not None:
        candidate_index = None
        for i, tc in enumerate(tracked_candidates):
            if hasattr(tc, "candidate_id") and tc.candidate_id == selected_candidate_id:
                candidate_index = i
                break
        if candidate_index is not None:
            converged_indices = [idx for idx in converged_indices if idx == candidate_index]
            if candidate_index not in converged_indices:
                # The selected candidate might still be valid - include it if
                # its answer is available (trust the pipeline selection)
                if candidate_index < len(answer_values) and answer_values[candidate_index] is not None:
                    converged_indices = [candidate_index]

    if converged_indices:
        converged_values = [
            answer_values[index]
            for index in converged_indices
            if answer_values[index] is not None
        ]
        converged_indices = [
            index
            for index in converged_indices
            if answer_values[index] is not None
        ]
        identified_converged = identify_exact_answers(
            converged_values,
            max_degree=4,
            precision=max(precision, 30),
        )
        for index, identified in zip(converged_indices, identified_converged):
            exact_answers[index] = identified

    most_likely_answer = None
    minimal_polynomial = None
    for identified in exact_answers:
        exact_value = identified.get("exact")
        if not identified.get("verified"):
            continue
        if exact_value in (None, ""):
            continue
        most_likely_answer = exact_value
        minimal_polynomial = identified.get("minimal_polynomial")
        break
    return answer_values, exact_answers, most_likely_answer, minimal_polynomial


def _coerce_family_residual(value: object, *, context: str) -> Any:
    """Convert a residual-like value to mpf for family ranking."""
    try:
        return strict_to_mpf(value, context=context)
    except Exception:
        try:
            return _strict_boundary_mpf(value, context=context)
        except Exception:
            return mp.inf


def _compute_family_answer_value(
    solution: Sequence[object],
    *,
    ans: Callable[[list[object]], object] | None,
    index: int,
) -> Any:
    """Compute the answer value used for solution-family clustering."""
    if callable(ans):
        try:
            solution_mpf = [
                _strict_boundary_mpf(value, context=f"family_answer_solution[{index}]")
                for value in solution
            ]
            return ensure_mpf(ans(solution_mpf), context=f"family_answer[{index}]")
        except Exception:
            pass
    if solution:
        try:
            return _strict_boundary_mpf(solution[0], context=f"family_fallback_answer[{index}]")
        except Exception:
            pass
    return mp.mpf(index)


def _compute_family_branch_key(
    solution: Sequence[object],
    *,
    hp_function: Callable[[list[object]], Sequence[object]] | None,
    hp_target: Sequence[object],
    index: int,
) -> str:
    """Extract a branch signature key for one solution."""
    if not callable(hp_function) or not hp_target:
        return "default"
    try:
        point_mpf = [
            _strict_boundary_mpf(value, context=f"family_branch_point[{index}]")
            for value in solution
        ]
        target_mpf = [
            _strict_boundary_mpf(value, context=f"family_branch_target[{index}]")
            for value in hp_target
        ]
        signature = extract_branch_signature(
            f_hp=hp_function,
            targets=target_mpf,
            point=point_mpf,
        )
        return signature.signature_key()
    except Exception:
        return "default"


def _build_solution_families(
    *,
    solutions: Sequence[Sequence[object]],
    residuals: Sequence[object],
    ans: Callable[[list[object]], object] | None,
    hp_function: Callable[[list[object]], Sequence[object]] | None,
    hp_target: Sequence[object],
) -> list[SolutionFamily]:
    """Build solution families from the current ordered candidate set."""
    if not solutions:
        return []
    family_solutions: list[list[Any]] = []
    answer_values: list[Any] = []
    residual_values: list[Any] = []
    branch_signatures: list[str] = []
    for index, solution in enumerate(solutions):
        family_solution = [
            _strict_boundary_mpf(value, context=f"family_solution[{index}]")
            for value in solution
        ]
        family_solutions.append(family_solution)
        answer_values.append(
            _compute_family_answer_value(solution, ans=ans, index=index)
        )
        residual_source = residuals[index] if index < len(residuals) else mp.inf
        residual_values.append(
            _coerce_family_residual(
                residual_source,
                context=f"family_residual[{index}]",
            )
        )
        branch_signatures.append(
            _compute_family_branch_key(
                solution,
                hp_function=hp_function,
                hp_target=hp_target,
                index=index,
            )
        )
    return cluster_solutions_into_families(
        solutions=family_solutions,
        residuals=residual_values,
        answer_values=answer_values,
        branch_signatures=branch_signatures,
    )

def run_legacy_solve_pipeline(
    *,
    n: int,
    f: Callable[[list[float]], list[float]],
    v: list[float],
    bounds: list[tuple[float, float]] | None,
    precision: int,
    find_all: bool,
    max_solutions: int,
    time_limit: float | None,
    verbose: bool,
    f_mp: Callable | None,
    f_fast: Callable | None,
    two_pass: bool,
    bounds_margin: float,
    ans: Callable | None,
    seed: int | None,
    candidate_evaluator: Callable[[list[float]], CandidateEval] | None = None,
    variable_names: list[str] | None = None,
    guard_irs: list[GuardIR] | None = None,
) -> tuple[list[float], dict[str, Any]]:
    started_at = time.time()
    bounds_effective = normalize_bounds(bounds, n)
    original_f = f
    original_f_fast = f_fast
    original_hp_function = None
    original_ans = ans
    original_candidate_evaluator = candidate_evaluator
    target_float = [float(value) for value in v]
    target_raw = list(v)
    hp_function = resolve_high_precision_function(f, f_mp, precision)
    original_hp_function = hp_function
    hp_path_enabled = bool(should_use_mpmath(int(precision)) and callable(hp_function))
    transforms: list[VariableTransform] = []
    transform_active = False
    deferred_open_bound_count = 0
    if variable_names and guard_irs:
        transform_bounds = [
            (_strict_boundary_mpf(lower, context=f"reparam_bound_low[{index}]"),
             _strict_boundary_mpf(upper, context=f"reparam_bound_high[{index}]"))
            for index, (lower, upper) in enumerate(bounds_effective)
        ]
        deferred_open_bound_count = _count_deferred_open_bounds(
            guard_irs=guard_irs,
            variable_names=variable_names,
        )
        transforms = build_transforms_from_guards(
            guard_irs=guard_irs,
            variable_names=variable_names,
            bounds=transform_bounds,
        )
        transform_active = False
    objective_fast = partial(_residual_objective, _create_fast_wrapper(f_fast, f), target_float)
    objective = partial(_residual_objective, f, target_float)
    residual_fn = partial(_residual_vector, f, target_float)
    hp_target_early: list[Any] = []
    if hp_path_enabled:
        hp_target_early = [_strict_boundary_mpf(value, context="legacy_solve.hp_target") for value in target_raw]
    # FIX-7: Activate precision audit/policy for high-precision pipelines
    _fix7_audit = PrecisionAudit() if int(precision) >= 60 else None
    _fix7_policy = default_precision_policy() if int(precision) >= 60 else None
    _fix7_policy_token = None
    _fix7_audit_token = None
    if _fix7_policy is not None and _fix7_audit is not None:
        from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
            _precision_policy_active,
            _precision_audit_log,
        )
        _fix7_policy_token = _precision_policy_active.set(_fix7_policy)
        _fix7_audit_token = _precision_audit_log.set(_fix7_audit)
    hp_refine_reserved_seconds = _hp_refine_reserved_seconds(
        n=int(n),
        hp_path_enabled=bool(hp_path_enabled),
        time_limit=time_limit,
    )
    search_time_limit = _search_time_limit_for_refine_reservation(
        time_limit=time_limit,
        reserved_seconds=hp_refine_reserved_seconds,
    )

    from geosolver.engine.standard.search.find_initial_points import find_initial_points

    find_initial_points_kwargs: dict[str, int] = {}
    if "seed" in inspect.signature(find_initial_points).parameters:
        find_initial_points_kwargs["seed"] = 0 if seed is None else int(seed)

    has_exact_answer = callable(ans)
    search_budget = _solve_search_budget(n, max_solutions, find_all)
    n_points = _sample_count(
        n,
        search_budget=search_budget,
        has_exact=has_exact_answer,
        phase_multiplier=1.0,
    )
    candidates = find_initial_points(
        n,
        bounds_effective,
        objective_fast,
        strategy="halton_random",
        search_budget=search_budget,
        has_exact=has_exact_answer,
        phase_multiplier=1.0,
        **find_initial_points_kwargs,
    )

    optimized: list[list[float]] = []
    phase1_optimized_count = 0
    optimize_budget = _optimization_budget(
        total_candidates=len(candidates),
        started_at=started_at,
        time_limit=search_time_limit,
        phase_time_share=_PHASE1_BUDGET_SHARE,
        seconds_per_candidate=2.5,
    )
    phase1_cap = _time_budget_candidate_cap(
        total_candidates=len(candidates),
        n=n,
        started_at=started_at,
        time_limit=search_time_limit,
        phase_time_share=_PHASE1_BUDGET_SHARE,
        seconds_per_candidate=2.5,
    )
    optimize_budget = min(optimize_budget, phase1_cap)
    mp_solve_deadline = (started_at + float(search_time_limit)) if search_time_limit is not None else None
    for candidate in candidates[:optimize_budget]:
        if _time_exceeded(started_at, search_time_limit):
            break
        optimized.append(_optimize_candidate(objective, residual_fn, bounds_effective, candidate))
        phase1_optimized_count += 1

    if not optimized and candidates:
        salvage_limit = max(10, int(max_solutions) * 4) if int(max_solutions) > 0 else 10
        salvage_limit = min(len(candidates), salvage_limit)
        optimized = [[float(value) for value in point] for point in candidates[:salvage_limit]]

    pass2_candidate_count = 0
    pass2_budget = 0
    phase2_optimized_count = 0
    extra_batch_candidate_count = 0
    extra_batch_budget = 0
    extra_batch_optimized_count = 0
    phase1_improvement_rate = _compute_improvement_rate(
        objective=objective,
        original_candidates=candidates[: max(1, optimize_budget)],
        optimized_candidates=optimized,
    )
    if two_pass and optimized and not _time_exceeded(started_at, search_time_limit):
        best = pick_best_solution(optimized, g=objective, mode="min")
        if best is not None:
            margin_scale = max(0.25, float(bounds_margin))
            pass2_bounds = _tighten_bounds_around_point(
                bounds_effective,
                best,
                margin_scale=margin_scale,
                margin_min=5.0,
            )
            pass2_candidates = find_initial_points(
                n,
                pass2_bounds,
                objective_fast,
                strategy="scale_adaptive",
                search_budget=search_budget,
                has_exact=has_exact_answer,
                phase_multiplier=(1.5 * _phase2_multiplier(
                    n=n,
                    started_at=started_at,
                    time_limit=time_limit,
                    improvement_rate=phase1_improvement_rate,
                )),
                **find_initial_points_kwargs,
            )
            wide_points_count = min(
                int(_PASS2_WIDE_POINTS_MAX),
                max(int(_PASS2_WIDE_POINTS_MIN), int(n_points // 4)),
            )
            wide_points = find_initial_points(
                n,
                bounds_effective,
                objective_fast,
                n_points=wide_points_count,
                strategy="halton_random",
                search_budget=search_budget,
                has_exact=has_exact_answer,
                **find_initial_points_kwargs,
            )
            pass2_candidates.extend(wide_points)
            pass2_candidates.extend([list(point) for point in optimized[: max(10, int(max_solutions) * 5)]])
            pass2_candidates = _dedupe_points_by_rounding(pass2_candidates, decimals=10)
            pass2_cap = (
                int(_PASS2_CANDIDATE_CAP_SMALL_N)
                if int(n) <= 5
                else int(_PASS2_CANDIDATE_CAP_LARGE_N)
            )
            if len(pass2_candidates) > pass2_cap:
                pass2_candidates = pass2_candidates[:pass2_cap]
            pass2_candidate_count = len(pass2_candidates)
            pass2_budget = _optimization_budget(
                total_candidates=len(pass2_candidates),
                started_at=started_at,
                time_limit=search_time_limit,
                phase_time_share=_PHASE2_BUDGET_SHARE,
                seconds_per_candidate=2.2,
            )
            phase2_cap = _time_budget_candidate_cap(
                total_candidates=len(pass2_candidates),
                n=n,
                started_at=started_at,
                time_limit=search_time_limit,
                phase_time_share=_PHASE2_BUDGET_SHARE,
                seconds_per_candidate=2.2,
            )
            pass2_budget = min(pass2_budget, phase2_cap)
            for candidate in pass2_candidates[:pass2_budget]:
                if _time_exceeded(started_at, search_time_limit):
                    break
                optimized.append(_optimize_candidate(objective, residual_fn, pass2_bounds, candidate))
                phase2_optimized_count += 1

            if find_all and not _time_exceeded(started_at, search_time_limit):
                extra_points_count = min(
                    int(_EXTRA_BATCH_POINTS_MAX),
                    max(int(_EXTRA_BATCH_POINTS_MIN), int(n) * 12),
                )
                extra_batch_points = find_initial_points(
                    n,
                    bounds_effective,
                    objective_fast,
                    n_points=extra_points_count,
                    strategy="halton_random",
                    search_budget=search_budget,
                    has_exact=has_exact_answer,
                    **find_initial_points_kwargs,
                )
                extra_batch_points = _dedupe_points_by_rounding(extra_batch_points, decimals=10)
                extra_batch_candidate_count = len(extra_batch_points)
                extra_batch_budget = _optimization_budget(
                    total_candidates=len(extra_batch_points),
                    started_at=started_at,
                    time_limit=search_time_limit,
                    phase_time_share=0.2,
                    seconds_per_candidate=2.4,
                )
                extra_batch_cap = _time_budget_candidate_cap(
                    total_candidates=len(extra_batch_points),
                    n=n,
                    started_at=started_at,
                    time_limit=search_time_limit,
                    phase_time_share=0.2,
                    seconds_per_candidate=2.4,
                )
                extra_batch_budget = min(extra_batch_budget, extra_batch_cap)
                for candidate in extra_batch_points[:extra_batch_budget]:
                    if _time_exceeded(started_at, search_time_limit):
                        break
                    optimized.append(_optimize_candidate(objective, residual_fn, bounds_effective, candidate))
                    extra_batch_optimized_count += 1

    dedupe_input = _limit_dedupe_input(
        points=optimized,
        objective=objective,
        n=n,
        find_all=find_all,
        max_solutions=max_solutions,
    )
    dedupe_input_count = len(dedupe_input)
    dedupe_input_limited = len(dedupe_input) < len(optimized)
    deduped = _deduplicate_points(dedupe_input, tolerance=1e-7)
    if not deduped and candidates:
        deduped = list(candidates[:1])
    residuals = [objective(point) for point in deduped]
    unique_solutions, unique_residuals = remove_duplicate_solutions(deduped, residuals, tolerance=1e-6)

    ordered = [point for _, point in sorted(zip(unique_residuals, unique_solutions), key=lambda item: item[0])]

    hp_target: list[Any] = list(hp_target_early) if hp_target_early else []
    float_origin_count = 0
    contamination_error_examples: list[str] = []
    contamination_detected = False
    if hp_path_enabled and not hp_target:
        hp_target = [_strict_boundary_mpf(value, context="legacy_solve.hp_target") for value in target_raw]
    if find_all and ordered and hp_path_enabled and not _time_exceeded(started_at, time_limit):
        from geosolver.engine.standard.refinement.multi.refine_solutions import (
            iterative_refine_multiple_solutions,
        )
        ordered = boundary_normalize_solutions(
            ordered,
            context="legacy_solve.hp_ordered_pre_refine_boundary",
            converter=lambda value, value_context: _strict_boundary_mpf(value, context=value_context),
        )
        try:
            with high_precision_mode():
                ordered, float_origin_pre = normalize_solutions_to_mpf(
                    ordered,
                    context="legacy_solve.hp_ordered_pre_refine",
                )
                float_origin_count += int(float_origin_pre)
                ensure_no_float(ordered, context="legacy_solve.hp_ordered_pre_refine")
        except HighPrecisionContaminationError as exc:
            contamination_detected = True
            float_origin_count += 1
            contamination_error_examples.append(str(exc))
            ordered = []
        refine_state: dict[str, bool] = {"failed": False}
        refine_one = partial(
            _refine_one_high_precision_solution,
            f_hp=hp_function,
            v=hp_target,
            precision=int(precision),
            deadline=(None if time_limit is None else started_at + float(time_limit)),
            refine_state=refine_state,
        )
        hp_residual_vector = partial(_high_precision_residual_vector, f_hp=hp_function, v=hp_target)
        with high_precision_mode():
            ordered = iterative_refine_multiple_solutions(
                ordered,
                refine_one,
                residual_vector=hp_residual_vector,
                residual_tolerance=solve_residual_tolerance(int(precision)),
                max_iterations=5,
                improvement_tolerance=solve_residual_tolerance(int(precision)) * mp.mpf("1e-6"),
                use_parallel=False,
                max_workers=1,
                max_solutions=(None if find_all else 1),
            )
    else:
        refine_state = {"failed": False}

    if hp_path_enabled:
        ordered = boundary_normalize_solutions(
            ordered,
            context="legacy_solve.hp_ordered_post_refine_boundary",
            converter=lambda value, value_context: _strict_boundary_mpf(value, context=value_context),
        )
        try:
            with high_precision_mode():
                ordered, float_origin_post = normalize_solutions_to_mpf(
                    ordered,
                    context="legacy_solve.hp_ordered",
                )
                float_origin_count += int(float_origin_post)
                ensure_no_float(ordered, context="legacy_solve.hp_ordered")
        except HighPrecisionContaminationError as exc:
            contamination_detected = True
            float_origin_count += 1
            contamination_error_examples.append(str(exc))
            ordered = []

    ordered, guard_feasible_count, selected_solution_index, selected_candidate_id, candidate_eval_error_count, candidate_eval_error_examples = apply_solve_candidate_evaluator(
        ordered,
        candidate_evaluator=candidate_evaluator,
    )

    # -- PHASE-0: wrap ordered into TrackedCandidate for ID alignment --
    tracked_ordered = tracked_from_pool(ordered, source="reported_solution")

    best_solution = ordered[0] if ordered else []
    if (
        hp_path_enabled
        and not find_all
        and best_solution
        and callable(hp_function)
        and hp_target
        and not _time_exceeded(started_at, time_limit)
    ):
        try:
            selected_seed = [
                _strict_boundary_mpf(value, context="legacy_solve.selected_seed")
                for value in best_solution
            ]
            selected_deadline = (
                None if time_limit is None else started_at + float(time_limit)
            )
            refined_selected, _ = mp_local_solve(
                f=hp_function,
                targets=hp_target,
                seed=selected_seed,
                dps=int(precision),
                residual_threshold=solve_residual_tolerance(int(precision)),
                deadline=selected_deadline,
            )
            ordered[0] = list(refined_selected)
            best_solution = ordered[0]
        except HighPrecisionContaminationError:
            raise
        except Exception:
            pass

    best_residual = objective(list(best_solution)) if best_solution else float("inf")
    best_residual_norm = float(best_residual**0.5) if math.isfinite(best_residual) else float("inf")
    best_residual_hp = None
    best_residual_norm_hp = None
    best_hp_result = None
    if hp_path_enabled and best_solution:
        try:
            with high_precision_mode():
                best_hp_result = evaluate_hp_residual(
                    point=list(best_solution),
                    f_hp=hp_function,
                    targets=hp_target,
                )
                best_residual_hp = best_hp_result.residual_norm
                if best_hp_result.is_finite:
                    best_residual_norm_hp = best_residual_hp
                    best_residual_norm = best_residual_hp
        except HighPrecisionContaminationError:
            raise
        except Exception:
            best_residual_hp = None
            best_residual_norm_hp = None
            best_hp_result = None
    residual_tolerance = solve_residual_tolerance(int(precision))

    residual_norms: list[Any] = []
    for solution in ordered:
        residual_value = objective(solution)
        if (math.isfinite(residual_value) if isinstance(residual_value, float) else mp.isfinite(residual_value)):
            residual_norms.append(residual_value**0.5)
        else:
            residual_norms.append(float("inf"))

    solution_residuals_hp: list[Any] = []
    if hp_path_enabled:
        with high_precision_mode():
            for solution in ordered:
                try:
                    sol_hp_result = evaluate_hp_residual(
                        point=list(solution),
                        f_hp=hp_function,
                        targets=hp_target,
                    )
                    solution_residuals_hp.append(
                        sol_hp_result.residual_norm if sol_hp_result.is_finite else mp.inf
                    )
                except HighPrecisionContaminationError:
                    raise
                except Exception:
                    solution_residuals_hp.append(mp.inf)

    if hp_path_enabled and ordered and len(solution_residuals_hp) == len(ordered):
        # Preserve guard-aware candidate evaluator selection when it has already
        # reordered the selected candidate to index 0.
        preserve_selected_order = bool(callable(candidate_evaluator) and selected_solution_index is not None)
        if not preserve_selected_order:
            ordered, residual_norms, solution_residuals_hp = _rerank_ordered_candidates_mp(
                ordered,
                residual_norms,
                solution_residuals_hp,
            )
            selected_solution_index = 0

    if not find_all and ordered:
        ordered = ordered[:1]
        residual_norms = residual_norms[:1]
        if solution_residuals_hp:
            solution_residuals_hp = solution_residuals_hp[:1]
        selected_solution_index = 0

    solution_families: list[SolutionFamily] = []
    family_stable: bool | None = None
    if find_all and ordered:
        family_residuals: Sequence[object] = (
            solution_residuals_hp
            if len(solution_residuals_hp) == len(ordered)
            else residual_norms
        )
        solution_families = _build_solution_families(
            solutions=ordered,
            residuals=family_residuals,
            ans=ans,
            hp_function=hp_function if hp_path_enabled else None,
            hp_target=hp_target,
        )
        if solution_families:
            family_limit = len(solution_families) if int(max_solutions) <= 0 else int(max_solutions)
            selected_families = solution_families[:family_limit]
            ordered = select_family_representatives(solution_families, family_limit)
            family_stable = check_family_set_stability(
                current=selected_families,
                previous=solution_families,
            )
            residual_norms = []
            for solution in ordered:
                residual_value = objective(solution)
                if (math.isfinite(residual_value) if isinstance(residual_value, float) else mp.isfinite(residual_value)):
                    residual_norms.append(residual_value**0.5)
                else:
                    residual_norms.append(float("inf"))
            if hp_path_enabled:
                solution_residuals_hp = []
                with high_precision_mode():
                    for solution in ordered:
                        try:
                            sol_hp_result = evaluate_hp_residual(
                                point=list(solution),
                                f_hp=hp_function,
                                targets=hp_target,
                            )
                            solution_residuals_hp.append(
                                sol_hp_result.residual_norm if sol_hp_result.is_finite else mp.inf
                            )
                        except HighPrecisionContaminationError:
                            raise
                        except Exception:
                            solution_residuals_hp.append(mp.inf)

    best_solution = ordered[0] if ordered else []
    if residual_norms:
        best_residual_norm = residual_norms[0]
    best_hp_result = None
    if solution_residuals_hp:
        best_residual_hp = solution_residuals_hp[0]
        if mp.isfinite(best_residual_hp):
            best_residual_norm_hp = best_residual_hp
            best_residual_norm = best_residual_hp
        else:
            best_residual_norm_hp = None
    if hp_path_enabled and best_solution:
        try:
            with high_precision_mode():
                best_hp_result = evaluate_hp_residual(
                    point=list(best_solution),
                    f_hp=hp_function,
                    targets=hp_target,
                )
        except HighPrecisionContaminationError:
            raise
        except Exception:
            best_hp_result = None

    reported_ordered = (
        [
            _forward_transform_values(solution, transforms)
            for solution in ordered
        ]
        if transform_active
        else [list(solution) for solution in ordered]
    )
    # -- PHASE-0: build tracked reported_ordered with candidate_id alignment --
    tracked_reported_ordered: list[TrackedCandidate] = []
    for idx, reported_sol in enumerate(reported_ordered):
        if idx < len(tracked_ordered):
            tc = tracked_ordered[idx]
            tracked_reported_ordered.append(
                TrackedCandidate(
                    candidate_id=tc.candidate_id,
                    values=list(reported_sol),
                    source=tc.source,
                )
            )
        else:
            tracked_reported_ordered.append(make_tracked(list(reported_sol), source="reported_solution"))
    reported_best_solution = reported_ordered[0] if reported_ordered else []

    # PHASE-6: restrict exact identification to the selected candidate
    _selected_cid_for_answer = None
    if not find_all and tracked_reported_ordered:
        _selected_cid_for_answer = tracked_reported_ordered[0].candidate_id
    answer_values, exact_answers, most_likely_answer, minimal_polynomial = _exact_answer_metadata(
        ans=original_ans,
        solutions=reported_ordered,
        precision=precision,
        residual_norms=residual_norms,
        residual_norms_hp=solution_residuals_hp,
        residual_tolerance=residual_tolerance,
        selected_candidate_id=_selected_cid_for_answer,
        tracked_candidates=tracked_reported_ordered,
    )

    if best_residual_norm_hp is not None:
        success = (
            bool(best_solution)
            and mp.isfinite(best_residual_norm_hp)
            and best_residual_norm_hp <= residual_tolerance
        )
    else:
        success = bool(best_solution) and math.isfinite(best_residual_norm) and best_residual_norm <= residual_tolerance

    convergence_status = None
    if best_hp_result is not None:
        convergence_criteria = build_convergence_criteria(
            precision=int(precision),
            mode=("find_all" if find_all else "solve"),
        )
        convergence_status = check_solve_convergence(
            residual_result=best_hp_result,
            criteria=convergence_criteria,
            family_stable=family_stable,
        )
        success = bool(best_solution) and convergence_status.overall_converged

    if verbose:
        _print_high_precision_solutions(reported_ordered, verbose=verbose)

    contamination_count = int(float_origin_count + candidate_eval_error_count)
    contamination_examples = list((contamination_error_examples + candidate_eval_error_examples)[:5])

    diagnostics: dict[str, Any] = {
        "success": success,
        "n_solutions": len(reported_ordered),
        "all_solutions": reported_ordered,
        "residual_norm": best_residual_norm,
        "residual_tolerance": residual_tolerance,
        "exact_answers": exact_answers,
        "elapsed_time": max(0.0, time.time() - started_at),
        "precision_achieved": int(precision),
        "candidate_count": int(len(reported_ordered)),
        "guard_feasible_count": int(guard_feasible_count),
        "used_high_precision": bool(hp_path_enabled),
        "precision_backend": precision_backend_name(int(precision)),
        "precision_threshold": mpmath_precision_threshold(),
        "answer_eval_backend": "mpf",
        "answer_eval_float_fallback_used": False,
        "solution_residuals_float": list(residual_norms),
        "selection_residual_source": "legacy_hp" if hp_path_enabled else "legacy_float",
        "candidate_eval_error_count": int(candidate_eval_error_count),
        "candidate_eval_error_examples": list(candidate_eval_error_examples),
        "float_origin_count": int(float_origin_count),
        "hp_float_contamination_count": int(contamination_count),
        "hp_float_contamination_examples": contamination_examples,
        "deferred_open_bound_count": int(deferred_open_bound_count),
    }
    if solution_residuals_hp:
        diagnostics["solution_residuals_hp"] = list(solution_residuals_hp)
    if solution_families:
        diagnostics["solution_families"] = [
            {
                "family_id": family.family_id,
                "answer_cluster": str(family.answer_cluster),
                "best_residual": str(family.best_residual),
                "branch_signature": family.branch_signature,
                "member_count": len(family.members),
            }
            for family in solution_families
        ]
    if family_stable is not None:
        diagnostics["family_stable"] = bool(family_stable)
    if convergence_status is not None:
        diagnostics["convergence_status"] = convergence_status
    search_distribution = {
        "phase1": {
            "sample_count": int(n_points),
            "candidate_count": int(len(candidates)),
            "optimization_budget": int(optimize_budget),
            "optimized_count": int(phase1_optimized_count),
        },
        "phase2": {
            "sample_count": int(_sample_count(
                n,
                search_budget=search_budget,
                has_exact=has_exact_answer,
                phase_multiplier=(1.5 * _phase2_multiplier(
                    n=n,
                    started_at=started_at,
                    time_limit=time_limit,
                    improvement_rate=phase1_improvement_rate,
                )),
            )),
            "candidate_count": int(pass2_candidate_count),
            "optimization_budget": int(pass2_budget),
            "optimized_count": int(phase2_optimized_count),
            "improvement_rate": float(phase1_improvement_rate),
        },
        "phase2b": {
            "candidate_count": int(extra_batch_candidate_count),
            "optimization_budget": int(extra_batch_budget),
            "optimized_count": int(extra_batch_optimized_count),
        },
        "dedupe": {
            "input_count": int(dedupe_input_count),
            "limited": bool(dedupe_input_limited),
            "raw_optimized_count": int(len(optimized)),
        },
    }
    diagnostics["hp_refine_failed"] = bool(refine_state.get("failed", False))
    diagnostics["candidate_ledger_distribution"] = search_distribution
    diagnostics["candidate_ledger"] = build_solve_candidate_ledger(
        ordered=tracked_reported_ordered,
        residual_norms=residual_norms,
        candidate_evaluator=original_candidate_evaluator,
        hp_path_enabled=hp_path_enabled,
        f_hp=original_hp_function if hp_path_enabled else None,
        hp_targets=hp_target if hp_path_enabled else None,
        search_distribution=search_distribution,
    )
    diagnostics["success"] = bool(success)
    if int(contamination_count) > 0 or contamination_detected:
        diagnostics["success"] = False
        diagnostics["failure_reason"] = "hp_float_contamination"
    elif success:
        diagnostics["failure_reason"] = None
    elif not best_solution:
        diagnostics["failure_reason"] = "no_solution"
    elif (
        (best_residual_norm_hp is not None and (
            (not mp.isfinite(best_residual_norm_hp))
            or best_residual_norm_hp > residual_tolerance
        ))
        or (best_residual_norm_hp is None and (
            (not math.isfinite(best_residual_norm))
            or best_residual_norm > residual_tolerance
        ))
    ):
        diagnostics["failure_reason"] = "residual_not_converged"
    elif (
        convergence_status is not None
        and convergence_status.constraint_converged
        and convergence_status.family_stable is False
    ):
        diagnostics["failure_reason"] = "family_not_stable"
    elif callable(original_candidate_evaluator) and reported_ordered and int(guard_feasible_count) <= 0 and int(candidate_eval_error_count) >= len(reported_ordered):
        diagnostics["failure_reason"] = "candidate_eval_failed"
    elif callable(original_candidate_evaluator) and int(guard_feasible_count) <= 0:
        diagnostics["failure_reason"] = "guard_not_feasible"
    else:
        diagnostics["failure_reason"] = "unknown"
    if best_residual_hp is not None:
        diagnostics["constraint_residual_hp"] = best_residual_hp
    if answer_values:
        diagnostics["answer_values"] = answer_values
    if most_likely_answer is not None:
        diagnostics["most_likely_answer"] = most_likely_answer
    if minimal_polynomial is not None:
        diagnostics["minimal_polynomial"] = minimal_polynomial
    if seed is not None:
        diagnostics["seed"] = int(seed)
    if time_limit is not None:
        diagnostics["time_limit"] = float(time_limit)
    if selected_solution_index is not None:
        diagnostics["selected_solution_index"] = int(selected_solution_index)
    # -- PHASE-0: candidate ID alignment diagnostics --
    best_tracked_id: int | None = None
    if tracked_reported_ordered:
        best_tracked_id = tracked_reported_ordered[0].candidate_id
    if selected_candidate_id is not None:
        best_tracked_id = int(selected_candidate_id)
    diagnostics["best_candidate_id"] = best_tracked_id
    diagnostics["answer_source_candidate_id"] = best_tracked_id
    diagnostics["residual_source_candidate_id"] = best_tracked_id
    # PHASE-6: answer extraction and family representative candidate IDs
    diagnostics["answer_extraction_candidate_ids"] = [
        tc.candidate_id for tc in tracked_reported_ordered
    ] if tracked_reported_ordered else []
    diagnostics["answer_candidates"] = [
        tc.candidate_id for tc in tracked_reported_ordered
    ] if tracked_reported_ordered else []
    diagnostics["answer_candidate_values"] = list(answer_values)
    diagnostics["answer_candidate_residuals_hp"] = (
        [
            (value if mp.isfinite(value) else None)
            for value in solution_residuals_hp
        ]
        if solution_residuals_hp
        else []
    )
    family_rep_ids: list[int] = []
    if solution_families and tracked_reported_ordered:
        for family in solution_families:
            if family.representative:
                for tc in tracked_reported_ordered:
                    if list(tc.values) == list(family.representative):
                        family_rep_ids.append(tc.candidate_id)
                        break
    diagnostics["family_representative_candidate_ids"] = family_rep_ids

    diagnostics["diagnostics"] = {
        "pipeline": "legacy_solve",
        "residual_norm": diagnostics["residual_norm"],
        "residual_tolerance": diagnostics["residual_tolerance"],
        "n_solutions": diagnostics["n_solutions"],
        "elapsed_time": diagnostics["elapsed_time"],
    }
    diagnostics.setdefault("trace_spans", [])
    diagnostics.setdefault("log_lines", [])

    # FIX-7: Extract audit and clean up ContextVar tokens
    if _fix7_audit is not None:
        diagnostics["precision_audit"] = {
            "total_conversions": _fix7_audit.total_conversions(),
            "has_violations": _fix7_audit.has_violations(),
            "violations": list(_fix7_audit.policy_violations),
            "records": [
                {"origin": r.origin, "stage": r.stage, "count": r.count}
                for r in _fix7_audit.records
            ],
        }
    if _fix7_audit_token is not None:
        _precision_audit_log.reset(_fix7_audit_token)
    if _fix7_policy_token is not None:
        _precision_policy_active.reset(_fix7_policy_token)

    return list(reported_best_solution), diagnostics
