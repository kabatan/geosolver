#!/usr/bin/env python3
"""Thin champion-v1 reproduction wrapper with the same five-second reserve."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CHAMPION_PATH = (
    ROOT / "research/experiments/EXP-V15-243-001/champion_v1/worker.py"
)
SELECTION_RESERVE_SECONDS = 5.0

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_champion():
    name = "geotarget_repro_20260722_champion_v1"
    spec = importlib.util.spec_from_file_location(name, CHAMPION_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(CHAMPION_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHAMPION = _load_champion()
V0 = CHAMPION.V0
_ORIGINAL_PLAN = V0.BASE._plan


def _plan(**kwargs):
    plan = _ORIGINAL_PLAN(**kwargs)
    plan.update(
        {
            "reproduction_wrapper": str(Path(__file__).resolve()),
            "selection_reserve_seconds": SELECTION_RESERVE_SECONDS,
            "selection_fix": "source-independent fixed five-second reserve",
        }
    )
    return plan


V0.SELECTION_RESERVE_SECONDS = SELECTION_RESERVE_SECONDS
V0.BASE.SELECTION_RESERVE_SECONDS = SELECTION_RESERVE_SECONDS
V0.BASE._plan = _plan


def main() -> None:
    CHAMPION.main()


if __name__ == "__main__":
    main()
