"""Stable Windows AppContainer broker for C0-owned child observations.

The broker deliberately uses only documented, stable Windows APIs.  It creates a
fresh AppContainer profile, grants the package SID the minimum requested file
access, starts one suspended process with an empty capability set and an
explicit three-handle inheritance list, DETACHED_PROCESS, and a token-level
no-child policy, assigns it to a one-process non-breakaway kill-on-close Job
atomically at creation, and only then resumes it.  The completed lifetime must
contain exactly that one process.

Formal protocol callers MUST create and durably publish their irreversible
attempt claim before calling :func:`run_sandboxed` (and therefore before any
profile or ACL mutation).  ``claim_reference`` is included in the attestation;
this C0 utility cannot itself decide whether an experiment-specific claim is
authoritative.

All broker instances in the logon session serialize validation through cleanup.
Every read entry is held without write/delete sharing and committed by content,
volume and file identity; the same handles also prove that there are no named
``$DATA`` streams or nonempty extended attributes.  The caller-captured
commitment must match again before profile creation or ACL mutation.  The
scratch namespace is likewise pinned by a non-delete-shared directory and
parent handle.  Every touched DACL is restored from its exact original
self-relative descriptor.  The scratch directory must be empty; children
created there are removed before its original DACL is restored.  Cleanup
failure is fatal.  This boundary distrusts the AppContainer child and concurrent
broker invocations; a process that can modify the trusted observer's memory is
outside the local experiment threat model.  On non-Windows hosts execution
fails closed, while validation and injected/mock tests remain usable.
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
from types import TracebackType
from typing import Callable, Final, Protocol


_SCHEMA_VERSION: Final = "geotarget.exp-local-003.appcontainer-attestation/v2"
_READ_IDENTITY_SCHEMA_VERSION: Final = (
    "geotarget.exp-local-003.read-identity-manifest/v2"
)
_PROFILE_PREFIX: Final = "GeoTarget.EXPLOCAL003."
_BROKER_MUTEX_NAME: Final = r"Local\GeoTarget.EXPLOCAL003.SandboxBroker.v2"
_BROKER_LOCK_TIMEOUT_SECONDS: Final = 300.0
_BROKER_IN_PROCESS_LOCK = threading.Lock()

# Process creation and STARTUPINFOEX.
_CREATE_SUSPENDED: Final = 0x00000004
_DETACHED_PROCESS: Final = 0x00000008
_CREATE_UNICODE_ENVIRONMENT: Final = 0x00000400
_EXTENDED_STARTUPINFO_PRESENT: Final = 0x00080000
_STARTF_USESTDHANDLES: Final = 0x00000100
_PROC_THREAD_ATTRIBUTE_HANDLE_LIST: Final = 0x00020002
_PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: Final = 0x00020009
_PROC_THREAD_ATTRIBUTE_JOB_LIST: Final = 0x0002000D
_PROC_THREAD_ATTRIBUTE_CHILD_PROCESS_POLICY: Final = 0x0002000E
_PROCESS_CREATION_CHILD_PROCESS_RESTRICTED: Final = 0x00000001

# Handles and waits.
_HANDLE_FLAG_INHERIT: Final = 0x00000001
_WAIT_OBJECT_0: Final = 0x00000000
_WAIT_ABANDONED: Final = 0x00000080
_WAIT_TIMEOUT: Final = 0x00000102
_WAIT_FAILED: Final = 0xFFFFFFFF
_INFINITE: Final = 0xFFFFFFFF
_STILL_ACTIVE: Final = 259
_ERROR_BROKEN_PIPE: Final = 109
_ERROR_SHARING_VIOLATION: Final = 32
_ERROR_NO_DATA: Final = 232
_ERROR_INSUFFICIENT_BUFFER: Final = 122
_ERROR_BAD_LENGTH: Final = 24
_ERROR_HANDLE_EOF: Final = 38
_ERROR_NOT_FOUND: Final = 1168
_ERROR_MORE_DATA: Final = 234
_HRESULT_FROM_WIN32_ERROR_NOT_FOUND: Final = 0x80070490
_INVALID_HANDLE_VALUE: Final = ctypes.c_void_p(-1).value

# Job APIs.  Omitting BREAKAWAY_OK and SILENT_BREAKAWAY_OK is intentional.
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS: Final = 0x00000008
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
_JOB_OBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION: Final = 8
_JOB_TERMINATION_CODE: Final = 0xC0DE0001

# File and ACL APIs.
_GENERIC_READ: Final = 0x80000000
_GENERIC_WRITE: Final = 0x40000000
_FILE_WRITE_DATA: Final = 0x00000002
_FILE_APPEND_DATA: Final = 0x00000004
_FILE_READ_EA: Final = 0x00000008
_FILE_WRITE_EA: Final = 0x00000010
_FILE_EXECUTE: Final = 0x00000020
_DELETE: Final = 0x00010000
_FILE_DELETE_CHILD: Final = 0x00000040
_FILE_WRITE_ATTRIBUTES: Final = 0x00000100
_FILE_READ_ATTRIBUTES: Final = 0x00000080
_WRITE_DAC: Final = 0x00040000
_WRITE_OWNER: Final = 0x00080000
_FILE_SHARE_READ: Final = 0x00000001
_FILE_SHARE_WRITE: Final = 0x00000002
_FILE_SHARE_DELETE: Final = 0x00000004
_OPEN_EXISTING: Final = 3
_FILE_ATTRIBUTE_NORMAL: Final = 0x00000080
_FILE_ATTRIBUTE_DIRECTORY: Final = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT: Final = 0x00000400
_FILE_FLAG_BACKUP_SEMANTICS: Final = 0x02000000
_FILE_FLAG_OVERLAPPED: Final = 0x40000000
_FILE_STREAM_INFO_CLASS: Final = 7
_FILE_EA_INFORMATION_CLASS: Final = 7
_FILE_ID_INFO_CLASS: Final = 18
_INVALID_FILE_ATTRIBUTES: Final = 0xFFFFFFFF
_DACL_SECURITY_INFORMATION: Final = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION: Final = 0x80000000
_UNPROTECTED_DACL_SECURITY_INFORMATION: Final = 0x20000000
_SE_DACL_PROTECTED: Final = 0x1000
_SE_DACL_AUTO_INHERITED: Final = 0x0400
_SE_FILE_OBJECT: Final = 1
_GRANT_ACCESS: Final = 1
_TRUSTEE_IS_SID: Final = 0
_TRUSTEE_IS_USER: Final = 1
_NO_INHERITANCE: Final = 0
_SUB_CONTAINERS_AND_OBJECTS_INHERIT: Final = 0x3
_INHERIT_ONLY_SUB_CONTAINERS_AND_OBJECTS: Final = 0xB
_ACL_SIZE_INFORMATION_CLASS: Final = 2
_ACCESS_ALLOWED_ACE_TYPE: Final = 0
_INHERITED_ACE: Final = 0x10
_FILE_GENERIC_READ: Final = 0x00120089
_FILE_GENERIC_WRITE: Final = 0x00120116
_FILE_GENERIC_EXECUTE: Final = 0x001200A0

_MAX_STREAM_INFO_BUFFER_BYTES: Final = 64 * 1024 * 1024

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
class ReadIdentityManifest:
    """A caller-captured identity commitment for all executable/read inputs."""

    schema_version: str
    entry_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class AccessProbe:
    """A C0-only pre-resume access assertion made with the child token.

    ``DENIED`` is a namespace-integrity assertion, not merely a read probe: the
    target and every existing descendant must deny read/execute and every
    relevant mutation right, while every existing ancestor must independently
    deny namespace/DACL/owner mutation rights.
    """

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
    expected_read_identity_manifest_sha256: str
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
    profile_storage_path: str
    capabilities: tuple[str, ...]
    allowed_read_paths: tuple[str, ...]
    read_identity_manifest_entry_count: int
    read_identity_manifest_sha256: str
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
    denied_probe_entry_count: int
    denied_probe_manifest_sha256: str
    read_only_probe_entry_count: int
    read_only_probe_manifest_sha256: str
    scratch_access_probe_manifest_sha256: str
    max_processes: int
    child_process_restricted: bool
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
    profile_storage_deleted: bool


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


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    )


class _FILE_ID_128(ctypes.Structure):
    _fields_ = (("Identifier", ctypes.c_ubyte * 16),)


class _FILE_ID_INFO(ctypes.Structure):
    _fields_ = (
        ("VolumeSerialNumber", ctypes.c_ulonglong),
        ("FileId", _FILE_ID_128),
    )


class _IO_STATUS_BLOCK(ctypes.Structure):
    # The first field is the Status/Pointer union.  Its storage is pointer-sized
    # even though NTSTATUS itself is 32 bits.
    _fields_ = (
        ("StatusOrPointer", ctypes.c_void_p),
        ("Information", ctypes.c_size_t),
    )


class _FILE_EA_INFORMATION(ctypes.Structure):
    _fields_ = (("EaSize", wintypes.ULONG),)


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
    control: int


@dataclass(frozen=True, slots=True)
class _ValidationIdentity:
    path: str
    st_dev: int
    st_ino: int
    st_mode: int
    st_size: int
    st_nlink: int


@dataclass(frozen=True, slots=True)
class _Win32FileIdentity:
    volume_serial_number: int
    file_id: bytes
    attributes: int
    size: int
    number_of_links: int


@dataclass(frozen=True, slots=True)
class _HeldReadIdentitySet:
    handles: tuple[int, ...]
    entry_count: int
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class _ValidatedRequest:
    request: SandboxRequest
    command: tuple[str, ...]
    executable: Path
    grants: tuple[ReadGrant, ...]
    grant_entries: tuple[Path, ...]
    grant_entry_identities: tuple[_ValidationIdentity, ...]
    scratch: Path
    scratch_identity: _ValidationIdentity
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
    denied_probe_entry_count: int
    denied_probe_manifest_sha256: str
    read_only_probe_entry_count: int
    read_only_probe_manifest_sha256: str
    scratch_access_probe_manifest_sha256: str
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
        # A bytearray grows amortized-linearly.  The former list implementation
        # joined every accumulated chunk after every read while parsing a
        # pre-exit frame, making a permitted 256 MiB output O(n^2).
        self._buffer = bytearray()
        self._size = 0
        self._stream_size = 0
        self._overflow = False
        self._error: BaseException | None = None
        self._frame_limit = frame_limit
        self._frame_payload: bytes | None = None
        self._frame_error: str | None = None
        self._lock = threading.Lock()
        self.overflow_event = threading.Event()
        self.failure_event = threading.Event()
        self.frame_event = threading.Event()
        self.eof_event = threading.Event()

    def _inspect_frame_locked(self) -> None:
        if self._frame_limit is None or self._frame_error is not None:
            return
        if self._size < 8:
            return
        declared = struct.unpack(">Q", self._buffer[:8])[0]
        if declared == 0 or declared > self._frame_limit:
            self._frame_error = f"pre-exit stdout frame length {declared} is outside 1..{self._frame_limit}"
            self.frame_event.set()
            return
        expected = 8 + declared
        if self._stream_size > expected:
            self._frame_error = "pre-exit stdout contains bytes after its single frame"
            self.frame_event.set()
            return
        if self._size == expected and self._frame_payload is None:
            self._frame_payload = bytes(memoryview(self._buffer)[8:expected])
            self.frame_event.set()

    def run(self) -> None:
        try:
            while True:
                chunk = self._api.read_pipe(self._handle)
                if chunk is None:
                    with self._lock:
                        if (
                            self._frame_limit is not None
                            and self._frame_payload is None
                            and self._frame_error is None
                        ):
                            self._frame_error = "pre-exit stdout closed before its single frame completed"
                        self.frame_event.set()
                        self.eof_event.set()
                    return
                with self._lock:
                    self._stream_size += len(chunk)
                    remaining = self._limit - self._size
                    if remaining > 0:
                        kept = chunk[:remaining]
                        self._buffer.extend(kept)
                        self._size += len(kept)
                    if len(chunk) > remaining:
                        self._overflow = True
                        self.overflow_event.set()
                    self._inspect_frame_locked()
        except BaseException as exc:  # surfaced to the broker thread
            self._error = exc
            self.failure_event.set()

    def result(self) -> _ReaderResult:
        with self._lock:
            return _ReaderResult(bytes(self._buffer), self._overflow, self._error)

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


def _grant_covers(grant: ReadGrant, target: Path) -> bool:
    return target == grant.path or (grant.recursive and _is_within(target, grant.path))


def _register_exact_case_path(
    seen: dict[str, str], path: Path, *, context: str
) -> bool:
    """Register one Windows path without hiding case-sensitive collisions.

    ``normcase`` is still the correct authority key on ordinary NTFS volumes,
    but case-sensitive directories can contain two distinct names that fold to
    the same key.  Silently deduplicating those names would omit one authority
    entry from validation, pinning, ACL restoration, or probing.
    """

    rendered = str(path)
    key = os.path.normcase(rendered)
    previous = seen.get(key)
    if previous is None:
        seen[key] = rendered
        return True
    if previous != rendered:
        raise SandboxError(
            f"{context} contains case-colliding paths: {previous}, {rendered}"
        )
    return False


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


def _validation_identity(path: Path) -> _ValidationIdentity:
    metadata = path.stat(follow_symlinks=False)
    return _ValidationIdentity(
        path=str(path),
        st_dev=int(metadata.st_dev),
        st_ino=int(metadata.st_ino),
        st_mode=int(metadata.st_mode),
        st_size=int(metadata.st_size),
        st_nlink=int(metadata.st_nlink),
    )


def _assert_validation_identity(
    path: Path, expected: _ValidationIdentity, *, phase: str
) -> None:
    observed = _validation_identity(path)
    if observed != expected:
        raise SandboxError(
            f"sandbox path identity changed during {phase}: {path}; "
            f"expected={(expected.st_dev, expected.st_ino, expected.st_mode, expected.st_size, expected.st_nlink)} "
            f"observed={(observed.st_dev, observed.st_ino, observed.st_mode, observed.st_size, observed.st_nlink)}"
        )


def _expand_recursive_tree(root: Path, *, context: str) -> tuple[Path, ...]:
    """Expand one normalized directory without omitting aliased entries."""

    if not root.is_dir():
        raise SandboxError(f"{context} root is not a directory: {root}")
    entries = [root]
    spellings = {os.path.normcase(str(root)): str(root)}

    def fail_walk(error: OSError) -> None:
        raise SandboxError(f"{context} changed during recursive expansion: {error}")

    for current, directory_names, file_names in os.walk(
        root, followlinks=False, onerror=fail_walk
    ):
        current_path = Path(current)
        directory_names.sort(key=str.casefold)
        file_names.sort(key=str.casefold)
        for name in (*directory_names, *file_names):
            entry = current_path / name
            try:
                metadata = entry.lstat()
            except OSError as error:
                raise SandboxError(
                    f"{context} changed during recursive expansion: {entry}: {error}"
                ) from error
            attributes = getattr(metadata, "st_file_attributes", 0)
            if (
                stat.S_ISLNK(metadata.st_mode)
                or attributes & _FILE_ATTRIBUTE_REPARSE_POINT
                or Path(os.path.realpath(entry)) != entry
            ):
                raise SandboxError(f"{context} contains a link/reparse alias: {entry}")
            if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
                raise SandboxError(f"{context} contains a hardlinked file: {entry}")
            _register_exact_case_path(spellings, entry, context=context)
            entries.append(entry)
    return tuple(entries)


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
    return _expand_recursive_tree(root, context="recursive read grant")


def _expand_denied_probe_target(target: Path) -> tuple[Path, ...]:
    if target.is_dir():
        return _expand_recursive_tree(
            target, context=f"denied access probe tree {target}"
        )
    return (target,)


def _validate_request(request: SandboxRequest) -> _ValidatedRequest:
    if not request.claim_reference or "\x00" in request.claim_reference:
        raise SandboxError("claim_reference must be a non-empty NUL-free identifier")
    if len(request.expected_read_identity_manifest_sha256) != 64 or any(
        character not in "0123456789abcdef"
        for character in request.expected_read_identity_manifest_sha256
    ):
        raise SandboxError(
            "expected_read_identity_manifest_sha256 must be 64 lowercase hex digits"
        )
    if not request.command:
        raise SandboxError("sandbox command must not be empty")
    if any(
        not isinstance(item, str) or not item or "\x00" in item
        for item in request.command
    ):
        raise SandboxError(
            "sandbox command arguments must be non-empty NUL-free strings"
        )
    raw_executable = Path(request.command[0])
    if not raw_executable.is_absolute():
        raise SandboxError("sandbox executable must be absolute")
    executable = _normalize_existing(raw_executable, directory=False)
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
    if request.max_processes != 1:
        raise SandboxError("the C0 sandbox contract requires max_processes == 1")

    scratch = _normalize_existing(request.scratch_directory, directory=True)
    scratch_identity = _validation_identity(scratch)
    if any(scratch.iterdir()):
        raise SandboxError(f"scratch directory must be empty before launch: {scratch}")

    grants: list[ReadGrant] = []
    entries: list[Path] = []
    seen_grants: set[tuple[str, bool]] = set()
    grant_spellings: dict[str, str] = {}
    entry_spellings: dict[str, str] = {}
    for raw in request.allowed_read:
        root = _normalize_existing(raw.path)
        _register_exact_case_path(
            grant_spellings, root, context="allowed_read grant roots"
        )
        key = (os.path.normcase(str(root)), raw.recursive)
        if key in seen_grants:
            continue
        seen_grants.add(key)
        if _is_within(scratch, root) or _is_within(root, scratch):
            raise SandboxError(f"read grants and scratch must not overlap: {root}")
        normalized = ReadGrant(root, raw.recursive)
        grants.append(normalized)
        for entry in _expand_grant(normalized):
            if _register_exact_case_path(
                entry_spellings, entry, context="expanded allowed_read entries"
            ):
                entries.append(entry)
    if not any(_grant_covers(grant, executable) for grant in grants):
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
    probes: list[AccessProbe] = []
    probe_spellings: dict[str, str] = {}
    for raw_probe in request.access_probes:
        if raw_probe.expected not in (PathProbeStatus.ALLOWED, PathProbeStatus.DENIED):
            raise SandboxError("access probe expectation must be allowed or denied")
        target = _normalize_existing(raw_probe.path)
        if not _register_exact_case_path(
            probe_spellings, target, context="access probes"
        ):
            raise SandboxError(f"duplicate access probe target: {target}")
        covered = any(_grant_covers(grant, target) for grant in grants)
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
        if raw_probe.expected is PathProbeStatus.DENIED:
            denied_entries = _expand_denied_probe_target(target)
            for descendant in denied_entries[1:]:
                if any(_grant_covers(grant, descendant) for grant in grants):
                    raise SandboxError(
                        "recursive denied access probe intersects an allowed read "
                        f"grant: probe={target} entry={descendant}"
                    )
                if _is_within(descendant, scratch) or _is_within(scratch, descendant):
                    raise SandboxError(
                        "recursive denied access probe intersects scratch: "
                        f"probe={target} entry={descendant}"
                    )
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
        grant_entries=tuple(entries),
        grant_entry_identities=tuple(_validation_identity(path) for path in entries),
        scratch=scratch,
        scratch_identity=scratch_identity,
        probes=tuple(probes),
        profile_name=profile_name,
        environment=environment,
    )


def _manifest_hash(entries: tuple[_SecurityDescriptorSnapshot, ...]) -> str:
    manifest = [
        {
            "path": snapshot.path,
            "protected": snapshot.protected,
            "control": snapshot.control,
            "security_descriptor_sha256": hashlib.sha256(snapshot.payload).hexdigest(),
        }
        for snapshot in sorted(entries, key=lambda item: os.path.normcase(item.path))
    ]
    payload = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def capture_read_identity_manifest(
    *, executable: Path, allowed_read: tuple[ReadGrant, ...]
) -> ReadIdentityManifest:
    """Capture the immutable read authority that a later request must match.

    The returned digest is intentionally captured in a distinct operation.
    :func:`run_sandboxed` reopens every entry with exclusive write/delete
    sharing, recomputes this commitment, and rejects replacement before it
    creates a profile or mutates an ACL.
    """

    serialization = _BrokerSerialization()
    serialization.acquire()
    held: _HeldReadIdentitySet | None = None
    api: _WindowsApi | None = None
    primary: BaseException | None = None
    try:
        if not Path(executable).is_absolute():
            raise SandboxError("sandbox executable must be absolute")
        normalized_executable = _normalize_existing(executable, directory=False)
        grants: list[ReadGrant] = []
        entries: list[Path] = []
        seen_grants: set[tuple[str, bool]] = set()
        grant_spellings: dict[str, str] = {}
        entry_spellings: dict[str, str] = {}
        for raw in allowed_read:
            root = _normalize_existing(raw.path)
            _register_exact_case_path(
                grant_spellings, root, context="allowed_read grant roots"
            )
            key = (os.path.normcase(str(root)), raw.recursive)
            if key in seen_grants:
                continue
            seen_grants.add(key)
            grant = ReadGrant(root, raw.recursive)
            grants.append(grant)
            for entry in _expand_grant(grant):
                if _register_exact_case_path(
                    entry_spellings,
                    entry,
                    context="expanded allowed_read entries",
                ):
                    entries.append(entry)
        if not any(_grant_covers(grant, normalized_executable) for grant in grants):
            raise SandboxError(
                "the executable must be covered by an explicit read grant"
            )
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
        identities = tuple(_validation_identity(path) for path in entries)
        api = _WindowsApi()
        held = api._acquire_read_identity_guards(
            tuple(entries), identities, tuple(grants)
        )
        return ReadIdentityManifest(
            _READ_IDENTITY_SCHEMA_VERSION,
            held.entry_count,
            held.manifest_sha256,
        )
    except BaseException as exc:
        primary = exc
        raise
    finally:
        cleanup: list[str] = []
        if api is not None and held is not None:
            for handle in reversed(held.handles):
                try:
                    api.close_handle(handle)
                except BaseException as exc:
                    cleanup.append(f"read identity capture handle cleanup: {exc}")
        try:
            serialization.release()
        except BaseException as exc:
            cleanup.append(f"broker serialization cleanup: {exc}")
        if cleanup:
            raise SandboxCleanupError("; ".join(cleanup)) from primary


def _differs_only_by_auto_inherited_metadata(
    original: _SecurityDescriptorSnapshot,
    current: _SecurityDescriptorSnapshot,
) -> bool:
    """Recognize the one metadata transition caused by ACL propagation.

    SetNamedSecurityInfo may set SE_DACL_AUTO_INHERITED on a pre-existing
    descendant whose baseline did not have it, even after the inherited ACE is
    removed again.  No other descriptor byte is safe to normalize silently.
    """

    if len(original.payload) < 28 or len(current.payload) < 28:
        return False
    if original.control & _SE_DACL_AUTO_INHERITED:
        return False
    if not current.control & _SE_DACL_AUTO_INHERITED:
        return False
    if original.control ^ current.control != _SE_DACL_AUTO_INHERITED:
        return False
    original_payload = bytearray(original.payload)
    current_payload = bytearray(current.payload)
    current_payload[2:4] = original_payload[2:4]

    original_dacl = int.from_bytes(original_payload[16:20], "little")
    current_dacl = int.from_bytes(current_payload[16:20], "little")
    if (
        original_dacl != current_dacl
        or original_dacl + 8 > len(original_payload)
        or current_dacl + 8 > len(current_payload)
        or original_payload[:original_dacl] != current_payload[:current_dacl]
    ):
        return False
    original_acl_size = int.from_bytes(
        original_payload[original_dacl + 2 : original_dacl + 4], "little"
    )
    current_acl_size = int.from_bytes(
        current_payload[current_dacl + 2 : current_dacl + 4], "little"
    )
    if (
        original_dacl + original_acl_size != len(original_payload)
        or current_dacl + current_acl_size != len(current_payload)
        or original_payload[original_dacl : original_dacl + 2]
        != current_payload[current_dacl : current_dacl + 2]
        or original_payload[original_dacl + 6 : original_dacl + 8]
        != current_payload[current_dacl + 6 : current_dacl + 8]
    ):
        return False
    original_ace_count = int.from_bytes(
        original_payload[original_dacl + 4 : original_dacl + 6], "little"
    )
    current_ace_count = int.from_bytes(
        current_payload[current_dacl + 4 : current_dacl + 6], "little"
    )
    if original_ace_count == 0 or current_ace_count not in {
        original_ace_count,
        2 * original_ace_count,
    }:
        return False

    def ace_payloads(payload: bytearray, start: int, count: int) -> list[bytes] | None:
        offset = start + 8
        result: list[bytes] = []
        for _ in range(count):
            if offset + 4 > len(payload):
                return None
            size = int.from_bytes(payload[offset + 2 : offset + 4], "little")
            if size < 4 or offset + size > len(payload):
                return None
            result.append(bytes(payload[offset : offset + size]))
            offset += size
        if offset != len(payload):
            return None
        return result

    original_aces = ace_payloads(original_payload, original_dacl, original_ace_count)
    current_aces = ace_payloads(current_payload, current_dacl, current_ace_count)
    if original_aces is None or current_aces is None:
        return False
    duplicated = current_ace_count == 2 * original_ace_count
    for index, current_ace in enumerate(current_aces):
        original_ace = original_aces[index % original_ace_count]
        original_flags = original_ace[1]
        current_flags = current_ace[1]
        if duplicated:
            expected_flags = (
                original_flags | _INHERITED_ACE
                if index >= original_ace_count
                else original_flags
            )
            if current_flags != expected_flags:
                return False
        elif current_flags not in {
            original_flags,
            original_flags | _INHERITED_ACE,
        }:
            return False
        normalized = bytearray(current_ace)
        normalized[1] = original_flags
        if normalized != original_ace:
            return False
    return True


class _BrokerSerialization:
    """Serialize every validation/mutation/cleanup boundary in this logon session."""

    def __init__(self) -> None:
        self._local_acquired = False
        self._kernel32: object | None = None
        self._mutex: int | None = None
        self._mutex_owned = False

    def acquire(self) -> None:
        if not _BROKER_IN_PROCESS_LOCK.acquire(timeout=_BROKER_LOCK_TIMEOUT_SECONDS):
            raise SandboxError("timed out acquiring the in-process broker lock")
        self._local_acquired = True
        if os.name != "nt":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateMutexW(None, False, _BROKER_MUTEX_NAME)
        value = ctypes.cast(handle, ctypes.c_void_p).value
        if value in {None, 0, _INVALID_HANDLE_VALUE}:
            self.release()
            raise _win_error("CreateMutexW(broker serialization) failed")
        self._kernel32 = kernel32
        self._mutex = value
        status = kernel32.WaitForSingleObject(
            handle, int(_BROKER_LOCK_TIMEOUT_SECONDS * 1000)
        )
        if status == _WAIT_OBJECT_0:
            self._mutex_owned = True
            return
        if status == _WAIT_ABANDONED:
            # WAIT_ABANDONED transfers ownership.  Release it, but never use
            # security state whose prior owner died inside the broker boundary.
            self._mutex_owned = True
            self.release()
            raise SandboxError("broker mutex was abandoned; refusing stale state")
        wait_error = ctypes.get_last_error() if status == _WAIT_FAILED else None
        self.release()
        if status == _WAIT_TIMEOUT:
            raise SandboxError("timed out acquiring the cross-process broker mutex")
        if status == _WAIT_FAILED:
            raise _win_error("WaitForSingleObject(broker mutex) failed", wait_error)
        raise SandboxError(f"unexpected broker mutex wait status: 0x{status:08x}")

    def release(self) -> None:
        errors: list[str] = []
        kernel32 = self._kernel32
        mutex = self._mutex
        if kernel32 is not None and mutex is not None:
            if self._mutex_owned:
                if not kernel32.ReleaseMutex(wintypes.HANDLE(mutex)):  # type: ignore[attr-defined]
                    errors.append(str(_win_error("ReleaseMutex(broker) failed")))
                self._mutex_owned = False
            if not kernel32.CloseHandle(wintypes.HANDLE(mutex)):  # type: ignore[attr-defined]
                errors.append(str(_win_error("CloseHandle(broker mutex) failed")))
            self._mutex = None
        if self._local_acquired:
            _BROKER_IN_PROCESS_LOCK.release()
            self._local_acquired = False
        if errors:
            raise SandboxCleanupError("; ".join(errors))


class _WindowsApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise UnsupportedPlatformError(
                "AppContainer sandboxing is available only on Windows"
            )
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.userenv = ctypes.WinDLL("userenv", use_last_error=True)
        self.ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll")
        self._bind()

    def _bind(self) -> None:
        k32, adv, user, ole, ntdll = (
            self.kernel32,
            self.advapi32,
            self.userenv,
            self.ole32,
            self.ntdll,
        )
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
        user.GetAppContainerFolderPath.argtypes = (
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.LPWSTR),
        )
        user.GetAppContainerFolderPath.restype = ctypes.c_long
        ole.CoTaskMemFree.argtypes = (wintypes.LPVOID,)
        ole.CoTaskMemFree.restype = None
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
        k32.GetFileInformationByHandle.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
        )
        k32.GetFileInformationByHandle.restype = wintypes.BOOL
        k32.GetFileInformationByHandleEx.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        k32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        ntdll.NtQueryInformationFile.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(_IO_STATUS_BLOCK),
            wintypes.LPVOID,
            wintypes.ULONG,
            ctypes.c_int,
        )
        ntdll.NtQueryInformationFile.restype = ctypes.c_long
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
        k32.CancelIoEx.argtypes = (wintypes.HANDLE, wintypes.LPVOID)
        k32.CancelIoEx.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        k32.CloseHandle.restype = wintypes.BOOL

    def profile_storage_path(self, package_sid: str) -> Path:
        storage = wintypes.LPWSTR()
        result = self.userenv.GetAppContainerFolderPath(
            package_sid, ctypes.byref(storage)
        )
        if result != 0:
            raise _hresult_error("GetAppContainerFolderPath failed", result)
        try:
            value = storage.value
        finally:
            self.ole32.CoTaskMemFree(storage)
        if not value:
            raise SandboxError("GetAppContainerFolderPath returned an empty path")
        path = Path(os.path.abspath(value))
        if not path.is_absolute():
            raise SandboxError("AppContainer profile storage path is not absolute")
        if os.path.lexists(path) and Path(os.path.realpath(path)) != path:
            raise SandboxError("AppContainer profile storage is a reparse alias")
        return path

    def create_profile(self, name: str) -> tuple[int, int, str, Path]:
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
        created_value = _handle_value(created)
        derived = wintypes.LPVOID()
        derived_value: int | None = None
        text: str | None = None
        storage_path: Path | None = None
        succeeded = False
        try:
            result = self.userenv.DeriveAppContainerSidFromAppContainerName(
                name, ctypes.byref(derived)
            )
            if result != 0:
                raise _hresult_error(
                    "DeriveAppContainerSidFromAppContainerName failed", result
                )
            derived_value = _handle_value(derived)
            if not self.advapi32.EqualSid(created, derived):
                raise SandboxError(
                    "created and independently derived AppContainer SIDs differ"
                )
            sid_text = wintypes.LPWSTR()
            if not self.advapi32.ConvertSidToStringSidW(
                created, ctypes.byref(sid_text)
            ):
                raise _win_error("ConvertSidToStringSidW failed")
            try:
                text = sid_text.value
            finally:
                self.kernel32.LocalFree(sid_text)
            if not text:
                raise SandboxError("ConvertSidToStringSidW returned an empty SID")
            storage_path = self.profile_storage_path(text)
            succeeded = True
            return created_value, derived_value, text, storage_path
        except BaseException as primary:
            cleanup_errors: list[str] = []
            if text is None:
                sid_text = wintypes.LPWSTR()
                if self.advapi32.ConvertSidToStringSidW(
                    created, ctypes.byref(sid_text)
                ):
                    try:
                        text = sid_text.value
                    finally:
                        self.kernel32.LocalFree(sid_text)
            if text and storage_path is None:
                try:
                    storage_path = self.profile_storage_path(text)
                except BaseException as error:
                    cleanup_errors.append(f"profile storage discovery: {error}")
            try:
                self.delete_profile(name, storage_path)
            except BaseException as error:
                cleanup_errors.append(f"profile rollback: {error}")
            if storage_path is None:
                cleanup_errors.append("profile storage path remained unknown")
            if cleanup_errors:
                raise SandboxCleanupError("; ".join(cleanup_errors)) from primary
            raise
        finally:
            if not succeeded:
                self.free_sid(derived_value)
                self.free_sid(created_value)

    def delete_profile(self, name: str, storage_path: Path | None) -> None:
        deletion_confirmed = False
        last_result = 0
        for attempt in range(5):
            if not deletion_confirmed:
                last_result = self.userenv.DeleteAppContainerProfile(name)
                deletion_confirmed = last_result == 0
            storage_absent = storage_path is None or not os.path.lexists(storage_path)
            if deletion_confirmed and storage_absent:
                return
            if (
                not deletion_confirmed
                and ctypes.c_uint32(last_result).value
                == _HRESULT_FROM_WIN32_ERROR_NOT_FOUND
                and storage_absent
            ):
                return
            if attempt != 4:
                time.sleep(0.05 * (attempt + 1))
        if not deletion_confirmed:
            raise _hresult_error("DeleteAppContainerProfile failed", last_result)
        raise SandboxCleanupError(
            f"AppContainer profile storage remains after deletion: {storage_path}"
        )

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
        present = wintypes.BOOL()
        acl = wintypes.LPVOID()
        defaulted = wintypes.BOOL()
        if not self.advapi32.GetSecurityDescriptorDacl(
            buffer,
            ctypes.byref(present),
            ctypes.byref(acl),
            ctypes.byref(defaulted),
        ):
            raise _win_error(f"GetSecurityDescriptorDacl failed for {path}")
        if not present.value or not acl:
            raise SandboxError(f"ACL target has an absent or NULL DACL: {path}")
        information = _ACL_SIZE_INFORMATION()
        if not self.advapi32.GetAclInformation(
            acl,
            ctypes.byref(information),
            ctypes.sizeof(information),
            _ACL_SIZE_INFORMATION_CLASS,
        ):
            raise _win_error(f"GetAclInformation failed for {path}")
        if information.AceCount == 0:
            raise SandboxError(f"ACL target has an empty DACL: {path}")
        return _SecurityDescriptorSnapshot(
            str(path),
            bytes(buffer.raw[: needed.value]),
            bool(control.value & _SE_DACL_PROTECTED),
            control.value,
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

    def restore_dacl_propagating(self, snapshot: _SecurityDescriptorSnapshot) -> None:
        """Restore a grant root and propagate inherited-ACE removal downward."""

        descriptor = ctypes.create_string_buffer(snapshot.payload)
        present = wintypes.BOOL()
        original_acl = wintypes.LPVOID()
        defaulted = wintypes.BOOL()
        if not self.advapi32.GetSecurityDescriptorDacl(
            descriptor,
            ctypes.byref(present),
            ctypes.byref(original_acl),
            ctypes.byref(defaulted),
        ):
            raise _win_error(
                f"GetSecurityDescriptorDacl restore failed for {snapshot.path}"
            )
        if not present.value:
            raise SandboxCleanupError(
                f"ACL restore target has no DACL: {snapshot.path}"
            )
        protection = (
            _PROTECTED_DACL_SECURITY_INFORMATION
            if snapshot.protected
            else _UNPROTECTED_DACL_SECURITY_INFORMATION
        )
        result = self.advapi32.SetNamedSecurityInfoW(
            snapshot.path,
            _SE_FILE_OBJECT,
            _DACL_SECURITY_INFORMATION | protection,
            None,
            None,
            original_acl,
            None,
        )
        if result != 0:
            raise _win_error(
                f"SetNamedSecurityInfoW propagating restore failed for {snapshot.path}",
                result,
            )

    def restore_dacl_exact(
        self, snapshot: _SecurityDescriptorSnapshot
    ) -> _SecurityDescriptorSnapshot:
        descriptor = ctypes.create_string_buffer(snapshot.payload)
        if not self.advapi32.SetFileSecurityW(
            snapshot.path, _DACL_SECURITY_INFORMATION, descriptor
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

    def _open_identity_guard(
        self, path: Path, *, scratch: bool, namespace_parent: bool = False
    ) -> int:
        is_directory = path.is_dir()
        desired_access = (
            _FILE_READ_ATTRIBUTES | _FILE_READ_EA if is_directory else _GENERIC_READ
        )
        if scratch:
            # DELETE in the held access mask is deliberate.  In addition to
            # omitting FILE_SHARE_DELETE, it forces every later opener to share
            # delete access with this handle and closes rename-by-parent gaps
            # observed with an attributes-only directory handle.
            desired_access |= _DELETE
        # The scratch namespace handles allow write sharing so suspended-token
        # probes observe the DACL for non-delete mutation rights.  Delete
        # sharing remains intentionally absent: the held handles are the
        # runtime mechanism that prevents rename/replacement even if an
        # ambient principal unexpectedly grants DELETE.
        share_mode = (
            _FILE_SHARE_READ | _FILE_SHARE_WRITE
            if scratch or namespace_parent
            else _FILE_SHARE_READ
        )
        flags = _FILE_FLAG_BACKUP_SEMANTICS if is_directory else _FILE_ATTRIBUTE_NORMAL
        ctypes.set_last_error(0)
        handle = self.kernel32.CreateFileW(
            str(path),
            desired_access,
            share_mode,
            None,
            _OPEN_EXISTING,
            flags,
            None,
        )
        value = ctypes.cast(handle, ctypes.c_void_p).value
        if value in {None, _INVALID_HANDLE_VALUE}:
            role = "scratch" if scratch else "read input"
            raise _win_error(f"CreateFileW({role} identity guard) failed for {path}")
        return value

    def _handle_identity(self, handle: int) -> _Win32FileIdentity:
        information = _BY_HANDLE_FILE_INFORMATION()
        if not self.kernel32.GetFileInformationByHandle(
            wintypes.HANDLE(handle), ctypes.byref(information)
        ):
            raise _win_error("GetFileInformationByHandle(identity guard) failed")
        file_id = _FILE_ID_INFO()
        if not self.kernel32.GetFileInformationByHandleEx(
            wintypes.HANDLE(handle),
            _FILE_ID_INFO_CLASS,
            ctypes.byref(file_id),
            ctypes.sizeof(file_id),
        ):
            raise _win_error("GetFileInformationByHandleEx(FileIdInfo) failed")
        size = (int(information.nFileSizeHigh) << 32) | int(information.nFileSizeLow)
        return _Win32FileIdentity(
            volume_serial_number=int(file_id.VolumeSerialNumber),
            file_id=bytes(file_id.FileId.Identifier),
            attributes=int(information.dwFileAttributes),
            size=size,
            number_of_links=int(information.nNumberOfLinks),
        )

    def _data_stream_inventory(
        self, handle: int, path: Path
    ) -> tuple[tuple[str, int, int], ...]:
        """Enumerate every ``$DATA`` stream through the held identity handle."""

        buffer_size = 64 * 1024
        while True:
            buffer = ctypes.create_string_buffer(buffer_size)
            ctypes.set_last_error(0)
            if self.kernel32.GetFileInformationByHandleEx(
                wintypes.HANDLE(handle),
                _FILE_STREAM_INFO_CLASS,
                buffer,
                buffer_size,
            ):
                break
            error = ctypes.get_last_error()
            if error == _ERROR_HANDLE_EOF:
                return ()
            if error in {_ERROR_INSUFFICIENT_BUFFER, _ERROR_MORE_DATA} and (
                buffer_size < _MAX_STREAM_INFO_BUFFER_BYTES
            ):
                buffer_size = min(buffer_size * 2, _MAX_STREAM_INFO_BUFFER_BYTES)
                continue
            raise _win_error(
                f"GetFileInformationByHandleEx(FileStreamInfo) failed for {path}",
                error,
            )

        payload = memoryview(buffer.raw)
        result: list[tuple[str, int, int]] = []
        offset = 0
        while True:
            if offset + 24 > buffer_size:
                raise SandboxError(f"truncated FILE_STREAM_INFO for {path}")
            next_offset, name_bytes, size, allocation_size = struct.unpack_from(
                "<IIqq", payload, offset
            )
            if name_bytes % 2 or offset + 24 + name_bytes > buffer_size:
                raise SandboxError(f"invalid FILE_STREAM_INFO name for {path}")
            if size < 0 or allocation_size < 0:
                raise SandboxError(f"negative FILE_STREAM_INFO size for {path}")
            try:
                name = bytes(payload[offset + 24 : offset + 24 + name_bytes]).decode(
                    "utf-16-le", errors="strict"
                )
            except UnicodeDecodeError as error:
                raise SandboxError(
                    f"invalid FILE_STREAM_INFO UTF-16 name for {path}"
                ) from error
            if not name or "\x00" in name:
                raise SandboxError(
                    f"invalid empty/NUL FILE_STREAM_INFO name for {path}"
                )
            result.append((name, size, allocation_size))
            if next_offset == 0:
                return tuple(result)
            if (
                next_offset % 8
                or next_offset < 24 + name_bytes
                or offset + next_offset <= offset
                or offset + next_offset >= buffer_size
            ):
                raise SandboxError(f"invalid FILE_STREAM_INFO chain for {path}")
            offset += next_offset

    def _extended_attribute_bytes(self, handle: int, path: Path) -> int:
        """Return the held handle's EA block size without reading file data.

        Microsoft documents ``NtQueryInformationFile`` for user-mode callers
        and ``FileEaInformation`` specifically returns ``FILE_EA_INFORMATION``.
        Querying the four-byte EA size keeps this check O(entries), independent
        of file content size, and avoids reopening the path.
        """

        status_block = _IO_STATUS_BLOCK()
        information = _FILE_EA_INFORMATION()
        status = self.ntdll.NtQueryInformationFile(
            wintypes.HANDLE(handle),
            ctypes.byref(status_block),
            ctypes.byref(information),
            ctypes.sizeof(information),
            _FILE_EA_INFORMATION_CLASS,
        )
        if status != 0:
            rendered = ctypes.c_uint32(status).value
            raise SandboxError(
                "NtQueryInformationFile(FileEaInformation) failed for "
                f"{path}: NTSTATUS=0x{rendered:08x}"
            )
        if status_block.Information != ctypes.sizeof(information):
            raise SandboxError(
                "NtQueryInformationFile(FileEaInformation) returned an "
                f"unexpected byte count for {path}: {status_block.Information}"
            )
        return int(information.EaSize)

    def _clean_metadata_observation(
        self, handle: int, path: Path, identity: _Win32FileIdentity
    ) -> tuple[int, int]:
        streams = self._data_stream_inventory(handle, path)
        unnamed = tuple(
            stream for stream in streams if stream[0].casefold() == "::$data"
        )
        named = tuple(stream for stream in streams if stream[0].casefold() != "::$data")
        if named:
            rendered = ", ".join(stream[0] for stream in named)
            raise SandboxError(
                f"read authority contains named data streams: {path}: {rendered}"
            )
        is_directory = bool(identity.attributes & _FILE_ATTRIBUTE_DIRECTORY)
        if len(unnamed) > 1 or (not is_directory and len(unnamed) != 1):
            raise SandboxError(
                f"read authority has an invalid unnamed data stream inventory: {path}"
            )
        if not is_directory and unnamed[0][1] != identity.size:
            raise SandboxError(
                f"unnamed data stream size differs from held identity: {path}"
            )
        ea_bytes = self._extended_attribute_bytes(handle, path)
        if ea_bytes:
            raise SandboxError(f"read authority contains extended attributes: {path}")
        return len(unnamed), ea_bytes

    def _hash_file_handle(self, handle: int) -> str:
        digest = hashlib.sha256()
        while True:
            buffer = ctypes.create_string_buffer(1024 * 1024)
            read = wintypes.DWORD()
            if not self.kernel32.ReadFile(
                wintypes.HANDLE(handle),
                buffer,
                len(buffer),
                ctypes.byref(read),
                None,
            ):
                raise _win_error("ReadFile(read identity manifest) failed")
            if read.value == 0:
                return digest.hexdigest()
            digest.update(buffer.raw[: read.value])

    def _acquire_read_identity_guards(
        self,
        entries: tuple[Path, ...],
        identities: tuple[_ValidationIdentity, ...],
        grants: tuple[ReadGrant, ...],
    ) -> _HeldReadIdentitySet:
        if len(entries) != len(identities):
            raise SandboxError("read identity validation table is inconsistent")
        handles: list[int] = []
        manifest: list[dict[str, object]] = []
        try:
            for path, expected in zip(entries, identities, strict=True):
                handle = self._open_identity_guard(path, scratch=False)
                handles.append(handle)
                _assert_validation_identity(
                    path, expected, phase="read identity guard acquisition"
                )
                identity = self._handle_identity(handle)
                is_directory = bool(identity.attributes & _FILE_ATTRIBUTE_DIRECTORY)
                if is_directory != stat.S_ISDIR(expected.st_mode):
                    raise SandboxError(
                        f"read identity handle type differs from validation: {path}"
                    )
                if identity.attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise SandboxError(
                        f"read identity handle resolved to a reparse point: {path}"
                    )
                if not is_directory and identity.number_of_links != 1:
                    raise SandboxError(
                        f"read identity handle has hardlink aliases: {path}"
                    )
                if not is_directory and identity.size != expected.st_size:
                    raise SandboxError(
                        f"read identity file size differs from validation: {path}"
                    )
                content_sha256 = (
                    None if is_directory else self._hash_file_handle(handle)
                )
                unnamed_data_stream_count, extended_attribute_bytes = (
                    self._clean_metadata_observation(handle, path, identity)
                )
                manifest.append(
                    {
                        "extended_attribute_bytes": extended_attribute_bytes,
                        "file_id": identity.file_id.hex(),
                        "kind": "directory" if is_directory else "file",
                        "named_data_stream_count": 0,
                        "path": str(path),
                        "sha256": content_sha256,
                        "size": identity.size,
                        "unnamed_data_stream_count": unnamed_data_stream_count,
                        "volume_serial_number": (
                            f"{identity.volume_serial_number:016x}"
                        ),
                    }
                )

            # Once all entries are pinned, enumerate the authority again.  This
            # catches additions, removals, and traversal substitutions that
            # raced the initial validation before their own guard was opened.
            reexpanded: list[Path] = []
            reexpanded_spellings: dict[str, str] = {}
            for grant in grants:
                for entry in _expand_grant(grant):
                    if _register_exact_case_path(
                        reexpanded_spellings,
                        entry,
                        context="closed read tree re-enumeration",
                    ):
                        reexpanded.append(entry)
            expected_paths = tuple(os.path.normcase(str(path)) for path in entries)
            observed_paths = tuple(os.path.normcase(str(path)) for path in reexpanded)
            if observed_paths != expected_paths:
                raise SandboxError(
                    "read grant tree changed between validation and guard closure"
                )
            for path, expected in zip(entries, identities, strict=True):
                _assert_validation_identity(
                    path, expected, phase="closed read tree re-enumeration"
                )
            canonical = {
                "entries": sorted(
                    manifest,
                    key=lambda item: (
                        os.path.normcase(str(item["path"])),
                        str(item["path"]),
                    ),
                ),
                "schema_version": _READ_IDENTITY_SCHEMA_VERSION,
            }
            payload = json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            return _HeldReadIdentitySet(
                tuple(handles), len(manifest), hashlib.sha256(payload).hexdigest()
            )
        except BaseException:
            for handle in reversed(handles):
                self.close_handle(handle)
            raise

    def _assert_read_metadata_remains_clean(
        self,
        handles: tuple[int, ...],
        entries: tuple[Path, ...],
        *,
        phase: str,
    ) -> None:
        if len(handles) != len(entries):
            raise SandboxError(
                f"read metadata audit table is inconsistent during {phase}"
            )
        for handle, path in zip(handles, entries, strict=True):
            identity = self._handle_identity(handle)
            try:
                self._clean_metadata_observation(handle, path, identity)
            except SandboxError as error:
                raise SandboxError(
                    f"read metadata audit failed during {phase}: {error}"
                ) from error

    def _acquire_scratch_identity_guard(
        self, path: Path, expected: _ValidationIdentity
    ) -> tuple[int, int, _Win32FileIdentity]:
        parent = path.parent
        parent_expected = _validation_identity(parent)
        # Pin the containing namespace as read-only as well as holding the
        # scratch directory itself without FILE_SHARE_DELETE.  Modern Windows
        # rename APIs can operate through a parent directory handle, so the
        # target handle alone is not a sufficient pathname guard.
        parent_handle = self._open_identity_guard(
            parent, scratch=False, namespace_parent=True
        )
        handle: int | None = None
        try:
            _assert_validation_identity(
                parent,
                parent_expected,
                phase="scratch parent namespace guard acquisition",
            )
            handle = self._open_identity_guard(path, scratch=True)
            _assert_validation_identity(
                path, expected, phase="scratch identity guard acquisition"
            )
            identity = self._handle_identity(handle)
            if not identity.attributes & _FILE_ATTRIBUTE_DIRECTORY:
                raise SandboxError("scratch identity guard is not a directory")
            if identity.attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise SandboxError("scratch identity guard is a reparse point")
            if any(path.iterdir()):
                raise SandboxError(
                    f"scratch directory changed or is not empty after pinning: {path}"
                )
            return handle, parent_handle, identity
        except BaseException:
            self.close_handle(handle)
            self.close_handle(parent_handle)
            raise

    def _assert_scratch_identity_guard(
        self,
        handle: int,
        path: Path,
        expected_validation: _ValidationIdentity,
        expected_win32: _Win32FileIdentity,
        *,
        require_empty: bool,
    ) -> None:
        _assert_validation_identity(path, expected_validation, phase="scratch audit")
        if self._handle_identity(handle) != expected_win32:
            raise SandboxCleanupError(
                f"held scratch identity changed unexpectedly: {path}"
            )
        if require_empty and any(path.iterdir()):
            raise SandboxCleanupError(
                f"held scratch directory is not empty at audit: {path}"
            )

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
        wintypes.DWORD,
    ]:
        size = ctypes.c_size_t()
        ctypes.set_last_error(0)
        self.kernel32.InitializeProcThreadAttributeList(None, 4, 0, ctypes.byref(size))
        if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER or size.value == 0:
            raise _win_error("InitializeProcThreadAttributeList size query failed")
        storage = ctypes.create_string_buffer(size.value)
        if not self.kernel32.InitializeProcThreadAttributeList(
            storage, 4, 0, ctypes.byref(size)
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
        child_policy = wintypes.DWORD(_PROCESS_CREATION_CHILD_PROCESS_RESTRICTED)
        if not self.kernel32.UpdateProcThreadAttribute(
            storage,
            0,
            _PROC_THREAD_ATTRIBUTE_CHILD_PROCESS_POLICY,
            ctypes.byref(child_policy),
            ctypes.sizeof(child_policy),
            None,
            None,
        ):
            self.kernel32.DeleteProcThreadAttributeList(storage)
            raise _win_error("UpdateProcThreadAttribute(CHILD_PROCESS_POLICY) failed")
        return storage, capabilities, handle_array, job_array, child_policy

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
        storage, capabilities, handle_array, job_array, child_policy = (
            self._attribute_list(sid, (stdin_handle, stdout_handle, stderr_handle), job)
        )
        # The attribute list stores pointers to these objects.  Keep all three
        # alive through CreateProcessW as required by UpdateProcThreadAttribute.
        keepalive = (capabilities, handle_array, job_array, child_policy)
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
                | _DETACHED_PROCESS,
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

    def _probe_access_winerror(
        self, target: str, desired_access: int, flags: int
    ) -> int:
        """Open one right independently and return zero or its exact Win32 error."""

        ctypes.set_last_error(0)
        handle = self.kernel32.CreateFileW(
            target,
            desired_access,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            flags | _FILE_FLAG_OVERLAPPED,
            None,
        )
        handle_value = ctypes.cast(handle, ctypes.c_void_p).value
        if handle_value == _INVALID_HANDLE_VALUE:
            return ctypes.get_last_error()
        self.close_handle(handle_value)
        return 0

    def _probe_with_token(
        self,
        token: int,
        probes: tuple[AccessProbe, ...],
        guarded_paths: tuple[Path, ...],
    ) -> tuple[tuple[AccessProbeObservation, ...], int, str]:
        """Probe ALLOWED reads and DENIED target/ancestor namespace integrity.

        A DENIED target is not considered safe merely because GENERIC_READ is
        rejected on its root.  Every preexisting descendant is recursively
        expanded and receives the same independent read/execute/mutation audit;
        every existing root ancestor receives the namespace mutation audit.
        ERROR_ACCESS_DENIED proves a DACL/token denial.  ERROR_SHARING_VIOLATION
        is accepted only for delete-like rights on a path whose broker identity
        guard is held without delete sharing through process exit and final
        identity audit.
        """

        empty_manifest = hashlib.sha256(b"[]").hexdigest()
        if not probes:
            return (), 0, empty_manifest

        specifications: list[
            tuple[
                AccessProbe,
                tuple[tuple[str, bool, int, str], ...],
                tuple[Path, ...],
            ]
        ] = []
        for probe in probes:
            tree_entries = (
                _expand_denied_probe_target(probe.path)
                if probe.expected is PathProbeStatus.DENIED
                else (probe.path,)
            )
            entry_specifications = tuple(
                (
                    str(entry),
                    entry.is_dir(),
                    _FILE_FLAG_BACKUP_SEMANTICS
                    if entry.is_dir()
                    else _FILE_ATTRIBUTE_NORMAL,
                    "target" if index == 0 else "descendant",
                )
                for index, entry in enumerate(tree_entries)
            )
            ancestors: list[Path] = []
            ancestor_spellings: dict[str, str] = {}
            if probe.expected is PathProbeStatus.DENIED:
                for ancestor in probe.path.parents:
                    if not ancestor.exists() or not ancestor.is_dir():
                        raise SandboxError(
                            "access probe ancestor disappeared or is not a directory: "
                            f"{ancestor}"
                        )
                    if _register_exact_case_path(
                        ancestor_spellings,
                        ancestor,
                        context=f"ancestors of denied access probe {probe.path}",
                    ):
                        ancestors.append(ancestor)
            specifications.append(
                (
                    probe,
                    entry_specifications,
                    tuple(ancestors),
                )
            )

        guarded_keys = {os.path.normcase(str(path)) for path in guarded_paths}
        target_rights = (
            ("read_winerror", _GENERIC_READ),
            # FILE_EXECUTE and FILE_TRAVERSE share this bit.  Requesting the
            # specific right avoids a denied READ_ATTRIBUTES/READ_CONTROL bit
            # masking accidentally permitted execution/traversal.
            ("execute_traverse_winerror", _FILE_EXECUTE),
            ("generic_write_winerror", _GENERIC_WRITE),
            ("write_data_winerror", _FILE_WRITE_DATA),
            ("append_data_winerror", _FILE_APPEND_DATA),
            ("write_ea_winerror", _FILE_WRITE_EA),
            ("write_attributes_winerror", _FILE_WRITE_ATTRIBUTES),
            ("delete_winerror", _DELETE),
            ("write_dac_winerror", _WRITE_DAC),
            ("write_owner_winerror", _WRITE_OWNER),
        )
        ancestor_rights = (
            ("generic_write_winerror", _GENERIC_WRITE),
            ("add_file_winerror", _FILE_WRITE_DATA),
            ("add_subdirectory_winerror", _FILE_APPEND_DATA),
            ("delete_child_winerror", _FILE_DELETE_CHILD),
            ("write_ea_winerror", _FILE_WRITE_EA),
            ("write_attributes_winerror", _FILE_WRITE_ATTRIBUTES),
            ("delete_winerror", _DELETE),
            ("write_dac_winerror", _WRITE_DAC),
            ("write_owner_winerror", _WRITE_OWNER),
        )
        guard_enforced_labels = {"delete_winerror", "delete_child_winerror"}
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
        denied_manifest: list[dict[str, object]] = []
        failures: list[str] = []
        impersonating = False
        try:
            if not self.advapi32.SetThreadToken(None, impersonation):
                raise _win_error("SetThreadToken(child AppContainer token) failed")
            impersonating = True
            for probe, entries, ancestors in specifications:
                target = str(probe.path)
                if probe.expected is PathProbeStatus.ALLOWED:
                    allowed_target, _is_directory, flags, _role = entries[0]
                    error = self._probe_access_winerror(
                        allowed_target, _GENERIC_READ, flags
                    )
                    observed = (
                        PathProbeStatus.ALLOWED
                        if error == 0
                        else PathProbeStatus.DENIED
                        if error == _ERROR_ACCESS_DENIED
                        else PathProbeStatus.ERROR
                    )
                    observations.append(
                        AccessProbeObservation(target, probe.expected, observed, error)
                    )
                    continue

                tree_errors: list[int] = []
                for entry_target, is_directory, flags, role in entries:
                    rights = list(target_rights)
                    if is_directory:
                        rights.append(("delete_child_winerror", _FILE_DELETE_CHILD))
                    entry_results = {
                        label: self._probe_access_winerror(
                            entry_target, desired_access, flags
                        )
                        for label, desired_access in rights
                    }
                    denied_manifest.append(
                        {
                            "directory": is_directory,
                            "path": entry_target,
                            "probe_path": target,
                            "role": role,
                            "rights": entry_results,
                        }
                    )
                    for label, error in entry_results.items():
                        if error != _ERROR_ACCESS_DENIED:
                            tree_errors.append(error)
                            failures.append(
                                f"denied {role} right is allowed or ambiguous: "
                                f"probe={target} entry={entry_target} "
                                f"right={label} winerror={error}"
                            )

                for ancestor in ancestors:
                    ancestor_target = str(ancestor)
                    ancestor_results = {
                        label: self._probe_access_winerror(
                            ancestor_target,
                            desired_access,
                            _FILE_FLAG_BACKUP_SEMANTICS,
                        )
                        for label, desired_access in ancestor_rights
                    }
                    denied_manifest.append(
                        {
                            "directory": True,
                            "path": ancestor_target,
                            "probe_path": target,
                            "role": "ancestor",
                            "rights": ancestor_results,
                        }
                    )
                    guarded = os.path.normcase(ancestor_target) in guarded_keys
                    for label, error in ancestor_results.items():
                        guard_denied = (
                            guarded
                            and label in guard_enforced_labels
                            and error == _ERROR_SHARING_VIOLATION
                        )
                        if error != _ERROR_ACCESS_DENIED and not guard_denied:
                            failures.append(
                                "denied ancestor right is allowed or ambiguous: "
                                f"probe={target} ancestor={ancestor_target} "
                                f"right={label} winerror={error} guarded={guarded}"
                            )

                if not tree_errors:
                    observations.append(
                        AccessProbeObservation(
                            target,
                            probe.expected,
                            PathProbeStatus.DENIED,
                            _ERROR_ACCESS_DENIED,
                        )
                    )
                else:
                    observations.append(
                        AccessProbeObservation(
                            target,
                            probe.expected,
                            PathProbeStatus.ERROR,
                            tree_errors[0],
                        )
                    )
        finally:
            if impersonating and not self.advapi32.RevertToSelf():
                # Continuing under a sandbox token would make all cleanup
                # observations unreliable.  There is no safe recovery here.
                self.close_handle(impersonation_value)
                raise SandboxCleanupError("RevertToSelf failed after access probes")
            self.close_handle(impersonation_value)
        if failures:
            raise SandboxError("; ".join(failures))
        for observation in observations:
            if observation.observed is not observation.expected:
                raise SandboxError(
                    "pre-resume child-token access probe differs: "
                    f"{observation.path} expected={observation.expected} "
                    f"observed={observation.observed} winerror={observation.winerror}"
                )
        canonical = sorted(
            denied_manifest,
            key=lambda item: (
                os.path.normcase(str(item["probe_path"])),
                str(item["role"]),
                os.path.normcase(str(item["path"])),
                str(item["path"]),
            ),
        )
        payload = json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return tuple(observations), len(canonical), hashlib.sha256(payload).hexdigest()

    def _probe_read_only_with_token(
        self, token: int, entries: tuple[Path, ...]
    ) -> tuple[int, str]:
        """Prove every read grant is readable but grants no mutation right.

        A package-SID RX ACE is not sufficient evidence: an AppContainer token
        can also receive access through another principal such as ALL
        APPLICATION PACKAGES.  Each relevant right is therefore opened
        independently with the exact suspended child token.  Combining the
        rights in one CreateFileW request would let one denied right mask a
        different, accidentally allowed right.
        """

        specifications = tuple(
            (
                str(entry),
                entry.is_dir(),
                _FILE_FLAG_BACKUP_SEMANTICS
                if entry.is_dir()
                else _FILE_ATTRIBUTE_NORMAL,
            )
            for entry in entries
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
            raise _win_error("DuplicateTokenEx(read-only probe token) failed")
        impersonation_value = _handle_value(impersonation)
        observations: list[dict[str, object]] = []
        impersonating = False
        try:
            if not self.advapi32.SetThreadToken(None, impersonation):
                raise _win_error("SetThreadToken(read-only probe token) failed")
            impersonating = True
            for target, is_directory, flags in specifications:
                rights = (
                    ("read_winerror", _GENERIC_READ),
                    ("generic_write_winerror", _GENERIC_WRITE),
                    ("write_data_winerror", _FILE_WRITE_DATA),
                    ("append_data_winerror", _FILE_APPEND_DATA),
                    ("write_ea_winerror", _FILE_WRITE_EA),
                    ("write_attributes_winerror", _FILE_WRITE_ATTRIBUTES),
                    ("delete_winerror", _DELETE),
                    ("write_dac_winerror", _WRITE_DAC),
                    ("write_owner_winerror", _WRITE_OWNER),
                )
                observation: dict[str, object] = {
                    "path": target,
                    "directory": is_directory,
                }
                for label, desired_access in rights:
                    ctypes.set_last_error(0)
                    handle = self.kernel32.CreateFileW(
                        target,
                        desired_access,
                        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
                        None,
                        _OPEN_EXISTING,
                        flags,
                        None,
                    )
                    handle_value = ctypes.cast(handle, ctypes.c_void_p).value
                    if handle_value == _INVALID_HANDLE_VALUE:
                        observation[label] = ctypes.get_last_error()
                    else:
                        observation[label] = 0
                        self.close_handle(handle_value)
                if is_directory:
                    ctypes.set_last_error(0)
                    handle = self.kernel32.CreateFileW(
                        target,
                        _FILE_DELETE_CHILD,
                        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
                        None,
                        _OPEN_EXISTING,
                        flags,
                        None,
                    )
                    handle_value = ctypes.cast(handle, ctypes.c_void_p).value
                    if handle_value == _INVALID_HANDLE_VALUE:
                        observation["file_delete_child_winerror"] = (
                            ctypes.get_last_error()
                        )
                    else:
                        observation["file_delete_child_winerror"] = 0
                        self.close_handle(handle_value)
                else:
                    observation["file_delete_child_winerror"] = None
                observations.append(observation)
        finally:
            if impersonating and not self.advapi32.RevertToSelf():
                self.close_handle(impersonation_value)
                raise SandboxCleanupError(
                    "RevertToSelf failed after read-only access probes"
                )
            self.close_handle(impersonation_value)

        for observation in observations:
            if observation["read_winerror"] != 0:
                raise SandboxError(
                    "pre-resume child token cannot read a granted entry: "
                    f"{observation['path']} "
                    f"winerror={observation['read_winerror']}"
                )
            for label in (
                "generic_write_winerror",
                "write_data_winerror",
                "append_data_winerror",
                "write_ea_winerror",
                "write_attributes_winerror",
                "delete_winerror",
                "write_dac_winerror",
                "write_owner_winerror",
                "file_delete_child_winerror",
            ):
                observed = observation[label]
                if observed is not None and observed != _ERROR_ACCESS_DENIED:
                    raise SandboxError(
                        "pre-resume child token has or ambiguously probes a mutation "
                        f"right: {observation['path']} right={label} "
                        f"winerror={observed}"
                    )
        payload = json.dumps(
            observations,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return len(observations), hashlib.sha256(payload).hexdigest()

    def _probe_scratch_with_token(self, token: int, scratch: Path) -> str:
        """Verify scratch child rights and deny mutation through every ancestor."""

        target = str(scratch)
        rights = (
            ("read_winerror", _GENERIC_READ, 0),
            ("execute_winerror", _FILE_GENERIC_EXECUTE, 0),
            ("add_file_winerror", _FILE_WRITE_DATA, 0),
            ("add_subdirectory_winerror", _FILE_APPEND_DATA, 0),
            ("delete_child_winerror", _FILE_DELETE_CHILD, 0),
            ("generic_write_winerror", _GENERIC_WRITE, _ERROR_ACCESS_DENIED),
            ("write_ea_winerror", _FILE_WRITE_EA, _ERROR_ACCESS_DENIED),
            (
                "write_attributes_winerror",
                _FILE_WRITE_ATTRIBUTES,
                _ERROR_ACCESS_DENIED,
            ),
            ("delete_root_winerror", _DELETE, _ERROR_ACCESS_DENIED),
            ("write_dac_winerror", _WRITE_DAC, _ERROR_ACCESS_DENIED),
            ("write_owner_winerror", _WRITE_OWNER, _ERROR_ACCESS_DENIED),
        )
        ancestor_rights = (
            ("generic_write_winerror", _GENERIC_WRITE),
            ("add_file_winerror", _FILE_WRITE_DATA),
            ("add_subdirectory_winerror", _FILE_APPEND_DATA),
            ("delete_child_winerror", _FILE_DELETE_CHILD),
            ("write_ea_winerror", _FILE_WRITE_EA),
            ("write_attributes_winerror", _FILE_WRITE_ATTRIBUTES),
            ("delete_winerror", _DELETE),
            ("write_dac_winerror", _WRITE_DAC),
            ("write_owner_winerror", _WRITE_OWNER),
        )
        ancestors: list[Path] = []
        ancestor_spellings: dict[str, str] = {}
        for ancestor in scratch.parents:
            if not ancestor.exists() or not ancestor.is_dir():
                raise SandboxError(
                    f"scratch ancestor disappeared or is not a directory: {ancestor}"
                )
            if _register_exact_case_path(
                ancestor_spellings,
                ancestor,
                context=f"ancestors of scratch {scratch}",
            ):
                ancestors.append(ancestor)
        impersonation = wintypes.HANDLE()
        if not self.advapi32.DuplicateTokenEx(
            wintypes.HANDLE(token),
            _TOKEN_QUERY | _TOKEN_IMPERSONATE,
            None,
            _SECURITY_IMPERSONATION,
            _TOKEN_IMPERSONATION,
            ctypes.byref(impersonation),
        ):
            raise _win_error("DuplicateTokenEx(scratch probe token) failed")
        impersonation_value = _handle_value(impersonation)
        root_observation: dict[str, object] = {"path": target}
        ancestor_observations: list[dict[str, object]] = []
        failures: list[str] = []
        impersonating = False
        try:
            if not self.advapi32.SetThreadToken(None, impersonation):
                raise _win_error("SetThreadToken(scratch probe token) failed")
            impersonating = True
            for label, desired_access, _expected in rights:
                root_observation[label] = self._probe_access_winerror(
                    target, desired_access, _FILE_FLAG_BACKUP_SEMANTICS
                )
            for ancestor in ancestors:
                ancestor_target = str(ancestor)
                right_results = {
                    label: self._probe_access_winerror(
                        ancestor_target,
                        desired_access,
                        _FILE_FLAG_BACKUP_SEMANTICS,
                    )
                    for label, desired_access in ancestor_rights
                }
                ancestor_observations.append(
                    {"path": ancestor_target, "rights": right_results}
                )
                guarded = ancestor == scratch.parent
                for label, error in right_results.items():
                    guard_denied = (
                        guarded
                        and label in {"delete_winerror", "delete_child_winerror"}
                        and error == _ERROR_SHARING_VIOLATION
                    )
                    if error != _ERROR_ACCESS_DENIED and not guard_denied:
                        failures.append(
                            "scratch ancestor mutation right is allowed or ambiguous: "
                            f"ancestor={ancestor_target} right={label} "
                            f"winerror={error} guarded={guarded}"
                        )
        finally:
            if impersonating and not self.advapi32.RevertToSelf():
                self.close_handle(impersonation_value)
                raise SandboxCleanupError(
                    "RevertToSelf failed after scratch access probes"
                )
            self.close_handle(impersonation_value)
        for label, _desired_access, expected in rights:
            error = root_observation[label]
            guard_denied = (
                label == "delete_root_winerror" and error == _ERROR_SHARING_VIOLATION
            )
            if error != expected and not guard_denied:
                failures.append(
                    "pre-resume scratch access differs from the minimal policy: "
                    f"{target} right={label} expected_winerror={expected} "
                    f"observed_winerror={error}"
                )
        if failures:
            raise SandboxError("; ".join(failures))
        payload = json.dumps(
            {
                "ancestors": ancestor_observations,
                "root": root_observation,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def verify_process_security(
        self,
        process: int,
        expected_sid: int,
        job: int,
        probes: tuple[AccessProbe, ...],
        read_only_entries: tuple[Path, ...],
        scratch: Path,
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
            (
                observations,
                denied_probe_count,
                denied_probe_manifest,
            ) = self._probe_with_token(
                token,
                probes,
                (*read_only_entries, scratch, scratch.parent),
            )
            read_only_count, read_only_manifest = self._probe_read_only_with_token(
                token, read_only_entries
            )
            scratch_manifest = self._probe_scratch_with_token(token, scratch)
            process_id = self.kernel32.GetProcessId(wintypes.HANDLE(process))
            if process_id == 0:
                raise _win_error("GetProcessId failed")
            return _SecurityObservation(
                process_id=process_id,
                integrity_rid=integrity_rid,
                capability_count=capability_count,
                access_probes=observations,
                denied_probe_entry_count=denied_probe_count,
                denied_probe_manifest_sha256=denied_probe_manifest,
                read_only_probe_entry_count=read_only_count,
                read_only_probe_manifest_sha256=read_only_manifest,
                scratch_access_probe_manifest_sha256=scratch_manifest,
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

    def cancel_io(self, handle: int) -> None:
        ctypes.set_last_error(0)
        if not self.kernel32.CancelIoEx(wintypes.HANDLE(handle), None):
            error = ctypes.get_last_error()
            if error not in {
                _ERROR_NOT_FOUND,
                _ERROR_BROKEN_PIPE,
                _ERROR_NO_DATA,
            }:
                raise _win_error("CancelIoEx(pipe reader) failed", error)

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
        profile_storage_path: Path | None = None
        profile_storage_deleted = False
        baseline_snapshots: list[_SecurityDescriptorSnapshot] = []
        baseline_by_path: dict[str, _SecurityDescriptorSnapshot] = {}
        read_restore_snapshots: list[_SecurityDescriptorSnapshot] = []
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
        held_read_identity: _HeldReadIdentitySet | None = None
        scratch_guard: int | None = None
        scratch_parent_guard: int | None = None
        scratch_win32_identity: _Win32FileIdentity | None = None
        cleanup_errors: list[str] = []
        package_sid = ""
        security_observation: _SecurityObservation | None = None
        preexit_receipt: PreexitReceipt | None = None
        result_fields: dict[str, object] | None = None
        primary_error: BaseException | None = None
        primary_traceback: TracebackType | None = None
        start_ns = time.perf_counter_ns()
        try:
            scratch_guard, scratch_parent_guard, scratch_win32_identity = (
                self._acquire_scratch_identity_guard(
                    validated.scratch, validated.scratch_identity
                )
            )
            held_read_identity = self._acquire_read_identity_guards(
                validated.grant_entries,
                validated.grant_entry_identities,
                validated.grants,
            )
            if (
                held_read_identity.manifest_sha256
                != validated.request.expected_read_identity_manifest_sha256
            ):
                raise SandboxError(
                    "captured read identity manifest differs before security mutation: "
                    f"expected={validated.request.expected_read_identity_manifest_sha256} "
                    f"observed={held_read_identity.manifest_sha256}"
                )
            (
                created_sid,
                derived_sid,
                package_sid,
                profile_storage_path,
            ) = self.create_profile(validated.profile_name)
            profile_created = True
            baseline_paths = (*validated.grant_entries, validated.scratch)
            baseline_snapshots.extend(
                self.snapshot_dacl(path) for path in baseline_paths
            )
            baseline_by_path = {
                os.path.normcase(snapshot.path): snapshot
                for snapshot in baseline_snapshots
            }
            # Grant every already-expanded entry explicitly.  A recursive ACE
            # on only the grant root lets SetNamedSecurityInfo normalize the
            # pre-existing descendants' inherited-ACE metadata; restoring the
            # root then cannot reconstruct every original descriptor byte.
            # Non-inheriting per-entry ACEs keep mutation local and make the
            # root-to-leaf restore below exact for arbitrary mixed/protected
            # trees.  The scratch inheritance policy remains separate because
            # only the untrusted child may create new entries there.
            for entry in validated.grant_entries:
                snapshot = baseline_by_path[os.path.normcase(str(entry))]
                read_restore_snapshots.append(snapshot)
                self.grant_sid(
                    snapshot,
                    created_sid,
                    _FILE_GENERIC_READ | _FILE_GENERIC_EXECUTE,
                    _NO_INHERITANCE,
                )
            scratch_snapshot = baseline_by_path[
                os.path.normcase(str(validated.scratch))
            ]
            self.grant_sid(
                scratch_snapshot,
                created_sid,
                _FILE_GENERIC_READ
                | _FILE_GENERIC_EXECUTE
                | _FILE_WRITE_DATA
                | _FILE_APPEND_DATA
                | _FILE_DELETE_CHILD,
                _NO_INHERITANCE,
            )
            scratch_with_root_grant = self.snapshot_dacl(validated.scratch)
            self.grant_sid(
                scratch_with_root_grant,
                created_sid,
                _FILE_GENERIC_READ
                | _FILE_GENERIC_WRITE
                | _FILE_GENERIC_EXECUTE
                | _DELETE
                | _FILE_DELETE_CHILD,
                _INHERIT_ONLY_SUB_CONTAINERS_AND_OBJECTS,
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
                process,
                created_sid,
                job,
                validated.probes,
                validated.grant_entries,
                validated.scratch,
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
            self._assert_read_metadata_remains_clean(
                held_read_identity.handles,
                validated.grant_entries,
                phase="immediately before child resume",
            )
            self.resume(thread)

            reason = TerminationReason.COMPLETED
            deadline_ns = time.perf_counter_ns() + int(
                validated.request.timeout_seconds * 1_000_000_000
            )
            terminated = False
            while True:
                accounting = self.query_job(job)
                if (
                    stdout_reader.failure_event.is_set()
                    or stderr_reader.failure_event.is_set()
                ):
                    stdout_error = stdout_reader.result().error
                    stderr_error = stderr_reader.result().error
                    raise SandboxError(
                        "sandbox output reader failed while the Job was active: "
                        f"stdout={stdout_error!r} stderr={stderr_error!r}"
                    )
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
                    and stdout_reader.eof_event.is_set()
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
                    if time.perf_counter_ns() >= deadline_ns:
                        raise SandboxError(
                            "sandbox deadline elapsed before the pre-exit callback"
                        )
                    active_before_callback = accounting.BasicInfo.ActiveProcesses
                    root_before_callback = (
                        self.process_exit_code(process) == _STILL_ACTIVE
                    )
                    if (
                        active_before_callback != 1
                        or accounting.BasicInfo.TotalProcesses != 1
                        or accounting.BasicInfo.TotalTerminatedProcesses != 0
                        or not root_before_callback
                    ):
                        raise SandboxError(
                            "candidate root is not the sole never-replaced Job process "
                            "at pre-exit: "
                            f"active={active_before_callback} "
                            f"total={accounting.BasicInfo.TotalProcesses} "
                            f"terminated={accounting.BasicInfo.TotalTerminatedProcesses} "
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
                    after_callback_accounting = self.query_job(job).BasicInfo
                    after_callback = after_callback_accounting.ActiveProcesses
                    root_before_ack = self.process_exit_code(process) == _STILL_ACTIVE
                    if (
                        time.perf_counter_ns() >= deadline_ns
                        or after_callback != 1
                        or after_callback_accounting.TotalProcesses != 1
                        or after_callback_accounting.TotalTerminatedProcesses != 0
                        or not root_before_ack
                    ):
                        raise SandboxError(
                            "candidate Job changed, deadline elapsed, or root exited "
                            "before observer released ACK: "
                            f"active={after_callback} "
                            f"total={after_callback_accounting.TotalProcesses} "
                            "terminated="
                            f"{after_callback_accounting.TotalTerminatedProcesses} "
                            f"root_active={root_before_ack}"
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

            if reason is TerminationReason.COMPLETED and (
                accounting.BasicInfo.TotalProcesses != 1
                or accounting.BasicInfo.TotalTerminatedProcesses != 0
            ):
                raise SandboxError(
                    "completed sandbox execution did not contain exactly one "
                    "unterminated process lifetime: "
                    f"total={accounting.BasicInfo.TotalProcesses} "
                    f"terminated={accounting.BasicInfo.TotalTerminatedProcesses}"
                )

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
        except BaseException as exc:
            # Preserve the primary failure, but do not let Python's automatic
            # re-raise skip the post-cleanup audit below.
            primary_error = exc
            primary_traceback = exc.__traceback__
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
                thread,
                process,
                job,
            ):
                try:
                    self.close_handle(handle)
                except BaseException as exc:
                    cleanup_errors.append(f"handle cleanup: {exc}")
            for reader, handle, role in (
                (stdout_reader, stdout_read, "stdout"),
                (stderr_reader, stderr_read, "stderr"),
            ):
                if reader is not None and reader.is_alive() and handle is not None:
                    try:
                        self.cancel_io(handle)
                    except BaseException as exc:
                        cleanup_errors.append(f"{role} reader cancellation: {exc}")
                    reader.join(timeout=5.0)
                    if reader.is_alive():
                        cleanup_errors.append(
                            f"{role} reader remained alive after CancelIoEx"
                        )
                try:
                    self.close_handle(handle)
                except BaseException as exc:
                    cleanup_errors.append(f"{role} read handle cleanup: {exc}")
            if scratch_guard is not None and scratch_win32_identity is not None:
                try:
                    # Authorize path-based cleanup only after proving that the
                    # pathname still names the directory pinned before any
                    # profile/ACL/process action.  A replacement tree is never
                    # traversed or deleted.
                    self._assert_scratch_identity_guard(
                        scratch_guard,
                        validated.scratch,
                        validated.scratch_identity,
                        scratch_win32_identity,
                        require_empty=False,
                    )
                    _empty_scratch(validated.scratch)
                    self._assert_scratch_identity_guard(
                        scratch_guard,
                        validated.scratch,
                        validated.scratch_identity,
                        scratch_win32_identity,
                        require_empty=True,
                    )
                except BaseException as exc:
                    cleanup_errors.append(f"scratch cleanup: {exc}")
            # Read entries are ordered root-to-leaf.  Restoring each through
            # SetNamedSecurityInfo first re-establishes its original
            # inheritance metadata after the local explicit ACE is removed;
            # a later child restore overwrites any normalization caused by its
            # ancestors.  Scratch is last and still requires reverse
            # propagation to remove its inherited package ACE from children
            # created by the untrusted process.
            ordered_read_restores = sorted(
                read_restore_snapshots,
                key=lambda snapshot: (
                    len(Path(snapshot.path).parts),
                    os.path.normcase(snapshot.path),
                    snapshot.path,
                ),
            )
            for snapshot in ordered_read_restores:
                try:
                    self.restore_dacl_propagating(snapshot)
                except BaseException as exc:
                    cleanup_errors.append(f"ACL restore for {snapshot.path}: {exc}")
            if scratch_snapshot is not None:
                try:
                    self.restore_dacl_propagating(scratch_snapshot)
                except BaseException as exc:
                    cleanup_errors.append(
                        f"ACL restore for {scratch_snapshot.path}: {exc}"
                    )
            for baseline in baseline_snapshots:
                try:
                    restored = self.snapshot_dacl(Path(baseline.path))
                    if (
                        restored.payload != baseline.payload
                        or restored.protected != baseline.protected
                    ) and _differs_only_by_auto_inherited_metadata(baseline, restored):
                        # Reverse propagation can leave AUTO_INHERITED and
                        # INHERITED_ACE metadata on a baseline no-AI root or
                        # descendant.  Replaying DACL-only is safe only after
                        # structural proof that nothing else changed.  A
                        # baseline AI object is never replayed.
                        restored = self.restore_dacl_exact(baseline)
                    if (
                        restored.payload != baseline.payload
                        or restored.protected != baseline.protected
                    ):
                        raise SandboxCleanupError(
                            f"security descriptor was not restored exactly: {baseline.path}"
                        )
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
            if scratch_guard is not None and scratch_win32_identity is not None:
                try:
                    self._assert_scratch_identity_guard(
                        scratch_guard,
                        validated.scratch,
                        validated.scratch_identity,
                        scratch_win32_identity,
                        require_empty=True,
                    )
                except BaseException as exc:
                    cleanup_errors.append(f"scratch identity final audit: {exc}")
            if held_read_identity is not None:
                try:
                    self._assert_read_metadata_remains_clean(
                        held_read_identity.handles,
                        validated.grant_entries,
                        phase="final post-execution audit",
                    )
                except BaseException as exc:
                    cleanup_errors.append(f"read metadata final audit: {exc}")
                for handle in reversed(held_read_identity.handles):
                    try:
                        self.close_handle(handle)
                    except BaseException as exc:
                        cleanup_errors.append(f"read identity guard cleanup: {exc}")
            if scratch_guard is not None:
                try:
                    self.close_handle(scratch_guard)
                except BaseException as exc:
                    cleanup_errors.append(f"scratch identity guard cleanup: {exc}")
                scratch_guard = None
            if scratch_parent_guard is not None:
                try:
                    self.close_handle(scratch_parent_guard)
                except BaseException as exc:
                    cleanup_errors.append(
                        f"scratch parent namespace guard cleanup: {exc}"
                    )
                scratch_parent_guard = None
            if profile_created:
                try:
                    self.delete_profile(validated.profile_name, profile_storage_path)
                    profile_deleted = True
                    profile_storage_deleted = (
                        profile_storage_path is not None
                        and not os.path.lexists(profile_storage_path)
                    )
                except BaseException as exc:
                    cleanup_errors.append(f"profile deletion: {exc}")
            self.free_sid(derived_sid)
            self.free_sid(created_sid)
        if cleanup_errors:
            raise SandboxCleanupError("; ".join(cleanup_errors)) from primary_error
        if primary_error is not None:
            raise primary_error.with_traceback(primary_traceback)
        if result_fields is None:
            raise SandboxError("sandbox failed before producing a result")
        if security_observation is None:
            raise SandboxError("sandbox failed before process security observation")
        if profile_storage_path is None:
            raise SandboxError("sandbox has no AppContainer profile storage authority")
        if held_read_identity is None:
            raise SandboxError("sandbox has no held read identity observation")
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
            profile_storage_path=str(profile_storage_path),
            capabilities=(),
            allowed_read_paths=tuple(str(grant.path) for grant in validated.grants),
            read_identity_manifest_entry_count=held_read_identity.entry_count,
            read_identity_manifest_sha256=held_read_identity.manifest_sha256,
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
            denied_probe_entry_count=security_observation.denied_probe_entry_count,
            denied_probe_manifest_sha256=(
                security_observation.denied_probe_manifest_sha256
            ),
            read_only_probe_entry_count=(
                security_observation.read_only_probe_entry_count
            ),
            read_only_probe_manifest_sha256=(
                security_observation.read_only_probe_manifest_sha256
            ),
            scratch_access_probe_manifest_sha256=(
                security_observation.scratch_access_probe_manifest_sha256
            ),
            max_processes=validated.request.max_processes,
            child_process_restricted=True,
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
            profile_storage_deleted=profile_storage_deleted,
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

    serialization = _BrokerSerialization()
    serialization.acquire()
    primary: BaseException | None = None
    try:
        _validate_request(request)
        if (request.preexit_payload_limit_bytes is None) != (on_preexit is None):
            raise SandboxError(
                "pre-exit frame limit and trusted callback must be supplied together"
            )
        backend = _api if _api is not None else _WindowsApi()
        return backend.run(request, on_preexit)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            serialization.release()
        except BaseException as exc:
            raise SandboxCleanupError(
                f"broker serialization cleanup failed: {exc}"
            ) from primary


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

    read_identity = capture_read_identity_manifest(
        executable=python_executable, allowed_read=allowed_read
    )
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
        expected_read_identity_manifest_sha256=read_identity.sha256,
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
    "ReadIdentityManifest",
    "SandboxAttestation",
    "SandboxCleanupError",
    "SandboxError",
    "SandboxRequest",
    "SandboxResult",
    "TerminationReason",
    "UnsupportedPlatformError",
    "capture_read_identity_manifest",
    "run_python_path_probe",
    "run_sandboxed",
)
