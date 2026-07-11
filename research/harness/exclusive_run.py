"""Cross-worktree exclusion and audit records for formal performance runs.

The lock is advisory: every formal performance runner must use this module and
operators must not start unrelated CPU-heavy work while the lease is held.
Correctness-only tests need not use it unless their timing is part of a claim.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

SCHEMA_VERSION = "geotarget.formal-performance-run/v1"
DEFAULT_LOCK_ENV = "GEOTARGET_FORMAL_RUN_LOCK"
HARD_TIMEOUT_EXIT_CODE = 124
TERMINATION_GRACE_SECONDS = 0.5
TERMINATION_WAIT_SECONDS = 5.0


class FormalRunError(RuntimeError):
    """Base error for the formal-run guard."""


class FormalRunBusy(FormalRunError):
    """Raised when another cooperating process owns the host lease."""

    def __init__(self, lock_path: Path, owner: dict[str, Any] | None) -> None:
        self.lock_path = lock_path
        self.owner = owner
        detail = (
            json.dumps(owner, sort_keys=True) if owner else "owner metadata unavailable"
        )
        super().__init__(f"formal performance host is busy at {lock_path}: {detail}")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def default_lock_path() -> Path:
    override = os.environ.get(DEFAULT_LOCK_ENV)
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    else:
        root = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
    return (root / "GeoTarget" / "formal-performance.lock").resolve()


def _lock_file(handle: IO[bytes]) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError from error
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle: IO[bytes]) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_owner(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            handle.seek(1)
            payload = handle.read()
    except OSError:
        return None
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _write_owner(handle: IO[bytes], owner: dict[str, Any]) -> None:
    payload = json.dumps(owner, sort_keys=True, separators=(",", ":")).encode("utf-8")
    handle.seek(1)
    handle.write(payload)
    handle.truncate()
    handle.flush()
    os.fsync(handle.fileno())


@dataclass
class FormalRunLease:
    """An advisory, process-scoped exclusive lease shared by all worktrees."""

    label: str
    lock_path: Path | None = None
    _handle: IO[bytes] | None = None
    _owner: dict[str, Any] | None = None

    @property
    def owner(self) -> dict[str, Any]:
        if self._owner is None:
            raise FormalRunError("formal performance lease is not held")
        return dict(self._owner)

    def acquire(self) -> FormalRunLease:
        if self._handle is not None:
            raise FormalRunError("formal performance lease is already held")
        label = self.label.strip()
        if not label:
            raise ValueError("formal run label must be nonempty")
        path = (self.lock_path or default_lock_path()).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            try:
                _lock_file(handle)
            except BlockingIOError:
                owner = _read_owner(path)
                handle.close()
                raise FormalRunBusy(path, owner) from None
            owner = {
                "schema": SCHEMA_VERSION,
                "state": "running",
                "label": label,
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "started_at_utc": _utc_now(),
            }
            _write_owner(handle, owner)
        except BaseException:
            if not handle.closed:
                handle.close()
            raise
        self.lock_path = path
        self._handle = handle
        self._owner = owner
        return self

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            owner = dict(self._owner or {})
            owner.update(state="released", released_at_utc=_utc_now())
            _write_owner(handle, owner)
            _unlock_file(handle)
        finally:
            handle.close()
            self._handle = None
            self._owner = None

    def __enter__(self) -> FormalRunLease:
        return self.acquire()

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.release()


def _write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _finite_positive(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite and positive")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be finite and positive") from error
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return numeric


def _positive_seconds_argument(value: str) -> float:
    try:
        return _finite_positive(value, "seconds")
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _termination_document(reason: str | None = None) -> dict[str, Any]:
    return {
        "attempted": reason is not None,
        "reason": reason,
        "strategy": ("windows_process_tree" if os.name == "nt" else "posix_process_group"),
        "grace_seconds": TERMINATION_GRACE_SECONDS,
        "term_sent": False,
        "kill_sent": False,
        "tree_kill_confirmed": False,
        "child_returncode": None,
        "errors": [],
    }


def _record_termination_error(document: dict[str, Any], stage: str, error: object) -> None:
    document["errors"].append(f"{stage}: {type(error).__name__}: {error}")


def _posix_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_group_exit(process_group: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while _posix_group_exists(process_group):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))
    return True


def _terminate_posix_process_group(
    process: subprocess.Popen[bytes], document: dict[str, Any]
) -> None:
    process_group = process.pid
    try:
        os.killpg(process_group, signal.SIGTERM)
        document["term_sent"] = True
    except ProcessLookupError:
        pass
    except OSError as error:
        _record_termination_error(document, "SIGTERM", error)

    group_exited = _wait_for_group_exit(process_group, TERMINATION_GRACE_SECONDS)
    if not group_exited:
        try:
            os.killpg(process_group, signal.SIGKILL)
            document["kill_sent"] = True
        except ProcessLookupError:
            pass
        except OSError as error:
            _record_termination_error(document, "SIGKILL", error)

    try:
        process.wait(timeout=TERMINATION_WAIT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _record_termination_error(document, "wait_after_group_kill", error)
        try:
            process.kill()
            document["kill_sent"] = True
            process.wait(timeout=TERMINATION_WAIT_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as kill_error:
            _record_termination_error(document, "direct_child_kill", kill_error)

    document["child_returncode"] = process.returncode
    document["tree_kill_confirmed"] = _wait_for_group_exit(process_group, 0.5)


def _terminate_windows_process_tree(
    process: subprocess.Popen[bytes], document: dict[str, Any]
) -> None:
    # taskkill /T is the strongest process-tree primitive available in the
    # supported standard Windows installation without introducing a resident
    # broker.  A nonzero result is recorded as unconfirmed rather than silently
    # narrowing the claim to the direct child.
    taskkill_succeeded = False
    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=TERMINATION_WAIT_SECONDS,
            check=False,
            shell=False,
        )
        document["kill_sent"] = True
        taskkill_succeeded = completed.returncode == 0
        if not taskkill_succeeded:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            document["errors"].append(f"taskkill: returncode={completed.returncode}: {detail}")
    except (OSError, subprocess.TimeoutExpired) as error:
        _record_termination_error(document, "taskkill", error)

    if process.poll() is None:
        try:
            process.kill()
            document["kill_sent"] = True
        except OSError as error:
            _record_termination_error(document, "direct_child_kill", error)
    try:
        process.wait(timeout=TERMINATION_WAIT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _record_termination_error(document, "wait_after_taskkill", error)

    document["child_returncode"] = process.returncode
    document["tree_kill_confirmed"] = bool(taskkill_succeeded and process.returncode is not None)


def _terminate_process_tree(process: subprocess.Popen[bytes], *, reason: str) -> dict[str, Any]:
    document = _termination_document(reason)
    if os.name == "nt":
        _terminate_windows_process_tree(process, document)
    else:
        _terminate_posix_process_group(process, document)
    return document


def _popen_options(working_directory: Path) -> dict[str, Any]:
    options: dict[str, Any] = {
        "cwd": working_directory,
        "shell": False,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return options


def run_command(
    command: Sequence[str],
    *,
    label: str,
    audit_path: Path,
    lock_path: Path | None = None,
    cwd: Path | None = None,
    heartbeat_seconds: float = 30.0,
    timeout_seconds: float | None = None,
) -> int:
    """Run one command under the formal host lease and persist its audit record.

    ``timeout_seconds`` is an outer process-tree deadline.  It does not make an
    in-process solver call asynchronously preemptible.
    """

    frozen_command = tuple(str(part) for part in command)
    if not frozen_command:
        raise ValueError("formal run command cannot be empty")
    heartbeat_seconds = _finite_positive(heartbeat_seconds, "heartbeat_seconds")
    configured_timeout = (
        None if timeout_seconds is None else _finite_positive(timeout_seconds, "timeout_seconds")
    )
    working_directory = Path.cwd() if cwd is None else cwd.expanduser().resolve()
    started_wall = _utc_now()
    started_ns = time.monotonic_ns()
    deadline_ns = (
        None if configured_timeout is None else started_ns + int(configured_timeout * 1_000_000_000)
    )
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    outcome = "runner_error"
    error_text: str | None = None
    timed_out = False
    termination = _termination_document()

    with FormalRunLease(label, lock_path) as lease:
        print(
            f"FORMAL-RUN START label={label} pid={os.getpid()} lock={lease.lock_path}",
            flush=True,
        )
        try:
            process = subprocess.Popen(
                frozen_command,
                **_popen_options(working_directory),
            )
            while True:
                polled = process.poll()
                if polled is not None:
                    exit_code = polled
                    termination["child_returncode"] = polled
                    break
                now_ns = time.monotonic_ns()
                if deadline_ns is not None and now_ns >= deadline_ns:
                    timed_out = True
                    termination = _terminate_process_tree(
                        process,
                        reason="hard_timeout",
                    )
                    exit_code = HARD_TIMEOUT_EXIT_CODE
                    outcome = "hard_timeout"
                    return HARD_TIMEOUT_EXIT_CODE
                wait_seconds = heartbeat_seconds
                if deadline_ns is not None:
                    wait_seconds = min(
                        wait_seconds,
                        max(0.0, (deadline_ns - now_ns) / 1_000_000_000),
                    )
                try:
                    exit_code = process.wait(timeout=wait_seconds)
                    termination["child_returncode"] = exit_code
                    break
                except subprocess.TimeoutExpired:
                    if deadline_ns is not None and time.monotonic_ns() >= deadline_ns:
                        continue
                    elapsed = (time.monotonic_ns() - started_ns) / 1_000_000_000
                    print(
                        f"FORMAL-RUN HEARTBEAT label={label} child={process.pid} "
                        f"elapsed_seconds={elapsed:.1f}",
                        flush=True,
                    )
            outcome = "completed" if exit_code == 0 else "child_failed"
            return exit_code
        except BaseException as error:
            error_text = f"{type(error).__name__}: {error}"
            outcome = (
                "interrupted"
                if isinstance(error, KeyboardInterrupt)
                else "runner_error"
            )
            if process is not None and process.poll() is None:
                termination = _terminate_process_tree(process, reason=outcome)
            exit_code = None if process is None else process.returncode
            raise
        finally:
            ended_ns = time.monotonic_ns()
            audit = {
                "schema": SCHEMA_VERSION,
                "label": label,
                "outcome": outcome,
                "command": list(frozen_command),
                "cwd": str(working_directory),
                "runner_pid": os.getpid(),
                "child_pid": None if process is None else process.pid,
                "exit_code": exit_code,
                "started_at_utc": started_wall,
                "ended_at_utc": _utc_now(),
                "elapsed_seconds": (ended_ns - started_ns) / 1_000_000_000,
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "python": platform.python_version(),
                "logical_cpu_count": os.cpu_count(),
                "lock_path": str(lease.lock_path),
                "configured_timeout_seconds": configured_timeout,
                "timed_out": timed_out,
                "termination": termination,
                "timeout_boundary": (
                    "outer child process tree only; no in-process preemption claim"
                ),
                "cooperation_boundary": (
                    "advisory lock; unrelated uncooperative host work remains forbidden"
                ),
                "error": error_text,
            }
            _write_json_atomic(audit_path, audit)
            print(
                f"FORMAL-RUN END label={label} outcome={outcome} "
                f"exit_code={exit_code} audit={audit_path}",
                flush=True,
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a command under GeoTarget's cross-worktree performance lease."
    )
    parser.add_argument("--label", required=True)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--heartbeat-seconds", type=_positive_seconds_argument, default=30.0)
    parser.add_argument("--timeout-seconds", type=_positive_seconds_argument)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    command = list(arguments.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        parser.error("a command is required after --")
    try:
        return run_command(
            command,
            label=arguments.label,
            audit_path=arguments.audit,
            lock_path=arguments.lock,
            cwd=arguments.cwd,
            heartbeat_seconds=arguments.heartbeat_seconds,
            timeout_seconds=arguments.timeout_seconds,
        )
    except FormalRunBusy as error:
        print(str(error), file=sys.stderr, flush=True)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
