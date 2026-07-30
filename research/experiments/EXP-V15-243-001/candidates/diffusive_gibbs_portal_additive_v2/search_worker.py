#!/usr/bin/env python3
"""Search-only worker for additive DiGS Repair A."""

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
ADAPTER_SHA256 = "856602efd5d1ac96464fa1a83dfad0f8f936b8dcd16ba5a95d0fad67371c22eb"
SCHEMA = "geotarget.exp-v15-243.digs-additive-tail-search-only/v1"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _load(name: str, path: Path, expected: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"hash-bound additive DiGS worker dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


SUPPORT = _load("geotarget_additive_digs_search_support", SUPPORT_PATH, SUPPORT_SHA256)
ADAPTER = _load("geotarget_additive_digs_search_adapter", ADAPTER_PATH, ADAPTER_SHA256)
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
REPLAY = ModuleType("replay")
REPLAY.replay_endpoint = SUPPORT.replay_endpoint
sys.modules["replay"] = REPLAY
BASE = _load(
    "geotarget_additive_digs_base_worker",
    SUPPORT.BASE_WORKER_PATH,
    SUPPORT.BASE_WORKER_SHA256,
)
BASE.SCHEMA = SCHEMA


def _output_argument(argv: Sequence[str]) -> Path:
    try:
        index = argv.index("--output")
        return Path(argv[index + 1])
    except (ValueError, IndexError) as error:
        raise SystemExit("--output is required for additive DiGS telemetry") from error


def main() -> None:
    output = _output_argument(sys.argv[1:])
    ADAPTER.set_partial_output(output.with_name(f"{output.stem}.telemetry.json"))
    BASE.main()


if __name__ == "__main__":
    main()
