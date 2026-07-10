"""Cross-worktree exclusion and audit records for formal performance runs.

The lock is advisory: every formal performance runner must use this module and
operators must not start unrelated CPU-heavy work while the lease is held.
Correctness-only tests need not use it unless their timing is part of a claim.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, Sequence


SCHEMA_VERSION = "geotarget.formal-performance-run/v1"
DEFAULT_LOCK_ENV = "GEOTARGET_FORMAL_RUN_LOCK"


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

    def acquire(self) -> "FormalRunLease":
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

    def __enter__(self) -> "FormalRunLease":
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


def run_command(
    command: Sequence[str],
    *,
    label: str,
    audit_path: Path,
    lock_path: Path | None = None,
    cwd: Path | None = None,
    heartbeat_seconds: float = 30.0,
) -> int:
    """Run one command under the formal host lease and persist its audit record."""

    frozen_command = tuple(str(part) for part in command)
    if not frozen_command:
        raise ValueError("formal run command cannot be empty")
    if not (heartbeat_seconds > 0 and heartbeat_seconds < float("inf")):
        raise ValueError("heartbeat_seconds must be finite and positive")
    working_directory = Path.cwd() if cwd is None else cwd.expanduser().resolve()
    started_wall = _utc_now()
    started_ns = time.monotonic_ns()
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    outcome = "runner_error"
    error_text: str | None = None

    with FormalRunLease(label, lock_path) as lease:
        print(
            f"FORMAL-RUN START label={label} pid={os.getpid()} lock={lease.lock_path}",
            flush=True,
        )
        try:
            process = subprocess.Popen(frozen_command, cwd=working_directory)
            while True:
                try:
                    exit_code = process.wait(timeout=heartbeat_seconds)
                    break
                except subprocess.TimeoutExpired:
                    elapsed = (time.monotonic_ns() - started_ns) / 1_000_000_000
                    print(
                        f"FORMAL-RUN HEARTBEAT label={label} child={process.pid} "
                        f"elapsed_seconds={elapsed:.1f}",
                        flush=True,
                    )
            outcome = "completed"
            return exit_code
        except BaseException as error:
            error_text = f"{type(error).__name__}: {error}"
            outcome = (
                "interrupted"
                if isinstance(error, KeyboardInterrupt)
                else "runner_error"
            )
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
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
    parser.add_argument("--heartbeat-seconds", type=float, default=30.0)
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
        )
    except FormalRunBusy as error:
        print(str(error), file=sys.stderr, flush=True)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
