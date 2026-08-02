#!/usr/bin/env python3
"""Guarded HP endpoint bridge bound to champion_v0 compatibility worker."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN_BRIDGE = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hp_endpoint_bridge_v10/run_one_endpoint.py"
)
COMPOSITION_WORKER = HERE / "hp_composition_worker.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_bridge():
    name = "geotarget_exp_v15_243_champion_v0_guarded_hp_bridge"
    specification = importlib.util.spec_from_file_location(name, FROZEN_BRIDGE)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_BRIDGE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    bridge = _load_bridge()
    bridge.WORKER = COMPOSITION_WORKER
    bridge.main()


if __name__ == "__main__":
    main()
