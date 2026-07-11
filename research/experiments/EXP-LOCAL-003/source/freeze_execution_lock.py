"""Freeze the stage-specific EXP-LOCAL-003 candidate execution boundary.

The only formal entry points are the pure-stdlib claim-first launcher::

    python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_execution_lock.py development
    python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_execution_lock.py locked

This helper has no direct CLI.  There are no output, overwrite, force, or
resume options.  Development runs at the immutable C1 commit with the exact
untracked C2 source/evidence/claim set; locked runs at the immutable C4 commit
with only its claim untracked and proves that runtime sources still have their
C2 Git blob identities.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, TypeAlias, cast

# A malformed non-``-B`` invocation must not dirty C0 before the entry-point
# check rejects it.  ``sys.flags.dont_write_bytecode`` still records whether
# the caller actually supplied ``-B``.
sys.dont_write_bytecode = True

from jsonschema import Draft202012Validator  # noqa: E402


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
for _import_root in (PYTHON_SOURCE, SOURCE_ROOT):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from geotarget.canonical import canonical_bytes  # noqa: E402

import authority  # noqa: E402
import materialize_development as environment_contract  # noqa: E402


Stage: TypeAlias = Literal["development", "locked"]

CARD_SHA256: Final = authority.CARD_SHA256
EXPERIMENT_ID: Final = authority.EXPERIMENT_ID
EXPERIMENT_PREFIX: Final = "research/experiments/EXP-LOCAL-003"
PREIMPLEMENTATION_LOCK_PATH: Final = f"{EXPERIMENT_PREFIX}/preimplementation-lock.json"
ENVIRONMENT_LOCK_PATH: Final = f"{EXPERIMENT_PREFIX}/environment-lock.json"
LOCAL_OPTIONS_PATH: Final = f"{EXPERIMENT_PREFIX}/local-options-contract.json"
DEVELOPMENT_ANCHOR_PATH: Final = f"{EXPERIMENT_PREFIX}/C1_STAGE_VAULT_ANCHOR.json"
LOCKED_ANCHOR_PATH: Final = f"{EXPERIMENT_PREFIX}/C4_LOCKED_STAGE_VAULT_ANCHOR.json"
DEVELOPMENT_AUTHORIZATION_PATH: Final = (
    f"{EXPERIMENT_PREFIX}/C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
)
DEVELOPMENT_OUTPUT_PATH: Final = f"{EXPERIMENT_PREFIX}/candidate-execution-lock.json"
LOCKED_OUTPUT_PATH: Final = f"{EXPERIMENT_PREFIX}/locked-candidate-execution-lock.json"
DEFAULT_EQUIVALENCE_PATH: Final = f"{EXPERIMENT_PREFIX}/C2_L0_DEFAULT_EQUIVALENCE.json"
RUNTIME_SOURCE_PATHS: Final = (
    "julia/GeoTargetCore/src/local_model_transform.jl",
    f"{EXPERIMENT_PREFIX}/source/candidate_runner.jl",
)
TEST_SOURCE_PATHS: Final = ("julia/GeoTargetCore/test/test_local_model_transform.jl",)
ISOLATED_TEST_PROJECT_PATHS: Final = (
    "julia/Project.toml",
    "julia/Manifest.toml",
)
ISOLATED_TEST_PACKAGE_PATHS: Final = tuple(
    path
    for package in (
        "julia/GeoTargetBase",
        "julia/GeoTargetCore",
        "julia/GeoTargetGeometry",
    )
    for path in (f"{package}/Project.toml", f"{package}/src")
)
DEVELOPMENT_DIRTY_PATHS: Final = frozenset(
    (*RUNTIME_SOURCE_PATHS, *TEST_SOURCE_PATHS, DEFAULT_EQUIVALENCE_PATH)
)
COMPARISON_FIXTURE_IDS: Final = (
    "JULIA-CORE-DEFAULT",
    "OPAQUE-PLUGIN-DEFAULT",
)
RUNNER_SOURCE_PATH: Final = f"{EXPERIMENT_PREFIX}/source/candidate_runner.jl"
LOCK_SCHEMA: Final = "geotarget.exp-local-003.candidate-execution-lock/v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class FreezeError(RuntimeError):
    """A formal execution-lock precondition or binding failed closed."""


@dataclass(frozen=True, slots=True)
class FreezeContext:
    """Immutable stage-input authority resolved at the required main HEAD."""

    stage: Stage
    head: str
    repository: authority.GitObjectRepository
    stage_input: authority.StageInputRecord


@dataclass(frozen=True, slots=True)
class ClaimIdentity:
    """Filesystem identity of the launcher's durable empty claim."""

    device: int
    inode: int
    creation_nanoseconds: int


def _path(relative: str) -> Path:
    return REPOSITORY_ROOT.joinpath(*relative.split("/"))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strict_object(payload: bytes, context: str) -> dict[str, Any]:
    value = authority.strict_jcs_bytes(payload, context=context)
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise FreezeError(f"{context} must be a JSON object")
    return cast(dict[str, Any], value)


def _json_object(payload: bytes, context: str) -> dict[str, Any]:
    """Decode closed semantic JSON while rejecting duplicates/extensions."""

    def reject_constant(token: str) -> None:
        raise ValueError(f"non-standard numeric literal {token!r}")

    def reject_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise FreezeError(f"invalid {context}: {error}") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise FreezeError(f"{context} must be a JSON object")
    return cast(dict[str, Any], value)


def _read_regular(relative: str, *, nonempty: bool = True) -> bytes:
    path = _path(relative)
    try:
        before = path.lstat()
    except OSError as error:
        raise FreezeError(
            f"required file is unavailable: {relative}: {error}"
        ) from error
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(before, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or attributes & reparse
    ):
        raise FreezeError(
            f"required path is not a regular non-reparse file: {relative}"
        )
    try:
        payload = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise FreezeError(f"cannot read required file: {relative}: {error}") from error
    if (
        before.st_mode != after.st_mode
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != before.st_size
    ):
        raise FreezeError(f"required file changed while being read: {relative}")
    if nonempty and not payload:
        raise FreezeError(f"required file is empty: {relative}")
    return payload


def _schema(name: str) -> Mapping[str, Any]:
    try:
        value = json.loads((SOURCE_ROOT / name).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FreezeError(f"cannot load schema {name}: {error}") from error
    if not isinstance(value, dict):
        raise FreezeError(f"schema {name} is not an object")
    try:
        Draft202012Validator.check_schema(value)
    except Exception as error:
        raise FreezeError(f"schema {name} is invalid: {error}") from error
    return cast(Mapping[str, Any], value)


def _validate_schema(document: Mapping[str, Any], name: str, context: str) -> None:
    errors = sorted(
        Draft202012Validator(_schema(name)).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise FreezeError(f"{context} fails {name} at {location}: {errors[0].message}")


def _environment_lock_git() -> authority.GitExecutable:
    document = _strict_object(
        _read_regular(ENVIRONMENT_LOCK_PATH), "C0 environment lock"
    )
    if (
        document.get("schema_version") != "exp-local-003-environment-lock/v1"
        or document.get("card_sha256") != CARD_SHA256
    ):
        raise FreezeError("C0 environment-lock identity differs")
    python_record = document.get("python")
    if not isinstance(python_record, dict):
        raise FreezeError("C0 environment lock has no Python authority")
    python_path = python_record.get("runtime_executable")
    python_sha256 = python_record.get("runtime_sha256")
    if not isinstance(python_path, str) or not isinstance(python_sha256, str):
        raise FreezeError("C0 environment lock has no pinned Python identity")
    try:
        locked_python = Path(python_path)
        if (
            not locked_python.is_file()
            or locked_python.resolve() != Path(sys.executable).resolve()
            or _sha256(locked_python.read_bytes()) != python_sha256
        ):
            raise FreezeError("environment-locked Python runtime differs")
    except OSError as error:
        raise FreezeError(
            f"cannot verify environment-locked Python: {error}"
        ) from error
    tools = document.get("tools")
    if not isinstance(tools, dict):
        raise FreezeError("C0 environment lock has no closed tool authority")
    git_path = tools.get("git_executable")
    git_sha256 = tools.get("git_sha256")
    if not isinstance(git_path, str) or not isinstance(git_sha256, str):
        raise FreezeError("C0 environment lock has no pinned Git identity")
    try:
        return authority.pin_git_executable(Path(git_path), git_sha256)
    except authority.AuthorityError as error:
        raise FreezeError(
            f"environment-locked Git verification failed: {error}"
        ) from error


def _git_environment() -> dict[str, str]:
    null_device = "NUL" if os.name == "nt" else "/dev/null"
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": null_device,
        "GIT_CONFIG_SYSTEM": null_device,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
    }
    if os.name == "nt":
        for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP"):
            if value := os.environ.get(key):
                environment[key] = value
    return environment


def _git_bytes(git: authority.GitExecutable, *arguments: str) -> bytes:
    command = [
        str(git.path),
        "--no-replace-objects",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "core.autocrlf=false",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=_git_environment(),
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise FreezeError(f"pinned Git could not execute: {error}") from error
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise FreezeError(f"pinned Git rejected {' '.join(arguments)}: {message}")
    return completed.stdout


def _git_text(git: authority.GitExecutable, *arguments: str) -> str:
    try:
        return _git_bytes(git, *arguments).decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise FreezeError("pinned Git returned non-UTF-8 control output") from error


def _status_entries(payload: bytes) -> dict[str, str]:
    if payload and not payload.endswith(b"\0"):
        raise FreezeError("Git porcelain status is not NUL terminated")
    result: dict[str, str] = {}
    for raw in payload.split(b"\0")[:-1]:
        if len(raw) < 4 or raw[2:3] != b" ":
            raise FreezeError("Git porcelain status record is malformed")
        try:
            status_code = raw[:2].decode("ascii", "strict")
            path = raw[3:].decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise FreezeError("Git status path is not canonical UTF-8") from error
        if (
            not path
            or "\\" in path
            or path.startswith("/")
            or path.endswith("/")
            or "//" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
            or path in result
        ):
            raise FreezeError("Git status contains an unsafe or duplicate path")
        result[path] = status_code
    return result


def _validate_status(stage: Stage, status: Mapping[str, str]) -> None:
    expected = (
        DEVELOPMENT_DIRTY_PATHS | {DEVELOPMENT_OUTPUT_PATH}
        if stage == "development"
        else {LOCKED_OUTPUT_PATH}
    )
    if stage == "development":
        if set(status) != expected or any(code != "??" for code in status.values()):
            raise FreezeError(
                "development freeze requires exactly the five untracked C2 "
                "runtime/test/evidence files plus its durable lock claim"
            )
    elif set(status) != expected or any(code != "??" for code in status.values()):
        raise FreezeError(
            "locked execution-lock freeze requires exactly its durable lock claim"
        )


def _output_path(stage: Stage) -> str:
    return DEVELOPMENT_OUTPUT_PATH if stage == "development" else LOCKED_OUTPUT_PATH


def _anchor_path(stage: Stage) -> str:
    return DEVELOPMENT_ANCHOR_PATH if stage == "development" else LOCKED_ANCHOR_PATH


def _candidate_root(stage: Stage) -> Path:
    name = (
        "development-candidate-inputs"
        if stage == "development"
        else "locked-candidate-inputs"
    )
    return _path(f"{EXPERIMENT_PREFIX}/{name}")


def _assessor_vault(stage: Stage) -> Path:
    name = (
        "development-assessor-vault"
        if stage == "development"
        else "locked-assessor-vault"
    )
    return (
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-vault")
        / "EXP-LOCAL-003"
        / name
    )


def _validate_repository_state(
    stage: Stage,
    git: authority.GitExecutable,
    repository: authority.GitObjectRepository,
    head: str,
) -> None:
    top_level = Path(_git_text(git, "rev-parse", "--show-toplevel")).resolve()
    if top_level != REPOSITORY_ROOT.resolve():
        raise FreezeError("formal execution-lock freeze is not at repository root")
    if _git_text(git, "branch", "--show-current") != "main":
        raise FreezeError("execution-lock freeze must run directly on main")
    if _git_text(git, "rev-parse", "HEAD") != head:
        raise FreezeError("repository HEAD changed during execution-lock freeze")
    status = _status_entries(
        _git_bytes(git, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    )
    _validate_status(stage, status)
    output = _output_path(stage)
    head_index = repository.tree_index(head)
    if output in head_index:
        raise FreezeError("execution-lock output already exists in immutable HEAD")
    if stage == "development":
        if any(path in head_index for path in DEVELOPMENT_DIRTY_PATHS):
            raise FreezeError("a C2 addition already exists in the immutable C1 tree")
    elif any(path not in head_index for path in RUNTIME_SOURCE_PATHS):
        raise FreezeError("locked runtime source is absent from immutable C4")


def _resolve_context(
    stage: Stage, git: authority.GitExecutable, head: str
) -> FreezeContext:
    repository = authority.GitObjectRepository(REPOSITORY_ROOT, git)
    anchor_path = _anchor_path(stage)
    try:
        anchor_blob = repository.blob_at(head, anchor_path)
        stage_input = authority.resolve_stage_input_authority(
            anchor_repository=REPOSITORY_ROOT,
            anchor_commit=head,
            anchor_path=anchor_path,
            anchor_sha256=_sha256(anchor_blob.data),
            candidate_publication_root=_candidate_root(stage),
            assessor_vault_repository=_assessor_vault(stage),
            git_executable=git,
        )
    except authority.AuthorityError as error:
        raise FreezeError(
            f"stage-input authority resolution failed: {error}"
        ) from error
    if stage_input.stage != stage or stage_input.anchor_commit != head:
        raise FreezeError("resolved stage input differs from requested HEAD/stage")
    return FreezeContext(stage, head, repository, stage_input)


def _verify_local_options() -> str:
    document = _json_object(
        _read_regular(LOCAL_OPTIONS_PATH), "C0 local-options contract"
    )
    expected_keys = {
        "schema_version",
        "card_sha256",
        "source_path",
        "source_sha256",
        "julia_version",
        "capture_contract",
        "constructor",
        "constructor_sha256",
        "binary64_bits",
    }
    if set(document) != expected_keys:
        raise FreezeError("C0 local-options contract is not closed")
    if (
        document["schema_version"] != "exp-local-003-local-options-contract/v1"
        or document["card_sha256"] != CARD_SHA256
        or document["source_path"] != "julia/GeoTargetCore/src/local_solver.jl"
        or document["julia_version"] != "1.12.6"
    ):
        raise FreezeError("C0 local-options identity differs")
    source = _read_regular(document["source_path"])
    if document["source_sha256"] != _sha256(source):
        raise FreezeError("C0 LocalSolveOptions source digest differs")
    constructor = document["constructor"]
    if not isinstance(constructor, dict):
        raise FreezeError("C0 LocalSolveOptions constructor is malformed")
    digest = _sha256(canonical_bytes(constructor))
    if document["constructor_sha256"] != digest:
        raise FreezeError("C0 LocalSolveOptions constructor digest differs")
    bits = document["binary64_bits"]
    if not isinstance(bits, dict):
        raise FreezeError("C0 LocalSolveOptions binary64 map is malformed")
    for name, value in constructor.items():
        if name.endswith("_hex"):
            if not isinstance(value, str):
                raise FreezeError("C0 LocalSolveOptions hexadecimal value is malformed")
            parsed = float.fromhex(value)
            expected = f"0x{struct.unpack('>Q', struct.pack('>d', parsed))[0]:016x}"
            if parsed.hex() != value or bits.get(name.removesuffix("_hex")) != expected:
                raise FreezeError(
                    "C0 LocalSolveOptions hexadecimal/bit binding differs"
                )
    return digest


def _verify_c0_bindings(context: FreezeContext) -> str:
    try:
        lock_blob = context.repository.blob_at(
            context.stage_input.source_lock_commit, PREIMPLEMENTATION_LOCK_PATH
        )
    except authority.AuthorityError as error:
        raise FreezeError(
            f"cannot resolve C0 preimplementation lock: {error}"
        ) from error
    if _sha256(lock_blob.data) != context.stage_input.preimplementation_lock_sha256:
        raise FreezeError("stage input preimplementation-lock digest differs")
    lock = _strict_object(lock_blob.data, "C0 preimplementation lock")
    environment = _read_regular(ENVIRONMENT_LOCK_PATH)
    if lock.get("environment_lock_sha256") != _sha256(environment):
        raise FreezeError("C0 environment-lock binding differs")
    local_options_sha256 = _verify_local_options()
    if lock.get("local_options_sha256") != local_options_sha256:
        raise FreezeError("C0 local-options binding differs")
    return local_options_sha256


def _file_records(paths: Sequence[str]) -> list[dict[str, Any]]:
    if tuple(paths) != tuple(sorted(paths)) or len(set(paths)) != len(paths):
        raise FreezeError("frozen source paths are not sorted and unique")
    records: list[dict[str, Any]] = []
    for relative in paths:
        payload = _read_regular(relative)
        records.append(
            {
                "path": relative,
                "sha256": _sha256(payload),
                "byte_length": len(payload),
            }
        )
    return records


def _broker_environment_records(
    request_environment: Mapping[str, str], scratch: Path
) -> list[dict[str, str]]:
    by_folded_name = {
        name.casefold(): (name, value) for name, value in request_environment.items()
    }
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
    for name, value in defaults.items():
        by_folded_name.setdefault(name.casefold(), (name, value))
    return [
        {"name": name, "value": value}
        for name, value in sorted(
            by_folded_name.values(), key=lambda item: (item[0].casefold(), item[0])
        )
    ]


def _validate_isolated_test_execution(
    document: Mapping[str, Any],
    context: FreezeContext,
    *,
    c0_commit: str,
    environment_lock_sha256: str,
    runtime_records: Sequence[Mapping[str, Any]],
    test_records: Sequence[Mapping[str, Any]],
) -> None:
    if (
        tuple(record.get("path") for record in runtime_records) != RUNTIME_SOURCE_PATHS
        or tuple(record.get("path") for record in test_records) != TEST_SOURCE_PATHS
    ):
        raise FreezeError("C2 isolated-test mechanism/test source binding differs")
    execution = document.get("isolated_test_execution")
    if not isinstance(execution, dict):
        raise FreezeError("C2 isolated-test execution evidence is malformed")
    expected_execution_keys = {
        "mode",
        "mechanism_source_granted",
        "command",
        "environment",
        "read_grants",
        "return_code",
        "termination_reason",
        "stdout",
        "stderr",
        "wall_time_nanoseconds",
        "total_user_time_100ns",
        "total_kernel_time_100ns",
        "total_processes",
        "terminated_processes",
        "io_accounting",
        "sandbox",
    }
    if set(execution) != expected_execution_keys:
        raise FreezeError("C2 isolated-test execution object is not closed")
    if document.get("isolated_test_execution_manifest_sha256") != _sha256(
        canonical_bytes(execution)
    ):
        raise FreezeError("C2 isolated-test execution manifest digest differs")
    try:
        (
            _environment_document,
            julia_executable,
            runtime_root,
            depot_root,
            locked_environment,
        ) = authority._c0_environment_authority(  # noqa: SLF001
            context.repository, c0_commit, environment_lock_sha256
        )
    except authority.AuthorityError as error:
        raise FreezeError(f"cannot resolve C0 Julia authority: {error}") from error
    locked_names = (
        "SystemRoot",
        "WINDIR",
        "PATH",
        "JULIA_LOAD_PATH",
        "JULIA_NUM_THREADS",
        "JULIA_CPU_TARGET",
        "JULIA_PKG_OFFLINE",
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
    )
    if any(not isinstance(locked_environment.get(name), str) for name in locked_names):
        raise FreezeError("C0 isolated-test Julia environment is malformed")
    request_environment = {
        name: cast(str, locked_environment[name]) for name in locked_names
    }
    request_environment.update(
        {
            "JULIA_DEPOT_PATH": str(depot_root),
            "JULIA_PKG_PRECOMPILE_AUTO": "0",
            "JULIA_PROJECT": str(REPOSITORY_ROOT / "julia"),
        }
    )
    sandbox = execution.get("sandbox")
    if not isinstance(sandbox, dict):
        raise FreezeError("C2 isolated-test sandbox evidence is malformed")
    scratch_value = sandbox.get("scratch_directory")
    if not isinstance(scratch_value, str):
        raise FreezeError("C2 isolated-test scratch path is malformed")
    scratch = Path(scratch_value)
    if (
        not scratch.is_absolute()
        or scratch.name != "scratch-isolated-test"
        or scratch.exists()
    ):
        raise FreezeError("C2 isolated-test scratch boundary differs")
    expected_command = [
        str(julia_executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={REPOSITORY_ROOT / 'julia'}",
        str(_path(TEST_SOURCE_PATHS[0])),
    ]
    expected_grants = [
        {"path": str(runtime_root), "recursive": True},
        {"path": str(depot_root), "recursive": False},
        {"path": str(depot_root / "packages"), "recursive": True},
        {"path": str(depot_root / "artifacts"), "recursive": True},
        {"path": str(REPOSITORY_ROOT), "recursive": False},
        {"path": str(REPOSITORY_ROOT / "julia"), "recursive": False},
        *(
            {"path": str(_path(path)), "recursive": False}
            for path in ISOLATED_TEST_PROJECT_PATHS
        ),
        *(
            {"path": str(_path(path)), "recursive": path.endswith("/src")}
            for path in ISOLATED_TEST_PACKAGE_PATHS
        ),
        {"path": str(_path(TEST_SOURCE_PATHS[0])), "recursive": False},
    ]
    expected_environment = _broker_environment_records(request_environment, scratch)
    if (
        execution.get("mode") != "isolated-test"
        or execution.get("mechanism_source_granted") is not True
        or execution.get("command") != expected_command
        or execution.get("environment") != expected_environment
        or execution.get("read_grants") != expected_grants
        or execution.get("return_code") != 0
        or execution.get("termination_reason") != "completed"
        or execution.get("total_processes") != 1
        or execution.get("terminated_processes") != 0
    ):
        raise FreezeError("C2 isolated-test command/environment/grants differ")
    stdout = execution.get("stdout")
    stderr = execution.get("stderr")
    if (
        not isinstance(stdout, dict)
        or set(stdout) != {"sha256", "byte_length"}
        or not isinstance(stdout.get("sha256"), str)
        or _SHA256.fullmatch(stdout["sha256"]) is None
        or not isinstance(stdout.get("byte_length"), int)
        or stdout["byte_length"] < 0
        or stderr
        != {
            "sha256": _sha256(b""),
            "byte_length": 0,
        }
    ):
        raise FreezeError("C2 isolated-test stream binding differs")
    for field in (
        "wall_time_nanoseconds",
        "total_user_time_100ns",
        "total_kernel_time_100ns",
    ):
        value = execution.get(field)
        minimum = 1 if field == "wall_time_nanoseconds" else 0
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise FreezeError("C2 isolated-test process accounting differs")
    io_accounting = execution.get("io_accounting")
    io_keys = {
        "read_operation_count",
        "write_operation_count",
        "other_operation_count",
        "read_transfer_count",
        "write_transfer_count",
        "other_transfer_count",
    }
    if (
        not isinstance(io_accounting, dict)
        or set(io_accounting) != io_keys
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in io_accounting.values()
        )
    ):
        raise FreezeError("C2 isolated-test I/O accounting differs")
    expected_allowed_read = [item["path"] for item in expected_grants]
    if (
        sandbox.get("schema_version")
        != "geotarget.exp-local-003.appcontainer-attestation/v2"
        or sandbox.get("claim_reference") != document.get("claim_reference")
        or sandbox.get("capabilities") != []
        or sandbox.get("allowed_read_paths") != expected_allowed_read
        or sandbox.get("environment") != expected_environment
        or sandbox.get("inherited_handle_roles") != ["stdin", "stdout", "stderr"]
        or sandbox.get("token_is_appcontainer") is not True
        or sandbox.get("token_appcontainer_sid_verified") is not True
        or sandbox.get("token_integrity_rid") != 4096
        or sandbox.get("token_elevated") is not False
        or sandbox.get("token_capability_count") != 0
        or sandbox.get("max_processes") != 1
        or sandbox.get("child_process_restricted") is not True
        or sandbox.get("job_assigned_at_creation") is not True
        or sandbox.get("job_membership_verified") is not True
        or sandbox.get("job_limit_flags") != 0x00002008
        or sandbox.get("breakaway_allowed") is not False
        or sandbox.get("kill_on_job_close") is not True
        or sandbox.get("job_empty") is not True
        or sandbox.get("acl_exactly_restored") is not True
        or sandbox.get("scratch_emptied") is not True
        or sandbox.get("profile_deleted") is not True
        or sandbox.get("profile_storage_deleted") is not True
        or sandbox.get("original_acl_manifest_sha256")
        != sandbox.get("restored_acl_manifest_sha256")
    ):
        raise FreezeError("C2 isolated-test AppContainer attestation differs")
    digest_fields = (
        "read_identity_manifest_sha256",
        "denied_probe_manifest_sha256",
        "read_only_probe_manifest_sha256",
        "scratch_access_probe_manifest_sha256",
        "original_acl_manifest_sha256",
        "restored_acl_manifest_sha256",
    )
    if any(
        not isinstance(sandbox.get(field), str)
        or _SHA256.fullmatch(cast(str, sandbox[field])) is None
        for field in digest_fields
    ):
        raise FreezeError("C2 isolated-test attestation digest differs")
    read_count = sandbox.get("read_only_probe_entry_count")
    if (
        not isinstance(read_count, int)
        or isinstance(read_count, bool)
        or read_count < 1
        or sandbox.get("read_identity_manifest_entry_count") != read_count
        or sandbox.get("acl_entry_count") != read_count + 1
    ):
        raise FreezeError("C2 isolated-test read identity/ACL accounting differs")
    profile_storage = sandbox.get("profile_storage_path")
    if not isinstance(profile_storage, str) or os.path.lexists(profile_storage):
        raise FreezeError("C2 isolated-test AppContainer profile cleanup differs")
    expected_probe_states = (
        (str(_path(TEST_SOURCE_PATHS[0])), "allowed", "allowed", 0),
        (str(_path(RUNTIME_SOURCE_PATHS[0])), "allowed", "allowed", 0),
        (str(_path(EXPERIMENT_PREFIX)), "denied", "denied", 5),
        (str(_path(DEFAULT_EQUIVALENCE_PATH)), "denied", "denied", 5),
        (
            str(_path(authority.C1_CANDIDATE_OUTCOME_PATH)),
            "denied",
            "denied",
            5,
        ),
        (
            str(_path(authority.C1_STAGE_VAULT_ANCHOR_PATH)),
            "denied",
            "denied",
            5,
        ),
        (
            str(_path(authority.C1_ATTEMPT_CLAIM_PATH)),
            "denied",
            "denied",
            5,
        ),
        *(
            (str(root), "denied", "denied", 5)
            for root in authority._c1_external_fixed_roots(REPOSITORY_ROOT)  # noqa: SLF001
        ),
        (str(REPOSITORY_ROOT / ".git"), "denied", "denied", 5),
    )
    probes = sandbox.get("access_probes")
    observed_probe_states: list[tuple[Any, Any, Any, Any]] = []
    if isinstance(probes, list):
        for probe in probes:
            if not isinstance(probe, dict) or set(probe) != {
                "path",
                "expected",
                "observed",
                "winerror",
            }:
                raise FreezeError("C2 isolated-test access probe is malformed")
            observed_probe_states.append(
                (
                    probe.get("path"),
                    probe.get("expected"),
                    probe.get("observed"),
                    probe.get("winerror"),
                )
            )
    if tuple(observed_probe_states) != expected_probe_states:
        raise FreezeError("C2 isolated-test recursive namespace probes differ")
    denied_count = sum(item[1] == "denied" for item in expected_probe_states)
    if (
        not isinstance(sandbox.get("denied_probe_entry_count"), int)
        or sandbox["denied_probe_entry_count"] < denied_count
    ):
        raise FreezeError("C2 isolated-test denied namespace accounting differs")


def _validate_default_equivalence(
    context: FreezeContext,
    *,
    local_options_sha256: str,
    runtime_records: Sequence[Mapping[str, Any]],
    test_records: Sequence[Mapping[str, Any]],
) -> None:
    payload = _read_regular(DEFAULT_EQUIVALENCE_PATH)
    document = _strict_object(payload, "C2 default-equivalence evidence")
    _validate_schema(
        document,
        "c2-default-equivalence.schema.json",
        "C2 default-equivalence evidence",
    )
    if list(runtime_records) != document["runtime_sources"]:
        raise FreezeError(
            "C2 evidence runtime source records differ from working bytes"
        )
    if list(test_records) != document["test_sources"]:
        raise FreezeError("C2 evidence test source records differ from working bytes")

    try:
        preimplementation_blob = context.repository.blob_at(
            context.stage_input.source_lock_commit, PREIMPLEMENTATION_LOCK_PATH
        )
    except authority.AuthorityError as error:
        raise FreezeError(f"cannot resolve immutable C0 authority: {error}") from error
    if (
        preimplementation_blob.mode != "100644"
        or _sha256(preimplementation_blob.data)
        != context.stage_input.preimplementation_lock_sha256
    ):
        raise FreezeError("immutable C0 preimplementation-lock binding differs")
    preimplementation = _strict_object(
        preimplementation_blob.data, "immutable C0 preimplementation lock"
    )
    c0_commit = preimplementation.get("c0_source_commit")
    c0_tree = preimplementation.get("c0_source_tree")
    environment_lock_sha256 = preimplementation.get("environment_lock_sha256")
    if (
        not isinstance(c0_commit, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", c0_commit) is None
        or not isinstance(c0_tree, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", c0_tree) is None
        or not isinstance(environment_lock_sha256, str)
        or _SHA256.fullmatch(environment_lock_sha256) is None
        or context.repository.commit_tree(c0_commit) != c0_tree
    ):
        raise FreezeError("immutable C0 commit/tree/environment authority differs")

    def c0_records(paths: Sequence[str], label: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for relative in sorted(paths):
            try:
                blob = context.repository.blob_at(c0_commit, relative)
            except authority.AuthorityError as error:
                raise FreezeError(
                    f"cannot resolve {label} {relative}: {error}"
                ) from error
            if blob.mode != "100644" or not blob.data:
                raise FreezeError(f"{label} is not a nonempty C0 blob: {relative}")
            records.append(
                {
                    "path": relative,
                    "sha256": _sha256(blob.data),
                    "byte_length": len(blob.data),
                }
            )
        return records

    fixture_records = c0_records(
        authority.C0_EQUIVALENCE_FIXTURE_PATHS, "C0 equivalence fixture"
    )
    golden_records = c0_records(
        authority.C0_EQUIVALENCE_GOLDEN_PATHS, "C0 equivalence golden"
    )
    protocol_records = c0_records(
        authority.C0_EQUIVALENCE_PROTOCOL_PATHS, "C0 equivalence protocol"
    )
    if document["fixture_sources"] != fixture_records:
        raise FreezeError("C2 evidence fixture records differ from immutable C0")
    if document["golden_sources"] != golden_records:
        raise FreezeError("C2 evidence golden records differ from immutable C0")

    reference = document["c0_reference_authority"]
    if not isinstance(reference, dict):
        raise FreezeError("C2 C0-reference authority is malformed")
    if (
        reference.get("source_lock_commit") != context.stage_input.source_lock_commit
        or reference.get("c0_source_commit") != c0_commit
        or reference.get("c0_source_tree") != c0_tree
        or reference.get("environment_lock_sha256") != environment_lock_sha256
        or reference.get("capsule_origin") != "immutable-main-git-c0-source-tree"
        or reference.get("protocol_sources") != protocol_records
        or reference.get("protocol_manifest_sha256")
        != _sha256(canonical_bytes(protocol_records))
        or reference.get("reference_child_c2_source_access") != "kernel-denied"
    ):
        raise FreezeError("C2 C0-reference authority binding differs")
    capsule_records = reference.get("capsule_files")
    if not isinstance(capsule_records, list) or not capsule_records:
        raise FreezeError("C2 C0-reference capsule manifest is malformed")
    try:
        c0_index = context.repository.tree_index(c0_commit)
    except authority.AuthorityError as error:
        raise FreezeError(f"cannot enumerate immutable C0 capsule: {error}") from error
    fixed_capsule = {
        "julia/Project.toml",
        "julia/Manifest.toml",
        authority.C0_EQUIVALENCE_CHILD_PATH,
        authority.C0_EQUIVALENCE_PROTOCOL_PATHS[0],
        *authority.C0_EQUIVALENCE_FIXTURE_PATHS,
    }
    package_roots = (
        "julia/GeoTargetBase",
        "julia/GeoTargetCore",
        "julia/GeoTargetGeometry",
    )
    selected_capsule_paths: list[str] = []
    for path, (mode, _oid) in c0_index.items():
        selected = path in fixed_capsule or any(
            path == f"{package}/Project.toml" or path.startswith(f"{package}/src/")
            for package in package_roots
        )
        if not selected:
            continue
        if mode != "100644":
            raise FreezeError(f"C0 capsule source is not a regular blob: {path}")
        selected_capsule_paths.append(path)
    expected_capsule_paths = tuple(sorted(selected_capsule_paths))
    if not fixed_capsule.issubset(expected_capsule_paths):
        raise FreezeError("immutable C0 capsule is missing a fixed source")
    expected_capsule_records = c0_records(
        expected_capsule_paths, "C0 reference capsule"
    )
    if capsule_records != expected_capsule_records:
        raise FreezeError("C2 C0-reference capsule set differs from immutable C0")
    if reference.get("capsule_manifest_sha256") != _sha256(
        canonical_bytes(capsule_records)
    ):
        raise FreezeError("C2 C0-reference capsule manifest digest differs")
    for index, record in enumerate(capsule_records):
        if not isinstance(record, dict) or set(record) != {
            "path",
            "sha256",
            "byte_length",
        }:
            raise FreezeError(f"C2 capsule record {index} is malformed")
        relative = record.get("path")
        if not isinstance(relative, str):
            raise FreezeError(f"C2 capsule record {index} path is malformed")
        try:
            blob = context.repository.blob_at(c0_commit, relative)
        except authority.AuthorityError as error:
            raise FreezeError(
                f"C2 capsule record {index} is not a C0 blob: {error}"
            ) from error
        if (
            blob.mode != "100644"
            or record.get("sha256") != _sha256(blob.data)
            or record.get("byte_length") != len(blob.data)
        ):
            raise FreezeError(f"C2 capsule record {index} differs from C0")
    source_manifest = {
        "runtime_sources": list(runtime_records),
        "test_sources": list(test_records),
        "fixture_sources": fixture_records,
        "golden_sources": golden_records,
        "c0_protocol_sources": protocol_records,
    }
    if document["source_manifest_sha256"] != _sha256(canonical_bytes(source_manifest)):
        raise FreezeError("C2 evidence source manifest digest differs")
    comparisons = document["comparisons"]
    if not isinstance(comparisons, list):
        raise FreezeError("C2 evidence comparison list is malformed")
    fixture_ids = tuple(item.get("fixture_id") for item in comparisons)
    if fixture_ids != COMPARISON_FIXTURE_IDS:
        raise FreezeError("C2 evidence fixture ids/order differ")
    for item in comparisons:
        if (
            not isinstance(item, dict)
            or item.get("reference_output_sha256")
            != item.get("mechanism_disabled_output_sha256")
            or item.get("golden_output_sha256") != item.get("reference_output_sha256")
            or item.get("reference_matches_golden") is not True
            or item.get("mechanism_disabled_matches_golden") is not True
            or item.get("byte_identical") is not True
        ):
            raise FreezeError("C2 evidence does not prove exact disabled/L0 equality")
    for index, item in enumerate(comparisons):
        if (
            item.get("fixture") != fixture_records[index]
            or item.get("golden") != golden_records[index]
        ):
            raise FreezeError("C2 comparison fixture/golden authority differs")
        golden_sha = golden_records[index]["sha256"]
        golden_length = golden_records[index]["byte_length"]
        for field, mode, mechanism_granted in (
            ("reference_execution", "reference", False),
            ("mechanism_disabled_execution", "mechanism-disabled", True),
        ):
            execution = item.get(field)
            if not isinstance(execution, dict):
                raise FreezeError("C2 comparison execution evidence is malformed")
            sandbox = execution.get("sandbox")
            if (
                execution.get("mode") != mode
                or execution.get("mechanism_source_granted") is not mechanism_granted
                or execution.get("return_code") != 0
                or execution.get("termination_reason") != "completed"
                or execution.get("total_processes") != 1
                or execution.get("terminated_processes") != 0
                or execution.get("stdout")
                != {"sha256": golden_sha, "byte_length": golden_length}
                or not isinstance(sandbox, dict)
                or sandbox.get("claim_reference") != document["claim_reference"]
                or sandbox.get("token_is_appcontainer") is not True
                or sandbox.get("token_appcontainer_sid_verified") is not True
                or sandbox.get("token_capability_count") != 0
                or sandbox.get("max_processes") != 1
                or sandbox.get("job_limit_flags") != 0x00002008
                or sandbox.get("job_empty") is not True
                or sandbox.get("acl_exactly_restored") is not True
                or sandbox.get("profile_deleted") is not True
                or sandbox.get("profile_storage_deleted") is not True
            ):
                raise FreezeError("C2 comparison execution authority differs")
    if document["comparison_manifest_sha256"] != _sha256(canonical_bytes(comparisons)):
        raise FreezeError("C2 evidence comparison manifest digest differs")
    _validate_isolated_test_execution(
        document,
        context,
        c0_commit=c0_commit,
        environment_lock_sha256=environment_lock_sha256,
        runtime_records=runtime_records,
        test_records=test_records,
    )
    expected_bindings = {
        "schema_version": "geotarget.exp-local-003.c2-default-equivalence/v1",
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": "development",
        "stage_input_anchor_commit": context.stage_input.anchor_commit,
        "stage_input_anchor_sha256": context.stage_input.anchor_file.sha256,
        "preimplementation_lock_sha256": (
            context.stage_input.preimplementation_lock_sha256
        ),
        "local_options_sha256": local_options_sha256,
        "baseline_variant": "L0-SEMANTIC",
        "candidate_mechanism_enabled": False,
        "passed": True,
    }
    if any(document.get(key) != value for key, value in expected_bindings.items()):
        raise FreezeError("C2 evidence stage/input/C0 binding differs")


def _locked_c2_commit(context: FreezeContext) -> str:
    development = context.stage_input.development_authority
    if development is None:
        raise FreezeError("locked stage input has no development authority")
    development_commit = development.get("development_authorization_anchor_commit")
    if not isinstance(development_commit, str):
        raise FreezeError("locked development authorization commit is malformed")
    try:
        if context.repository.commit_parents(context.head) != (development_commit,):
            raise FreezeError("C4 HEAD is not the development authorization child")
        blob = context.repository.blob_at(
            development_commit, DEVELOPMENT_AUTHORIZATION_PATH
        )
    except authority.AuthorityError as error:
        raise FreezeError(
            f"cannot resolve immutable C3 authorization: {error}"
        ) from error
    if _sha256(blob.data) != development.get("development_authorization_anchor_sha256"):
        raise FreezeError("C4 development authorization digest differs")
    document = _strict_object(blob.data, "C3 development authorization")
    _validate_schema(
        document,
        "development-authorization-anchor.schema.json",
        "C3 development authorization",
    )
    c2_commit = document["c2_source_commit"]
    try:
        if context.repository.commit_parents(development_commit) != (c2_commit,):
            raise FreezeError("C3 authorization is not the exact C2 child")
    except authority.AuthorityError as error:
        raise FreezeError(f"cannot verify immutable C2 ancestry: {error}") from error
    return cast(str, c2_commit)


def _verify_locked_runtime(
    context: FreezeContext, runtime_records: Sequence[Mapping[str, Any]]
) -> None:
    c2_commit = _locked_c2_commit(context)
    for record in runtime_records:
        relative = cast(str, record["path"])
        try:
            c2_blob = context.repository.blob_at(c2_commit, relative)
            head_blob = context.repository.blob_at(context.head, relative)
        except authority.AuthorityError as error:
            raise FreezeError(
                f"locked C2 runtime source is unavailable: {error}"
            ) from error
        if (
            c2_blob.mode != "100644"
            or head_blob.mode != "100644"
            or c2_blob.oid != head_blob.oid
            or _sha256(c2_blob.data) != record["sha256"]
            or len(c2_blob.data) != record["byte_length"]
        ):
            raise FreezeError(f"runtime source changed since C2: {relative}")


def _build_document(
    context: FreezeContext,
    *,
    local_options_sha256: str,
    runtime_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    allowed_sources = [
        {"path": record["path"], "sha256": record["sha256"]}
        for record in runtime_records
    ]
    if [record["path"] for record in allowed_sources] != list(RUNTIME_SOURCE_PATHS):
        raise FreezeError("candidate runtime source set/order differs")
    candidate_files = context.stage_input.candidate_files
    allowed_artifacts = [
        {"path": f"candidate/{relative}", "sha256": record.sha256}
        for relative, record in sorted(candidate_files.items())
    ]
    if not allowed_artifacts:
        raise FreezeError("stage input exposes no candidate artifacts")
    runner_matches = [
        record for record in allowed_sources if record["path"] == RUNNER_SOURCE_PATH
    ]
    if len(runner_matches) != 1:
        raise FreezeError("runtime set has no unique candidate runner")
    document = {
        "schema_version": LOCK_SCHEMA,
        "card_sha256": CARD_SHA256,
        "stage": context.stage,
        "candidate_input_sha256": context.stage_input.candidate_input_sha256,
        "local_options_sha256": local_options_sha256,
        "stage_input_anchor_sha256": context.stage_input.anchor_file.sha256,
        "stage_input_anchor_commit": context.stage_input.anchor_commit,
        "runner_source_path": RUNNER_SOURCE_PATH,
        "runner_source_sha256": runner_matches[0]["sha256"],
        "source_manifest_sha256": _sha256(canonical_bytes(allowed_sources)),
        "allowed_sources": allowed_sources,
        "allowed_candidate_artifacts": allowed_artifacts,
    }
    _validate_schema(
        document,
        "candidate-execution-lock.schema.json",
        "candidate execution lock",
    )
    return document


def _claim_identity(info: os.stat_result) -> ClaimIdentity:
    return ClaimIdentity(
        device=info.st_dev,
        inode=info.st_ino,
        creation_nanoseconds=info.st_ctime_ns,
    )


def _verify_empty_claim(relative: str) -> ClaimIdentity:
    path = _path(relative)
    try:
        info = path.lstat()
    except OSError as error:
        raise FreezeError(
            f"durable execution-lock claim is unavailable: {error}"
        ) from error
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(info, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or attributes & reparse
        or info.st_nlink != 1
        or info.st_size != 0
    ):
        raise FreezeError(
            "execution-lock claim must be the exact regular, empty, single-link file"
        )
    return _claim_identity(info)


def _write_claimed(
    relative: str,
    document: Mapping[str, Any],
    expected_identity: ClaimIdentity,
) -> None:
    payload = canonical_bytes(document)
    path = _path(relative)
    if _verify_empty_claim(relative) != expected_identity:
        raise FreezeError("execution-lock claim identity changed before final write")
    flags = os.O_WRONLY
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise FreezeError(
            f"cannot open durable execution-lock claim: {error}"
        ) from error
    try:
        descriptor_info = os.fstat(descriptor)
        if (
            _claim_identity(descriptor_info) != expected_identity
            or descriptor_info.st_nlink != 1
            or descriptor_info.st_size != 0
            or _verify_empty_claim(relative) != expected_identity
        ):
            raise FreezeError("execution-lock claim changed while being opened")
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise FreezeError("short write while freezing execution lock")
            view = view[written:]
        os.fsync(descriptor)
        written_info = os.fstat(descriptor)
        try:
            path_info = path.lstat()
        except OSError as error:
            raise FreezeError(
                f"execution-lock claim disappeared after write: {error}"
            ) from error
        if (
            written_info.st_dev != expected_identity.device
            or written_info.st_ino != expected_identity.inode
            or path_info.st_dev != expected_identity.device
            or path_info.st_ino != expected_identity.inode
            or written_info.st_nlink != 1
            or path_info.st_nlink != 1
            or written_info.st_size != len(payload)
            or path_info.st_size != len(payload)
        ):
            raise FreezeError(
                "execution-lock claim identity changed during final write"
            )
    finally:
        os.close(descriptor)
    if os.name != "nt":
        parent_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    if path.read_bytes() != payload:
        raise FreezeError("execution-lock bytes differ after claimed-file write")


def freeze(stage: Stage, *, claim_already_created: bool) -> Path:
    """Validate one formal stage and fill the launcher's durable claim."""

    if claim_already_created is not True:
        raise FreezeError("execution-lock helper requires a prior durable claim")
    output = _output_path(stage)
    claim_identity = _verify_empty_claim(output)
    try:
        environment_contract.verify_frozen_environment()
    except environment_contract.MaterializationError as error:
        raise FreezeError(f"frozen environment verification failed: {error}") from error
    _verify_formal_python()
    if (
        len(sys.argv) != 2
        or sys.argv[1] != stage
        or Path(sys.argv[0]).resolve()
        != (SOURCE_ROOT / "launch_execution_lock.py").resolve()
    ):
        raise FreezeError("execution-lock helper may only run through its launcher")
    git = _environment_lock_git()
    head = _git_text(git, "rev-parse", "HEAD")
    repository = authority.GitObjectRepository(REPOSITORY_ROOT, git)
    _validate_repository_state(stage, git, repository, head)
    context = _resolve_context(stage, git, head)
    local_options_sha256 = _verify_c0_bindings(context)
    runtime_records = _file_records(RUNTIME_SOURCE_PATHS)
    if stage == "development":
        test_records = _file_records(TEST_SOURCE_PATHS)
        _validate_default_equivalence(
            context,
            local_options_sha256=local_options_sha256,
            runtime_records=runtime_records,
            test_records=test_records,
        )
    else:
        _verify_locked_runtime(context, runtime_records)
    document = _build_document(
        context,
        local_options_sha256=local_options_sha256,
        runtime_records=runtime_records,
    )
    final_runtime_records = _file_records(RUNTIME_SOURCE_PATHS)
    if final_runtime_records != runtime_records:
        raise FreezeError("runtime source bytes changed during execution-lock freeze")
    if stage == "development":
        final_test_records = _file_records(TEST_SOURCE_PATHS)
        if final_test_records != test_records:
            raise FreezeError("test source bytes changed during execution-lock freeze")
        _validate_default_equivalence(
            context,
            local_options_sha256=local_options_sha256,
            runtime_records=final_runtime_records,
            test_records=final_test_records,
        )
    else:
        _verify_locked_runtime(context, final_runtime_records)
    _validate_repository_state(stage, git, context.repository, head)
    _write_claimed(output, document, claim_identity)
    return _path(output)


def _verify_formal_python() -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode is not True
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
    ):
        raise FreezeError(
            "formal invocation requires `python -I -B -S` without optimization"
        )
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise FreezeError("formal invocation must run from the repository root")


def main() -> int:
    raise FreezeError("direct execution is prohibited; use launch_execution_lock.py")


if __name__ == "__main__":
    raise SystemExit(main())
