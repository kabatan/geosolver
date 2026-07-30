#!/usr/bin/env python3
"""Search-only v15 worker for the progressive local-budget arms."""

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
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
BASE_WORKER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
)
BASE_WORKER_SHA256 = "17bfea52e7da6c3cca58c5baabcb120017714cbbf2ecfa53428cb1c81d6636dc"
ADAPTER_PATH = HERE / "search_adapter.py"
SCHEMA = "geotarget.exp-v15-243.progressive-local-search-only/v1"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _load(name: str, path: Path, expected_sha256: str | None = None):
    payload = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError(f"hash-bound worker dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def replay_endpoint(evaluator: object, point: Sequence[float], *, precision: int = 80):
    """Unchanged source replay; target evaluation and exactification are deferred."""

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


ADAPTER = _load("geotarget_progressive_local_budget_adapter", ADAPTER_PATH)
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load(
    "geotarget_progressive_local_budget_base_worker",
    BASE_WORKER_PATH,
    BASE_WORKER_SHA256,
)
BASE.SCHEMA = SCHEMA


def _output_argument(argv: Sequence[str]) -> Path:
    try:
        index = argv.index("--output")
        return Path(argv[index + 1])
    except (ValueError, IndexError) as error:
        raise SystemExit("--output is required for progressive telemetry") from error


def main() -> None:
    output = _output_argument(sys.argv[1:])
    ADAPTER.set_partial_output(output.with_name(f"{output.stem}.telemetry.json"))
    BASE.main()


if __name__ == "__main__":
    main()
