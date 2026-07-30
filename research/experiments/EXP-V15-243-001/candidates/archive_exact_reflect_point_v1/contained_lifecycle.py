"""Candidate-private same-group lifecycle for the archived champion.

The historical worker launches search/HP helpers with the generic detached
experiment guard.  A detached descendant is incompatible with the formal
root-scoped guard.  This module changes only process containment: commands,
limits, native-thread settings, numerical policies, and result acceptance are
left to the historical caller.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_ARCHIVE_EXACT_OUTER_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
HP_ROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/hp_lock_scheduler"
)
DEADLINE_GUARD = HP_ROOT / "deadline_guard.py"
PDEATH_EXEC = HP_ROOT / "pdeath_exec.py"
SAME_GROUP = (
    RUNTIME_ROOT
    / "research/infrastructure/memory_safety/same_group_subprocess.py"
)
FORMAL_DEADLINE_ENV = "GEOTARGET_FORMAL_CASE_DEADLINE_MONOTONIC"
EXPECTED_PARENT_ENV = "GEOTARGET_EXPECTED_WORKER_PARENT_PID"
ACTIVATION_ENV = "GEOTARGET_ARCHIVE_CONTAINED_CHILDREN"
EXPECTED_SHA256 = {
    DEADLINE_GUARD: "9d26a006bbfc6073221e6e4135ad92072d3151bc3a2c84d2d982d7672e9ca70f",
    PDEATH_EXEC: "36232592cd52b5a48142f311b8e28350afdd7f72c1e031193058ec46d33d1ffc",
    SAME_GROUP: "fda141f0608b09b3919d758ac56db79e8a14e6d63282a7c120d948879c3fe01e",
}


class LifecycleError(RuntimeError):
    """The reviewed containment closure or formal parent contract changed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(path.resolve()): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_SHA256
    }
    expected = {
        str(path.resolve()): digest for path, digest in EXPECTED_SHA256.items()
    }
    if observed != expected:
        raise LifecycleError("archived containment closure changed")
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
DEADLINE = _load("geotarget_archive_contained_deadline_guard", DEADLINE_GUARD)
PDEATH = _load("geotarget_archive_contained_pdeath_exec", PDEATH_EXEC)


def _formal_deadline() -> float | None:
    raw = os.environ.get(FORMAL_DEADLINE_ENV)
    if raw is None:
        return None
    try:
        deadline = float(raw)
    except ValueError as error:
        raise LifecycleError("invalid formal case deadline") from error
    if not math.isfinite(deadline):
        raise LifecycleError("invalid formal case deadline")
    return deadline


def contained_run_guarded(
    command,
    *,
    limits,
    environment=None,
    cwd=None,
    status_path=None,
):
    """Run one child in the inherited case group with exact-parent pdeath."""

    verify_dependencies()
    absolute_deadline = time.monotonic() + float(limits.timeout_seconds)
    formal_deadline = _formal_deadline()
    if formal_deadline is not None:
        absolute_deadline = min(absolute_deadline, formal_deadline)
    return DEADLINE.run_guarded_until(
        command,
        limits=limits,
        absolute_deadline=absolute_deadline,
        environment=environment,
        cwd=cwd,
        status_path=status_path,
        rss_scope="closure",
    )


def _child_python_path() -> str:
    existing = os.environ.get("PYTHONPATH", "")
    entries = [str(HERE), str(RUNTIME_ROOT)]
    entries.extend(item for item in existing.split(os.pathsep) if item)
    return os.pathsep.join(dict.fromkeys(entries))


def install(base) -> None:
    """Replace only the historical subprocess guard and child bootstrap."""

    verify_dependencies()
    if getattr(base, "_geotarget_archive_contained_children", False):
        if base.run_guarded is not contained_run_guarded:
            raise LifecycleError("archived contained guard was rebound")
        return
    base.run_guarded = contained_run_guarded
    base.THREAD_ENVIRONMENT.update(
        {
            ACTIVATION_ENV: "1",
            "PYTHONPATH": _child_python_path(),
        }
    )
    base._geotarget_archive_contained_children = True


def arm_formal_root() -> None:
    """Arm pdeath without changing the inherited formal pgrp/session."""

    verify_dependencies()
    raw = os.environ.get(EXPECTED_PARENT_ENV)
    if raw is None:
        return
    try:
        expected_parent = int(raw)
    except ValueError as error:
        raise LifecycleError("invalid formal worker parent pid") from error
    if expected_parent <= 1:
        raise LifecycleError("invalid formal worker parent pid")
    before = (os.getpgrp(), os.getsid(0))
    PDEATH.arm_parent_death_signal(expected_parent)
    after = (os.getpgrp(), os.getsid(0))
    if before != after:
        raise LifecycleError("worker root changed process group or session")


def manifest() -> dict[str, object]:
    return {
        "schema_version": "geotarget.archive-contained-lifecycle/v1",
        "root_calls_setsid_or_setpgrp": False,
        "children_share_formal_process_group": True,
        "children_use_exact_parent_death_sigkill": True,
        "formal_absolute_deadline_preserved": True,
        "numerical_algorithm_or_budget_changed": False,
        "dependencies": verify_dependencies(),
        "candidate_lifecycle_sha256": _sha256(Path(__file__)),
    }
