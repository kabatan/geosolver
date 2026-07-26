#!/usr/bin/env python3
"""Current champion plus the existing guard-stratum proposal scheduler."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CURRENT = HERE / "champion_v2_poc_preloaded.py"
SEARCH_WORKER = HERE / "guard_stratum_search_worker.py"
SEARCH_ADAPTER = HERE / "guard_stratum_search_adapter.py"
SEARCH_CANDIDATE = (
    ROOT
    / "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
    "corrective_nearroot_strict_restart_v2/candidate.py"
)

for path in (HERE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CURRENT_WORKER = _load(
    "geotarget_repro_champion_v2_poc_guard_stratum_current", CURRENT
)
BASE = CURRENT_WORKER.CHAMPION.BASE
BASE.SEARCH_WORKER = SEARCH_WORKER
BASE.SEARCH_ADAPTER = SEARCH_ADAPTER
BASE.SEARCH_CANDIDATE = SEARCH_CANDIDATE


def main() -> None:
    CURRENT_WORKER.main()


if __name__ == "__main__":
    main()
