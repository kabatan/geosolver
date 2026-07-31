#!/usr/bin/env python3
"""Add the Repair-B particle tail after one frozen progressive execution."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
BASE_SCHEDULER = HERE.parent / "archive_progressive_hybrid_exact_outer_v1/scheduler_shim.py"
PARTICLE_ROOT = HERE.parents[2] / "EXP-PARTICLE-CONSENSUS-001"
PARTICLE_TAIL = PARTICLE_ROOT / "tail_full_wrapper.py"

EXPECTED_SHA256 = {
    BASE_SCHEDULER: "b3b9df6062dc0aa603fc5da02ae2eefa0947721eafe9069bf545af75747350e0",
    PARTICLE_TAIL: "2e8902f81ccd677d62546a29e49244b481879bc4e9a4752149cd7e9541905a8b",
    PARTICLE_ROOT / "real_search_worker.py": "0f0f1983f2684caf043d51be8df3b70e0f502ea9ee6531b8c4d0e5ed8084ff61",
    PARTICLE_ROOT / "real_adapter.py": "e9e3600e1ba9830e70cbdad11886e3bca043f12c7d7c0441e23431bbdb2caaae",
    PARTICLE_ROOT / "candidate.py": "1d24ab131de635ef47c5f9f2230822f3d62a6d7b5787be95e26089d59c924a4e",
}


class IntegrationError(RuntimeError):
    """The frozen progressive, particle, or authority seam changed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_dependencies() -> dict[str, str]:
    observed = {
        str(path.resolve()): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_SHA256
    }
    expected = {str(path.resolve()): digest for path, digest in EXPECTED_SHA256.items()}
    if observed != expected:
        raise IntegrationError("progressive/particle dependency closure changed")
    return observed


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


_verify_dependencies()
UPSTREAM = _load("geotarget_particle_tail_exact_upstream", BASE_SCHEDULER)
TAIL = _load("geotarget_particle_tail_exact_repair_b", PARTICLE_TAIL)
TAIL._verify_particle()

BASE = UPSTREAM.BASE
CONTROL = UPSTREAM.CONTROL
HISTORICAL = UPSTREAM.HISTORICAL
PROGRESSIVE = UPSTREAM.PROGRESSIVE
RESOURCE_BUSY_STATUSES = UPSTREAM.RESOURCE_BUSY_STATUSES
SEARCH_POLICY = UPSTREAM.SEARCH_POLICY
V1 = UPSTREAM.V1
ZERO = UPSTREAM.ZERO
adapter = UPSTREAM.adapter
_BASE_PLAN = BASE._plan


def _assert_binding() -> None:
    _verify_dependencies()
    UPSTREAM._assert_binding()
    TAIL._verify_particle()
    if BASE is not CONTROL.CHAMPION.BASE or HISTORICAL is not CONTROL:
        raise IntegrationError("particle tail would target a second control stack")
    if ZERO is not CONTROL.CHAMPION.ZERO:
        raise IntegrationError("zero-dimensional authority changed")


def _plan(**kwargs) -> dict[str, object]:
    _assert_binding()
    plan = _BASE_PLAN(**kwargs)
    plan.update(
        {
            "particle_repair_b": "post-authority-surplus-only-exact-confirmed-union",
            "particle_tail_callback_fraction_cap": 0.25,
            "particle_tail_wall_fraction_cap": 0.25,
            "baseline_budget_quota_minimum": 0.75,
            "baseline_runs_to_completion_before_particle_tail": True,
            "particle_mixed_ad_fd_policy": "fail-closed exact-prefix fallback",
            "particle_nonsmooth_unknown_selector_semantic_policy": (
                "fail-closed exact-prefix fallback"
            ),
            "particle_full_ad_or_smooth_all_fd_only": True,
            "particle_existing_charged_one_sided_fd_preserved": True,
            "particle_tail_all_authorities_require_exact_outer": True,
            "particle_baseline_descriptor_prefix_immutable": True,
            "particle_search_endpoint_union_or_recluster": False,
            "particle_zero_dimensional_route_changed": False,
            "particle_dependency_sha256": _verify_dependencies(),
            "case_family_truth_target_count_or_outcome_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def _zero_dimensional(source: Path) -> bool:
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        variables = document.get("variables") if isinstance(document, dict) else None
        names = variables.get("names") if isinstance(variables, dict) else None
        return isinstance(names, list) and len(names) == 0
    except (OSError, json.JSONDecodeError):
        return False


def _run_particle_tail(*, arguments, hard_deadline: float) -> None:
    """Apply callback/wall caps, then call the frozen Repair-B tail helper."""

    output = arguments.output.resolve()
    if _zero_dimensional(arguments.source):
        return
    used = TAIL._callbacks_used(output)
    if used is None:
        return
    total_cap = int(arguments.aggregate_callback_cap)
    remaining = max(0, total_cap - used)
    side_cap = min(remaining, total_cap // 4)
    if side_cap < TAIL.MIN_TAIL_CALLBACKS:
        return
    side_arguments = copy.copy(arguments)
    side_arguments.aggregate_callback_cap = used + side_cap
    side_deadline = min(
        hard_deadline,
        time.monotonic() + 0.25 * float(arguments.total_seconds),
    )
    TAIL._run_tail(
        base=BASE,
        arguments=side_arguments,
        output=output,
        hard_deadline=side_deadline,
    )


def main() -> None:
    _assert_binding()
    arguments = CONTROL.CHAMPION.ORIGINAL_V2._parser().parse_args()
    hard_deadline = BASE.PROCESS_STARTED + float(arguments.total_seconds)
    HISTORICAL.main()
    if not arguments.execute:
        return
    try:
        _run_particle_tail(arguments=arguments, hard_deadline=hard_deadline)
    except Exception:
        # RESULT.json already contains the immutable proof-bearing baseline.
        return


__all__ = [
    "BASE",
    "CONTROL",
    "HISTORICAL",
    "PROGRESSIVE",
    "RESOURCE_BUSY_STATUSES",
    "SEARCH_POLICY",
    "TAIL",
    "V1",
    "ZERO",
    "adapter",
    "main",
]


if __name__ == "__main__":
    main()
