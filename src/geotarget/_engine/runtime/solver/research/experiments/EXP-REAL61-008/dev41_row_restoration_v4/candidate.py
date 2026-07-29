"""Row-equilibrated lexicographic restoration/filter local kernel.

This disposable combination retains exactly two already-tested mechanisms:

* the frozen start-local dynamic row equilibration used by the dev41 local
  survivor, applied only to the equality residual/Jacobian used to construct
  a step; and
* the corrected restoration/filter acceptance policy whose comparison
  resolution is compatible with the original-evaluator root goal.

All trials remain in the original source variables.  The caller supplies the
original-coordinate start, a numerical per-start scale, and literal source
bounds.  Missing source bounds remain infinite.  Row weights never affect
semantic decisions, filter acceptance, best-point selection, termination, or
endpoint authority.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
EXP008 = HERE.parent
CORRECTIVE_PATH = (
    EXP008 / "dev41_restoration_filter_v3/acceptance_corrective/candidate.py"
)
ROW_SURVIVOR_PATH = EXP008 / "ad_row_equilibration_rebind/candidate.py"
CORRECTIVE_SHA256 = "a2279ffa1b3ee31a6fbe501e7bbcb1d00c211bc43bdc76bbdfa83a2bcaa49b72"
ROW_SURVIVOR_SHA256 = "59a021f7a5628dcf03010e7cc2035ce2582e61f092235164f635e159b5f48e9a"


def _load(name: str, path: Path, expected: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound combined-kernel dependency changed: {name}")
    module_name = f"geotarget_exp008_row_restoration_v4_{name}"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


CORRECTIVE = _load("acceptance_corrective", CORRECTIVE_PATH, CORRECTIVE_SHA256)
ROW = _load("row_survivor", ROW_SURVIVOR_PATH, ROW_SURVIVOR_SHA256)
BASE = CORRECTIVE.BASE

MarginProgram = BASE.MarginProgram
CandidateOutcome = BASE.CandidateOutcome
Configuration = BASE.Configuration
compile_program = BASE.compile_program

COMBINED = "source_literal_row_equilibrated_restoration_filter_corrective"
CONFIGURATION = CORRECTIVE.replace(CORRECTIVE.CONFIGURATION, name=COMBINED)
CONFIGURATIONS = {COMBINED: CONFIGURATION}


def _add(counters: dict[str, int], values: Mapping[str, int]) -> None:
    for name, value in values.items():
        counters[name] = counters.get(name, 0) + int(value)


def _row_equilibrate(
    equality_jacobian: np.ndarray,
    previous: np.ndarray,
) -> tuple[np.ndarray, dict[str, int]]:
    """Use the frozen survivor's row-equilibration rule without retuning."""

    return ROW._ROW._equilibrate_rows(  # noqa: SLF001 - hash-bound prototype seam
        equality_jacobian, previous, ROW.REFERENCE
    )


def _row_restoration_step(
    state: object,
    equality_jacobian: np.ndarray,
    margin_jacobian: np.ndarray,
    weighted_equality_jacobian: np.ndarray,
    weighted_equality_residual: np.ndarray,
    configuration: Configuration,
    counters: dict[str, int],
) -> np.ndarray:
    """Frozen restoration normal step plus row-equilibrated tangential step."""

    violations = np.maximum(0.0, -np.asarray(state.base.margins, dtype=float))
    active = np.flatnonzero(violations > configuration.margin_tolerance)
    if active.size == 0:
        active = np.flatnonzero(
            np.asarray(state.base.margins, dtype=float)
            < configuration.active_margin_band
        )
    normal = np.zeros(equality_jacobian.shape[1], dtype=float)
    active_matrix = np.empty((0, equality_jacobian.shape[1]), dtype=float)
    if active.size:
        active_matrix = np.asarray(margin_jacobian[active], dtype=float)
        margin_row_norm = np.maximum(1.0, np.linalg.norm(active_matrix, axis=1))
        normal = BASE.CORE.CORE._minimum_norm_step(
            active_matrix / margin_row_norm[:, None],
            violations[active] / margin_row_norm,
            configuration.rank_rtol,
            counters,
        )
        counters["restoration_rows"] += int(active.size)

    null = BASE._nullspace(active_matrix, configuration.rank_rtol, counters)
    if null.shape[1]:
        tangential = BASE.CORE.CORE._minimum_norm_step(
            weighted_equality_jacobian @ null,
            -weighted_equality_residual - weighted_equality_jacobian @ normal,
            configuration.rank_rtol,
            counters,
        )
        normal = normal + null @ tangential
        counters["nullspace_tangential_steps"] += 1

    if not np.any(np.isfinite(normal)) or float(np.linalg.norm(normal)) == 0.0:
        normal = BASE.CORE.CORE._minimum_norm_step(
            weighted_equality_jacobian,
            -weighted_equality_residual,
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
    """Run one original-coordinate lane with the two frozen mechanisms."""

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
    if not BASE._same_source_array(
        lower, np.asarray(program.lower, dtype=float)
    ) or not BASE._same_source_array(upper, np.asarray(program.upper, dtype=float)):
        raise ValueError("caller bounds differ from literal source bounds")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")

    counters = BASE._initial_counters()
    counters.update(
        {
            "row_equilibration_updates": 0,
            "row_equilibration_active_rows": 0,
            "row_equilibration_changed_rows": 0,
            "row_equilibration_ratio_cap_hits": 0,
            "row_equilibration_absolute_cap_hits": 0,
            "row_equilibration_reverts": 0,
            "row_equilibration_cooldown_iterations": 0,
        }
    )
    tracker = BASE._ObservationTracker(evaluator_case)
    center = start.copy()
    lower_working = (lower - center) / scale
    upper_working = (upper - center) / scale
    initial = np.minimum(np.maximum(start, lower), upper)
    try:
        current, equality_scale = BASE._make_lex_state(
            tracker, program, initial, None, configuration, counters
        )
    except Exception as error:
        if error.__class__.__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(initial.copy(), "budget_before_start", counters)
        raise

    best = current
    filter_entries = [BASE._entry(current)]
    radius = configuration.initial_trust_radius
    stagnation = 0
    row_weights = np.ones(np.asarray(current.base.equality).size, dtype=float)
    consecutive_rejections = 0
    cooldown = 0

    for _iteration in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if current.semantics_valid and current.equality_inf <= configuration.equality_goal_inf:
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1
        try:
            equality_jacobian, margin_jacobian = BASE.CORE.CORE._fill_fd_rows(
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

        prior_weights = row_weights.copy()
        if cooldown:
            proposed_weights = prior_weights
            cooldown -= 1
            counters["row_equilibration_cooldown_iterations"] += 1
        else:
            proposed_weights, diagnostics = _row_equilibrate(
                equality_jacobian, prior_weights
            )
            _add(counters, diagnostics)
            counters["row_equilibration_updates"] += int(
                diagnostics["row_equilibration_changed_rows"] > 0
            )
        weighted_equality_jacobian = proposed_weights[:, None] * equality_jacobian
        weighted_equality_residual = proposed_weights * np.asarray(
            current.base.equality, dtype=float
        )

        infeasible = bool(
            not current.finite_construction
            or not current.semantics_valid
            or np.any(
                np.asarray(current.base.margins, dtype=float)
                < -configuration.margin_tolerance
            )
        )
        if infeasible:
            step = _row_restoration_step(
                current,
                equality_jacobian,
                margin_jacobian,
                weighted_equality_jacobian,
                weighted_equality_residual,
                configuration,
                counters,
            )
        else:
            step = BASE.CORE.CORE._minimum_norm_step(
                weighted_equality_jacobian,
                -weighted_equality_residual,
                configuration.rank_rtol,
                counters,
            )
            counters["root_steps"] += 1

        step_norm = float(np.linalg.norm(step))
        if not math.isfinite(step_norm) or step_norm == 0.0:
            radius *= 0.25
            stagnation += 1
            consecutive_rejections += 1
            if consecutive_rejections >= ROW.REFERENCE.revert_after_rejections:
                cooldown = ROW.REFERENCE.revert_cooldown_iterations
                counters["row_equilibration_reverts"] += int(
                    not np.array_equal(proposed_weights, prior_weights)
                )
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
                trial, _same_scale = BASE._make_lex_state(
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
            if CORRECTIVE._lex_compare(trial, best, configuration) < 0:
                best = trial
            lex_better = CORRECTIVE._lex_compare(trial, current, configuration) < 0
            filter_ok = not CORRECTIVE._filter_dominated(
                trial, filter_entries, configuration
            )
            if lex_better and filter_ok:
                finite_entry = trial.finite_construction and not current.finite_construction
                current = trial
                row_weights = proposed_weights
                BASE._insert_filter(filter_entries, trial, configuration)
                counters["accepted_steps"] += 1
                counters["finite_construction_entries"] += int(finite_entry)
                accepted = True
                stagnation = 0
                consecutive_rejections = 0
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
            consecutive_rejections += 1
            radius *= 0.3
            if consecutive_rejections >= ROW.REFERENCE.revert_after_rejections:
                cooldown = ROW.REFERENCE.revert_cooldown_iterations
                counters["row_equilibration_reverts"] += int(
                    not np.array_equal(proposed_weights, prior_weights)
                )
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


def kernel_manifest() -> dict[str, object]:
    return {
        "name": COMBINED,
        "mechanisms": [
            "frozen dynamic equality-row equilibration for step construction",
            "corrected lexicographic restoration/filter acceptance",
        ],
        "row_survivor_sha256": ROW_SURVIVOR_SHA256,
        "acceptance_corrective_sha256": CORRECTIVE_SHA256,
        "row_configuration_retuned": False,
        "restoration_or_acceptance_configuration_retuned": False,
        "row_scaling_scope": "equality residual/Jacobian step construction only",
        "acceptance_authority": "untouched original evaluator state",
        "coordinates": "all original source variables",
        "hard_bounds": "literal source bounds only",
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "gauge_or_symmetry_reduction": False,
        "added_or_inferred_bounds": False,
        "case_identity_family_truth_target_count_inputs": False,
        "untouched_original_evaluator_final_authority": True,
    }


__all__ = [
    "COMBINED",
    "CONFIGURATION",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "MarginProgram",
    "compile_program",
    "kernel_manifest",
    "solve_local",
]
