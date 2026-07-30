#!/usr/bin/env python3
"""Expose the archived champion-v2/POC worker to exact_outer.

This module intentionally does not install a numerical scheduler or replace
the archived HP callable.  The only new runtime seam is the reviewed per-core
lease API required by ``exact_outer_decorator`` for its exact child.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
ARCHIVE_ROOT_ENV = "GEOTARGET_ARCHIVE_EXACT_OUTER_RUNTIME_ROOT"
DEFAULT_ARCHIVE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver"
)
ARCHIVE_ROOT = Path(
    os.environ.get(ARCHIVE_ROOT_ENV, str(DEFAULT_ARCHIVE_ROOT))
).resolve()
CAMPAIGN_ROOT = (
    ARCHIVE_ROOT / "research/experiments/EXP-V15-243-001"
)
PRELOADED_ROOT = CAMPAIGN_ROOT / "repro_20260722/workers"
HISTORICAL_WORKER = PRELOADED_ROOT / "champion_v2_poc_preloaded.py"
PRECISION_PRELOAD = PRELOADED_ROOT / "precision_runtime_preload.py"
POC_ROOT = CAMPAIGN_ROOT / "candidates/point_on_circle_periodic_semantics"
POC_V2_WRAPPER = POC_ROOT / "champion_v2_wrapper.py"
POC_V1_WRAPPER = POC_ROOT / "champion_v1_wrapper.py"
POC_MANIFEST = POC_ROOT / "champion_closure_manifest.py"
POC_HP_BRIDGE = POC_ROOT / "approved_hp_bridge_v5.py"
CHAMPION_V2 = CAMPAIGN_ROOT / "champion_v2/worker.py"
RESOURCE_POLICY = CAMPAIGN_ROOT / "candidates/hp_lock_scheduler/policy.py"

EXPECTED_DEPENDENCY_SHA256 = {
    HISTORICAL_WORKER: (
        "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
    ),
    PRECISION_PRELOAD: (
        "1139fa3ae5f4805b4791bc3f99fb6dd89b38f0cdc778c29871eb7d3469e3c403"
    ),
    POC_V2_WRAPPER: (
        "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d"
    ),
    POC_V1_WRAPPER: (
        "022bd5363adc5df51ff0e9c44d82dbced9f830dd9ea3271f0e4af26cf05e3d9c"
    ),
    POC_MANIFEST: (
        "0e7910f33594ac600e85f964ca182e3bbc6835ca9a44a39db40d877e957542d5"
    ),
    POC_HP_BRIDGE: (
        "812f7a2d761e7fe19c3991b9fcdffa5adb9d859aa36b034f7bfddaf201afb40f"
    ),
    CHAMPION_V2: (
        "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca"
    ),
    RESOURCE_POLICY: (
        "c32ed095643c7154742bc94743fbe69e83e77cddd6d5b9f8a00e4b38b5c16121"
    ),
}


class IntegrationError(RuntimeError):
    """The frozen archive closure no longer matches the reviewed lane."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(path.resolve()): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_DEPENDENCY_SHA256
    }
    expected = {
        str(path.resolve()): digest
        for path, digest in EXPECTED_DEPENDENCY_SHA256.items()
    }
    if observed != expected:
        raise IntegrationError("frozen historical champion/POC closure changed")
    return observed


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


verify_dependencies()
# The preloaded entry imports its one helper by module name before it adds the
# archive root to sys.path.  Adding only that reviewed directory preserves the
# original load order without copying the historical closure.
if str(PRELOADED_ROOT) not in sys.path:
    sys.path.insert(0, str(PRELOADED_ROOT))
if str(ARCHIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(ARCHIVE_ROOT))

POLICY = _load(
    "geotarget_archive_exact_outer_resource_policy",
    RESOURCE_POLICY,
)
HISTORICAL = _load(
    "geotarget_archive_exact_outer_champion_v2_poc_preloaded",
    HISTORICAL_WORKER,
)
CHAMPION = HISTORICAL.CHAMPION
BASE = CHAMPION.BASE
ZERO = CHAMPION.ZERO
V1 = CHAMPION.V1

# exact_outer needs only these three lease attributes.  Deliberately do not
# call hp_lock_scheduler.adapter.install(): ordinary HP/reservoir scheduling
# must remain the archived PointOnCircle-repaired champion schedule.
adapter = SimpleNamespace(
    DEFAULT_POLICY=POLICY.DEFAULT_POLICY,
    LeaseUnavailable=POLICY.LeaseUnavailable,
    per_core_lease=POLICY.per_core_lease,
)
RESOURCE_BUSY_STATUSES = frozenset(
    ("LOCK_BUSY_DEFERRED", "MEMORY_BUSY_DEFERRED")
)

_HISTORICAL_HP = BASE._run_hp_candidate
_HISTORICAL_PLAN = BASE._plan


def _plan(**kwargs) -> dict[str, object]:
    verify_dependencies()
    if BASE._run_hp_candidate is not _HISTORICAL_HP:
        # exact_outer replaces this callable after it captures _HISTORICAL_HP.
        # No other replacement is allowed before the outer is installed.
        installed = getattr(BASE, "_geotarget_exact_outer_installed", False)
        if not installed:
            raise IntegrationError("archived ordinary HP callable changed")
    plan = _HISTORICAL_PLAN(**kwargs)
    plan.update(
        {
            "archive_reopen_scheduler_shim": True,
            "archive_historical_worker_path": str(HISTORICAL_WORKER),
            "archive_historical_worker_sha256": _sha256(HISTORICAL_WORKER),
            "archive_dependency_sha256": verify_dependencies(),
            "ordinary_hp_callable_preserved_before_exact_outer_capture": True,
            "ordinary_hp_schedule_or_budget_changed_by_shim": False,
            "point_on_circle_periodic_semantic_repair_active": True,
            "zero_dimensional_source_exact_authority_preserved": True,
            "resource_runtime_role": "exact-child per-core lease only",
            "resource_runtime_installed_on_ordinary_hp": False,
            "case_family_truth_target_count_or_outcome_routing": False,
            "archive_scheduler_shim_sha256": _sha256(Path(__file__)),
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    verify_dependencies()
    HISTORICAL.main()


__all__ = [
    "BASE",
    "CHAMPION",
    "HISTORICAL",
    "RESOURCE_BUSY_STATUSES",
    "V1",
    "ZERO",
    "adapter",
    "main",
]


if __name__ == "__main__":
    main()
