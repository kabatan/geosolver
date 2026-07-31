#!/usr/bin/env python3.12
"""Existing source worker with only the guard-billiard adapter injected."""

from __future__ import annotations

import importlib.util
import hashlib
import math
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Sequence


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get("GEOTARGET_EXPERIMENT_RUNTIME", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
BASE_WORKER = RUNTIME_ROOT / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
EXPECTED_BASE_WORKER_SHA256 = "17bfea52e7da6c3cca58c5baabcb120017714cbbf2ecfa53428cb1c81d6636dc"
ADAPTER_PATH = HERE / "search_adapter.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
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
        safe = bool(finite and guard_ok and hard.hard_feasible and residual_norm <= 1.0e-8)
    except Exception as error:
        return {
            "endpoint": values, "safe": False, "residual_inf": None,
            "guard_ok": False, "hard_feasible": False, "diagnostic_target": None,
            "target_evaluation_deferred": True,
            "error": f"{type(error).__name__}: {error}",
        }
    return {
        "endpoint": values, "safe": safe,
        "residual_inf": residual_norm if math.isfinite(residual_norm) else None,
        "guard_ok": bool(guard_ok), "guard_violations": list(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "hard_failure_tags": list(hard.failure_tags),
        "diagnostic_target": None, "diagnostic_target_is_exact": False,
        "target_evaluation_deferred": True,
    }


ADAPTER = _load("geotarget_guard_billiard_current_search_adapter", ADAPTER_PATH)
sys.modules["adapter"] = ADAPTER
if ADAPTER.PRECISION_RUNTIME is not None:
    sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = replay_endpoint
sys.modules["replay"] = REPLAY
if not BASE_WORKER.is_file() or _sha(BASE_WORKER) != EXPECTED_BASE_WORKER_SHA256:
    raise RuntimeError("restoration search worker changed")
BASE = _load("geotarget_guard_billiard_current_base_worker", BASE_WORKER)
BASE.SCHEMA = "geotarget.guard-billiard-current-search-v2/v1"


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
