"""Champion-v1 wrapper changing only its authenticated HP bridge closure."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parents[1] / "champion_v1/worker.py"
BRIDGE = HERE / "approved_hp_bridge_v5.py"
MANIFEST_PATH = HERE / "champion_closure_manifest.py"
EXPECTED_SHA256 = (
    "9189a7e2c64a51c70a1cc41cca44ed35c561058c2ffc82d962410d8b913d3e14"
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise RuntimeError("champion-v1 worker digest changed")
ORIGINAL_V1 = _load("geotarget_point_on_circle_champion_v1_base", ORIGINAL)
H1_MANIFEST_API = _load(
    "geotarget_point_on_circle_champion_v1_manifest", MANIFEST_PATH
)
H1_MANIFEST = H1_MANIFEST_API.build_manifest(H1_MANIFEST_API.ARM_NO_1280)

ORIGINAL_V1.H1_HP_BRIDGE = BRIDGE
ORIGINAL_V1.H1_MANIFEST_MODULE = MANIFEST_PATH
ORIGINAL_V1.H1_MANIFEST_API = H1_MANIFEST_API
ORIGINAL_V1.H1_MANIFEST = H1_MANIFEST
ORIGINAL_V1.V0.BASE.HP_BRIDGE = BRIDGE
ORIGINAL_V1.V0.BASE.THREAD_ENVIRONMENT[H1_MANIFEST_API.ARM_ENV] = (
    H1_MANIFEST_API.ARM_NO_1280
)
ORIGINAL_V1.V0.BASE.THREAD_ENVIRONMENT[H1_MANIFEST_API.CLOSURE_ENV] = H1_MANIFEST[
    "closure_sha256"
]

V0 = ORIGINAL_V1.V0
BASE = V0.BASE


def main() -> None:
    ORIGINAL_V1.main()


__all__ = ["BASE", "H1_MANIFEST", "H1_MANIFEST_API", "V0", "main"]


if __name__ == "__main__":
    main()

