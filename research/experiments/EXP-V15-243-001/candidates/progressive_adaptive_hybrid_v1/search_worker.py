#!/usr/bin/env python3
"""Search-only frozen-v15 worker for the adaptive hybrid arm."""

from __future__ import annotations

import hashlib
import importlib.util
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
BASE_SEARCH_WORKER = (
    HERE.parent / "progressive_local_budget_v1" / "search_worker.py"
)
BASE_SEARCH_WORKER_SHA256 = (
    "c60752971a5e7bd95d8e4b73151123457961874f191cb0ead877bb08de812332"
)
ADAPTER_PATH = HERE / "search_adapter.py"
SCHEMA = "geotarget.exp-v15-243.progressive-adaptive-hybrid-search-only/v1"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _load(name: str, path: Path, expected_sha256: str | None = None):
    payload = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError(f"hash-bound hybrid worker dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


SUPPORT = _load(
    "geotarget_progressive_adaptive_hybrid_search_support",
    BASE_SEARCH_WORKER,
    BASE_SEARCH_WORKER_SHA256,
)
ADAPTER = _load("geotarget_progressive_adaptive_hybrid_adapter", ADAPTER_PATH)
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = SUPPORT.replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load(
    "geotarget_progressive_adaptive_hybrid_base_worker",
    SUPPORT.BASE_WORKER_PATH,
    SUPPORT.BASE_WORKER_SHA256,
)
BASE.SCHEMA = SCHEMA


def _output_argument(argv: Sequence[str]) -> Path:
    try:
        index = argv.index("--output")
        return Path(argv[index + 1])
    except (ValueError, IndexError) as error:
        raise SystemExit("--output is required for adaptive hybrid telemetry") from error


def main() -> None:
    output = _output_argument(sys.argv[1:])
    ADAPTER.set_partial_output(output.with_name(f"{output.stem}.telemetry.json"))
    BASE.main()


if __name__ == "__main__":
    main()
