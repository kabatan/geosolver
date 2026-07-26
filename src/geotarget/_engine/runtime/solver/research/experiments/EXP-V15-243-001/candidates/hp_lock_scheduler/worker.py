#!/usr/bin/env python3
"""Candidate-private champion wrapper for HP resource scheduling."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DEFAULT_CHAMPION_WORKER = (
    ROOT
    / "research/experiments/EXP-V15-243-001/champion_v0/worker.py"
)
CHAMPION_WORKER_ENV = "GEOTARGET_HP_CHAMPION_WORKER"
CHAMPION_WORKER = Path(
    os.environ.get(CHAMPION_WORKER_ENV, str(DEFAULT_CHAMPION_WORKER))
).resolve()
BRIDGE = HERE / "bridge.py"
ADAPTER = HERE / "adapter.py"
POLICY = HERE / "policy.py"
PDEATH_EXEC = HERE / "pdeath_exec.py"
DEADLINE_GUARD = HERE / "deadline_guard.py"
ROOT_SCOPED_SUBPROCESS = HERE / "root_scoped_subprocess.py"
SAME_GROUP_SUBPROCESS = (
    ROOT
    / "research/infrastructure/memory_safety/same_group_subprocess.py"
)
SAFE_SUBPROCESS = (
    ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"
)
LIMIT_EXEC = ROOT / "research/infrastructure/memory_safety/_limit_exec.py"
CANDIDATE_DATASET_RUNNER = HERE / "run_dataset.py"
EXPECTED_PARENT_PID_ENV = "GEOTARGET_EXPECTED_WORKER_PARENT_PID"
FORMAL_CASE_DEADLINE_ENV = "GEOTARGET_FORMAL_CASE_DEADLINE_MONOTONIC"
POST_COMPLETION_QUIET_SECONDS = 2.5

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import adapter  # noqa: E402
import deadline_guard  # noqa: E402
from pdeath_exec import arm_parent_death_signal  # noqa: E402
from policy import DEFAULT_POLICY  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _execution_chain() -> dict[str, str]:
    paths = {
        "candidate_worker": Path(__file__),
        "candidate_adapter": ADAPTER,
        "candidate_bridge": BRIDGE,
        "candidate_policy": POLICY,
        "candidate_pdeath_exec": PDEATH_EXEC,
        "candidate_deadline_guard": DEADLINE_GUARD,
        "candidate_root_scoped_subprocess": ROOT_SCOPED_SUBPROCESS,
        "same_group_subprocess": SAME_GROUP_SUBPROCESS,
        "safe_subprocess": SAFE_SUBPROCESS,
        "limit_exec": LIMIT_EXEC,
        "candidate_dataset_runner": CANDIDATE_DATASET_RUNNER,
        "champion_worker": CHAMPION_WORKER,
    }
    observed: dict[str, str] = {}
    for label, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f"missing execution-chain file: {label}")
        observed[label] = _sha256(path)
    return observed


def _load_champion():
    name = "geotarget_exp_v15_243_hp_lock_scheduler_champion"
    specification = importlib.util.spec_from_file_location(
        name, CHAMPION_WORKER
    )
    if specification is None or specification.loader is None:
        raise ImportError(CHAMPION_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CHAMPION = _load_champion()

# The frozen base worker carries its historical 8 GiB reservation in the
# explicit child environment.  A scheduler profile selected by the parent
# process must propagate the same resource-only values to bridge/restoration
# children; otherwise a 16-case profile validates in the parent and then the
# child re-imports policy with contradictory 7-job/8-GiB defaults.
CHAMPION.BASE.THREAD_ENVIRONMENT.update(
    {
        "GEOTARGET_HP_MAX_JOBS": str(DEFAULT_POLICY.max_jobs),
        "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(
            DEFAULT_POLICY.global_reservation_bytes
        ),
        "GEOTARGET_MEMORY_RESERVATION_TOKEN_BYTES": str(
            DEFAULT_POLICY.reservation_token_bytes
        ),
    }
)


def _formal_case_deadline() -> float | None:
    raw = os.environ.get(FORMAL_CASE_DEADLINE_ENV)
    if raw is None:
        return None
    try:
        deadline = float(raw)
    except ValueError as error:
        raise SystemExit(f"invalid {FORMAL_CASE_DEADLINE_ENV}") from error
    if not math.isfinite(deadline):
        raise SystemExit(f"invalid {FORMAL_CASE_DEADLINE_ENV}")
    return deadline


def _argument_float(flag: str, default: float) -> float:
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return float(default)
    if index + 1 >= len(sys.argv):
        raise SystemExit(f"missing value after {flag}")
    try:
        value = float(sys.argv[index + 1])
    except ValueError as error:
        raise SystemExit(f"invalid {flag}") from error
    if not math.isfinite(value):
        raise SystemExit(f"invalid {flag}")
    return value


def _contained_search_guard(
    command,
    *,
    limits,
    environment=None,
    cwd=None,
    status_path=None,
):
    """Keep the search lane in the formal case process group.

    Search owns one closure-wide 768 MiB reservation.  The outer formal guard
    separately owns only the worker-root 256 MiB reservation.
    """

    now = time.monotonic()
    absolute_deadline = now + float(limits.timeout_seconds)
    formal_deadline = _formal_case_deadline()
    if formal_deadline is not None:
        absolute_deadline = min(absolute_deadline, formal_deadline)
    return deadline_guard.run_guarded_until(
        command,
        limits=limits,
        absolute_deadline=absolute_deadline,
        environment=environment,
        cwd=cwd,
        status_path=status_path,
        rss_scope="closure",
    )


CHAMPION.BASE.run_guarded = _contained_search_guard
adapter.install(CHAMPION.BASE, bridge=BRIDGE)
_ORIGINAL_PLAN = CHAMPION.BASE._plan
_ORIGINAL_SERVICE_CANDIDATES = CHAMPION.BASE._service_candidates
RESOURCE_BUSY_STATUSES = frozenset(
    ("LOCK_BUSY_DEFERRED", "MEMORY_BUSY_DEFERRED")
)


def _plan(**kwargs):
    plan = _ORIGINAL_PLAN(**kwargs)
    formal_deadline = _formal_case_deadline()
    child_resource_environment = {
        "GEOTARGET_HP_MAX_JOBS": str(DEFAULT_POLICY.max_jobs),
        "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(
            DEFAULT_POLICY.global_reservation_bytes
        ),
        "GEOTARGET_MEMORY_RESERVATION_TOKEN_BYTES": str(
            DEFAULT_POLICY.reservation_token_bytes
        ),
    }
    observed_child_environment = {
        name: CHAMPION.BASE.THREAD_ENVIRONMENT.get(name)
        for name in child_resource_environment
    }
    if observed_child_environment != child_resource_environment:
        raise RuntimeError(
            "HP child resource environment differs from scheduler policy"
        )
    plan.update(
        {
            "schema_version": (
                "geotarget.exp-v15-243-hp-lock-scheduler-plan/v1"
            ),
            "hp_resource_scheduler": (
                "per-pinned-physical-core short-wait lease plus existing "
                "aggregate RSS token reservation"
            ),
            "hp_cross_core_global_mutex": False,
            "hp_late_timeout_artifact_salvage": False,
            "hp_single_absolute_attempt_deadline": True,
            "hp_memory_admission_and_child_timeout_additive": False,
            "hp_outer_process_group_detached": False,
            "hp_parent_death_chain": (
                "formal runner -> worker -> bridge/restoration -> nested HP"
            ),
            "hp_formal_parent_pid_environment_contract": (
                EXPECTED_PARENT_PID_ENV
            ),
            "formal_case_absolute_deadline_environment_contract": (
                FORMAL_CASE_DEADLINE_ENV
            ),
            "formal_case_absolute_deadline_monotonic": formal_deadline,
            "formal_case_budget_origin_monotonic": (
                formal_deadline - float(kwargs["total_seconds"])
                if formal_deadline is not None
                else None
            ),
            "hp_execute_requires_formal_parent_pid_contract": True,
            "hp_execute_requires_formal_case_deadline_contract": True,
            "hp_outer_wrapper_rss_scope": "direct root only",
            "formal_worker_root_rss_bytes": (
                DEFAULT_POLICY.top_level_rss_bytes
            ),
            "formal_case_process_group_rss_bytes": (
                DEFAULT_POLICY.formal_process_group_rss_bytes
            ),
            "formal_case_process_group_cap_disabled": False,
            "formal_case_root_and_group_caps_separate": True,
            "formal_case_aggregate_reservation_scope": (
                "root token plus independently reserved nested lane tokens"
            ),
            "formal_search_child_rss_scope": "complete descendant closure",
            "formal_search_child_process_group_detached": False,
            "formal_restoration_child_rss_scope": (
                "complete descendant closure"
            ),
            "formal_case_memory_admission_and_execution_share_deadline": (
                True
            ),
            "formal_case_post_completion_lifecycle_audit": True,
            "formal_case_post_completion_quiet_seconds": (
                POST_COMPLETION_QUIET_SECONDS
            ),
            "hp_nested_child_rss_scope": "complete descendant closure",
            "hp_restoration_flock_foreground_exec": True,
            "hp_bridge_wrapper_rss_bytes": (
                DEFAULT_POLICY.bridge_rss_bytes
            ),
            "hp_resource_policy": DEFAULT_POLICY.to_dict(),
            "hp_child_resource_environment": child_resource_environment,
            "hp_child_resource_environment_matches_parent_policy": True,
            "hp_resource_execution_chain_sha256": _execution_chain(),
            "candidate_integrated_worker_sha256": _sha256(Path(__file__)),
        }
    )
    return plan


CHAMPION.BASE._plan = _plan


def _resource_busy_candidates(candidates, attempts):
    successful = {
        str(attempt.get("endpoint_float64_sha256"))
        for attempt in attempts
        if attempt.get("authority_pass") is True
    }
    required = Counter(
        str(attempt.get("endpoint_float64_sha256"))
        for attempt in attempts
        if attempt.get("status") in RESOURCE_BUSY_STATUSES
        and str(attempt.get("endpoint_float64_sha256")) not in successful
    )
    selected = []
    for candidate in candidates:
        digest = candidate.endpoint_sha256
        if required[digest] > 0:
            selected.append(candidate)
            required[digest] -= 1
    return tuple(selected)


def _service_candidates(
    *,
    source,
    source_sha256,
    candidates,
    cpu,
    output,
    hard_deadline,
):
    """Requeue resource-busy endpoints without calling them numerical failures."""

    attempts, descriptors, statistics = _ORIGINAL_SERVICE_CANDIDATES(
        source=source,
        source_sha256=source_sha256,
        candidates=candidates,
        cpu=cpu,
        output=output,
        hard_deadline=hard_deadline,
    )
    all_attempts = list(attempts)
    all_descriptors = dict(descriptors)
    rounds: list[dict[str, object]] = []
    pending = _resource_busy_candidates(candidates, attempts)
    for round_ordinal in range(2):
        remaining = (
            hard_deadline
            - time.monotonic()
            - CHAMPION.BASE.FINALIZE_RESERVE_SECONDS
        )
        if not pending or remaining < CHAMPION.BASE.MIN_HP_ATTEMPT_SECONDS:
            break
        time.sleep(min(0.05, max(0.0, remaining - 0.1)))
        retry_attempts, retry_descriptors, retry_statistics = (
            _ORIGINAL_SERVICE_CANDIDATES(
                source=source,
                source_sha256=source_sha256,
                candidates=pending,
                cpu=cpu,
                output=output
                / f"resource-requeue-{round_ordinal + 1:03d}",
                hard_deadline=hard_deadline,
            )
        )
        all_attempts.extend(retry_attempts)
        for key, descriptor in retry_descriptors.items():
            all_descriptors.setdefault(key, descriptor)
        rounds.append(
            {
                "round": round_ordinal + 1,
                "input_count": len(pending),
                "statistics": dict(retry_statistics),
            }
        )
        pending = _resource_busy_candidates(pending, retry_attempts)
    merged_statistics = dict(statistics)
    merged_statistics.update(
        {
            "resource_busy_statuses": sorted(RESOURCE_BUSY_STATUSES),
            "resource_busy_attempt_count": sum(
                attempt.get("status") in RESOURCE_BUSY_STATUSES
                for attempt in all_attempts
            ),
            "resource_requeue_round_count": len(rounds),
            "resource_requeue_rounds": rounds,
            "resource_busy_unresolved_count": len(pending),
            "resource_busy_unresolved_endpoint_sha256": [
                candidate.endpoint_sha256 for candidate in pending
            ],
            "resource_busy_is_numerical_failure": False,
        }
    )
    return all_attempts, all_descriptors, merged_statistics


CHAMPION.BASE._service_candidates = _service_candidates


def _arm_formal_parent_contract() -> None:
    execute = "--execute" in sys.argv
    raw = os.environ.get(EXPECTED_PARENT_PID_ENV)
    if raw is None:
        if execute:
            raise SystemExit(
                f"execute requires {EXPECTED_PARENT_PID_ENV}"
            )
    else:
        try:
            expected_parent_pid = int(raw)
        except ValueError as error:
            raise SystemExit(
                f"invalid {EXPECTED_PARENT_PID_ENV}"
            ) from error
        if expected_parent_pid <= 1:
            raise SystemExit(f"invalid {EXPECTED_PARENT_PID_ENV}")
        try:
            arm_parent_death_signal(expected_parent_pid)
        except RuntimeError as error:
            raise SystemExit(str(error)) from error

    deadline = _formal_case_deadline()
    if deadline is None:
        if execute:
            raise SystemExit(
                f"execute requires {FORMAL_CASE_DEADLINE_ENV}"
            )
        return
    total_seconds = _argument_float(
        "--total-seconds",
        CHAMPION.BASE.DEFAULT_TOTAL_SECONDS,
    )
    now = time.monotonic()
    process_started = deadline - total_seconds
    if (
        not 0.0 < total_seconds <= 180.0
        or process_started > now + 0.05
        or deadline > now + total_seconds + 0.05
        or (execute and deadline <= now)
    ):
        raise SystemExit("invalid or exhausted formal case deadline")
    # The frozen worker derives every downstream deadline and its reported
    # elapsed time from PROCESS_STARTED.  Rebase that clock to the runner's
    # dry-run admission instant without changing any command or PLAN field.
    CHAMPION.BASE.PROCESS_STARTED = process_started


def main() -> None:
    _arm_formal_parent_contract()
    _execution_chain()
    CHAMPION.main()


if __name__ == "__main__":
    main()
