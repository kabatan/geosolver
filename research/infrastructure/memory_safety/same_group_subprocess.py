"""Deadline-aware child-tree guard that preserves an outer process group.

Formal case runners own a process group and may kill it asynchronously. Nested
exact lanes must therefore remain in that group instead of calling ``setsid``.
This module enforces an inner deadline/RSS/output boundary by tracking the lane
root's Linux ``/proc`` descendant closure and signalling only those PID/start
time identities. A temporary child-subreaper closes the fast-orphan race and
allows adopted grandchildren to be reaped.

The API is intentionally one-command and exclusive: only one same-group guard
may be active per process. It retains the repository-wide memory reservation,
RLIMIT AS/DATA launcher, one-thread environment, bounded output, and optional
atomic status artifact used by the detached experiment guard.
"""

from __future__ import annotations

import ctypes
from dataclasses import asdict, dataclass
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import BinaryIO, Mapping, Sequence


HERE = Path(__file__).resolve().parent
SAFE_SUBPROCESS_PATH = HERE / "safe_subprocess.py"
LIMIT_LAUNCHER = HERE / "_limit_exec.py"
SCHEMA = "geotarget.same-process-group-subprocess/v1"
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37
_ACTIVE_GUARD = threading.Lock()


def _load_safe_subprocess():
    name = "geotarget_same_group_safe_subprocess_dependency"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, SAFE_SUBPROCESS_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("safe subprocess dependency is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


SAFE = _load_safe_subprocess()
MIB = SAFE.MIB
GIB = SAFE.GIB


@dataclass(frozen=True)
class Limits:
    lane_cap_seconds: float
    finalization_reserve_seconds: float
    teardown_reserve_seconds: float
    rss_bytes: int
    address_space_bytes: int
    data_bytes: int
    output_bytes: int
    tail_bytes: int = 4096
    poll_seconds: float = 0.01
    terminate_grace_seconds: float = 0.1

    def validate(self) -> None:
        for name in (
            "lane_cap_seconds",
            "finalization_reserve_seconds",
            "teardown_reserve_seconds",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{name} must be numeric")
            if not 0.0 < float(value) < float("inf"):
                raise ValueError(f"{name} must be finite and positive")
        for name in (
            "rss_bytes",
            "address_space_bytes",
            "data_bytes",
            "output_bytes",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.address_space_bytes < self.rss_bytes:
            raise ValueError("address-space cap cannot be below RSS cap")
        if self.data_bytes < self.rss_bytes:
            raise ValueError("data cap cannot be below RSS cap")
        if not 0.002 <= self.poll_seconds <= 1.0:
            raise ValueError("poll_seconds must be between 0.002 and 1.0")
        if not 0 <= self.tail_bytes <= self.output_bytes:
            raise ValueError("tail_bytes must be between zero and output_bytes")
        if not 0.0 <= self.terminate_grace_seconds <= 2.0:
            raise ValueError("terminate_grace_seconds must be between zero and two")


@dataclass(frozen=True)
class RunResult:
    schema_version: str
    classification: str
    accepted_output: bool
    command: list[str]
    returncode: int | None
    elapsed_seconds: float
    child_timeout_seconds: float
    peak_descendant_closure_rss_bytes: int
    timeout: bool
    rss_cap_exceeded: bool
    rss_monitor_failed: bool
    output_cap_exceeded: bool
    containment_breach: bool
    descendant_leak: bool
    descendants_observed: int
    descendants_reaped: int
    root_process_group: int | None
    root_session: int | None
    caller_process_group: int
    caller_session: int
    parent_finalization_reserve_preserved: bool
    stdout_bytes: int
    stderr_bytes: int
    stdout_tail: str
    stderr_tail: str
    limits: dict[str, int | float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _Process:
    pid: int
    state: str
    ppid: int
    process_group: int
    session: int
    start_ticks: int
    rss_bytes: int


class _TailCollector(threading.Thread):
    def __init__(self, stream: BinaryIO, *, tail_bytes: int, output_bytes: int):
        super().__init__(daemon=True)
        self._stream = stream
        self._tail_bytes = tail_bytes
        self._output_bytes = output_bytes
        self.tail = bytearray()
        self.total = 0
        self.cap_exceeded = threading.Event()

    def run(self) -> None:
        try:
            while True:
                chunk = self._stream.read(64 * 1024)
                if not chunk:
                    break
                self.total += len(chunk)
                if self.total > self._output_bytes:
                    self.cap_exceeded.set()
                if self._tail_bytes:
                    self.tail.extend(chunk)
                    if len(self.tail) > self._tail_bytes:
                        del self.tail[: len(self.tail) - self._tail_bytes]
        finally:
            self._stream.close()

    def text(self) -> str:
        return bytes(self.tail).decode("utf-8", errors="replace")


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
                pid = int(entry.name)
                raw = Path(entry.path, "stat").read_text(encoding="ascii")
                fields = raw[raw.rfind(")") + 2 :].split()
                statm = Path(entry.path, "statm").read_text(encoding="ascii").split()
                if len(fields) < 20 or len(statm) < 2:
                    continue
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


def _subreaper_state() -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    value = ctypes.c_int()
    if libc.prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(value), 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    return int(value.value)


def _set_subreaper(enabled: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, int(enabled), 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


class _Tracker:
    def __init__(
        self,
        *,
        guardian_pid: int,
        root: _Process,
        baseline_descendants: set[int],
        expected_process_group: int,
        expected_session: int,
    ) -> None:
        self.guardian_pid = guardian_pid
        self.root_pid = root.pid
        self.root_start_ticks = root.start_ticks
        self.baseline_descendants = baseline_descendants
        self.expected_process_group = expected_process_group
        self.expected_session = expected_session
        self.identities: dict[int, int] = {root.pid: root.start_ticks}
        self.containment_breach = False

    def refresh(self, table: Mapping[int, _Process]) -> dict[int, _Process]:
        guardian_descendants = _descendants(self.guardian_pid, table)
        rooted = {self.root_pid, *_descendants(self.root_pid, table)}
        adopted = guardian_descendants - self.baseline_descendants
        for pid in rooted | adopted:
            process = table.get(pid)
            if process is None or process.start_ticks < self.root_start_ticks:
                continue
            self.identities.setdefault(pid, process.start_ticks)
            if (
                process.process_group != self.expected_process_group
                or process.session != self.expected_session
            ):
                self.containment_breach = True
        return {
            pid: process
            for pid, start_ticks in self.identities.items()
            if (process := table.get(pid)) is not None
            and process.start_ticks == start_ticks
        }


def _signal_tracked(
    tracker: _Tracker,
    table: Mapping[int, _Process],
    signal_number: int,
) -> None:
    live = tracker.refresh(table)
    depths: dict[int, int] = {}
    for pid in live:
        depth = 0
        current = live[pid]
        while current.ppid in live:
            depth += 1
            current = live[current.ppid]
        depths[pid] = depth
    for pid in sorted(live, key=lambda item: (depths[item], item), reverse=True):
        if live[pid].state == "Z":
            continue
        try:
            os.kill(pid, signal_number)
        except ProcessLookupError:
            pass


def _reap_tracked(root: subprocess.Popen[bytes], tracker: _Tracker) -> int:
    reaped = 0
    try:
        root.wait(timeout=0.02)
    except subprocess.TimeoutExpired:
        pass
    for pid in tuple(tracker.identities):
        if pid == root.pid:
            continue
        try:
            waited, _status = os.waitpid(pid, os.WNOHANG)
        except (ChildProcessError, ProcessLookupError):
            continue
        if waited == pid:
            reaped += 1
    return reaped


def _terminate_and_reap(
    root: subprocess.Popen[bytes],
    tracker: _Tracker,
    grace_seconds: float,
) -> int:
    table = _read_process_table() or {}
    _signal_tracked(tracker, table, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    reaped = 0
    while time.monotonic() < deadline:
        reaped += _reap_tracked(root, tracker)
        remaining = tracker.refresh(_read_process_table() or {})
        if not any(process.state != "Z" for process in remaining.values()):
            break
        time.sleep(0.005)
    _signal_tracked(tracker, _read_process_table() or {}, signal.SIGKILL)
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        reaped += _reap_tracked(root, tracker)
        if not tracker.refresh(_read_process_table() or {}):
            break
        time.sleep(0.005)
    reaped += _reap_tracked(root, tracker)
    return reaped


def _empty_result(
    *,
    classification: str,
    command: Sequence[str],
    started: float,
    child_timeout_seconds: float,
    caller_process_group: int,
    caller_session: int,
    parent_deadline: float,
    limits: Limits,
) -> RunResult:
    return RunResult(
        schema_version=SCHEMA,
        classification=classification,
        accepted_output=False,
        command=list(command),
        returncode=None,
        elapsed_seconds=time.monotonic() - started,
        child_timeout_seconds=max(0.0, child_timeout_seconds),
        peak_descendant_closure_rss_bytes=0,
        timeout=False,
        rss_cap_exceeded=False,
        rss_monitor_failed=False,
        output_cap_exceeded=False,
        containment_breach=False,
        descendant_leak=False,
        descendants_observed=0,
        descendants_reaped=0,
        root_process_group=None,
        root_session=None,
        caller_process_group=caller_process_group,
        caller_session=caller_session,
        parent_finalization_reserve_preserved=(
            time.monotonic() <= parent_deadline - limits.finalization_reserve_seconds
        ),
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_tail="",
        stderr_tail="",
        limits=asdict(limits),
    )


def _run_admitted(
    command: Sequence[str],
    *,
    child_timeout_seconds: float,
    parent_deadline: float,
    limits: Limits,
    environment: Mapping[str, str] | None,
    cwd: Path | None,
) -> RunResult:
    started = time.monotonic()
    caller_process_group = os.getpgrp()
    caller_session = os.getsid(0)
    previous_subreaper = 0
    subreaper_changed = False
    process: subprocess.Popen[bytes] | None = None
    tracker: _Tracker | None = None
    stdout: _TailCollector | None = None
    stderr: _TailCollector | None = None
    root_process: _Process | None = None
    peak_rss = 0
    timeout = False
    rss_cap_exceeded = False
    rss_monitor_failed = False
    output_cap_exceeded = False
    descendant_leak = False
    descendants_reaped = 0
    parent_completed = False
    try:
        previous_subreaper = _subreaper_state()
        _set_subreaper(1)
        subreaper_changed = True
        baseline_table = _read_process_table()
        if baseline_table is None:
            raise RuntimeError("cannot establish baseline descendant closure")
        baseline_descendants = _descendants(os.getpid(), baseline_table)
        wrapped = [
            sys.executable,
            str(LIMIT_LAUNCHER),
            "--as-bytes",
            str(limits.address_space_bytes),
            "--data-bytes",
            str(limits.data_bytes),
            "--",
            *[str(part) for part in command],
        ]
        child_environment = dict(os.environ)
        if environment is not None:
            child_environment.update(
                {str(key): str(value) for key, value in environment.items()}
            )
        child_environment.update(SAFE.THREAD_ENV)
        process = subprocess.Popen(
            wrapped,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=cwd,
            env=child_environment,
            start_new_session=False,
        )
        assert process.stdout is not None and process.stderr is not None
        table = _read_process_table()
        root_process = None if table is None else table.get(process.pid)
        if root_process is None:
            process.terminate()
            process.wait(timeout=1.0)
            raise RuntimeError(
                "lane root disappeared before containment was established"
            )
        tracker = _Tracker(
            guardian_pid=os.getpid(),
            root=root_process,
            baseline_descendants=baseline_descendants,
            expected_process_group=caller_process_group,
            expected_session=caller_session,
        )
        tracker.refresh(table)
        stdout = _TailCollector(
            process.stdout,
            tail_bytes=limits.tail_bytes,
            output_bytes=limits.output_bytes,
        )
        stderr = _TailCollector(
            process.stderr,
            tail_bytes=limits.tail_bytes,
            output_bytes=limits.output_bytes,
        )
        stdout.start()
        stderr.start()
        child_deadline = started + child_timeout_seconds
        while True:
            now = time.monotonic()
            table = _read_process_table()
            if table is None:
                rss_monitor_failed = True
                break
            live = tracker.refresh(table)
            peak_rss = max(
                peak_rss,
                sum(candidate.rss_bytes for candidate in live.values()),
            )
            if peak_rss > limits.rss_bytes:
                rss_cap_exceeded = True
                break
            if tracker.containment_breach:
                break
            if (
                stdout.cap_exceeded.is_set()
                or stderr.cap_exceeded.is_set()
                or stdout.total + stderr.total > limits.output_bytes
            ):
                output_cap_exceeded = True
                break
            returncode = process.poll()
            if returncode is not None:
                parent_completed = True
                if now >= child_deadline:
                    timeout = True
                # A short-lived native helper may exit immediately before its
                # parent and be adopted by this subreaper as a zombie.  It is
                # already dead, holds no RSS or pipe, and is precisely what
                # the subreaper is expected to collect.  Reap such children
                # before deciding whether the completed lane leaked a live
                # descendant.  A still-running child remains a hard leak.
                descendants_reaped += _reap_tracked(process, tracker)
                refreshed = _read_process_table()
                if refreshed is None:
                    rss_monitor_failed = True
                    break
                live = tracker.refresh(refreshed)
                if any(
                    pid != process.pid and candidate.state != "Z"
                    for pid, candidate in live.items()
                ):
                    descendant_leak = True
                break
            if now >= child_deadline:
                timeout = True
                break
            time.sleep(min(limits.poll_seconds, max(0.0, child_deadline - now)))

        must_cleanup = (
            timeout
            or rss_cap_exceeded
            or rss_monitor_failed
            or output_cap_exceeded
            or tracker.containment_breach
            or descendant_leak
            or not parent_completed
        )
        if must_cleanup:
            descendants_reaped += _terminate_and_reap(
                process, tracker, limits.terminate_grace_seconds
            )
        else:
            descendants_reaped += _reap_tracked(process, tracker)
        stdout.join(timeout=0.25)
        stderr.join(timeout=0.25)
        if stdout.is_alive() or stderr.is_alive():
            descendant_leak = True
            descendants_reaped += _terminate_and_reap(
                process, tracker, limits.terminate_grace_seconds
            )
            stdout.join(timeout=0.5)
            stderr.join(timeout=0.5)
        output_cap_exceeded = (
            output_cap_exceeded
            or stdout.cap_exceeded.is_set()
            or stderr.cap_exceeded.is_set()
            or stdout.total + stderr.total > limits.output_bytes
        )
        descendants_reaped += _reap_tracked(process, tracker)
        final_table = _read_process_table()
        if final_table is None:
            rss_monitor_failed = True
            final_live: dict[int, _Process] = {}
        else:
            final_live = tracker.refresh(final_table)
            peak_rss = max(
                peak_rss,
                sum(candidate.rss_bytes for candidate in final_live.values()),
            )
        if any(candidate.state != "Z" for candidate in final_live.values()):
            descendant_leak = True
            descendants_reaped += _terminate_and_reap(
                process, tracker, limits.terminate_grace_seconds
            )
        elif final_live:
            # A final /proc sample can race the waitpid above.  These entries
            # are dead adopted children, so collect them without converting a
            # successful lane into DESCENDANT_LEAK.
            descendants_reaped += _reap_tracked(process, tracker)
        if timeout:
            classification = "TIMEOUT"
        elif rss_cap_exceeded:
            classification = "RSS_LIMIT_EXCEEDED"
        elif rss_monitor_failed:
            classification = "RSS_MONITOR_FAILED"
        elif output_cap_exceeded:
            classification = "OUTPUT_LIMIT_EXCEEDED"
        elif tracker.containment_breach:
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
        reserve_preserved = (
            time.monotonic() <= parent_deadline - limits.finalization_reserve_seconds
        )
        if not reserve_preserved:
            classification = "PARENT_RESERVE_BREACHED"
        return RunResult(
            schema_version=SCHEMA,
            classification=classification,
            accepted_output=classification == "SUCCESS",
            command=[str(part) for part in command],
            returncode=process.returncode,
            elapsed_seconds=time.monotonic() - started,
            child_timeout_seconds=child_timeout_seconds,
            peak_descendant_closure_rss_bytes=peak_rss,
            timeout=timeout,
            rss_cap_exceeded=rss_cap_exceeded,
            rss_monitor_failed=rss_monitor_failed,
            output_cap_exceeded=output_cap_exceeded,
            containment_breach=tracker.containment_breach,
            descendant_leak=descendant_leak,
            descendants_observed=max(0, len(tracker.identities) - 1),
            descendants_reaped=descendants_reaped,
            root_process_group=root_process.process_group,
            root_session=root_process.session,
            caller_process_group=caller_process_group,
            caller_session=caller_session,
            parent_finalization_reserve_preserved=reserve_preserved,
            stdout_bytes=stdout.total,
            stderr_bytes=stderr.total,
            stdout_tail=stdout.text(),
            stderr_tail=stderr.text(),
            limits=asdict(limits),
        )
    finally:
        if process is not None and tracker is not None:
            if tracker.refresh(_read_process_table() or {}):
                try:
                    _terminate_and_reap(process, tracker, 0.05)
                except (OSError, subprocess.SubprocessError):
                    pass
        elif process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.1)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    pass
        try:
            if subreaper_changed:
                _set_subreaper(previous_subreaper)
        finally:
            _ACTIVE_GUARD.release()


def run_guarded_until(
    command: Sequence[str],
    *,
    parent_deadline_monotonic: float,
    limits: Limits,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    status_path: Path | None = None,
) -> RunResult:
    """Run one child tree without detaching it from the caller's outer pgrp.

    Memory admission and child execution share one absolute parent deadline.
    The child is launched only when the declared finalization and teardown
    reserves remain. All non-success classifications are fail closed.
    """

    limits.validate()
    if os.name != "posix" or not Path("/proc").is_dir():
        raise RuntimeError("same-group subprocess guard requires Linux /proc")
    if (
        not isinstance(parent_deadline_monotonic, (int, float))
        or isinstance(parent_deadline_monotonic, bool)
        or not time.monotonic() < float(parent_deadline_monotonic) < float("inf")
    ):
        raise ValueError("parent_deadline_monotonic must be a future finite time")
    command = [str(part) for part in command]
    if not command:
        raise ValueError("command must not be empty")
    started = time.monotonic()
    caller_process_group = os.getpgrp()
    caller_session = os.getsid(0)
    parent_deadline = float(parent_deadline_monotonic)
    latest_guard_return = (
        parent_deadline
        - limits.finalization_reserve_seconds
        - limits.teardown_reserve_seconds
    )
    reservation_wait = min(
        limits.lane_cap_seconds,
        max(0.0, latest_guard_return - time.monotonic()),
    )
    if reservation_wait <= 0.0:
        result = _empty_result(
            classification="DEADLINE_EXHAUSTED",
            command=command,
            started=started,
            child_timeout_seconds=0.0,
            caller_process_group=caller_process_group,
            caller_session=caller_session,
            parent_deadline=parent_deadline,
            limits=limits,
        )
    else:
        try:
            with SAFE._memory_reservation(
                limits.rss_bytes,
                wait_seconds=reservation_wait,
            ):
                child_timeout = min(
                    limits.lane_cap_seconds,
                    latest_guard_return - time.monotonic(),
                )
                if child_timeout <= 0.0:
                    result = _empty_result(
                        classification="DEADLINE_EXHAUSTED",
                        command=command,
                        started=started,
                        child_timeout_seconds=0.0,
                        caller_process_group=caller_process_group,
                        caller_session=caller_session,
                        parent_deadline=parent_deadline,
                        limits=limits,
                    )
                elif not _ACTIVE_GUARD.acquire(blocking=False):
                    result = _empty_result(
                        classification="GUARD_BUSY",
                        command=command,
                        started=started,
                        child_timeout_seconds=child_timeout,
                        caller_process_group=caller_process_group,
                        caller_session=caller_session,
                        parent_deadline=parent_deadline,
                        limits=limits,
                    )
                else:
                    # _run_admitted owns release after the nonblocking acquire.
                    result = _run_admitted(
                        command,
                        child_timeout_seconds=child_timeout,
                        parent_deadline=parent_deadline,
                        limits=limits,
                        environment=environment,
                        cwd=cwd,
                    )
        except (SAFE._MemoryReservationError, SAFE._MemoryReservationTimeout) as error:
            result = _empty_result(
                classification=(
                    "MEMORY_RESERVATION_TIMEOUT"
                    if isinstance(error, SAFE._MemoryReservationTimeout)
                    else "INVALID_MEMORY_RESERVATION"
                ),
                command=command,
                started=started,
                child_timeout_seconds=0.0,
                caller_process_group=caller_process_group,
                caller_session=caller_session,
                parent_deadline=parent_deadline,
                limits=limits,
            )
    if status_path is not None:
        SAFE.atomic_write_json(status_path, result.to_dict())
    return result
