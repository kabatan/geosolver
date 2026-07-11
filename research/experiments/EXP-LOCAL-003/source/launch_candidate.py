"""Claim-first C0 launcher for one formal candidate observation.

The launcher intentionally knows nothing about the future C2 candidate
implementation.  Its first persistent mutation is an empty, exclusive,
write-through marker in the C0-provisioned external namespace.  A fresh nonce
is then written through the *same* file identity.  Only after that terminal
claim is durable may the frozen C0 :mod:`candidate_observer` be imported.

The future C2 Julia runner is never imported or evaluated in this process.  It
is launched directly by the C0 observer through the Windows AppContainer
broker.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import secrets
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Literal, cast


sys.dont_write_bytecode = True


Stage = Literal["development", "locked"]
CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"
EXPERIMENT_ID = "EXP-LOCAL-003"
SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
RUN_EVIDENCE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-run-evidence") / EXPERIMENT_ID
)
SANDBOX_SCRATCH_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-sandbox-scratch") / EXPERIMENT_ID
)
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
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

OBSERVER_API = "observe_claimed"
OBSERVER_MODULE = "candidate_observer"
CLAIM_SCHEMA = "geotarget.exp-local-003.candidate-launch-attempt/v2"
DIRECT_FORMAL_EXECUTION_PROHIBITED = True


class CandidateLaunchError(RuntimeError):
    """The terminal candidate launch contract cannot continue safely."""


@dataclass(frozen=True, slots=True)
class FileIdentity:
    """Stable identity of the marker that was first created empty."""

    device: int
    inode: int
    empty_claim_ctime_nanoseconds: int
    link_count: int


@dataclass(frozen=True, slots=True)
class LaunchClaim:
    """Durable nonce-bound marker passed to the C0 observer."""

    path: Path
    payload: bytes
    nonce: str
    identity: FileIdentity

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    @property
    def nonce_sha256(self) -> str:
        return hashlib.sha256(bytes.fromhex(self.nonce)).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidencePaths:
    """Fixed external publication paths for one stage."""

    root: Path
    scratch_root: Path
    evidence_repository: Path
    staging_repository: Path
    attempt_marker: Path
    scratch_directory: Path

    @classmethod
    def fixed(
        cls,
        stage: Stage,
        *,
        root: Path = RUN_EVIDENCE_ROOT,
        scratch_root: Path | None = None,
    ) -> EvidencePaths:
        name = f"{stage}-candidate-run"
        fixed_root = root.absolute()
        if scratch_root is None:
            fixed_scratch_root = (
                SANDBOX_SCRATCH_ROOT.absolute()
                if fixed_root == RUN_EVIDENCE_ROOT.absolute()
                else fixed_root.with_name(f"{fixed_root.name}-sandbox-scratch")
            )
        else:
            fixed_scratch_root = scratch_root.absolute()
        return cls(
            root=fixed_root,
            scratch_root=fixed_scratch_root,
            evidence_repository=fixed_root / name,
            staging_repository=fixed_root / f".{name}-staging.partial",
            attempt_marker=fixed_root / f"{name}.attempt",
            scratch_directory=fixed_scratch_root / f".{name}-scratch.partial",
        )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _marker_bytes(stage: Stage, nonce: str) -> bytes:
    if len(nonce) != 64:
        raise CandidateLaunchError("candidate launch nonce is not 256 bits")
    try:
        bytes.fromhex(nonce)
    except ValueError as error:
        raise CandidateLaunchError(
            "candidate launch nonce is not lowercase hex"
        ) from error
    if nonce != nonce.lower():
        raise CandidateLaunchError("candidate launch nonce is not lowercase hex")
    return _canonical_bytes(
        {
            "card_sha256": CARD_SHA256,
            "failure_is_terminal": True,
            "nonce": nonce,
            "rerun_permitted": False,
            "schema_version": CLAIM_SCHEMA,
            "stage": stage,
        }
    )


def _lexists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _reject_reparse_ancestry(path: Path, *, include_leaf: bool) -> None:
    candidate = path.absolute()
    chain = (candidate, *candidate.parents) if include_leaf else candidate.parents
    for entry in chain:
        try:
            metadata = entry.lstat()
        except FileNotFoundError:
            continue
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse:
            raise CandidateLaunchError(
                f"candidate evidence path traverses a reparse point: {entry}"
            )


def _verify_preimport_hygiene() -> None:
    """Reject every known pre-claim Python import-injection surface."""

    if sys.flags.no_site != 1 or "site" in sys.modules:
        raise CandidateLaunchError(
            "formal candidate launcher requires site-disabled `python -I -B -S`"
        )
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise CandidateLaunchError(
            f"formal candidate launcher has injection environment: {blocked}"
        )
    if any("site-packages" in value.casefold() for value in sys.path):
        raise CandidateLaunchError(
            "site-packages was active before the candidate claim"
        )
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise CandidateLaunchError(
                    f"stale project bytecode exists under {current}"
                )


def _activate_claimed_import_paths() -> None:
    """Expose fixed imports without loading ``site`` or processing ``.pth``."""

    try:
        executable = Path(sys.executable).resolve(strict=True)
        venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    except OSError as error:
        raise CandidateLaunchError(
            "fixed project venv cannot be resolved after the candidate claim"
        ) from error
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise CandidateLaunchError(
            "formal candidate launcher is not using the fixed project venv executable"
        )
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise CandidateLaunchError("fixed project venv site-packages is unavailable")
    _reject_reparse_ancestry(site_packages, include_leaf=True)
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _identity(info: os.stat_result) -> FileIdentity:
    return FileIdentity(
        device=info.st_dev,
        inode=info.st_ino,
        empty_claim_ctime_nanoseconds=info.st_ctime_ns,
        link_count=info.st_nlink,
    )


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_empty(path: Path) -> None:
    """Create and flush a zero-byte marker without ever opening existing data."""

    if os.name == "nt":
        _write_windows(path, b"", create_new=True)
        return
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_SYNC", 0),
        0o444,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def _fill_existing(path: Path, payload: bytes) -> None:
    """Fill an empty marker with write-through, never truncating or replacing it."""

    if os.name == "nt":
        _write_windows(path, payload, create_new=False)
        return
    flags = os.O_WRONLY | getattr(os, "O_SYNC", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if before.st_size != 0 or before.st_nlink != 1:
            raise CandidateLaunchError("empty candidate marker identity changed")
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("candidate marker write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def _write_windows(path: Path, payload: bytes, *, create_new: bool) -> None:
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

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
    if not create_new:
        info = path.stat()
        if info.st_size != 0 or info.st_nlink != 1:
            raise CandidateLaunchError("empty candidate marker identity changed")
    disposition = 1 if create_new else 3  # CREATE_NEW / OPEN_EXISTING
    handle = create(str(path), 0x40000000, 0, None, disposition, 0x80000080, None)
    if handle == wintypes.HANDLE(-1).value:
        error = ctypes.get_last_error()
        if create_new and error in (80, 183):
            raise FileExistsError(
                error, "candidate execution attempt already exists", str(path)
            )
        raise ctypes.WinError(error)
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
                raise OSError("candidate marker write made no progress")
            offset += written.value
        if not flush(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException as error:
        failure = error
        raise
    finally:
        if not close(handle) and failure is None:
            raise ctypes.WinError(ctypes.get_last_error())


def _assert_unattempted(paths: EvidencePaths) -> None:
    occupied = [
        path
        for path in (
            paths.evidence_repository,
            paths.staging_repository,
            paths.attempt_marker,
            paths.scratch_directory,
        )
        if _lexists(path)
    ]
    if occupied:
        raise CandidateLaunchError(
            "candidate execution cannot overwrite, resume, or retry: "
            + ", ".join(str(path) for path in occupied)
        )


def verify_claim(claim: LaunchClaim, paths: EvidencePaths) -> None:
    """Re-read the durable marker and prove that its initial identity remains."""

    if claim.path != paths.attempt_marker or claim.identity.link_count != 1:
        raise CandidateLaunchError("candidate launch claim path/link identity differs")
    try:
        metadata = claim.path.lstat()
        observed = claim.path.read_bytes()
    except OSError as error:
        raise CandidateLaunchError(
            "durable candidate attempt marker vanished"
        ) from error
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or attributes & reparse
        or metadata.st_nlink != 1
        or metadata.st_dev != claim.identity.device
        or metadata.st_ino != claim.identity.inode
        or observed != claim.payload
        or observed
        != _marker_bytes(cast(Stage, json.loads(observed)["stage"]), claim.nonce)
    ):
        raise CandidateLaunchError("durable candidate attempt marker differs")


def _claim(stage: Stage, paths: EvidencePaths) -> LaunchClaim:
    _assert_unattempted(paths)
    _reject_reparse_ancestry(paths.root, include_leaf=True)
    if not paths.root.is_dir():
        raise CandidateLaunchError(
            "C0-provisioned candidate evidence namespace is unavailable"
        )
    _reject_reparse_ancestry(paths.root, include_leaf=True)
    _reject_reparse_ancestry(paths.scratch_root, include_leaf=True)
    if not paths.scratch_root.is_dir():
        raise CandidateLaunchError(
            "C0-provisioned candidate scratch namespace is unavailable"
        )
    if (
        paths.scratch_root == paths.root
        or paths.scratch_root in paths.root.parents
        or paths.root in paths.scratch_root.parents
    ):
        raise CandidateLaunchError("candidate scratch and evidence namespaces overlap")
    try:
        # This is deliberately the first persistent mutation.
        _exclusive_empty(paths.attempt_marker)
    except FileExistsError as error:
        raise CandidateLaunchError(
            "candidate execution attempt already exists"
        ) from error
    empty_info = paths.attempt_marker.lstat()
    empty_identity = _identity(empty_info)
    if empty_info.st_size != 0 or empty_identity.link_count != 1:
        raise CandidateLaunchError(
            "exclusive candidate marker was not empty/single-link"
        )
    nonce = secrets.token_hex(32)
    payload = _marker_bytes(stage, nonce)
    _fill_existing(paths.attempt_marker, payload)
    claim = LaunchClaim(paths.attempt_marker, payload, nonce, empty_identity)
    verify_claim(claim, paths)
    # Close the check/create race.  The marker remains a terminal attempt even
    # if a competing writer occupied one of the other fixed names.
    if any(
        _lexists(path)
        for path in (
            paths.evidence_repository,
            paths.staging_repository,
            paths.scratch_directory,
        )
    ):
        raise CandidateLaunchError(
            "candidate evidence appeared while claiming the terminal attempt"
        )
    return claim


def _load_observer() -> ModuleType:
    # Production reaches this point only after the durable terminal claim.
    _activate_claimed_import_paths()
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))
    module = importlib.import_module(OBSERVER_MODULE)
    module_file = getattr(module, "__file__", None)
    expected = SOURCE_ROOT / f"{OBSERVER_MODULE}.py"
    if (
        not isinstance(module_file, str)
        or Path(module_file).resolve() != expected.resolve()
    ):
        raise CandidateLaunchError("candidate_observer module path is not fixed")
    return module


def launch(
    stage: Stage,
    *,
    paths: EvidencePaths | None = None,
    module_loader: Callable[[], ModuleType] = _load_observer,
) -> object:
    """Claim exactly once, then invoke only the frozen C0 observer."""

    if stage not in ("development", "locked"):
        raise CandidateLaunchError("candidate stage must be development or locked")
    selected = paths or EvidencePaths.fixed(stage)
    if selected != EvidencePaths.fixed(
        stage, root=selected.root, scratch_root=selected.scratch_root
    ):
        raise CandidateLaunchError("candidate evidence paths are not the fixed layout")
    claim = _claim(stage, selected)
    module = module_loader()
    observer = getattr(module, OBSERVER_API, None)
    if not callable(observer):
        raise CandidateLaunchError("candidate_observer.observe_claimed is unavailable")
    if getattr(module, "C0_OBSERVER_OWNS_CANDIDATE_PROCESS", None) is not True:
        raise CandidateLaunchError("candidate observer ownership marker differs")
    verify_claim(claim, selected)
    if any(
        _lexists(path)
        for path in (
            selected.evidence_repository,
            selected.staging_repository,
            selected.scratch_directory,
        )
    ):
        raise CandidateLaunchError(
            "candidate boundary changed during C0 observer import"
        )
    return observer(stage=stage, paths=selected, claim=claim)


def _verify_formal_invocation(argv: list[str]) -> Stage:
    flags = (
        sys.flags.isolated,
        sys.flags.ignore_environment,
        sys.flags.no_user_site,
        sys.flags.dont_write_bytecode,
        sys.flags.no_site,
    )
    if (
        flags != (1, 1, 1, 1, 1)
        or sys.flags.safe_path is not True
        or sys.flags.optimize != 0
    ):
        raise CandidateLaunchError(
            "formal candidate launcher requires `python -I -B -S launch_candidate.py`"
        )
    if len(argv) != 2 or argv[1] not in ("development", "locked"):
        raise CandidateLaunchError(
            "usage: python -I -B -S launch_candidate.py development|locked"
        )
    try:
        script = Path(argv[0]).resolve(strict=True)
        main_file = Path(sys.modules["__main__"].__file__).resolve(strict=True)
        cwd = Path.cwd().resolve(strict=True)
    except (AttributeError, KeyError, OSError, TypeError) as error:
        raise CandidateLaunchError(
            "formal candidate CLI path resolution failed"
        ) from error
    expected = Path(__file__).resolve(strict=True)
    if script != expected or main_file != expected:
        raise CandidateLaunchError("formal candidate launcher path differs")
    if not os.path.samefile(cwd, REPOSITORY_ROOT):
        raise CandidateLaunchError(
            "formal candidate launcher must run from the main repository root"
        )
    _verify_preimport_hygiene()
    return cast(Stage, argv[1])


def main(argv: list[str] | None = None) -> int:
    stage = _verify_formal_invocation(list(sys.argv if argv is None else argv))
    launch(stage)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CandidateLaunchError as error:
        print(f"formal-candidate-launch-failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
