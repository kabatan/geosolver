"""Detached case guard with separate root and process-group RSS caps.

The formal v15 worker is the root of one process group.  Its HP children have
their own closure-wide guards and memory reservations, so charging them again
to the worker's 256 MiB cap is incorrect.  This guard keeps that cap on the
root process, retains an independent cap for the complete process group, and
continues to reserve the root allowance in the shared host-wide token pool.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Mapping, Sequence

from research.infrastructure.memory_safety import safe_subprocess as safe


SCHEMA = "geotarget.root-scoped-subprocess/v1"
LIMIT_LAUNCHER = Path(safe.__file__).with_name("_limit_exec.py")


@dataclass(frozen=True)
class _Process:
    pid: int
    state: str
    ppid: int
    process_group: int
    session: int
    start_ticks: int
    rss_bytes: int


@dataclass(frozen=True)
class RunResult:
    schema_version: str
    classification: str
    accepted_output: bool
    command: list[str]
    returncode: int | None
    elapsed_seconds: float
    absolute_deadline_monotonic: float
    peak_root_rss_bytes: int
    peak_process_group_rss_bytes: int
    root_rss_cap_bytes: int
    process_group_rss_cap_bytes: int
    memory_reservation_bytes: int
    memory_reservation_scope: str
    timeout: bool
    root_rss_cap_exceeded: bool
    process_group_rss_cap_exceeded: bool
    rss_cap_exceeded: bool
    rss_monitor_failed: bool
    output_cap_exceeded: bool
    containment_breach: bool
    descendant_leak: bool
    tracked_descendant_count: int
    root_process_group: int | None
    root_session: int | None
    resource_limit_failure_possible: bool
    stdout_bytes: int
    stderr_bytes: int
    stdout_tail: str
    stderr_tail: str
    limits: dict[str, int | float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_process_table() -> dict[int, _Process] | None:
    page_size = os.sysconf("SC_PAGE_SIZE")
    result: dict[int, _Process] = {}
    try:
        entries = os.scandir("/proc")
    except OSError:
        return None
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                raw = Path(entry.path, "stat").read_text(encoding="ascii")
                fields = raw[raw.rfind(")") + 2 :].split()
                statm = Path(entry.path, "statm").read_text(
                    encoding="ascii"
                ).split()
                if len(fields) < 20 or len(statm) < 2:
                    continue
                pid = int(entry.name)
                result[pid] = _Process(
                    pid=pid,
                    state=fields[0],
                    ppid=int(fields[1]),
                    process_group=int(fields[2]),
                    session=int(fields[3]),
                    start_ticks=int(fields[19]),
                    rss_bytes=int(statm[1]) * page_size,
                )
            except (
                FileNotFoundError,
                PermissionError,
                OSError,
                ValueError,
                IndexError,
            ):
                continue
    return result


def _descendants(root_pid: int, table: Mapping[int, _Process]) -> set[int]:
    result: set[int] = set()
    frontier = {root_pid}
    while frontier:
        next_frontier = {
            process.pid
            for process in table.values()
            if process.ppid in frontier and process.pid not in result
        }
        result.update(next_frontier)
        frontier = next_frontier
    return result


def _signal_identity(
    pid: int,
    start_ticks: int,
    signal_number: int,
) -> None:
    table = _read_process_table() or {}
    process = table.get(pid)
    if process is None or process.start_ticks != start_ticks:
        return
    try:
        os.kill(pid, signal_number)
    except ProcessLookupError:
        pass


def _terminate(
    process: subprocess.Popen[bytes],
    tracked: Mapping[int, int],
    grace_seconds: float,
) -> None:
    for pid, start_ticks in tracked.items():
        if pid != process.pid:
            _signal_identity(pid, start_ticks, signal.SIGTERM)
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        process.poll()
        table = _read_process_table() or {}
        live = {
            pid
            for pid, start_ticks in tracked.items()
            if (candidate := table.get(pid)) is not None
            and candidate.start_ticks == start_ticks
            and candidate.state != "Z"
        }
        if not live and not safe._process_group_exists(process.pid):  # noqa: SLF001
            break
        time.sleep(0.005)
    for pid, start_ticks in tracked.items():
        if pid != process.pid:
            _signal_identity(pid, start_ticks, signal.SIGKILL)
    if safe._process_group_exists(process.pid):  # noqa: SLF001
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1.0)


def _empty_result(
    *,
    classification: str,
    command: Sequence[str],
    limits: safe.Limits,
    group_rss_bytes: int,
    started: float,
    deadline: float,
    stderr_tail: str = "",
) -> RunResult:
    return RunResult(
        schema_version=SCHEMA,
        classification=classification,
        accepted_output=False,
        command=[str(part) for part in command],
        returncode=None,
        elapsed_seconds=time.monotonic() - started,
        absolute_deadline_monotonic=deadline,
        peak_root_rss_bytes=0,
        peak_process_group_rss_bytes=0,
        root_rss_cap_bytes=limits.rss_bytes,
        process_group_rss_cap_bytes=group_rss_bytes,
        memory_reservation_bytes=limits.rss_bytes,
        memory_reservation_scope="root process",
        timeout=False,
        root_rss_cap_exceeded=False,
        process_group_rss_cap_exceeded=False,
        rss_cap_exceeded=False,
        rss_monitor_failed=False,
        output_cap_exceeded=False,
        containment_breach=False,
        descendant_leak=False,
        tracked_descendant_count=0,
        root_process_group=None,
        root_session=None,
        resource_limit_failure_possible=False,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_tail="",
        stderr_tail=stderr_tail,
        limits=asdict(limits),
    )


def _run_admitted(
    command: Sequence[str],
    *,
    limits: safe.Limits,
    process_group_rss_bytes: int,
    absolute_deadline: float,
    started: float,
    environment: Mapping[str, str] | None,
    cwd: Path | None,
) -> RunResult:
    command = [str(part) for part in command]
    child_environment = dict(os.environ)
    if environment is not None:
        child_environment.update(
            {str(key): str(value) for key, value in environment.items()}
        )
    child_environment.update(safe.THREAD_ENV)
    wrapped = [
        sys.executable,
        str(LIMIT_LAUNCHER),
        "--as-bytes",
        str(limits.address_space_bytes),
        "--data-bytes",
        str(limits.data_bytes),
        "--",
        *command,
    ]
    try:
        process = subprocess.Popen(
            wrapped,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=cwd,
            env=child_environment,
            start_new_session=True,
        )
    except OSError as error:
        return _empty_result(
            classification="LAUNCH_ERROR",
            command=command,
            limits=limits,
            group_rss_bytes=process_group_rss_bytes,
            started=started,
            deadline=absolute_deadline,
            stderr_tail=str(error),
        )
    assert process.stdout is not None and process.stderr is not None
    stdout = safe._TailCollector(  # noqa: SLF001
        process.stdout,
        tail_bytes=limits.tail_bytes,
        output_bytes=limits.output_bytes,
    )
    stderr = safe._TailCollector(  # noqa: SLF001
        process.stderr,
        tail_bytes=limits.tail_bytes,
        output_bytes=limits.output_bytes,
    )
    stdout.start()
    stderr.start()
    root_start_ticks: int | None = None
    tracked: dict[int, int] = {}
    peak_root = 0
    peak_group = 0
    timeout = False
    root_exceeded = False
    group_exceeded = False
    monitor_failed = False
    output_exceeded = False
    containment_breach = False
    descendant_leak = False
    parent_completed = False
    root_session: int | None = None
    while True:
        now = time.monotonic()
        table = _read_process_table()
        if table is None:
            monitor_failed = True
            break
        root = table.get(process.pid)
        if root is not None:
            if root_start_ticks is None:
                root_start_ticks = root.start_ticks
                root_session = root.session
                tracked[root.pid] = root.start_ticks
            elif root.start_ticks != root_start_ticks:
                monitor_failed = True
                break
            peak_root = max(peak_root, root.rss_bytes)
            descendants = _descendants(process.pid, table)
            for pid in descendants:
                candidate = table.get(pid)
                if candidate is None or candidate.start_ticks < root_start_ticks:
                    continue
                tracked.setdefault(pid, candidate.start_ticks)
                if (
                    candidate.process_group != process.pid
                    or candidate.session != process.pid
                ):
                    containment_breach = True
            if root.process_group != process.pid or root.session != process.pid:
                containment_breach = True
        elif process.poll() is None:
            monitor_failed = True
            break
        group_members = [
            candidate
            for candidate in table.values()
            if candidate.process_group == process.pid
        ]
        if group_members:
            group_rss = sum(candidate.rss_bytes for candidate in group_members)
            peak_group = max(peak_group, group_rss)
            if any(candidate.session != process.pid for candidate in group_members):
                containment_breach = True
        elif process.poll() is None:
            monitor_failed = True
            break
        if peak_root > limits.rss_bytes:
            root_exceeded = True
            break
        if peak_group > process_group_rss_bytes:
            group_exceeded = True
            break
        if containment_breach:
            break
        if (
            stdout.cap_exceeded.is_set()
            or stderr.cap_exceeded.is_set()
            or stdout.total + stderr.total > limits.output_bytes
        ):
            output_exceeded = True
            break
        returncode = process.poll()
        if returncode is not None:
            parent_completed = True
            if now >= absolute_deadline:
                timeout = True
            live_descendants = [
                pid
                for pid, start_ticks in tracked.items()
                if pid != process.pid
                and (candidate := table.get(pid)) is not None
                and candidate.start_ticks == start_ticks
                and candidate.state != "Z"
            ]
            if live_descendants or any(
                candidate.pid != process.pid
                and candidate.state != "Z"
                for candidate in group_members
            ):
                descendant_leak = True
            break
        if now >= absolute_deadline:
            timeout = True
            break
        time.sleep(
            min(limits.poll_seconds, max(0.0, absolute_deadline - now))
        )

    must_cleanup = bool(
        timeout
        or root_exceeded
        or group_exceeded
        or monitor_failed
        or output_exceeded
        or containment_breach
        or descendant_leak
        or not parent_completed
    )
    if must_cleanup:
        _terminate(process, tracked, limits.terminate_grace_seconds)
    else:
        process.wait(timeout=1.0)
    stdout.join(timeout=0.25)
    stderr.join(timeout=0.25)
    if stdout.is_alive() or stderr.is_alive():
        descendant_leak = True
        _terminate(process, tracked, limits.terminate_grace_seconds)
        stdout.join(timeout=1.0)
        stderr.join(timeout=1.0)
    output_exceeded = bool(
        output_exceeded
        or stdout.cap_exceeded.is_set()
        or stderr.cap_exceeded.is_set()
        or stdout.total + stderr.total > limits.output_bytes
    )
    final_table = _read_process_table()
    if final_table is None:
        monitor_failed = True
    else:
        final_live = {
            pid
            for pid, start_ticks in tracked.items()
            if (candidate := final_table.get(pid)) is not None
            and candidate.start_ticks == start_ticks
            and candidate.state != "Z"
        }
        final_group = {
            candidate.pid
            for candidate in final_table.values()
            if candidate.process_group == process.pid
            and candidate.state != "Z"
        }
        if final_live or final_group:
            descendant_leak = True
            _terminate(process, tracked, limits.terminate_grace_seconds)
    if timeout:
        classification = "TIMEOUT"
    elif root_exceeded:
        classification = "ROOT_RSS_LIMIT_EXCEEDED"
    elif group_exceeded:
        classification = "PROCESS_GROUP_RSS_LIMIT_EXCEEDED"
    elif monitor_failed:
        classification = "RSS_MONITOR_FAILED"
    elif output_exceeded:
        classification = "OUTPUT_LIMIT_EXCEEDED"
    elif containment_breach:
        classification = "CONTAINMENT_BREACH"
    elif descendant_leak:
        classification = "DESCENDANT_LEAK"
    elif process.returncode == 78:
        classification = "LIMIT_SETUP_FAILED"
    elif process.returncode == 127 and "MEMSAFE_EXEC_ERROR" in stderr.text():
        classification = "EXEC_ERROR"
    elif process.returncode != 0:
        classification = "NONZERO_EXIT"
    else:
        classification = "SUCCESS"
    return RunResult(
        schema_version=SCHEMA,
        classification=classification,
        accepted_output=classification == "SUCCESS",
        command=command,
        returncode=process.returncode,
        elapsed_seconds=time.monotonic() - started,
        absolute_deadline_monotonic=absolute_deadline,
        peak_root_rss_bytes=peak_root,
        peak_process_group_rss_bytes=peak_group,
        root_rss_cap_bytes=limits.rss_bytes,
        process_group_rss_cap_bytes=process_group_rss_bytes,
        memory_reservation_bytes=limits.rss_bytes,
        memory_reservation_scope="root process",
        timeout=timeout,
        root_rss_cap_exceeded=root_exceeded,
        process_group_rss_cap_exceeded=group_exceeded,
        rss_cap_exceeded=root_exceeded or group_exceeded,
        rss_monitor_failed=monitor_failed,
        output_cap_exceeded=output_exceeded,
        containment_breach=containment_breach,
        descendant_leak=descendant_leak,
        tracked_descendant_count=max(0, len(tracked) - 1),
        root_process_group=process.pid,
        root_session=root_session,
        resource_limit_failure_possible=(
            classification == "NONZERO_EXIT"
            and (limits.address_space_bytes > 0 or limits.data_bytes > 0)
        ),
        stdout_bytes=stdout.total,
        stderr_bytes=stderr.total,
        stdout_tail=stdout.text(),
        stderr_tail=stderr.text(),
        limits=asdict(limits),
    )


def run_guarded(
    command: Sequence[str],
    *,
    limits: safe.Limits,
    process_group_rss_bytes: int,
    absolute_deadline_monotonic: float | None = None,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    status_path: Path | None = None,
) -> RunResult:
    """Run one formal case under a single admission/execution deadline."""

    limits.validate()
    if os.name != "posix" or not Path("/proc").is_dir():
        raise RuntimeError("root-scoped guard requires Linux /proc")
    if (
        not isinstance(process_group_rss_bytes, int)
        or isinstance(process_group_rss_bytes, bool)
        or process_group_rss_bytes < limits.rss_bytes
    ):
        raise ValueError(
            "process-group RSS cap must be an integer at least the root cap"
        )
    command = [str(part) for part in command]
    if not command:
        raise ValueError("command must not be empty")
    started = time.monotonic()
    phase_deadline = started + limits.timeout_seconds
    if absolute_deadline_monotonic is None:
        absolute_deadline = phase_deadline
    else:
        if not math.isfinite(absolute_deadline_monotonic):
            raise ValueError("absolute deadline must be finite")
        absolute_deadline = min(
            phase_deadline,
            float(absolute_deadline_monotonic),
        )
    if absolute_deadline <= started:
        result = _empty_result(
            classification="DEADLINE_EXHAUSTED",
            command=command,
            limits=limits,
            group_rss_bytes=process_group_rss_bytes,
            started=started,
            deadline=absolute_deadline,
        )
        if status_path is not None:
            safe.atomic_write_json(status_path, result.to_dict())
        return result
    try:
        with safe._memory_reservation(  # noqa: SLF001
            limits.rss_bytes,
            wait_seconds=max(0.0, absolute_deadline - time.monotonic()),
        ):
            if time.monotonic() >= absolute_deadline:
                result = _empty_result(
                    classification="DEADLINE_EXHAUSTED",
                    command=command,
                    limits=limits,
                    group_rss_bytes=process_group_rss_bytes,
                    started=started,
                    deadline=absolute_deadline,
                )
            else:
                result = _run_admitted(
                    command,
                    limits=limits,
                    process_group_rss_bytes=process_group_rss_bytes,
                    absolute_deadline=absolute_deadline,
                    started=started,
                    environment=environment,
                    cwd=cwd,
                )
    except (safe._MemoryReservationError, safe._MemoryReservationTimeout) as error:  # noqa: SLF001
        result = _empty_result(
            classification=(
                "MEMORY_RESERVATION_TIMEOUT"
                if isinstance(error, safe._MemoryReservationTimeout)  # noqa: SLF001
                else "INVALID_MEMORY_RESERVATION"
            ),
            command=command,
            limits=limits,
            group_rss_bytes=process_group_rss_bytes,
            started=started,
            deadline=absolute_deadline,
            stderr_tail=str(error),
        )
    if status_path is not None:
        safe.atomic_write_json(status_path, result.to_dict())
    return result
