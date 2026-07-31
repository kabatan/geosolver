#!/usr/bin/env python3
"""Hash-bound full common-control entrypoint for collect-only gate screening."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "collect_full_wrapper.py"
EXPECTED_WRAPPER_SHA256 = (
    "eb2aafe9473e4887f59ea987d029902d6bfd19e50188f8cc6c398e82e1eb582c"
)


def main() -> None:
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest() != EXPECTED_WRAPPER_SHA256:
        raise SystemExit("collect-only full wrapper SHA-256 mismatch")
    specification = importlib.util.spec_from_file_location(
        "geotarget_guard_merge_collect_full_wrapper", WRAPPER
    )
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import collect-only full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()
