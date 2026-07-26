"""Hash-bound adapter for the already tested source-only evaluator runtime."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Sequence


HERE = Path(__file__).resolve().parent
AUTHORITY_PATH = (
    HERE.parents[1]
    / "EXP-REAL61-007/provisional_numerical_architecture/source_only_runtime.py"
)
AUTHORITY_SHA256 = "a3596c7273122ee49f537a43c1c05b57318a86b56bfdf6f19eb0bd20c6f59796"


def _load():
    if hashlib.sha256(AUTHORITY_PATH.read_bytes()).hexdigest() != AUTHORITY_SHA256:
        raise RuntimeError("source-only runtime authority changed")
    name = "geotarget_exp008_source_only_runtime_authority"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, AUTHORITY_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(AUTHORITY_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


AUTHORITY = _load()
BudgetExceeded = AUTHORITY.BudgetExceeded
EvaluationBudget = AUTHORITY.EvaluationBudget
Observation = AUTHORITY.OpaqueEvaluation
SourceCase = AUTHORITY.SourceOnlyCase
build_source_case = AUTHORITY.build_opaque_case
source_bounds = AUTHORITY.source_bounds


def with_affine_metadata(
    case: SourceCase, *, origin: Sequence[float], scales: Sequence[float]
) -> SourceCase:
    from dataclasses import replace
    import numpy as np

    return replace(
        case,
        origin=np.asarray(origin, dtype=float).copy(),
        scales=np.asarray(scales, dtype=float).copy(),
    )


__all__ = [
    "AUTHORITY_PATH",
    "AUTHORITY_SHA256",
    "BudgetExceeded",
    "EvaluationBudget",
    "Observation",
    "SourceCase",
    "build_source_case",
    "source_bounds",
    "with_affine_metadata",
]
