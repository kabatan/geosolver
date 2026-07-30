#!/usr/bin/env python3
"""Full frozen-v15 authority with the 96/300/600 search profile."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = "cf1d9ab139895a1f6ac27477664316e2274e279ce400a069fdb7e306032d0f0d"


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("progressive full wrapper SHA-256 mismatch")
    name = "geotarget_progressive_local_budget_full_wrapper_96"
    specification = importlib.util.spec_from_file_location(name, WRAPPER)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import progressive full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.main("96-300-600")


if __name__ == "__main__":
    main()
