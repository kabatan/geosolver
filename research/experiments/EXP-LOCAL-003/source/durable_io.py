"""Small C0-owned crash-durable filesystem primitives.

Formal callers use these after their irreversible attempt claim.  Creation is
exclusive, Windows handles request write-through, POSIX writes fsync both file
and parent, and directory publication is atomically no-replace.
"""

from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path


class DurabilityError(OSError):
    """The operating system could not satisfy the formal durability contract."""


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise DurabilityError("durable write made no forward progress")
        view = view[written:]


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def exclusive_write(path: Path, payload: bytes, *, mode: int = 0o444) -> None:
    """Create exactly one new file and durably write all bytes."""

    if os.name == "nt":
        _exclusive_write_windows(path, payload)
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_SYNC", 0)
        descriptor = os.open(path, flags, mode)
        try:
            _write_all(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_parent(path)
    if path.read_bytes() != payload:
        raise DurabilityError(f"durable file bytes differ after creation: {path}")


def _exclusive_write_windows(path: Path, payload: bytes) -> None:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create.restype = wintypes.HANDLE
    write = kernel32.WriteFile
    write.argtypes = (
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    )
    write.restype = wintypes.BOOL
    flush = kernel32.FlushFileBuffers
    flush.argtypes = (wintypes.HANDLE,)
    flush.restype = wintypes.BOOL
    close = kernel32.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handle = create(str(path), 0x40000000, 0, None, 1, 0x80000080, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    failure: BaseException | None = None
    try:
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + 0x7FFF_FFFF]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not write(handle, buffer, len(chunk), ctypes.byref(written), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value <= 0:
                raise DurabilityError("durable Windows write made no progress")
            offset += written.value
        if not flush(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException as error:
        failure = error
        raise
    finally:
        if not close(handle) and failure is None:
            raise ctypes.WinError(ctypes.get_last_error())


def durable_write(path: Path, payload: bytes) -> None:
    """Flush a newly staged file before its directory is published."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if path.read_bytes() != payload:
        raise DurabilityError(f"durable staged bytes differ: {path}")


def _flush_directory_tree(root: Path) -> None:
    directories = [path for path in root.rglob("*") if path.is_dir()]
    directories.sort(key=lambda path: len(path.parts), reverse=True)
    for directory in (*directories, root):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def durable_rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish a directory and fail if the destination exists."""

    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move = kernel32.MoveFileExW
        move.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong)
        move.restype = ctypes.c_int
        # MOVEFILE_WRITE_THROUGH without MOVEFILE_REPLACE_EXISTING.
        if not move(str(source), str(destination), 0x00000008):
            raise ctypes.WinError(ctypes.get_last_error())
        return

    _flush_directory_tree(source)
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise DurabilityError(
            "formal POSIX publication requires renameat2(RENAME_NOREPLACE)"
        )
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, os.strerror(error), str(destination))
        raise DurabilityError(error, os.strerror(error), str(destination))
    for parent in {source.parent, destination.parent}:
        descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
