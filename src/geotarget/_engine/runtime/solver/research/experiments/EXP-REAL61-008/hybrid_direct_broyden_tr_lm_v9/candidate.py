"""Event-refreshed direct-Broyden TR/LM for expensive source evaluators.

The kernel acquires one source-semantic hybrid AD/charged-FD Jacobian in the
caller's start-local step coordinates.  Accepted moves update that *direct*
augmented Jacobian with the good-Broyden rank-one secant formula.  A full
Jacobian is requested only after measured model-quality failure or a
semantic-invalid trial; there is no iteration-, rank-, or column-scheduled
refresh.

All residuals, guards, acceptance decisions, trials, and endpoints remain in
the untouched original problem.  The caller supplies only source-declared
bounds.  Two-sided Ruiz scaling is a bounded linear-algebra preconditioner of
the current raw model and never changes the model used for acceptance.
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
from typing import Callable, Mapping, MutableMapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
EXP008 = HERE.parent
ROW_PATH = EXP008 / "ad_row_equilibration_rebind/candidate.py"
CACHE_PATH = EXP008 / "same_current_jacobian_cache_v9/candidate.py"
RUIZ_PATH = EXP008 / "iterative_two_sided_ruiz_lm_v1/candidate.py"
EXPECTED_SHA256 = {
    "row": "59a021f7a5628dcf03010e7cc2035ce2582e61f092235164f635e159b5f48e9a",
    "cache": "06c516e9b304fca6ca8d86cba793eb4d66bbcda8ead31ad1cb755cc89c297c5c",
    "ruiz": "6a0d1cda0f049648e0948e43f43313425d19704836761bab10327aef24488e62",
}


def _load(label: str, path: Path) -> ModuleType:
    expected = EXPECTED_SHA256[label]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound direct-Broyden dependency changed: {label}")
    name = f"geotarget_exp008_hybrid_direct_broyden_{label}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


_ROW = _load("row", ROW_PATH)
_CACHE = _load("cache", CACHE_PATH)
_RUIZ = _load("ruiz", RUIZ_PATH)

ADProgram = _ROW.ADProgram
compile_program = _ROW.compile_program
CandidateOutcome = _ROW.CandidateOutcome
REFERENCE_NAME = "precision_isolated_event_refreshed_direct_broyden_ruiz_tr_lm"


@dataclass(frozen=True)
class Configuration:
    name: str = REFERENCE_NAME
    base_configuration: object = _ROW.REFERENCE
    ruiz_configuration: object = _RUIZ.REFERENCE
    maximum_iterations: int = 96
    denominator_rtol: float = 1.0e-14
    secant_defect_refresh: float = 0.85
    poor_model_ratio: float = 0.05
    poor_model_refresh_after: int = 2
    maximum_consecutive_rejections: int = 8
    maximum_consecutive_linear_failures: int = 2


REFERENCE = Configuration()
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}


class _StopLocal(RuntimeError):
    pass


def _counter_template() -> dict[str, int]:
    counters = {
        "starts_attempted": 1,
        "iterations": 0,
        "accepted_steps": 0,
        "rejected_steps": 0,
        "raw_lexicographic_accepts": 0,
        "raw_nonmonotone_accepts": 0,
        "initial_state_evaluations": 0,
        "trial_state_evaluations": 0,
        "analytic_relation_rows": 0,
        "analytic_guard_rows": 0,
        "analytic_inactive_hard_rows": 0,
        "analytic_rows_total": 0,
        "fd_fallback_rows_total": 0,
        "relation_parity_fallback_rows": 0,
        "guard_parity_fallback_rows": 0,
        "fd_direction_evaluations": 0,
        "initial_fresh_jacobian_builds": 0,
        "full_jacobian_builds": 0,
        "full_jacobian_refresh_builds": 0,
        "full_jacobian_refresh_requests": 0,
        "full_jacobian_cache_restores": 0,
        "same_current_raw_jacobian_cache_hits": 0,
        "same_current_raw_jacobian_cache_misses": 0,
        "same_current_raw_jacobian_invalidations": 0,
        "same_current_fd_direction_evaluations_avoided": 0,
        "same_current_cache_state_mutations": 0,
        "model_quality_refresh_requests": 0,
        "semantic_invalid_refresh_requests": 0,
        "poor_ratio_refresh_requests": 0,
        "secant_defect_refresh_requests": 0,
        "linear_failure_refresh_requests": 0,
        "zero_step_refresh_requests": 0,
        "denominator_refresh_requests": 0,
        "direct_broyden_updates": 0,
        "direct_broyden_denominator_skips": 0,
        "direct_broyden_secant_checks": 0,
        "direct_broyden_secant_check_failures": 0,
        "rank_deficient_iterations": 0,
        "trust_region_step_clips": 0,
        "explicit_source_bound_projections": 0,
        "semantic_invalid_trials": 0,
        "nonpositive_model_predictions": 0,
        "poor_model_ratio_trials": 0,
        "linear_failures": 0,
        "zero_step_failures": 0,
        "reported_safe_endpoint": 0,
        "deadline_stops": 0,
        "budget_stops": 0,
        "compiler_coordinate_metadata_reads": 0,
        "legacy_or_inferred_bound_reads": 0,
        "scheduled_refreshes": 0,
        "case_identity_routes": 0,
    }
    counters.update(_RUIZ._counter_template())
    return counters


class _RawJacobianCache:
    """Exact same-current raw-J cache using the reviewed v9 cache key."""

    def __init__(self) -> None:
        self.state: object | None = None
        self.x: np.ndarray | None = None
        self.augmented: np.ndarray | None = None
        self.raw: np.ndarray | None = None
        self.fd_calls = 0

    def get_or_build(
        self,
        state: object,
        build: Callable[[], np.ndarray],
        counters: MutableMapping[str, int],
        *,
        initial: bool,
    ) -> np.ndarray:
        if state is self.state:
            key_equal = bool(
                self.x is not None
                and self.augmented is not None
                and _CACHE._bitwise_equal(state.x, self.x)
                and _CACHE._bitwise_equal(state.augmented, self.augmented)
            )
            if not key_equal:
                counters["same_current_cache_state_mutations"] += 1
                raise RuntimeError("cached direct-Broyden state mutated in place")
            if self.raw is None:
                raise RuntimeError("same-current cache lost its raw Jacobian")
            counters["same_current_raw_jacobian_cache_hits"] += 1
            counters["full_jacobian_cache_restores"] += 1
            counters["same_current_fd_direction_evaluations_avoided"] += self.fd_calls
            return self.raw.copy()

        if self.state is not None:
            counters["same_current_raw_jacobian_invalidations"] += 1
        before = int(counters["fd_direction_evaluations"])
        raw = np.asarray(build(), dtype=float)
        after = int(counters["fd_direction_evaluations"])
        if raw.ndim != 2 or raw.shape[0] != state.augmented.size:
            raise ValueError("hybrid raw Jacobian has the wrong shape")
        if not np.all(np.isfinite(raw)):
            raise ValueError("hybrid raw Jacobian is non-finite")
        self.state = state
        self.x = np.asarray(state.x).copy()
        self.augmented = np.asarray(state.augmented).copy()
        self.raw = raw.copy()
        self.fd_calls = max(0, after - before)
        counters["same_current_raw_jacobian_cache_misses"] += 1
        counters["full_jacobian_builds"] += 1
        if initial:
            counters["initial_fresh_jacobian_builds"] += 1
        else:
            counters["full_jacobian_refresh_builds"] += 1
        return raw


def _good_broyden_update(
    matrix: np.ndarray,
    step: np.ndarray,
    residual_change: np.ndarray,
    denominator_rtol: float,
) -> tuple[np.ndarray, float | None, bool]:
    """Return the direct good-Broyden update and pre-update secant defect."""

    model = np.asarray(matrix, dtype=float)
    delta = np.asarray(step, dtype=float)
    change = np.asarray(residual_change, dtype=float)
    if model.ndim != 2 or delta.shape != (model.shape[1],):
        raise ValueError("Broyden matrix/step shapes disagree")
    if change.shape != (model.shape[0],):
        raise ValueError("Broyden residual-change shape disagrees")
    predicted = model @ delta
    defect_vector = change - predicted
    scale = max(
        float(np.linalg.norm(change)),
        float(np.linalg.norm(predicted)),
        np.finfo(float).tiny,
    )
    defect = float(np.linalg.norm(defect_vector)) / scale
    denominator = float(np.dot(delta, delta))
    threshold = float(denominator_rtol) * max(
        1.0, float(np.linalg.norm(delta, ord=np.inf)) ** 2
    )
    usable = bool(
        math.isfinite(denominator)
        and denominator > threshold
        and math.isfinite(defect)
        and np.all(np.isfinite(defect_vector))
    )
    if not usable:
        return model.copy(), defect if math.isfinite(defect) else None, False
    updated = model + np.outer(defect_vector, delta) / denominator
    if not np.all(np.isfinite(updated)):
        return model.copy(), defect, False
    return updated, defect, True


def _request_refresh(counters: MutableMapping[str, int], reason: str) -> None:
    counters["full_jacobian_refresh_requests"] += 1
    if reason == "semantic_invalid":
        counters["semantic_invalid_refresh_requests"] += 1
        return
    counters["model_quality_refresh_requests"] += 1
    key = {
        "poor_ratio": "poor_ratio_refresh_requests",
        "secant_defect": "secant_defect_refresh_requests",
        "linear_failure": "linear_failure_refresh_requests",
        "zero_step": "zero_step_refresh_requests",
        "denominator": "denominator_refresh_requests",
    }[reason]
    counters[key] += 1


def _raw_prediction(
    current: object, matrix: np.ndarray, step: np.ndarray
) -> tuple[float, float]:
    predicted = np.asarray(current.augmented) + matrix @ step
    predicted_objective = 0.5 * float(np.dot(predicted, predicted))
    reduction = float(current.objective) - predicted_objective
    return predicted_objective, reduction


def _validate_configuration(configuration: Configuration) -> None:
    if configuration.maximum_iterations < 1:
        raise ValueError("maximum_iterations must be positive")
    if not (0.0 < configuration.denominator_rtol < 1.0):
        raise ValueError("denominator_rtol must lie in (0,1)")
    if not (0.0 < configuration.secant_defect_refresh < 2.0):
        raise ValueError("secant_defect_refresh must lie in (0,2)")
    if not (0.0 <= configuration.poor_model_ratio < 1.0):
        raise ValueError("poor_model_ratio must lie in [0,1)")
    if configuration.poor_model_refresh_after < 1:
        raise ValueError("poor_model_refresh_after must be positive")


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
    """Solve with one initial hybrid J and event-only direct-Broyden refresh."""

    if not isinstance(configuration, Configuration):
        raise TypeError("direct-Broyden Configuration is required")
    _validate_configuration(configuration)
    base = configuration.base_configuration
    anchor, variable_scale, explicit_lower, explicit_upper = _ROW._coordinate_inputs(
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
    counters = _counter_template()
    cache = _RawJacobianCache()

    try:
        current = _ROW._AD._make_state(case, anchor, base.guard_weight)
        counters["initial_state_evaluations"] += 1
    except Exception as error:
        if type(error).__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(anchor.copy(), "budget_before_start", counters)
        raise
    best = current
    trust_radius = float(base.initial_trust_radius)
    damping = float(base.initial_damping)
    objectives: deque[float] = deque(
        [current.objective], maxlen=base.nonmonotone_window
    )
    relation_norms: deque[float] = deque(
        [current.relation_inf], maxlen=base.nonmonotone_window
    )
    consecutive_rejections = 0
    consecutive_linear_failures = 0
    consecutive_poor_ratios = 0
    refresh_requested = False

    def build_raw() -> np.ndarray:
        return _ROW._AD._hybrid_jacobian(
            case,
            program,
            current,
            anchor,
            variable_scale,
            lower_z,
            upper_z,
            base,
            counters,
        )

    try:
        direct_model = cache.get_or_build(current, build_raw, counters, initial=True)
    except Exception as error:
        if type(error).__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(
                best.x.copy(), "budget_during_initial_jacobian", counters
            )
        counters["linear_failures"] += 1
        return CandidateOutcome(best.x.copy(), "initial_jacobian_failure", counters)

    for _ in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if (
            current.semantics_valid
            and current.relation_inf <= base.success_residual_inf
        ):
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1

        if refresh_requested:
            try:
                direct_model = cache.get_or_build(
                    current, build_raw, counters, initial=False
                )
            except Exception as error:
                if type(error).__name__ == "BudgetExceeded":
                    counters["budget_stops"] += 1
                    break
                counters["linear_failures"] += 1
                break
            refresh_requested = False

        try:
            step, rank = _RUIZ._linear_step(
                direct_model,
                current.augmented,
                damping,
                base.rank_rtol,
                "cpqr",
                configuration.ruiz_configuration,
                counters,
            )
        except Exception:
            counters["linear_failures"] += 1
            consecutive_linear_failures += 1
            _request_refresh(counters, "linear_failure")
            refresh_requested = True
            damping = min(base.maximum_damping, damping * 8.0)
            trust_radius = max(base.minimum_trust_radius, trust_radius * 0.35)
            if (
                consecutive_linear_failures
                >= configuration.maximum_consecutive_linear_failures
            ):
                break
            continue
        counters["rank_deficient_iterations"] += int(rank < min(direct_model.shape))
        consecutive_linear_failures = 0
        step_norm = float(np.linalg.norm(step))
        if not math.isfinite(step_norm) or step_norm == 0.0:
            counters["zero_step_failures"] += 1
            consecutive_rejections += 1
            _request_refresh(counters, "zero_step")
            refresh_requested = True
            damping = min(base.maximum_damping, damping * 8.0)
            trust_radius = max(base.minimum_trust_radius, trust_radius * 0.35)
            if consecutive_rejections >= configuration.maximum_consecutive_rejections:
                break
            continue
        if step_norm > trust_radius:
            step *= trust_radius / step_norm
            step_norm = trust_radius
            counters["trust_region_step_clips"] += 1

        current_z = (current.x - anchor) / variable_scale
        unprojected_z = current_z + step
        trial_z = np.minimum(np.maximum(unprojected_z, lower_z), upper_z)
        counters["explicit_source_bound_projections"] += int(
            not np.array_equal(unprojected_z, trial_z)
        )
        delta_z = trial_z - current_z
        if not np.any(delta_z):
            counters["zero_step_failures"] += 1
            consecutive_rejections += 1
            _request_refresh(counters, "zero_step")
            refresh_requested = True
            damping = min(base.maximum_damping, damping * 8.0)
            trust_radius = max(base.minimum_trust_radius, trust_radius * 0.35)
            if consecutive_rejections >= configuration.maximum_consecutive_rejections:
                break
            continue
        trial_x = anchor + variable_scale * trial_z
        try:
            trial = _ROW._AD._make_state(case, trial_x, base.guard_weight)
            counters["trial_state_evaluations"] += 1
        except Exception as error:
            if type(error).__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["rejected_steps"] += 1
            consecutive_rejections += 1
            _request_refresh(counters, "semantic_invalid")
            refresh_requested = True
            damping = min(base.maximum_damping, damping * 8.0)
            trust_radius = max(base.minimum_trust_radius, trust_radius * 0.35)
            continue
        if _ROW._AD._better(trial, best):
            best = trial

        _predicted_objective, predicted_reduction = _raw_prediction(
            current, direct_model, delta_z
        )
        actual_reduction = current.objective - trial.objective
        raw_ratio = (
            actual_reduction / predicted_reduction
            if predicted_reduction > 0.0 and math.isfinite(predicted_reduction)
            else -math.inf
        )
        if not trial.semantics_valid:
            counters["semantic_invalid_trials"] += 1
            _request_refresh(counters, "semantic_invalid")
            refresh_requested = True
        poor_ratio = bool(
            not math.isfinite(raw_ratio) or raw_ratio < configuration.poor_model_ratio
        )
        counters["poor_model_ratio_trials"] += int(poor_ratio)
        counters["nonpositive_model_predictions"] += int(
            not math.isfinite(predicted_reduction) or predicted_reduction <= 0.0
        )
        consecutive_poor_ratios = consecutive_poor_ratios + 1 if poor_ratio else 0
        if consecutive_poor_ratios >= configuration.poor_model_refresh_after:
            _request_refresh(counters, "poor_ratio")
            refresh_requested = True
            consecutive_poor_ratios = 0

        accepted, reason = _ROW._ROW._raw_nonmonotone_accept(
            trial,
            current,
            tuple(objectives),
            tuple(relation_norms),
            predicted_reduction,
            base,
        )
        if accepted:
            old = current
            residual_change = trial.augmented - old.augmented
            updated, defect, usable = _good_broyden_update(
                direct_model,
                delta_z,
                residual_change,
                configuration.denominator_rtol,
            )
            counters["direct_broyden_secant_checks"] += 1
            if usable:
                direct_model = updated
                counters["direct_broyden_updates"] += 1
                secant_error = float(
                    np.linalg.norm(direct_model @ delta_z - residual_change)
                )
                secant_scale = max(1.0, float(np.linalg.norm(residual_change)))
                counters["direct_broyden_secant_check_failures"] += int(
                    not math.isfinite(secant_error)
                    or secant_error > 1.0e-10 * secant_scale
                )
            else:
                counters["direct_broyden_denominator_skips"] += 1
                _request_refresh(counters, "denominator")
                refresh_requested = True
            if defect is not None and defect > configuration.secant_defect_refresh:
                _request_refresh(counters, "secant_defect")
                refresh_requested = True
            current = trial
            counters["accepted_steps"] += 1
            counters["raw_lexicographic_accepts"] += int(reason == "raw_lexicographic")
            counters["raw_nonmonotone_accepts"] += int(reason == "raw_nonmonotone")
            objectives.append(current.objective)
            relation_norms.append(current.relation_inf)
            consecutive_rejections = 0
            if raw_ratio > 0.75:
                trust_radius = min(
                    base.maximum_trust_radius,
                    max(trust_radius, 2.0 * step_norm),
                )
                damping = max(base.minimum_damping, damping * 0.3)
            elif raw_ratio < 0.25:
                trust_radius = max(base.minimum_trust_radius, trust_radius * 0.5)
                damping = min(base.maximum_damping, damping * 3.0)
        else:
            counters["rejected_steps"] += 1
            consecutive_rejections += 1
            trust_radius = max(base.minimum_trust_radius, trust_radius * 0.35)
            damping = min(base.maximum_damping, damping * 8.0)
            if consecutive_rejections >= configuration.maximum_consecutive_rejections:
                break

    if best.semantics_valid and best.relation_inf <= base.success_residual_inf:
        counters["reported_safe_endpoint"] = 1
        status = "safe_root"
    elif time.monotonic() >= deadline_monotonic:
        status = "deadline"
    elif counters["budget_stops"]:
        status = "budget"
    else:
        status = "stalled_or_budget"
    return CandidateOutcome(best.x.copy(), status, counters)


def configuration_manifest(
    configuration: Configuration = REFERENCE,
) -> Mapping[str, object]:
    return {
        "candidate": configuration.name,
        "mechanism": "one hybrid AD/charged-FD augmented J followed by direct good-Broyden updates and event-only full refresh",
        "dependency_sha256": dict(EXPECTED_SHA256),
        "direct_model": "full raw augmented relation+guard Jacobian in caller start-local step coordinates",
        "linear_step": "fresh bounded two-sided Ruiz preconditioning plus CPQR/SVD LM solve; raw model remains acceptance authority",
        "refresh_triggers": [
            "semantic-invalid trial",
            "two consecutive raw model ratios below 0.05",
            "accepted pre-update secant defect above 0.85",
            "linear or zero-step model failure",
            "unusable Broyden denominator",
        ],
        "scheduled_periodic_rank_or_cyclic_column_refresh": False,
        "same_current_cache_key": "same state object plus bitwise-identical x and augmented vectors",
        "precision_runtime_requirement": "process-isolated evaluator seam restores mpmath precision after every call",
        "coordinate_anchor": "caller-provided original-coordinate start",
        "coordinate_scale": "max(1,abs(start)) supplied by paired adapter; numerical preconditioner only",
        "hard_bounds": "source-declared bounds only; missing bounds remain infinite",
        "acceptance_and_endpoint_authority": "untouched raw evaluator state",
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "source_rewrite_or_reparameterization": False,
        "gauge_or_symmetry_reduction": False,
        "added_or_inferred_bounds": False,
        "case_family_truth_target_count_or_outcome_routing": False,
    }


__all__ = [
    "ADProgram",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "REFERENCE",
    "REFERENCE_NAME",
    "compile_program",
    "configuration_manifest",
    "solve_local",
]
