#!/usr/bin/env python3.12
"""Current exact_outer over the 25% guard-billiard search overlay."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get("GEOTARGET_EXPERIMENT_RUNTIME", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
EXACT_OUTER = RUNTIME_ROOT / "research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/worker.py"
AUTHORITY_BOUNDARY = EXACT_OUTER.parent / "authority_boundary.py"
SCHEDULER_SHIM = HERE / "scheduler_shim.py"
EXPECTED = {
    EXACT_OUTER: "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7",
    AUTHORITY_BOUNDARY: "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setting(name: str, required: str, *, path: bool = False) -> None:
    observed = os.environ.get(name)
    matches = Path(observed).resolve() == Path(required).resolve() if path and observed else observed == required
    if observed is not None and not matches:
        raise RuntimeError(f"conflicting global setting: {name}")
    os.environ[name] = required


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


for _path, _expected in EXPECTED.items():
    if not _path.is_file() or _sha(_path) != _expected:
        raise RuntimeError(f"current exact authority dependency changed: {_path}")
_setting("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", str(SCHEDULER_SHIM.resolve()), path=True)
_setting("GEOTARGET_EXACT_OUTER_MODE", "CONFIRM_ALL_AUTHORITIES")
OUTER = _load("geotarget_guard_billiard_current_exact_outer", EXACT_OUTER)
SCHEDULER = OUTER.SCHEDULER_MODULE
BASE = OUTER.BASE


def _assert_binding() -> None:
    if OUTER.ORDINARY_HP_CAPTURE_COUNT != 1:
        raise RuntimeError("ordinary HP capture count changed")
    if OUTER._ORDINARY_HP is not SCHEDULER._AUTHORITY_OBJECTS["_run_hp_candidate"]:
        raise RuntimeError("exact_outer did not capture formal-control ordinary HP")
    if BASE._run_hp_candidate is not OUTER._run_exact_outer:
        raise RuntimeError("current exact_outer is not installed")
    if BASE.SEARCH_ARM != SCHEDULER.SEARCH_ARM:
        raise RuntimeError("guard-billiard search arm is not active")
    SCHEDULER._assert_binding()


_OUTER_PLAN = BASE._plan


def _plan(**kwargs):
    _assert_binding()
    plan = _OUTER_PLAN(**kwargs)
    plan.update(
        {
            "guard_billiard_exact_terminal_worker_sha256": _sha(Path(__file__)),
            "exact_outer_sha256": EXPECTED[EXACT_OUTER],
            "authority_boundary_sha256": EXPECTED[AUTHORITY_BOUNDARY],
            "approximate_guard_or_endpoint_is_authority": False,
            "truth_case_family_target_count_outcome_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    _assert_binding()
    OUTER.main()


if __name__ == "__main__":
    main()
