#!/usr/bin/env python3
"""Champion v1: target-free reservoir plus failure-typed HP refinement.

This is deliberately a thin integration layer.  It reuses champion_v0
unchanged and replaces only its HP bridge with the fixed H1 portfolio:

* thin 512/768 refinement and the original 1024-bit authority;
* event-triggered direct Broyden when the thin prefix stalls;
* condition-aware target-stability correction;
* no fresh-1280 lane.

The bridge cannot read case identity, family, truth, or a known target count.
All final targets still come from the original exact authority.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CHAMPION_V0_WORKER = HERE.parent / "champion_v0/worker.py"
H1_HP_BRIDGE = (
    HERE / "approved_hp_bridge.py"
)
H1_MANIFEST_MODULE = (
    HERE.parent / "candidates/adaptive_hp/transitive_manifest.py"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_champion_v0():
    name = "geotarget_exp_v15_243_champion_v1_base"
    specification = importlib.util.spec_from_file_location(
        name, CHAMPION_V0_WORKER
    )
    if specification is None or specification.loader is None:
        raise ImportError(CHAMPION_V0_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_h1_manifest_module():
    name = "geotarget_exp_v15_243_champion_v1_h1_manifest"
    specification = importlib.util.spec_from_file_location(
        name, H1_MANIFEST_MODULE
    )
    if specification is None or specification.loader is None:
        raise ImportError(H1_MANIFEST_MODULE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


H1_MANIFEST_API = _load_h1_manifest_module()
H1_MANIFEST = H1_MANIFEST_API.build_manifest(
    H1_MANIFEST_API.ARM_NO_1280
)
V0 = _load_champion_v0()
_V0_PLAN = V0.BASE._plan


def _plan(**kwargs):
    plan = _V0_PLAN(**kwargs)
    plan.update(
        {
            "schema_version": "geotarget.exp-v15-243-champion-v1-plan/v1",
            "champion_v1_worker_sha256": V0.BASE._sha256(
                Path(__file__).read_bytes()
            ),
            "hp_policy": (
                "failure-typed H1: thin 512/768 plus event-Broyden and "
                "condition-aware target-stability correction; original "
                "1024-bit replay/exact authority; fresh-1280 disabled"
            ),
            "hp_bridge_path": str(H1_HP_BRIDGE),
            "hp_bridge_sha256": V0.BASE._sha256(H1_HP_BRIDGE.read_bytes()),
            "hp_candidate_bridge_path": str(
                HERE.parent
                / "candidates/adaptive_hp/champion_bridge_no_1280.py"
            ),
            "hp_transitive_implementation_manifest": H1_MANIFEST,
            "hp_transitive_closure_approved_by_top_level": True,
            "fresh_1280_enabled": False,
        }
    )
    return plan


V0.BASE.HP_BRIDGE = H1_HP_BRIDGE
V0.BASE.THREAD_ENVIRONMENT[H1_MANIFEST_API.ARM_ENV] = (
    H1_MANIFEST_API.ARM_NO_1280
)
V0.BASE.THREAD_ENVIRONMENT[H1_MANIFEST_API.CLOSURE_ENV] = H1_MANIFEST[
    "closure_sha256"
]
V0.BASE._plan = _plan


def main() -> None:
    V0.main()


if __name__ == "__main__":
    main()
