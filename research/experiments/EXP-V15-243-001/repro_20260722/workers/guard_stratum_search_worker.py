#!/usr/bin/env python3
"""Champion search artifact using the existing guard-stratum start order."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_WORKER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
)
ADAPTER_PATH = HERE / "guard_stratum_search_adapter.py"
SCHEMA = "geotarget.exp-v15-243.guard-stratum-champion-search/v1"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


ADAPTER = _load("geotarget_repro_guard_stratum_search_adapter", ADAPTER_PATH)
sys.modules["adapter"] = ADAPTER


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
        finite = bool(residual.is_finite and math.isfinite(residual_norm))
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
        "residual_inf": residual_norm if math.isfinite(residual_norm) else None,
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
BASE = _load("geotarget_repro_guard_stratum_shared_search_worker", BASE_WORKER)
BASE.SCHEMA = SCHEMA


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
