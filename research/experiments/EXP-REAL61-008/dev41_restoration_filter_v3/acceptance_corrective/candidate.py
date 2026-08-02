"""Single general corrective for the v3 filter acceptance-resolution defect.

The tested v3 configuration compared normalized residual components with an
absolute resolution of roughly ``1e-5`` because its relative tolerance was
multiplied by ``max(1, |residual|)``.  That is incompatible with its raw
``1e-8`` root goal and can reject every late Newton improvement.  This wrapper
changes only that comparison: relative tolerance scales with the actual two
components, the absolute floor is a small floating-point noise allowance, and
an original-evaluator-safe root is never rejected by the historical filter.
The restoration model, trust region, linear algebra, source semantics, bounds,
prefix, and budgets are unchanged.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from typing import Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "candidate.py"
BASE_SHA256 = "61ade7133531d6a74675896deea2e1ca8cd833238005595b50ac044cf86cf29d"


def _load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
        raise RuntimeError("tested restoration-filter configuration changed")
    name = "geotarget_exp008_restoration_filter_tested_configuration"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, BASE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_base()
MarginProgram = BASE.MarginProgram
compile_program = BASE.compile_program
CandidateOutcome = BASE.CandidateOutcome
Configuration = BASE.Configuration
_TESTED_FILTER_DOMINATED = BASE._filter_dominated

CORRECTIVE = "source_literal_lexicographic_restoration_filter_acceptance_corrective"
MACHINE_FLOOR = 32.0 * np.finfo(float).eps
CONFIGURATION = replace(
    BASE.CONFIGURATION,
    name=CORRECTIVE,
    filter_relative_tolerance=1.0e-8,
    filter_absolute_tolerance=MACHINE_FLOOR,
)
CONFIGURATIONS = {CORRECTIVE: CONFIGURATION}


def _compare_vectors(left: np.ndarray, right: np.ndarray, configuration: Configuration) -> int:
    if left.shape != right.shape:
        raise ValueError("lexicographic vectors have different shapes")
    for candidate, incumbent in zip(left, right, strict=True):
        candidate = float(candidate)
        incumbent = float(incumbent)
        candidate_finite = math.isfinite(candidate)
        incumbent_finite = math.isfinite(incumbent)
        if candidate_finite != incumbent_finite:
            return -1 if candidate_finite else 1
        if not candidate_finite:
            continue
        tolerance = configuration.filter_absolute_tolerance + (
            configuration.filter_relative_tolerance
            * max(abs(candidate), abs(incumbent))
        )
        if candidate < incumbent - tolerance:
            return -1
        if candidate > incumbent + tolerance:
            return 1
    return 0


def _safe_root(state: object, configuration: Configuration) -> bool:
    return bool(
        state.finite_construction
        and state.semantics_valid
        and state.equality_inf <= configuration.equality_goal_inf
    )


def _lex_compare(left: object, right: object, configuration: Configuration) -> int:
    left_safe = _safe_root(left, configuration)
    right_safe = _safe_root(right, configuration)
    if left_safe != right_safe:
        return -1 if left_safe else 1
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


def _filter_dominated(
    state: object,
    entries: Sequence[object],
    configuration: Configuration,
) -> bool:
    if _safe_root(state, configuration):
        return False
    return _TESTED_FILTER_DOMINATED(state, entries, configuration)


def solve_local(*args, **kwargs) -> CandidateOutcome:
    old_compare = BASE._lex_compare
    old_filter = BASE._filter_dominated
    BASE._lex_compare = _lex_compare
    BASE._filter_dominated = _filter_dominated
    try:
        return BASE.solve_local(*args, **kwargs)
    finally:
        BASE._lex_compare = old_compare
        BASE._filter_dominated = old_filter


def kernel_manifest() -> dict[str, object]:
    return {
        **BASE.kernel_manifest(),
        "name": CORRECTIVE,
        "single_corrective": "filter acceptance resolution compatible with root goal",
        "tested_configuration_sha256": BASE_SHA256,
        "relative_comparison": "actual component magnitude, not max(1, magnitude)",
        "safe_original_evaluator_root_filter_bypass": True,
        "restoration_step_or_model_changed": False,
        "source_problem_or_prefix_changed": False,
    }


__all__ = [
    "CORRECTIVE",
    "CONFIGURATION",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "MarginProgram",
    "compile_program",
    "kernel_manifest",
    "solve_local",
]
