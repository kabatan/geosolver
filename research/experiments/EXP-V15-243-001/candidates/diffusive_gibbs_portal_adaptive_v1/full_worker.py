#!/usr/bin/env python3
"""Full current champion authority with thin DiGS discovery."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = "baf7575bfb885be2ff073a012a59ec51307c7f884cb65ee531fae01d97da2d50"


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("DiGS full-wrapper SHA-256 mismatch")
    name = "geotarget_digs_adaptive_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, WRAPPER)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import DiGS full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
