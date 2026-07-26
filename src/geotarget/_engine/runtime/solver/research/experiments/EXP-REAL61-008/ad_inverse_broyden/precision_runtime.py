"""Precision-isolated view of the frozen unchanged-source evaluator runtime.

The legacy geometry evaluator uses the process-global ``mpmath.mp.dps``
context in a few guard/hard-feasibility paths.  This seam restores the caller's
precision after every build, charged evaluation, progressive evaluation, and
endpoint replay.  It changes neither source values nor evaluator outputs.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Callable

from mpmath import mp


HERE = Path(__file__).resolve().parent
SOURCE_ONLY = HERE.parent / "source_only"
SOURCE_RUNTIME_PATH = SOURCE_ONLY / "runtime.py"
SOURCE_REPLAY_PATH = SOURCE_ONLY / "replay.py"
EXPECTED_SHA256 = {
    "source_runtime": "5594c7f673171999ac4455f00223861673ea42bc02be1bb3e115f28951dfdaf1",
    "source_replay": "18ec12d900aacb7756e27fbee85fb3edf48dd348e68407b163b424fc18df2e13",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path, expected: str):
    if _sha256(path) != expected:
        raise RuntimeError(f"precision-isolated source seam changed: {name}")
    module_name = f"geotarget_exp008_inverse_broyden_precision_{name}"
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


_SOURCE = _load("source_runtime", SOURCE_RUNTIME_PATH, EXPECTED_SHA256["source_runtime"])
_REPLAY = _load("source_replay", SOURCE_REPLAY_PATH, EXPECTED_SHA256["source_replay"])

BudgetExceeded = _SOURCE.BudgetExceeded
EvaluationBudget = _SOURCE.EvaluationBudget
Observation = _SOURCE.Observation
SourceCase = _SOURCE.SourceCase
source_bounds = _SOURCE.source_bounds


def precision_isolated(function: Callable, *args, **kwargs):
    """Call ``function`` while preventing a global ``mp.dps`` leak."""

    original_dps = int(mp.dps)
    try:
        return function(*args, **kwargs)
    finally:
        mp.dps = original_dps


def build_source_case(document: dict[str, object], *, callback_cap: int, deadline: float):
    """Build the original evaluator and isolate every charged public call."""

    case, budget, evaluator = precision_isolated(
        _SOURCE.build_source_case,
        document,
        callback_cap=callback_cap,
        deadline=deadline,
    )

    def evaluate(point):
        return precision_isolated(case.evaluate, point)

    def progressive(point):
        return precision_isolated(case.progressive_residual, point)

    isolated = replace(
        case,
        evaluate=evaluate,
        progressive_residual=progressive,
    )
    return isolated, budget, evaluator


def replay_endpoint(evaluator: object, point, *, precision: int = 80):
    """Replay through the untouched evaluator without leaking precision."""

    return precision_isolated(
        _REPLAY.replay_endpoint,
        evaluator,
        point,
        precision=precision,
    )


def precision_manifest() -> dict[str, object]:
    return {
        "mechanism": "restore process-global mpmath mp.dps after each evaluator call",
        "source_runtime_sha256": EXPECTED_SHA256["source_runtime"],
        "source_replay_sha256": EXPECTED_SHA256["source_replay"],
        "evaluator_output_or_source_semantics_changed": False,
    }


__all__ = [
    "BudgetExceeded",
    "EvaluationBudget",
    "Observation",
    "SourceCase",
    "build_source_case",
    "precision_isolated",
    "precision_manifest",
    "replay_endpoint",
    "source_bounds",
]
