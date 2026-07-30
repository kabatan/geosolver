#!/usr/bin/env python3
"""Full-v15 entrypoint for the generated-qualified trust-radius v2 arm."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


SHARED = Path(__file__).resolve().parents[1] / "shared/trusted_full_worker.py"
SHARED_SHA256 = "ceced55804bcedaf339e5a6751eef1bdfef3a4ed56eddd87565c1cfa04aec55b"

if hashlib.sha256(SHARED.read_bytes()).hexdigest() != SHARED_SHA256:
    raise RuntimeError("hash-bound trust-v2 full worker changed")
specification = importlib.util.spec_from_file_location(
    "geotarget_exp_rank_guard_001_trust_v2_full", SHARED
)
if specification is None or specification.loader is None:
    raise ImportError(SHARED)
module = importlib.util.module_from_spec(specification)
sys.modules[specification.name] = module
specification.loader.exec_module(module)


if __name__ == "__main__":
    module.run()
