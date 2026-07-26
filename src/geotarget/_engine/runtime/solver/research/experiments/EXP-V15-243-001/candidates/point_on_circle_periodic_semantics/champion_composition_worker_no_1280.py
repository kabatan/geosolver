#!/usr/bin/env python3
"""Candidate adaptive-HP worker: original schedule, repaired POC semantics."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE_WORKER = HERE.parent / "adaptive_hp/champion_composition_worker.py"
MANIFEST = HERE / "champion_closure_manifest.py"
INTEGRATION = HERE / "champion_backend_integration.py"
EXPECTED_BASE_SHA256 = (
    "f9b1a999412e8088a8522b9b2d88b78322ffb0b825eb913083990194998b89c7"
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    if hashlib.sha256(BASE_WORKER.read_bytes()).hexdigest() != EXPECTED_BASE_SHA256:
        raise RuntimeError("adaptive HP composition worker digest changed")
    os.environ["GEOTARGET_ADAPTIVE_HP_ENABLE_FRESH_1280"] = "0"
    base = _load(
        "geotarget_point_on_circle_adaptive_worker_base", BASE_WORKER
    )
    integration = _load(
        "geotarget_point_on_circle_adaptive_worker_integration", INTEGRATION
    )
    base.MANIFEST_PATH = MANIFEST
    original_load = base._load

    def repaired_load(name: str, path: Path):
        module = original_load(name, path)
        if Path(path).resolve() == Path(base.ADAPTER_PATH).resolve():
            integration.install(module)
        return module

    base._load = repaired_load
    base.main()


if __name__ == "__main__":
    main()

