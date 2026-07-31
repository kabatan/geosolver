#!/usr/bin/env python3
"""Current adaptive baseline plus surplus-only particle descriptor tail."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "tail_full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = "2e8902f81ccd677d62546a29e49244b481879bc4e9a4752149cd7e9541905a8b"


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("particle tail full-wrapper SHA-256 mismatch")
    name = "geotarget_particle_tail_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, WRAPPER)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import particle tail full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
