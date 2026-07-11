"""Cross-worktree exclusion and audit records for formal performance runs.

The lock is advisory: every formal performance runner must use this module and
operators must not start unrelated CPU-heavy work while the lease is held.
Correctness-only tests need not use it unless their timing is part of a claim.
"""

from __future__ import annotations

import argparse
import ctypes
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
INTERRUPT_POLL_SECONDS = 0.05
_LINUX_PR_SET_CHILD_SUBREAPER = 36
_LINUX_PR_GET_CHILD_SUBREAPER = 37


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


class _DeferredTerminationSignals:
    """Defer SIGINT/SIGTERM delivery until process-tree cleanup is complete."""

    def __init__(self) -> None:
        self.counts: dict[int, int] = {}
        self._previous: dict[int, Any] = {}

    @property
    def count(self) -> int:
        return self.counts.get(signal.SIGINT, 0)

    @property
    def termination_count(self) -> int:
        return self.counts.get(signal.SIGTERM, 0)

    def _receive(self, signum: int, _frame: object) -> None:
        self.counts[signum] = self.counts.get(signum, 0) + 1

    def __enter__(self) -> _DeferredTerminationSignals:
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                self._previous[signum] = signal.getsignal(signum)
                signal.signal(signum, self._receive)
        except ValueError:
            # Python only permits signal-handler changes on the main thread.
            # A formal CLI run is main-threaded; a library call from another
            # thread retains normal platform signal behavior.
            for signum, previous in self._previous.items():
                signal.signal(signum, previous)
            self._previous.clear()
        return self

    def raise_if_pending(self) -> None:
        if self.counts.get(signal.SIGINT, 0):
            raise KeyboardInterrupt
        if self.counts.get(signal.SIGTERM, 0):
            raise SystemExit(128 + signal.SIGTERM)

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        for signum, previous in self._previous.items():
            signal.signal(signum, previous)
        self._previous.clear()


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
    strategy = "windows_process_tree" if os.name == "nt" else "posix_process_group"
    if sys.platform.startswith("linux"):
        strategy = "linux_subreaper_process_tree"
    return {
        "attempted": reason is not None,
        "reason": reason,
        "strategy": strategy,
        "grace_seconds": TERMINATION_GRACE_SECONDS,
        "term_sent": False,
        "kill_sent": False,
        "tree_kill_confirmed": False,
        "child_returncode": None,
        "errors": [],
    }


@dataclass(frozen=True)
class _LinuxProcessRecord:
    pid: int
    parent_pid: int
    state: str
    start_ticks: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.pid, self.start_ticks


def _linux_process_table() -> dict[int, _LinuxProcessRecord]:
    """Return a PID-reuse-safe snapshot from procfs.

    Linux ``/proc/<pid>/stat`` may contain spaces and closing parentheses in
    ``comm``.  Splitting only after its final closing parenthesis keeps the
    state, parent PID, and start-time fields aligned.
    """

    table: dict[int, _LinuxProcessRecord] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            payload = (entry / "stat").read_text(encoding="utf-8")
            close = payload.rfind(")")
            fields = payload[close + 2 :].split()
            if close < 0 or len(fields) < 20:
                continue
            pid = int(entry.name)
            table[pid] = _LinuxProcessRecord(
                pid=pid,
                parent_pid=int(fields[1]),
                state=fields[0],
                start_ticks=int(fields[19]),
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return table


def _enable_linux_subreaper() -> None:
    """Make escaped/orphaned descendants observable by this formal runner."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        current = ctypes.c_int()
        if libc.prctl(
            _LINUX_PR_GET_CHILD_SUBREAPER,
            ctypes.byref(current),
            0,
            0,
            0,
        ) != 0:
            raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER failed")
        if current.value == 0 and libc.prctl(
            _LINUX_PR_SET_CHILD_SUBREAPER,
            1,
            0,
            0,
            0,
        ) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")
    except (AttributeError, OSError) as error:
        raise FormalRunError(
            "Linux formal runs require PR_SET_CHILD_SUBREAPER process-tree custody"
        ) from error


class _LinuxProcessTree:
    """Track descendants even after session changes or intermediate-parent exit."""

    def __init__(
        self,
        root_pid: int,
        root_start_ticks: int,
        baseline_children: set[tuple[int, int]],
    ) -> None:
        self.root_identity = (root_pid, root_start_ticks)
        self.runner_pid = os.getpid()
        self.baseline_children = set(baseline_children)
        self.known: set[tuple[int, int]] = {self.root_identity}
        self.maximum_live_count = 1

    def _same_known_records(
        self, table: dict[int, _LinuxProcessRecord]
    ) -> dict[int, _LinuxProcessRecord]:
        return {
            pid: record
            for pid, record in table.items()
            if record.identity in self.known
        }

    def refresh(self) -> tuple[_LinuxProcessRecord, ...]:
        table = _linux_process_table()
        discovered = self._same_known_records(table)

        # Discover descendants while their ancestry is intact.
        parents = set(discovered)
        changed = True
        while changed:
            changed = False
            for record in table.values():
                if record.parent_pid in parents and record.pid not in parents:
                    discovered[record.pid] = record
                    parents.add(record.pid)
                    changed = True

        # PR_SET_CHILD_SUBREAPER reparents an escaped tree to the runner.  A
        # child absent from the pre-launch baseline therefore still belongs to
        # this command.  Formal run_command is deliberately single-launch and
        # does not permit concurrent child creation in the runner process.
        for record in table.values():
            if (
                record.parent_pid == self.runner_pid
                and record.identity not in self.baseline_children
            ):
                discovered[record.pid] = record

        self.known.update(record.identity for record in discovered.values())
        live = tuple(
            sorted(
                (record for record in discovered.values() if record.state != "Z"),
                key=lambda record: record.pid,
            )
        )
        self.maximum_live_count = max(self.maximum_live_count, len(live))
        return live

    def descendants_live(self) -> tuple[_LinuxProcessRecord, ...]:
        root = self.root_identity
        records = self.refresh()
        self.reap_adopted(root[0])
        # The first refresh can be the operation that discovers a newly
        # adopted zombie.  Reap once more after a second snapshot so repeated
        # library calls do not accumulate already-dead descendants.
        records = self.refresh()
        self.reap_adopted(root[0])
        return tuple(record for record in records if record.identity != root)

    def signal_live(self, signum: int, document: dict[str, Any], stage: str) -> int:
        sent = 0
        for record in reversed(self.refresh()):
            current = _linux_process_table().get(record.pid)
            if current is None or current.identity != record.identity:
                continue
            try:
                os.kill(record.pid, signum)
                sent += 1
            except ProcessLookupError:
                continue
            except OSError as error:
                _record_termination_error(document, f"{stage}[{record.pid}]", error)
        return sent

    def reap_adopted(self, direct_pid: int) -> None:
        for pid, _start_ticks in tuple(self.known):
            if pid == direct_pid:
                continue
            try:
                os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, ProcessLookupError):
                continue


def _prepare_linux_process_tree() -> set[tuple[int, int]] | None:
    if not sys.platform.startswith("linux"):
        return None
    _enable_linux_subreaper()
    return {
        record.identity
        for record in _linux_process_table().values()
        if record.parent_pid == os.getpid()
    }


def _start_linux_process_tree(
    process: subprocess.Popen[bytes],
    baseline_children: set[tuple[int, int]] | None,
) -> _LinuxProcessTree | None:
    if baseline_children is None:
        return None
    record = _linux_process_table().get(process.pid)
    if record is None:
        # A command may exit before the first snapshot.  Any surviving child is
        # still adopted by the subreaper and discovered relative to the empty
        # synthetic root identity.
        return _LinuxProcessTree(process.pid, -1, baseline_children)
    return _LinuxProcessTree(process.pid, record.start_ticks, baseline_children)


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


def _wait_for_linux_tree_exit(
    tree: _LinuxProcessTree,
    direct_pid: int,
    seconds: float,
) -> bool:
    deadline = time.monotonic() + seconds
    while True:
        tree.reap_adopted(direct_pid)
        if not tree.refresh():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.02, remaining))


def _terminate_linux_process_tree(
    process: subprocess.Popen[bytes],
    tree: _LinuxProcessTree,
    document: dict[str, Any],
) -> None:
    document["tracked_identity_count"] = len(tree.known)
    document["term_sent"] = tree.signal_live(signal.SIGTERM, document, "SIGTERM") > 0
    tree_exited = _wait_for_linux_tree_exit(
        tree,
        process.pid,
        TERMINATION_GRACE_SECONDS,
    )
    if not tree_exited:
        document["kill_sent"] = tree.signal_live(
            signal.SIGKILL,
            document,
            "SIGKILL",
        ) > 0
        tree_exited = _wait_for_linux_tree_exit(
            tree,
            process.pid,
            TERMINATION_WAIT_SECONDS,
        )

    try:
        process.wait(timeout=TERMINATION_WAIT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _record_termination_error(document, "wait_after_tree_kill", error)
        try:
            process.kill()
            document["kill_sent"] = True
            process.wait(timeout=TERMINATION_WAIT_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as kill_error:
            _record_termination_error(document, "direct_child_kill", kill_error)

    tree.reap_adopted(process.pid)
    document["child_returncode"] = process.returncode
    document["tracked_identity_count"] = len(tree.known)
    document["maximum_live_process_count"] = tree.maximum_live_count
    document["tree_kill_confirmed"] = bool(tree_exited and not tree.refresh())


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


def _terminate_process_tree(
    process: subprocess.Popen[bytes],
    *,
    reason: str,
    linux_tree: _LinuxProcessTree | None = None,
) -> dict[str, Any]:
    document = _termination_document(reason)
    if os.name == "nt":
        _terminate_windows_process_tree(process, document)
    elif linux_tree is not None:
        _terminate_linux_process_tree(process, linux_tree, document)
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
    linux_tree: _LinuxProcessTree | None = None
    exit_code: int | None = None
    outcome = "runner_error"
    error_text: str | None = None
    timed_out = False
    termination = _termination_document()
    interrupts = _DeferredTerminationSignals()

    with FormalRunLease(label, lock_path) as lease:
        interrupts.__enter__()
        print(
            f"FORMAL-RUN START label={label} pid={os.getpid()} lock={lease.lock_path}",
            flush=True,
        )
        try:
            baseline_children = _prepare_linux_process_tree()
            process = subprocess.Popen(
                frozen_command,
                **_popen_options(working_directory),
            )
            linux_tree = _start_linux_process_tree(process, baseline_children)
            next_heartbeat_ns = started_ns + int(heartbeat_seconds * 1_000_000_000)
            while True:
                interrupts.raise_if_pending()
                now_ns = time.monotonic_ns()
                if deadline_ns is not None and now_ns >= deadline_ns:
                    timed_out = True
                    termination = _terminate_process_tree(
                        process,
                        reason="hard_timeout",
                        linux_tree=linux_tree,
                    )
                    exit_code = HARD_TIMEOUT_EXIT_CODE
                    outcome = "hard_timeout"
                    return HARD_TIMEOUT_EXIT_CODE

                polled = process.poll()
                if polled is not None:
                    exit_code = polled
                    termination["child_returncode"] = polled
                    descendants_live = False
                    if linux_tree is not None:
                        linux_tree.reap_adopted(process.pid)
                        descendants_live = bool(linux_tree.descendants_live())
                    if not descendants_live:
                        # Polling and procfs custody checks take nonzero time.
                        # A completion is accepted only if that entire check
                        # finished before the hard monotonic deadline.
                        if deadline_ns is not None and time.monotonic_ns() >= deadline_ns:
                            timed_out = True
                            termination = _terminate_process_tree(
                                process,
                                reason="hard_timeout",
                                linux_tree=linux_tree,
                            )
                            exit_code = HARD_TIMEOUT_EXIT_CODE
                            outcome = "hard_timeout"
                            return HARD_TIMEOUT_EXIT_CODE
                        break

                if now_ns >= next_heartbeat_ns:
                    elapsed = (now_ns - started_ns) / 1_000_000_000
                    print(
                        f"FORMAL-RUN HEARTBEAT label={label} child={process.pid} "
                        f"elapsed_seconds={elapsed:.1f}",
                        flush=True,
                    )
                    next_heartbeat_ns = now_ns + int(
                        heartbeat_seconds * 1_000_000_000
                    )

                wait_seconds = INTERRUPT_POLL_SECONDS
                if deadline_ns is not None:
                    wait_seconds = min(
                        wait_seconds,
                        max(0.0, (deadline_ns - now_ns) / 1_000_000_000),
                    )
                if polled is None:
                    try:
                        process.wait(timeout=wait_seconds)
                    except subprocess.TimeoutExpired:
                        pass
                else:
                    time.sleep(wait_seconds)
            outcome = "completed" if exit_code == 0 else "child_failed"
            return exit_code
        except BaseException as error:
            error_text = f"{type(error).__name__}: {error}"
            outcome = (
                "interrupted"
                if isinstance(error, (KeyboardInterrupt, SystemExit))
                and (interrupts.count or interrupts.termination_count)
                else "runner_error"
            )
            if process is not None:
                termination = _terminate_process_tree(
                    process,
                    reason=outcome,
                    linux_tree=linux_tree,
                )
            exit_code = None if process is None else process.returncode
            raise
        finally:
            try:
                while True:
                    signal_snapshot = (
                        interrupts.count,
                        interrupts.termination_count,
                    )
                    if any(signal_snapshot) and outcome in ("completed", "child_failed"):
                        outcome = "interrupted"
                        error_text = error_text or "termination signal during finalization"
                        termination["finalization_signal_observed"] = True
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
                        "interrupt_signal_count": signal_snapshot[0],
                        "termination_signal_count": signal_snapshot[1],
                        "termination": termination,
                        "timeout_boundary": (
                            "outer child process tree only; success is accepted only "
                            "when observed strictly before the monotonic deadline; no "
                            "in-process preemption claim"
                        ),
                        "process_tree_boundary": (
                            "Linux PR_SET_CHILD_SUBREAPER plus PID/start-time procfs "
                            "custody; other platforms retain their recorded strategy"
                        ),
                        "runner_kill_boundary": (
                            "SIGINT and SIGTERM are deferred through cleanup; SIGKILL "
                            "or host failure cannot be handled in-process"
                        ),
                        "cooperation_boundary": (
                            "advisory lock; unrelated uncooperative host work remains "
                            "forbidden"
                        ),
                        "error": error_text,
                    }
                    _write_json_atomic(audit_path, audit)
                    print(
                        f"FORMAL-RUN END label={label} outcome={outcome} "
                        f"exit_code={exit_code} audit={audit_path}",
                        flush=True,
                    )
                    if signal_snapshot == (
                        interrupts.count,
                        interrupts.termination_count,
                    ):
                        break
            finally:
                interrupts.__exit__(None, None, None)
            interrupts.raise_if_pending()


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
