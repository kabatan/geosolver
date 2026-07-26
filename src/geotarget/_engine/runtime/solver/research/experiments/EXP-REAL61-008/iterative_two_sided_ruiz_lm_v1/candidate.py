"""Disposable iterative two-sided Ruiz preconditioner for the row-LM kernel.

The frozen row-equilibrated solver still owns Jacobian construction, trust
radius, damping updates, raw acceptance, bounds, and endpoint selection.  This
candidate replaces only one process-local linear-step call.  It equilibrates
the already row-weighted full augmented Jacobian, solves in an internal column
scale, maps the step back to the existing start-local coordinates, and then
lets the frozen solver evaluate the trial in untouched original coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import threading
from types import ModuleType
from typing import Mapping, MutableMapping, Sequence

import numpy as np
from scipy import linalg


HERE = Path(__file__).resolve().parent
ROW_PATH = HERE.parent / "ad_row_equilibration_rebind/candidate.py"
ROW_SHA256 = "59a021f7a5628dcf03010e7cc2035ce2582e61f092235164f635e159b5f48e9a"


def _load_row() -> ModuleType:
    if hashlib.sha256(ROW_PATH.read_bytes()).hexdigest() != ROW_SHA256:
        raise RuntimeError("frozen row-equilibrated kernel changed")
    name = "geotarget_exp008_iterative_ruiz_frozen_row"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, ROW_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(ROW_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


_ROW = _load_row()
ADProgram = _ROW.ADProgram
CandidateOutcome = _ROW.CandidateOutcome
compile_program = _ROW.compile_program

REFERENCE_NAME = "iterative_two_sided_ruiz_lm_cpqr_svd"


@dataclass(frozen=True)
class Configuration:
    name: str = REFERENCE_NAME
    maximum_ruiz_iterations: int = 4
    minimum_update_factor: float = 1.0 / 16.0
    maximum_update_factor: float = 16.0
    minimum_cumulative_factor: float = 1.0e-6
    maximum_cumulative_factor: float = 1.0e6
    convergence_norm_ratio: float = 1.25
    cpqr_condition_limit: float = 1.0e8
    base_configuration: object = _ROW.REFERENCE


REFERENCE = Configuration()
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}


@dataclass(frozen=True)
class RuizSystem:
    matrix: np.ndarray
    residual: np.ndarray
    row_scale: np.ndarray
    column_scale: np.ndarray
    iterations: int
    converged: bool
    update_cap_hits: int
    cumulative_cap_hits: int


def _axis_update(
    norms: np.ndarray,
    cumulative: np.ndarray,
    configuration: Configuration,
) -> tuple[np.ndarray, int, int]:
    factors = np.ones_like(norms, dtype=float)
    active = np.isfinite(norms) & (norms > np.finfo(float).tiny)
    factors[active] = 1.0 / np.sqrt(norms[active])
    update_clipped = np.clip(
        factors,
        configuration.minimum_update_factor,
        configuration.maximum_update_factor,
    )
    update_hits = int(np.count_nonzero(update_clipped != factors))
    proposed = cumulative * update_clipped
    cumulative_clipped = np.clip(
        proposed,
        configuration.minimum_cumulative_factor,
        configuration.maximum_cumulative_factor,
    )
    cumulative_hits = int(np.count_nonzero(cumulative_clipped != proposed))
    actual = cumulative_clipped / cumulative
    actual[~active] = 1.0
    return actual, update_hits, cumulative_hits


def _axis_norms(matrix: np.ndarray, axis: int) -> np.ndarray:
    length = matrix.shape[0] if axis == 1 else matrix.shape[1]
    if matrix.size == 0:
        return np.zeros(length, dtype=float)
    return np.max(np.abs(matrix), axis=axis)


def equilibrate(
    jacobian: Sequence[Sequence[float]],
    residual: Sequence[float],
    configuration: Configuration = REFERENCE,
) -> RuizSystem:
    """Bounded fresh Ruiz scaling of one full augmented linearization."""

    matrix = np.asarray(jacobian, dtype=float).copy()
    right = np.asarray(residual, dtype=float).copy()
    if matrix.ndim != 2 or right.shape != (matrix.shape[0],):
        raise ValueError("Ruiz matrix/residual shapes disagree")
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(right)):
        raise ValueError("Ruiz input is non-finite")
    if configuration.maximum_ruiz_iterations < 1:
        raise ValueError("at least one Ruiz iteration is required")
    if not (
        0.0 < configuration.minimum_update_factor <= 1.0
        <= configuration.maximum_update_factor
        and 0.0 < configuration.minimum_cumulative_factor <= 1.0
        <= configuration.maximum_cumulative_factor
        and configuration.convergence_norm_ratio > 1.0
    ):
        raise ValueError("Ruiz factor caps are malformed")

    row_scale = np.ones(matrix.shape[0], dtype=float)
    column_scale = np.ones(matrix.shape[1], dtype=float)
    update_hits = 0
    cumulative_hits = 0
    converged = False
    iterations = 0
    log_tolerance = math.log(configuration.convergence_norm_ratio)
    for iterations in range(1, configuration.maximum_ruiz_iterations + 1):
        row_update, hits, total_hits = _axis_update(
            _axis_norms(matrix, axis=1), row_scale, configuration
        )
        update_hits += hits
        cumulative_hits += total_hits
        matrix *= row_update[:, None]
        right *= row_update
        row_scale *= row_update

        column_update, hits, total_hits = _axis_update(
            _axis_norms(matrix, axis=0), column_scale, configuration
        )
        update_hits += hits
        cumulative_hits += total_hits
        matrix *= column_update[None, :]
        column_scale *= column_update

        row_norms = _axis_norms(matrix, axis=1)
        column_norms = _axis_norms(matrix, axis=0)
        active = np.concatenate(
            (row_norms[row_norms > 0.0], column_norms[column_norms > 0.0])
        )
        if active.size == 0 or float(np.max(np.abs(np.log(active)))) <= log_tolerance:
            converged = True
            break
    return RuizSystem(
        matrix=matrix,
        residual=right,
        row_scale=row_scale,
        column_scale=column_scale,
        iterations=iterations,
        converged=converged,
        update_cap_hits=update_hits,
        cumulative_cap_hits=cumulative_hits,
    )


def _rank_and_condition(matrix: np.ndarray, rank_rtol: float) -> tuple[int, float]:
    singular = linalg.svdvals(matrix, check_finite=False)
    if singular.size == 0:
        return 0, math.inf
    threshold = rank_rtol * max(1.0, float(singular[0]))
    rank = int(np.count_nonzero(singular > threshold))
    condition = (
        float(singular[0] / singular[-1])
        if singular[-1] > 0.0 and math.isfinite(float(singular[0]))
        else math.inf
    )
    return rank, condition


def _cpqr_solve(matrix: np.ndarray, rhs: np.ndarray, rank_rtol: float) -> np.ndarray:
    q, triangular, pivots = linalg.qr(
        matrix, mode="economic", pivoting=True, check_finite=False
    )
    columns = matrix.shape[1]
    diagonal = np.abs(np.diag(triangular))
    threshold = rank_rtol * max(
        1.0, float(diagonal[0]) if diagonal.size else 0.0
    )
    if diagonal.size < columns or int(np.count_nonzero(diagonal > threshold)) < columns:
        raise linalg.LinAlgError("augmented CPQR is numerically rank deficient")
    pivoted = linalg.solve_triangular(
        triangular[:columns, :columns],
        (q.T @ rhs)[:columns],
        lower=False,
        check_finite=False,
    )
    solution = np.empty(columns, dtype=float)
    solution[np.asarray(pivots, dtype=int)] = pivoted
    if not np.all(np.isfinite(solution)):
        raise linalg.LinAlgError("augmented CPQR returned a non-finite step")
    return solution


def _filtered_svd_solve(
    matrix: np.ndarray, rhs: np.ndarray, rank_rtol: float
) -> np.ndarray:
    left, singular, right = linalg.svd(
        matrix, full_matrices=False, check_finite=False
    )
    if singular.size == 0:
        return np.zeros(matrix.shape[1], dtype=float)
    threshold = rank_rtol * max(1.0, float(singular[0]))
    inverse = np.zeros_like(singular)
    active = singular > threshold
    inverse[active] = 1.0 / singular[active]
    solution = right.T @ (inverse * (left.T @ rhs))
    if not np.all(np.isfinite(solution)):
        raise linalg.LinAlgError("filtered SVD returned a non-finite step")
    return np.asarray(solution, dtype=float)


def _add_condition_counters(
    counters: MutableMapping[str, int], before: float, after: float
) -> None:
    if not (math.isfinite(before) and math.isfinite(after) and after > 0.0):
        return
    ratio = before / after
    counters["ruiz_condition_improved_steps"] += int(ratio > 1.0)
    counters["ruiz_condition_reduction_ge_10x"] += int(ratio >= 10.0)
    counters["ruiz_condition_reduction_ge_100x"] += int(ratio >= 100.0)
    if ratio > 1.0:
        decades = max(0, int(math.floor(math.log10(ratio))))
        counters["ruiz_max_condition_reduction_decades"] = max(
            counters["ruiz_max_condition_reduction_decades"], decades
        )


def _linear_step(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    rank_rtol: float,
    solver: str,
    configuration: Configuration,
    counters: MutableMapping[str, int],
) -> tuple[np.ndarray, int]:
    rows, columns = jacobian.shape
    counters["ruiz_linearizations"] += 1
    if columns == 0:
        return np.empty(0), 0
    if solver != "cpqr":
        raise ValueError("Ruiz wrapper expects the frozen CPQR base configuration")
    if not np.all(np.isfinite(jacobian)) or not np.all(np.isfinite(residual)):
        counters["ruiz_nonfinite_linearizations"] += 1
        return np.zeros(columns), 0

    before_rank, before_condition = _rank_and_condition(jacobian, rank_rtol)
    system = equilibrate(jacobian, residual, configuration)
    rank, condition = _rank_and_condition(system.matrix, rank_rtol)
    counters["ruiz_iterations"] += system.iterations
    counters["ruiz_converged_linearizations"] += int(system.converged)
    counters["ruiz_nontrivial_row_scalings"] += int(
        np.any(np.abs(np.log(system.row_scale)) > 1.0e-12)
    )
    counters["ruiz_nontrivial_column_scalings"] += int(
        np.any(np.abs(np.log(system.column_scale)) > 1.0e-12)
    )
    counters["ruiz_update_cap_hits"] += system.update_cap_hits
    counters["ruiz_cumulative_cap_hits"] += system.cumulative_cap_hits
    _add_condition_counters(counters, before_condition, condition)

    # p = Dc*q.  sqrt(lambda)*Dc keeps the regularizer equal to
    # lambda*||p||^2, rather than silently changing it to lambda*||q||^2.
    regularizer = math.sqrt(max(float(damping), 1.0e-16)) * np.diag(
        system.column_scale
    )
    augmented = np.vstack((system.matrix, regularizer))
    rhs = -np.concatenate((system.residual, np.zeros(columns, dtype=float)))
    rank_trigger = rank < columns
    condition_trigger = not math.isfinite(condition) or (
        condition > configuration.cpqr_condition_limit
    )
    use_svd = rank_trigger or condition_trigger
    counters["ruiz_svd_rank_trigger_steps"] += int(rank_trigger)
    counters["ruiz_svd_condition_trigger_steps"] += int(
        condition_trigger and not rank_trigger
    )
    if use_svd:
        internal = _filtered_svd_solve(augmented, rhs, rank_rtol)
        counters["ruiz_svd_steps"] += 1
    else:
        try:
            internal = _cpqr_solve(augmented, rhs, rank_rtol)
            counters["ruiz_cpqr_steps"] += 1
        except Exception:
            counters["ruiz_cpqr_failure_fallbacks"] += 1
            internal = _filtered_svd_solve(augmented, rhs, rank_rtol)
            counters["ruiz_svd_steps"] += 1
    step = system.column_scale * internal
    if not np.all(np.isfinite(step)):
        raise linalg.LinAlgError("mapped Ruiz step is non-finite")
    # Rank is always the scaled *undamped Jacobian* rank, never the rank of
    # the damping-augmented solve matrix.
    return np.asarray(step, dtype=float), rank


_PATCH_LOCK = threading.RLock()


def _counter_template() -> dict[str, int]:
    return {
        "ruiz_linearizations": 0,
        "ruiz_iterations": 0,
        "ruiz_converged_linearizations": 0,
        "ruiz_nontrivial_row_scalings": 0,
        "ruiz_nontrivial_column_scalings": 0,
        "ruiz_update_cap_hits": 0,
        "ruiz_cumulative_cap_hits": 0,
        "ruiz_condition_improved_steps": 0,
        "ruiz_condition_reduction_ge_10x": 0,
        "ruiz_condition_reduction_ge_100x": 0,
        "ruiz_max_condition_reduction_decades": 0,
        "ruiz_cpqr_steps": 0,
        "ruiz_svd_steps": 0,
        "ruiz_svd_rank_trigger_steps": 0,
        "ruiz_svd_condition_trigger_steps": 0,
        "ruiz_cpqr_failure_fallbacks": 0,
        "ruiz_nonfinite_linearizations": 0,
    }


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
    """Run one frozen row-LM solve with only its linear step preconditioned."""

    if not isinstance(configuration, Configuration):
        raise TypeError("Ruiz configuration is required")
    counters = _counter_template()

    def replacement(jacobian, residual, damping, rank_rtol, solver):
        return _linear_step(
            jacobian,
            residual,
            damping,
            rank_rtol,
            solver,
            configuration,
            counters,
        )

    with _PATCH_LOCK:
        original = _ROW._AD._rank_aware_step
        _ROW._AD._rank_aware_step = replacement
        try:
            outcome = _ROW.solve_local(
                case,
                program,
                configuration.base_configuration,
                start,
                per_start_scale=per_start_scale,
                source_lower=source_lower,
                source_upper=source_upper,
                max_callbacks=max_callbacks,
                deadline_monotonic=deadline_monotonic,
            )
        finally:
            _ROW._AD._rank_aware_step = original
    merged = dict(outcome.counters)
    merged.update(counters)
    return replace(outcome, counters=merged)


def configuration_manifest(
    configuration: Configuration = REFERENCE,
) -> Mapping[str, object]:
    return {
        "candidate": configuration.name,
        "mechanism": "fresh bounded iterative two-sided Ruiz preconditioning of frozen row-LM linear steps",
        "frozen_row_kernel_sha256": ROW_SHA256,
        "ruiz_rows": "full augmented relation+guard+hard model after frozen dynamic row weights",
        "ruiz_update_frequency": "fresh at every LM linearization; no scale carry-over",
        "maximum_ruiz_iterations": configuration.maximum_ruiz_iterations,
        "per_iteration_factor_bounds": [
            configuration.minimum_update_factor,
            configuration.maximum_update_factor,
        ],
        "cumulative_factor_bounds": [
            configuration.minimum_cumulative_factor,
            configuration.maximum_cumulative_factor,
        ],
        "linear_solver_policy": "CPQR when scaled undamped J is full-column-rank and cond<=1e8; filtered SVD otherwise or on CPQR failure",
        "column_mapping": "p=Dc*q; return p in caller start-local coordinates",
        "lm_regularizer": "sqrt(lambda)*Dc in q coordinates, exactly lambda*||p||^2",
        "trial_coordinates": "frozen row kernel maps p to original variables",
        "acceptance_authority": "untouched raw evaluator through frozen row kernel",
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
    "ROW_SHA256",
    "RuizSystem",
    "compile_program",
    "configuration_manifest",
    "equilibrate",
    "solve_local",
]
