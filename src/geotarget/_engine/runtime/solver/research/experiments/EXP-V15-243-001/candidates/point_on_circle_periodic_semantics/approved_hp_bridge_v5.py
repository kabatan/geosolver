#!/usr/bin/env python3
"""Authenticated champion HP bridge for the POC semantic-repair closure."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE.parent / "adaptive_hp/bridge_contract.py"
MANIFEST_PATH = HERE / "champion_closure_manifest.py"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    manifest = _load(
        "geotarget_point_on_circle_approved_manifest", MANIFEST_PATH
    )
    verified = manifest.verify_environment(os.environ)
    if verified.get("arm") != manifest.ARM_NO_1280:
        raise SystemExit("POC repair closure requires the no-fresh-1280 arm")
    contract = _load(
        "geotarget_point_on_circle_approved_bridge_contract", CONTRACT_PATH
    )
    contract.HERE = HERE
    contract.MANIFEST_PATH = MANIFEST_PATH
    contract.run_bridge(manifest.ARM_NO_1280)


if __name__ == "__main__":
    main()

