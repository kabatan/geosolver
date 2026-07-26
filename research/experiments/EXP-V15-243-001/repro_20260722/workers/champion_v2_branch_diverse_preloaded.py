#!/usr/bin/env python3
"""Champion v2/preload with the existing branch-diverse reservoir seam."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Sequence

from precision_runtime_preload import install


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CHAMPION_PATH = (
    ROOT / "research/experiments/EXP-V15-243-001/champion_v2/worker.py"
)
BRANCH_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/branch_diverse_reservoir"
)

for path in (ROOT, BRANCH_ROOT):
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


CHAMPION = _load(
    "geotarget_repro_20260722_champion_v2_branch_diverse_preloaded",
    CHAMPION_PATH,
)
install(
    CHAMPION.BASE,
    "geotarget_repro_20260722_champion_v2_branch_diverse_precision_runtime",
)
BRANCH_BINDING = _load(
    "geotarget_repro_20260722_branch_diverse_binding",
    BRANCH_ROOT / "champion_binding.py",
)

# champion_v2 -> champion_v1 -> champion_v0. Patch only the existing
# search-to-HP endpoint seam; search, HP, exactification, and CLI stay v2.
V0 = CHAMPION.V1.V0


def _fresh_replay_candidates(
    document: dict[str, object],
    endpoints: Sequence[object],
    *,
    hard_deadline: float,
):
    return BRANCH_BINDING.build_replay_candidates(
        V0,
        arm=BRANCH_BINDING.ADAPTER.BRANCH_DIVERSE_ARM,
        document=document,
        endpoints=endpoints,
        hard_deadline=hard_deadline,
    )


V0._fresh_replay_candidates = _fresh_replay_candidates
V0.BASE._fresh_replay_candidates = _fresh_replay_candidates


def main() -> None:
    CHAMPION.main()


if __name__ == "__main__":
    main()
