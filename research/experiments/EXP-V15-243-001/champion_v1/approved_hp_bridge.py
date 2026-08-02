#!/usr/bin/env python3
"""Top-level authenticated entry to the frozen H1 adaptive-HP closure."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ADAPTIVE_HP = HERE.parent / "candidates/adaptive_hp"
MANIFEST_PATH = ADAPTIVE_HP / "transitive_manifest.py"
BRIDGE_CONTRACT_PATH = ADAPTIVE_HP / "bridge_contract.py"

if str(ADAPTIVE_HP) not in sys.path:
    sys.path.insert(0, str(ADAPTIVE_HP))


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
        "geotarget_exp_v15_243_champion_v1_approved_manifest",
        MANIFEST_PATH,
    )
    verified = manifest.verify_environment(os.environ)
    if verified.get("arm") != manifest.ARM_NO_1280:
        raise SystemExit("champion_v1 requires the no-fresh-1280 HP arm")

    bridge_contract = _load(
        "geotarget_exp_v15_243_champion_v1_approved_contract",
        BRIDGE_CONTRACT_PATH,
    )
    # The candidate bridge recomputes the same closure before loading its
    # backend and again before accepting an artifact.
    bridge_contract.run_bridge(manifest.ARM_NO_1280)


if __name__ == "__main__":
    main()
