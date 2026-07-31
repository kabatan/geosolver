#!/usr/bin/env python3
"""Source-only shared worker with the particle-consensus prefix adapter."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SHARED_WORKER = (
    Path(
        os.environ.get(
            "GEOTARGET_PARTICLE_SHARED_SOURCE_WORKER",
            str(
                RUNTIME_ROOT
                / "research/experiments/EXP-REAL61-008/"
                "dev41_restoration_filter_v3/worker.py"
            ),
        )
    ).resolve()
)
EXPECTED_SHARED_WORKER_SHA256 = (
    "17bfea52e7da6c3cca58c5baabcb120017714cbbf2ecfa53428cb1c81d6636dc"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_shared_worker() -> str:
    if (
        SHARED_WORKER.is_symlink()
        or not SHARED_WORKER.is_file()
        or _sha256(SHARED_WORKER) != EXPECTED_SHARED_WORKER_SHA256
    ):
        raise RuntimeError("particle shared source-worker SHA-256 mismatch")
    return EXPECTED_SHARED_WORKER_SHA256


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_verify_shared_worker()
ADAPTER = _load("geotarget_particle_consensus_real_adapter", HERE / "real_adapter.py")
sys.modules["adapter"] = ADAPTER
sys.modules["runtime"] = ADAPTER.PRECISION_RUNTIME
sys.modules["replay"] = ADAPTER.PRECISION_RUNTIME
BASE = _load("geotarget_particle_consensus_shared_source_worker", SHARED_WORKER)
BASE.SCHEMA = "geotarget.exp-particle-consensus-001.real-source-smoke/v1"


def main() -> None:
    _verify_shared_worker()
    BASE.main()


if __name__ == "__main__":
    main()
