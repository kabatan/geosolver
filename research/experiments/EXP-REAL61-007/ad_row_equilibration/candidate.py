"""Forward-AD, dynamically row-equilibrated nonmonotone LM/CPQR.

This disposable candidate imports the frozen EXP-REAL61-006 source-semantic
forward-AD interpreter.  The untouched evaluator remains authoritative for
every residual value, semantic decision, acceptance decision, and endpoint.
Analytic rows are used only after value parity; all other rows use the frozen
charged one-sided finite-difference fallback.

Dynamic row weights are computed from robust Jacobian row norms and affect
only the linearized step.  They never change the residual supplied to the raw
nonmonotone acceptance test.  Weight changes are ratio/absolute capped and are
rolled back with a short cooldown after repeated rejected steps.  No source
equation, variable, guard, branch, bound, gauge, or parameterization changes.
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


def _load_frozen(path: Path, module_name: str) -> ModuleType:
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


_AD = _load_frozen(FROZEN_AD_PATH, "geotarget_exp007_frozen_forward_ad_rowscale")

ADProgram = _AD.ADProgram
Dual = _AD.Dual
compile_program = _AD.compile_program


REFERENCE_NAME = "ad_dynamic_row_equilibrated_cpqr"


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
        "mechanism": "forward-AD robust dynamic row equilibration nonmonotone LM CPQR",
        "frozen_ad_sha256": hashlib.sha256(FROZEN_AD_PATH.read_bytes()).hexdigest(),
        "row_scaling_scope": "linearized step only",
        "acceptance_authority": "untouched raw residual and semantic evaluator",
        "endpoint_authority": "untouched evaluator replay",
        "source_rewrite": False,
        "variable_or_equation_elimination": False,
        "gauge_or_symmetry_reduction": False,
        "inferred_or_artificial_bounds": False,
        "case_identity_available": False,
        "truth_or_target_count_available": False,
        "runtime_case_or_family_routing": False,
        "maximum_weight_update_ratio": configuration.maximum_weight_update_ratio,
        "row_weight_limits": [
            configuration.minimum_row_weight,
            configuration.maximum_row_weight,
        ],
        "nonmonotone_window": configuration.nonmonotone_window,
        "revert_after_rejections": configuration.revert_after_rejections,
    }


def _equilibrate_rows(
    jacobian: np.ndarray,
    previous: np.ndarray,
    configuration: Configuration,
) -> tuple[np.ndarray, dict[str, int]]:
    """Return a robust, ratio-capped row scaling for step construction only."""

    matrix = np.asarray(jacobian, dtype=float)
    prior = np.asarray(previous, dtype=float)
    if matrix.ndim != 2 or prior.shape != (matrix.shape[0],):
        raise ValueError("row-equilibration shape mismatch")
    norms = np.linalg.norm(matrix, axis=1)
    finite_positive = np.isfinite(norms) & (norms > np.finfo(float).tiny)
    diagnostics = {
        "row_equilibration_active_rows": int(np.count_nonzero(finite_positive)),
        "row_equilibration_ratio_cap_hits": 0,
        "row_equilibration_absolute_cap_hits": 0,
        "row_equilibration_changed_rows": 0,
    }
    if not np.any(finite_positive):
        return prior.copy(), diagnostics

    # The log median remains meaningful across the extreme row scales seen in
    # the real geometry corpus and is insensitive to a few enormous rows.
    typical = float(np.exp(np.median(np.log(norms[finite_positive]))))
    if not math.isfinite(typical) or typical <= 0.0:
        return prior.copy(), diagnostics
    effective = np.clip(
        norms,
        typical * configuration.row_norm_floor_relative,
        typical * configuration.row_norm_ceiling_relative,
    )
    desired = np.ones_like(prior)
    desired[finite_positive] = typical / effective[finite_positive]
    unclipped_desired = desired.copy()
    desired = np.clip(
        desired,
        configuration.minimum_row_weight,
        configuration.maximum_row_weight,
    )
    diagnostics["row_equilibration_absolute_cap_hits"] = int(
        np.count_nonzero(desired != unclipped_desired)
    )

    # Relax in log space, then limit the multiplicative change relative to the
    # last accepted scaling.  This prevents one noisy Jacobian from flipping
    # the metric by many orders of magnitude.
    safe_prior = np.clip(
        prior,
        configuration.minimum_row_weight,
        configuration.maximum_row_weight,
    )
    relaxed = np.exp(
        (1.0 - configuration.row_weight_relaxation) * np.log(safe_prior)
        + configuration.row_weight_relaxation * np.log(desired)
    )
    ratio = relaxed / safe_prior
    ratio_limit = configuration.maximum_weight_update_ratio
    clipped_ratio = np.clip(ratio, 1.0 / ratio_limit, ratio_limit)
    diagnostics["row_equilibration_ratio_cap_hits"] = int(
        np.count_nonzero(clipped_ratio != ratio)
    )
    result = np.clip(
        safe_prior * clipped_ratio,
        configuration.minimum_row_weight,
        configuration.maximum_row_weight,
    )
    # Locally constant inactive rows have no step information and retain their
    # previous weight rather than receiving an arbitrary large multiplier.
    result[~finite_positive] = safe_prior[~finite_positive]
    diagnostics["row_equilibration_changed_rows"] = int(
        np.count_nonzero(np.abs(np.log(result / safe_prior)) > 1.0e-12)
    )
    return result, diagnostics


def _raw_nonmonotone_accept(
    trial: object,
    current: object,
    objective_history: Sequence[float],
    relation_inf_history: Sequence[float],
    raw_predicted_reduction: float,
    configuration: Configuration,
) -> tuple[bool, str]:
    """Accept using raw untouched residual/semantic values only."""

    if _AD._better(trial, current):
        return True, "raw_lexicographic"
    if not bool(current.semantics_valid) or not bool(trial.semantics_valid):
        return False, "raw_semantic_reject"
    finite_objectives = [float(value) for value in objective_history if math.isfinite(value)]
    finite_inf = [float(value) for value in relation_inf_history if math.isfinite(value)]
    if not finite_objectives or not finite_inf or not math.isfinite(trial.objective):
        return False, "raw_nonfinite_reject"
    reference = max(finite_objectives)
    required = configuration.sufficient_decrease * max(
        0.0,
        raw_predicted_reduction if math.isfinite(raw_predicted_reduction) else 0.0,
    )
    inf_limit = configuration.nonmonotone_inf_growth * max(finite_inf)
    accepted = bool(
        trial.objective <= reference - required
        and trial.relation_inf <= inf_limit
    )
    return accepted, "raw_nonmonotone" if accepted else "raw_merit_reject"


def _add_diagnostics(counters: dict[str, int], values: Mapping[str, int]) -> None:
    for name, value in values.items():
        counters[name] = counters.get(name, 0) + int(value)


def solve_local(
    case: object,
    program: ADProgram,
    configuration: Configuration,
    start: Sequence[float],
    *,
    max_callbacks: int,
    deadline_monotonic: float,
) -> CandidateOutcome:
    """Run one unchanged-coordinate, raw-authority local solve."""

    if program.dimension != int(case.dimension) or program.residual_dimension != int(
        case.residual_dimension
    ):
        raise ValueError("AD program shape differs from the original evaluator")
    point = np.asarray(start, dtype=float)
    if point.shape != (program.dimension,) or not np.all(np.isfinite(point)):
        raise ValueError("start has wrong shape or is nonfinite")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")
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
    }
    origin = np.asarray(case.origin, dtype=float)
    variable_scales = np.asarray(case.scales, dtype=float)
    lower = np.asarray(case.lower, dtype=float)
    upper = np.asarray(case.upper, dtype=float)
    if (
        origin.shape != point.shape
        or variable_scales.shape != point.shape
        or not np.all(np.isfinite(origin))
        or not np.all(np.isfinite(variable_scales))
        or np.any(variable_scales <= 0.0)
    ):
        raise ValueError("opaque compiler scale metadata is invalid")
    lower_z = (lower - origin) / variable_scales
    upper_z = (upper - origin) / variable_scales
    clipped = np.minimum(np.maximum(point, lower), upper)
    try:
        current = _AD._make_state(case, clipped, configuration.guard_weight)
    except Exception as error:
        if type(error).__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(clipped.copy(), "budget_before_start", counters)
        raise
    best = current
    trust_radius = configuration.initial_trust_radius
    damping = configuration.initial_damping
    row_weights = np.ones(current.augmented.size, dtype=float)
    objective_history: deque[float] = deque(
        [current.objective], maxlen=configuration.nonmonotone_window
    )
    relation_inf_history: deque[float] = deque(
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
                origin,
                variable_scales,
                lower_z,
                upper_z,
                configuration,
                counters,
            )
            prior_weights = row_weights.copy()
            if cooldown > 0:
                proposed_weights = prior_weights
                cooldown -= 1
                counters["row_equilibration_cooldown_iterations"] += 1
            else:
                proposed_weights, diagnostics = _equilibrate_rows(
                    raw_jacobian, prior_weights, configuration
                )
                _add_diagnostics(counters, diagnostics)
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
                counters["row_equilibration_reverts"] += int(
                    not np.array_equal(proposed_weights, prior_weights)
                )
                row_weights = prior_weights
                cooldown = configuration.revert_cooldown_iterations
            if consecutive_rejections >= 6:
                break
            continue
        if step_norm > trust_radius:
            step *= trust_radius / step_norm
            step_norm = trust_radius
        current_z = (current.x - origin) / variable_scales
        trial_z = np.minimum(np.maximum(current_z + step, lower_z), upper_z)
        delta_z = trial_z - current_z
        trial_x = origin + variable_scales * trial_z
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

        # All acceptance/globalization quantities below are computed in the
        # unscaled, untouched residual metric.  Row scaling has already served
        # its sole purpose by selecting ``step`` above.
        raw_predicted = current.augmented + raw_jacobian @ delta_z
        raw_predicted_objective = 0.5 * float(np.dot(raw_predicted, raw_predicted))
        raw_predicted_reduction = current.objective - raw_predicted_objective
        raw_actual_reduction = current.objective - trial.objective
        raw_ratio = (
            raw_actual_reduction / raw_predicted_reduction
            if raw_predicted_reduction > 0.0
            and math.isfinite(raw_predicted_reduction)
            else -math.inf
        )
        accepted, reason = _raw_nonmonotone_accept(
            trial,
            current,
            tuple(objective_history),
            tuple(relation_inf_history),
            raw_predicted_reduction,
            configuration,
        )
        if accepted:
            current = trial
            row_weights = proposed_weights
            counters["accepted_steps"] += 1
            counters["raw_lexicographic_accepts"] += int(reason == "raw_lexicographic")
            counters["raw_nonmonotone_accepts"] += int(reason == "raw_nonmonotone")
            objective_history.append(current.objective)
            relation_inf_history.append(current.relation_inf)
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
                counters["row_equilibration_reverts"] += int(
                    not np.array_equal(proposed_weights, prior_weights)
                )
                row_weights = prior_weights
                cooldown = configuration.revert_cooldown_iterations
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
