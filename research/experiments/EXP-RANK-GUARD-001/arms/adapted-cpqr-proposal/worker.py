#!/usr/bin/env python3
"""Full-v15 fail-closed entrypoint for the blocked adapted-CPQR arm."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


SHARED = Path(__file__).resolve().parents[1] / "shared/full_worker.py"
SHARED_SHA256 = "7f30a88956726658fe54f5e995be9db5544b3667e406159d1e6eb7bbe7f5d3a6"

if hashlib.sha256(SHARED.read_bytes()).hexdigest() != SHARED_SHA256:
    raise RuntimeError("hash-bound shared full worker changed")
specification = importlib.util.spec_from_file_location(
    "geotarget_exp_rank_guard_001_cpqr_full", SHARED
)
if specification is None or specification.loader is None:
    raise ImportError(SHARED)
module = importlib.util.module_from_spec(specification)
sys.modules[specification.name] = module
specification.loader.exec_module(module)


if __name__ == "__main__":
    module.run(module.ADAPTED_CPQR_BLOCKED)
