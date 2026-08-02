#!/usr/bin/env python3
"""Frozen v15 local search with target-free endpoint replay.

The local optimizer, proposals, callback limits, and source semantics are
unchanged.  Only the final search-artifact replay is made cheap: it records
residual/guard/hard-feasibility and deliberately defers target evaluation to
the integrated HP worker.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN_SEARCH_ROOT = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hybrid_direct_broyden_tr_lm_v9/corrective_nearroot_strict_restart_v2"
)
BASE_WORKER_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
)
SCHEMA = "geotarget.exp-real61-008.nearroot-restart-trial/v1"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def replay_endpoint(
    evaluator: object, point: Sequence[float], *, precision: int = 80
) -> dict[str, object]:
    """Replay source semantics without evaluating the scalar target."""

    del precision
    values = [float(value) for value in point]
    try:
        residual = evaluator.evaluate_float_residual(values)
        guard_ok, violations = evaluator.evaluate_guard(values)
        hard = evaluator.evaluate_float_hard_feasibility(values)
        residual_norm = float(residual.residual_norm_float)
        finite = bool(
            getattr(residual, "is_finite", False)
            and math.isfinite(residual_norm)
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
        "residual_inf": residual_norm if math.isfinite(residual_norm) else None,
        "guard_ok": bool(guard_ok),
        "guard_violations": list(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "hard_failure_tags": list(hard.failure_tags),
        "diagnostic_target": None,
        "diagnostic_target_is_exact": False,
        "target_evaluation_deferred": True,
    }


ADAPTER = _load(
    "geotarget_exp_v15_243_champion_v0_search_adapter",
    FROZEN_SEARCH_ROOT / "adapter.py",
)
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load(
    "geotarget_exp_v15_243_champion_v0_shared_search_worker",
    BASE_WORKER_PATH,
)
BASE.SCHEMA = SCHEMA


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
