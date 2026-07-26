#!/usr/bin/env python3
"""Champion-v2 + PointOnCircle repair + bounded/periodic Wave1 proposals.

This candidate-private composition changes only the positive-dimensional
search proposal prefix.  It preserves the current PointOnCircle HP bridge and
champion-v2's zero-dimensional route.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from precision_runtime_preload import install


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
POC_WORKER = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "point_on_circle_periodic_semantics/champion_v2_wrapper.py"
)
BOUNDED_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "bounded_periodic_cover"
)
SEARCH_WORKER = BOUNDED_ROOT / "champion_v2_exact/search_worker.py"
SEARCH_ADAPTER = BOUNDED_ROOT / "adapter.py"
SEARCH_CANDIDATE = BOUNDED_ROOT / "candidate.py"
SEARCH_ARM = "bounded_periodic_cover_wave1_75pct"

EXPECTED = {
    "poc_worker": "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d",
    "search_worker": "51ef7c7313c9fe0fb033b8324afeb62ab4805996019b94c6bf57ab0a2a59f774",
    "search_adapter": "16b5d10c76a3660194c749ebbc8b97a44e52c382d5b65b9dbae9a88229c6eb08",
    "search_candidate": "9bef660e7a6ae1ea1600ccbfad69af52a4c69b2de2c61a5886e0abbcce47aee0",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


PATHS = {
    "poc_worker": POC_WORKER,
    "search_worker": SEARCH_WORKER,
    "search_adapter": SEARCH_ADAPTER,
    "search_candidate": SEARCH_CANDIDATE,
}
ACTUAL = {label: _sha256(path) for label, path in PATHS.items()}
if ACTUAL != EXPECTED:
    raise RuntimeError(
        "candidate dependency changed: "
        + json.dumps({"expected": EXPECTED, "actual": ACTUAL}, sort_keys=True)
    )

POC = _load("geotarget_repro_champion_v2_poc_bounded_wave1", POC_WORKER)
BASE = POC.BASE
ZERO = POC.ZERO

_HP_BRIDGE = Path(BASE.HP_BRIDGE).resolve()
_HP_BRIDGE_SHA256 = _sha256(_HP_BRIDGE)
_PLAN = BASE._plan

# The sole algorithmic mutation: use the already-tested Wave1 proposal seam.
BASE.SEARCH_WORKER = SEARCH_WORKER
BASE.SEARCH_ADAPTER = SEARCH_ADAPTER
BASE.SEARCH_CANDIDATE = SEARCH_CANDIDATE
BASE.SEARCH_ARM = SEARCH_ARM
BASE.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED["search_candidate"]

if Path(BASE.HP_BRIDGE).resolve() != _HP_BRIDGE or _sha256(_HP_BRIDGE) != _HP_BRIDGE_SHA256:
    raise RuntimeError("Wave1 composition changed the PointOnCircle HP bridge")


def active_manifest() -> dict[str, object]:
    return {
        "candidate": "champion_v2_poc_bounded_wave1_preloaded",
        "base": "champion_v2_poc",
        "search_arm": SEARCH_ARM,
        "changed_seams": [
            "SEARCH_WORKER",
            "SEARCH_ADAPTER",
            "SEARCH_CANDIDATE",
            "SEARCH_ARM",
        ],
        "unchanged": [
            "point_on_circle_hp_bridge",
            "champion_v2_zero_dimensional_route",
            "local_solver",
            "endpoint_replay",
            "exactifier",
        ],
        "dependencies": {
            label: {"path": str(PATHS[label].resolve()), "sha256": ACTUAL[label]}
            for label in sorted(PATHS)
        },
        "hp_bridge": {
            "path": str(_HP_BRIDGE),
            "sha256": _HP_BRIDGE_SHA256,
        },
        "truth_or_case_routing": False,
    }


def _plan(**kwargs) -> dict[str, object]:
    plan = _PLAN(**kwargs)
    plan.update(
        {
            "candidate_private_composition": active_manifest(),
            "positive_dimensional_search_start_prefix_changed": True,
            "positive_dimensional_change_scope": "proposal/start-prefix only",
            "positive_dimensional_hp_and_exactification_unchanged": True,
        }
    )
    return plan


BASE._plan = _plan
POC.ORIGINAL_V2._plan = _plan
install(BASE, "geotarget_repro_champion_v2_poc_bounded_wave1_precision")


def main() -> None:
    if "--manifest" in sys.argv:
        print(json.dumps(active_manifest(), sort_keys=True, indent=2))
        return
    if "--help" in sys.argv or "-h" in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--manifest", action="store_true")
        parser.print_help()
        return
    POC.main()


if __name__ == "__main__":
    main()
