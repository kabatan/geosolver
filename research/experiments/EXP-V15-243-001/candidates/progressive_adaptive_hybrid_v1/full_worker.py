#!/usr/bin/env python3
"""Full frozen-v15 authority with adaptive 64->600 discovery."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("adaptive hybrid full wrapper SHA-256 mismatch")
    name = "geotarget_progressive_adaptive_hybrid_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, WRAPPER)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import adaptive hybrid full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
