#!/usr/bin/env python3
"""Full current champion authority with additive DiGS Repair A."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = "e2a64742bd2c10f3feb983ed2d7a3ca068d5505a738e3124ea6b56f2229c2135"


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("additive DiGS full-wrapper SHA-256 mismatch")
    name = "geotarget_additive_digs_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, WRAPPER)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import additive DiGS full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
