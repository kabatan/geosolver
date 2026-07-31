#!/usr/bin/env python3
"""Hash-bound full common-control entrypoint for portal Repair A."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "portal_full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = (
    "e0687264846cc7704eaaedd171e7e5f7c34e4c01c62d34b0333845ab163d7954"
)


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("portal repair full wrapper SHA-256 mismatch")
    specification = importlib.util.spec_from_file_location(
        "geotarget_guard_merge_portal_full_wrapper", WRAPPER
    )
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import portal repair full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
