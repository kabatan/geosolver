"""Reviewed thin authority runner with only its adapter path redirected."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ORIGINAL = (
    ROOT
    / "research/experiments/EXP-REAL61-008/hp_precision_schedule_v11/run_candidate_one.py"
)
AUTHORITY_WRAPPER = HERE / "authority_adapter_wrapper.py"
EXPECTED_SHA256 = (
    "d1337a71a2a4caf0d0ea8de54f9e4cb1ba846f7d6c031b8b119a4e97a529b41e"
)


if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise RuntimeError("active thin authority runner digest changed")
specification = importlib.util.spec_from_file_location(
    "geotarget_point_on_circle_active_thin_runner_base", ORIGINAL
)
if specification is None or specification.loader is None:
    raise ImportError(ORIGINAL)
BASE = importlib.util.module_from_spec(specification)
sys.modules[specification.name] = BASE
specification.loader.exec_module(BASE)
BASE.ADAPTER_PATH = AUTHORITY_WRAPPER

build_candidate_authority = BASE.build_candidate_authority


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
