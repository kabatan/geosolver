"""Pure-stdlib, claim-first launcher for EXP-LOCAL-003 C2 equivalence."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
OUTPUT_RELATIVE = "research/experiments/EXP-LOCAL-003/C2_L0_DEFAULT_EQUIVALENCE.json"
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

# Keep malformed non-``-B`` invocations from dirtying project directories.
sys.dont_write_bytecode = True


class LaunchError(RuntimeError):
    """The formal invocation or irreversible claim operation failed."""


def _verify_preimport_hygiene() -> None:
    if sys.flags.no_site != 1 or "site" in sys.modules:
        raise LaunchError("formal C2 launch requires `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise LaunchError(f"C2 launch has injection environment: {blocked}")
    if any("site-packages" in value.casefold() for value in sys.path):
        raise LaunchError("site-packages was active before the C2 claim")
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise LaunchError(f"stale project bytecode exists under {current}")


def _activate_claimed_import_paths() -> None:
    executable = Path(sys.executable).resolve(strict=True)
    venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise LaunchError("formal C2 Python is not the fixed project venv executable")
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise LaunchError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _output_path() -> Path:
    return REPOSITORY_ROOT.joinpath(*OUTPUT_RELATIVE.split("/"))


def _claim_windows(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    flush_file_buffers = kernel32.FlushFileBuffers
    flush_file_buffers.argtypes = (wintypes.HANDLE,)
    flush_file_buffers.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        str(path),
        0x40000000,  # GENERIC_WRITE
        0,
        None,
        1,  # CREATE_NEW
        0x00000080 | 0x80000000,  # NORMAL | WRITE_THROUGH
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error in (80, 183):
            raise LaunchError(f"C2 equivalence claim already exists: {path}")
        raise LaunchError(f"CreateFileW(CREATE_NEW) failed: winerror={error}")
    flush_ok = bool(flush_file_buffers(handle))
    flush_error = 0 if flush_ok else ctypes.get_last_error()
    close_ok = bool(close_handle(handle))
    close_error = 0 if close_ok else ctypes.get_last_error()
    if not flush_ok:
        raise LaunchError(f"claim FlushFileBuffers failed: winerror={flush_error}")
    if not close_ok:
        raise LaunchError(f"claim CloseHandle failed: winerror={close_error}")


def _claim_posix(path: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise LaunchError(f"C2 equivalence claim already exists: {path}") from error
    except OSError as error:
        raise LaunchError(f"cannot create C2 equivalence claim: {error}") from error
    try:
        os.fsync(descriptor)
    except OSError as error:
        raise LaunchError(f"cannot flush C2 equivalence claim: {error}") from error
    finally:
        os.close(descriptor)
    try:
        parent_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except OSError as error:
        raise LaunchError(f"cannot flush claim directory: {error}") from error


def _claim() -> Path:
    path = _output_path()
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
            raise LaunchError(f"C2 claim traverses a reparse point: {entry}")
    try:
        parent = path.parent.lstat()
    except OSError as error:
        raise LaunchError(f"claim parent is unavailable: {error}") from error
    if (
        not stat.S_ISDIR(parent.st_mode)
        or stat.S_ISLNK(parent.st_mode)
        or getattr(parent, "st_file_attributes", 0) & reparse
    ):
        raise LaunchError("claim parent is not a regular non-reparse directory")
    if os.name == "nt":
        _claim_windows(path)
    else:
        _claim_posix(path)
    return path


def _invoke_helper() -> Path:
    # The durable claim exists before this first project/third-party import.
    _activate_claimed_import_paths()
    from capture_c2_equivalence import capture

    return capture(claim_already_created=True)


def launch() -> Path:
    claimed = _claim()
    result = _invoke_helper()
    if result.resolve() != claimed.resolve():
        raise LaunchError("C2 capture helper returned a different claim path")
    return result


def _verify_formal_invocation() -> None:
    if len(sys.argv) != 1:
        raise LaunchError("C2 equivalence launcher accepts no arguments")
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode is not True
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
    ):
        raise LaunchError(
            "formal invocation requires `python -I -B -S` without optimization"
        )
    expected = Path(__file__).resolve(strict=True)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if (
        Path(sys.argv[0]).resolve(strict=True) != expected
        or not isinstance(main_file, str)
        or Path(main_file).resolve(strict=True) != expected
    ):
        raise LaunchError(
            "formal C2 equivalence launcher must execute this script directly"
        )
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise LaunchError("formal invocation must run from repository root")
    _verify_preimport_hygiene()


def main() -> int:
    _verify_formal_invocation()
    result = launch()
    print(f"created {result.relative_to(REPOSITORY_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
