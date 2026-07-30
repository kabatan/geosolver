#!/usr/bin/env python3
"""Frozen target-free search worker with only the local adapter redirected."""

from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Sequence


HERE = Path(__file__).resolve().parent
FROZEN_ROOT = Path(os.environ.get(
    "GEOTARGET_FROZEN_REPOSITORY", "/home/kabatan/work/solver-experiment-runtime/solver"
)).resolve()
BASE_WORKER_PATH = (
    FROZEN_ROOT / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
)
SCHEMA = "geotarget.spectral-cosh-quarter-lane-search/v1"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def replay_endpoint(evaluator: object, point: Sequence[float], *, precision: int = 80):
    del precision
    values = [float(value) for value in point]
    try:
        residual = evaluator.evaluate_float_residual(values)
        guard_ok, violations = evaluator.evaluate_guard(values)
        hard = evaluator.evaluate_float_hard_feasibility(values)
        residual_norm = float(residual.residual_norm_float)
        finite = bool(getattr(residual, "is_finite", False) and math.isfinite(residual_norm))
        safe = bool(finite and guard_ok and hard.hard_feasible and residual_norm <= 1e-8)
    except Exception as error:
        return {
            "endpoint": values, "safe": False, "residual_inf": None,
            "guard_ok": False, "hard_feasible": False, "diagnostic_target": None,
            "target_evaluation_deferred": True, "error": f"{type(error).__name__}: {error}",
        }
    return {
        "endpoint": values, "safe": safe,
        "residual_inf": residual_norm if math.isfinite(residual_norm) else None,
        "guard_ok": bool(guard_ok), "guard_violations": list(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "hard_failure_tags": list(hard.failure_tags), "diagnostic_target": None,
        "diagnostic_target_is_exact": False, "target_evaluation_deferred": True,
    }


ADAPTER = _load("geotarget_spectral_cosh_adapter", HERE / "real_adapter.py")
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load("geotarget_spectral_cosh_shared_search_worker", BASE_WORKER_PATH)
BASE.SCHEMA = SCHEMA


if __name__ == "__main__":
    BASE.main()

