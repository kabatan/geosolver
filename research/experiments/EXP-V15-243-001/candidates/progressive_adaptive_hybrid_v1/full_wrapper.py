"""Exact common-control stack with only its search seam rebound.

The formal control is not the finalist-v15 worker by itself.  It is the
hash-bound champion-v2 + PointOnCircle + precision-preload entrypoint.  Load
that exact top-level stack first, prove every champion layer shares the same
finalist BASE object, and only then replace the five public search-binding
fields.  HP, reservoir, zero-dimensional, periodic, plan, verifier, and
precision-preload authorities therefore remain the common-control objects.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from typing import Mapping


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
CONTROL_ENTRYPOINT_RELATIVE = Path(
    "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
    "champion_v2_poc_preloaded.py"
)
EXPECTED_CONTROL_ENTRYPOINT_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)
EXPECTED_CONTROL_CLOSURE_SHA256 = {
    "champion_v2_wrapper": "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d",
    "original_v2": "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    "poc_champion_v1_wrapper": "022bd5363adc5df51ff0e9c44d82dbced9f830dd9ea3271f0e4af26cf05e3d9c",
    "original_v1": "9189a7e2c64a51c70a1cc41cca44ed35c561058c2ffc82d962410d8b913d3e14",
    "champion_v0": "1a9b62f2b88657f0e43aa0c9fc2a794d686ea595a6544b1a75093e3d6239e889",
    "base": "330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d",
    "hp_bridge": "812f7a2d761e7fe19c3991b9fcdffa5adb9d859aa36b034f7bfddaf201afb40f",
    "baseline_search_worker": "ce2dd5018037fbe5175fc63a2d20d9463243be58d4deeca3bc7cb1aed44e30bf",
    "precision_runtime": "8d072c47f8a7f3bcb15dfff44d952e94c97adba22d6f42a2a758cad52a80cd7b",
}
SEARCH_WORKER = HERE / "search_worker.py"
SEARCH_ADAPTER = HERE / "search_adapter.py"
SEARCH_CANDIDATE = HERE / "candidate.py"
EXPECTED_LOCAL_SHA256 = {
    "search_worker.py": "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6",
    "search_adapter.py": "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    "candidate.py": "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972",
}
SEARCH_ARM = "progressive_adaptive_hybrid_64_600"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_control(root: Path):
    path = root / CONTROL_ENTRYPOINT_RELATIVE
    if not path.is_file():
        raise SystemExit(f"frozen common-control entrypoint is unavailable: {path}")
    if _sha256(path) != EXPECTED_CONTROL_ENTRYPOINT_SHA256:
        raise SystemExit("frozen common-control entrypoint SHA-256 mismatch")
    workers = path.parent
    # champion_v2_poc_preloaded imports precision_runtime_preload by name.
    for directory in (workers, root):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    name = "geotarget_progressive_adaptive_hybrid_common_control"
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise SystemExit(f"cannot import frozen common control: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _control_paths(control) -> Mapping[str, Path]:
    champion = control.CHAMPION
    original_v2 = champion.ORIGINAL_V2
    periodic_v1 = champion.V1
    original_v1 = periodic_v1.ORIGINAL_V1
    champion_v0 = original_v1.V0
    base = champion.BASE
    return {
        "champion_v2_wrapper": Path(champion.__file__).resolve(),
        "original_v2": Path(original_v2.__file__).resolve(),
        "poc_champion_v1_wrapper": Path(periodic_v1.__file__).resolve(),
        "original_v1": Path(original_v1.__file__).resolve(),
        "champion_v0": Path(champion_v0.__file__).resolve(),
        "base": Path(base.__file__).resolve(),
        "hp_bridge": Path(base.HP_BRIDGE).resolve(),
        "baseline_search_worker": Path(base.SEARCH_WORKER).resolve(),
        "precision_runtime": Path(base.PRECISION_RUNTIME).resolve(),
    }


def _verify_control_stack(control) -> None:
    champion = control.CHAMPION
    original_v2 = champion.ORIGINAL_V2
    periodic_v1 = champion.V1
    original_v1 = periodic_v1.ORIGINAL_V1
    champion_v0 = original_v1.V0
    base = champion.BASE
    identities = (
        base is original_v2.BASE,
        base is periodic_v1.BASE,
        base is original_v1.V0.BASE,
        base is champion_v0.BASE,
        original_v2.V1 is periodic_v1,
    )
    if not all(identities):
        raise SystemExit("common-control champion layers do not share one BASE")
    paths = _control_paths(control)
    for name, expected in EXPECTED_CONTROL_CLOSURE_SHA256.items():
        path = paths[name]
        if not path.is_file() or _sha256(path) != expected:
            raise SystemExit(f"common-control closure SHA-256 mismatch: {name}")


def _verify_local_search_binding() -> None:
    paths = {
        "search_worker.py": SEARCH_WORKER,
        "search_adapter.py": SEARCH_ADAPTER,
        "candidate.py": SEARCH_CANDIDATE,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise SystemExit(f"adaptive hybrid dependency is unavailable: {path}")
        if _sha256(path) != EXPECTED_LOCAL_SHA256[name]:
            raise SystemExit(f"adaptive hybrid SHA-256 mismatch: {name}")


def configure(*, frozen_root: Path, enable_hybrid: bool = True):
    """Return the exact control stack, optionally rebinding only discovery."""

    control = _load_control(frozen_root)
    _verify_control_stack(control)
    if not enable_hybrid:
        return control
    _verify_local_search_binding()
    base = control.CHAMPION.BASE
    base.SEARCH_WORKER = SEARCH_WORKER
    base.SEARCH_ADAPTER = SEARCH_ADAPTER
    base.SEARCH_CANDIDATE = SEARCH_CANDIDATE
    base.SEARCH_ARM = SEARCH_ARM
    base.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED_LOCAL_SHA256["candidate.py"]
    return control


def main() -> None:
    frozen_root = Path(
        os.environ.get("GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT))
    ).resolve()
    configure(frozen_root=frozen_root, enable_hybrid=True).main()


__all__ = [
    "CONTROL_ENTRYPOINT_RELATIVE",
    "EXPECTED_CONTROL_CLOSURE_SHA256",
    "EXPECTED_CONTROL_ENTRYPOINT_SHA256",
    "EXPECTED_LOCAL_SHA256",
    "SEARCH_ARM",
    "configure",
    "main",
]
