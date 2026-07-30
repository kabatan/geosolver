#!/usr/bin/env python3
"""Progressive historical arm with exact confirmation of every HP authority."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SCHEDULER_SHIM = HERE / "scheduler_shim.py"
OUTER_MODE_ENV = "GEOTARGET_EXACT_OUTER_MODE"
OUTER_SCHEDULER_ENV = "GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER"
CONFIRM_ALL_AUTHORITIES = "CONFIRM_ALL_AUTHORITIES"
ARCHIVE_ROOT = Path(
    os.environ.get(
        "GEOTARGET_ARCHIVE_EXACT_OUTER_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
EXACT_OUTER = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "exact_outer_decorator/worker.py"
)
AUTHORITY_BOUNDARY = EXACT_OUTER.parent / "authority_boundary.py"
EXPECTED_EXACT_OUTER_SHA256 = (
    "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"
)
EXPECTED_AUTHORITY_BOUNDARY_SHA256 = (
    "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9"
)


class IntegrationError(RuntimeError):
    """The progressive/exact composition no longer matches its contract."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_global_setting(name: str, required: str, *, path: bool = False) -> None:
    observed = os.environ.get(name)
    matches = (
        Path(observed).resolve() == Path(required).resolve()
        if path and observed is not None
        else observed == required
    )
    if observed is not None and not matches:
        raise IntegrationError(f"conflicting global setting: {name}")
    os.environ[name] = required


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


if _sha256(EXACT_OUTER) != EXPECTED_EXACT_OUTER_SHA256:
    raise IntegrationError("exact_outer worker digest changed")
if _sha256(AUTHORITY_BOUNDARY) != EXPECTED_AUTHORITY_BOUNDARY_SHA256:
    raise IntegrationError("exact_outer authority boundary digest changed")
_require_global_setting(
    OUTER_SCHEDULER_ENV,
    str(SCHEDULER_SHIM.resolve()),
    path=True,
)
_require_global_setting(OUTER_MODE_ENV, CONFIRM_ALL_AUTHORITIES)

OUTER = _load("geotarget_archive_progressive_hybrid_exact_outer", EXACT_OUTER)
SCHEDULER = OUTER.SCHEDULER_MODULE
BASE = OUTER.BASE
ZERO = SCHEDULER.ZERO
V1 = SCHEDULER.V1

_OUTER_PLAN = BASE._plan
_ZERO_PLAN = SCHEDULER.CONTROL.CHAMPION.ORIGINAL_V2._plan


def _assert_runtime_binding() -> None:
    if OUTER.MODE != CONFIRM_ALL_AUTHORITIES:
        raise IntegrationError("exact_outer mode changed after import")
    if OUTER.ORDINARY_HP_CAPTURE_COUNT != 1:
        raise IntegrationError("ordinary HP capture count changed")
    if OUTER._ORDINARY_HP is not SCHEDULER._HISTORICAL_HP:
        raise IntegrationError("exact_outer did not capture historical POC HP")
    if BASE._run_hp_candidate is not OUTER._run_exact_outer:
        raise IntegrationError("exact_outer is not the installed authority boundary")
    if BASE.SEARCH_ARM != SCHEDULER.PROGRESSIVE.SEARCH_ARM:
        raise IntegrationError("progressive search scheduler is not active")
    if ZERO is not SCHEDULER.CONTROL.CHAMPION.ZERO:
        raise IntegrationError("zero-dimensional source authority changed")
    SCHEDULER._assert_binding()
    if _sha256(EXACT_OUTER) != EXPECTED_EXACT_OUTER_SHA256:
        raise IntegrationError("exact_outer worker changed after import")
    if _sha256(AUTHORITY_BOUNDARY) != EXPECTED_AUTHORITY_BOUNDARY_SHA256:
        raise IntegrationError("authority boundary changed after import")


def _integration_ledger() -> dict[str, object]:
    return {
        "archive_progressive_exact_candidate_worker_sha256": _sha256(
            Path(__file__)
        ),
        "archive_progressive_exact_scheduler_shim_sha256": _sha256(
            SCHEDULER_SHIM
        ),
        "archive_progressive_exact_outer_sha256": _sha256(EXACT_OUTER),
        "archive_progressive_authority_boundary_sha256": _sha256(
            AUTHORITY_BOUNDARY
        ),
        "progressive_search_arm": SCHEDULER.PROGRESSIVE.SEARCH_ARM,
        "ordinary_original_order_baseline_handoff_fraction": 0.25,
        "ordinary_baseline_quota_permanently_retained": True,
        "historical_poc_hp_captured_by_exact_outer": True,
        "ordinary_authority_policy": (
            "proposal-only until matching exact source/guard/branch replay"
        ),
        "positive_dimensional_ordinary_authority_can_bypass_exact_outer": False,
        "zero_dimensional_route_uses_existing_source_exact_authority": True,
        "historical_search_and_hp_children_same_group_contained": True,
        "historical_child_lifecycle": SCHEDULER.LIFECYCLE.manifest(),
        "case_family_truth_target_count_or_outcome_routing": False,
    }


def _plan(**kwargs) -> dict[str, object]:
    _assert_runtime_binding()
    plan = _OUTER_PLAN(**kwargs)
    plan.update(_integration_ledger())
    return plan


def _zero_plan(**kwargs) -> dict[str, object]:
    _assert_runtime_binding()
    plan = _ZERO_PLAN(**kwargs)
    plan.update(_integration_ledger())
    plan.update(
        {
            "archive_progressive_execution_route": (
                "existing_source_exact_zero_dimensional_authority"
            ),
            "progressive_search_invoked_for_zero_dimensional_route": False,
            "exact_outer_invoked_for_zero_dimensional_route": False,
            "zero_dimensional_authority_logic_changed": False,
        }
    )
    return plan


BASE._plan = _plan
SCHEDULER.CONTROL.CHAMPION.ORIGINAL_V2._plan = _zero_plan


def main() -> None:
    _assert_runtime_binding()
    OUTER.main()


__all__ = ["BASE", "OUTER", "SCHEDULER", "V1", "ZERO", "main"]


if __name__ == "__main__":
    main()
