#!/usr/bin/env python3
"""Champion v1 with only its precision runtime preloaded before search."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from precision_runtime_preload import install


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CHAMPION_PATH = (
    ROOT / "research/experiments/EXP-V15-243-001/champion_v1/worker.py"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_champion():
    name = "geotarget_repro_20260722_champion_v1_preloaded"
    spec = importlib.util.spec_from_file_location(name, CHAMPION_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(CHAMPION_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHAMPION = _load_champion()
V0 = CHAMPION.V0
install(V0.BASE, "geotarget_repro_20260722_champion_v1_precision_runtime")
_ORIGINAL_PLAN = V0.BASE._plan


def _plan(**kwargs):
    plan = _ORIGINAL_PLAN(**kwargs)
    plan.update(
        {
            "reproduction_wrapper": str(Path(__file__).resolve()),
            "selection_fix": "precision runtime preloaded before frozen search",
            "selection_reserve_seconds": 3.0,
        }
    )
    return plan


V0.BASE._plan = _plan


def main() -> None:
    CHAMPION.main()


if __name__ == "__main__":
    main()
