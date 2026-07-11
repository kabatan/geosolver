"""Stable Windows AppContainer broker for C0-owned child observations.

The broker deliberately uses only documented, stable Win32 APIs.  It creates a
fresh AppContainer profile, grants the package SID the minimum requested file
access, starts one suspended process with an empty capability set and an
explicit three-handle inheritance list, assigns the process to a non-breakaway
kill-on-close Job atomically at process creation, and only then resumes it.
All Job descendants are accounted
for and must be gone before a result is returned.

Formal protocol callers MUST create and durably publish their irreversible
attempt claim before calling :func:`run_sandboxed` (and therefore before any
profile or ACL mutation).  ``claim_reference`` is included in the attestation;
this C0 utility cannot itself decide whether an experiment-specific claim is
authoritative.

Read trees are expanded before mutation and every touched DACL is restored from
its exact original self-relative security descriptor.  The scratch directory
must be empty; children created there are removed before its original DACL is
restored.  Cleanup failure is fatal.  On non-Windows hosts execution fails
closed, while request validation and injected/mock unit tests remain usable.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import stat
import struct
import subprocess
import threading
import time
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable, Final, Protocol


_SCHEMA_VERSION: Final = "geotarget.exp-local-003.appcontainer-attestation/v1"
_PROFILE_PREFIX: Final = "GeoTarget.EXPLOCAL003."

# Process creation and STARTUPINFOEX.
_CREATE_SUSPENDED: Final = 0x00000004
_CREATE_UNICODE_ENVIRONMENT: Final = 0x00000400
_EXTENDED_STARTUPINFO_PRESENT: Final = 0x00080000
_CREATE_NO_WINDOW: Final = 0x08000000
_STARTF_USESTDHANDLES: Final = 0x00000100
_PROC_THREAD_ATTRIBUTE_HANDLE_LIST: Final = 0x00020002
_PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: Final = 0x00020009
_PROC_THREAD_ATTRIBUTE_JOB_LIST: Final = 0x0002000D

# Handles and waits.
_HANDLE_FLAG_INHERIT: Final = 0x00000001
_WAIT_OBJECT_0: Final = 0x00000000
_WAIT_TIMEOUT: Final = 0x00000102
_INFINITE: Final = 0xFFFFFFFF
_STILL_ACTIVE: Final = 259
_ERROR_BROKEN_PIPE: Final = 109
_ERROR_NO_DATA: Final = 232
_ERROR_INSUFFICIENT_BUFFER: Final = 122
_ERROR_BAD_LENGTH: Final = 24
_INVALID_HANDLE_VALUE: Final = ctypes.c_void_p(-1).value

# Job APIs.  Omitting BREAKAWAY_OK and SILENT_BREAKAWAY_OK is intentional.
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS: Final = 0x00000008
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
_JOB_OBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION: Final = 8
_JOB_TERMINATION_CODE: Final = 0xC0DE0001

# File and ACL APIs.
_GENERIC_READ: Final = 0x80000000
_FILE_SHARE_READ: Final = 0x00000001
_FILE_SHARE_WRITE: Final = 0x00000002
_FILE_SHARE_DELETE: Final = 0x00000004
_OPEN_EXISTING: Final = 3
_FILE_ATTRIBUTE_NORMAL: Final = 0x00000080
_FILE_ATTRIBUTE_DIRECTORY: Final = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT: Final = 0x00000400
_FILE_FLAG_BACKUP_SEMANTICS: Final = 0x02000000
_INVALID_FILE_ATTRIBUTES: Final = 0xFFFFFFFF
_DACL_SECURITY_INFORMATION: Final = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION: Final = 0x80000000
_UNPROTECTED_DACL_SECURITY_INFORMATION: Final = 0x20000000
_SE_DACL_PROTECTED: Final = 0x1000
_SE_FILE_OBJECT: Final = 1
_GRANT_ACCESS: Final = 1
_REVOKE_ACCESS: Final = 4
_TRUSTEE_IS_SID: Final = 0
_TRUSTEE_IS_USER: Final = 1
_NO_INHERITANCE: Final = 0
_SUB_CONTAINERS_AND_OBJECTS_INHERIT: Final = 0x3
_ACL_SIZE_INFORMATION_CLASS: Final = 2
_ACCESS_ALLOWED_ACE_TYPE: Final = 0
_FILE_GENERIC_READ: Final = 0x00120089
_FILE_GENERIC_EXECUTE: Final = 0x001200A0
_FILE_ALL_ACCESS: Final = 0x001F01FF

# Token inspection/impersonation.  Values are stable winnt.h constants.
_TOKEN_DUPLICATE: Final = 0x0002
_TOKEN_IMPERSONATE: Final = 0x0004
_TOKEN_QUERY: Final = 0x0008
_SECURITY_IMPERSONATION: Final = 2
_TOKEN_IMPERSONATION: Final = 2
_TOKEN_ELEVATION: Final = 20
_TOKEN_INTEGRITY_LEVEL: Final = 25
_TOKEN_IS_APPCONTAINER: Final = 29
_TOKEN_CAPABILITIES: Final = 30
_TOKEN_APPCONTAINER_SID: Final = 31
_SECURITY_MANDATORY_LOW_RID: Final = 0x1000
_ERROR_ACCESS_DENIED: Final = 5


class SandboxError(RuntimeError):
    """The sandbox could not uphold its fail-closed contract."""


class UnsupportedPlatformError(SandboxError):
    """AppContainer execution was requested on a non-Windows host."""


class SandboxCleanupError(SandboxError):
    """One or more security cleanup operations failed."""


class TerminationReason(StrEnum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    STDOUT_LIMIT = "stdout-limit"
    STDERR_LIMIT = "stderr-limit"


class PathProbeStatus(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ReadGrant:
    """A file or an existing directory tree granted read/execute access."""

    path: Path
    recursive: bool = False


@dataclass(frozen=True, slots=True)
class AccessProbe:
    """A C0-only pre-resume access assertion made with the child token."""

    path: Path
    expected: PathProbeStatus


@dataclass(frozen=True, slots=True)
class AccessProbeObservation:
    """Kernel access result observed before untrusted code can execute."""

    path: str
    expected: PathProbeStatus
    observed: PathProbeStatus
    winerror: int


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    """A complete, secret-free request for one fresh AppContainer invocation."""

    command: tuple[str, ...]
    allowed_read: tuple[ReadGrant, ...]
    scratch_directory: Path
    claim_reference: str
    timeout_seconds: float = 30.0
    stdout_limit_bytes: int = 4 * 1024 * 1024
    stderr_limit_bytes: int = 4 * 1024 * 1024
    preexit_payload_limit_bytes: int | None = None
    max_processes: int = 1
    environment: tuple[tuple[str, str], ...] = ()
    access_probes: tuple[AccessProbe, ...] = ()
    profile_name: str | None = None


@dataclass(frozen=True, slots=True)
class SandboxAttestation:
    schema_version: str
    claim_reference: str
    profile_name: str
    package_sid: str
    capabilities: tuple[str, ...]
    allowed_read_paths: tuple[str, ...]
    scratch_directory: str
    environment: tuple[tuple[str, str], ...]
    inherited_handle_roles: tuple[str, ...]
    process_id: int
    token_is_appcontainer: bool
    token_appcontainer_sid_verified: bool
    token_integrity_rid: int
    token_elevated: bool
    token_capability_count: int
    access_probes: tuple[AccessProbeObservation, ...]
    max_processes: int
    job_assigned_at_creation: bool
    job_membership_verified: bool
    job_limit_flags: int
    breakaway_allowed: bool
    kill_on_job_close: bool
    job_empty: bool
    acl_entry_count: int
    original_acl_manifest_sha256: str
    restored_acl_manifest_sha256: str
    acl_exactly_restored: bool
    scratch_emptied: bool
    profile_deleted: bool


@dataclass(frozen=True, slots=True)
class SandboxResult:
    command: tuple[str, ...]
    return_code: int
    stdout: bytes
    stderr: bytes
    termination_reason: TerminationReason
    wall_time_ns: int
    total_user_time_100ns: int
    total_kernel_time_100ns: int
    total_processes: int
    terminated_processes: int
    read_operation_count: int
    write_operation_count: int
    other_operation_count: int
    read_transfer_count: int
    write_transfer_count: int
    other_transfer_count: int
    preexit: PreexitReceipt | None
    attestation: SandboxAttestation


@dataclass(frozen=True, slots=True)
class PreexitContext:
    """C0 observation passed to the trusted seal callback while child is blocked."""

    process_id: int
    active_processes: int
    root_process_still_active: bool
    payload_sha256: str
    payload_byte_length: int
    observer_elapsed_ns: int


@dataclass(frozen=True, slots=True)
class PreexitReceipt:
    """Broker-owned proof that sealing preceded ACK and process exit."""

    payload_sha256: str
    payload_byte_length: int
    ack_sha256: str
    ack_byte_length: int
    active_processes_before_callback: int
    root_active_before_callback: bool
    active_processes_before_ack: int
    root_active_before_ack: bool
    callback_completed: bool
    ack_released: bool


@dataclass(frozen=True, slots=True)
class PathProbeResult:
    target: str
    status: PathProbeStatus
    sandbox: SandboxResult


class _ApiProtocol(Protocol):
    """Narrow seam used by request-level tests and the concrete Win32 backend."""

    def run(
        self,
        request: SandboxRequest,
        on_preexit: Callable[[bytes, PreexitContext], bytes] | None = None,
    ) -> SandboxResult: ...


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = (
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    )


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = (("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD))


class _TOKEN_APPCONTAINER_INFORMATION(ctypes.Structure):
    _fields_ = (("TokenAppContainer", wintypes.LPVOID),)


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = (("Label", _SID_AND_ATTRIBUTES),)


class _TOKEN_ELEVATION_STRUCT(ctypes.Structure):
    _fields_ = (("TokenIsElevated", wintypes.DWORD),)


class _SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = (
        ("AppContainerSid", wintypes.LPVOID),
        ("Capabilities", ctypes.POINTER(_SID_AND_ATTRIBUTES)),
        ("CapabilityCount", wintypes.DWORD),
        ("Reserved", wintypes.DWORD),
    )


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    )


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = (("StartupInfo", _STARTUPINFOW), ("lpAttributeList", wintypes.LPVOID))


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    )


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = (
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    )


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    )


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


class _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    )


class _JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("BasicInfo", _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
    )


class _TRUSTEE_W(ctypes.Structure):
    pass


_TRUSTEE_W._fields_ = (
    ("pMultipleTrustee", ctypes.POINTER(_TRUSTEE_W)),
    ("MultipleTrusteeOperation", wintypes.DWORD),
    ("TrusteeForm", wintypes.DWORD),
    ("TrusteeType", wintypes.DWORD),
    ("ptstrName", wintypes.LPVOID),
)


class _EXPLICIT_ACCESS_W(ctypes.Structure):
    _fields_ = (
        ("grfAccessPermissions", wintypes.DWORD),
        ("grfAccessMode", wintypes.DWORD),
        ("grfInheritance", wintypes.DWORD),
        ("Trustee", _TRUSTEE_W),
    )


class _ACE_HEADER(ctypes.Structure):
    _fields_ = (
        ("AceType", ctypes.c_ubyte),
        ("AceFlags", ctypes.c_ubyte),
        ("AceSize", wintypes.WORD),
    )


class _ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("AceCount", wintypes.DWORD),
        ("AclBytesInUse", wintypes.DWORD),
        ("AclBytesFree", wintypes.DWORD),
    )


@dataclass(frozen=True, slots=True)
class _SecurityDescriptorSnapshot:
    path: str
    payload: bytes
    protected: bool


@dataclass(frozen=True, slots=True)
class _AclGrantTarget:
    path: Path
    inheritance: int


@dataclass(frozen=True, slots=True)
class _ValidatedRequest:
    request: SandboxRequest
    command: tuple[str, ...]
    executable: Path
    grants: tuple[ReadGrant, ...]
    acl_targets: tuple[_AclGrantTarget, ...]
    grant_entries: tuple[Path, ...]
    scratch: Path
    probes: tuple[AccessProbe, ...]
    profile_name: str
    environment: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class _ReaderResult:
    payload: bytes
    overflow: bool
    error: BaseException | None


@dataclass(frozen=True, slots=True)
class _SecurityObservation:
    process_id: int
    integrity_rid: int
    capability_count: int
    access_probes: tuple[AccessProbeObservation, ...]
    job_limit_flags: int


class _PipeReader(threading.Thread):
    def __init__(
        self,
        api: _WindowsApi,
        handle: int,
        limit: int,
        role: str,
        *,
        frame_limit: int | None = None,
    ) -> None:
        super().__init__(name=f"appcontainer-{role}-reader", daemon=True)
        self._api = api
        self._handle = handle
        self._limit = limit
        self._chunks: list[bytes] = []
        self._size = 0
        self._overflow = False
        self._error: BaseException | None = None
        self._frame_limit = frame_limit
        self._frame_payload: bytes | None = None
        self._frame_error: str | None = None
        self._lock = threading.Lock()
        self.overflow_event = threading.Event()
        self.frame_event = threading.Event()

    def _inspect_frame_locked(self) -> None:
        if self._frame_limit is None or self._frame_error is not None:
            return
        payload = b"".join(self._chunks)
        if len(payload) < 8:
            return
        declared = struct.unpack(">Q", payload[:8])[0]
        if declared == 0 or declared > self._frame_limit:
            self._frame_error = f"pre-exit stdout frame length {declared} is outside 1..{self._frame_limit}"
            self.frame_event.set()
            return
        expected = 8 + declared
        if len(payload) > expected:
            self._frame_error = "pre-exit stdout contains bytes after its single frame"
            self.frame_event.set()
            return
        if len(payload) == expected:
            self._frame_payload = payload[8:]
            self.frame_event.set()

    def run(self) -> None:
        try:
            while True:
                chunk = self._api.read_pipe(self._handle)
                if chunk is None:
                    return
                with self._lock:
                    remaining = self._limit - self._size
                    if remaining > 0:
                        kept = chunk[:remaining]
                        self._chunks.append(kept)
                        self._size += len(kept)
                    if len(chunk) > remaining:
                        self._overflow = True
                        self.overflow_event.set()
                    self._inspect_frame_locked()
        except BaseException as exc:  # surfaced to the broker thread
            self._error = exc

    def result(self) -> _ReaderResult:
        with self._lock:
            return _ReaderResult(b"".join(self._chunks), self._overflow, self._error)

    def frame(self) -> tuple[bytes | None, str | None]:
        with self._lock:
            return self._frame_payload, self._frame_error


def _win_error(message: str, code: int | None = None) -> SandboxError:
    error = ctypes.get_last_error() if code is None else code
    return SandboxError(
        f"{message}: [WinError {error}] {ctypes.FormatError(error).strip()}"
    )


def _hresult_error(message: str, value: int) -> SandboxError:
    unsigned = ctypes.c_uint32(value).value
    return SandboxError(f"{message}: HRESULT 0x{unsigned:08X}")


def _handle_value(handle: object) -> int:
    value = ctypes.cast(handle, ctypes.c_void_p).value
    if value is None:
        raise SandboxError("Win32 returned a null handle")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalize_existing(path: Path, *, directory: bool | None = None) -> Path:
    candidate = Path(os.path.abspath(path))
    if not candidate.exists():
        raise SandboxError(f"sandbox path does not exist: {candidate}")
    resolved = Path(os.path.realpath(candidate))
    if resolved != candidate:
        raise SandboxError(f"sandbox path traverses a link/reparse alias: {candidate}")
    metadata = candidate.lstat()
    attributes = getattr(metadata, "st_file_attributes", 0)
    if stat.S_ISLNK(metadata.st_mode) or attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        raise SandboxError(f"sandbox path is a link/reparse point: {candidate}")
    if directory is True and not candidate.is_dir():
        raise SandboxError(f"sandbox path must be a directory: {candidate}")
    if directory is False and not candidate.is_file():
        raise SandboxError(f"sandbox path must be a regular file: {candidate}")
    if candidate.is_file() and metadata.st_nlink != 1:
        raise SandboxError(f"sandbox file must not have hardlink aliases: {candidate}")
    return candidate


def _expand_grant(grant: ReadGrant) -> tuple[Path, ...]:
    root = _normalize_existing(grant.path)
    if root.is_file():
        if grant.recursive:
            raise SandboxError(f"recursive read grant is invalid for a file: {root}")
        return (root,)
    if not root.is_dir():
        raise SandboxError(f"read grant is not a file or directory: {root}")
    if not grant.recursive:
        return (root,)
    entries = [root]
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        directory_names.sort(key=str.casefold)
        file_names.sort(key=str.casefold)
        for name in (*directory_names, *file_names):
            entry = current_path / name
            metadata = entry.lstat()
            attributes = getattr(metadata, "st_file_attributes", 0)
            if (
                stat.S_ISLNK(metadata.st_mode)
                or attributes & _FILE_ATTRIBUTE_REPARSE_POINT
                or Path(os.path.realpath(entry)) != entry
            ):
                raise SandboxError(
                    f"recursive read grant contains a link/reparse alias: {entry}"
                )
            if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
                raise SandboxError(
                    f"recursive read grant contains a hardlinked file: {entry}"
                )
            entries.append(entry)
    return tuple(entries)


def _validate_request(request: SandboxRequest) -> _ValidatedRequest:
    if not request.claim_reference or "\x00" in request.claim_reference:
        raise SandboxError("claim_reference must be a non-empty NUL-free identifier")
    if not request.command:
        raise SandboxError("sandbox command must not be empty")
    if any(
        not isinstance(item, str) or not item or "\x00" in item
        for item in request.command
    ):
        raise SandboxError(
            "sandbox command arguments must be non-empty NUL-free strings"
        )
    executable = _normalize_existing(Path(request.command[0]), directory=False)
    if not executable.is_absolute():
        raise SandboxError("sandbox executable must be absolute")
    if not (0.001 <= request.timeout_seconds <= 86_400.0):
        raise SandboxError("timeout_seconds must be between 0.001 and 86400")
    if not (1 <= request.stdout_limit_bytes <= 1 << 30):
        raise SandboxError("stdout_limit_bytes must be between 1 and 2^30")
    if not (1 <= request.stderr_limit_bytes <= 1 << 30):
        raise SandboxError("stderr_limit_bytes must be between 1 and 2^30")
    if request.preexit_payload_limit_bytes is not None and not (
        1 <= request.preexit_payload_limit_bytes <= request.stdout_limit_bytes - 8
    ):
        raise SandboxError(
            "preexit_payload_limit_bytes must fit a nonempty 8-byte framed stdout"
        )
    if not (1 <= request.max_processes <= 256):
        raise SandboxError("max_processes must be between 1 and 256")

    scratch = _normalize_existing(request.scratch_directory, directory=True)
    if any(scratch.iterdir()):
        raise SandboxError(f"scratch directory must be empty before launch: {scratch}")

    grants: list[ReadGrant] = []
    entries: list[Path] = []
    seen_grants: set[tuple[str, bool]] = set()
    seen_entries: set[str] = set()
    for raw in request.allowed_read:
        root = _normalize_existing(raw.path)
        key = (os.path.normcase(str(root)), raw.recursive)
        if key in seen_grants:
            continue
        seen_grants.add(key)
        if _is_within(scratch, root) or _is_within(root, scratch):
            raise SandboxError(f"read grants and scratch must not overlap: {root}")
        normalized = ReadGrant(root, raw.recursive)
        grants.append(normalized)
        for entry in _expand_grant(normalized):
            entry_key = os.path.normcase(str(entry))
            if entry_key not in seen_entries:
                seen_entries.add(entry_key)
                entries.append(entry)
    if not any(_is_within(executable, grant.path) for grant in grants):
        raise SandboxError("the executable must be covered by an explicit read grant")
    for index, grant in enumerate(grants):
        for other in grants[index + 1 :]:
            if (
                grant.recursive
                and _is_within(other.path, grant.path)
                or other.recursive
                and _is_within(grant.path, other.path)
            ):
                raise SandboxError(
                    "read grant roots must be disjoint after recursive coverage: "
                    f"{grant.path}, {other.path}"
                )
    acl_targets = tuple(
        _AclGrantTarget(
            grant.path,
            _SUB_CONTAINERS_AND_OBJECTS_INHERIT
            if grant.recursive and grant.path.is_dir()
            else _NO_INHERITANCE,
        )
        for grant in grants
    )

    probes: list[AccessProbe] = []
    seen_probes: set[str] = set()
    for raw_probe in request.access_probes:
        if raw_probe.expected not in (PathProbeStatus.ALLOWED, PathProbeStatus.DENIED):
            raise SandboxError("access probe expectation must be allowed or denied")
        target = _normalize_existing(raw_probe.path)
        key = os.path.normcase(str(target))
        if key in seen_probes:
            raise SandboxError(f"duplicate access probe target: {target}")
        seen_probes.add(key)
        covered = any(_is_within(target, grant.path) for grant in grants)
        if raw_probe.expected is PathProbeStatus.ALLOWED and not covered:
            raise SandboxError(
                f"allowed access probe is outside every read grant: {target}"
            )
        if raw_probe.expected is PathProbeStatus.DENIED and covered:
            raise SandboxError(
                f"denied access probe is inside an allowed read grant: {target}"
            )
        if _is_within(target, scratch) or _is_within(scratch, target):
            raise SandboxError(f"access probe and scratch must not overlap: {target}")
        probes.append(AccessProbe(target, raw_probe.expected))

    environment_by_folded_key: dict[str, tuple[str, str]] = {}
    for key, value in request.environment:
        if not key or "=" in key or "\x00" in key or "\x00" in value:
            raise SandboxError(
                "environment names and values must be NUL-free; names cannot contain ="
            )
        folded = key.casefold()
        if folded in environment_by_folded_key:
            raise SandboxError(f"duplicate case-insensitive environment name: {key}")
        environment_by_folded_key[folded] = (key, value)
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    defaults = {
        "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"),
        "PATH": str(Path(system_root) / "System32"),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "SystemRoot": system_root,
        "HOME": str(scratch),
        "HOMEDRIVE": scratch.drive,
        "HOMEPATH": str(scratch)[len(scratch.drive) :],
        "USERPROFILE": str(scratch),
        "LOCALAPPDATA": str(scratch),
        "APPDATA": str(scratch),
        "TEMP": str(scratch),
        "TMP": str(scratch),
        "WINDIR": system_root,
    }
    for key, value in defaults.items():
        environment_by_folded_key.setdefault(key.casefold(), (key, value))
    environment = tuple(
        sorted(
            environment_by_folded_key.values(),
            key=lambda item: (item[0].casefold(), item[0]),
        )
    )

    profile_name = request.profile_name or f"{_PROFILE_PREFIX}{uuid.uuid4().hex}"
    if not profile_name.startswith(_PROFILE_PREFIX) or len(profile_name) > 64:
        raise SandboxError(
            f"invalid or non-namespaced AppContainer profile name: {profile_name}"
        )
    if any(
        not (character.isascii() and (character.isalnum() or character in ".-"))
        for character in profile_name
    ):
        raise SandboxError(
            f"AppContainer profile name contains an unsafe character: {profile_name}"
        )

    return _ValidatedRequest(
        request=request,
        command=tuple(request.command),
        executable=executable,
        grants=tuple(grants),
        acl_targets=acl_targets,
        grant_entries=tuple(entries),
        scratch=scratch,
        probes=tuple(probes),
        profile_name=profile_name,
        environment=environment,
    )


def _manifest_hash(entries: tuple[_SecurityDescriptorSnapshot, ...]) -> str:
    manifest = [
        {
            "path": snapshot.path,
            "protected": snapshot.protected,
            "security_descriptor_sha256": hashlib.sha256(snapshot.payload).hexdigest(),
        }
        for snapshot in sorted(entries, key=lambda item: os.path.normcase(item.path))
    ]
    payload = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


class _WindowsApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise UnsupportedPlatformError(
                "AppContainer sandboxing is available only on Windows"
            )
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.userenv = ctypes.WinDLL("userenv", use_last_error=True)
        self._bind()

    def _bind(self) -> None:
        k32, adv, user = self.kernel32, self.advapi32, self.userenv
        user.CreateAppContainerProfile.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(_SID_AND_ATTRIBUTES),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
        )
        user.CreateAppContainerProfile.restype = ctypes.c_long
        user.DeriveAppContainerSidFromAppContainerName.argtypes = (
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.LPVOID),
        )
        user.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
        user.DeleteAppContainerProfile.argtypes = (wintypes.LPCWSTR,)
        user.DeleteAppContainerProfile.restype = ctypes.c_long
        adv.FreeSid.argtypes = (wintypes.LPVOID,)
        adv.FreeSid.restype = wintypes.LPVOID
        adv.EqualSid.argtypes = (wintypes.LPVOID, wintypes.LPVOID)
        adv.EqualSid.restype = wintypes.BOOL
        adv.ConvertSidToStringSidW.argtypes = (
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.LPWSTR),
        )
        adv.ConvertSidToStringSidW.restype = wintypes.BOOL
        adv.GetSidSubAuthorityCount.argtypes = (wintypes.LPVOID,)
        adv.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
        adv.GetSidSubAuthority.argtypes = (wintypes.LPVOID, wintypes.DWORD)
        adv.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
        adv.OpenProcessToken.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        )
        adv.OpenProcessToken.restype = wintypes.BOOL
        adv.GetTokenInformation.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        )
        adv.GetTokenInformation.restype = wintypes.BOOL
        adv.DuplicateTokenEx.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        )
        adv.DuplicateTokenEx.restype = wintypes.BOOL
        adv.SetThreadToken.argtypes = (
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.HANDLE,
        )
        adv.SetThreadToken.restype = wintypes.BOOL
        adv.RevertToSelf.argtypes = ()
        adv.RevertToSelf.restype = wintypes.BOOL

        adv.GetFileSecurityW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        )
        adv.GetFileSecurityW.restype = wintypes.BOOL
        adv.GetSecurityDescriptorControl.argtypes = (
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        )
        adv.GetSecurityDescriptorControl.restype = wintypes.BOOL
        adv.GetSecurityDescriptorDacl.argtypes = (
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.BOOL),
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.BOOL),
        )
        adv.GetSecurityDescriptorDacl.restype = wintypes.BOOL
        adv.GetAclInformation.argtypes = (
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        adv.GetAclInformation.restype = wintypes.BOOL
        adv.GetAce.argtypes = (
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
        )
        adv.GetAce.restype = wintypes.BOOL
        adv.SetEntriesInAclW.argtypes = (
            wintypes.ULONG,
            ctypes.POINTER(_EXPLICIT_ACCESS_W),
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.LPVOID),
        )
        adv.SetEntriesInAclW.restype = wintypes.DWORD
        adv.SetNamedSecurityInfoW.argtypes = (
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.LPVOID,
        )
        adv.SetNamedSecurityInfoW.restype = wintypes.DWORD
        adv.SetFileSecurityW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
        )
        adv.SetFileSecurityW.restype = wintypes.BOOL

        k32.GetFileAttributesW.argtypes = (wintypes.LPCWSTR,)
        k32.GetFileAttributesW.restype = wintypes.DWORD
        k32.LocalFree.argtypes = (wintypes.HLOCAL,)
        k32.LocalFree.restype = wintypes.HLOCAL
        k32.InitializeProcThreadAttributeList.argtypes = (
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        )
        k32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        k32.UpdateProcThreadAttribute.argtypes = (
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.c_size_t,
            wintypes.LPVOID,
            ctypes.c_size_t,
            wintypes.LPVOID,
            ctypes.POINTER(ctypes.c_size_t),
        )
        k32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        k32.DeleteProcThreadAttributeList.argtypes = (wintypes.LPVOID,)
        k32.DeleteProcThreadAttributeList.restype = None
        k32.CreatePipe.argtypes = (
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
            wintypes.DWORD,
        )
        k32.CreatePipe.restype = wintypes.BOOL
        k32.SetHandleInformation.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        k32.SetHandleInformation.restype = wintypes.BOOL
        k32.CreateFileW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateProcessW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPCWSTR,
            ctypes.POINTER(_STARTUPINFOW),
            ctypes.POINTER(_PROCESS_INFORMATION),
        )
        k32.CreateProcessW.restype = wintypes.BOOL
        k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.QueryInformationJobObject.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        )
        k32.QueryInformationJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.IsProcessInJob.argtypes = (
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        )
        k32.IsProcessInJob.restype = wintypes.BOOL
        k32.GetProcessId.argtypes = (wintypes.HANDLE,)
        k32.GetProcessId.restype = wintypes.DWORD
        k32.ResumeThread.argtypes = (wintypes.HANDLE,)
        k32.ResumeThread.restype = wintypes.DWORD
        k32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.WaitForSingleObject.restype = wintypes.DWORD
        k32.GetExitCodeProcess.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        )
        k32.GetExitCodeProcess.restype = wintypes.BOOL
        k32.ReadFile.argtypes = (
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        )
        k32.ReadFile.restype = wintypes.BOOL
        k32.WriteFile.argtypes = (
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        )
        k32.WriteFile.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        k32.CloseHandle.restype = wintypes.BOOL

    def create_profile(self, name: str) -> tuple[int, int, str]:
        created = wintypes.LPVOID()
        result = self.userenv.CreateAppContainerProfile(
            name,
            name,
            "GeoTarget EXP-LOCAL-003 ephemeral sandbox",
            None,
            0,
            ctypes.byref(created),
        )
        if result != 0:
            raise _hresult_error("CreateAppContainerProfile failed", result)
        derived = wintypes.LPVOID()
        result = self.userenv.DeriveAppContainerSidFromAppContainerName(
            name, ctypes.byref(derived)
        )
        if result != 0:
            self.userenv.DeleteAppContainerProfile(name)
            self.advapi32.FreeSid(created)
            raise _hresult_error(
                "DeriveAppContainerSidFromAppContainerName failed", result
            )
        if not self.advapi32.EqualSid(created, derived):
            self.advapi32.FreeSid(derived)
            self.advapi32.FreeSid(created)
            self.userenv.DeleteAppContainerProfile(name)
            raise SandboxError(
                "created and independently derived AppContainer SIDs differ"
            )
        sid_text = wintypes.LPWSTR()
        if not self.advapi32.ConvertSidToStringSidW(created, ctypes.byref(sid_text)):
            self.advapi32.FreeSid(derived)
            self.advapi32.FreeSid(created)
            self.userenv.DeleteAppContainerProfile(name)
            raise _win_error("ConvertSidToStringSidW failed")
        try:
            text = sid_text.value
        finally:
            self.kernel32.LocalFree(sid_text)
        return _handle_value(created), _handle_value(derived), text

    def delete_profile(self, name: str) -> None:
        result = self.userenv.DeleteAppContainerProfile(name)
        if result != 0:
            raise _hresult_error("DeleteAppContainerProfile failed", result)

    def free_sid(self, sid: int | None) -> None:
        if sid:
            self.advapi32.FreeSid(ctypes.c_void_p(sid))

    def snapshot_dacl(self, path: Path) -> _SecurityDescriptorSnapshot:
        attributes = self.kernel32.GetFileAttributesW(str(path))
        if attributes == _INVALID_FILE_ATTRIBUTES:
            raise _win_error(f"GetFileAttributesW failed for {path}")
        if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise SandboxError(f"ACL target is a reparse point: {path}")
        needed = wintypes.DWORD()
        ctypes.set_last_error(0)
        self.advapi32.GetFileSecurityW(
            str(path), _DACL_SECURITY_INFORMATION, None, 0, ctypes.byref(needed)
        )
        if (
            ctypes.get_last_error()
            not in {_ERROR_INSUFFICIENT_BUFFER, _ERROR_BAD_LENGTH}
            or needed.value == 0
        ):
            raise _win_error(f"GetFileSecurityW size query failed for {path}")
        buffer = ctypes.create_string_buffer(needed.value)
        if not self.advapi32.GetFileSecurityW(
            str(path),
            _DACL_SECURITY_INFORMATION,
            buffer,
            needed.value,
            ctypes.byref(needed),
        ):
            raise _win_error(f"GetFileSecurityW failed for {path}")
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not self.advapi32.GetSecurityDescriptorControl(
            buffer, ctypes.byref(control), ctypes.byref(revision)
        ):
            raise _win_error(f"GetSecurityDescriptorControl failed for {path}")
        return _SecurityDescriptorSnapshot(
            str(path),
            bytes(buffer.raw[: needed.value]),
            bool(control.value & _SE_DACL_PROTECTED),
        )

    def grant_sid(
        self,
        snapshot: _SecurityDescriptorSnapshot,
        sid: int,
        access_mask: int,
        inheritance: int,
    ) -> None:
        descriptor = ctypes.create_string_buffer(snapshot.payload)
        present = wintypes.BOOL()
        old_acl = wintypes.LPVOID()
        defaulted = wintypes.BOOL()
        if not self.advapi32.GetSecurityDescriptorDacl(
            descriptor,
            ctypes.byref(present),
            ctypes.byref(old_acl),
            ctypes.byref(defaulted),
        ):
            raise _win_error(f"GetSecurityDescriptorDacl failed for {snapshot.path}")
        if not present.value:
            raise SandboxError(
                f"ACL target has no DACL and is refused fail-closed: {snapshot.path}"
            )
        access = _EXPLICIT_ACCESS_W()
        access.grfAccessPermissions = access_mask
        access.grfAccessMode = _GRANT_ACCESS
        access.grfInheritance = inheritance
        access.Trustee.pMultipleTrustee = None
        access.Trustee.MultipleTrusteeOperation = 0
        access.Trustee.TrusteeForm = _TRUSTEE_IS_SID
        access.Trustee.TrusteeType = _TRUSTEE_IS_USER
        access.Trustee.ptstrName = ctypes.c_void_p(sid)
        new_acl = wintypes.LPVOID()
        result = self.advapi32.SetEntriesInAclW(
            1, ctypes.byref(access), old_acl, ctypes.byref(new_acl)
        )
        if result != 0:
            raise _win_error(f"SetEntriesInAclW failed for {snapshot.path}", result)
        try:
            result = self.advapi32.SetNamedSecurityInfoW(
                snapshot.path,
                _SE_FILE_OBJECT,
                _DACL_SECURITY_INFORMATION,
                None,
                None,
                new_acl,
                None,
            )
            if result != 0:
                raise _win_error(
                    f"SetNamedSecurityInfoW failed for {snapshot.path}", result
                )
        finally:
            self.kernel32.LocalFree(new_acl)

    def revoke_sid(self, path: Path, sid: int) -> None:
        """Remove every allowed/denied ACE for the ephemeral package SID."""

        snapshot = self.snapshot_dacl(path)
        descriptor = ctypes.create_string_buffer(snapshot.payload)
        present = wintypes.BOOL()
        old_acl = wintypes.LPVOID()
        defaulted = wintypes.BOOL()
        if not self.advapi32.GetSecurityDescriptorDacl(
            descriptor,
            ctypes.byref(present),
            ctypes.byref(old_acl),
            ctypes.byref(defaulted),
        ):
            raise _win_error(f"GetSecurityDescriptorDacl revoke failed for {path}")
        if not present.value:
            raise SandboxCleanupError(f"ACL revoke target has no DACL: {path}")
        access = _EXPLICIT_ACCESS_W()
        access.grfAccessPermissions = 0
        access.grfAccessMode = _REVOKE_ACCESS
        access.grfInheritance = _NO_INHERITANCE
        access.Trustee.pMultipleTrustee = None
        access.Trustee.MultipleTrusteeOperation = 0
        access.Trustee.TrusteeForm = _TRUSTEE_IS_SID
        access.Trustee.TrusteeType = _TRUSTEE_IS_USER
        access.Trustee.ptstrName = ctypes.c_void_p(sid)
        new_acl = wintypes.LPVOID()
        result = self.advapi32.SetEntriesInAclW(
            1, ctypes.byref(access), old_acl, ctypes.byref(new_acl)
        )
        if result != 0:
            raise _win_error(f"SetEntriesInAclW revoke failed for {path}", result)
        try:
            result = self.advapi32.SetNamedSecurityInfoW(
                str(path),
                _SE_FILE_OBJECT,
                _DACL_SECURITY_INFORMATION,
                None,
                None,
                new_acl,
                None,
            )
            if result != 0:
                raise _win_error(
                    f"SetNamedSecurityInfoW revoke failed for {path}", result
                )
        finally:
            self.kernel32.LocalFree(new_acl)

    def restore_dacl(
        self, snapshot: _SecurityDescriptorSnapshot
    ) -> _SecurityDescriptorSnapshot:
        descriptor = ctypes.create_string_buffer(snapshot.payload)
        protection = (
            _PROTECTED_DACL_SECURITY_INFORMATION
            if snapshot.protected
            else _UNPROTECTED_DACL_SECURITY_INFORMATION
        )
        if not self.advapi32.SetFileSecurityW(
            snapshot.path, _DACL_SECURITY_INFORMATION | protection, descriptor
        ):
            raise _win_error(f"SetFileSecurityW restore failed for {snapshot.path}")
        restored = self.snapshot_dacl(Path(snapshot.path))
        if (
            restored.payload != snapshot.payload
            or restored.protected != snapshot.protected
        ):
            raise SandboxCleanupError(
                f"security descriptor was not restored exactly: {snapshot.path}"
            )
        return restored

    def descriptor_has_allowed_sid(
        self, snapshot: _SecurityDescriptorSnapshot, sid: int
    ) -> bool:
        """Return whether a DACL contains an ACCESS_ALLOWED ACE for ``sid``."""

        descriptor = ctypes.create_string_buffer(snapshot.payload)
        present = wintypes.BOOL()
        acl = wintypes.LPVOID()
        defaulted = wintypes.BOOL()
        if not self.advapi32.GetSecurityDescriptorDacl(
            descriptor,
            ctypes.byref(present),
            ctypes.byref(acl),
            ctypes.byref(defaulted),
        ):
            raise _win_error(
                f"GetSecurityDescriptorDacl cleanup check failed for {snapshot.path}"
            )
        if not present.value or not acl:
            return False
        information = _ACL_SIZE_INFORMATION()
        if not self.advapi32.GetAclInformation(
            acl,
            ctypes.byref(information),
            ctypes.sizeof(information),
            _ACL_SIZE_INFORMATION_CLASS,
        ):
            raise _win_error(f"GetAclInformation failed for {snapshot.path}")
        for index in range(information.AceCount):
            ace = wintypes.LPVOID()
            if not self.advapi32.GetAce(acl, index, ctypes.byref(ace)):
                raise _win_error(f"GetAce({index}) failed for {snapshot.path}")
            address = ctypes.cast(ace, ctypes.c_void_p).value
            if address is None:
                raise SandboxCleanupError(f"null ACE in DACL for {snapshot.path}")
            header = ctypes.cast(address, ctypes.POINTER(_ACE_HEADER)).contents
            if header.AceType != _ACCESS_ALLOWED_ACE_TYPE:
                continue
            sid_offset = ctypes.sizeof(_ACE_HEADER) + ctypes.sizeof(wintypes.DWORD)
            if header.AceSize <= sid_offset:
                raise SandboxCleanupError(f"truncated allowed ACE for {snapshot.path}")
            ace_sid = ctypes.c_void_p(address + sid_offset)
            if self.advapi32.EqualSid(ace_sid, ctypes.c_void_p(sid)):
                return True
        return False

    def _create_pipe(self) -> tuple[int, int]:
        read = wintypes.HANDLE()
        write = wintypes.HANDLE()
        attributes = _SECURITY_ATTRIBUTES(
            ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True
        )
        if not self.kernel32.CreatePipe(
            ctypes.byref(read), ctypes.byref(write), ctypes.byref(attributes), 0
        ):
            raise _win_error("CreatePipe failed")
        read_value, write_value = _handle_value(read), _handle_value(write)
        if not self.kernel32.SetHandleInformation(read, _HANDLE_FLAG_INHERIT, 0):
            self.close_handle(read_value)
            self.close_handle(write_value)
            raise _win_error("SetHandleInformation failed")
        return read_value, write_value

    def _create_stdin_pipe(self) -> tuple[int, int]:
        read = wintypes.HANDLE()
        write = wintypes.HANDLE()
        attributes = _SECURITY_ATTRIBUTES(
            ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True
        )
        if not self.kernel32.CreatePipe(
            ctypes.byref(read), ctypes.byref(write), ctypes.byref(attributes), 0
        ):
            raise _win_error("CreatePipe(stdin) failed")
        read_value, write_value = _handle_value(read), _handle_value(write)
        if not self.kernel32.SetHandleInformation(write, _HANDLE_FLAG_INHERIT, 0):
            self.close_handle(read_value)
            self.close_handle(write_value)
            raise _win_error("SetHandleInformation(stdin) failed")
        return read_value, write_value

    def _create_stdin(self) -> int:
        handle = self.kernel32.CreateFileW(
            "NUL",
            _GENERIC_READ,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_EXISTING,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        value = _handle_value(handle)
        if value == _INVALID_HANDLE_VALUE:
            raise _win_error("CreateFileW(NUL) failed")
        if not self.kernel32.SetHandleInformation(
            handle, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT
        ):
            self.close_handle(value)
            raise _win_error("SetHandleInformation(NUL) failed")
        return value

    def _attribute_list(
        self, sid: int, inherited_handles: tuple[int, int, int], job: int
    ) -> tuple[
        ctypes.Array[ctypes.c_char],
        _SECURITY_CAPABILITIES,
        object,
        object,
    ]:
        size = ctypes.c_size_t()
        ctypes.set_last_error(0)
        self.kernel32.InitializeProcThreadAttributeList(None, 3, 0, ctypes.byref(size))
        if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER or size.value == 0:
            raise _win_error("InitializeProcThreadAttributeList size query failed")
        storage = ctypes.create_string_buffer(size.value)
        if not self.kernel32.InitializeProcThreadAttributeList(
            storage, 3, 0, ctypes.byref(size)
        ):
            raise _win_error("InitializeProcThreadAttributeList failed")
        capabilities = _SECURITY_CAPABILITIES(ctypes.c_void_p(sid), None, 0, 0)
        if not self.kernel32.UpdateProcThreadAttribute(
            storage,
            0,
            _PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(capabilities),
            ctypes.sizeof(capabilities),
            None,
            None,
        ):
            self.kernel32.DeleteProcThreadAttributeList(storage)
            raise _win_error("UpdateProcThreadAttribute(SECURITY_CAPABILITIES) failed")
        handle_array_type = wintypes.HANDLE * len(inherited_handles)
        handle_array = handle_array_type(
            *(wintypes.HANDLE(item) for item in inherited_handles)
        )
        if not self.kernel32.UpdateProcThreadAttribute(
            storage,
            0,
            _PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            handle_array,
            ctypes.sizeof(handle_array),
            None,
            None,
        ):
            self.kernel32.DeleteProcThreadAttributeList(storage)
            raise _win_error("UpdateProcThreadAttribute(HANDLE_LIST) failed")
        job_array_type = wintypes.HANDLE * 1
        job_array = job_array_type(wintypes.HANDLE(job))
        if not self.kernel32.UpdateProcThreadAttribute(
            storage,
            0,
            _PROC_THREAD_ATTRIBUTE_JOB_LIST,
            job_array,
            ctypes.sizeof(job_array),
            None,
            None,
        ):
            self.kernel32.DeleteProcThreadAttributeList(storage)
            raise _win_error("UpdateProcThreadAttribute(JOB_LIST) failed")
        return storage, capabilities, handle_array, job_array

    @staticmethod
    def _environment_block(
        environment: tuple[tuple[str, str], ...],
    ) -> ctypes.Array[ctypes.c_wchar]:
        return ctypes.create_unicode_buffer(
            "\0".join(f"{key}={value}" for key, value in environment) + "\0\0"
        )

    def create_job(self, max_processes: int) -> int:
        job = self.kernel32.CreateJobObjectW(None, None)
        value = _handle_value(job)
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_ACTIVE_PROCESS | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        limits.BasicLimitInformation.ActiveProcessLimit = max_processes
        if not self.kernel32.SetInformationJobObject(
            job,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            self.close_handle(value)
            raise _win_error("SetInformationJobObject failed")
        return value

    def create_suspended_process(
        self,
        validated: _ValidatedRequest,
        sid: int,
        job: int,
        stdin_handle: int,
        stdout_handle: int,
        stderr_handle: int,
    ) -> tuple[int, int]:
        storage, capabilities, handle_array, job_array = self._attribute_list(
            sid, (stdin_handle, stdout_handle, stderr_handle), job
        )
        # The attribute list stores pointers to these objects.  Keep all three
        # alive through CreateProcessW as required by UpdateProcThreadAttribute.
        keepalive = (capabilities, handle_array, job_array)
        startup = _STARTUPINFOEXW()
        startup.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
        startup.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput = wintypes.HANDLE(stdin_handle)
        startup.StartupInfo.hStdOutput = wintypes.HANDLE(stdout_handle)
        startup.StartupInfo.hStdError = wintypes.HANDLE(stderr_handle)
        startup.lpAttributeList = ctypes.cast(storage, wintypes.LPVOID)
        process = _PROCESS_INFORMATION()
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline(validated.command)
        )
        environment = self._environment_block(validated.environment)
        try:
            created = self.kernel32.CreateProcessW(
                str(validated.executable),
                command_line,
                None,
                None,
                True,
                _CREATE_SUSPENDED
                | _CREATE_UNICODE_ENVIRONMENT
                | _EXTENDED_STARTUPINFO_PRESENT
                | _CREATE_NO_WINDOW,
                environment,
                str(validated.scratch),
                ctypes.byref(startup.StartupInfo),
                ctypes.byref(process),
            )
            if not created:
                raise _win_error("CreateProcessW(AppContainer) failed")
            del keepalive
            return _handle_value(process.hProcess), _handle_value(process.hThread)
        finally:
            self.kernel32.DeleteProcThreadAttributeList(storage)

    def _token_information(self, token: int, information_class: int) -> object:
        needed = wintypes.DWORD()
        ctypes.set_last_error(0)
        self.advapi32.GetTokenInformation(
            wintypes.HANDLE(token),
            information_class,
            None,
            0,
            ctypes.byref(needed),
        )
        if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER or needed.value == 0:
            raise _win_error(
                f"GetTokenInformation({information_class}) size query failed"
            )
        buffer = ctypes.create_string_buffer(needed.value)
        if not self.advapi32.GetTokenInformation(
            wintypes.HANDLE(token),
            information_class,
            buffer,
            needed.value,
            ctypes.byref(needed),
        ):
            raise _win_error(f"GetTokenInformation({information_class}) failed")
        return buffer

    def _token_fixed_information(
        self, token: int, information_class: int, value_type: type[ctypes.Structure]
    ) -> ctypes.Structure:
        value = value_type()
        returned = wintypes.DWORD()
        if not self.advapi32.GetTokenInformation(
            wintypes.HANDLE(token),
            information_class,
            ctypes.byref(value),
            ctypes.sizeof(value),
            ctypes.byref(returned),
        ):
            raise _win_error(f"GetTokenInformation({information_class}) failed")
        if returned.value != ctypes.sizeof(value):
            raise SandboxError(
                f"GetTokenInformation({information_class}) returned an unexpected size"
            )
        return value

    def _probe_with_token(
        self, token: int, probes: tuple[AccessProbe, ...]
    ) -> tuple[AccessProbeObservation, ...]:
        if not probes:
            return ()
        specifications = tuple(
            (
                str(probe.path),
                probe.expected,
                _FILE_FLAG_BACKUP_SEMANTICS
                if probe.path.is_dir()
                else _FILE_ATTRIBUTE_NORMAL,
            )
            for probe in probes
        )
        impersonation = wintypes.HANDLE()
        if not self.advapi32.DuplicateTokenEx(
            wintypes.HANDLE(token),
            _TOKEN_QUERY | _TOKEN_IMPERSONATE,
            None,
            _SECURITY_IMPERSONATION,
            _TOKEN_IMPERSONATION,
            ctypes.byref(impersonation),
        ):
            raise _win_error("DuplicateTokenEx(child AppContainer token) failed")
        impersonation_value = _handle_value(impersonation)
        observations: list[AccessProbeObservation] = []
        impersonating = False
        try:
            if not self.advapi32.SetThreadToken(None, impersonation):
                raise _win_error("SetThreadToken(child AppContainer token) failed")
            impersonating = True
            for target, expected, flags in specifications:
                ctypes.set_last_error(0)
                handle = self.kernel32.CreateFileW(
                    target,
                    _GENERIC_READ,
                    _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
                    None,
                    _OPEN_EXISTING,
                    flags,
                    None,
                )
                handle_value = ctypes.cast(handle, ctypes.c_void_p).value
                if handle_value == _INVALID_HANDLE_VALUE:
                    error = ctypes.get_last_error()
                    observed = (
                        PathProbeStatus.DENIED
                        if error == _ERROR_ACCESS_DENIED
                        else PathProbeStatus.ERROR
                    )
                else:
                    error = 0
                    observed = PathProbeStatus.ALLOWED
                    self.close_handle(handle_value)
                observations.append(
                    AccessProbeObservation(target, expected, observed, error)
                )
        finally:
            if impersonating and not self.advapi32.RevertToSelf():
                # Continuing under a sandbox token would make all cleanup
                # observations unreliable.  There is no safe recovery here.
                self.close_handle(impersonation_value)
                raise SandboxCleanupError("RevertToSelf failed after access probes")
            self.close_handle(impersonation_value)
        for observation in observations:
            if observation.observed is not observation.expected:
                raise SandboxError(
                    "pre-resume child-token access probe differs: "
                    f"{observation.path} expected={observation.expected} "
                    f"observed={observation.observed} winerror={observation.winerror}"
                )
        return tuple(observations)

    def verify_process_security(
        self,
        process: int,
        expected_sid: int,
        job: int,
        probes: tuple[AccessProbe, ...],
    ) -> _SecurityObservation:
        token_handle = wintypes.HANDLE()
        if not self.advapi32.OpenProcessToken(
            wintypes.HANDLE(process),
            _TOKEN_QUERY | _TOKEN_DUPLICATE,
            ctypes.byref(token_handle),
        ):
            raise _win_error("OpenProcessToken(AppContainer child) failed")
        token = _handle_value(token_handle)
        try:
            appcontainer_buffer = self._token_information(token, _TOKEN_IS_APPCONTAINER)
            is_appcontainer = ctypes.cast(
                appcontainer_buffer, ctypes.POINTER(wintypes.DWORD)
            ).contents.value
            if is_appcontainer != 1:
                raise SandboxError("child token is not an AppContainer token")

            sid_buffer = self._token_information(token, _TOKEN_APPCONTAINER_SID)
            token_sid = ctypes.cast(
                sid_buffer, ctypes.POINTER(_TOKEN_APPCONTAINER_INFORMATION)
            ).contents.TokenAppContainer
            if not token_sid or not self.advapi32.EqualSid(
                token_sid, ctypes.c_void_p(expected_sid)
            ):
                raise SandboxError("child token AppContainer SID differs")

            capability_buffer = self._token_information(token, _TOKEN_CAPABILITIES)
            capability_count = ctypes.cast(
                capability_buffer, ctypes.POINTER(wintypes.DWORD)
            ).contents.value
            if capability_count != 0:
                raise SandboxError("child AppContainer token has capabilities")

            integrity_buffer = self._token_information(token, _TOKEN_INTEGRITY_LEVEL)
            integrity_sid = ctypes.cast(
                integrity_buffer, ctypes.POINTER(_TOKEN_MANDATORY_LABEL)
            ).contents.Label.Sid
            subauthority_count_pointer = self.advapi32.GetSidSubAuthorityCount(
                integrity_sid
            )
            if not subauthority_count_pointer:
                raise _win_error("GetSidSubAuthorityCount(integrity SID) failed")
            subauthority_count = subauthority_count_pointer.contents.value
            if subauthority_count == 0:
                raise SandboxError("child integrity SID has no subauthority")
            integrity_pointer = self.advapi32.GetSidSubAuthority(
                integrity_sid, subauthority_count - 1
            )
            if not integrity_pointer:
                raise _win_error("GetSidSubAuthority(integrity SID) failed")
            integrity_rid = integrity_pointer.contents.value
            if integrity_rid != _SECURITY_MANDATORY_LOW_RID:
                raise SandboxError(
                    f"child integrity level is not Low: 0x{integrity_rid:08x}"
                )

            elevation = self._token_fixed_information(
                token, _TOKEN_ELEVATION, _TOKEN_ELEVATION_STRUCT
            )
            elevated = elevation.TokenIsElevated  # type: ignore[attr-defined]
            if elevated != 0:
                raise SandboxError("child AppContainer token is elevated")

            in_job = wintypes.BOOL()
            if not self.kernel32.IsProcessInJob(
                wintypes.HANDLE(process), wintypes.HANDLE(job), ctypes.byref(in_job)
            ):
                raise _win_error("IsProcessInJob failed")
            if not in_job.value:
                raise SandboxError("child was not atomically assigned to the Job")
            limits = self.query_job_limits(job)
            expected_flags = (
                _JOB_OBJECT_LIMIT_ACTIVE_PROCESS | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            observed_flags = limits.BasicLimitInformation.LimitFlags
            if observed_flags != expected_flags:
                raise SandboxError(
                    "Job limit flags differ from non-breakaway kill-on-close policy"
                )
            observations = self._probe_with_token(token, probes)
            process_id = self.kernel32.GetProcessId(wintypes.HANDLE(process))
            if process_id == 0:
                raise _win_error("GetProcessId failed")
            return _SecurityObservation(
                process_id=process_id,
                integrity_rid=integrity_rid,
                capability_count=capability_count,
                access_probes=observations,
                job_limit_flags=observed_flags,
            )
        finally:
            self.close_handle(token)

    def resume(self, thread: int) -> None:
        if self.kernel32.ResumeThread(wintypes.HANDLE(thread)) == _INFINITE:
            raise _win_error("ResumeThread failed")

    def query_job(self, job: int) -> _JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION:
        accounting = _JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION()
        if not self.kernel32.QueryInformationJobObject(
            wintypes.HANDLE(job),
            _JOB_OBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            None,
        ):
            raise _win_error("QueryInformationJobObject failed")
        return accounting

    def query_job_limits(self, job: int) -> _JOBOBJECT_EXTENDED_LIMIT_INFORMATION:
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not self.kernel32.QueryInformationJobObject(
            wintypes.HANDLE(job),
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
            None,
        ):
            raise _win_error("QueryInformationJobObject(limits) failed")
        return limits

    def terminate_job(self, job: int) -> None:
        if not self.kernel32.TerminateJobObject(
            wintypes.HANDLE(job), _JOB_TERMINATION_CODE
        ):
            raise _win_error("TerminateJobObject failed")

    def process_exit_code(self, process: int) -> int:
        exit_code = wintypes.DWORD()
        if not self.kernel32.GetExitCodeProcess(
            wintypes.HANDLE(process), ctypes.byref(exit_code)
        ):
            raise _win_error("GetExitCodeProcess failed")
        return exit_code.value

    def read_pipe(self, handle: int) -> bytes | None:
        buffer = ctypes.create_string_buffer(64 * 1024)
        read = wintypes.DWORD()
        if not self.kernel32.ReadFile(
            wintypes.HANDLE(handle), buffer, len(buffer), ctypes.byref(read), None
        ):
            error = ctypes.get_last_error()
            if error in {_ERROR_BROKEN_PIPE, _ERROR_NO_DATA}:
                return None
            raise _win_error("ReadFile(pipe) failed", error)
        if read.value == 0:
            return None
        return bytes(buffer.raw[: read.value])

    def write_pipe(self, handle: int, payload: bytes) -> None:
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + 64 * 1024]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not self.kernel32.WriteFile(
                wintypes.HANDLE(handle),
                buffer,
                len(chunk),
                ctypes.byref(written),
                None,
            ):
                raise _win_error("WriteFile(pre-exit ACK) failed")
            if written.value == 0:
                raise SandboxError("WriteFile(pre-exit ACK) made no progress")
            offset += written.value

    def close_handle(self, handle: int | None) -> None:
        if handle and handle != _INVALID_HANDLE_VALUE:
            if not self.kernel32.CloseHandle(wintypes.HANDLE(handle)):
                raise _win_error("CloseHandle failed")

    def run(
        self,
        request: SandboxRequest,
        on_preexit: Callable[[bytes, PreexitContext], bytes] | None = None,
    ) -> SandboxResult:
        validated = _validate_request(request)
        if (request.preexit_payload_limit_bytes is None) != (on_preexit is None):
            raise SandboxError(
                "pre-exit frame limit and trusted callback must be supplied together"
            )
        return self._run_validated(validated, on_preexit)

    def _run_validated(
        self,
        validated: _ValidatedRequest,
        on_preexit: Callable[[bytes, PreexitContext], bytes] | None,
    ) -> SandboxResult:
        created_sid: int | None = None
        derived_sid: int | None = None
        profile_created = False
        profile_deleted = False
        baseline_snapshots: list[_SecurityDescriptorSnapshot] = []
        baseline_by_path: dict[str, _SecurityDescriptorSnapshot] = {}
        root_snapshots: list[_SecurityDescriptorSnapshot] = []
        restored_snapshots: list[_SecurityDescriptorSnapshot] = []
        scratch_snapshot: _SecurityDescriptorSnapshot | None = None
        job: int | None = None
        process: int | None = None
        thread: int | None = None
        stdin_handle: int | None = None
        stdin_parent: int | None = None
        stdout_read: int | None = None
        stdout_write: int | None = None
        stderr_read: int | None = None
        stderr_write: int | None = None
        stdout_reader: _PipeReader | None = None
        stderr_reader: _PipeReader | None = None
        cleanup_errors: list[str] = []
        package_sid = ""
        security_observation: _SecurityObservation | None = None
        preexit_receipt: PreexitReceipt | None = None
        result_fields: dict[str, object] | None = None
        start_ns = time.perf_counter_ns()
        try:
            created_sid, derived_sid, package_sid = self.create_profile(
                validated.profile_name
            )
            profile_created = True
            baseline_paths = (*validated.grant_entries, validated.scratch)
            baseline_snapshots.extend(
                self.snapshot_dacl(path) for path in baseline_paths
            )
            baseline_by_path = {
                os.path.normcase(snapshot.path): snapshot
                for snapshot in baseline_snapshots
            }
            for target in validated.acl_targets:
                snapshot = baseline_by_path[os.path.normcase(str(target.path))]
                root_snapshots.append(snapshot)
                self.grant_sid(
                    snapshot,
                    created_sid,
                    _FILE_GENERIC_READ | _FILE_GENERIC_EXECUTE,
                    target.inheritance,
                )
            scratch_snapshot = baseline_by_path[
                os.path.normcase(str(validated.scratch))
            ]
            root_snapshots.append(scratch_snapshot)
            self.grant_sid(
                scratch_snapshot,
                created_sid,
                _FILE_ALL_ACCESS,
                _SUB_CONTAINERS_AND_OBJECTS_INHERIT,
            )

            stdout_read, stdout_write = self._create_pipe()
            stderr_read, stderr_write = self._create_pipe()
            if validated.request.preexit_payload_limit_bytes is None:
                stdin_handle = self._create_stdin()
            else:
                stdin_handle, stdin_parent = self._create_stdin_pipe()
            job = self.create_job(validated.request.max_processes)
            process, thread = self.create_suspended_process(
                validated,
                created_sid,
                job,
                stdin_handle,
                stdout_write,
                stderr_write,
            )
            security_observation = self.verify_process_security(
                process, created_sid, job, validated.probes
            )
            self.close_handle(stdin_handle)
            stdin_handle = None
            self.close_handle(stdout_write)
            stdout_write = None
            self.close_handle(stderr_write)
            stderr_write = None
            stdout_reader = _PipeReader(
                self,
                stdout_read,
                validated.request.stdout_limit_bytes,
                "stdout",
                frame_limit=validated.request.preexit_payload_limit_bytes,
            )
            stderr_reader = _PipeReader(
                self, stderr_read, validated.request.stderr_limit_bytes, "stderr"
            )
            stdout_reader.start()
            stderr_reader.start()
            self.resume(thread)

            reason = TerminationReason.COMPLETED
            deadline_ns = time.perf_counter_ns() + int(
                validated.request.timeout_seconds * 1_000_000_000
            )
            terminated = False
            while True:
                accounting = self.query_job(job)
                if accounting.BasicInfo.ActiveProcesses == 0:
                    break
                if stdout_reader.overflow_event.is_set():
                    reason = TerminationReason.STDOUT_LIMIT
                elif stderr_reader.overflow_event.is_set():
                    reason = TerminationReason.STDERR_LIMIT
                elif (
                    validated.request.preexit_payload_limit_bytes is not None
                    and preexit_receipt is None
                    and stdout_reader.frame_event.is_set()
                ):
                    frame_payload, frame_error = stdout_reader.frame()
                    if frame_error is not None:
                        raise SandboxError(frame_error)
                    if frame_payload is None:
                        raise SandboxError(
                            "pre-exit frame event has no complete payload"
                        )
                    if on_preexit is None or stdin_parent is None:
                        raise SandboxError("pre-exit callback/ACK pipe is unavailable")
                    active_before_callback = accounting.BasicInfo.ActiveProcesses
                    root_before_callback = (
                        self.process_exit_code(process) == _STILL_ACTIVE
                    )
                    if active_before_callback < 1 or not root_before_callback:
                        raise SandboxError(
                            "candidate root is not live in its Job at pre-exit: "
                            f"active={active_before_callback} "
                            f"root_active={root_before_callback}"
                        )
                    context = PreexitContext(
                        process_id=security_observation.process_id,
                        active_processes=active_before_callback,
                        root_process_still_active=root_before_callback,
                        payload_sha256=hashlib.sha256(frame_payload).hexdigest(),
                        payload_byte_length=len(frame_payload),
                        observer_elapsed_ns=time.perf_counter_ns() - start_ns,
                    )
                    acknowledgement = on_preexit(frame_payload, context)
                    if (
                        not isinstance(acknowledgement, bytes)
                        or not acknowledgement
                        or len(acknowledgement) > 4096
                    ):
                        raise SandboxError(
                            "trusted pre-exit callback returned an invalid ACK"
                        )
                    after_callback = self.query_job(job).BasicInfo.ActiveProcesses
                    root_before_ack = self.process_exit_code(process) == _STILL_ACTIVE
                    if after_callback != active_before_callback or not root_before_ack:
                        raise SandboxError(
                            "candidate Job changed or root exited before observer released ACK: "
                            f"active={after_callback} root_active={root_before_ack}"
                        )
                    self.write_pipe(stdin_parent, acknowledgement)
                    self.close_handle(stdin_parent)
                    stdin_parent = None
                    preexit_receipt = PreexitReceipt(
                        payload_sha256=context.payload_sha256,
                        payload_byte_length=context.payload_byte_length,
                        ack_sha256=hashlib.sha256(acknowledgement).hexdigest(),
                        ack_byte_length=len(acknowledgement),
                        active_processes_before_callback=active_before_callback,
                        root_active_before_callback=root_before_callback,
                        active_processes_before_ack=after_callback,
                        root_active_before_ack=root_before_ack,
                        callback_completed=True,
                        ack_released=True,
                    )
                    continue
                elif time.perf_counter_ns() >= deadline_ns:
                    reason = TerminationReason.TIMEOUT
                else:
                    time.sleep(0.005)
                    continue
                self.terminate_job(job)
                terminated = True
                break
            if terminated:
                cleanup_deadline = time.perf_counter_ns() + 5_000_000_000
                while self.query_job(job).BasicInfo.ActiveProcesses != 0:
                    if time.perf_counter_ns() >= cleanup_deadline:
                        raise SandboxCleanupError(
                            "Job did not become empty after termination"
                        )
                    time.sleep(0.005)
            accounting = self.query_job(job)
            if accounting.BasicInfo.ActiveProcesses != 0:
                raise SandboxCleanupError("Job was not empty at result boundary")
            exit_code = self.process_exit_code(process)
            if exit_code == _STILL_ACTIVE:
                raise SandboxCleanupError(
                    "main process remained active after Job became empty"
                )
            wall_time_ns = time.perf_counter_ns() - start_ns

            stdout_reader.join(timeout=5.0)
            stderr_reader.join(timeout=5.0)
            if stdout_reader.is_alive() or stderr_reader.is_alive():
                raise SandboxCleanupError("output reader did not observe pipe closure")
            stdout_result = stdout_reader.result()
            stderr_result = stderr_reader.result()
            if stdout_result.error is not None:
                raise SandboxError(f"stdout reader failed: {stdout_result.error}")
            if stderr_result.error is not None:
                raise SandboxError(f"stderr reader failed: {stderr_result.error}")
            if (
                validated.request.preexit_payload_limit_bytes is not None
                and preexit_receipt is None
            ):
                diagnostic = stderr_result.payload[:512].decode(
                    "utf-8", errors="backslashreplace"
                )
                raise SandboxError(
                    "candidate exited without a sealed pre-exit frame and ACK; "
                    f"exit={exit_code} stderr={diagnostic!r}"
                )
            observed_stdout = stdout_result.payload
            if validated.request.preexit_payload_limit_bytes is not None:
                frame_payload, frame_error = stdout_reader.frame()
                if frame_error is not None or frame_payload is None:
                    raise SandboxError(
                        frame_error or "pre-exit stdout frame remained incomplete"
                    )
                expected_frame = struct.pack(">Q", len(frame_payload)) + frame_payload
                if stdout_result.payload != expected_frame:
                    raise SandboxError(
                        "candidate stdout differs from its one closed pre-exit frame"
                    )
                if (
                    preexit_receipt is None
                    or preexit_receipt.payload_sha256
                    != hashlib.sha256(frame_payload).hexdigest()
                ):
                    raise SandboxError("pre-exit receipt differs from final stdout")
                observed_stdout = frame_payload
            # A stream may cross its limit just as the final process exits.
            if reason is TerminationReason.COMPLETED and stdout_result.overflow:
                reason = TerminationReason.STDOUT_LIMIT
            if reason is TerminationReason.COMPLETED and stderr_result.overflow:
                reason = TerminationReason.STDERR_LIMIT
            basic, io = accounting.BasicInfo, accounting.IoInfo
            result_fields = {
                "return_code": exit_code,
                "stdout": observed_stdout,
                "stderr": stderr_result.payload,
                "termination_reason": reason,
                "wall_time_ns": wall_time_ns,
                "total_user_time_100ns": basic.TotalUserTime,
                "total_kernel_time_100ns": basic.TotalKernelTime,
                "total_processes": basic.TotalProcesses,
                "terminated_processes": basic.TotalTerminatedProcesses,
                "read_operation_count": io.ReadOperationCount,
                "write_operation_count": io.WriteOperationCount,
                "other_operation_count": io.OtherOperationCount,
                "read_transfer_count": io.ReadTransferCount,
                "write_transfer_count": io.WriteTransferCount,
                "other_transfer_count": io.OtherTransferCount,
                "preexit": preexit_receipt,
            }
        finally:
            if job is not None:
                try:
                    if self.query_job(job).BasicInfo.ActiveProcesses:
                        self.terminate_job(job)
                        deadline = time.perf_counter_ns() + 5_000_000_000
                        while self.query_job(job).BasicInfo.ActiveProcesses:
                            if time.perf_counter_ns() >= deadline:
                                raise SandboxCleanupError(
                                    "Job remained nonempty during final cleanup"
                                )
                            time.sleep(0.005)
                except BaseException as exc:
                    cleanup_errors.append(f"job cleanup: {exc}")
            for handle in (
                stdin_handle,
                stdin_parent,
                stdout_write,
                stderr_write,
                stdout_read,
                stderr_read,
                thread,
                process,
                job,
            ):
                try:
                    self.close_handle(handle)
                except BaseException as exc:
                    cleanup_errors.append(f"handle cleanup: {exc}")
            try:
                _empty_scratch(validated.scratch)
            except BaseException as exc:
                cleanup_errors.append(f"scratch cleanup: {exc}")
            # Restore grant roots first, then explicitly revoke the inherited
            # package ACE top-down from descendants.  Windows propagates a new
            # inheritable ACE to existing children but does not symmetrically
            # retract all propagated copies when only the parent is restored.
            for snapshot in root_snapshots:
                try:
                    self.restore_dacl(snapshot)
                except BaseException as exc:
                    cleanup_errors.append(f"ACL restore for {snapshot.path}: {exc}")
            if created_sid is not None:
                for path in validated.grant_entries:
                    try:
                        current = self.snapshot_dacl(path)
                        if self.descriptor_has_allowed_sid(current, created_sid):
                            self.revoke_sid(path, created_sid)
                    except BaseException as exc:
                        cleanup_errors.append(f"ACL SID revocation for {path}: {exc}")
            for baseline in baseline_snapshots:
                try:
                    # A final parent-first replay restores the original control
                    # bits and canonical ACE bytes after propagated copies of
                    # the package SID have been revoked.
                    restored = self.restore_dacl(baseline)
                    if created_sid is not None and self.descriptor_has_allowed_sid(
                        restored, created_sid
                    ):
                        raise SandboxCleanupError(
                            f"AppContainer SID remains after cleanup: {baseline.path}"
                        )
                    restored_snapshots.append(restored)
                except BaseException as exc:
                    cleanup_errors.append(
                        f"ACL final verification for {baseline.path}: {exc}"
                    )
            if profile_created:
                try:
                    self.delete_profile(validated.profile_name)
                    profile_deleted = True
                except BaseException as exc:
                    cleanup_errors.append(f"profile deletion: {exc}")
            self.free_sid(derived_sid)
            self.free_sid(created_sid)
        if cleanup_errors:
            raise SandboxCleanupError("; ".join(cleanup_errors))
        if result_fields is None:
            raise SandboxError("sandbox failed before producing a result")
        if security_observation is None:
            raise SandboxError("sandbox failed before process security observation")
        original_tuple = tuple(baseline_snapshots)
        # Manifest sorting makes restoration traversal order immaterial.
        restored_tuple = tuple(restored_snapshots)
        original_manifest = _manifest_hash(original_tuple)
        restored_manifest = _manifest_hash(restored_tuple)
        if original_manifest != restored_manifest:
            raise SandboxCleanupError(
                "restored ACL manifest does not equal its original manifest"
            )
        attestation = SandboxAttestation(
            schema_version=_SCHEMA_VERSION,
            claim_reference=validated.request.claim_reference,
            profile_name=validated.profile_name,
            package_sid=package_sid,
            capabilities=(),
            allowed_read_paths=tuple(str(grant.path) for grant in validated.grants),
            scratch_directory=str(validated.scratch),
            environment=validated.environment,
            inherited_handle_roles=("stdin", "stdout", "stderr"),
            process_id=security_observation.process_id,
            token_is_appcontainer=True,
            token_appcontainer_sid_verified=True,
            token_integrity_rid=security_observation.integrity_rid,
            token_elevated=False,
            token_capability_count=security_observation.capability_count,
            access_probes=security_observation.access_probes,
            max_processes=validated.request.max_processes,
            job_assigned_at_creation=True,
            job_membership_verified=True,
            job_limit_flags=security_observation.job_limit_flags,
            breakaway_allowed=False,
            kill_on_job_close=True,
            job_empty=True,
            acl_entry_count=len(original_tuple),
            original_acl_manifest_sha256=original_manifest,
            restored_acl_manifest_sha256=restored_manifest,
            acl_exactly_restored=True,
            scratch_emptied=not any(validated.scratch.iterdir()),
            profile_deleted=profile_deleted,
        )
        return SandboxResult(
            command=validated.command, attestation=attestation, **result_fields
        )  # type: ignore[arg-type]


def _empty_scratch(scratch: Path) -> None:
    """Remove only children of the already validated, non-reparse scratch root."""

    root = Path(os.path.abspath(scratch))
    if not root.is_dir() or Path(os.path.realpath(root)) != root:
        raise SandboxCleanupError(
            f"scratch root changed identity during execution: {root}"
        )
    for child in tuple(root.iterdir()):
        _remove_scratch_entry(child)
    if any(root.iterdir()):
        raise SandboxCleanupError(f"scratch directory could not be emptied: {root}")


def _remove_scratch_entry(path: Path) -> None:
    """Delete one scratch entry without ever traversing a reparse point."""

    metadata = path.lstat()
    attributes = getattr(metadata, "st_file_attributes", 0)
    if stat.S_ISLNK(metadata.st_mode) or attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        if attributes & _FILE_ATTRIBUTE_DIRECTORY:
            os.rmdir(path)
        else:
            path.unlink()
        return
    if stat.S_ISDIR(metadata.st_mode):
        for child in tuple(path.iterdir()):
            _remove_scratch_entry(child)
        os.rmdir(path)
        return
    if stat.S_ISREG(metadata.st_mode):
        path.unlink()
        return
    raise SandboxCleanupError(f"scratch contains an unsupported file type: {path}")


def run_sandboxed(
    request: SandboxRequest,
    *,
    on_preexit: Callable[[bytes, PreexitContext], bytes] | None = None,
    _api: _ApiProtocol | None = None,
) -> SandboxResult:
    """Run one claimed child attempt in a fresh, no-capability AppContainer.

    ``_api`` is private dependency injection for deterministic unit tests.  A
    real invocation always constructs the Windows backend and therefore fails
    closed on every other platform.
    """

    _validate_request(request)
    if (request.preexit_payload_limit_bytes is None) != (on_preexit is None):
        raise SandboxError(
            "pre-exit frame limit and trusted callback must be supplied together"
        )
    backend = _api if _api is not None else _WindowsApi()
    return backend.run(request, on_preexit)


_PATH_PROBE_CODE: Final = (
    "import sys\n"
    "try:\n"
    "    with open(sys.argv[1], 'rb') as stream: stream.read(1)\n"
    "except PermissionError:\n"
    "    print('GEOTARGET_PATH_PROBE:DENIED')\n"
    "except OSError as exc:\n"
    "    if getattr(exc, 'winerror', None) == 5:\n"
    "        print('GEOTARGET_PATH_PROBE:DENIED')\n"
    "    else:\n"
    "        print('GEOTARGET_PATH_PROBE:ERROR:' + str(getattr(exc, 'winerror', '')) + ':' + str(exc.errno))\n"
    "        raise SystemExit(3)\n"
    "else:\n"
    "    print('GEOTARGET_PATH_PROBE:ALLOWED')\n"
)


def run_python_path_probe(
    *,
    python_executable: Path,
    target: Path,
    allowed_read: tuple[ReadGrant, ...],
    scratch_directory: Path,
    claim_reference: str,
    timeout_seconds: float = 15.0,
    _api: _ApiProtocol | None = None,
) -> PathProbeResult:
    """Probe one path in its own C0 child invocation.

    The target is intentionally *not* added to ``allowed_read``.  Callers use
    separate invocations for positive and denied-path probes so a probe cannot
    inherit security state or handles from the candidate observation.
    """

    request = SandboxRequest(
        command=(
            str(python_executable),
            "-I",
            "-S",
            "-c",
            _PATH_PROBE_CODE,
            str(target),
        ),
        allowed_read=allowed_read,
        scratch_directory=scratch_directory,
        claim_reference=claim_reference,
        timeout_seconds=timeout_seconds,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
        max_processes=1,
    )
    sandbox = run_sandboxed(request, _api=_api)
    marker = sandbox.stdout.strip()
    if marker == b"GEOTARGET_PATH_PROBE:ALLOWED" and sandbox.return_code == 0:
        status = PathProbeStatus.ALLOWED
    elif marker == b"GEOTARGET_PATH_PROBE:DENIED" and sandbox.return_code == 0:
        status = PathProbeStatus.DENIED
    else:
        status = PathProbeStatus.ERROR
    return PathProbeResult(str(Path(os.path.abspath(target))), status, sandbox)


__all__ = (
    "AccessProbe",
    "AccessProbeObservation",
    "PathProbeResult",
    "PathProbeStatus",
    "PreexitContext",
    "PreexitReceipt",
    "ReadGrant",
    "SandboxAttestation",
    "SandboxCleanupError",
    "SandboxError",
    "SandboxRequest",
    "SandboxResult",
    "TerminationReason",
    "UnsupportedPlatformError",
    "run_python_path_probe",
    "run_sandboxed",
)
