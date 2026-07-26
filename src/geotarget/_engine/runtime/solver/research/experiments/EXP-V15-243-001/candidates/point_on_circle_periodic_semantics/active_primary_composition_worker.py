#!/usr/bin/env python3
"""Primary-only composition with the reviewed runner redirected semantically."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ORIGINAL = (
    ROOT
    / "research/experiments/EXP-REAL61-008/hp_precision_schedule_v11/composition_worker.py"
)
RUNNER = HERE / "active_run_candidate_one.py"
EXPECTED_SHA256 = (
    "b4f3cb1b20042cde4c5143ad5a20f1eba5bf5c176216804aa1beb768881d6d29"
)


def main() -> None:
    observed = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
    if observed != EXPECTED_SHA256:
        raise RuntimeError("active primary composition worker digest changed")
    specification = importlib.util.spec_from_file_location(
        "geotarget_point_on_circle_active_primary_composition_base", ORIGINAL
    )
    if specification is None or specification.loader is None:
        raise ImportError(ORIGINAL)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    module.RUNNER_PATH = RUNNER
    module.main()


if __name__ == "__main__":
    main()
