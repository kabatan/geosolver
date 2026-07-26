"""Candidate-private adapter to the reviewed same-process-group guard.

The detached experiment guard gives memory admission and child execution
separate relative timeouts.  HP work instead receives one monotonic parent
deadline.  This adapter preserves the formal case process group, adds
parent-death SIGKILL as defense in depth, and maps the existing v15 limit
object onto the reviewed absolute-deadline guard.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import math
import os
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

from research.infrastructure.memory_safety import (
    same_group_subprocess as same_group,
)


HERE = Path(__file__).resolve().parent
PDEATH_EXEC = HERE / "pdeath_exec.py"
MINIMUM_CHILD_SECONDS = 0.05
DEFAULT_FINALIZATION_RESERVE_SECONDS = 0.75
DEFAULT_TEARDOWN_RESERVE_SECONDS = 0.75
DEFAULT_CLEANUP_RESERVE_SECONDS = (
    DEFAULT_FINALIZATION_RESERVE_SECONDS
    + DEFAULT_TEARDOWN_RESERVE_SECONDS
)


@contextmanager
def _root_only_rss_accounting():
    """Keep containment closure-wide while charging RSS to the lane root.

    The outer 128 MiB bridge wrapper must not re-reserve or re-charge the
    nested 480 MiB HP child; that child has its own closure-wide guard and
    reservation.  The same-group tracker still observes and tears down every
    descendant.
    """

    guardian_pid = os.getpid()
    original = same_group._read_process_table  # noqa: SLF001

    def root_only_table():
        table = original()
        if table is None:
            return None
        return {
            pid: replace(
                process,
                rss_bytes=(
                    process.rss_bytes
                    if process.ppid == guardian_pid
                    else 0
                ),
            )
            for pid, process in table.items()
        }

    same_group._read_process_table = root_only_table  # noqa: SLF001
    try:
        yield
    finally:
        same_group._read_process_table = original  # noqa: SLF001


def contained_command(
    command: Sequence[str],
    *,
    parent_pid: int | None = None,
) -> list[str]:
    """Wrap one same-group child in exact-parent death containment."""

    parent_pid = os.getpid() if parent_pid is None else int(parent_pid)
    return [
        sys.executable,
        str(PDEATH_EXEC),
        "--parent-pid",
        str(parent_pid),
        "--",
        *[str(part) for part in command],
    ]


def run_guarded_until(
    command: Sequence[str],
    *,
    limits,
    absolute_deadline: float,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    status_path: Path | None = None,
    finalization_reserve_seconds: float = (
        DEFAULT_FINALIZATION_RESERVE_SECONDS
    ),
    teardown_reserve_seconds: float = DEFAULT_TEARDOWN_RESERVE_SECONDS,
    contain_parent: bool = True,
    rss_scope: str = "root",
):
    """Run one child tree under a single absolute deadline."""

    limits.validate()
    if rss_scope not in {"root", "closure"}:
        raise ValueError("rss_scope must be 'root' or 'closure'")
    wrapped = contained_command(command) if contain_parent else [
        str(part) for part in command
    ]
    converted = same_group.Limits(
        lane_cap_seconds=float(limits.timeout_seconds),
        finalization_reserve_seconds=finalization_reserve_seconds,
        teardown_reserve_seconds=teardown_reserve_seconds,
        rss_bytes=int(limits.rss_bytes),
        address_space_bytes=int(limits.address_space_bytes),
        data_bytes=int(limits.data_bytes),
        output_bytes=int(limits.output_bytes),
        tail_bytes=int(limits.tail_bytes),
        poll_seconds=max(0.002, min(1.0, float(limits.poll_seconds))),
        terminate_grace_seconds=min(
            0.25,
            float(limits.terminate_grace_seconds),
        ),
    )
    started = time.monotonic()
    if not math.isfinite(absolute_deadline):
        raise ValueError("absolute_deadline must be finite")
    if absolute_deadline <= started:
        result = same_group._empty_result(  # noqa: SLF001
            classification="DEADLINE_EXHAUSTED",
            command=wrapped,
            started=started,
            child_timeout_seconds=0.0,
            caller_process_group=os.getpgrp(),
            caller_session=os.getsid(0),
            parent_deadline=absolute_deadline,
            limits=converted,
        )
        if status_path is not None:
            same_group.SAFE.atomic_write_json(status_path, result.to_dict())
        return result
    if rss_scope == "closure":
        return same_group.run_guarded_until(
            wrapped,
            parent_deadline_monotonic=absolute_deadline,
            limits=converted,
            environment=environment,
            cwd=cwd,
            status_path=status_path,
        )
    with _root_only_rss_accounting():
        return same_group.run_guarded_until(
            wrapped,
            parent_deadline_monotonic=absolute_deadline,
            limits=converted,
            environment=environment,
            cwd=cwd,
            status_path=status_path,
        )
