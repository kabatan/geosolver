#!/usr/bin/env python3
"""Run the safe v15 dataset harness with the HP scheduler parent contract."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import threading
import time
from typing import Mapping, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_RUNNER = (
    ROOT
    / "research/experiments/EXP-OMC-G-PART01-V15-EVAL-001/"
    "run_dataset.py"
)
WORKER = HERE / "worker.py"
ROOT_SCOPED_SUBPROCESS = HERE / "root_scoped_subprocess.py"
EXPECTED_PARENT_PID_ENV = "GEOTARGET_EXPECTED_WORKER_PARENT_PID"
FORMAL_CASE_DEADLINE_ENV = "GEOTARGET_FORMAL_CASE_DEADLINE_MONOTONIC"
POST_COMPLETION_QUIET_SECONDS = 2.5

_CASE_DEADLINES: dict[tuple[str, str], tuple[float, float]] = {}
_CASE_DEADLINES_LOCK = threading.Lock()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from policy import (  # noqa: E402
    DEFAULT_POLICY,
    GLOBAL_RESERVATION_ENV,
    MAX_JOBS_ENV,
    RESERVATION_TOKEN_ENV,
)
import root_scoped_subprocess  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_snapshot(root: Path) -> dict[str, dict[str, object]]:
    if not root.exists():
        return {}
    snapshot: dict[str, dict[str, object]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        snapshot[str(path.relative_to(root))] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": _sha256(path),
        }
    return snapshot


def _matching_case_processes(output: Path) -> list[dict[str, object]]:
    output_text = str(output.resolve())
    matches: list[dict[str, object]] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (
                (entry / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode("utf-8", errors="replace")
            )
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if output_text in command:
            matches.append({"pid": int(entry.name), "command": command})
    return sorted(matches, key=lambda row: int(row["pid"]))


def _post_completion_audit(output: Path) -> dict[str, object]:
    before = _artifact_snapshot(output)
    processes_before = _matching_case_processes(output)
    time.sleep(POST_COMPLETION_QUIET_SECONDS)
    after = _artifact_snapshot(output)
    processes_after = _matching_case_processes(output)
    changed = sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )
    return {
        "schema_version": "geotarget.full-worker-lifecycle-audit/v1",
        "quiet_seconds": POST_COMPLETION_QUIET_SECONDS,
        "case_output": str(output.resolve()),
        "late_artifact_paths": changed,
        "late_artifact_count": len(changed),
        "matching_processes_before_quiet": processes_before,
        "matching_processes_after_quiet": processes_after,
        "pass": not changed and not processes_before and not processes_after,
    }


def _command_value(command: Sequence[str], flag: str) -> str | None:
    converted = [str(part) for part in command]
    try:
        index = converted.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(converted):
        raise RuntimeError(f"missing value after {flag}")
    return converted[index + 1]


def _formal_case_identity(
    command: Sequence[str],
) -> tuple[tuple[str, str], float, bool] | None:
    source_sha256 = _command_value(command, "--source-sha256")
    output = _command_value(command, "--output")
    raw_total = _command_value(command, "--total-seconds")
    if source_sha256 is None and output is None and raw_total is None:
        return None
    if source_sha256 is None or output is None or raw_total is None:
        raise RuntimeError("incomplete formal case command contract")
    try:
        total_seconds = float(raw_total)
        int(source_sha256, 16)
    except ValueError as error:
        raise RuntimeError("invalid formal case command contract") from error
    if (
        len(source_sha256) != 64
        or not math.isfinite(total_seconds)
        or not 0.0 < total_seconds <= 180.0
    ):
        raise RuntimeError("invalid formal case command contract")
    identity = (source_sha256, str(Path(output).resolve()))
    return identity, total_seconds, any(
        str(part) == "--execute" for part in command
    )


def _case_deadline(
    command: Sequence[str],
) -> tuple[float | None, bool, tuple[str, str] | None]:
    contract = _formal_case_identity(command)
    if contract is None:
        return None, False, None
    identity, total_seconds, execute = contract
    now = time.monotonic()
    with _CASE_DEADLINES_LOCK:
        expired = [
            key
            for key, (deadline, _total) in _CASE_DEADLINES.items()
            if deadline <= now
        ]
        for key in expired:
            _CASE_DEADLINES.pop(key, None)
        if execute:
            frozen = _CASE_DEADLINES.pop(identity, None)
            if frozen is None:
                raise RuntimeError(
                    "formal execute has no matching dry-run deadline"
                )
            deadline, frozen_total = frozen
            if not math.isclose(
                frozen_total,
                total_seconds,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise RuntimeError("formal dry/execute budget mismatch")
            return deadline, True, identity
        if identity in _CASE_DEADLINES:
            raise RuntimeError("duplicate formal dry-run identity")
        deadline = now + total_seconds
        _CASE_DEADLINES[identity] = (deadline, total_seconds)
        return deadline, False, identity


def _formal_case_guard(
    command: Sequence[str],
    *,
    limits,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    status_path: Path | None = None,
):
    deadline, execute, identity = _case_deadline(command)
    child_environment = dict(environment or {})
    if deadline is not None:
        child_environment[FORMAL_CASE_DEADLINE_ENV] = str(deadline)
    try:
        result = root_scoped_subprocess.run_guarded(
            command,
            limits=limits,
            process_group_rss_bytes=(
                DEFAULT_POLICY.formal_process_group_rss_bytes
            ),
            absolute_deadline_monotonic=deadline,
            environment=child_environment,
            cwd=cwd,
            status_path=status_path,
        )
    except BaseException:
        if identity is not None and not execute:
            with _CASE_DEADLINES_LOCK:
                _CASE_DEADLINES.pop(identity, None)
        raise
    if identity is not None and not execute and not result.accepted_output:
        with _CASE_DEADLINES_LOCK:
            _CASE_DEADLINES.pop(identity, None)
    if identity is not None and execute and status_path is not None:
        audit = _post_completion_audit(Path(identity[1]))
        audit_path = status_path.with_name(
            f"{status_path.stem}-lifecycle-audit.json"
        )
        root_scoped_subprocess.safe.atomic_write_json(audit_path, audit)
        if audit["pass"] is not True:
            result = replace(
                result,
                classification="LIFECYCLE_AUDIT_FAILED",
                accepted_output=False,
                descendant_leak=True,
                stderr_tail=(
                    result.stderr_tail
                    + "\npost-completion lifecycle audit failed"
                ).strip(),
            )
            root_scoped_subprocess.safe.atomic_write_json(
                status_path,
                result.to_dict(),
            )
    return result


def _load_runner():
    name = "geotarget_exp_v15_243_hp_lock_scheduler_dataset_runner"
    specification = importlib.util.spec_from_file_location(name, BASE_RUNNER)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_RUNNER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def configure_runner(runner) -> None:
    with _CASE_DEADLINES_LOCK:
        _CASE_DEADLINES.clear()
    runner.WORKER = WORKER
    runner.MAX_JOBS = DEFAULT_POLICY.max_jobs
    runner.run_guarded = _formal_case_guard
    runner.THREAD_ENVIRONMENT = {
        **runner.THREAD_ENVIRONMENT,
        EXPECTED_PARENT_PID_ENV: str(os.getpid()),
        MAX_JOBS_ENV: str(DEFAULT_POLICY.max_jobs),
        GLOBAL_RESERVATION_ENV: str(
            DEFAULT_POLICY.global_reservation_bytes
        ),
        RESERVATION_TOKEN_ENV: str(
            DEFAULT_POLICY.reservation_token_bytes
        ),
    }


def main() -> None:
    runner = _load_runner()
    configure_runner(runner)
    runner.main()


if __name__ == "__main__":
    main()
