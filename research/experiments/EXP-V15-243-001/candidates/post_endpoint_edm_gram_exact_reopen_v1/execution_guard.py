"""Candidate-private formal lease, containment, and artifact primitives.

This is intentionally not a reusable harness.  It only closes the execution
boundary of the disposable EDM/Gram exact-replay experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import tempfile
import time
from typing import Mapping, Sequence


FORMAL_LOCK_PATH = Path("/tmp/GeoTarget/formal-performance.lock")
LEASE_FD_KEY = "GEOTARGET_EDM_EXACT_LEASE_FD"
TOKEN_FD_KEY = "GEOTARGET_EDM_EXACT_TOKEN_FD"
HANDOFF_KEY = "GEOTARGET_EDM_EXACT_HANDOFF_HMAC"
ATTEMPT_SHA_KEY = "GEOTARGET_EDM_EXACT_ATTEMPT_SHA256"
STATIC_ENVIRONMENT = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TZ": "UTC",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_PRECOMPILE_TASKS": "1",
    "JULIA_PKG_PRECOMPILE_AUTO": "0",
    "MALLOC_ARENA_MAX": "2",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(document: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def atomic_write_0600(root: Path, target: Path, payload: bytes) -> None:
    """No-follow atomic publication to one direct child of ``root``."""

    supplied_root = root.absolute()
    if supplied_root.is_symlink():
        raise PermissionError("artifact root is a symlink")
    supplied_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = supplied_root.resolve()
    target = target.absolute()
    if target.parent.resolve() != root or target.name in {"", ".", ".."}:
        raise PermissionError("artifact escaped its frozen output root")
    try:
        if target.is_symlink():
            raise PermissionError("artifact target is a symlink")
    except OSError as error:
        raise PermissionError("artifact target cannot be inspected") from error
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=root
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        os.chmod(target, 0o600, follow_symlinks=False)
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass
class FormalRunLease:
    """Internal shared-host lease with an unforgeable child handoff."""

    label: str
    lock_path: Path = FORMAL_LOCK_PATH
    _descriptor: int | None = None
    _token: bytes | None = None

    def acquire(self) -> "FormalRunLease":
        if self._descriptor is not None:
            raise RuntimeError("formal lease already acquired")
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(
            self.lock_path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            owner = canonical_json(
                {
                    "schema_version": "geotarget.edm-exact-formal-lease/v1",
                    "label": self.label,
                    "pid": os.getpid(),
                    "started_monotonic_ns": time.monotonic_ns(),
                }
            )
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.write(descriptor, b"\0" + owner)
            os.fsync(descriptor)
            os.set_inheritable(descriptor, True)
        except BaseException:
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        self._token = secrets.token_bytes(32)
        return self

    def child_handoff(self, attempt_payload: bytes) -> tuple[dict[str, str], tuple[int, ...]]:
        if self._descriptor is None or self._token is None:
            raise RuntimeError("formal lease is not held")
        read_descriptor, write_descriptor = os.pipe2(os.O_CLOEXEC)
        try:
            os.write(write_descriptor, self._token)
        finally:
            os.close(write_descriptor)
        os.set_inheritable(read_descriptor, True)
        lease_stat = os.fstat(self._descriptor)
        binding = _handoff_binding(
            attempt_payload,
            lease_stat.st_dev,
            lease_stat.st_ino,
            os.getpid(),
        )
        proof = hmac.new(self._token, binding, hashlib.sha256).hexdigest()
        environment = dict(STATIC_ENVIRONMENT)
        environment.update(
            {
                LEASE_FD_KEY: str(self._descriptor),
                TOKEN_FD_KEY: str(read_descriptor),
                HANDOFF_KEY: proof,
                ATTEMPT_SHA_KEY: sha256_bytes(attempt_payload),
            }
        )
        return environment, (self._descriptor, read_descriptor)

    def close_child_token_fd(self, descriptors: Sequence[int]) -> None:
        if len(descriptors) == 2:
            try:
                os.close(int(descriptors[1]))
            except OSError:
                pass

    def release(self) -> None:
        if self._descriptor is None:
            return
        try:
            fcntl.flock(self._descriptor, fcntl.LOCK_UN)
        finally:
            os.close(self._descriptor)
            self._descriptor = None
            self._token = None

    def __enter__(self) -> "FormalRunLease":
        return self.acquire()

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.release()


def _handoff_binding(
    attempt_payload: bytes, lease_device: int, lease_inode: int, parent_pid: int
) -> bytes:
    return b"\0".join(
        (
            b"geotarget.edm-exact-child-handoff/v1",
            sha256_bytes(attempt_payload).encode("ascii"),
            str(lease_device).encode("ascii"),
            str(lease_inode).encode("ascii"),
            str(parent_pid).encode("ascii"),
        )
    )


def verify_inherited_handoff(attempt_payload: bytes) -> None:
    """Fail closed unless launched by a live parent-held FormalRunLease."""

    try:
        lease_fd = int(os.environ.pop(LEASE_FD_KEY))
        token_fd = int(os.environ.pop(TOKEN_FD_KEY))
        claimed = os.environ.pop(HANDOFF_KEY)
        attempt_sha = os.environ.pop(ATTEMPT_SHA_KEY)
    except (KeyError, TypeError, ValueError) as error:
        raise PermissionError("inherited formal lease proof is absent") from error
    if attempt_sha != sha256_bytes(attempt_payload):
        raise PermissionError("attempt bytes changed after parent authorization")
    lease_stat = os.fstat(lease_fd)
    path_stat = FORMAL_LOCK_PATH.stat()
    if (lease_stat.st_dev, lease_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
        raise PermissionError("inherited descriptor is not the formal lock")
    probe = os.open(FORMAL_LOCK_PATH, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(probe, fcntl.LOCK_UN)
            raise PermissionError("formal lock is not held by an ancestor")
    finally:
        os.close(probe)
    token = bytearray()
    try:
        while len(token) <= 64:
            part = os.read(token_fd, 65 - len(token))
            if not part:
                break
            token.extend(part)
    finally:
        os.close(token_fd)
    try:
        if len(token) != 32:
            raise PermissionError("invalid inherited lease token")
        binding = _handoff_binding(
            attempt_payload,
            lease_stat.st_dev,
            lease_stat.st_ino,
            os.getppid(),
        )
        expected = hmac.new(token, binding, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, claimed):
            raise PermissionError("inherited formal lease proof mismatch")
    finally:
        for index in range(len(token)):
            token[index] = 0


@dataclass(frozen=True)
class ContainedResult:
    classification: str
    returncode: int | None
    elapsed_seconds: float
    peak_group_rss_bytes: int


def _group_processes(group_id: int) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    page_size = os.sysconf("SC_PAGE_SIZE")
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat_text = (entry / "stat").read_text(encoding="ascii")
            remainder = stat_text[stat_text.rfind(")") + 2 :].split()
            if int(remainder[2]) != group_id:
                continue
            resident_pages = int((entry / "statm").read_text(encoding="ascii").split()[1])
            rows.append((int(entry.name), resident_pages * page_size))
        except (OSError, ValueError, IndexError):
            continue
    return rows


def _terminate_group(group_id: int) -> None:
    try:
        os.killpg(group_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 0.20
    while time.monotonic() < deadline and _group_processes(group_id):
        time.sleep(0.01)
    try:
        os.killpg(group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for pid, _rss in _group_processes(group_id):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_contained(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    pass_fds: Sequence[int],
    timeout_seconds: float,
    rss_cap_bytes: int,
    stdout_path: Path,
    stderr_path: Path,
    output_cap_bytes: int,
) -> ContainedResult:
    """Start one new session and account/kill its complete process group."""

    started = time.monotonic()
    peak = 0
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    stdout_fd = os.open(stdout_path, flags, 0o600)
    stderr_fd = os.open(stderr_path, flags, 0o600)
    try:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=stdout_fd,
            stderr=stderr_fd,
            close_fds=True,
            pass_fds=tuple(pass_fds),
            start_new_session=True,
        )
    finally:
        os.close(stdout_fd)
        os.close(stderr_fd)
    classification = "NONZERO_EXIT"
    try:
        while process.poll() is None:
            rows = _group_processes(process.pid)
            peak = max(peak, sum(rss for _pid, rss in rows))
            if peak > rss_cap_bytes:
                classification = "RSS_CAP_TERMINATED"
                _terminate_group(process.pid)
                break
            if time.monotonic() - started > timeout_seconds:
                classification = "HARD_DEADLINE_TERMINATED"
                _terminate_group(process.pid)
                break
            if any(
                path.exists() and path.stat().st_size > output_cap_bytes
                for path in (stdout_path, stderr_path)
            ):
                classification = "OUTPUT_CAP_TERMINATED"
                _terminate_group(process.pid)
                break
            time.sleep(0.01)
        try:
            returncode = process.wait(timeout=0.50)
        except subprocess.TimeoutExpired:
            _terminate_group(process.pid)
            returncode = process.wait(timeout=1.0)
        if classification == "NONZERO_EXIT" and returncode == 0:
            classification = "COMPLETED"
        if classification == "COMPLETED" and any(
            path.exists() and path.stat().st_size > output_cap_bytes
            for path in (stdout_path, stderr_path)
        ):
            classification = "OUTPUT_CAP_POSTEXIT_REJECTED"
        if _group_processes(process.pid):
            _terminate_group(process.pid)
            if classification in {"COMPLETED", "NONZERO_EXIT"}:
                classification = "DESCENDANT_LEAK_TERMINATED"
    finally:
        if process.poll() is None:
            _terminate_group(process.pid)
    return ContainedResult(
        classification, returncode, time.monotonic() - started, peak
    )
