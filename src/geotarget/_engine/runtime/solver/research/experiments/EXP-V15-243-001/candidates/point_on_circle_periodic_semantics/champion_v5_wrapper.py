#!/usr/bin/env python3
"""Executable champion-v5 closure with only POC HP semantics repaired."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ORIGINAL = HERE.parents[1] / "champion_v5/worker.py"
SCHEDULER_WORKER = HERE.parent / "hp_lock_scheduler/worker.py"
CANDIDATE_V2 = HERE / "champion_v2_wrapper.py"
MANIFEST_PATH = HERE / "champion_closure_manifest.py"
ACTIVE_SCHEDULER_BRIDGE = HERE / "active_scheduler_bridge.py"
ACTIVE_HP_COMPOSITION = HERE / "active_hp_composition_worker.py"
ACTIVE_AUTHORITY_WRAPPER = HERE / "authority_adapter_wrapper.py"
INACTIVE_ADAPTIVE_BRIDGE = HERE / "approved_hp_bridge_v5.py"
ORIGINAL_SCHEDULER_BRIDGE = HERE.parent / "hp_lock_scheduler/bridge.py"
EXPECTED_ORIGINAL_SHA256 = (
    "114db602b85ec340d4e602c52e463eb8d74796a7c0f889fe1cf692548c4544f0"
)
EXPECTED_SCHEDULER_SHA256 = (
    "48e86f29beca80587f15a1b691e1d45e7cc0a41d9855c80f4618d3efe6c1b141"
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if _sha256(ORIGINAL) != EXPECTED_ORIGINAL_SHA256:
    raise RuntimeError("champion-v5 worker digest changed")
if _sha256(SCHEDULER_WORKER) != EXPECTED_SCHEDULER_SHA256:
    raise RuntimeError("HP scheduler worker digest changed")

# Load the original solely to reuse its reviewed failure-only exact-coordinate
# functions.  Then construct a fresh scheduler around the candidate v2 chain.
ORIGINAL_V5 = _load("geotarget_point_on_circle_champion_v5_base", ORIGINAL)
os.environ["GEOTARGET_HP_CHAMPION_WORKER"] = str(CANDIDATE_V2.resolve())
SCHEDULER = _load(
    "geotarget_point_on_circle_champion_v5_scheduler", SCHEDULER_WORKER
)

if Path(SCHEDULER.BRIDGE).resolve() != ORIGINAL_SCHEDULER_BRIDGE.resolve():
    raise RuntimeError("champion-v5 scheduler bridge seam changed")
if Path(SCHEDULER.CHAMPION.BASE.HP_BRIDGE).resolve() != ORIGINAL_SCHEDULER_BRIDGE.resolve():
    raise RuntimeError("champion-v5 active HP bridge differs from scheduler ledger")
SCHEDULER.BRIDGE = ACTIVE_SCHEDULER_BRIDGE
SCHEDULER.CHAMPION.BASE.HP_BRIDGE = ACTIVE_SCHEDULER_BRIDGE

ORIGINAL_V5.SCHEDULER = SCHEDULER
ORIGINAL_V5.SCHEDULER_ROOT = SCHEDULER_WORKER.parent
ORIGINAL_V5.SCHEDULER_WORKER = SCHEDULER_WORKER
ORIGINAL_V5.CHAMPION_V2_WORKER = CANDIDATE_V2
ORIGINAL_V5.BASE = SCHEDULER.CHAMPION.BASE
ORIGINAL_V5._SCHEDULER_PLAN = ORIGINAL_V5.BASE._plan
ORIGINAL_V5._SCHEDULED_HP = ORIGINAL_V5.BASE._run_hp_candidate
ORIGINAL_V5.BASE._run_hp_candidate = ORIGINAL_V5._run_exact_fallback
ORIGINAL_V5.BASE._plan = ORIGINAL_V5._plan

BASE = ORIGINAL_V5.BASE
_V5_PLAN = BASE._plan
MANIFEST = _load("geotarget_point_on_circle_champion_v5_manifest", MANIFEST_PATH)


def _plan(**kwargs) -> dict[str, object]:
    plan = _V5_PLAN(**kwargs)
    closure = MANIFEST.build_manifest(MANIFEST.ARM_NO_1280)
    closure_ledger = {
        key: closure[key]
        for key in (
            "schema_version",
            "arm",
            "base_closure_sha256",
            "closure_sha256",
            "file_count",
            "case_family_truth_or_target_read",
            "point_on_circle_semantic_repair_only",
            "optional_endpoint_canonicalization_enabled",
        )
    }
    plan.update(
        {
            "schema_version": (
                "geotarget.exp-v15-243.point-on-circle-champion-v5-plan/v1"
            ),
            "point_on_circle_hp_semantic_repair": True,
            "optional_endpoint_canonicalization_enabled": False,
            "candidate_champion_v5_wrapper_sha256": _sha256(Path(__file__)),
            "candidate_champion_v2_wrapper_sha256": _sha256(CANDIDATE_V2),
            # The digest commits the complete 503-file manifest.  The full
            # list is rebuilt in every fresh worker, but is not copied into
            # stdout: the reviewed outer dry-run cap is 256 KiB.
            "point_on_circle_transitive_manifest": closure_ledger,
            "hp_bridge_path": str(ACTIVE_SCHEDULER_BRIDGE.resolve()),
            "hp_bridge_sha256": _sha256(ACTIVE_SCHEDULER_BRIDGE),
            # The inherited v1 ledger describes an adaptive H1 arm which v5's
            # scheduler does not execute.  State the executable schedule here
            # instead of silently advertising the inactive arm.
            "hp_policy": (
                "unchanged champion-v5 active primary-only two-prefix/four-stage"
            ),
            "hp_candidate_bridge_path": str(ACTIVE_HP_COMPOSITION.resolve()),
            "hp_candidate_bridge_sha256": _sha256(ACTIVE_HP_COMPOSITION),
            "active_authority_wrapper_path": str(
                ACTIVE_AUTHORITY_WRAPPER.resolve()
            ),
            "active_authority_wrapper_sha256": _sha256(
                ACTIVE_AUTHORITY_WRAPPER
            ),
            "hp_runtime_schedule": (
                "unchanged champion-v5 active primary-only two-prefix/four-stage"
            ),
            "adaptive_h1_runtime_active": False,
            "inactive_adaptive_bridge_path": str(
                INACTIVE_ADAPTIVE_BRIDGE.resolve()
            ),
            "inactive_adaptive_bridge_sha256": _sha256(
                INACTIVE_ADAPTIVE_BRIDGE
            ),
            "inactive_adaptive_seams_redirected_and_hash_closed": True,
            "plan_runtime_hp_bridge_consistent": True,
            "zero_dimensional_route_changed": False,
            "scheduler_search_endpoint_budget_changed": False,
            "case_family_truth_target_count_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    SCHEDULER.main()


if __name__ == "__main__":
    main()
