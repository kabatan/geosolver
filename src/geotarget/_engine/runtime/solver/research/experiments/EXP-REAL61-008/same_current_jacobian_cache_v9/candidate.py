"""Exact same-current raw-Jacobian reuse for the frozen row-LM kernel.

The frozen kernel can retry a rejected LM/TR step from the exact same
``_State`` while changing only damping, trust radius, or row weights.  Its raw
hybrid Jacobian depends on none of those quantities, so reacquiring charged
finite-difference columns at that unchanged state is redundant.

This disposable candidate caches only that raw Jacobian.  A different state
object -- including every accepted ``current = trial`` move -- invalidates the
cache even if its arrays happen to contain the same bytes.  Every trial point
is still evaluated by the original evaluator and all frozen step, scaling,
acceptance, termination, and endpoint rules remain unchanged.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import threading
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
ROW_PATH = HERE.parent / "ad_row_equilibration_rebind/candidate.py"
ROW_SHA256 = "59a021f7a5628dcf03010e7cc2035ce2582e61f092235164f635e159b5f48e9a"


def _load_row():
    if hashlib.sha256(ROW_PATH.read_bytes()).hexdigest() != ROW_SHA256:
        raise RuntimeError("frozen row-LM dependency changed")
    name = "geotarget_exp008_same_current_cache_frozen_row"
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
Configuration = _ROW.Configuration
REFERENCE = _ROW.REFERENCE
REFERENCE_NAME = "precision_isolated_roweq_same_current_raw_jacobian_cache"
compile_program = _ROW.compile_program


_PATCH_LOCK = threading.RLock()


def _bitwise_equal(left: np.ndarray, right: np.ndarray) -> bool:
    a = np.asarray(left)
    b = np.asarray(right)
    return bool(
        a.shape == b.shape
        and a.dtype.str == b.dtype.str
        and a.tobytes(order="C") == b.tobytes(order="C")
    )


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
    """Run frozen row-LM with exact reuse after an unchanged-state retry."""

    cached_state: object | None = None
    cached_x: np.ndarray | None = None
    cached_augmented: np.ndarray | None = None
    cached_raw_jacobian: np.ndarray | None = None
    cached_fd_calls = 0
    diagnostics = {
        "same_current_raw_jacobian_cache_hits": 0,
        "same_current_raw_jacobian_cache_misses": 0,
        "same_current_raw_jacobian_invalidations": 0,
        "same_current_fd_direction_evaluations_avoided": 0,
        "same_current_cache_state_mutations": 0,
    }

    original_hybrid = _ROW._AD._hybrid_jacobian

    def cached_hybrid(
        inner_case,
        inner_program,
        current,
        origin,
        scales,
        lower_z,
        upper_z,
        inner_configuration,
        counters,
    ):
        nonlocal cached_state
        nonlocal cached_x
        nonlocal cached_augmented
        nonlocal cached_raw_jacobian
        nonlocal cached_fd_calls

        same_object = current is cached_state
        if same_object:
            key_equal = bool(
                cached_x is not None
                and cached_augmented is not None
                and _bitwise_equal(current.x, cached_x)
                and _bitwise_equal(current.augmented, cached_augmented)
            )
            if not key_equal:
                diagnostics["same_current_cache_state_mutations"] += 1
                raise RuntimeError("cached frozen row state mutated in place")
            if cached_raw_jacobian is None:
                raise RuntimeError("same-current cache lost its raw Jacobian")
            diagnostics["same_current_raw_jacobian_cache_hits"] += 1
            diagnostics["same_current_fd_direction_evaluations_avoided"] += int(
                cached_fd_calls
            )
            return cached_raw_jacobian.copy()

        if cached_state is not None:
            # The frozen loop assigns a new _State only after accepting a
            # trial.  Object identity therefore makes accepted moves invalidate
            # even if two state arrays coincidentally have identical bytes.
            diagnostics["same_current_raw_jacobian_invalidations"] += 1

        before = int(counters.get("fd_direction_evaluations", 0))
        raw = original_hybrid(
            inner_case,
            inner_program,
            current,
            origin,
            scales,
            lower_z,
            upper_z,
            inner_configuration,
            counters,
        )
        after = int(counters.get("fd_direction_evaluations", 0))
        cached_state = current
        cached_x = np.asarray(current.x).copy()
        cached_augmented = np.asarray(current.augmented).copy()
        cached_raw_jacobian = np.asarray(raw, dtype=float).copy()
        cached_fd_calls = max(0, after - before)
        diagnostics["same_current_raw_jacobian_cache_misses"] += 1
        return raw

    with _PATCH_LOCK:
        if _ROW._AD._hybrid_jacobian is not original_hybrid:
            raise RuntimeError("frozen hybrid-Jacobian seam is already rebound")
        _ROW._AD._hybrid_jacobian = cached_hybrid
        try:
            outcome = _ROW.solve_local(
                case,
                program,
                configuration,
                start,
                per_start_scale=per_start_scale,
                source_lower=source_lower,
                source_upper=source_upper,
                max_callbacks=max_callbacks,
                deadline_monotonic=deadline_monotonic,
            )
        finally:
            _ROW._AD._hybrid_jacobian = original_hybrid

    merged = dict(outcome.counters)
    merged.update(diagnostics)
    return replace(outcome, counters=merged)


def configuration_manifest() -> Mapping[str, object]:
    return {
        "candidate": REFERENCE_NAME,
        "mechanism": "bitwise exact raw-Jacobian memoization only while the frozen current state object is unchanged after rejection",
        "frozen_row_kernel_sha256": ROW_SHA256,
        "cache_key": "same _State object plus bitwise-identical x and augmented vectors",
        "accepted_move_invalidation": "mandatory on every new _State object",
        "reused_quantity": "unweighted raw hybrid Jacobian only",
        "row_weights_recomputed_each_retry": True,
        "trial_evaluator_calls_preserved": True,
        "step_acceptance_termination_and_endpoint_rules": "frozen row-LM unchanged",
        "requires_deterministic_precision_isolated_evaluator": True,
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "source_rewrite_or_reparameterization": False,
        "gauge_or_symmetry_reduction": False,
        "added_or_inferred_bounds": False,
        "case_family_truth_target_count_or_outcome_routing": False,
    }


__all__ = [
    "ADProgram",
    "CandidateOutcome",
    "Configuration",
    "REFERENCE",
    "REFERENCE_NAME",
    "ROW_SHA256",
    "compile_program",
    "configuration_manifest",
    "solve_local",
]
