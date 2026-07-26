"""Clean start-local rebind of AD row-equilibrated LM/CPQR.

The local kernel receives its coordinate chart explicitly from its caller:
the original start, a positive per-start scale, and source-declared bounds.
It never reads compiler origin/scale metadata, legacy/inferred bounds, or any
problem identity.  Missing source bounds must be represented by +/- infinity.

The frozen source-semantic forward-AD implementation remains parity-gated
against the untouched evaluator.  Dynamic row scaling affects step selection
only; unscaled original residuals and semantic observations own acceptance,
best-point selection, termination, and the exposed endpoint.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
from types import ModuleType
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parents[1]
FROZEN_AD_PATH = EXPERIMENTS / "EXP-REAL61-006/analytic_jacobian/candidate.py"
ROW_HELPERS_PATH = (
    EXPERIMENTS / "EXP-REAL61-007/ad_row_equilibration/candidate.py"
)


def _load(path: Path, name: str) -> ModuleType:
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


_AD = _load(FROZEN_AD_PATH, "geotarget_exp008_frozen_forward_ad")
_ROW = _load(ROW_HELPERS_PATH, "geotarget_exp008_frozen_row_helpers")

ADProgram = _AD.ADProgram
Dual = _AD.Dual
compile_program = _AD.compile_program


REFERENCE_NAME = "ad_row_equilibrated_start_local_cpqr"


@dataclass(frozen=True)
class Configuration:
    name: str = REFERENCE_NAME
    linear_solver: str = "cpqr"
    fd_relative_step: float = 2.0e-7
    initial_trust_radius: float = 1.0
    maximum_trust_radius: float = 100.0
    minimum_trust_radius: float = 1.0e-9
    initial_damping: float = 1.0e-4
    minimum_damping: float = 1.0e-14
    maximum_damping: float = 1.0e12
    rank_rtol: float = 3.0e-10
    success_residual_inf: float = 1.0e-8
    maximum_iterations: int = 64
    guard_weight: float = 1.0
    parity_rtol: float = 2.0e-8
    parity_atol: float = 2.0e-10
    row_norm_floor_relative: float = 1.0e-3
    row_norm_ceiling_relative: float = 1.0e3
    minimum_row_weight: float = 1.0 / 64.0
    maximum_row_weight: float = 64.0
    maximum_weight_update_ratio: float = 4.0
    row_weight_relaxation: float = 0.65
    nonmonotone_window: int = 5
    sufficient_decrease: float = 1.0e-4
    nonmonotone_inf_growth: float = 1.25
    revert_after_rejections: int = 2
    revert_cooldown_iterations: int = 2


REFERENCE = Configuration()
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}


@dataclass(frozen=True)
class CandidateOutcome:
    endpoint: np.ndarray
    status: str
    counters: Mapping[str, int]


def configuration_manifest(configuration: Configuration = REFERENCE) -> dict[str, object]:
    return {
        "candidate": configuration.name,
        "mechanism": "start-local forward-AD dynamic row-equilibrated nonmonotone LM CPQR",
        "frozen_ad_sha256": hashlib.sha256(FROZEN_AD_PATH.read_bytes()).hexdigest(),
        "row_helper_sha256": hashlib.sha256(ROW_HELPERS_PATH.read_bytes()).hexdigest(),
        "coordinate_anchor": "caller-provided original start",
        "coordinate_scale": "caller-provided positive per-start scale",
        "hard_bounds": "caller-provided explicit source bounds only",
        "missing_bound_representation": "negative/positive infinity",
        "compiler_origin_or_scales_read": False,
        "legacy_or_inferred_bounds_read": False,
        "case_metadata_read": ["dimension", "residual_dimension", "evaluate"],
        "row_scaling_scope": "linearized step only",
        "acceptance_authority": "untouched raw residual and semantic evaluator",
        "source_rewrite": False,
        "variable_or_equation_elimination": False,
        "gauge_or_symmetry_reduction": False,
        "inferred_or_artificial_bounds": False,
        "case_identity_available": False,
        "truth_or_target_count_available": False,
        "runtime_case_or_family_routing": False,
    }


def _coordinate_inputs(
    start: Sequence[float],
    per_start_scale: Sequence[float],
    source_lower: Sequence[float],
    source_upper: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    anchor = np.asarray(start, dtype=float).copy()
    scale = np.asarray(per_start_scale, dtype=float).copy()
    lower = np.asarray(source_lower, dtype=float).copy()
    upper = np.asarray(source_upper, dtype=float).copy()
    if anchor.ndim != 1 or not np.all(np.isfinite(anchor)):
        raise ValueError("original start must be a finite vector")
    if (
        scale.shape != anchor.shape
        or not np.all(np.isfinite(scale))
        or np.any(scale <= 0.0)
    ):
        raise ValueError("per-start scale must be finite, positive, and shape-matched")
    if lower.shape != anchor.shape or upper.shape != anchor.shape:
        raise ValueError("explicit source-bound arrays must match the start")
    if np.any(np.isnan(lower)) or np.any(np.isnan(upper)) or np.any(lower > upper):
        raise ValueError("explicit source bounds are malformed")
    if np.any(anchor < lower) or np.any(anchor > upper):
        raise ValueError("original start violates an explicit source bound")
    return anchor, scale, lower, upper


def _add(counters: dict[str, int], values: Mapping[str, int]) -> None:
    for name, value in values.items():
        counters[name] = counters.get(name, 0) + int(value)


def solve_local(
    case: object,
    program: ADProgram,
    configuration: Configuration,
    start: Sequence[float],
    *,
    per_start_scale: Sequence[float],
    source_lower: Sequence[float],
    source_upper: Sequence[float],
    max_callbacks: int,
    deadline_monotonic: float,
) -> CandidateOutcome:
    """Solve in the caller-owned start-local chart without metadata fallback."""

    anchor, variable_scale, explicit_lower, explicit_upper = _coordinate_inputs(
        start, per_start_scale, source_lower, source_upper
    )
    if program.dimension != int(case.dimension) or program.residual_dimension != int(
        case.residual_dimension
    ):
        raise ValueError("AD program shape differs from the untouched evaluator")
    if anchor.shape != (program.dimension,):
        raise ValueError("start dimension differs from the untouched evaluator")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")
    lower_z = (explicit_lower - anchor) / variable_scale
    upper_z = (explicit_upper - anchor) / variable_scale
    counters: dict[str, int] = {
        "starts_attempted": 1,
        "iterations": 0,
        "accepted_steps": 0,
        "rejected_steps": 0,
        "raw_lexicographic_accepts": 0,
        "raw_nonmonotone_accepts": 0,
        "analytic_relation_rows": 0,
        "analytic_guard_rows": 0,
        "analytic_inactive_hard_rows": 0,
        "analytic_rows_total": 0,
        "fd_fallback_rows_total": 0,
        "relation_parity_fallback_rows": 0,
        "guard_parity_fallback_rows": 0,
        "fd_direction_evaluations": 0,
        "rank_deficient_iterations": 0,
        "row_equilibration_updates": 0,
        "row_equilibration_active_rows": 0,
        "row_equilibration_changed_rows": 0,
        "row_equilibration_ratio_cap_hits": 0,
        "row_equilibration_absolute_cap_hits": 0,
        "row_equilibration_reverts": 0,
        "row_equilibration_cooldown_iterations": 0,
        "reported_safe_endpoint": 0,
        "deadline_stops": 0,
        "budget_stops": 0,
        "linear_failures": 0,
        "compiler_coordinate_metadata_reads": 0,
        "legacy_or_inferred_bound_reads": 0,
    }
    try:
        current = _AD._make_state(case, anchor, configuration.guard_weight)
    except Exception as error:
        if type(error).__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(anchor.copy(), "budget_before_start", counters)
        raise
    best = current
    trust_radius = configuration.initial_trust_radius
    damping = configuration.initial_damping
    row_weights = np.ones(current.augmented.size, dtype=float)
    objectives: deque[float] = deque(
        [current.objective], maxlen=configuration.nonmonotone_window
    )
    relation_norms: deque[float] = deque(
        [current.relation_inf], maxlen=configuration.nonmonotone_window
    )
    consecutive_rejections = 0
    cooldown = 0

    for _ in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if current.semantics_valid and current.relation_inf <= configuration.success_residual_inf:
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1
        try:
            raw_jacobian = _AD._hybrid_jacobian(
                case,
                program,
                current,
                anchor,
                variable_scale,
                lower_z,
                upper_z,
                configuration,
                counters,
            )
            prior_weights = row_weights.copy()
            if cooldown:
                proposed_weights = prior_weights
                cooldown -= 1
                counters["row_equilibration_cooldown_iterations"] += 1
            else:
                proposed_weights, diagnostics = _ROW._equilibrate_rows(
                    raw_jacobian, prior_weights, configuration
                )
                _add(counters, diagnostics)
                counters["row_equilibration_updates"] += int(
                    diagnostics["row_equilibration_changed_rows"] > 0
                )
            weighted_jacobian = proposed_weights[:, None] * raw_jacobian
            weighted_residual = proposed_weights * current.augmented
            step, rank = _AD._rank_aware_step(
                weighted_jacobian,
                weighted_residual,
                damping,
                configuration.rank_rtol,
                configuration.linear_solver,
            )
        except Exception as error:
            if type(error).__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["linear_failures"] += 1
            break
        counters["rank_deficient_iterations"] += int(
            rank < min(weighted_jacobian.shape)
        )
        step_norm = float(np.linalg.norm(step))
        if not math.isfinite(step_norm) or step_norm == 0.0:
            damping = min(configuration.maximum_damping, damping * 10.0)
            trust_radius = max(configuration.minimum_trust_radius, trust_radius * 0.5)
            consecutive_rejections += 1
            if consecutive_rejections >= configuration.revert_after_rejections:
                row_weights = prior_weights
                cooldown = configuration.revert_cooldown_iterations
                counters["row_equilibration_reverts"] += int(
                    not np.array_equal(proposed_weights, prior_weights)
                )
            if consecutive_rejections >= 6:
                break
            continue
        if step_norm > trust_radius:
            step *= trust_radius / step_norm
            step_norm = trust_radius
        current_z = (current.x - anchor) / variable_scale
        trial_z = np.minimum(np.maximum(current_z + step, lower_z), upper_z)
        delta_z = trial_z - current_z
        trial_x = anchor + variable_scale * trial_z
        try:
            trial = _AD._make_state(case, trial_x, configuration.guard_weight)
        except Exception as error:
            if type(error).__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["rejected_steps"] += 1
            damping = min(configuration.maximum_damping, damping * 10.0)
            trust_radius = max(configuration.minimum_trust_radius, trust_radius * 0.5)
            continue
        if _AD._better(trial, best):
            best = trial

        # Row weights are absent from every acceptance quantity.
        raw_prediction = current.augmented + raw_jacobian @ delta_z
        predicted_objective = 0.5 * float(np.dot(raw_prediction, raw_prediction))
        predicted_reduction = current.objective - predicted_objective
        actual_reduction = current.objective - trial.objective
        raw_ratio = (
            actual_reduction / predicted_reduction
            if predicted_reduction > 0.0 and math.isfinite(predicted_reduction)
            else -math.inf
        )
        accepted, reason = _ROW._raw_nonmonotone_accept(
            trial,
            current,
            tuple(objectives),
            tuple(relation_norms),
            predicted_reduction,
            configuration,
        )
        if accepted:
            current = trial
            row_weights = proposed_weights
            counters["accepted_steps"] += 1
            counters["raw_lexicographic_accepts"] += int(reason == "raw_lexicographic")
            counters["raw_nonmonotone_accepts"] += int(reason == "raw_nonmonotone")
            objectives.append(current.objective)
            relation_norms.append(current.relation_inf)
            consecutive_rejections = 0
            if raw_ratio > 0.75:
                trust_radius = min(
                    configuration.maximum_trust_radius,
                    max(trust_radius, 2.0 * step_norm),
                )
                damping = max(configuration.minimum_damping, damping * 0.3)
            elif raw_ratio < 0.25:
                trust_radius = max(configuration.minimum_trust_radius, trust_radius * 0.5)
                damping = min(configuration.maximum_damping, damping * 3.0)
        else:
            counters["rejected_steps"] += 1
            consecutive_rejections += 1
            trust_radius = max(configuration.minimum_trust_radius, trust_radius * 0.4)
            damping = min(configuration.maximum_damping, damping * 6.0)
            if consecutive_rejections >= configuration.revert_after_rejections:
                row_weights = prior_weights
                cooldown = configuration.revert_cooldown_iterations
                counters["row_equilibration_reverts"] += int(
                    not np.array_equal(proposed_weights, prior_weights)
                )
            if consecutive_rejections >= 8:
                break

    if best.semantics_valid and best.relation_inf <= configuration.success_residual_inf:
        counters["reported_safe_endpoint"] = 1
        status = "safe_root"
    elif time.monotonic() >= deadline_monotonic:
        status = "deadline"
    else:
        status = "stalled_or_budget"
    return CandidateOutcome(best.x.copy(), status, counters)


__all__ = [
    "ADProgram",
    "CandidateOutcome",
    "CONFIGURATIONS",
    "Configuration",
    "Dual",
    "REFERENCE",
    "REFERENCE_NAME",
    "compile_program",
    "configuration_manifest",
    "solve_local",
]
