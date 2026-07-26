#!/usr/bin/env python3
"""Baseline v15 with only its precision runtime preloaded before search."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from precision_runtime_preload import install


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_base():
    name = "geotarget_repro_20260722_baseline_preloaded"
    spec = importlib.util.spec_from_file_location(name, BASE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base()
install(BASE, "geotarget_repro_20260722_baseline_precision_runtime")
_ORIGINAL_PLAN = BASE._plan


def _plan(**kwargs):
    plan = _ORIGINAL_PLAN(**kwargs)
    plan.update(
        {
            "reproduction_wrapper": str(Path(__file__).resolve()),
            "selection_fix": "precision runtime preloaded before frozen search",
            "selection_reserve_seconds": 1.0,
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
