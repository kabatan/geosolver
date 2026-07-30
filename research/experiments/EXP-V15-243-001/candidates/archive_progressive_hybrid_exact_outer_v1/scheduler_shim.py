#!/usr/bin/env python3
"""Bind the frozen progressive search seam before exact_outer captures HP."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
CAMPAIGN_CANDIDATES = HERE.parent
PROGRESSIVE_ROOT = CAMPAIGN_CANDIDATES / "progressive_adaptive_hybrid_v1"
PROGRESSIVE_WRAPPER = PROGRESSIVE_ROOT / "full_wrapper.py"
PROGRESSIVE_ENTRY = PROGRESSIVE_ROOT / "full_worker.py"
SEARCH_WORKER = PROGRESSIVE_ROOT / "search_worker.py"
SEARCH_ADAPTER = PROGRESSIVE_ROOT / "search_adapter.py"
SEARCH_CANDIDATE = PROGRESSIVE_ROOT / "candidate.py"
ARCHIVE_ROOT = Path(
    os.environ.get(
        "GEOTARGET_ARCHIVE_EXACT_OUTER_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
RESOURCE_POLICY = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "hp_lock_scheduler/policy.py"
)
CONTAINED_LIFECYCLE = (
    CAMPAIGN_CANDIDATES
    / "archive_champion_v2_poc_exact_outer_v1/contained_lifecycle.py"
)

EXPECTED_DEPENDENCY_SHA256 = {
    PROGRESSIVE_WRAPPER: (
        "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"
    ),
    PROGRESSIVE_ENTRY: (
        "7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500"
    ),
    SEARCH_WORKER: (
        "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6"
    ),
    SEARCH_ADAPTER: (
        "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea"
    ),
    SEARCH_CANDIDATE: (
        "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972"
    ),
    RESOURCE_POLICY: (
        "c32ed095643c7154742bc94743fbe69e83e77cddd6d5b9f8a00e4b38b5c16121"
    ),
}


class IntegrationError(RuntimeError):
    """The frozen progressive/common-control composition changed."""


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
        raise IntegrationError("frozen progressive/exact resource closure changed")
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
PROGRESSIVE = _load(
    "geotarget_archive_progressive_exact_outer_binding",
    PROGRESSIVE_WRAPPER,
)
POLICY = _load(
    "geotarget_archive_progressive_exact_outer_resource_policy",
    RESOURCE_POLICY,
)
LIFECYCLE = _load(
    "geotarget_archive_progressive_contained_lifecycle",
    CONTAINED_LIFECYCLE,
)
SEARCH_POLICY = _load(
    "geotarget_archive_progressive_exact_outer_search_policy",
    SEARCH_CANDIDATE,
)

# Load the exact historical champion-v2 + POC + precision-preload stack once,
# capture its authority objects, and make configure() rebind that same object.
CONTROL = PROGRESSIVE._load_control(ARCHIVE_ROOT)
PROGRESSIVE._verify_control_stack(CONTROL)
BASE = CONTROL.CHAMPION.BASE
ZERO = CONTROL.CHAMPION.ZERO
V1 = CONTROL.CHAMPION.V1
LIFECYCLE.install(BASE)
_HISTORICAL_HP = BASE._run_hp_candidate
_HISTORICAL_PLAN = BASE._plan
_HISTORICAL_AUTHORITY = {
    name: getattr(BASE, name)
    for name in (
        "HP_BRIDGE",
        "PRECISION_RUNTIME",
        "RESTORATION_WORKER",
        "RESTORATION_ADAPTER",
        "RESTORATION_CANDIDATE",
        "_authority_descriptor",
        "_descriptor_key",
        "_fresh_replay_candidates",
        "_run_hp_candidate",
        "_run_restoration_candidate",
        "_service_candidates",
    )
}
_load_control = PROGRESSIVE._load_control
PROGRESSIVE._load_control = lambda _root: CONTROL
try:
    HISTORICAL = PROGRESSIVE.configure(
        frozen_root=ARCHIVE_ROOT,
        enable_hybrid=True,
    )
finally:
    PROGRESSIVE._load_control = _load_control

if HISTORICAL is not CONTROL or BASE is not HISTORICAL.CHAMPION.BASE:
    raise IntegrationError("progressive scheduler loaded a second control stack")
for _name, _value in _HISTORICAL_AUTHORITY.items():
    if getattr(BASE, _name) is not _value:
        raise IntegrationError(f"progressive search rebind changed authority: {_name}")
if BASE.SEARCH_WORKER != SEARCH_WORKER:
    raise IntegrationError("progressive search worker is not active")
if BASE.SEARCH_ADAPTER != SEARCH_ADAPTER:
    raise IntegrationError("progressive search adapter is not active")
if BASE.SEARCH_CANDIDATE != SEARCH_CANDIDATE:
    raise IntegrationError("progressive search policy is not active")
if BASE.SEARCH_ARM != PROGRESSIVE.SEARCH_ARM:
    raise IntegrationError("progressive search arm is not active")

SEARCH_POLICY_MANIFEST = SEARCH_POLICY.configuration_manifest()
if SEARCH_POLICY_MANIFEST["original_order_baseline_handoff_fraction"] != 0.25:
    raise IntegrationError("ordinary baseline handoff quota changed")
if SEARCH_POLICY_MANIFEST["counter_cauchy_handoff_fraction"] != 0.25:
    raise IntegrationError("counter-Cauchy insurance quota changed")

# exact_outer requires only this resource API for its exact child. Installing
# hp_lock_scheduler.adapter on BASE would alter the historical ordinary HP
# schedule, so the shim deliberately exposes the reviewed lease without doing
# so.
adapter = SimpleNamespace(
    DEFAULT_POLICY=POLICY.DEFAULT_POLICY,
    LeaseUnavailable=POLICY.LeaseUnavailable,
    per_core_lease=POLICY.per_core_lease,
)
RESOURCE_BUSY_STATUSES = frozenset(
    ("LOCK_BUSY_DEFERRED", "MEMORY_BUSY_DEFERRED")
)


def _assert_binding() -> None:
    verify_dependencies()
    if HISTORICAL is not CONTROL or BASE is not CONTROL.CHAMPION.BASE:
        raise IntegrationError("historical progressive control identity changed")
    if ZERO is not CONTROL.CHAMPION.ZERO:
        raise IntegrationError("zero-dimensional source authority changed")
    if BASE.SEARCH_WORKER != SEARCH_WORKER:
        raise IntegrationError("progressive search worker changed")
    if BASE.SEARCH_ADAPTER != SEARCH_ADAPTER:
        raise IntegrationError("progressive search adapter changed")
    if BASE.SEARCH_CANDIDATE != SEARCH_CANDIDATE:
        raise IntegrationError("progressive search policy changed")
    if BASE.SEARCH_ARM != PROGRESSIVE.SEARCH_ARM:
        raise IntegrationError("progressive search arm changed")
    if BASE._run_hp_candidate is not _HISTORICAL_HP:
        installed = getattr(BASE, "_geotarget_exact_outer_installed", False)
        if not installed:
            raise IntegrationError("historical POC HP callable changed")
    for name, value in _HISTORICAL_AUTHORITY.items():
        if name == "_run_hp_candidate" and getattr(
            BASE, "_geotarget_exact_outer_installed", False
        ):
            continue
        if getattr(BASE, name) is not value:
            raise IntegrationError(f"authority object changed: {name}")


def _plan(**kwargs) -> dict[str, object]:
    _assert_binding()
    plan = _HISTORICAL_PLAN(**kwargs)
    plan.update(
        {
            "archive_progressive_exact_scheduler_shim": True,
            "progressive_search_arm": PROGRESSIVE.SEARCH_ARM,
            "progressive_search_worker_sha256": _sha256(SEARCH_WORKER),
            "progressive_search_adapter_sha256": _sha256(SEARCH_ADAPTER),
            "progressive_search_candidate_sha256": _sha256(SEARCH_CANDIDATE),
            "progressive_search_policy": SEARCH_POLICY_MANIFEST,
            "ordinary_original_order_baseline_handoff_fraction": 0.25,
            "counter_cauchy_insurance_handoff_fraction": 0.25,
            "ordinary_baseline_quota_permanently_retained": True,
            "historical_poc_hp_callable_preserved_before_outer_capture": True,
            "historical_hp_reservoir_or_budget_changed_by_shim": False,
            "zero_dimensional_source_exact_authority_preserved": True,
            "resource_runtime_role": "exact-child per-core lease only",
            "resource_runtime_installed_on_ordinary_hp": False,
            "historical_child_lifecycle": LIFECYCLE.manifest(),
            "progressive_exact_dependency_sha256": verify_dependencies(),
            "archive_progressive_scheduler_shim_sha256": _sha256(Path(__file__)),
            "case_family_truth_target_count_or_outcome_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    _assert_binding()
    LIFECYCLE.arm_formal_root()
    HISTORICAL.main()


__all__ = [
    "BASE",
    "CONTROL",
    "HISTORICAL",
    "PROGRESSIVE",
    "RESOURCE_BUSY_STATUSES",
    "SEARCH_POLICY",
    "V1",
    "ZERO",
    "adapter",
    "main",
]


if __name__ == "__main__":
    main()
