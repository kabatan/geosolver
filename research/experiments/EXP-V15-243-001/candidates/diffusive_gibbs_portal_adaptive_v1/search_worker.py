#!/usr/bin/env python3
"""Search-only worker for the thin DiGS/current-adaptive integration."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Sequence


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(os.environ.get(
    "GEOTARGET_EXPERIMENT_RUNTIME", "/home/kabatan/work/solver-experiment-runtime/solver"
)).resolve()
SUPPORT_PATH = HERE.parent / "progressive_local_budget_v1" / "search_worker.py"
SUPPORT_SHA256 = "c60752971a5e7bd95d8e4b73151123457961874f191cb0ead877bb08de812332"
ADAPTER_PATH = HERE / "search_adapter.py"
ADAPTER_SHA256 = "fcf30837f3f89272c73a7e439b84f7ac3d3f284f534cb2fa7f041532f2ee823c"
SCHEMA = "geotarget.exp-v15-243.digs-adaptive-search-only/v1"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _load(name: str, path: Path, expected: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound DiGS worker dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


SUPPORT = _load("geotarget_digs_adaptive_search_support", SUPPORT_PATH, SUPPORT_SHA256)
ADAPTER = _load("geotarget_digs_adaptive_search_adapter", ADAPTER_PATH, ADAPTER_SHA256)
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = SUPPORT.replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load(
    "geotarget_digs_adaptive_base_worker",
    SUPPORT.BASE_WORKER_PATH,
    SUPPORT.BASE_WORKER_SHA256,
)
BASE.SCHEMA = SCHEMA


def _output_argument(argv: Sequence[str]) -> Path:
    try:
        index = argv.index("--output")
        return Path(argv[index + 1])
    except (ValueError, IndexError) as error:
        raise SystemExit("--output is required for DiGS telemetry") from error


def main() -> None:
    output = _output_argument(sys.argv[1:])
    ADAPTER.set_partial_output(output.with_name(f"{output.stem}.telemetry.json"))
    BASE.main()


if __name__ == "__main__":
    main()
