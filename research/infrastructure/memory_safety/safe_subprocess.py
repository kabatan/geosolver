"""Bounded, fail-closed subprocess execution for disposable experiments.

The helper is intentionally independent of the production solver.  It keeps
captured output bounded, enforces Linux address/data limits in an exec
launcher, monitors aggregate RSS for the complete process group, and kills
that process group on a wall/RSS/output breach.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from contextlib import contextmanager
from typing import BinaryIO, Iterator, Mapping, Sequence


SCHEMA = "geotarget.memory-safe-subprocess/v1"
MIB = 1024**2
GIB = 1024**3
DEFAULT_GLOBAL_RSS_RESERVATION_BYTES = 8 * GIB
DEFAULT_RESERVATION_TOKEN_BYTES = 256 * MIB
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_PRECOMPILE_TASKS": "1",
    "JULIA_PKG_PRECOMPILE_AUTO": "0",
    "RAYON_NUM_THREADS": "1",
    "CMAKE_BUILD_PARALLEL_LEVEL": "1",
    "MAKEFLAGS": "-j1",
    "MALLOC_ARENA_MAX": "2",
}


class _MemoryReservationError(ValueError):
    pass


class _MemoryReservationTimeout(TimeoutError):
    pass


@dataclass(frozen=True)
class Limits:
    timeout_seconds: float
    rss_bytes: int
    address_space_bytes: int
    data_bytes: int
    output_bytes: int = 4 * MIB
    tail_bytes: int = 16 * 1024
    poll_seconds: float = 0.05
    terminate_grace_seconds: float = 1.0

    def validate(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        for name in ("rss_bytes", "address_space_bytes", "data_bytes", "output_bytes"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0.005 <= self.poll_seconds <= 1.0:
            raise ValueError("poll_seconds must be between 0.005 and 1.0")
        if self.tail_bytes < 0 or self.tail_bytes > self.output_bytes:
            raise ValueError("tail_bytes must be between zero and output_bytes")
        if self.terminate_grace_seconds < 0 or self.terminate_grace_seconds > 10:
            raise ValueError("terminate_grace_seconds must be between zero and ten")


@dataclass(frozen=True)
class RunResult:
    schema_version: str
    classification: str
    accepted_output: bool
    command: list[str]
    returncode: int | None
    elapsed_seconds: float
    peak_process_group_rss_bytes: int
    timeout: bool
    rss_cap_exceeded: bool
    rss_monitor_failed: bool
    output_cap_exceeded: bool
    descendant_leak: bool
    resource_limit_failure_possible: bool
    stdout_bytes: int
    stderr_bytes: int
    stdout_tail: str
    stderr_tail: str
    limits: dict[str, int | float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class _TailCollector(threading.Thread):
    def __init__(self, stream: BinaryIO, *, tail_bytes: int, output_bytes: int) -> None:
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


def atomic_write_json(path: Path, document: object, *, mode: int = 0o600) -> None:
    """Durably replace a JSON status/checkpoint within its destination directory."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _process_group_rss_bytes(process_group: int) -> int | None:
    """Read aggregate resident pages for every live member of a Linux pgrp."""

    total_pages = 0
    try:
        entries = os.scandir("/proc")
    except OSError:
        return None
    observed = 0
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                stat = Path(entry.path, "stat").read_text(encoding="ascii")
                after_name = stat[stat.rfind(")") + 2 :].split()
                # Fields following comm are: state, ppid, pgrp, ...
                if len(after_name) < 3 or int(after_name[2]) != process_group:
                    continue
                statm = Path(entry.path, "statm").read_text(encoding="ascii").split()
                total_pages += int(statm[1])
                observed += 1
            except (FileNotFoundError, PermissionError, OSError, ValueError, IndexError):
                continue
    if observed == 0:
        return None
    return total_pages * os.sysconf("SC_PAGE_SIZE")


def _process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_process_group(process: subprocess.Popen[bytes], grace_seconds: float) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        process.poll()
        if not _process_group_exists(process.pid):
            break
        time.sleep(0.01)
    if _process_group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _result_for_launch_error(command: Sequence[str], limits: Limits, error: OSError) -> RunResult:
    return RunResult(
        schema_version=SCHEMA,
        classification="LAUNCH_ERROR",
        accepted_output=False,
        command=list(command),
        returncode=None,
        elapsed_seconds=0.0,
        peak_process_group_rss_bytes=0,
        timeout=False,
        rss_cap_exceeded=False,
        rss_monitor_failed=False,
        output_cap_exceeded=False,
        descendant_leak=False,
        resource_limit_failure_possible=False,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_tail="",
        stderr_tail=str(error),
        limits=asdict(limits),
    )


def _reservation_configuration() -> tuple[Path, int, int]:
    directory = Path(
        os.environ.get(
            "GEOTARGET_MEMORY_RESERVATION_DIR",
            f"/tmp/geotarget-memory-reservations-v1-{os.getuid()}",
        )
    )
    cap = int(
        os.environ.get(
            "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES",
            DEFAULT_GLOBAL_RSS_RESERVATION_BYTES,
        )
    )
    token = int(
        os.environ.get(
            "GEOTARGET_MEMORY_RESERVATION_TOKEN_BYTES",
            DEFAULT_RESERVATION_TOKEN_BYTES,
        )
    )
    if cap <= 0 or token <= 0 or token > cap:
        raise _MemoryReservationError("invalid global memory reservation configuration")
    return directory, cap, token


@contextmanager
def _memory_reservation(
    requested_bytes: int,
    *,
    wait_seconds: float,
    directory: Path | None = None,
    cap_bytes: int | None = None,
    token_bytes: int | None = None,
) -> Iterator[None]:
    """Reserve crash-safe host-RSS tokens shared by every experiment agent.

    Advisory locks are held for the complete child lifetime and are released
    by the kernel even if Codex or the runner process crashes.  This prevents
    individually bounded symbolic jobs from exceeding the aggregate research
    allowance when separate agents launch them concurrently.
    """

    configured_directory, configured_cap, configured_token = _reservation_configuration()
    directory = configured_directory if directory is None else Path(directory)
    cap_bytes = configured_cap if cap_bytes is None else cap_bytes
    token_bytes = configured_token if token_bytes is None else token_bytes
    if requested_bytes <= 0 or cap_bytes <= 0 or token_bytes <= 0 or token_bytes > cap_bytes:
        raise _MemoryReservationError("invalid memory reservation request")
    if requested_bytes > cap_bytes:
        raise _MemoryReservationError(
            f"requested RSS cap {requested_bytes} exceeds aggregate reservation cap {cap_bytes}"
        )
    token_count = cap_bytes // token_bytes
    needed = math.ceil(requested_bytes / token_bytes)
    if needed > token_count:
        raise _MemoryReservationError(
            "memory reservation cannot be represented by available tokens"
        )
    directory.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    acquired: list[BinaryIO] = []
    try:
        while True:
            for index in range(token_count):
                handle = (directory / f"token-{index:04d}.lock").open("a+b")
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    handle.close()
                    continue
                acquired.append(handle)
                if len(acquired) == needed:
                    yield
                    return
            for handle in acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
            acquired.clear()
            if time.monotonic() >= deadline:
                raise _MemoryReservationTimeout(
                    "aggregate memory reservation timed out before process launch"
                )
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    finally:
        for handle in acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _result_for_reservation_failure(
    command: Sequence[str],
    limits: Limits,
    error: _MemoryReservationError | _MemoryReservationTimeout,
    elapsed_seconds: float,
) -> RunResult:
    classification = (
        "MEMORY_RESERVATION_TIMEOUT"
        if isinstance(error, _MemoryReservationTimeout)
        else "INVALID_MEMORY_RESERVATION"
    )
    return RunResult(
        schema_version=SCHEMA,
        classification=classification,
        accepted_output=False,
        command=list(command),
        returncode=None,
        elapsed_seconds=elapsed_seconds,
        peak_process_group_rss_bytes=0,
        timeout=False,
        rss_cap_exceeded=False,
        rss_monitor_failed=False,
        output_cap_exceeded=False,
        descendant_leak=False,
        resource_limit_failure_possible=False,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_tail="",
        stderr_tail=str(error),
        limits=asdict(limits),
    )


def _run_guarded_reserved(
    command: Sequence[str],
    *,
    limits: Limits,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    status_path: Path | None = None,
    inherit_environment: bool = True,
    pass_fds: Sequence[int] = (),
) -> RunResult:
    """Run one command; never accept output from a breached/failed process.

    This is deliberately a one-command API: callers must opt in explicitly to
    parallelism rather than inheriting a high-concurrency batch default.
    """

    limits.validate()
    if os.name != "posix" or not Path("/proc").is_dir():
        raise RuntimeError("run_guarded currently requires Linux /proc")
    command = [str(part) for part in command]
    if not command:
        raise ValueError("command must not be empty")
    launcher = Path(__file__).with_name("_limit_exec.py")
    wrapped_command = [
        sys.executable,
        "-I",
        "-S",
        str(launcher),
        "--as-bytes",
        str(limits.address_space_bytes),
        "--data-bytes",
        str(limits.data_bytes),
        "--",
        *command,
    ]
    child_environment = dict(os.environ) if inherit_environment else {}
    if environment is not None:
        child_environment.update({str(key): str(value) for key, value in environment.items()})
    child_environment.update(THREAD_ENV)
    inherited_fds = tuple(int(file_descriptor) for file_descriptor in pass_fds)
    if any(file_descriptor < 0 for file_descriptor in inherited_fds):
        raise ValueError("pass_fds entries must be non-negative")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            wrapped_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=cwd,
            env=child_environment,
            pass_fds=inherited_fds,
            start_new_session=True,
        )
    except OSError as error:
        result = _result_for_launch_error(command, limits, error)
        if status_path is not None:
            atomic_write_json(status_path, result.to_dict())
        return result
    assert process.stdout is not None and process.stderr is not None
    stdout = _TailCollector(
        process.stdout, tail_bytes=limits.tail_bytes, output_bytes=limits.output_bytes
    )
    stderr = _TailCollector(
        process.stderr, tail_bytes=limits.tail_bytes, output_bytes=limits.output_bytes
    )
    stdout.start()
    stderr.start()
    deadline = started + limits.timeout_seconds
    peak_rss = 0
    timeout = False
    rss_cap_exceeded = False
    rss_monitor_failed = False
    output_cap_exceeded = False
    parent_completed = False
    while True:
        returncode = process.poll()
        now = time.monotonic()
        if returncode is not None:
            parent_completed = True
            # The only fail-closed wall-clock authority available here is when
            # completion was observed.  A child first observed after the
            # deadline must not be accepted merely because it exited between
            # monitor polls.
            if now >= deadline:
                timeout = True
            break
        rss = _process_group_rss_bytes(process.pid)
        if rss is None:
            rss_monitor_failed = True
            break
        peak_rss = max(peak_rss, rss)
        if rss > limits.rss_bytes:
            rss_cap_exceeded = True
            break
        if (
            stdout.cap_exceeded.is_set()
            or stderr.cap_exceeded.is_set()
            or stdout.total + stderr.total > limits.output_bytes
        ):
            output_cap_exceeded = True
            break
        if now >= deadline:
            timeout = True
            break
        time.sleep(min(limits.poll_seconds, max(0.0, deadline - now)))

    descendant_leak = parent_completed and _process_group_exists(process.pid)
    if (
        timeout
        or rss_cap_exceeded
        or rss_monitor_failed
        or output_cap_exceeded
        or descendant_leak
        or process.poll() is None
    ):
        _terminate_process_group(process, limits.terminate_grace_seconds)
    final_rss = _process_group_rss_bytes(process.pid)
    if final_rss is not None:
        peak_rss = max(peak_rss, final_rss)
    stdout.join(timeout=0.25)
    stderr.join(timeout=0.25)
    descendant_leak = descendant_leak or stdout.is_alive() or stderr.is_alive()
    if descendant_leak:
        _terminate_process_group(process, limits.terminate_grace_seconds)
        stdout.join(timeout=1.0)
        stderr.join(timeout=1.0)
    # A short-lived writer can exit between monitor polls.  Its result is still
    # rejected if either drain or their aggregate exceeded the permitted bytes.
    output_cap_exceeded = (
        output_cap_exceeded
        or stdout.cap_exceeded.is_set()
        or stderr.cap_exceeded.is_set()
        or stdout.total + stderr.total > limits.output_bytes
    )
    elapsed = time.monotonic() - started
    if timeout:
        classification = "TIMEOUT"
    elif rss_cap_exceeded:
        classification = "RSS_LIMIT_EXCEEDED"
    elif rss_monitor_failed:
        classification = "RSS_MONITOR_FAILED"
    elif output_cap_exceeded:
        classification = "OUTPUT_LIMIT_EXCEEDED"
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
    accepted = classification == "SUCCESS"
    result = RunResult(
        schema_version=SCHEMA,
        classification=classification,
        accepted_output=accepted,
        command=command,
        returncode=process.returncode,
        elapsed_seconds=elapsed,
        peak_process_group_rss_bytes=peak_rss,
        timeout=timeout,
        rss_cap_exceeded=rss_cap_exceeded,
        rss_monitor_failed=rss_monitor_failed,
        output_cap_exceeded=output_cap_exceeded,
        descendant_leak=descendant_leak,
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
    if status_path is not None:
        atomic_write_json(status_path, result.to_dict())
    return result


def run_guarded(
    command: Sequence[str],
    *,
    limits: Limits,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    status_path: Path | None = None,
    inherit_environment: bool = True,
    pass_fds: Sequence[int] = (),
) -> RunResult:
    """Run one command with both per-process and aggregate RSS protection."""

    limits.validate()
    command = [str(part) for part in command]
    started = time.monotonic()
    try:
        with _memory_reservation(
            limits.rss_bytes,
            wait_seconds=limits.timeout_seconds,
        ):
            return _run_guarded_reserved(
                command,
                limits=limits,
                environment=environment,
                cwd=cwd,
                status_path=status_path,
                inherit_environment=inherit_environment,
                pass_fds=pass_fds,
            )
    except (_MemoryReservationError, _MemoryReservationTimeout) as error:
        result = _result_for_reservation_failure(
            command,
            limits,
            error,
            time.monotonic() - started,
        )
        if status_path is not None:
            atomic_write_json(status_path, result.to_dict())
        return result


def _mib(value: float) -> int:
    return int(value * MIB)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--rss-mib", type=float, required=True)
    parser.add_argument("--address-space-mib", type=float, required=True)
    parser.add_argument("--data-mib", type=float, required=True)
    parser.add_argument("--output-mib", type=float, default=4.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = list(arguments.command)
    if command and command[0] == "--":
        command.pop(0)
    result = run_guarded(
        command,
        limits=Limits(
            timeout_seconds=arguments.timeout_seconds,
            rss_bytes=_mib(arguments.rss_mib),
            address_space_bytes=_mib(arguments.address_space_mib),
            data_bytes=_mib(arguments.data_mib),
            output_bytes=_mib(arguments.output_mib),
        ),
        status_path=arguments.status,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.accepted_output else 1)


if __name__ == "__main__":
    main()
