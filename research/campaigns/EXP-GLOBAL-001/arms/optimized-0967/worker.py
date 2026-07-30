#!/usr/bin/env python3
"""Adapt the clean 0967ff1c optimized core to the frozen worker CLI."""

from __future__ import annotations

import os
from pathlib import Path
import sys


PINNED_ROOT = Path("/home/kabatan/work/solver-wt/control-0967")
SOURCE_ROOT = PINNED_ROOT / "src"


def main() -> None:
    if not SOURCE_ROOT.is_dir():
        raise SystemExit(f"pinned product source is unavailable: {SOURCE_ROOT}")
    os.environ["GEOTARGET_PRODUCT_PYTHON"] = sys.executable
    sys.path.insert(0, str(SOURCE_ROOT))
    from geotarget.optimized_entrypoint import main as optimized_main

    cpu = None
    for index, value in enumerate(sys.argv[:-1]):
        if value == "--cpu":
            cpu = sys.argv[index + 1]
            break
    if cpu is None:
        raise SystemExit("frozen worker --cpu is required")
    sys.argv = [sys.argv[0], "--product-cpus", cpu, *sys.argv[1:]]
    optimized_main()


if __name__ == "__main__":
    main()
