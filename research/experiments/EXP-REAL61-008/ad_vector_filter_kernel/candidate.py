"""Original-coordinate AD vector-filter local kernel.

The caller supplies one original-coordinate start, one positive per-start
working scale, and the literal source-bound arrays.  The kernel does not
consult compiler chart metadata or any inferred search envelope.  All source
equalities and signed semantic margins are compiled by the parity-checked
vector program, while the untouched evaluator remains endpoint authority.

This is a compute-free EXP-REAL61-008 rebind of the frozen EXP-REAL61-007
algorithm.  It deliberately has no proposal generation or benchmark runner;
the central paired prefix will be bound later.
"""

from __future__ import annotations

import importlib.util
import hashlib
import math
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
FROZEN_CORE = HERE.parents[1] / "EXP-REAL61-007/ad_vector_filter/candidate.py"
FROZEN_CORE_SHA256 = "1ac0391109fa0ffac525c552523044d464568e73b09ec4ff961d42cb110418f5"


def _load_frozen_core():
    if hashlib.sha256(FROZEN_CORE.read_bytes()).hexdigest() != FROZEN_CORE_SHA256:
        raise RuntimeError("frozen EXP-REAL61-007 vector-filter core changed")
    name = "geotarget_exp008_vector_filter_frozen_mechanism"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, FROZEN_CORE)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_CORE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CORE = _load_frozen_core()

CANDIDATE = "ad_vector_filter_original_coordinate_kernel"
Configuration = CORE.Configuration
CandidateOutcome = CORE.CandidateOutcome
MarginProgram = CORE.MarginProgram
CONFIGURATION = CORE.CONFIGURATION
compile_program = CORE.compile_program


def _same_source_array(left: np.ndarray, right: np.ndarray) -> bool:
    return bool(left.shape == right.shape and np.array_equal(left, right))


def _initial_counters() -> dict[str, int]:
    return {
        "starts_attempted": 1,
        "iterations": 0,
        "restoration_steps": 0,
        "restoration_tangential_equality_rows": 0,
        "root_steps": 0,
        "accepted_steps": 0,
        "rejected_steps": 0,
        "filter_rejections": 0,
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
        "linear_failures": 0,
        "fraction_to_boundary_steps": 0,
        "semantic_entries": 0,
        "reported_safe_endpoint": 0,
        "budget_stops": 0,
        "deadline_stops": 0,
    }


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
    """Solve one lane without consulting any search/compiler chart metadata."""

    dimension = int(program.dimension)
    start = np.asarray(start_original, dtype=float)
    scale = np.asarray(per_start_scale, dtype=float)
    lower = np.asarray(source_lower, dtype=float)
    upper = np.asarray(source_upper, dtype=float)
    expected_shape = (dimension,)
    if any(values.shape != expected_shape for values in (start, scale, lower, upper)):
        raise ValueError("start, scale, and source bounds must match source dimension")
    if not np.all(np.isfinite(start)):
        raise ValueError("original-coordinate start must be finite")
    if not np.all(np.isfinite(scale)) or np.any(scale <= 0.0):
        raise ValueError("per-start working scale must be finite and positive")
    if np.any(np.isnan(lower)) or np.any(np.isnan(upper)) or np.any(lower >= upper):
        raise ValueError("source bounds are malformed")
    if not _same_source_array(lower, np.asarray(program.lower, dtype=float)) or not _same_source_array(
        upper, np.asarray(program.upper, dtype=float)
    ):
        raise ValueError("caller bounds differ from literal source bounds")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")

    counters = _initial_counters()
    center = start.copy()
    lower_working = (lower - center) / scale
    upper_working = (upper - center) / scale
    initial = np.minimum(np.maximum(start, lower), upper)
    try:
        current = CORE._make_state(
            evaluator_case, program, initial, configuration, counters
        )
    except Exception as error:
        if error.__class__.__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(initial.copy(), "budget_before_start", counters)
        raise

    best = current
    radius = configuration.initial_trust_radius
    filter_entries: list[tuple[float, float]] = [(current.phi, current.theta)]
    stagnation = 0

    for _ in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if current.semantics_valid and current.equality_inf <= configuration.equality_goal_inf:
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1
        try:
            equality_jacobian, margin_jacobian = CORE._fill_fd_rows(
                evaluator_case,
                program,
                current,
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

        infeasible = (
            current.theta > configuration.margin_tolerance
            or not current.semantics_valid
        )
        if infeasible:
            active = np.flatnonzero(
                current.margins < configuration.active_margin_band
            )
            if active.size == 0:
                active = np.arange(current.margins.size)
            violation = np.minimum(current.margins[active], 0.0)
            equality_weight = min(
                1.0,
                max(current.theta, configuration.margin_tolerance)
                / max(current.phi, configuration.margin_tolerance),
            )
            matrix = np.vstack(
                (margin_jacobian[active], equality_weight * equality_jacobian)
            )
            rhs = np.concatenate(
                (-violation, -equality_weight * current.equality)
            )
            counters["restoration_steps"] += 1
            counters["restoration_tangential_equality_rows"] += int(
                equality_jacobian.shape[0]
            )
        else:
            matrix = equality_jacobian
            rhs = -current.equality
            counters["root_steps"] += 1

        step = CORE._minimum_norm_step(
            matrix, rhs, configuration.rank_rtol, counters
        )
        step_norm = float(np.linalg.norm(step))
        if not math.isfinite(step_norm) or step_norm == 0.0:
            radius *= 0.25
            stagnation += 1
            if radius < configuration.minimum_trust_radius or stagnation >= 5:
                break
            continue
        if step_norm > radius:
            step *= radius / step_norm
            step_norm = radius

        if not infeasible:
            directional = margin_jacobian @ step
            threatened = np.flatnonzero(
                (directional < 0.0)
                & (current.margins + directional < 0.0)
            )
            if threatened.size:
                fractions = (
                    0.9
                    * current.margins[threatened]
                    / -directional[threatened]
                )
                alpha = max(0.0, min(1.0, float(np.min(fractions))))
                step *= alpha
                step_norm *= alpha
                counters["fraction_to_boundary_steps"] += 1

        current_working = (current.x - center) / scale
        accepted = False
        for fraction in (1.0, 0.5, 0.25):
            trial_working = np.minimum(
                np.maximum(
                    current_working + fraction * step,
                    lower_working,
                ),
                upper_working,
            )
            trial_point = center + scale * trial_working
            try:
                trial = CORE._make_state(
                    evaluator_case,
                    program,
                    trial_point,
                    configuration,
                    counters,
                )
            except Exception as error:
                if error.__class__.__name__ == "BudgetExceeded":
                    counters["budget_stops"] += 1
                    break
                continue
            if CORE._better(trial, best):
                best = trial
            filter_ok = CORE._filter_acceptable(
                trial.phi,
                trial.theta,
                filter_entries,
                configuration.filter_gamma,
            )
            feasibility_progress = trial.theta <= max(
                configuration.margin_tolerance,
                (1.0 - configuration.sufficient_decrease) * current.theta,
            )
            root_progress = (
                trial.theta
                <= max(configuration.margin_tolerance, 1.05 * current.theta)
                and trial.phi
                <= (1.0 - configuration.sufficient_decrease) * current.phi
            )
            semantic_entry = trial.semantics_valid and not current.semantics_valid
            if filter_ok and (
                feasibility_progress or root_progress or semantic_entry
            ):
                current = trial
                CORE._insert_filter(
                    filter_entries, (trial.phi, trial.theta)
                )
                counters["accepted_steps"] += 1
                counters["semantic_entries"] += int(semantic_entry)
                accepted = True
                stagnation = 0
                radius = min(
                    configuration.maximum_trust_radius,
                    max(radius, 1.8 * fraction * step_norm),
                )
                break
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
        "coordinate_input": "caller_original_start_plus_positive_per_start_scale",
        "hard_bounds": "literal_source_bounds_only",
        "proposal_generation": False,
        "case_identity_or_truth_input": False,
        "untouched_evaluator_is_endpoint_authority": True,
        "frozen_mechanism_sha256": FROZEN_CORE_SHA256,
    }


__all__ = [
    "CANDIDATE",
    "CONFIGURATION",
    "CandidateOutcome",
    "Configuration",
    "MarginProgram",
    "compile_program",
    "kernel_manifest",
    "solve_local",
]
