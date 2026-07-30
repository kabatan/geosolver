"""Outer-deadline policy shared by the v2 wrapper and slow-replay probes."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Mapping, Sequence

import psutil


HARD_FINISH_MARGIN_SECONDS = 1.50
INITIAL_PHASE_RESERVE_SECONDS = 3.00
CHILD_FINALIZE_RESERVE_SECONDS = 0.20
MIN_CHILD_ALLOWANCE_SECONDS = 0.75
TERMINATION_GRACE_SECONDS = 0.15


@dataclass(frozen=True)
class InternalBudget:
    total_seconds: float
    search_seconds: float


@dataclass(frozen=True)
class BoundedProcessResult:
    classification: str
    returncode: int | None
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str

    @property
    def accepted(self) -> bool:
        return self.classification == "COMPLETED" and self.returncode == 0


def internal_budget(outer_total_seconds: float, requested_search_seconds: float) -> InternalBudget:
    """Reserve wall time before the frozen phase starts, never after it overruns."""

    total = float(outer_total_seconds) - INITIAL_PHASE_RESERVE_SECONDS
    # Champion-v0 widens the frozen reserves to selection=3, finalize=3,
    # minimum HP attempt=3.  They are deducted before the dry plan so execute
    # never discovers an invalid integrated budget after custody is frozen.
    search = min(float(requested_search_seconds), total - 9.0)
    if total <= 10.0 or search <= 0.0:
        raise ValueError("outer budget is too small for the frozen v15 contract")
    return InternalBudget(total, search)


def continuation_seconds(*, latest_finish: float, now: float) -> float:
    return max(0.0, latest_finish - now - CHILD_FINALIZE_RESERVE_SECONDS)


def run_bounded_process(
    command: Sequence[str],
    *,
    latest_finish: float,
    environment: Mapping[str, str],
    cwd: Path,
) -> BoundedProcessResult:
    """Run one process group, killing it at the pre-reserved outer boundary."""

    started = time.monotonic()
    allowance = latest_finish - started
    if allowance < MIN_CHILD_ALLOWANCE_SECONDS:
        return BoundedProcessResult(
            "NOT_STARTED_NO_MARGIN", None, 0.0, "", ""
        )
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=max(0.01, allowance))
        classification = "COMPLETED" if process.returncode == 0 else "NONZERO_EXIT"
    except subprocess.TimeoutExpired:
        descendants = _signal_process_tree(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _signal_process_tree(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        for descendant in descendants:
            with suppress(psutil.Error):
                if descendant.is_running():
                    descendant.kill()
        classification = "HARD_DEADLINE_TERMINATED"
    return BoundedProcessResult(
        classification,
        process.returncode,
        time.monotonic() - started,
        (stdout or "")[-2000:],
        (stderr or "")[-2000:],
    )


def _signal_process_tree(
    pid: int, requested_signal: signal.Signals
) -> list[psutil.Process]:
    try:
        root = psutil.Process(pid)
        descendants = root.children(recursive=True)
    except psutil.Error:
        descendants = []
    for process in reversed(descendants):
        with suppress(psutil.Error):
            process.send_signal(requested_signal)
    with suppress(ProcessLookupError):
        os.killpg(pid, requested_signal)
    return descendants
