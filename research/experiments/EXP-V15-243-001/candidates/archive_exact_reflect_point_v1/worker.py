#!/usr/bin/env python3
"""Archive exact-only arm with one QPoint/QPoint reflection replay opcode."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ARCHIVE_WORKER = HERE.parent / "archive_champion_v2_poc_exact_outer_v1/worker.py"
PRIVATE_CANDIDATE = HERE / "private_candidate.py"
PRIVATE_FALLBACK = HERE / "private_fallback_worker.py"
CONTAINED_LIFECYCLE = HERE / "contained_lifecycle.py"
SITECUSTOMIZE = HERE / "sitecustomize.py"
EXPECTED_ARCHIVE_WORKER_SHA256 = (
    "4c128a0e83e0cfbe959a97d4673f8e0f6a1e39ad4c336c2f31625fc6b0e4b715"
)
EXPECTED_PRIVATE_CANDIDATE_SHA256 = (
    "8c9f5b656db49344b1514b4cfcc293479d016218c05d307a6b5c108adf706fc4"
)
EXPECTED_PRIVATE_FALLBACK_SHA256 = (
    "dfefce57bebe685728cb86770519730f187f378e460ccaff9469ba189b2998d2"
)
EXPECTED_CONTAINED_LIFECYCLE_SHA256 = (
    "9fa8e50d6f030cf6c673eed4e065d24c8937cea655163789dee8fe9b48eae862"
)
EXPECTED_SITECUSTOMIZE_SHA256 = (
    "de3cc49c1fbb525072992af657a3823c05da1774dfefb9e5b7cafdceb7d3aca7"
)


class IntegrationError(RuntimeError):
    """The frozen archive or private exact shim changed."""


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


def _verify_private_files() -> dict[str, str]:
    observed = {
        str(ARCHIVE_WORKER): _sha256(ARCHIVE_WORKER),
        str(PRIVATE_CANDIDATE): _sha256(PRIVATE_CANDIDATE),
        str(PRIVATE_FALLBACK): _sha256(PRIVATE_FALLBACK),
        str(CONTAINED_LIFECYCLE): _sha256(CONTAINED_LIFECYCLE),
        str(SITECUSTOMIZE): _sha256(SITECUSTOMIZE),
    }
    expected = {
        str(ARCHIVE_WORKER): EXPECTED_ARCHIVE_WORKER_SHA256,
        str(PRIVATE_CANDIDATE): EXPECTED_PRIVATE_CANDIDATE_SHA256,
        str(PRIVATE_FALLBACK): EXPECTED_PRIVATE_FALLBACK_SHA256,
        str(CONTAINED_LIFECYCLE): EXPECTED_CONTAINED_LIFECYCLE_SHA256,
        str(SITECUSTOMIZE): EXPECTED_SITECUSTOMIZE_SHA256,
    }
    if observed != expected:
        raise IntegrationError("archive/private reflect dependency changed")
    return observed


_verify_private_files()
ARCHIVE = _load("geotarget_archive_exact_reflect_point_archive", ARCHIVE_WORKER)
LIFECYCLE = _load(
    "geotarget_archive_exact_reflect_point_contained_lifecycle",
    CONTAINED_LIFECYCLE,
)
OUTER = ARCHIVE.OUTER
BASE = ARCHIVE.BASE
SCHEDULER = ARCHIVE.SCHEDULER
ZERO = ARCHIVE.ZERO
V1 = ARCHIVE.V1
LIFECYCLE.install(BASE)

# Candidate-private substitution only.  The original decorator consults these
# globals dynamically for child launch, hash closure, and freeze verification.
OUTER.EXACT_CANDIDATE = PRIVATE_CANDIDATE
OUTER.EXACT_WORKER = PRIVATE_FALLBACK
OUTER.EXPECTED_EXACT_SHA256 = {
    PRIVATE_CANDIDATE: EXPECTED_PRIVATE_CANDIDATE_SHA256,
    PRIVATE_FALLBACK: EXPECTED_PRIVATE_FALLBACK_SHA256,
    OUTER.EXACT_REFINER: OUTER.EXPECTED_EXACT_SHA256[OUTER.EXACT_REFINER],
    OUTER.EXACT_AUDIT: OUTER.EXPECTED_EXACT_SHA256[OUTER.EXACT_AUDIT],
    OUTER.EXACT_DAG: OUTER.EXPECTED_EXACT_SHA256[OUTER.EXACT_DAG],
    OUTER.EXACT_QQBAR: OUTER.EXPECTED_EXACT_SHA256[OUTER.EXACT_QQBAR],
}
OUTER.verify_exact_freeze()

_ARCHIVE_PLAN = BASE._plan
_ARCHIVE_ZERO_PLAN = SCHEDULER.HISTORICAL.CHAMPION.ORIGINAL_V2._plan


def _assert_binding() -> None:
    _verify_private_files()
    ARCHIVE._assert_runtime_binding()
    OUTER.verify_exact_freeze()
    if OUTER.MODE != OUTER.CONFIRM_ALL_AUTHORITIES:
        raise IntegrationError("exact confirmation is not global")
    if BASE._run_hp_candidate is not OUTER._run_exact_outer:
        raise IntegrationError("private arm bypassed the exact outer boundary")
    if OUTER.EXACT_CANDIDATE != PRIVATE_CANDIDATE:
        raise IntegrationError("private exact candidate binding changed")
    if OUTER.EXACT_WORKER != PRIVATE_FALLBACK:
        raise IntegrationError("private fallback binding changed")
    if BASE.run_guarded is not LIFECYCLE.contained_run_guarded:
        raise IntegrationError("candidate-private child containment changed")


def _reflect_ledger() -> dict[str, object]:
    return {
        "exact_reflect_point_opcode": "qreflect(::QPoint, ::QPoint)",
        "exact_reflect_point_semantics": "2*center-point",
        "exact_reflect_point_argument_order": ["reflected_point", "center_point"],
        "exact_reflect_point_branch_or_guard_added": False,
        "exact_reflect_point_wrong_types_fail_closed": True,
        "exact_reflect_point_other_exact_authority_changed": False,
        "historical_search_and_hp_children_same_group_contained": True,
        "historical_child_lifecycle": LIFECYCLE.manifest(),
        "exact_reflect_point_private_file_sha256": _verify_private_files(),
        "case_family_truth_target_count_or_outcome_routing": False,
    }


def _plan(**kwargs) -> dict[str, object]:
    _assert_binding()
    plan = _ARCHIVE_PLAN(**kwargs)
    plan.update(_reflect_ledger())
    return plan


def _zero_plan(**kwargs) -> dict[str, object]:
    _assert_binding()
    plan = _ARCHIVE_ZERO_PLAN(**kwargs)
    plan.update(_reflect_ledger())
    plan["exact_reflect_point_invoked_for_zero_dimensional_route"] = False
    return plan


BASE._plan = _plan
SCHEDULER.HISTORICAL.CHAMPION.ORIGINAL_V2._plan = _zero_plan


def main() -> None:
    _assert_binding()
    LIFECYCLE.arm_formal_root()
    ARCHIVE.main()


__all__ = ["ARCHIVE", "BASE", "OUTER", "SCHEDULER", "V1", "ZERO", "main"]


if __name__ == "__main__":
    main()
