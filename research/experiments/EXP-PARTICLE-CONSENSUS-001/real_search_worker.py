#!/usr/bin/env python3
"""Source-only shared worker with the particle-consensus prefix adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SHARED_WORKER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-008/dev41_restoration_filter_v3/worker.py"
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ADAPTER = _load("geotarget_particle_consensus_real_adapter", HERE / "real_adapter.py")
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
sys.modules["replay"] = ADAPTER.PRECISION_RUNTIME
BASE = _load("geotarget_particle_consensus_shared_source_worker", SHARED_WORKER)
BASE.SCHEMA = "geotarget.exp-particle-consensus-001.real-source-smoke/v1"


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()

