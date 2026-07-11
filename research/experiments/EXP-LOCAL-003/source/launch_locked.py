"""Pure-stdlib, claim-first launcher for locked input materialization."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = SOURCE_ROOT.parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
ATTEMPT_PATH = EXPERIMENT_ROOT / "LOCKED_ATTEMPT_CLAIM.json"
FAILURE_PATH = EXPERIMENT_ROOT / "LOCKED_TERMINAL_FAILURE.json"
CLAIM_BYTES = (
    b'{"attempt_ordinal":0,"authority_validation_occurs_after_claim":true,'
    b'"card_sha256":"0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c",'
    b'"failure_is_terminal":true,"rerun_permitted":false,'
    b'"schema_version":"exp-local-003-locked-attempt-claim/v1"}'
)
FAILURE_BYTES = (
    b'{"failure_is_terminal":true,"rerun_permitted":false,'
    b'"schema_version":"exp-local-003-locked-launcher-terminal/v1"}'
)
_BLOCKED_ENVIRONMENT_PREFIXES = (
    "COVERAGE_",
    "COV_CORE_",
    "PYTEST_",
    "PYTHON",
    "DD_",
    "OTEL_",
    "NEW_RELIC_",
    "SENTRY_",
    "PYDEVD_",
)


def _verify_preimport_hygiene() -> None:
    if sys.flags.no_site != 1 or "site" in sys.modules:
        raise RuntimeError("formal locked launcher requires `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise RuntimeError(
            f"formal locked launcher has injection environment: {blocked}"
        )
    if any("site-packages" in value.casefold() for value in sys.path):
        raise RuntimeError("site-packages was active before the locked claim")
    for root in (SOURCE_ROOT, REPOSITORY_ROOT / "python" / "src"):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise RuntimeError(f"stale project bytecode exists under {current}")


def _activate_claimed_import_paths() -> None:
    executable = Path(sys.executable).resolve(strict=True)
    venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise RuntimeError(
            "formal locked Python is not the fixed project venv executable"
        )
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise RuntimeError("fixed project venv site-packages is unavailable")
    for path in reversed(
        (SOURCE_ROOT, REPOSITORY_ROOT / "python" / "src", site_packages)
    ):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _reject_reparse_ancestry(path: Path) -> None:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for entry in (path.parent.absolute(), *path.parent.absolute().parents):
        try:
            metadata = entry.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & reparse
        ):
            raise RuntimeError(
                f"formal locked claim traverses a reparse point: {entry}"
            )


def _exclusive_write(path: Path, payload: bytes) -> None:
    if os.name == "nt":
        _exclusive_write_windows(path, payload)
        return
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_SYNC", 0)
    )
    descriptor = os.open(path, flags, 0o444)
    try:
        offset = 0
        while offset < len(payload):
            count = os.write(descriptor, payload[offset:])
            if count <= 0:
                raise OSError("exclusive launcher write made no progress")
            offset += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if os.name != "nt":
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)


def _exclusive_write_windows(path: Path, payload: bytes) -> None:
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    write = kernel32.WriteFile
    write.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    write.restype = wintypes.BOOL
    flush = kernel32.FlushFileBuffers
    flush.argtypes = [wintypes.HANDLE]
    flush.restype = wintypes.BOOL
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    handle = create(str(path), 0x40000000, 0, None, 1, 0x80000080, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + 0x7FFF_FFFF]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not write(handle, buffer, len(chunk), ctypes.byref(written), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value <= 0:
                raise OSError("exclusive launcher write made no progress")
            offset += written.value
        if not flush(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        close(handle)


def _verify_launcher() -> None:
    flags = (
        sys.flags.isolated,
        sys.flags.ignore_environment,
        sys.flags.no_user_site,
        sys.flags.safe_path,
        sys.flags.dont_write_bytecode,
        sys.flags.no_site,
        sys.flags.optimize,
    )
    if flags != (1, 1, 1, True, 1, 1, 0):
        raise RuntimeError(
            "formal locked launcher requires `python -I -B -S launch_locked.py`"
        )
    if len(sys.argv) != 1:
        raise RuntimeError("formal locked launcher accepts no options")
    expected = Path(__file__).resolve(strict=True)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if (
        Path(sys.argv[0]).resolve(strict=True) != expected
        or not isinstance(main_file, str)
        or Path(main_file).resolve(strict=True) != expected
    ):
        raise RuntimeError("formal locked launcher must execute this script directly")
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise RuntimeError("formal locked launcher must run from repository root")
    _verify_preimport_hygiene()


def main() -> int:
    _verify_launcher()
    _reject_reparse_ancestry(ATTEMPT_PATH)
    _exclusive_write(ATTEMPT_PATH, CLAIM_BYTES)
    try:
        _activate_claimed_import_paths()
        import materialize_locked as materializer

        output = materializer.materialize(claim_already_created=True)
    except BaseException:
        if not FAILURE_PATH.exists():
            try:
                _exclusive_write(FAILURE_PATH, FAILURE_BYTES)
            except OSError:
                pass
        raise
    print(f"materialized frozen LOCAL003 locked inputs at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
