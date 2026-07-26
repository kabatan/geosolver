#!/usr/bin/env python3
"""Existing champion-v2 + PointOnCircle repair with precision preloaded."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from precision_runtime_preload import install


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
WORKER = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/point_on_circle_periodic_semantics/champion_v2_wrapper.py"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_worker():
    name = "geotarget_repro_20260722_champion_v2_poc_preloaded"
    spec = importlib.util.spec_from_file_location(name, WORKER)
    if spec is None or spec.loader is None:
        raise ImportError(WORKER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHAMPION = _load_worker()
install(CHAMPION.BASE, "geotarget_repro_20260722_champion_v2_poc_precision_runtime")


def main() -> None:
    CHAMPION.main()


if __name__ == "__main__":
    main()
