#!/usr/bin/env python3
"""Bind the current formal scheduler, replacing only its search prefix seam."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
SCHEDULER_WORKER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "hp_scheduler_preserve_binding/worker.py"
)
SEARCH_WORKER = HERE / "search_worker.py"
SEARCH_ADAPTER = HERE / "search_adapter.py"
SEARCH_CANDIDATE = SEARCH_ADAPTER
SEARCH_ARM = "bounded_periodic_exact_prejoin_25pct_v1"
EXPECTED_SCHEDULER_SHA256 = (
    "5453a30c46d3050c0520a6492f149595bf93d4f2794e3e1fa86d7d60c2365702"
)


class IntegrationError(RuntimeError):
    pass


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


if not SCHEDULER_WORKER.is_file() or _sha256(SCHEDULER_WORKER) != EXPECTED_SCHEDULER_SHA256:
    raise IntegrationError("formal control scheduler changed")

CONTROL = _load("geotarget_bounded_prejoin_formal_scheduler", SCHEDULER_WORKER)
BASE = CONTROL.BASE
_AUTHORITY_OBJECTS = {
    name: getattr(BASE, name)
    for name in (
        "HP_BRIDGE",
        "_run_hp_candidate",
        "_run_restoration_candidate",
        "_service_candidates",
    )
}
_CONTROL_PLAN = BASE._plan

# The only algorithm mutation in this candidate.
BASE.SEARCH_WORKER = SEARCH_WORKER
BASE.SEARCH_ADAPTER = SEARCH_ADAPTER
BASE.SEARCH_CANDIDATE = SEARCH_CANDIDATE
BASE.SEARCH_ARM = SEARCH_ARM

# exact_outer asks its selected scheduler module for this resource-only API.
adapter = CONTROL.SCHEDULER.adapter
RESOURCE_BUSY_STATUSES = CONTROL.SCHEDULER.RESOURCE_BUSY_STATUSES


def _assert_binding() -> None:
    if _sha256(SCHEDULER_WORKER) != EXPECTED_SCHEDULER_SHA256:
        raise IntegrationError("formal scheduler digest changed after load")
    if BASE.SEARCH_WORKER != SEARCH_WORKER:
        raise IntegrationError("candidate search worker is not active")
    if BASE.SEARCH_ADAPTER != SEARCH_ADAPTER:
        raise IntegrationError("candidate search adapter is not active")
    if BASE.SEARCH_CANDIDATE != SEARCH_CANDIDATE or BASE.SEARCH_ARM != SEARCH_ARM:
        raise IntegrationError("candidate search identity changed")
    for name, value in _AUTHORITY_OBJECTS.items():
        if name == "_run_hp_candidate" and getattr(BASE, "_geotarget_exact_outer_installed", False):
            continue
        if getattr(BASE, name) is not value:
            raise IntegrationError(f"non-search authority seam changed: {name}")


def _plan(**kwargs) -> dict[str, object]:
    _assert_binding()
    plan = _CONTROL_PLAN(**kwargs)
    plan.update(
        {
            "bounded_periodic_exact_prejoin_v1": True,
            "formal_scheduler_sha256": EXPECTED_SCHEDULER_SHA256,
            "search_worker_sha256": _sha256(SEARCH_WORKER),
            "search_adapter_sha256": _sha256(SEARCH_ADAPTER),
            "search_arm": SEARCH_ARM,
            "side_route_fraction_upper_bound": 0.25,
            "baseline_fraction_lower_bound": 0.75,
            "ordinary_hp_and_exact_authority_changed": False,
            "truth_case_family_target_count_outcome_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    _assert_binding()
    CONTROL.main()


if __name__ == "__main__":
    main()
