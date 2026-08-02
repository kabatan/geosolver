#!/usr/bin/env python3
"""Champion-v5's active primary-only composition, semantic repair only."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ORIGINAL = ROOT / "research/experiments/EXP-V15-243-001/champion_v0/hp_composition_worker.py"
PRIMARY = HERE / "active_primary_composition_worker.py"
EXPECTED_SHA256 = (
    "b8c3b03d2e13da829f9333f1d1285b08b5537c07532c294b383226188d939ef5"
)


def main() -> None:
    if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise RuntimeError("champion-v0 HP composition digest changed")
    specification = importlib.util.spec_from_file_location(
        "geotarget_point_on_circle_active_hp_composition_base", ORIGINAL
    )
    if specification is None or specification.loader is None:
        raise ImportError(ORIGINAL)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    module.BASE_COMPOSITION_WORKER = PRIMARY
    module.main()


if __name__ == "__main__":
    main()

