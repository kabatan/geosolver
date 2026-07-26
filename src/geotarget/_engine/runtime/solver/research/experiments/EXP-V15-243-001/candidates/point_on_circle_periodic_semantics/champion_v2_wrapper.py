"""Champion-v2 wrapper preserving its zero-dimensional authority verbatim."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parents[1] / "champion_v2/worker.py"
CANDIDATE_V1 = HERE / "champion_v1_wrapper.py"
EXPECTED_SHA256 = (
    "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca"
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
    raise RuntimeError("champion-v2 worker digest changed")
ORIGINAL_V2 = _load("geotarget_point_on_circle_champion_v2_base", ORIGINAL)
V1 = _load("geotarget_point_on_circle_champion_v2_candidate_v1", CANDIDATE_V1)

# Rebind only the positive-dimensional delegate.  ZERO and every exact-source
# zero-dimensional function remain the original champion-v2 objects.
ORIGINAL_V2.V1 = V1
ORIGINAL_V2.CHAMPION_V1_WORKER = CANDIDATE_V1
ORIGINAL_V2.BASE = V1.V0.BASE
ORIGINAL_V2._V1_PLAN = ORIGINAL_V2.BASE._plan
ORIGINAL_V2.BASE._plan = ORIGINAL_V2._plan

BASE = ORIGINAL_V2.BASE
ZERO = ORIGINAL_V2.ZERO


def main() -> None:
    ORIGINAL_V2.main()


__all__ = ["BASE", "V1", "ZERO", "main"]


if __name__ == "__main__":
    main()

