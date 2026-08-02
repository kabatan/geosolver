#!/usr/bin/env python3
"""Ablation worker: identical adaptive portfolio with fresh 1280 disabled."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE / "champion_composition_worker.py"
ENVIRONMENT_KEY = "GEOTARGET_ADAPTIVE_HP_ENABLE_FRESH_1280"
EXPECTED_BASE_SHA256 = (
    "f9b1a999412e8088a8522b9b2d88b78322ffb0b825eb913083990194998b89c7"
)


def _load_base():
    observed = hashlib.sha256(BASE.read_bytes()).hexdigest()
    if observed != EXPECTED_BASE_SHA256:
        raise RuntimeError("no-1280 ablation base worker digest mismatch")
    name = "geotarget_exp_v15_243_adaptive_hp_no_1280_worker_base"
    specification = importlib.util.spec_from_file_location(name, BASE)
    if specification is None or specification.loader is None:
        raise ImportError(BASE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    os.environ[ENVIRONMENT_KEY] = "0"
    _load_base().main()


if __name__ == "__main__":
    main()
