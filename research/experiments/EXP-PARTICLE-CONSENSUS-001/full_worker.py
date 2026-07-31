#!/usr/bin/env python3
"""Full current champion authority with thin particle discovery."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = "5b8dd54dfc079c7db8c0b1317a250407a198a2b2ec29cf89d6b3b8bea9d6d864"


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("particle full-wrapper SHA-256 mismatch")
    name = "geotarget_particle_adaptive_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, WRAPPER)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import particle full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
