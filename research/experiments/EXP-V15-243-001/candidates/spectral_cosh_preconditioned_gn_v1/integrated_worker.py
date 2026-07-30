#!/usr/bin/env python3
"""Frozen proof-bearing champion with only SEARCH_WORKER redirected."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
FROZEN_ROOT = Path(os.environ.get(
    "GEOTARGET_FROZEN_REPOSITORY", "/home/kabatan/work/solver-experiment-runtime/solver"
)).resolve()
CHAMPION_PATH = FROZEN_ROOT / "research/experiments/EXP-V15-243-001/champion_v1/worker.py"
CHAMPION_SHA256 = "9189a7e2c64a51c70a1cc41cca44ed35c561058c2ffc82d962410d8b913d3e14"
SEARCH_WORKER = HERE / "search_worker.py"


if hashlib.sha256(CHAMPION_PATH.read_bytes()).hexdigest() != CHAMPION_SHA256:
    raise RuntimeError("frozen proof-bearing champion changed")
spec = importlib.util.spec_from_file_location("geotarget_spectral_cosh_frozen_champion", CHAMPION_PATH)
if spec is None or spec.loader is None:
    raise ImportError(CHAMPION_PATH)
CHAMPION = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = CHAMPION
spec.loader.exec_module(CHAMPION)

CHAMPION.V0.BASE.SEARCH_WORKER = SEARCH_WORKER
_ORIGINAL_PLAN = CHAMPION.V0.BASE._plan


def _plan(**kwargs):
    plan = _ORIGINAL_PLAN(**kwargs)
    plan.update({
        "schema_version": "geotarget.spectral-cosh-quarter-lane-integrated/v1",
        "frozen_champion_sha256": CHAMPION_SHA256,
        "candidate_search_worker_path": str(SEARCH_WORKER),
        "candidate_search_worker_sha256": CHAMPION.V0.BASE._sha256(SEARCH_WORKER.read_bytes()),
        "search_delta": "75% frozen starts; every fourth start changes only Ruiz LM RHS",
        "hp_and_final_exact_authority_unchanged": True,
    })
    return plan


CHAMPION.V0.BASE._plan = _plan


if __name__ == "__main__":
    CHAMPION.main()

