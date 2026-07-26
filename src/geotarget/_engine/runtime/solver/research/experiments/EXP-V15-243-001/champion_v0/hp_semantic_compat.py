"""Bind champion_v0 to the independently tested HP semantic parity shim."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SEMANTIC_PARITY = (
    ROOT
    / "research/experiments/EXP-V15-243-001/"
    "candidates/hp_semantic_parity/semantic_parity.py"
)


def _load():
    name = "geotarget_exp_v15_243_champion_v0_semantic_parity"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, SEMANTIC_PARITY)
    if specification is None or specification.loader is None:
        raise ImportError(SEMANTIC_PARITY)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def install_hp_semantic_compatibility() -> dict[str, object]:
    return _load().install()


__all__ = ["install_hp_semantic_compatibility"]
