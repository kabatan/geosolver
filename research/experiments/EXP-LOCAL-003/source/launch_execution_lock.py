"""Pure-stdlib, claim-first launcher for EXP-LOCAL-003 execution locks."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Final, Literal, TypeAlias, cast


Stage: TypeAlias = Literal["development", "locked"]

SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
EXPERIMENT_PREFIX: Final = "research/experiments/EXP-LOCAL-003"
OUTPUT_PATHS: Final = {
    "development": f"{EXPERIMENT_PREFIX}/candidate-execution-lock.json",
    "locked": f"{EXPERIMENT_PREFIX}/locked-candidate-execution-lock.json",
}
_BLOCKED_ENVIRONMENT_PREFIXES: Final = (
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

# Invalid invocations must not create project bytecode before ``main`` rejects
# them.  The immutable flag still proves whether the caller supplied ``-B``.
sys.dont_write_bytecode = True


class LaunchError(RuntimeError):
    """The formal invocation or irreversible claim operation failed."""


def _verify_preimport_hygiene() -> None:
    if sys.flags.no_site != 1 or "site" in sys.modules:
        raise LaunchError("formal execution-lock launch requires `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise LaunchError(f"execution-lock launch has injection environment: {blocked}")
    if any("site-packages" in value.casefold() for value in sys.path):
        raise LaunchError("site-packages was active before the execution-lock claim")
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
        raise LaunchError(
            "formal execution-lock Python is not the fixed project venv executable"
        )
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise LaunchError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _output_path(stage: Stage) -> Path:
    return REPOSITORY_ROOT.joinpath(*OUTPUT_PATHS[stage].split("/"))


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
    generic_write = 0x40000000
    create_new = 1
    file_attribute_normal = 0x00000080
    file_flag_write_through = 0x80000000
    invalid_handle = ctypes.c_void_p(-1).value
    handle = create_file(
        str(path),
        generic_write,
        0,
        None,
        create_new,
        file_attribute_normal | file_flag_write_through,
        None,
    )
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        if error in (80, 183):
            raise LaunchError(f"execution-lock claim already exists: {path}")
        raise LaunchError(f"CreateFileW(CREATE_NEW) failed for claim: winerror={error}")
    flush_ok = bool(flush_file_buffers(handle))
    flush_error = 0 if flush_ok else ctypes.get_last_error()
    close_ok = bool(close_handle(handle))
    close_error = 0 if close_ok else ctypes.get_last_error()
    if not flush_ok:
        raise LaunchError(
            f"FlushFileBuffers failed for durable claim: winerror={flush_error}"
        )
    if not close_ok:
        raise LaunchError(
            f"CloseHandle failed for durable claim: winerror={close_error}"
        )


def _claim_posix(path: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise LaunchError(f"execution-lock claim already exists: {path}") from error
    except OSError as error:
        raise LaunchError(f"cannot create execution-lock claim: {error}") from error
    try:
        os.fsync(descriptor)
    except OSError as error:
        raise LaunchError(f"cannot flush execution-lock claim: {error}") from error
    finally:
        os.close(descriptor)
    try:
        parent_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except OSError as error:
        raise LaunchError(
            f"cannot flush execution-lock claim directory: {error}"
        ) from error


def _claim(stage: Stage) -> Path:
    path = _output_path(stage)
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
            raise LaunchError(
                f"execution-lock claim traverses a reparse point: {entry}"
            )
    try:
        parent_info = path.parent.lstat()
    except OSError as error:
        raise LaunchError(
            f"execution-lock claim parent is unavailable: {error}"
        ) from error
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_ISLNK(parent_info.st_mode)
        or getattr(parent_info, "st_file_attributes", 0) & reparse
    ):
        raise LaunchError("execution-lock claim parent directory is unavailable")
    if os.name == "nt":
        _claim_windows(path)
    else:
        _claim_posix(path)
    return path


def _invoke_helper(stage: Stage) -> Path:
    # This is deliberately the first project/third-party import boundary.  The
    # durable CREATE_NEW/O_EXCL claim already exists whenever execution arrives
    # here, so import, validation, or process failure permanently consumes the
    # attempt.
    _activate_claimed_import_paths()
    from freeze_execution_lock import freeze

    return freeze(stage, claim_already_created=True)


def launch(stage: Stage) -> Path:
    """Durably claim first, then load and invoke the validating helper."""

    claimed = _claim(stage)
    result = _invoke_helper(stage)
    if result.resolve() != claimed.resolve():
        raise LaunchError("execution-lock helper returned a different claim path")
    return result


def _verify_formal_invocation() -> Stage:
    if len(sys.argv) != 2 or sys.argv[1] not in OUTPUT_PATHS:
        raise LaunchError("expected exactly one stage argument: development|locked")
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
            "formal execution-lock launcher must execute this script directly"
        )
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise LaunchError("formal invocation must run from the repository root")
    _verify_preimport_hygiene()
    return cast(Stage, sys.argv[1])


def main() -> int:
    stage = _verify_formal_invocation()
    result = launch(stage)
    print(f"created {result.relative_to(REPOSITORY_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
