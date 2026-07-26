#!/usr/bin/env python3
"""Current champion-v2+PoC arm with the existing direct-exact HP seam.

This deliberately stays in the current reproduction worker directory so the
preloaded champion and its sibling helper are imported by their normal module
names.  The direct-exact adapter is installed once on that already assembled
BASE; no scheduler or dataset-runner replacement is introduced here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DIRECT_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/direct_exact_first"
)
RESOURCE_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/hp_lock_scheduler"
)

# The champion preload helper is intentionally resolved as a normal sibling.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(RESOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(RESOURCE_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import champion_v2_poc_preloaded as CHAMPION  # noqa: E402


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


DIRECT = _load(
    "geotarget_repro_20260722_direct_exact_adapter",
    DIRECT_ROOT / "adapter.py",
)
RESOURCE_ADAPTER = _load(
    "geotarget_repro_20260722_direct_exact_resource_adapter",
    RESOURCE_ROOT / "adapter.py",
)
RESOURCE = SimpleNamespace(
    adapter=RESOURCE_ADAPTER,
    RESOURCE_BUSY_STATUSES=DIRECT.RESOURCE_BUSY_STATUSES,
)
BASE = CHAMPION.CHAMPION.BASE
INSTALLATION = DIRECT.install(
    BASE,
    RESOURCE,
    scheduler_worker=HERE / "champion_v2_poc_preloaded.py",
    candidate_worker=Path(__file__),
)


def main() -> None:
    DIRECT.verify_exact_freeze()
    CHAMPION.main()


if __name__ == "__main__":
    main()
