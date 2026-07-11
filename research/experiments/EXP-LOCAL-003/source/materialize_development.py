"""One-shot C1 materializer for EXP-LOCAL-003 development inputs.

This module is C0 source. Importing it does not generate an input. The CLI is
enabled only by a future immutable ``preimplementation-lock.json`` at the exact
clean HEAD that introduced that lock. There is no force, resume, overwrite, or
output-path option.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

sys.dont_write_bytecode = True

from jsonschema import Draft202012Validator  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
if str(PYTHON_SOURCE) not in sys.path:
    sys.path.insert(0, str(PYTHON_SOURCE))

from geotarget.canonical import canonical_bytes, canonical_hash  # noqa: E402
from geotarget.validation import validate_document  # noqa: E402


SOURCE_ROOT = EXPERIMENT_ROOT / "source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from durable_io import (  # noqa: E402
    durable_rename_noreplace,
    durable_write,
    exclusive_write,
)

CARD_PATH = EXPERIMENT_ROOT.parent / "EXP-LOCAL-003.json"
LOCK_PATH = EXPERIMENT_ROOT / "preimplementation-lock.json"
VISIBILITY_PATH = EXPERIMENT_ROOT / "visibility-contract.json"
NUMERIC_DOMAIN_PATH = EXPERIMENT_ROOT / "numeric-json-domain.json"
LOCAL_OPTIONS_PATH = EXPERIMENT_ROOT / "local-options-contract.json"
ENVIRONMENT_LOCK_PATH = EXPERIMENT_ROOT / "environment-lock.json"
CANDIDATE_OUTPUT_PATH = EXPERIMENT_ROOT / "development-candidate-inputs"
CANDIDATE_STAGING_PATH = EXPERIMENT_ROOT / ".C1-candidate-staging.partial"
VAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-vault")
    / "EXP-LOCAL-003"
    / "development-assessor-vault"
)
PRIVATE_VAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-private-audit")
    / "EXP-LOCAL-003"
    / "development-generator-private-vault"
)
RUN_EVIDENCE_NAMESPACE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-run-evidence") / "EXP-LOCAL-003"
)
ASSESSMENT_EVIDENCE_NAMESPACE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-assessment-evidence")
    / "EXP-LOCAL-003"
)
SANDBOX_SCRATCH_NAMESPACE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-sandbox-scratch")
    / "EXP-LOCAL-003"
)
FORMAL_OUTCOME_NAMESPACE_ROOTS = (
    RUN_EVIDENCE_NAMESPACE_ROOT,
    ASSESSMENT_EVIDENCE_NAMESPACE_ROOT,
    SANDBOX_SCRATCH_NAMESPACE_ROOT,
)
FORMAL_JULIA_DEPOT_PATH = REPOSITORY_ROOT.with_name(
    f"{REPOSITORY_ROOT.name}-julia-depot-local3"
)
VAULT_STAGING_PATH = VAULT_OUTPUT_PATH.with_name(
    f".{VAULT_OUTPUT_PATH.name}-staging.partial"
)
PRIVATE_VAULT_STAGING_PATH = PRIVATE_VAULT_OUTPUT_PATH.with_name(
    f".{PRIVATE_VAULT_OUTPUT_PATH.name}-staging.partial"
)
ATTEMPT_PATH = EXPERIMENT_ROOT / "C1_ATTEMPT_CLAIM.json"
FAILURE_PATH = EXPERIMENT_ROOT / "C1_TERMINAL_FAILURE.json"
VAULT_ANCHOR_PATH = EXPERIMENT_ROOT / "C1_STAGE_VAULT_ANCHOR.json"
PRIVATE_VAULT_ANCHOR_PATH = EXPERIMENT_ROOT / "C1_PRIVATE_AUDIT_ANCHOR.json"
COMPLETION_NAME = "ONE_SHOT_COMPLETE.json"
CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"

EXPECTED_ASSESSOR_VAULT_FILES = frozenset(
    {
        COMPLETION_NAME,
        "manifest.json",
        "assessor/manifest.json",
        "assessor/development-assessor-truth.json.gz",
        "assessor/development-bootstrap-indices.bin",
    }
)
EXPECTED_PRIVATE_VAULT_FILES = frozenset(
    {
        COMPLETION_NAME,
        "manifest.json",
        "generator-private/manifest.json",
        "generator-private/development-generator-private.json.gz",
        "generator-private/development-generator-assessor-projection.json.gz",
        "generator-private/development-calibration-capture.json.gz",
    }
)

FAMILY_IDS = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "REDUNDANT-OVERDETERMINED",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)
PRIMARY_REPRESENTATIONS = (
    "base",
    "signed-permutation",
    "semantic-equivalent-row-rescaling",
)
SAFETY_REPRESENTATION = "orthogonal-safety"

CANDIDATE_CASE_KEYS = {
    "opaque_case_key",
    "problem_document",
    "problem_sha256",
    "calibration_points",
    "calibration_points_sha256",
    "starts",
    "starts_sha256",
    "public_numeric_metadata",
    "budget",
}
FORBIDDEN_CANDIDATE_KEYS = {
    "family",
    "family_id",
    "family_ordinal",
    "factors",
    "latent_group",
    "latent_group_id",
    "representation",
    "expected_invariant",
    "primary",
    "calibration_key",
    "calibration_key_hex",
    "start_key",
    "start_key_hex",
    "gold",
    "gold_configurations",
    "gold_targets",
    "analytic_truth",
    "expected_decision",
    "configuration_tolerance",
    "target_tolerance",
    "tolerances",
}
FORBIDDEN_CANDIDATE_MARKERS = tuple(value.lower() for value in FAMILY_IDS) + (
    "signed-permutation",
    "semantic-equivalent-row-rescaling",
    "orthogonal-safety",
)
LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
CONTENT_HASH = re.compile(r"^sha256:([0-9a-f]{64})$")
FORBIDDEN_MECHANISM_PATHS = (
    "julia/GeoTargetCore/src/local_model_transform.jl",
    "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl",
    "julia/GeoTargetCore/test/test_local_model_transform.jl",
    "research/experiments/EXP-LOCAL-003/C2_L0_DEFAULT_EQUIVALENCE.json",
    "research/experiments/EXP-LOCAL-003/candidate-execution-lock.json",
    "research/experiments/EXP-LOCAL-003/locked-candidate-execution-lock.json",
    "research/experiments/EXP-LOCAL-003/development-candidate-inputs",
)


class MaterializationError(RuntimeError):
    """A frozen precondition or projection invariant failed closed."""


_VALIDATION_CHILD_CPU_NANOSECONDS: int | None = None


def _begin_validation_child_accounting() -> None:
    global _VALIDATION_CHILD_CPU_NANOSECONDS
    if _VALIDATION_CHILD_CPU_NANOSECONDS is not None:
        raise MaterializationError("formal child accounting is already active")
    _VALIDATION_CHILD_CPU_NANOSECONDS = 0


def _validation_child_cpu_nanoseconds() -> int:
    return _VALIDATION_CHILD_CPU_NANOSECONDS or 0


def _end_validation_child_accounting() -> None:
    global _VALIDATION_CHILD_CPU_NANOSECONDS
    _VALIDATION_CHILD_CPU_NANOSECONDS = None


if os.name == "nt":

    class _FileTime(ctypes.Structure):
        _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))


def _windows_process_cpu_nanoseconds(process: subprocess.Popen[bytes]) -> int:
    if os.name != "nt":
        raise MaterializationError("formal child CPU accounting requires Windows")
    creation = _FileTime()
    exit_time = _FileTime()
    kernel = _FileTime()
    user = _FileTime()
    get_process_times = ctypes.windll.kernel32.GetProcessTimes
    get_process_times.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_FileTime),
        ctypes.POINTER(_FileTime),
        ctypes.POINTER(_FileTime),
        ctypes.POINTER(_FileTime),
    )
    get_process_times.restype = wintypes.BOOL
    if not get_process_times(
        int(process._handle),  # type: ignore[attr-defined]
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise MaterializationError("GetProcessTimes failed for formal Julia child")
    kernel_100ns = (kernel.high << 32) | kernel.low
    user_100ns = (user.high << 32) | user.low
    return (kernel_100ns + user_100ns) * 100


def _run_accounted_bytes(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    validation_child: bool = False,
) -> tuple[subprocess.CompletedProcess[bytes], int]:
    """Run one formal child and read its final OS-owned CPU counter."""

    global _VALIDATION_CHILD_CPU_NANOSECONDS
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        stdout, stderr = process.communicate()
        child_cpu_nanoseconds = _windows_process_cpu_nanoseconds(process)
        completed = subprocess.CompletedProcess(
            command, process.returncode, stdout, stderr
        )
    if validation_child and _VALIDATION_CHILD_CPU_NANOSECONDS is not None:
        _VALIDATION_CHILD_CPU_NANOSECONDS += child_cpu_nanoseconds
    return completed, child_cpu_nanoseconds


def _run_accounted_text(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    validation_child: bool = False,
) -> tuple[subprocess.CompletedProcess[str], int]:
    completed, cpu = _run_accounted_bytes(
        command,
        cwd=cwd,
        env=env,
        validation_child=validation_child,
    )
    return (
        subprocess.CompletedProcess(
            completed.args,
            completed.returncode,
            completed.stdout.decode("utf-8", errors="replace"),
            completed.stderr.decode("utf-8", errors="replace"),
        ),
        cpu,
    )


def _required_c0_files() -> set[str]:
    required = {
        CARD_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        VISIBILITY_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        NUMERIC_DOMAIN_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        LOCAL_OPTIONS_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        ENVIRONMENT_LOCK_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "docs/research/EXP-LOCAL-003.md",
        "toolchain.toml",
        ".julia-version",
        ".python-version",
        ".gitattributes",
        "julia/Project.toml",
        "julia/Manifest.toml",
        "python/pyproject.toml",
        "python/uv.lock",
    }
    trees = (
        SOURCE_ROOT,
        REPOSITORY_ROOT / "schemas",
        REPOSITORY_ROOT / "python" / "src" / "geotarget",
        REPOSITORY_ROOT / "julia" / "GeoTargetBase" / "src",
        REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "src",
        REPOSITORY_ROOT / "julia" / "GeoTargetGeometry" / "src",
    )
    for tree in trees:
        for path in tree.rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            ):
                required.add(path.relative_to(REPOSITORY_ROOT).as_posix())
    for project in (
        REPOSITORY_ROOT / "julia" / "GeoTargetBase" / "Project.toml",
        REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "Project.toml",
        REPOSITORY_ROOT / "julia" / "GeoTargetGeometry" / "Project.toml",
    ):
        required.add(project.relative_to(REPOSITORY_ROOT).as_posix())
    return required


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _environment_tree_record(
    root: Path,
    *,
    included: tuple[str, ...] = (".",),
    excluded_parts: frozenset[str] = frozenset(),
    excluded_suffixes: frozenset[str] = frozenset(),
    require_sandbox_safe: bool = False,
) -> dict[str, Any]:
    if not root.is_dir():
        raise MaterializationError(f"environment tree root is unavailable: {root}")
    root_metadata = root.lstat()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if require_sandbox_safe and (
        root.is_symlink()
        or getattr(root_metadata, "st_file_attributes", 0) & reparse_flag
    ):
        raise MaterializationError(f"environment tree root is reparse-backed: {root}")
    files: list[Path] = []
    for relative_root in included:
        start = root if relative_root == "." else root / relative_root
        if not start.exists():
            raise MaterializationError(f"environment subtree is unavailable: {start}")
        candidates = [start] if start.is_file() else [start, *start.rglob("*")]
        for path in candidates:
            metadata = path.lstat()
            if require_sandbox_safe and (
                path.is_symlink()
                or getattr(metadata, "st_file_attributes", 0) & reparse_flag
            ):
                raise MaterializationError(
                    f"environment tree contains link/reparse entry: {path}"
                )
            if require_sandbox_safe and path.is_file() and metadata.st_nlink != 1:
                raise MaterializationError(
                    f"environment tree contains hardlinked file: {path}"
                )
            relative = path.relative_to(root)
            if (
                path.is_file()
                and not (set(relative.parts) & excluded_parts)
                and path.suffix not in excluded_suffixes
            ):
                files.append(path)
    unique = sorted(set(files), key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256(b"GTLOCAL3ENVTREE1\0")
    total_bytes = 0
    for path in unique:
        relative_bytes = path.relative_to(root).as_posix().encode("utf-8")
        content_digest = bytes.fromhex(_sha256_path(path))
        size = path.stat().st_size
        total_bytes += size
        digest.update(struct.pack(">I", len(relative_bytes)))
        digest.update(relative_bytes)
        digest.update(struct.pack(">Q", size))
        digest.update(content_digest)
    return {
        "root": str(root),
        "included": list(included),
        "excluded_parts": sorted(excluded_parts),
        "excluded_suffixes": sorted(excluded_suffixes),
        "file_count": len(unique),
        "total_bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }


def _publication_tree_record(root: Path) -> dict[str, Any]:
    """Hash one candidate-visible tree while rejecting links and reparse points."""

    if not root.is_dir():
        raise MaterializationError(f"publication tree is unavailable: {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        is_reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if path.is_symlink() or is_reparse:
            raise MaterializationError(
                f"publication tree contains link/reparse: {path}"
            )
        if path.is_file():
            if path.lstat().st_nlink != 1:
                raise MaterializationError(
                    f"publication tree contains hardlinked file: {path}"
                )
            files.append(path)
    files.sort(key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256(b"GTLOCAL3PUBLICATIONTREE1\0")
    total_bytes = 0
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        total_bytes += size
        digest.update(struct.pack(">I", len(relative)))
        digest.update(relative)
        digest.update(struct.pack(">Q", size))
        digest.update(bytes.fromhex(_sha256_path(path)))
    return {
        "file_count": len(files),
        "total_bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }


def _python_base_runtime_included(root: Path) -> tuple[str, ...]:
    """Select executable, stdlib and native DLL trees, not a whole conda install."""

    candidates = ["DLLs", "Lib", "Library/bin", "python.exe"]
    candidates.extend(path.name for path in root.glob("python*.dll"))
    candidates.extend(path.name for path in root.glob("python*.zip"))
    candidates.extend(path.name for path in root.glob("vcruntime*.dll"))
    included = tuple(sorted({name for name in candidates if (root / name).exists()}))
    if "Lib" not in included or not any(name.startswith("python") for name in included):
        raise MaterializationError("Python base runtime layout is incomplete")
    return included


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MaterializationError(f"{path} is not a JSON object")
    return value


def _schema(name: str) -> dict[str, Any]:
    return _load_object(SOURCE_ROOT / name)


def _validate_schema(document: Any, name: str) -> None:
    try:
        Draft202012Validator(_schema(name)).validate(document)
    except Exception as exc:
        raise MaterializationError(
            f"{name} rejected a generated document: {exc}"
        ) from exc


def _raw_content_hash(value: Any, *, context: str) -> str:
    digest = canonical_hash(value)
    return _raw_prefixed_hash(digest, context=context)


def _raw_prefixed_hash(digest: Any, *, context: str) -> str:
    if not isinstance(digest, str):
        raise MaterializationError(f"{context} is not a string content hash")
    match = CONTENT_HASH.fullmatch(digest)
    if match is None:
        raise MaterializationError(f"{context} is not a canonical SHA-256 content hash")
    return match.group(1)


def _float_from_bits(value: Any, *, context: str) -> float:
    if not isinstance(value, str) or re.fullmatch(r"0x[0-9a-f]{16}", value) is None:
        raise MaterializationError(f"{context} is not one binary64 bit pattern")
    return struct.unpack(">d", int(value[2:], 16).to_bytes(8, "big"))[0]


def _finite_hex(value: float, *, context: str) -> str:
    if not math.isfinite(value):
        raise MaterializationError(f"{context} must be a finite binary64 value")
    return value.hex()


def _julia_executable() -> str:
    executable = os.environ.get("JULIA") or shutil.which("julia")
    if not executable:
        raise MaterializationError("Julia executable not found; set JULIA explicitly")
    return executable


def _formal_julia_environment(runtime: Path) -> dict[str, str]:
    """Return the complete, non-inheriting environment for formal Julia work."""

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    formal_home = FORMAL_JULIA_DEPOT_PATH / "formal-home"
    formal_tmp = FORMAL_JULIA_DEPOT_PATH / "formal-tmp"
    formal_home.mkdir(parents=True, exist_ok=True)
    formal_tmp.mkdir(parents=True, exist_ok=True)
    return {
        "SystemRoot": str(system_root),
        "WINDIR": str(system_root),
        "PATH": os.pathsep.join((str(runtime.parent), str(system_root / "System32"))),
        "HOME": str(formal_home),
        "USERPROFILE": str(formal_home),
        "TEMP": str(formal_tmp),
        "TMP": str(formal_tmp),
        "JULIA_DEPOT_PATH": str(FORMAL_JULIA_DEPOT_PATH),
        "JULIA_LOAD_PATH": os.pathsep.join(("@", "@stdlib")),
        "JULIA_PROJECT": str(REPOSITORY_ROOT / "julia"),
        "JULIA_NUM_THREADS": "1",
        "JULIA_CPU_TARGET": "generic",
        "JULIA_PKG_OFFLINE": "true",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }


def _python_execution_record() -> dict[str, Any]:
    """Capture Python state that can alter imports or numeric execution."""

    flags = {
        "isolated": sys.flags.isolated,
        "ignore_environment": sys.flags.ignore_environment,
        "no_user_site": sys.flags.no_user_site,
        "safe_path": sys.flags.safe_path,
        "dont_write_bytecode": bool(sys.flags.dont_write_bytecode),
        "no_site": sys.flags.no_site,
        "optimize": sys.flags.optimize,
        "utf8_mode": sys.flags.utf8_mode,
        "hash_randomization": sys.flags.hash_randomization,
        "int_max_str_digits": sys.flags.int_max_str_digits,
    }
    required_flags = {
        "isolated": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
        "dont_write_bytecode": True,
        "no_site": 1,
        "optimize": 0,
        "utf8_mode": 0,
        "hash_randomization": 1,
        "int_max_str_digits": 4300,
    }
    if flags != required_flags:
        raise MaterializationError(
            "formal Python must be invoked with `python -I -B -S` and no optimization"
        )
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise MaterializationError(
            "formal Python working directory must be repository root"
        )
    host_keys = ("PATH", "PATHEXT", "SystemRoot", "WINDIR", "TEMP", "TMP")
    return {
        "flags": flags,
        "cwd": str(Path.cwd().resolve()),
        "sys_prefix": str(Path(sys.prefix)),
        "sys_base_prefix": str(Path(sys.base_prefix)),
        "sys_path": list(sys.path),
        "host_environment": {name: os.environ.get(name) for name in host_keys},
    }


def _fixed_python_environment_root() -> Path:
    """Resolve the project venv independently of ``sys.prefix`` under ``-S``."""

    try:
        executable = Path(sys.executable).resolve(strict=True)
        expected = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    except OSError as error:
        raise MaterializationError(
            "fixed Python environment cannot be resolved"
        ) from error
    if (
        executable.parent.parent != expected
        or executable.name.casefold() != "python.exe"
    ):
        raise MaterializationError(
            "formal Python executable is not the fixed project venv"
        )
    return expected


def _pinned_git_executable() -> Path:
    if ENVIRONMENT_LOCK_PATH.is_file():
        document = _load_object(ENVIRONMENT_LOCK_PATH)
        tools = document.get("tools")
        if not isinstance(tools, dict) or not isinstance(
            tools.get("git_executable"), str
        ):
            raise MaterializationError("environment lock lacks the Git executable")
        executable = Path(tools["git_executable"])
        if not executable.is_file() or tools.get("git_sha256") != _sha256_path(
            executable
        ):
            raise MaterializationError("environment-locked Git executable drift")
        return executable
    executable = Path(shutil.which("git") or "")
    if not executable.is_file():
        raise MaterializationError("Git executable is unavailable")
    return executable


def _closed_git_environment() -> dict[str, str]:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    git_path = _pinned_git_executable()
    return {
        "SystemRoot": str(system_root),
        "WINDIR": str(system_root),
        "PATH": os.pathsep.join((str(git_path.parent), str(system_root / "System32"))),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git_command_prefix() -> list[str]:
    return [
        str(_pinned_git_executable()),
        "--no-replace-objects",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "commit.gpgSign=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.fsync=committed,reference",
        "-c",
        "core.fsyncMethod=fsync",
    ]


def _local_options_sha256() -> str:
    contract = _load_object(LOCAL_OPTIONS_PATH)
    if set(contract) != {
        "schema_version",
        "card_sha256",
        "source_path",
        "source_sha256",
        "julia_version",
        "capture_contract",
        "constructor",
        "constructor_sha256",
        "binary64_bits",
    }:
        raise MaterializationError("local options contract is not closed")
    if contract.get("schema_version") != "exp-local-003-local-options-contract/v1":
        raise MaterializationError("local options contract schema mismatch")
    if contract.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("local options contract card mismatch")
    source_path = contract.get("source_path")
    source_sha = contract.get("source_sha256")
    if source_path != "julia/GeoTargetCore/src/local_solver.jl":
        raise MaterializationError("local options source path drift")
    if _sha256_path(REPOSITORY_ROOT / source_path) != source_sha:
        raise MaterializationError("C0 LocalSolveOptions source hash drift")
    constructor = contract.get("constructor")
    if not isinstance(constructor, dict) or set(constructor) != {
        "max_iterations",
        "max_evaluations",
        "residual_tolerance_hex",
        "step_tolerance_hex",
        "finite_difference_step_hex",
        "initial_damping_hex",
        "damping_increase_hex",
        "damping_decrease_hex",
    }:
        raise MaterializationError("LocalSolveOptions constructor record is not closed")
    digest = _raw_content_hash(constructor, context="LocalSolveOptions constructor")
    if digest != contract.get("constructor_sha256"):
        raise MaterializationError("LocalSolveOptions constructor digest drift")
    if (
        constructor.get("max_iterations") != 250
        or constructor.get("max_evaluations") != 2000
    ):
        raise MaterializationError("LocalSolveOptions budget drift")
    bits = contract.get("binary64_bits")
    float_fields = (
        "residual_tolerance",
        "step_tolerance",
        "finite_difference_step",
        "initial_damping",
        "damping_increase",
        "damping_decrease",
    )
    if not isinstance(bits, dict) or set(bits) != set(float_fields):
        raise MaterializationError("LocalSolveOptions bit record is not closed")
    for name, value in constructor.items():
        if name.endswith("_hex"):
            parsed = float.fromhex(value)
            if not math.isfinite(parsed) or parsed <= 0.0 or parsed.hex() != value:
                raise MaterializationError(f"invalid frozen LocalSolveOptions {name}")
            field = name.removesuffix("_hex")
            expected_bits = (
                f"0x{struct.unpack('>Q', struct.pack('>d', parsed))[0]:016x}"
            )
            if bits.get(field) != expected_bits:
                raise MaterializationError(
                    f"LocalSolveOptions {field} hex/bit mismatch"
                )
    if contract.get("julia_version") != "1.12.6" or not isinstance(
        contract.get("capture_contract"), str
    ):
        raise MaterializationError("LocalSolveOptions capture environment drift")
    return digest


def _verify_numeric_runtime(runtime: Path, environment: dict[str, str]) -> None:
    completed, _ = _run_accounted_text(
        [
            str(runtime),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            f"--project={REPOSITORY_ROOT / 'julia'}",
            str(SOURCE_ROOT / "verify_numeric_environment.jl"),
            str(NUMERIC_DOMAIN_PATH),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        validation_child=True,
    )
    if completed.returncode != 0 or completed.stdout != "numeric-environment-ok":
        raise MaterializationError(
            f"Julia numeric/FMA environment gate failed: {completed.stderr.strip()}"
        )


def _assert_locked_julia_trees_unchanged() -> None:
    document = _load_object(ENVIRONMENT_LOCK_PATH)
    julia = document.get("julia")
    if not isinstance(julia, dict):
        raise MaterializationError("locked Julia tree authority is malformed")
    runtime_value = julia.get("runtime_executable")
    runtime_record = julia.get("runtime_tree")
    depot_record = julia.get("depot_tree")
    if (
        not isinstance(runtime_value, str)
        or not isinstance(runtime_record, dict)
        or not isinstance(depot_record, dict)
    ):
        raise MaterializationError("locked Julia tree authority is incomplete")
    runtime_root = Path(runtime_value).parent.parent
    observed_runtime = _environment_tree_record(
        runtime_root,
        included=tuple(runtime_record["included"]),
        excluded_parts=frozenset(runtime_record["excluded_parts"]),
        excluded_suffixes=frozenset(runtime_record["excluded_suffixes"]),
        require_sandbox_safe=True,
    )
    observed_depot = _environment_tree_record(
        FORMAL_JULIA_DEPOT_PATH,
        included=tuple(depot_record["included"]),
        excluded_parts=frozenset(depot_record["excluded_parts"]),
        excluded_suffixes=frozenset(depot_record["excluded_suffixes"]),
        require_sandbox_safe=True,
    )
    if observed_runtime != runtime_record or observed_depot != depot_record:
        raise MaterializationError(
            "formal Julia phase mutated a locked environment tree"
        )


def verify_frozen_environment() -> None:
    document = _load_object(ENVIRONMENT_LOCK_PATH)
    if set(document) != {
        "schema_version",
        "card_sha256",
        "platform",
        "julia",
        "python",
        "tools",
        "execution",
        "numeric_fixture_sha256",
    }:
        raise MaterializationError("environment lock is not closed")
    if document["schema_version"] != "exp-local-003-environment-lock/v1":
        raise MaterializationError("environment lock schema mismatch")
    if document["card_sha256"] != CARD_SHA256:
        raise MaterializationError("environment lock card mismatch")
    expected_platform = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
    }
    if document["platform"] != expected_platform:
        raise MaterializationError("formal platform differs from C0 environment lock")

    julia = document["julia"]
    if not isinstance(julia, dict):
        raise MaterializationError("Julia environment record is malformed")
    runtime_path_value = julia.get("runtime_executable")
    if not isinstance(runtime_path_value, str):
        raise MaterializationError("locked Julia runtime path is malformed")
    runtime_path = Path(runtime_path_value)
    if not runtime_path.is_file():
        raise MaterializationError("locked Julia runtime is unavailable")
    formal_julia_environment = _formal_julia_environment(runtime_path)
    completed, _ = _run_accounted_text(
        [
            str(runtime_path),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            "-e",
            'print(VERSION, "\\n", joinpath(Sys.BINDIR, "julia.exe"), "\\n", Threads.nthreads(), "\\n", Sys.CPU_NAME)',
        ],
        env=formal_julia_environment,
        cwd=REPOSITORY_ROOT,
        validation_child=True,
    )
    lines = completed.stdout.splitlines()
    if completed.returncode != 0 or len(lines) != 4:
        raise MaterializationError("cannot identify locked Julia runtime")
    observed_runtime_path = Path(lines[1])
    if observed_runtime_path.resolve() != runtime_path.resolve():
        raise MaterializationError("Julia reported a different locked runtime")
    runtime_tree_contract = julia.get("runtime_tree")
    depot_tree_contract = julia.get("depot_tree")
    if not isinstance(runtime_tree_contract, dict) or not isinstance(
        depot_tree_contract, dict
    ):
        raise MaterializationError("Julia environment tree contracts are missing")
    runtime_root = runtime_path.parent.parent
    if runtime_tree_contract.get("root") != str(runtime_root):
        raise MaterializationError("Julia runtime tree root drift")
    if depot_tree_contract.get("root") != str(FORMAL_JULIA_DEPOT_PATH):
        raise MaterializationError("Julia depot tree root drift")
    if (
        runtime_tree_contract.get("included") != ["."]
        or runtime_tree_contract.get("excluded_parts") != []
        or runtime_tree_contract.get("excluded_suffixes") != []
        or depot_tree_contract.get("included") != ["."]
        or depot_tree_contract.get("excluded_parts")
        != ["compiled", "formal-tmp", "logs"]
        or depot_tree_contract.get("excluded_suffixes") != []
    ):
        raise MaterializationError("Julia environment tree scope is not closed")
    observed_julia = {
        "version": lines[0],
        "runtime_executable": str(runtime_path),
        "runtime_sha256": _sha256_path(runtime_path),
        "project_sha256": _sha256_path(REPOSITORY_ROOT / "julia" / "Project.toml"),
        "manifest_sha256": _sha256_path(REPOSITORY_ROOT / "julia" / "Manifest.toml"),
        "threads": int(lines[2]),
        "cpu_name": lines[3],
        "runtime_tree": _environment_tree_record(
            runtime_root,
            included=tuple(runtime_tree_contract["included"]),
            excluded_parts=frozenset(runtime_tree_contract["excluded_parts"]),
            excluded_suffixes=frozenset(runtime_tree_contract["excluded_suffixes"]),
            require_sandbox_safe=True,
        ),
        "depot_tree": _environment_tree_record(
            FORMAL_JULIA_DEPOT_PATH,
            included=tuple(depot_tree_contract["included"]),
            excluded_parts=frozenset(depot_tree_contract["excluded_parts"]),
            excluded_suffixes=frozenset(depot_tree_contract["excluded_suffixes"]),
            require_sandbox_safe=True,
        ),
    }
    if julia != observed_julia:
        raise MaterializationError(
            "Julia runtime/project differs from C0 environment lock"
        )
    options_completed, _ = _run_accounted_text(
        [
            str(runtime_path),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            f"--project={REPOSITORY_ROOT / 'julia'}",
            "-e",
            (
                "using GeoTargetCore; o=LocalSolveOptions(); "
                "for n in fieldnames(typeof(o)); v=getfield(o,n); "
                'println(n, "=", v isa Float64 ? '
                'string("0x",string(reinterpret(UInt64,v);base=16,pad=16)) : string(v)); end'
            ),
        ],
        env=formal_julia_environment,
        cwd=REPOSITORY_ROOT,
        validation_child=True,
    )
    observed_options: dict[str, str] = {}
    for line in options_completed.stdout.splitlines():
        name, separator, value = line.partition("=")
        if not separator or name in observed_options:
            raise MaterializationError("LocalSolveOptions runtime capture is malformed")
        observed_options[name] = value
    options_contract = _load_object(LOCAL_OPTIONS_PATH)
    expected_options = {
        "max_iterations": str(options_contract["constructor"]["max_iterations"]),
        "max_evaluations": str(options_contract["constructor"]["max_evaluations"]),
        **options_contract["binary64_bits"],
    }
    if options_completed.returncode != 0 or observed_options != expected_options:
        raise MaterializationError("runtime LocalSolveOptions differs from C0 contract")
    _verify_numeric_runtime(runtime_path, formal_julia_environment)

    python_record = document["python"]
    if (
        not isinstance(python_record, dict)
        or not isinstance(python_record.get("environment_tree"), dict)
        or not isinstance(python_record.get("base_runtime_tree"), dict)
    ):
        raise MaterializationError("Python environment tree contract is missing")
    python_tree_contract = python_record["environment_tree"]
    base_tree_contract = python_record["base_runtime_tree"]
    python_environment_root = _fixed_python_environment_root()
    if python_tree_contract.get("root") != str(python_environment_root):
        raise MaterializationError("Python environment tree root drift")
    if base_tree_contract.get("root") != str(Path(sys.base_prefix)):
        raise MaterializationError("Python base runtime tree root drift")
    expected_base_included = list(_python_base_runtime_included(Path(sys.base_prefix)))
    if (
        python_tree_contract.get("included") != ["."]
        or python_tree_contract.get("excluded_parts") != []
        or python_tree_contract.get("excluded_suffixes") != []
        or base_tree_contract.get("included") != expected_base_included
        or base_tree_contract.get("excluded_parts") != ["site-packages"]
        or base_tree_contract.get("excluded_suffixes") != []
    ):
        raise MaterializationError("Python environment tree scope is not closed")
    observed_python = {
        "version": platform.python_version(),
        "runtime_executable": str(Path(sys.executable)),
        "runtime_sha256": _sha256_path(Path(sys.executable)),
        "pyproject_sha256": _sha256_path(REPOSITORY_ROOT / "python" / "pyproject.toml"),
        "uv_lock_sha256": _sha256_path(REPOSITORY_ROOT / "python" / "uv.lock"),
        "environment_tree": _environment_tree_record(
            python_environment_root,
            included=tuple(python_tree_contract["included"]),
            excluded_parts=frozenset(python_tree_contract["excluded_parts"]),
            excluded_suffixes=frozenset(python_tree_contract["excluded_suffixes"]),
        ),
        "base_runtime_tree": _environment_tree_record(
            Path(sys.base_prefix),
            included=tuple(base_tree_contract["included"]),
            excluded_parts=frozenset(base_tree_contract["excluded_parts"]),
            excluded_suffixes=frozenset(base_tree_contract["excluded_suffixes"]),
        ),
    }
    if python_record != observed_python:
        raise MaterializationError(
            "Python runtime/project differs from C0 environment lock"
        )

    tools_contract = document.get("tools")
    if not isinstance(tools_contract, dict):
        raise MaterializationError("locked tool record is malformed")
    uv_value = tools_contract.get("uv_executable")
    git_value = tools_contract.get("git_executable")
    if not isinstance(uv_value, str) or not isinstance(git_value, str):
        raise MaterializationError("locked tool paths are malformed")
    uv_path = Path(uv_value)
    git_path = Path(git_value)
    if (
        not uv_path.is_file()
        or not git_path.is_file()
        or _sha256_path(uv_path) != tools_contract.get("uv_sha256")
        or _sha256_path(git_path) != tools_contract.get("git_sha256")
    ):
        raise MaterializationError("locked uv/git executables are unavailable")
    uv_completed, _ = _run_accounted_text(
        [str(uv_path), "--version"],
        cwd=REPOSITORY_ROOT,
        env=dict(os.environ),
        validation_child=True,
    )
    git_completed, _ = _run_accounted_text(
        [str(git_path), "--version"],
        cwd=REPOSITORY_ROOT,
        env=_closed_git_environment(),
        validation_child=True,
    )
    if uv_completed.returncode != 0 or git_completed.returncode != 0:
        raise MaterializationError("locked uv/git version capture failed")
    uv_version = uv_completed.stdout.strip()
    git_version = git_completed.stdout.strip()
    observed_tools = {
        "uv_version": uv_version,
        "uv_executable": str(uv_path),
        "uv_sha256": _sha256_path(uv_path),
        "git_version": git_version,
        "git_executable": str(git_path),
        "git_sha256": _sha256_path(git_path),
    }
    if tools_contract != observed_tools:
        raise MaterializationError("uv/git tools differ from C0 environment lock")
    for root in FORMAL_OUTCOME_NAMESPACE_ROOTS:
        try:
            metadata = root.lstat()
        except OSError as error:
            raise MaterializationError(
                f"formal outcome namespace is unavailable: {root}: {error}"
            ) from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise MaterializationError(
                f"formal outcome namespace is not a direct directory: {root}"
            )
        for ancestor in root.parents:
            try:
                ancestor_metadata = ancestor.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(ancestor_metadata.st_mode) or getattr(
                ancestor_metadata, "st_file_attributes", 0
            ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise MaterializationError(
                    f"formal outcome namespace traverses a reparse point: {ancestor}"
                )
    if document["execution"] != {
        "julia_num_threads": 1,
        "openblas_num_threads": 1,
        "omp_num_threads": 1,
        "mkl_num_threads": 1,
        "julia_depot_path": str(FORMAL_JULIA_DEPOT_PATH),
        "julia_environment": formal_julia_environment,
        "julia_compiled_modules": False,
        "julia_pkgimages": False,
        "python": _python_execution_record(),
        "float_mode": "IEEE-754 binary64 roundTiesToEven with Base.fma",
        "formal_outcome_namespace_roots": [
            str(path) for path in FORMAL_OUTCOME_NAMESPACE_ROOTS
        ],
    }:
        raise MaterializationError("formal execution settings differ from C0 lock")
    if document["numeric_fixture_sha256"] != _sha256_path(NUMERIC_DOMAIN_PATH):
        raise MaterializationError("numeric/FMA fixture hash differs from C0 lock")
    _assert_locked_julia_trees_unchanged()


def _run_git(*arguments: str) -> str:
    completed, _ = _run_accounted_text(
        [*_git_command_prefix(), *arguments],
        cwd=REPOSITORY_ROOT,
        env=_closed_git_environment(),
        validation_child=True,
    )
    if completed.returncode != 0:
        raise MaterializationError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _reject_source_bytecode() -> None:
    for source_tree in (SOURCE_ROOT, REPOSITORY_ROOT / "python" / "src"):
        if any(
            path.is_file()
            and (path.suffix in {".pyc", ".pyo"} or "__pycache__" in path.parts)
            for path in source_tree.rglob("*")
        ):
            raise MaterializationError(
                f"formal source tree contains executable bytecode cache: {source_tree}"
            )


def _import_frozen(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise MaterializationError(f"cannot import frozen source {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _verify_clean_lock_head(
    lock: dict[str, Any], *, claim_already_created: bool = False
) -> str:
    if claim_already_created:
        if not ATTEMPT_PATH.is_file():
            raise MaterializationError("C1 launcher claim is missing")
        expected_status = f"?? {ATTEMPT_PATH.relative_to(REPOSITORY_ROOT).as_posix()}"
        if (
            _run_git("status", "--porcelain=v1", "--untracked-files=all")
            != expected_status
        ):
            raise MaterializationError(
                "after C1 claim, the claim must be the only worktree change"
            )
    else:
        if ATTEMPT_PATH.exists():
            raise MaterializationError("C1 was already claimed; one-shot rerun refused")
        if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
            raise MaterializationError(
                "one-shot materialization requires a completely clean worktree"
            )
    if _run_git("branch", "--show-current") != "main":
        raise MaterializationError("formal C1 materialization requires main")
    if VAULT_ANCHOR_PATH.exists() or PRIVATE_VAULT_ANCHOR_PATH.exists():
        raise MaterializationError("C1 vault authority was already anchored")
    if (
        CANDIDATE_OUTPUT_PATH.exists()
        or VAULT_OUTPUT_PATH.exists()
        or PRIVATE_VAULT_OUTPUT_PATH.exists()
    ):
        raise MaterializationError(
            "development inputs already exist; one-shot rerun refused"
        )
    head = _run_git("rev-parse", "HEAD")
    lock_commit = _run_git(
        "log", "-1", "--format=%H", "--", str(LOCK_PATH.relative_to(REPOSITORY_ROOT))
    )
    if not lock_commit or lock_commit != head:
        raise MaterializationError(
            "HEAD must be exactly the commit that introduced the C0 lock"
        )
    if lock.get("status") != "frozen-before-one-shot-development-materialization":
        raise MaterializationError("preimplementation lock is not frozen for C1")
    if lock.get("card_sha256") != CARD_SHA256 or _sha256_path(CARD_PATH) != CARD_SHA256:
        raise MaterializationError("EXP-LOCAL-003 card identity drift")
    return head


def _verify_file_lock(lock: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "experiment_id",
        "status",
        "card_sha256",
        "c0_source_commit",
        "c0_source_tree",
        "files",
        "experiment_source_files",
        "forbidden_mechanism_paths",
        "environment_lock_sha256",
        "local_options_sha256",
    }
    if set(lock) != expected_keys:
        raise MaterializationError("preimplementation lock is not a closed C0 record")
    if lock.get("schema_version") != "exp-local-003-preimplementation-lock/v1":
        raise MaterializationError("preimplementation lock schema mismatch")
    if lock.get("experiment_id") != "EXP-LOCAL-003":
        raise MaterializationError("preimplementation lock experiment mismatch")
    lock_commit = _run_git(
        "log", "-1", "--format=%H", "--", str(LOCK_PATH.relative_to(REPOSITORY_ROOT))
    )
    source_parent = _run_git("rev-parse", f"{lock_commit}^")
    if lock.get("c0_source_commit") != source_parent:
        raise MaterializationError("preimplementation lock C0 source parent mismatch")
    if lock.get("c0_source_tree") != _run_git("rev-parse", f"{source_parent}^{{tree}}"):
        raise MaterializationError("preimplementation lock C0 source tree mismatch")
    declared = lock.get("files")
    if not isinstance(declared, dict) or not declared:
        raise MaterializationError("preimplementation lock has no file hashes")
    required_files = _required_c0_files()
    if set(declared) != required_files:
        raise MaterializationError(
            "preimplementation file set drift: "
            f"extra={sorted(set(declared) - required_files)}, "
            f"missing={sorted(required_files - set(declared))}"
        )
    for relative, expected in declared.items():
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or LOWER_HEX_SHA256.fullmatch(expected) is None
        ):
            raise MaterializationError(
                "preimplementation file map is not string-to-string"
            )
        path = REPOSITORY_ROOT / relative
        if not path.is_file() or _sha256_path(path) != expected:
            raise MaterializationError(f"preimplementation hash drift: {relative}")

    declared_sources = lock.get("experiment_source_files")
    if not isinstance(declared_sources, list) or not declared_sources:
        raise MaterializationError("experiment source allowlist is missing")
    expected_sources = {str(value) for value in declared_sources}
    actual_sources = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    if actual_sources != expected_sources:
        raise MaterializationError(
            "experiment source allowlist drift: "
            f"extra={sorted(actual_sources - expected_sources)}, "
            f"missing={sorted(expected_sources - actual_sources)}"
        )
    _reject_source_bytecode()
    if not expected_sources <= set(declared):
        raise MaterializationError("experiment source files are not all hash-bound")
    forbidden_paths = lock.get("forbidden_mechanism_paths")
    if forbidden_paths != list(FORBIDDEN_MECHANISM_PATHS):
        raise MaterializationError("mechanism-absence list differs from C0 contract")
    for relative in forbidden_paths:
        if (REPOSITORY_ROOT / str(relative)).exists():
            raise MaterializationError(
                f"candidate mechanism exists before C1: {relative}"
            )
    if lock.get("environment_lock_sha256") != _sha256_path(ENVIRONMENT_LOCK_PATH):
        raise MaterializationError("environment lock hash mismatch")
    if lock.get("local_options_sha256") != _local_options_sha256():
        raise MaterializationError("local options digest mismatch")
    verify_frozen_environment()


def _walk_candidate_boundary(value: Any, path: str = "candidate") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_CANDIDATE_KEYS:
                raise MaterializationError(f"forbidden candidate key at {path}.{key}")
            _walk_candidate_boundary(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_candidate_boundary(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_CANDIDATE_MARKERS):
            raise MaterializationError(f"family/representation marker leaked at {path}")


def _finite_number(value: Any, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaterializationError(
            f"{path} must be a JSON number, not {type(value).__name__}"
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise MaterializationError(f"{path} must be finite")
    return numeric


def _validate_points(
    points: Any,
    *,
    count: int,
    lower: list[float],
    upper: list[float],
    path: str,
) -> None:
    if not isinstance(points, list) or len(points) != count:
        raise MaterializationError(f"{path} must contain exactly {count} points")
    for row_index, row in enumerate(points):
        if not isinstance(row, list) or len(row) != len(lower):
            raise MaterializationError(f"{path}[{row_index}] has wrong dimension")
        for column, value in enumerate(row):
            numeric = _finite_number(value, path=f"{path}[{row_index}][{column}]")
            if not lower[column] <= numeric <= upper[column]:
                raise MaterializationError(
                    f"{path}[{row_index}] is outside public bounds"
                )


def _validate_candidate(candidate: dict[str, Any], *, stage: str) -> list[str]:
    expected_schema = {
        "development": "exp-local-003-candidate-inputs/v1",
        "locked": "exp-local-003-locked-candidate-inputs/v1",
    }[stage]
    expected_count = 64 if stage == "development" else 96
    if candidate.get("schema_version") != expected_schema:
        raise MaterializationError("wrong candidate projection schema")
    if candidate.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("candidate projection card mismatch")
    cases = candidate.get("cases")
    if not isinstance(cases, list) or len(cases) != expected_count:
        raise MaterializationError(
            f"candidate projection must contain {expected_count} cases"
        )
    keys: list[str] = []
    _walk_candidate_boundary(candidate)
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != CANDIDATE_CASE_KEYS:
            raise MaterializationError(f"candidate case {index} has unexpected fields")
        key = case["opaque_case_key"]
        if not isinstance(key, str) or LOWER_HEX_SHA256.fullmatch(key) is None:
            raise MaterializationError(f"candidate case {index} has invalid opaque key")
        keys.append(key)
        problem = case["problem_document"]
        validate_document(
            problem, schema="problem", schemas=REPOSITORY_ROOT / "schemas"
        )
        if case["problem_sha256"] != canonical_hash(problem):
            raise MaterializationError(f"candidate case {index} problem hash mismatch")
        if not isinstance(problem, dict):
            raise MaterializationError(
                f"candidate case {index} problem is not an object"
            )
        variables = problem.get("variables")
        if not isinstance(variables, list) or not variables:
            raise MaterializationError(f"candidate case {index} has no variables")
        lower: list[float] = []
        upper: list[float] = []
        for variable_index, variable in enumerate(variables):
            if not isinstance(variable, dict):
                raise MaterializationError("problem variable is not an object")
            lo = _finite_number(
                variable.get("lower"),
                path=f"candidate[{index}].lower[{variable_index}]",
            )
            hi = _finite_number(
                variable.get("upper"),
                path=f"candidate[{index}].upper[{variable_index}]",
            )
            if not lo < hi:
                raise MaterializationError("candidate variable bounds are not strict")
            lower.append(lo)
            upper.append(hi)
        _validate_points(
            case["calibration_points"],
            count=64,
            lower=lower,
            upper=upper,
            path=f"candidate[{index}].calibration_points",
        )
        _validate_points(
            case["starts"],
            count=32,
            lower=lower,
            upper=upper,
            path=f"candidate[{index}].starts",
        )
        if case["calibration_points_sha256"] != canonical_hash(
            case["calibration_points"]
        ):
            raise MaterializationError(
                f"candidate case {index} calibration hash mismatch"
            )
        if case["starts_sha256"] != canonical_hash(case["starts"]):
            raise MaterializationError(f"candidate case {index} start hash mismatch")
        budget = case["budget"]
        expected_budget = {
            "local_max_iterations": 250,
            "local_max_evaluations": 2000,
            "launch_prefixes": [8, 16, 32],
        }
        if budget != expected_budget:
            raise MaterializationError(f"candidate case {index} budget drift")
        canonical_bytes(case["public_numeric_metadata"])
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MaterializationError("candidate opaque keys must be unique and sorted")
    canonical_bytes(candidate)
    return keys


def _validate_assessor(assessor: dict[str, Any], *, stage: str) -> list[str]:
    expected_schema = {
        "development": "exp-local-003-generator-assessor-projection/v1",
        "locked": "exp-local-003-locked-generator-assessor-projection/v1",
    }[stage]
    expected_count = 64 if stage == "development" else 96
    groups = (0, 1) if stage == "development" else (2, 3, 4, 5)
    representations = (
        (*PRIMARY_REPRESENTATIONS, SAFETY_REPRESENTATION)
        if stage == "development"
        else PRIMARY_REPRESENTATIONS
    )
    if assessor.get("schema_version") != expected_schema:
        raise MaterializationError("wrong assessor projection schema")
    if assessor.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("assessor projection card mismatch")
    cases = assessor.get("cases")
    if not isinstance(cases, list) or len(cases) != expected_count:
        raise MaterializationError(
            f"assessor projection must contain {expected_count} cases"
        )
    keys: list[str] = []
    allocation: Counter[tuple[str, int, str]] = Counter()
    primary_count = 0
    safety_count = 0
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise MaterializationError(f"assessor case {index} is not an object")
        key = case.get("opaque_case_key")
        family = case.get("family_id")
        family_ordinal = case.get("family_ordinal")
        group = case.get("latent_group")
        representation = case.get("representation")
        invariant = case.get("expected_invariant")
        if not isinstance(key, str) or LOWER_HEX_SHA256.fullmatch(key) is None:
            raise MaterializationError(f"assessor case {index} has invalid key")
        if family not in FAMILY_IDS or family_ordinal != FAMILY_IDS.index(family):
            raise MaterializationError(f"assessor case {index} family mapping drift")
        if isinstance(group, bool) or group not in groups:
            raise MaterializationError(f"assessor case {index} latent group drift")
        if representation in PRIMARY_REPRESENTATIONS:
            if invariant is not True:
                raise MaterializationError("primary representation must be invariant")
            primary_count += 1
        elif representation == SAFETY_REPRESENTATION:
            if invariant is not False:
                raise MaterializationError(
                    "Safety16 must have expected_invariant=false"
                )
            safety_count += 1
        else:
            raise MaterializationError(f"assessor case {index} representation drift")
        if not isinstance(case.get("gold"), dict) or not isinstance(
            case.get("tolerances"), dict
        ):
            raise MaterializationError(f"assessor case {index} lacks Gold/tolerances")
        keys.append(key)
        allocation[(family, group, representation)] += 1
    expected_allocation = {
        (family, group, representation)
        for family in FAMILY_IDS
        for group in groups
        for representation in representations
    }
    if set(allocation) != expected_allocation or any(
        value != 1 for value in allocation.values()
    ):
        raise MaterializationError("assessor 8x2x4 allocation drift")
    expected_primary = 48 if stage == "development" else 96
    expected_safety = 16 if stage == "development" else 0
    if primary_count != expected_primary or safety_count != expected_safety:
        raise MaterializationError("assessor primary/Safety counts drift")
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MaterializationError("assessor opaque keys must be unique and sorted")
    canonical_bytes(assessor)
    return keys


def _validate_private(
    private: dict[str, Any], master_secret: bytes, *, stage: str
) -> list[str]:
    expected_schema = {
        "development": "exp-local-003-generator-private/v1",
        "locked": "exp-local-003-locked-generator-private/v1",
    }[stage]
    expected_mode = (
        "formal-c1-caller-secret"
        if stage == "development"
        else "formal-locked-caller-secret"
    )
    expected_groups = 16 if stage == "development" else 32
    expected_cases = 64 if stage == "development" else 96
    allowed_groups = (0, 1) if stage == "development" else (2, 3, 4, 5)
    if private.get("schema_version") != expected_schema:
        raise MaterializationError("wrong generator-private schema")
    if private.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("generator-private card mismatch")
    if private.get("master_secret_hex") != master_secret.hex():
        raise MaterializationError("generator-private master secret mismatch")
    entropy = private.get("entropy_contract")
    if not isinstance(entropy, dict) or entropy.get("mode") != expected_mode:
        raise MaterializationError("generator-private entropy mode differs from stage")
    groups = private.get("groups")
    if not isinstance(groups, list) or len(groups) != expected_groups:
        raise MaterializationError(
            f"generator-private projection must contain {expected_groups} groups"
        )
    group_keys: set[str] = set()
    allocation: set[tuple[str, int]] = set()
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise MaterializationError(f"generator-private group {index} is malformed")
        key = group.get("latent_group_key")
        family = group.get("family_id")
        ordinal = group.get("family_ordinal")
        latent = group.get("latent_group")
        if not isinstance(key, str) or LOWER_HEX_SHA256.fullmatch(key) is None:
            raise MaterializationError("generator-private latent group key is invalid")
        if family not in FAMILY_IDS or ordinal != FAMILY_IDS.index(family):
            raise MaterializationError("generator-private family mapping drift")
        if latent not in allowed_groups:
            raise MaterializationError("generator-private stage group drift")
        if key in group_keys or (family, latent) in allocation:
            raise MaterializationError("generator-private latent group is duplicated")
        group_keys.add(key)
        allocation.add((family, latent))
        for field in (
            "calibration_key_hex",
            "start_key_hex",
            "parameter_key_hex",
            "gold_key_hex",
        ):
            value = group.get(field)
            if not isinstance(value, str) or LOWER_HEX_SHA256.fullmatch(value) is None:
                raise MaterializationError(f"generator-private group lacks {field}")
    cases = private.get("cases")
    if not isinstance(cases, list) or len(cases) != expected_cases:
        raise MaterializationError(
            f"generator-private projection must contain {expected_cases} cases"
        )
    keys: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise MaterializationError(
                f"generator-private case {index} is not an object"
            )
        key = case.get("opaque_case_key")
        latent_group_key = case.get("latent_group_key")
        if not isinstance(key, str) or LOWER_HEX_SHA256.fullmatch(key) is None:
            raise MaterializationError(
                f"generator-private case {index} has invalid join key"
            )
        if latent_group_key not in group_keys:
            raise MaterializationError(
                f"generator-private case {index} has unknown latent group key"
            )
        keys.append(key)
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MaterializationError(
            "generator-private opaque keys must be unique and sorted"
        )
    canonical_bytes(private)
    return keys


def validate_documents(
    documents: dict[str, dict[str, Any]], *, master_secret: bytes, stage: str
) -> None:
    if set(documents) != {"candidate", "assessor", "generator_private"}:
        raise MaterializationError("generator returned the wrong projection set")
    for projection, schema_name in (
        ("candidate", "candidate-inputs.schema.json"),
        ("assessor", "generator-assessor-projection.schema.json"),
        ("generator_private", "generator-private.schema.json"),
    ):
        _validate_schema(documents[projection], schema_name)
    candidate_keys = _validate_candidate(documents["candidate"], stage=stage)
    assessor_keys = _validate_assessor(documents["assessor"], stage=stage)
    private_keys = _validate_private(
        documents["generator_private"], master_secret, stage=stage
    )
    if candidate_keys != assessor_keys or candidate_keys != private_keys:
        raise MaterializationError("candidate/assessor/private joins differ")


def _capture_calibration_truth(
    candidate: dict[str, Any], assessor_projection: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """Run the frozen real Julia compiler/C0 evaluator in an ephemeral directory."""

    with tempfile.TemporaryDirectory(prefix="local3-c0-capture-") as temporary:
        root = Path(temporary)
        candidate_path = root / "candidate.json"
        assessor_path = root / "assessor-projection.json"
        candidate_path.write_bytes(canonical_bytes(candidate))
        assessor_path.write_bytes(canonical_bytes(assessor_projection))
        formal_capture = ENVIRONMENT_LOCK_PATH.is_file()
        if formal_capture:
            environment_lock = _load_object(ENVIRONMENT_LOCK_PATH)
            runtime = Path(environment_lock["julia"]["runtime_executable"])
            environment = _formal_julia_environment(runtime)
            command = [
                str(runtime),
                "--startup-file=no",
                "--history-file=no",
                "--compiled-modules=no",
                "--pkgimages=no",
                f"--project={REPOSITORY_ROOT / 'julia'}",
                str(SOURCE_ROOT / "capture_calibration_truth.jl"),
                str(candidate_path),
                str(assessor_path),
            ]
        else:
            # C0 tests run before the machine-specific formal lock exists.
            environment = os.environ.copy()
            environment.update(
                {
                    "JULIA_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                }
            )
            command = [
                _julia_executable(),
                "+1.12.6",
                "--startup-file=no",
                "--history-file=no",
                f"--project={REPOSITORY_ROOT / 'julia'}",
                str(SOURCE_ROOT / "capture_calibration_truth.jl"),
                str(candidate_path),
                str(assessor_path),
            ]
        completed, child_cpu_nanoseconds = _run_accounted_bytes(
            command, cwd=REPOSITORY_ROOT, env=environment
        )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MaterializationError(
            f"Julia calibration capture failed with {completed.returncode}: {stderr}"
        )
    if formal_capture and child_cpu_nanoseconds <= 0:
        raise MaterializationError("formal Julia capture reported no process CPU")
    if formal_capture:
        _assert_locked_julia_trees_unchanged()
    try:
        capture = json.loads(
            completed.stdout.decode("utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"nonstandard JSON constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise MaterializationError(
            "Julia calibration capture emitted invalid JSON"
        ) from exc
    if not isinstance(capture, dict):
        raise MaterializationError("Julia calibration capture is not an object")
    if canonical_bytes(capture) != completed.stdout:
        raise MaterializationError(
            "Julia calibration capture is not exact canonical JSON"
        )
    _validate_schema(capture, "calibration-truth.schema.json")
    if capture.get("candidate_projection_sha256") != canonical_hash(candidate):
        raise MaterializationError(
            "calibration capture candidate projection hash mismatch"
        )
    if capture.get("assessor_projection_sha256") != canonical_hash(assessor_projection):
        raise MaterializationError(
            "calibration capture assessor projection hash mismatch"
        )
    return capture, child_cpu_nanoseconds


def _scale_from_base(truth_case: dict[str, Any]) -> list[int] | None:
    if truth_case["representation"] == SAFETY_REPRESENTATION:
        return None
    matrix = truth_case["inverse_mapping"]["semantic_z_from_base"]
    if not isinstance(matrix, list) or not matrix:
        raise MaterializationError("primary semantic residual map is empty")
    permutation: list[int] = []
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != len(matrix):
            raise MaterializationError("primary semantic residual map is not square")
        nonzero = [
            column
            for column, raw in enumerate(row)
            if _finite_number(raw, path=f"semantic_map[{row_index}]") != 0.0
        ]
        if len(nonzero) != 1:
            raise MaterializationError("primary semantic residual map is not monomial")
        coefficient = float(row[nonzero[0]])
        if abs(coefficient) != 1.0:
            raise MaterializationError(
                "primary semantic residual map is not signed-unit"
            )
        permutation.append(nonzero[0])
    if sorted(permutation) != list(range(len(matrix))):
        raise MaterializationError("primary semantic residual map is not a permutation")
    return permutation


def _target_center(target: dict[str, Any], *, context: str) -> tuple[float, float]:
    lower = _finite_number(target.get("lower"), path=f"{context}.lower")
    upper = _finite_number(target.get("upper"), path=f"{context}.upper")
    if lower > upper:
        raise MaterializationError(f"{context} target interval is reversed")
    if lower == upper:
        return lower, 0.0
    from_lower = math.nextafter(lower, math.inf)
    from_upper = math.nextafter(upper, -math.inf)
    if from_lower != from_upper:
        raise MaterializationError(
            f"{context} outward target interval does not identify one binary64 center"
        )
    center = from_lower
    return center, max(center - lower, upper - center)


def _gold_solutions(truth_case: dict[str, Any]) -> list[dict[str, Any]]:
    gold = truth_case["gold"]
    configurations = gold["configurations"]
    targets = gold["targets"]
    tolerance = truth_case["tolerances"]
    configuration_tolerance = _finite_number(
        tolerance["configuration_absolute"], path="configuration tolerance"
    )
    target_tolerance = _finite_number(
        tolerance["target_absolute"], path="target tolerance"
    )
    if configuration_tolerance <= 0.0 or target_tolerance <= 0.0:
        raise MaterializationError("Gold tolerances must be strictly positive")
    by_configuration: dict[int, tuple[float, float]] = {}
    for target_index, target in enumerate(targets):
        center, radius = _target_center(target, context=f"targets[{target_index}]")
        indexes = target["configuration_indexes"]
        if not isinstance(indexes, list) or not indexes:
            raise MaterializationError("Gold target has no configuration indexes")
        for raw_index in indexes:
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise MaterializationError("Gold configuration index is not an integer")
            if raw_index in by_configuration:
                raise MaterializationError(
                    "Gold configuration belongs to multiple targets"
                )
            by_configuration[raw_index] = (center, radius)
    if set(by_configuration) != set(range(len(configurations))):
        raise MaterializationError("Gold target/configuration relation is incomplete")

    result: list[dict[str, Any]] = []
    for index, configuration in enumerate(configurations):
        if not isinstance(configuration, list) or not configuration:
            raise MaterializationError("Gold configuration is empty or malformed")
        center, radius = by_configuration[index]
        combined_target_tolerance = target_tolerance + radius
        if radius > 0.0:
            combined_target_tolerance = math.nextafter(
                combined_target_tolerance, math.inf
            )
        result.append(
            {
                "configuration_hex": [
                    _finite_hex(
                        _finite_number(value, path=f"Gold[{index}][{coordinate}]"),
                        context=f"Gold[{index}][{coordinate}]",
                    )
                    for coordinate, value in enumerate(configuration)
                ],
                "target_hex": _finite_hex(center, context=f"Gold target {index}"),
                "configuration_abs_tolerance_hex": _finite_hex(
                    configuration_tolerance, context="configuration tolerance"
                ),
                "target_abs_tolerance_hex": _finite_hex(
                    combined_target_tolerance, context="target tolerance"
                ),
                "branch_label": None,
            }
        )
    return result


def _verify_compiled_numeric_metadata(
    candidate_case: dict[str, Any], capture_case: dict[str, Any]
) -> None:
    public = candidate_case["public_numeric_metadata"]
    compiled = capture_case["compiled_numeric_metadata"]
    variables = compiled["variables"]
    if (
        len(variables) != public["dimension"]
        or len(public["bounds"]) != public["dimension"]
        or len(public["origins"]) != public["dimension"]
        or len(public["variable_scales"]) != public["dimension"]
    ):
        raise MaterializationError("public/compiled variable metadata shape mismatch")
    for index, variable in enumerate(variables):
        if variable["variable_index"] != index:
            raise MaterializationError("compiled variable metadata order mismatch")
        expected = (
            public["bounds"][index][0],
            public["bounds"][index][1],
            public["origins"][index],
            public["variable_scales"][index],
        )
        observed = tuple(
            _float_from_bits(
                variable[field], context=f"compiled variable {index} {field}"
            )
            for field in ("lower_bits", "upper_bits", "origin_bits", "scale_bits")
        )
        if any(
            struct.pack(">d", float(left)) != struct.pack(">d", float(right))
            for left, right in zip(expected, observed, strict=True)
        ):
            raise MaterializationError("public variable metadata differs bit-for-bit")
        midpoint = _float_from_bits(
            variable["safe_midpoint_bits"], context="safe midpoint"
        )
        halfwidth = _float_from_bits(
            variable["safe_halfwidth_bits"], context="safe halfwidth"
        )
        if (
            not math.isfinite(midpoint)
            or not math.isfinite(halfwidth)
            or halfwidth <= 0.0
        ):
            raise MaterializationError("compiled safe midpoint/halfwidth is invalid")
    relation_bits = compiled["relation_semantic_scale_bits"]
    if (
        len(relation_bits) != public["relation_count"]
        or len(public["relation_scales"]) != public["relation_count"]
    ):
        raise MaterializationError("public/compiled relation metadata shape mismatch")
    for index, (expected, bits) in enumerate(
        zip(public["relation_scales"], relation_bits, strict=True)
    ):
        observed = _float_from_bits(bits, context=f"relation scale {index}")
        if struct.pack(">d", float(expected)) != struct.pack(">d", observed):
            raise MaterializationError("public relation scale differs bit-for-bit")


def _formal_calibration(
    capture_case: dict[str, Any], assessor_module: ModuleType
) -> dict[str, Any]:
    residual_count = capture_case["residual_count"]
    calibration = capture_case["calibration"]
    observations = capture_case["observations"]
    nearest = [
        _float_from_bits(value, context=f"nearest_rank[{index}]")
        for index, value in enumerate(calibration["r_bits"])
    ]
    scales = [
        _float_from_bits(value, context=f"model_scale[{index}]")
        for index, value in enumerate(calibration["a_bits"])
    ]
    if len(nearest) != residual_count or len(scales) != residual_count:
        raise MaterializationError("captured calibration vector length mismatch")
    if any(not math.isfinite(value) for value in nearest):
        fallback = "nonfinite-nearest-rank"
    elif any(value <= 0.0 for value in nearest):
        fallback = "nonpositive-nearest-rank"
    else:
        fallback = None
    captured_fallback = calibration["joint_fallback_reason"]
    expected_captured = {
        None: None,
        "insufficient_valid_vectors": "insufficient-valid-vectors",
        "nonpositive_or_nonfinite_nearest_rank": fallback,
    }[captured_fallback]
    if expected_captured == "insufficient-valid-vectors":
        fallback = expected_captured
    elif expected_captured != fallback:
        raise MaterializationError(
            "captured calibration fallback classification mismatch"
        )

    valid_count = calibration["valid_vector_count"]
    expected_rank_index = 0 if valid_count == 0 else (3 * valid_count + 3) // 4
    if calibration["nearest_rank_index"] != expected_rank_index:
        raise MaterializationError("captured nearest-rank index mismatch")
    valid_observations = 0
    nonfinite_q_count = 0
    costs: list[int] = []
    for observation_index, observation in enumerate(observations):
        cost = observation["evaluation_cost"]
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise MaterializationError("captured observation cost is invalid")
        costs.append(cost)
        z_bits = observation["z_bits"]
        if z_bits:
            if len(z_bits) != residual_count:
                raise MaterializationError(
                    "captured complete z vector has wrong length"
                )
            valid_observations += 1
            for component, (bits, scale) in enumerate(zip(z_bits, scales, strict=True)):
                z_value = _float_from_bits(
                    bits,
                    context=f"observation[{observation_index}].z[{component}]",
                )
                if not math.isfinite(z_value):
                    raise MaterializationError("captured valid z vector is nonfinite")
                try:
                    quotient = z_value / scale
                except OverflowError:
                    quotient = math.inf
                if not math.isfinite(quotient):
                    nonfinite_q_count += 1
    if valid_observations != valid_count:
        raise MaterializationError(
            "captured valid-vector count differs from observations"
        )
    if nonfinite_q_count != calibration["q_nonfinite_count"]:
        raise MaterializationError(
            "captured nonfinite-q count differs from observations"
        )

    clamp_reasons: list[dict[str, bool]] = []
    for reason in calibration["clamp_reasons"]:
        if reason in ("joint_fallback", "none"):
            clamp_reasons.append({"lower": False, "upper": False})
        elif reason == "below_0x1.0p-40":
            clamp_reasons.append({"lower": True, "upper": False})
        elif reason == "above_0x1.0p+40":
            clamp_reasons.append({"lower": False, "upper": True})
        else:
            raise MaterializationError("captured clamp reason is unsupported")
    nearest_hex = [
        _finite_hex(value, context=f"nearest_rank[{index}]")
        for index, value in enumerate(nearest)
    ]
    scale_hex = [
        _finite_hex(value, context=f"model_scale[{index}]")
        for index, value in enumerate(scales)
    ]
    scale_digest = assessor_module.model_scale_sha256(scale_hex)
    return {
        "observation_evaluation_costs": costs,
        "valid_vector_count": valid_count,
        "nearest_rank_hex": nearest_hex,
        "model_scale_hex": scale_hex,
        "model_scale_sha256": scale_digest,
        "joint_fallback_reason": fallback,
        "clamp_reasons": clamp_reasons,
        "nonfinite_q_count": nonfinite_q_count,
        "nonfinite_q_misclassification_count": 0,
    }


def _build_formal_assessor_truth(
    documents: dict[str, dict[str, Any]],
    capture: dict[str, Any],
    bootstrap: bytes,
    assessor_module: ModuleType,
    *,
    stage: str,
    group_index_map: dict[int, int],
    locked_decision: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = documents["candidate"]
    projection = documents["assessor"]
    private = documents["generator_private"]
    candidate_by_key = {case["opaque_case_key"]: case for case in candidate["cases"]}
    projection_by_key = {case["opaque_case_key"]: case for case in projection["cases"]}
    private_by_key = {case["opaque_case_key"]: case for case in private["cases"]}
    private_groups_by_key = {
        group["latent_group_key"]: group for group in private["groups"]
    }
    capture_by_key = {case["opaque_case_key"]: case for case in capture["cases"]}
    key_set = set(candidate_by_key)
    if (
        set(projection_by_key) != key_set
        or set(private_by_key) != key_set
        or set(capture_by_key) != key_set
    ):
        raise MaterializationError("formal truth inputs have different opaque key sets")

    group_keys: dict[tuple[str, int], str] = {}
    formal_cases: list[dict[str, Any]] = []
    for opaque_key in sorted(key_set):
        candidate_case = candidate_by_key[opaque_key]
        truth_case = projection_by_key[opaque_key]
        private_case = private_by_key[opaque_key]
        capture_case = capture_by_key[opaque_key]
        if capture_case["problem_sha256"] != candidate_case["problem_sha256"]:
            raise MaterializationError("calibration capture problem hash mismatch")
        if (
            capture_case["calibration_points_sha256"]
            != candidate_case["calibration_points_sha256"]
        ):
            raise MaterializationError("calibration capture point hash mismatch")
        if capture_case["starts_sha256"] != candidate_case["starts_sha256"]:
            raise MaterializationError("calibration capture start hash mismatch")
        private_group_key = private_case["latent_group_key"]
        if private_group_key not in private_groups_by_key:
            raise MaterializationError(
                "private case references an unknown latent group"
            )
        private_group = private_groups_by_key[private_group_key]
        if truth_case["representation"] != private_case["representation"]:
            raise MaterializationError("assessor/private representation mismatch")
        family_id = truth_case["family_id"]
        latent_group = truth_case["latent_group"]
        if latent_group not in group_index_map:
            raise MaterializationError(
                "generator group lacks a formal stage-local index"
            )
        if (
            family_id != private_group["family_id"]
            or truth_case["family_ordinal"] != private_group["family_ordinal"]
            or latent_group != private_group["latent_group"]
        ):
            raise MaterializationError(
                "assessor projection/private group identity mismatch"
            )
        if (
            capture_case["gold_audit"]["gold_identity_key"]
            != truth_case["gold"]["identity_key"]
        ):
            raise MaterializationError("Gold capture identity mismatch")
        group_identity = (family_id, latent_group)
        previous_group_key = group_keys.setdefault(group_identity, private_group_key)
        if previous_group_key != private_group_key:
            raise MaterializationError(
                "latent representations use different private keys"
            )
        public = candidate_case["public_numeric_metadata"]
        if (
            capture_case["variable_count"] != public["dimension"]
            or capture_case["residual_count"] != public["relation_count"]
        ):
            raise MaterializationError(
                "compiled dimensions differ from public metadata"
            )
        _verify_compiled_numeric_metadata(candidate_case, capture_case)
        formal_cases.append(
            {
                "opaque_case_key": opaque_key,
                "family_id": family_id,
                "family_ordinal": truth_case["family_ordinal"],
                "latent_group_index": group_index_map[latent_group],
                "latent_group_key": private_group_key,
                "representation": truth_case["representation"],
                "expected_invariant": truth_case["expected_invariant"],
                "scale_from_base": _scale_from_base(truth_case),
                "problem_sha256": _raw_prefixed_hash(
                    candidate_case["problem_sha256"], context="problem document"
                ),
                "calibration_points_sha256": _raw_prefixed_hash(
                    candidate_case["calibration_points_sha256"],
                    context="calibration points",
                ),
                "starts_sha256": _raw_prefixed_hash(
                    candidate_case["starts_sha256"], context="starts"
                ),
                "variable_count": capture_case["variable_count"],
                "residual_count": capture_case["residual_count"],
                "logical_evaluation_cost": capture_case["logical_evaluation_cost"],
                "gold_solutions": _gold_solutions(truth_case),
                "expected_calibration": _formal_calibration(
                    capture_case, assessor_module
                ),
            }
        )
    if stage == "development":
        if locked_decision is not None:
            raise MaterializationError(
                "development truth cannot bind a locked decision"
            )
        formal_locked_decision = None
    else:
        if not isinstance(locked_decision, dict):
            raise MaterializationError("locked truth requires a development decision")
        _validate_schema(locked_decision, "development-decision-record.schema.json")
        formal_locked_decision = {
            "candidate_id": locked_decision["selected_variant"],
            "development_path": locked_decision["selected_path"],
            "development_assessment_sha256": locked_decision[
                "development_assessment_sha256"
            ],
            "development_decision_record_sha256": _sha256_bytes(
                canonical_bytes(locked_decision)
            ),
        }
    formal = {
        "schema_version": assessor_module.ASSESSOR_TRUTH_SCHEMA,
        "stage": stage,
        "candidate_input_sha256": _raw_content_hash(
            candidate, context="candidate input"
        ),
        "bootstrap_sha256": _sha256_bytes(bootstrap),
        "local_options_sha256": _local_options_sha256(),
        "locked_decision": formal_locked_decision,
        "cases": formal_cases,
    }
    _validate_schema(formal, "assessor-truth.schema.json")
    try:
        assessor_module.validate_assessor_truth(formal)
    except Exception as exc:
        raise MaterializationError(f"formal assessor truth is invalid: {exc}") from exc
    canonical_bytes(formal)
    return formal


def _gzip_document(path: Path, document: Any) -> dict[str, Any]:
    raw = canonical_bytes(document)
    compressed = _deterministic_gzip_bytes(raw)
    _write_bytes_durable(path, compressed)
    return {
        "path": path.name,
        "jcs_sha256": _sha256_bytes(raw),
        "gzip_sha256": _sha256_bytes(compressed),
        "jcs_bytes": len(raw),
        "gzip_bytes": len(compressed),
        "compression": "gzip-level-9-mtime-0",
    }


def _deterministic_gzip_bytes(payload: bytes) -> bytes:
    """Produce the cross-platform gzip member required by authority replay."""

    compressed = bytearray(gzip.compress(payload, compresslevel=9, mtime=0))
    if (
        len(compressed) < 18
        or compressed[:4] != b"\x1f\x8b\x08\x00"
        or compressed[4:8] != b"\x00\x00\x00\x00"
        or compressed[8] != 2
    ):
        raise MaterializationError("runtime gzip codec differs from frozen format")
    # Python 3.11/3.12 expose zlib's platform OS byte when mtime=0. Normalize
    # it explicitly so publication and immutable-authority replay agree.
    compressed[9] = 255
    result = bytes(compressed)
    if gzip.decompress(result) != payload:
        raise MaterializationError("deterministic gzip round-trip failed")
    return result


def _write_bytes_durable(path: Path, payload: bytes) -> None:
    """Flush one staging file before its containing tree can be published."""

    durable_write(path, payload)


def _write_json(path: Path, document: Any) -> None:
    _write_bytes_durable(path, canonical_bytes(document))


def _exclusive_write_json(path: Path, document: Any) -> None:
    exclusive_write(path, canonical_bytes(document))


def _durable_directory_rename(source: Path, destination: Path) -> None:
    """Atomically publish one same-volume directory with write-through."""

    durable_rename_noreplace(source, destination)


def _claim_c1_attempt() -> None:
    """Test helper matching the pure-stdlib formal launcher claim bytes."""

    _exclusive_write_json(
        ATTEMPT_PATH,
        {
            "schema_version": "exp-local-003-c1-attempt-claim/v1",
            "card_sha256": CARD_SHA256,
            "attempt_ordinal": 0,
            "rerun_permitted": False,
            "failure_is_terminal": True,
            "authority_validation_occurs_after_claim": True,
        },
    )


def _verify_c1_attempt_claim() -> None:
    expected = {
        "schema_version": "exp-local-003-c1-attempt-claim/v1",
        "card_sha256": CARD_SHA256,
        "attempt_ordinal": 0,
        "rerun_permitted": False,
        "failure_is_terminal": True,
        "authority_validation_occurs_after_claim": True,
    }
    if ATTEMPT_PATH.read_bytes() != canonical_bytes(expected):
        raise MaterializationError(
            "C1 launcher claim bytes differ from frozen authority"
        )


def _record_terminal_failure(
    error: BaseException, *, lock_commit: str, lock_sha256: str
) -> None:
    if FAILURE_PATH.exists():
        return
    try:
        _exclusive_write_json(
            FAILURE_PATH,
            {
                "schema_version": "exp-local-003-c1-terminal-failure/v1",
                "card_sha256": CARD_SHA256,
                "source_lock_commit": lock_commit,
                "preimplementation_lock_sha256": lock_sha256,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:1000],
                "rerun_permitted": False,
            },
        )
    except OSError:
        # The durable attempt claim is already sufficient to reject retries;
        # never obscure the original protocol/infrastructure failure.
        pass


def _seal_vault_git(
    vault: Path,
    *,
    lock_commit: str,
    expected_files: frozenset[str],
    role: str,
) -> dict[str, str]:
    if role not in ("assessor", "generator-private"):
        raise MaterializationError("vault seal role is unsupported")
    actual_files: set[str] = set()
    for path in vault.rglob("*"):
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if path.is_symlink() or bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise MaterializationError(f"vault contains link/reparse entry: {path}")
        if path.is_file():
            actual_files.add(path.relative_to(vault).as_posix())
    if actual_files != expected_files:
        raise MaterializationError(
            f"{role} vault file set drift: "
            f"extra={sorted(actual_files - expected_files)}, "
            f"missing={sorted(expected_files - actual_files)}"
        )
    commit_date = _run_git("show", "-s", "--format=%cI", lock_commit)
    environment = {
        **_closed_git_environment(),
        "GIT_AUTHOR_NAME": "GeoTarget Research Vault",
        "GIT_AUTHOR_EMAIL": "research-vault@invalid",
        "GIT_COMMITTER_NAME": "GeoTarget Research Vault",
        "GIT_COMMITTER_EMAIL": "research-vault@invalid",
        "GIT_AUTHOR_DATE": commit_date,
        "GIT_COMMITTER_DATE": commit_date,
    }
    common = _git_command_prefix()
    commands = (
        [*common, "init", "--initial-branch=private-evidence"],
        [*common, "add", "--all"],
        [
            *common,
            "commit",
            "-m",
            f"research(local): seal development {role} authority",
        ],
    )
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=vault,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise MaterializationError(
                f"{role} vault git seal failed: {completed.stderr.strip()}"
            )
    if (vault / ".git" / "objects" / "info" / "alternates").exists():
        raise MaterializationError(f"{role} vault unexpectedly uses object alternates")
    completed = subprocess.run(
        [*common, "rev-parse", "HEAD"],
        cwd=vault,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise MaterializationError("private vault commit identity is invalid")
    tree_completed = subprocess.run(
        [*common, "rev-parse", "HEAD^{tree}"],
        cwd=vault,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    tree = tree_completed.stdout.strip()
    if tree_completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", tree) is None:
        raise MaterializationError("private vault tree identity is invalid")
    parent_completed = subprocess.run(
        [*common, "rev-list", "--parents", "-n", "1", "HEAD"],
        cwd=vault,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if parent_completed.returncode != 0 or parent_completed.stdout.strip().split() != [
        commit
    ]:
        raise MaterializationError(f"{role} vault seal is not an orphan root commit")
    status_completed = subprocess.run(
        [*common, "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=vault,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if status_completed.returncode != 0 or status_completed.stdout:
        raise MaterializationError(f"{role} vault is not clean after sealing")
    tree_listing = subprocess.run(
        [*common, "ls-tree", "-r", "--full-tree", "HEAD"],
        cwd=vault,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if tree_listing.returncode != 0:
        raise MaterializationError(f"cannot inspect sealed {role} vault tree")
    immutable_paths: set[str] = set()
    for line in tree_listing.stdout.splitlines():
        metadata, separator, relative = line.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[1] != "blob":
            raise MaterializationError(f"{role} vault contains a non-blob tree entry")
        if fields[0] not in ("100644", "100755"):
            raise MaterializationError(f"{role} vault contains a non-regular mode")
        immutable_paths.add(relative)
    if immutable_paths != expected_files:
        raise MaterializationError(f"sealed {role} vault file set differs")
    for relative in sorted(expected_files):
        blob = subprocess.run(
            [*common, "show", f"HEAD:{relative}"],
            cwd=vault,
            env=environment,
            check=False,
            capture_output=True,
            text=False,
        )
        if (
            blob.returncode != 0
            or bytes(blob.stdout) != (vault / relative).read_bytes()
        ):
            raise MaterializationError(f"sealed {role} blob differs: {relative}")
    return {"commit": commit, "tree": tree}


def _publish_documents(
    candidate_publication: Path,
    vault_publication: Path,
    private_vault_publication: Path,
    documents: dict[str, dict[str, Any]],
    bootstrap: bytes,
    *,
    stage: str,
    locked_decision: dict[str, Any] | None,
    candidate_final_path: Path,
    timing_started: tuple[int, int, int],
    lock_sha256: str,
    lock_commit: str,
    child_cpu_nanoseconds: int,
) -> None:
    if stage not in ("development", "locked"):
        raise MaterializationError("publication stage is unsupported")
    case_count = 64 if stage == "development" else 96
    primary_count = 48 if stage == "development" else 96
    safety_count = 16 if stage == "development" else 0
    candidate_root = candidate_publication
    assessor_root = vault_publication / "assessor"
    private_root = private_vault_publication / "generator-private"
    candidate_root.mkdir(parents=True)
    assessor_root.mkdir(parents=True)
    private_root.mkdir(parents=True)

    candidate_artifact = _gzip_document(
        candidate_root / f"{stage}-candidate-inputs.json.gz", documents["candidate"]
    )
    if stage == "development":
        if locked_decision is not None:
            raise MaterializationError(
                "development publication cannot expose a locked selection"
            )
        locked_selection_artifact = None
    else:
        if not isinstance(locked_decision, dict):
            raise MaterializationError(
                "locked publication requires a development decision"
            )
        _validate_schema(locked_decision, "development-decision-record.schema.json")
        locked_selection = {
            "schema_version": "geotarget.exp-local-003.locked-selection/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "stage": "locked",
            "selected_variant": locked_decision["selected_variant"],
            "candidate_input_sha256": _raw_content_hash(
                documents["candidate"], context="candidate input"
            ),
        }
        _validate_schema(locked_selection, "locked-selection.schema.json")
        locked_selection_path = candidate_root / "locked-selection.json"
        _write_json(locked_selection_path, locked_selection)
        locked_selection_artifact = {
            "path": locked_selection_path.name,
            "sha256": _sha256_path(locked_selection_path),
            "bytes": locked_selection_path.stat().st_size,
        }
    plugin_root = candidate_root / "plugin"
    plugin_root.mkdir()
    plugin_source = SOURCE_ROOT / "Local3FixturePlugin.jl"
    plugin_destination = plugin_root / plugin_source.name
    _write_bytes_durable(plugin_destination, plugin_source.read_bytes())
    plugin_artifact = {
        "path": f"plugin/{plugin_destination.name}",
        "sha256": _sha256_path(plugin_destination),
        "bytes": plugin_destination.stat().st_size,
    }
    assessor_artifact = _gzip_document(
        assessor_root / f"{stage}-assessor-truth.json.gz", documents["assessor"]
    )
    private_artifact = _gzip_document(
        private_root / f"{stage}-generator-private.json.gz",
        documents["generator_private"],
    )
    projection_artifact = _gzip_document(
        private_root / f"{stage}-generator-assessor-projection.json.gz",
        documents["generator_assessor_projection"],
    )
    capture_artifact = _gzip_document(
        private_root / f"{stage}-calibration-capture.json.gz",
        documents["calibration_capture"],
    )
    bootstrap_path = assessor_root / f"{stage}-bootstrap-indices.bin"
    _write_bytes_durable(bootstrap_path, bootstrap)
    bootstrap_artifact = {
        "path": bootstrap_path.name,
        "sha256": _sha256_bytes(bootstrap),
        "bytes": len(bootstrap),
        "format": f"GTLOCAL3BOOT1-{stage}",
    }

    candidate_manifest = {
        "schema_version": "exp-local-003-candidate-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": stage,
        "case_count": case_count,
        "starts_per_case": 32,
        "calibration_points_per_case": 64,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "candidate_input_sha256": _raw_content_hash(
            documents["candidate"], context="candidate input"
        ),
        "artifact": candidate_artifact,
        "fixture_plugin_artifact": plugin_artifact,
        "locked_selection_artifact": locked_selection_artifact,
        "visible_tree": "candidate-only",
    }
    assessor_manifest = {
        "schema_version": "exp-local-003-assessor-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": stage,
        "primary_case_count": primary_count,
        "safety_case_count": safety_count,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "truth_artifact": assessor_artifact,
        "bootstrap_artifact": bootstrap_artifact,
        "visible_tree": "assessor-only-after-candidate-seal",
    }
    private_manifest = {
        "schema_version": "exp-local-003-generator-private-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": stage,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "artifacts": {
            "generator_private": private_artifact,
            "generator_assessor_projection": projection_artifact,
            "calibration_capture": capture_artifact,
        },
        "visible_tree": "materializer-and-audit-only",
    }
    _write_json(candidate_root / "manifest.json", candidate_manifest)
    _write_json(assessor_root / "manifest.json", assessor_manifest)
    _write_json(private_root / "manifest.json", private_manifest)

    process_started_ns, monotonic_started_ns, epoch_started_ns = timing_started
    process_ended_ns = time.process_time_ns()
    monotonic_ended_ns = time.perf_counter_ns()
    epoch_ended_ns = time.time_ns()
    c1_times = {
        "parent_process_cpu_nanoseconds_decimal": str(
            process_ended_ns - process_started_ns
        ),
        "julia_capture_cpu_nanoseconds_decimal": str(child_cpu_nanoseconds),
        "validation_child_cpu_nanoseconds_decimal": str(
            _validation_child_cpu_nanoseconds()
        ),
        "total_process_cpu_nanoseconds_decimal": str(
            process_ended_ns
            - process_started_ns
            + child_cpu_nanoseconds
            + _validation_child_cpu_nanoseconds()
        ),
        "monotonic_elapsed_nanoseconds_decimal": str(
            monotonic_ended_ns - monotonic_started_ns
        ),
        "epoch_started_nanoseconds_decimal": str(epoch_started_ns),
        "epoch_ended_nanoseconds_decimal": str(epoch_ended_ns),
        "host_exclusion_observed": False,
        "primary_oracle_work_included": False,
        "count_in_end_to_end_exactly_once": True,
    }

    candidate_completion = {
        "schema_version": "exp-local-003-candidate-one-shot-completion/v1",
        "partition": stage,
        "candidate_manifest_sha256": _sha256_path(candidate_root / "manifest.json"),
        "source_lock_commit": lock_commit,
        "rerun_permitted": False,
        "contains_assessor_digest": False,
    }
    _write_json(candidate_root / COMPLETION_NAME, candidate_completion)

    vault_manifest = {
        "schema_version": "exp-local-003-assessor-vault-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": stage,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "source_lock_commit": lock_commit,
        "candidate_manifest_sha256": _sha256_path(candidate_root / "manifest.json"),
        "assessor_manifest_sha256": _sha256_path(assessor_root / "manifest.json"),
        "c1_materialization_times": c1_times,
        "candidate_process_argument": str(candidate_final_path),
        "candidate_repository_contains_vault": False,
        "assessor_open_order": "after sealed candidate raw output and process exit",
        "rerun_permitted": False,
        "locked_inputs_materialized": stage == "locked",
        "locked_authority": (
            None
            if locked_decision is None
            else {
                "development_assessment_sha256": locked_decision[
                    "development_assessment_sha256"
                ],
                "development_decision_record_sha256": _sha256_bytes(
                    canonical_bytes(locked_decision)
                ),
                "decision_commit": locked_decision["decision_commit"],
                "selected_variant": locked_decision["selected_variant"],
                "selected_path": locked_decision["selected_path"],
                "locked_selection_sha256": (
                    None
                    if locked_selection_artifact is None
                    else locked_selection_artifact["sha256"]
                ),
            }
        ),
    }
    _write_json(vault_publication / "manifest.json", vault_manifest)
    vault_completion = {
        "schema_version": "exp-local-003-assessor-vault-one-shot-completion/v1",
        "partition": stage,
        "manifest_sha256": _sha256_path(vault_publication / "manifest.json"),
        "source_lock_commit": lock_commit,
        "rerun_permitted": False,
    }
    _write_json(vault_publication / COMPLETION_NAME, vault_completion)
    private_vault_manifest = {
        "schema_version": "exp-local-003-generator-private-vault-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": stage,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "source_lock_commit": lock_commit,
        "candidate_manifest_sha256": _sha256_path(candidate_root / "manifest.json"),
        "generator_private_manifest_sha256": _sha256_path(
            private_root / "manifest.json"
        ),
        "candidate_repository_contains_private_vault": False,
        "assessor_repository_contains_private_vault": False,
        "formal_assessor_input": False,
        "rerun_permitted": False,
    }
    _write_json(private_vault_publication / "manifest.json", private_vault_manifest)
    private_completion = {
        "schema_version": "exp-local-003-generator-private-vault-completion/v1",
        "partition": stage,
        "manifest_sha256": _sha256_path(private_vault_publication / "manifest.json"),
        "source_lock_commit": lock_commit,
        "rerun_permitted": False,
    }
    _write_json(private_vault_publication / COMPLETION_NAME, private_completion)


def _materialize_from_modules(
    generator: ModuleType,
    bootstrap_module: ModuleType,
    assessor_module: ModuleType,
    candidate_publication: Path,
    vault_publication: Path,
    private_vault_publication: Path,
    *,
    master_secret: bytes,
    timing_started: tuple[int, int, int],
    lock_sha256: str,
    lock_commit: str,
) -> None:
    build = getattr(generator, "build_development_documents", None)
    if not callable(build):
        raise MaterializationError("frozen generator lacks build_development_documents")
    if not isinstance(master_secret, bytes) or len(master_secret) != 32:
        raise MaterializationError("C1 master secret must be exactly 32 bytes")
    documents = build(master_secret=master_secret)
    if not isinstance(documents, dict):
        raise MaterializationError(
            "frozen generator did not return a projection object"
        )
    make_bootstrap = getattr(bootstrap_module, "bootstrap_index_bytes", None)
    parse_bootstrap = getattr(bootstrap_module, "parse_bootstrap_index_bytes", None)
    if not callable(make_bootstrap) or not callable(parse_bootstrap):
        raise MaterializationError("frozen bootstrap module lacks required functions")
    bootstrap = make_bootstrap("development")
    if not isinstance(bootstrap, bytes):
        raise MaterializationError("bootstrap authority is not bytes")
    parse_bootstrap(
        bootstrap,
        expected_stage="development",
        expected_sha256=_sha256_bytes(bootstrap),
    )
    materialize_stage_documents(
        documents=documents,
        stage="development",
        assessor_module=assessor_module,
        bootstrap_bytes=bootstrap,
        candidate_publication=candidate_publication,
        vault_publication=vault_publication,
        private_vault_publication=private_vault_publication,
        candidate_final_path=CANDIDATE_OUTPUT_PATH,
        group_index_map={0: 0, 1: 1},
        locked_decision=None,
        master_secret=master_secret,
        timing_started=timing_started,
        lock_sha256=lock_sha256,
        lock_commit=lock_commit,
    )


def materialize_stage_documents(
    *,
    documents: dict[str, dict[str, Any]],
    stage: str,
    assessor_module: ModuleType,
    bootstrap_bytes: bytes,
    candidate_publication: Path,
    vault_publication: Path,
    private_vault_publication: Path,
    candidate_final_path: Path,
    group_index_map: dict[int, int],
    locked_decision: dict[str, Any] | None,
    master_secret: bytes,
    timing_started: tuple[int, int, int],
    lock_sha256: str,
    lock_commit: str,
) -> None:
    """Validate, capture and publish one stage without choosing its inputs."""

    if stage not in ("development", "locked"):
        raise MaterializationError("stage materializer accepts development or locked")
    expected_group_map = (
        {0: 0, 1: 1} if stage == "development" else {2: 0, 3: 1, 4: 2, 5: 3}
    )
    if group_index_map != expected_group_map:
        raise MaterializationError("stage-local latent-group mapping drift")
    if not isinstance(bootstrap_bytes, bytes):
        raise MaterializationError("bootstrap authority is not bytes")
    validate_documents(documents, master_secret=master_secret, stage=stage)
    parse_bootstrap = getattr(assessor_module, "parse_bootstrap_index_bytes", None)
    if not callable(parse_bootstrap):
        raise MaterializationError("assessor lacks frozen bootstrap parser")
    parse_bootstrap(
        bootstrap_bytes,
        expected_stage=stage,
        expected_sha256=_sha256_bytes(bootstrap_bytes),
    )
    capture, child_cpu_nanoseconds = _capture_calibration_truth(
        documents["candidate"], documents["assessor"]
    )
    formal_truth = _build_formal_assessor_truth(
        documents,
        capture,
        bootstrap_bytes,
        assessor_module,
        stage=stage,
        group_index_map=group_index_map,
        locked_decision=locked_decision,
    )
    publication_documents = {
        "candidate": documents["candidate"],
        "assessor": formal_truth,
        "generator_private": documents["generator_private"],
        "generator_assessor_projection": documents["assessor"],
        "calibration_capture": capture,
    }
    _publish_documents(
        candidate_publication,
        vault_publication,
        private_vault_publication,
        publication_documents,
        bootstrap_bytes,
        stage=stage,
        locked_decision=locked_decision,
        candidate_final_path=candidate_final_path,
        timing_started=timing_started,
        lock_sha256=lock_sha256,
        lock_commit=lock_commit,
        child_cpu_nanoseconds=child_cpu_nanoseconds,
    )


def materialize(*, claim_already_created: bool = False) -> Path:
    if not claim_already_created:
        raise MaterializationError(
            "formal C1 must enter through launch_c1.py before project imports"
        )
    # Invocation shape is a launcher precondition, not the C1 attempt itself.
    # Check it before the durable claim so missing ``-I -B -S`` cannot
    # accidentally consume the only formal attempt.
    _python_execution_record()
    if not all(
        path.is_file()
        for path in (
            LOCK_PATH,
            VISIBILITY_PATH,
            NUMERIC_DOMAIN_PATH,
            LOCAL_OPTIONS_PATH,
            ENVIRONMENT_LOCK_PATH,
        )
    ):
        raise MaterializationError(
            "C0 lock, visibility, numeric-domain and local-options artifacts are required"
        )
    lock = _load_object(LOCK_PATH)
    lock_commit = _verify_clean_lock_head(lock, claim_already_created=True)
    lock_sha256 = _sha256_path(LOCK_PATH)
    for path in (
        CANDIDATE_STAGING_PATH,
        VAULT_STAGING_PATH,
        PRIVATE_VAULT_STAGING_PATH,
        FAILURE_PATH,
    ):
        if path.exists():
            raise MaterializationError(f"preexisting C1 evidence/staging path: {path}")
    _verify_c1_attempt_claim()
    try:
        # Every failure after the durable claim, including environment,
        # dependency, schema or Julia capture failure, terminates C1.
        _verify_file_lock(lock)
        generator = _import_frozen(
            "local3_frozen_generator", SOURCE_ROOT / "generator.py"
        )
        bootstrap = _import_frozen(
            "local3_frozen_bootstrap", SOURCE_ROOT / "bootstrap_indices.py"
        )
        assessor = _import_frozen("local3_frozen_assessor", SOURCE_ROOT / "assessor.py")
        # The report-only input-preparation phase begins only after protocol,
        # environment and dependency validation. It includes generation,
        # compilation/capture and artifact projection, not gate verification.
        timing_started = (
            time.process_time_ns(),
            time.perf_counter_ns(),
            time.time_ns(),
        )
        _begin_validation_child_accounting()
        CANDIDATE_STAGING_PATH.mkdir()
        VAULT_STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
        VAULT_STAGING_PATH.mkdir()
        PRIVATE_VAULT_STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRIVATE_VAULT_STAGING_PATH.mkdir()
        _materialize_from_modules(
            generator,
            bootstrap,
            assessor,
            CANDIDATE_STAGING_PATH,
            VAULT_STAGING_PATH,
            PRIVATE_VAULT_STAGING_PATH,
            master_secret=os.urandom(32),
            timing_started=timing_started,
            lock_sha256=lock_sha256,
            lock_commit=lock_commit,
        )
        # C1 input-preparation accounting ends after all candidate/assessor/
        # private artifact bytes and their submanifests exist. Root evidence
        # manifests, anchors and Git sealing are publication overhead.
        _end_validation_child_accounting()
        assessor_vault_seal = _seal_vault_git(
            VAULT_STAGING_PATH,
            lock_commit=lock_commit,
            expected_files=EXPECTED_ASSESSOR_VAULT_FILES,
            role="assessor",
        )
        private_vault_seal = _seal_vault_git(
            PRIVATE_VAULT_STAGING_PATH,
            lock_commit=lock_commit,
            expected_files=EXPECTED_PRIVATE_VAULT_FILES,
            role="generator-private",
        )
        candidate_tree = _publication_tree_record(CANDIDATE_STAGING_PATH)
        stage_anchor = {
            "schema_version": "geotarget.exp-local-003.stage-vault-anchor/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "stage": "development",
            "source_lock_commit": lock_commit,
            "preimplementation_lock_sha256": lock_sha256,
            "materialization_attempt_claim_sha256": _sha256_path(ATTEMPT_PATH),
            "c1_phase_accounting": _load_object(VAULT_STAGING_PATH / "manifest.json")[
                "c1_materialization_times"
            ],
            "assessor_vault_git_commit": assessor_vault_seal["commit"],
            "assessor_vault_git_tree": assessor_vault_seal["tree"],
            "assessor_vault_manifest_sha256": _sha256_path(
                VAULT_STAGING_PATH / "manifest.json"
            ),
            "assessor_vault_completion_sha256": _sha256_path(
                VAULT_STAGING_PATH / COMPLETION_NAME
            ),
            "assessor_manifest_sha256": _sha256_path(
                VAULT_STAGING_PATH / "assessor" / "manifest.json"
            ),
            "candidate_manifest_sha256": _sha256_path(
                CANDIDATE_STAGING_PATH / "manifest.json"
            ),
            "candidate_completion_sha256": _sha256_path(
                CANDIDATE_STAGING_PATH / COMPLETION_NAME
            ),
            "candidate_publication_tree": candidate_tree,
            "candidate_visible": False,
            "rerun_permitted": False,
        }
        _validate_schema(stage_anchor, "stage-vault-anchor.schema.json")
        _exclusive_write_json(VAULT_ANCHOR_PATH, stage_anchor)
        private_anchor = {
            "schema_version": (
                "geotarget.exp-local-003.generator-private-vault-anchor/v1"
            ),
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "stage": "development",
            "source_lock_commit": lock_commit,
            "materialization_attempt_claim_sha256": _sha256_path(ATTEMPT_PATH),
            "stage_vault_anchor_sha256": _sha256_path(VAULT_ANCHOR_PATH),
            "generator_private_vault_git_commit": private_vault_seal["commit"],
            "generator_private_vault_git_tree": private_vault_seal["tree"],
            "generator_private_vault_manifest_sha256": _sha256_path(
                PRIVATE_VAULT_STAGING_PATH / "manifest.json"
            ),
            "generator_private_vault_completion_sha256": _sha256_path(
                PRIVATE_VAULT_STAGING_PATH / COMPLETION_NAME
            ),
            "generator_private_manifest_sha256": _sha256_path(
                PRIVATE_VAULT_STAGING_PATH / "generator-private" / "manifest.json"
            ),
            "candidate_manifest_sha256": _sha256_path(
                CANDIDATE_STAGING_PATH / "manifest.json"
            ),
            "candidate_visible": False,
            "formal_assessor_input": False,
            "rerun_permitted": False,
        }
        _validate_schema(private_anchor, "generator-private-vault-anchor.schema.json")
        _exclusive_write_json(PRIVATE_VAULT_ANCHOR_PATH, private_anchor)
        if (
            CANDIDATE_OUTPUT_PATH.exists()
            or VAULT_OUTPUT_PATH.exists()
            or PRIVATE_VAULT_OUTPUT_PATH.exists()
        ):
            raise MaterializationError("development output appeared during staging")
        _durable_directory_rename(VAULT_STAGING_PATH, VAULT_OUTPUT_PATH)
        _durable_directory_rename(PRIVATE_VAULT_STAGING_PATH, PRIVATE_VAULT_OUTPUT_PATH)
        _durable_directory_rename(CANDIDATE_STAGING_PATH, CANDIDATE_OUTPUT_PATH)
        return CANDIDATE_OUTPUT_PATH
    except BaseException as error:
        _end_validation_child_accounting()
        _record_terminal_failure(
            error, lock_commit=lock_commit, lock_sha256=lock_sha256
        )
        raise


def preflight() -> None:
    """Verify the exact no-output C1 launch boundary without claiming C1."""

    _python_execution_record()
    if not all(
        path.is_file()
        for path in (
            LOCK_PATH,
            VISIBILITY_PATH,
            NUMERIC_DOMAIN_PATH,
            LOCAL_OPTIONS_PATH,
            ENVIRONMENT_LOCK_PATH,
        )
    ):
        raise MaterializationError("C1 preflight requires every frozen C0 artifact")
    lock = _load_object(LOCK_PATH)
    _verify_clean_lock_head(lock)
    _verify_file_lock(lock)


def main() -> int:
    raise MaterializationError(
        "direct execution is forbidden; use `python -I -B -S launch_c1.py`"
    )


if __name__ == "__main__":
    raise SystemExit(main())
