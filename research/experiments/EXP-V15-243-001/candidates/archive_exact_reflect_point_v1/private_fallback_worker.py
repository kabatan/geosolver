#!/usr/bin/env python3
"""Frozen exact-coordinate fallback with a private Reflect(point, center) shim."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
PRIVATE_CANDIDATE = HERE / "private_candidate.py"
ORIGINAL_FALLBACK = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/fallback_worker.py"
)
EXPECTED_PRIVATE_CANDIDATE_SHA256 = "8c9f5b656db49344b1514b4cfcc293479d016218c05d307a6b5c108adf706fc4"
EXPECTED_ORIGINAL_FALLBACK_SHA256 = "44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900"


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


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(PRIVATE_CANDIDATE): _sha256(PRIVATE_CANDIDATE),
        str(ORIGINAL_FALLBACK): _sha256(ORIGINAL_FALLBACK),
    }
    expected = {
        str(PRIVATE_CANDIDATE): EXPECTED_PRIVATE_CANDIDATE_SHA256,
        str(ORIGINAL_FALLBACK): EXPECTED_ORIGINAL_FALLBACK_SHA256,
    }
    if observed != expected:
        raise RuntimeError("private reflect fallback dependency changed")
    return observed


verify_dependencies()
PRIVATE = _load("candidate", PRIVATE_CANDIDATE)
ORIGINAL = _load("geotarget_exact_reflect_original_fallback", ORIGINAL_FALLBACK)


def main() -> None:
    verify_dependencies()
    PRIVATE.verify_dependencies()
    ORIGINAL.main()


if __name__ == "__main__":
    main()
