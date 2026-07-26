#!/usr/bin/env python3
"""Run the candidate-private champion-v5 closure with the reviewed harness."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SCHEDULER_ROOT = HERE.parent / "hp_lock_scheduler"
SCHEDULER_RUNNER = SCHEDULER_ROOT / "run_dataset.py"
WORKER = HERE / "champion_v5_wrapper.py"

# Preserve champion-v5's resource policy while selecting the candidate-private
# top-level executable.  The scheduler itself still enforces the per-core lock.
os.environ["GEOTARGET_HP_MAX_JOBS"] = "16"
os.environ["GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES"] = str(20 * 1024**3)
os.environ["GEOTARGET_MEMORY_RESERVATION_TOKEN_BYTES"] = str(256 * 1024**2)
os.environ["GEOTARGET_HP_CHAMPION_WORKER"] = str(
    (HERE / "champion_v2_wrapper.py").resolve()
)

if str(SCHEDULER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULER_ROOT))


def _load_scheduler_runner():
    name = "geotarget_point_on_circle_champion_v5_dataset_scheduler"
    specification = importlib.util.spec_from_file_location(
        name,
        SCHEDULER_RUNNER,
    )
    if specification is None or specification.loader is None:
        raise ImportError(SCHEDULER_RUNNER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    runner = _load_scheduler_runner()
    runner.WORKER = WORKER
    runner.main()


if __name__ == "__main__":
    main()
