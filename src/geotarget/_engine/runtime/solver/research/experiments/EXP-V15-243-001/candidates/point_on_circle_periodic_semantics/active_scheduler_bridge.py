#!/usr/bin/env python3
"""Per-core scheduler bridge preserving policy and redirecting HP semantics."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "hp_lock_scheduler/bridge.py"
COMPOSITION = HERE / "active_hp_composition_worker.py"
EXPECTED_SHA256 = (
    "15a292ccc98f1c86b989aa1104584cc60fa590fe011b1a33de45a7b66704b8e8"
)


def main() -> None:
    if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise RuntimeError("scheduler bridge digest changed")
    specification = importlib.util.spec_from_file_location(
        "geotarget_point_on_circle_active_scheduler_bridge_base", ORIGINAL
    )
    if specification is None or specification.loader is None:
        raise ImportError(ORIGINAL)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    module.COMPOSITION_WORKER = COMPOSITION
    module.EXPECTED_COMPOSITION_WORKER_SHA256 = hashlib.sha256(
        COMPOSITION.read_bytes()
    ).hexdigest()
    module.main()


if __name__ == "__main__":
    main()
