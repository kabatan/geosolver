#!/usr/bin/env python3
"""Existing HP composition worker with general primitive semantic parity."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GEOSOLVER_SRC = ROOT.parent / "geosolver/src"
BASE_COMPOSITION_WORKER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hp_precision_schedule_v11/composition_worker.py"
)

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(GEOSOLVER_SRC) not in sys.path:
    sys.path.insert(0, str(GEOSOLVER_SRC))

from hp_semantic_compat import install_hp_semantic_compatibility  # noqa: E402


def _load_base():
    name = "geotarget_exp_v15_243_champion_v0_hp_composition_base"
    specification = importlib.util.spec_from_file_location(
        name, BASE_COMPOSITION_WORKER
    )
    if specification is None or specification.loader is None:
        raise ImportError(BASE_COMPOSITION_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    install_hp_semantic_compatibility()
    _load_base().main()


if __name__ == "__main__":
    main()
