"""Exact common control with only SEARCH_WORKER rebound to portal Repair A."""

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
PORTAL_SEARCH_WORKER = HERE / "portal_search_worker.py"
EXPECTED_PORTAL_SEARCH_WORKER_SHA256 = (
    "74236c96c4e4dd42fa9079435dbf41b824a9ecdd5baf1477e076da701833b4f7"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_control(root: Path):
    path = root / CONTROL_ENTRYPOINT_RELATIVE
    if not path.is_file() or _sha256(path) != EXPECTED_CONTROL_ENTRYPOINT_SHA256:
        raise SystemExit("frozen common-control entrypoint SHA-256 mismatch")
    for directory in (path.parent, root):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    specification = importlib.util.spec_from_file_location(
        "geotarget_guard_merge_portal_common_control", path
    )
    if specification is None or specification.loader is None:
        raise SystemExit("cannot import frozen common control")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
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
    if not all(
        (
            base is original_v2.BASE,
            base is periodic_v1.BASE,
            base is original_v1.V0.BASE,
            base is champion_v0.BASE,
            original_v2.V1 is periodic_v1,
        )
    ):
        raise SystemExit("common-control champion layers do not share one BASE")
    for name, expected in EXPECTED_CONTROL_CLOSURE_SHA256.items():
        path = _control_paths(control)[name]
        if not path.is_file() or _sha256(path) != expected:
            raise SystemExit(f"common-control closure SHA-256 mismatch: {name}")


def configure(*, frozen_root: Path, enable_portal: bool = True):
    control = _load_control(frozen_root)
    _verify_control_stack(control)
    if not enable_portal:
        return control
    if (
        not PORTAL_SEARCH_WORKER.is_file()
        or _sha256(PORTAL_SEARCH_WORKER) != EXPECTED_PORTAL_SEARCH_WORKER_SHA256
    ):
        raise SystemExit("portal repair search worker SHA-256 mismatch")
    # Candidate-specific monkey patch only.  HP, reservoir, verifier,
    # canonical replay, adapter, local kernel, and arm stay exact control.
    control.CHAMPION.BASE.SEARCH_WORKER = PORTAL_SEARCH_WORKER
    return control


def main() -> None:
    frozen_root = Path(
        os.environ.get("GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT))
    ).resolve()
    configure(frozen_root=frozen_root, enable_portal=True).main()


__all__ = [
    "EXPECTED_PORTAL_SEARCH_WORKER_SHA256",
    "PORTAL_SEARCH_WORKER",
    "configure",
    "main",
]
