#!/usr/bin/env python3
"""Use the existing guarded/locked endpoint bridge with the reviewed primary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN_BRIDGE_PATH = HERE.parent / "hp_endpoint_bridge_v10/run_one_endpoint.py"
COMPOSITION_WORKER = HERE / "composition_worker.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_bridge():
    name = "geotarget_exp008_hp_precision_schedule_guarded_bridge"
    specification = importlib.util.spec_from_file_location(name, FROZEN_BRIDGE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_BRIDGE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    bridge = _load_bridge()
    # This is the only seam changed from the existing memory-safe bridge.  Its
    # dry-plan digest, global one-HP-job lock, process limits, source/endpoint
    # digest checks, and accepted-artifact predicate remain unchanged.
    bridge.WORKER = COMPOSITION_WORKER
    bridge.main()


if __name__ == "__main__":
    main()
