#!/usr/bin/env python3
"""Drop-in HP bridge with a bounded per-physical-core lease.

The numerical/exact authority remains the frozen endpoint bridge and champion
composition worker.  Only the resource lease is changed: unrelated pinned
cores no longer share one blocking repository-wide mutex.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FROZEN_BRIDGE = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hp_endpoint_bridge_v10/run_one_endpoint.py"
)
COMPOSITION_WORKER = (
    ROOT
    / "research/experiments/EXP-V15-243-001/"
    "champion_v0/hp_composition_worker.py"
)
SAFE_SUBPROCESS = (
    ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"
)
SAME_GROUP_SUBPROCESS = (
    ROOT
    / "research/infrastructure/memory_safety/same_group_subprocess.py"
)
PDEATH_EXEC = HERE / "pdeath_exec.py"
DEADLINE_GUARD = HERE / "deadline_guard.py"

EXPECTED_FROZEN_BRIDGE_SHA256 = (
    "760fb5e018026df644aadd56a1078f3a9d54332c581dc98502a56b4284afbc27"
)
EXPECTED_COMPOSITION_WORKER_SHA256 = (
    "b8c3b03d2e13da829f9333f1d1285b08b5537c07532c294b383226188d939ef5"
)
EXPECTED_SAFE_SUBPROCESS_SHA256 = (
    "8bc185c35726a38aabe480d57a3928ed6067393454b64aa90eaa5f87aff30d4a"
)
EXPECTED_SAME_GROUP_SUBPROCESS_SHA256 = (
    "fda141f0608b09b3919d758ac56db79e8a14e6d63282a7c120d948879c3fe01e"
)

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy import (  # noqa: E402
    core_lock_path,
    lease_wait_budget,
    per_core_lease,
)
from deadline_guard import (  # noqa: E402
    MINIMUM_CHILD_SECONDS,
    run_guarded_until,
)


NESTED_FINALIZATION_RESERVE_SECONDS = 2.25
NESTED_TEARDOWN_RESERVE_SECONDS = 0.75
NESTED_TOTAL_RESERVE_SECONDS = (
    NESTED_FINALIZATION_RESERVE_SECONDS
    + NESTED_TEARDOWN_RESERVE_SECONDS
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_execution_chain() -> dict[str, str]:
    expected = {
        "frozen_bridge": (FROZEN_BRIDGE, EXPECTED_FROZEN_BRIDGE_SHA256),
        "composition_worker": (
            COMPOSITION_WORKER,
            EXPECTED_COMPOSITION_WORKER_SHA256,
        ),
        "safe_subprocess": (
            SAFE_SUBPROCESS,
            EXPECTED_SAFE_SUBPROCESS_SHA256,
        ),
        "same_group_subprocess": (
            SAME_GROUP_SUBPROCESS,
            EXPECTED_SAME_GROUP_SUBPROCESS_SHA256,
        ),
    }
    observed: dict[str, str] = {}
    for label, (path, digest) in expected.items():
        if not path.is_file():
            raise RuntimeError(f"missing execution-chain file: {label}")
        observed[label] = _sha256(path)
        if observed[label] != digest:
            raise RuntimeError(
                f"execution-chain digest changed for {label}: "
                f"expected {digest}, observed {observed[label]}"
            )
    if not PDEATH_EXEC.is_file():
        raise RuntimeError("missing parent-death containment launcher")
    observed["pdeath_exec"] = _sha256(PDEATH_EXEC)
    if not DEADLINE_GUARD.is_file():
        raise RuntimeError("missing one-deadline guard adapter")
    observed["deadline_guard"] = _sha256(DEADLINE_GUARD)
    return observed


def _argument(name: str, conversion):
    try:
        index = sys.argv.index(name)
        raw = sys.argv[index + 1]
    except (ValueError, IndexError) as error:
        raise SystemExit(f"missing required bridge argument: {name}") from error
    try:
        return conversion(raw)
    except ValueError as error:
        raise SystemExit(f"invalid bridge argument: {name}") from error


def _pop_argument(name: str, conversion):
    try:
        index = sys.argv.index(name)
        raw = sys.argv[index + 1]
    except (ValueError, IndexError) as error:
        raise SystemExit(f"missing required bridge argument: {name}") from error
    del sys.argv[index : index + 2]
    try:
        return conversion(raw)
    except ValueError as error:
        raise SystemExit(f"invalid bridge argument: {name}") from error


def _load_bridge():
    name = "geotarget_exp_v15_243_hp_per_core_bridge_base"
    specification = importlib.util.spec_from_file_location(name, FROZEN_BRIDGE)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_BRIDGE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    _check_execution_chain()
    absolute_deadline = _pop_argument(
        "--absolute-deadline-monotonic",
        float,
    )
    cpu = _argument("--cpu", int)
    deadline_seconds = _argument("--deadline-seconds", float)
    process_timeout_seconds = _argument("--process-timeout-seconds", float)
    wait_seconds = lease_wait_budget(
        deadline_seconds=deadline_seconds,
        process_timeout_seconds=process_timeout_seconds,
    )
    if (
        not math.isfinite(absolute_deadline)
        or absolute_deadline <= time.monotonic()
    ):
        raise SystemExit("absolute HP deadline must be a future finite time")
    wait_seconds = min(
        wait_seconds,
        max(
            0.0,
            absolute_deadline
            - time.monotonic()
            - NESTED_TOTAL_RESERVE_SECONDS
            - MINIMUM_CHILD_SECONDS,
        ),
    )
    affinity = os.sched_getaffinity(0)
    if affinity != {cpu}:
        raise SystemExit(
            "bridge CPU argument does not match one-core process affinity: "
            f"cpu={cpu}, affinity={sorted(affinity)}"
        )
    lock_path = core_lock_path(cpu)
    bridge = _load_bridge()
    bridge.WORKER = COMPOSITION_WORKER
    bridge.GLOBAL_HP_LOCK = lock_path

    @contextmanager
    def _bounded_per_core_job():
        with per_core_lease(cpu, wait_seconds=wait_seconds):
            yield

    def _deadline_aware_run_guarded(
        command,
        *,
        limits,
        environment=None,
        cwd=None,
        status_path=None,
    ):
        """Share one root deadline and process group with the outer worker."""

        return run_guarded_until(
            command,
            limits=limits,
            absolute_deadline=absolute_deadline,
            environment=environment,
            cwd=cwd,
            status_path=status_path,
            finalization_reserve_seconds=(
                NESTED_FINALIZATION_RESERVE_SECONDS
            ),
            teardown_reserve_seconds=NESTED_TEARDOWN_RESERVE_SECONDS,
            rss_scope="closure",
        )

    bridge._exclusive_hp_job = _bounded_per_core_job
    bridge.run_guarded = _deadline_aware_run_guarded
    bridge.main()


if __name__ == "__main__":
    main()
