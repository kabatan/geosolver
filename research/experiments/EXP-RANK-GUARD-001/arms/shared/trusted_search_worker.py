#!/usr/bin/env python3
"""Frozen v15 search worker with the trust-v2 proposal adapter."""

from __future__ import annotations

import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Sequence


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
BASE_WORKER = RUNTIME_ROOT / (
    "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
)
BASE_WORKER_SHA256 = (
    "17bfea52e7da6c3cca58c5baabcb120017714cbbf2ecfa53428cb1c81d6636dc"
)
ADAPTER_PATH = HERE / "trusted_search_adapter.py"
ADAPTER_SHA256 = (
    "3fc36b6ec622547f20317dee13d1a1af90ecf091046d41d4cfdc68ee3b778fd4"
)
SCHEMA = "geotarget.exp-rank-guard-001.trusted-search-v2/v1"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


if _sha256(BASE_WORKER) != BASE_WORKER_SHA256:
    raise RuntimeError("hash-bound frozen search worker changed")
if _sha256(ADAPTER_PATH) != ADAPTER_SHA256:
    raise RuntimeError("hash-bound trust-v2 search adapter changed")

ADAPTER = _load("geotarget_exp_rank_guard_001_trusted_adapter", ADAPTER_PATH)
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME


def replay_endpoint(
    evaluator: object, point: Sequence[float], *, precision: int = 80
) -> dict[str, object]:
    del precision
    values = [float(value) for value in point]
    try:
        residual = evaluator.evaluate_float_residual(values)
        guard_ok, violations = evaluator.evaluate_guard(values)
        hard = evaluator.evaluate_float_hard_feasibility(values)
        residual_norm = float(residual.residual_norm_float)
        finite = bool(
            getattr(residual, "is_finite", False) and math.isfinite(residual_norm)
        )
        safe = bool(
            finite
            and guard_ok
            and hard.hard_feasible
            and residual_norm <= 1.0e-8
        )
    except Exception as error:
        return {
            "endpoint": values,
            "safe": False,
            "residual_inf": None,
            "guard_ok": False,
            "hard_feasible": False,
            "diagnostic_target": None,
            "target_evaluation_deferred": True,
            "error": f"{type(error).__name__}: {error}",
        }
    return {
        "endpoint": values,
        "safe": safe,
        "residual_inf": residual_norm if finite else None,
        "guard_ok": bool(guard_ok),
        "guard_violations": list(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "hard_failure_tags": list(hard.failure_tags),
        "diagnostic_target": None,
        "diagnostic_target_is_exact": False,
        "target_evaluation_deferred": True,
    }


REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load("geotarget_exp_rank_guard_001_trusted_search_base", BASE_WORKER)
BASE.SCHEMA = SCHEMA


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
