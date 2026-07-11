"""C0 observer for independent C2 default-equivalence executions.

The pure-stdlib launcher creates the irreversible evidence claim before this
module is imported.  For each fixed C0 fixture this observer materializes a
baseline Julia capsule exclusively from the immutable C0 Git tree, then runs a
reference child and a mechanism-disabled child in separate fresh
AppContainers.  Children receive no golden bytes and emit only their observed
canonical stdout.  This C0 observer alone performs every byte comparison.
The same observer also runs the future C2 Julia test file directly with the
pinned Julia executable in a fifth fresh AppContainer.  The test receives only
the root Julia project/manifest, the exact Base/Core/Geometry package sources,
the pinned runtime/depot package data, and its own source.  Consequently the
formal protocol never executes the test later as an ambient host process.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final


sys.dont_write_bytecode = True


SOURCE_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = SOURCE_ROOT.parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
for _import_root in (PYTHON_SOURCE, SOURCE_ROOT):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

import durable_io  # noqa: E402
import freeze_execution_lock as contract  # noqa: E402
import sandbox_broker  # noqa: E402


FIXTURE_IDS: Final = contract.COMPARISON_FIXTURE_IDS
FIXTURE_PATHS: Final = (
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-fixtures/"
    "julia-core-default.json",
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-fixtures/"
    "opaque-plugin-default.json",
)
GOLDEN_PATHS: Final = (
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-golden/"
    "julia-core-default.stdout.json",
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-golden/"
    "opaque-plugin-default.stdout.json",
)
CHILD_SOURCE_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/source/c2_equivalence_child.jl"
)
PLUGIN_SOURCE_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/source/Local3FixturePlugin.jl"
)
C2_RUNTIME_SOURCE_PATHS: Final = (
    "julia/GeoTargetCore/src/local_model_transform.jl",
    "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl",
)
C2_TEST_SOURCE_PATHS: Final = (
    "julia/GeoTargetCore/test/test_local_model_transform.jl",
)
MECHANISM_SOURCE_PATH: Final = C2_RUNTIME_SOURCE_PATHS[0]
C0_PROTOCOL_PATHS: Final = (
    PLUGIN_SOURCE_PATH,
    "research/experiments/EXP-LOCAL-003/source/c2-default-equivalence.schema.json",
    *FIXTURE_PATHS,
    *GOLDEN_PATHS,
    CHILD_SOURCE_PATH,
    "research/experiments/EXP-LOCAL-003/source/sandbox_broker.py",
)
DIRTY_PATHS: Final = frozenset(
    (
        *C2_RUNTIME_SOURCE_PATHS,
        *C2_TEST_SOURCE_PATHS,
        contract.DEFAULT_EQUIVALENCE_PATH,
    )
)
CAPSULE_PACKAGES: Final = (
    "julia/GeoTargetBase",
    "julia/GeoTargetCore",
    "julia/GeoTargetGeometry",
)
TEST_PACKAGE_GRANT_PATHS: Final = tuple(
    path
    for package in CAPSULE_PACKAGES
    for path in (f"{package}/Project.toml", f"{package}/src")
)
TEST_PROJECT_GRANT_PATHS: Final = (
    "julia/Project.toml",
    "julia/Manifest.toml",
)
CHILD_TIMEOUT_SECONDS: Final = 600.0
CHILD_OUTPUT_LIMIT: Final = 4 * 1024 * 1024
OBSERVATION_SCHEMA: Final = "geotarget.exp-local-003.c2-equivalence-observation/v1"
C1_CANDIDATE_OUTCOME_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/development-candidate-inputs"
)
C1_STAGE_VAULT_ANCHOR_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/C1_STAGE_VAULT_ANCHOR.json"
)
C1_ATTEMPT_CLAIM_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/C1_ATTEMPT_CLAIM.json"
)


def _c1_external_denied_roots() -> tuple[Path, ...]:
    """Rebase every fixed C1 external namespace onto this repository root."""

    environment = contract.environment_contract
    return (
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-vault")
        / contract.EXPERIMENT_ID
        / environment.VAULT_OUTPUT_PATH.name,
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-private-audit")
        / contract.EXPERIMENT_ID
        / environment.PRIVATE_VAULT_OUTPUT_PATH.name,
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-run-evidence")
        / contract.EXPERIMENT_ID,
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-assessment-evidence")
        / contract.EXPERIMENT_ID,
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-sandbox-scratch")
        / contract.EXPERIMENT_ID,
    )


class CaptureError(RuntimeError):
    """The irreversible C2 capture attempt failed closed."""


@dataclass(frozen=True, slots=True)
class FixtureSpec:
    fixture_id: str
    fixture_path: str
    golden_path: str


@dataclass(frozen=True, slots=True)
class RuntimeAuthority:
    executable: Path
    runtime_root: Path
    depot_root: Path
    base_environment: tuple[tuple[str, str], ...]
    depot_grants: tuple[sandbox_broker.ReadGrant, ...]


@dataclass(frozen=True, slots=True)
class CapsuleAuthority:
    root: Path
    files: tuple[dict[str, Any], ...]
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class Observation:
    fixture: FixtureSpec
    mode: str
    result: sandbox_broker.SandboxResult


@dataclass(frozen=True, slots=True)
class IsolatedTestObservation:
    request: sandbox_broker.SandboxRequest
    result: sandbox_broker.SandboxResult


FIXTURES: Final = tuple(
    FixtureSpec(*values)
    for values in zip(FIXTURE_IDS, FIXTURE_PATHS, GOLDEN_PATHS, strict=True)
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _path(relative: str) -> Path:
    return REPOSITORY_ROOT.joinpath(*relative.split("/"))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _record(relative: str, payload: bytes) -> dict[str, Any]:
    if not payload:
        raise CaptureError(f"equivalence authority file is empty: {relative}")
    return {
        "path": relative,
        "sha256": _sha256(payload),
        "byte_length": len(payload),
    }


def _git_records(
    repository: contract.authority.GitObjectRepository,
    commit: str,
    paths: Sequence[str],
) -> tuple[dict[str, Any], ...]:
    if tuple(paths) != tuple(sorted(paths)) or len(paths) != len(set(paths)):
        raise CaptureError("Git authority paths must be sorted and unique")
    records: list[dict[str, Any]] = []
    for relative in paths:
        try:
            blob = repository.blob_at(commit, relative)
        except contract.authority.AuthorityError as error:
            raise CaptureError(
                f"cannot read C0 authority blob {relative}: {error}"
            ) from error
        if blob.mode != "100644":
            raise CaptureError(f"C0 authority is not a regular Git blob: {relative}")
        records.append(_record(relative, blob.data))
    return tuple(records)


def _working_records(paths: Sequence[str]) -> tuple[dict[str, Any], ...]:
    return tuple(contract._file_records(tuple(paths)))


def _validate_repository_state(
    git: contract.authority.GitExecutable,
    repository: contract.authority.GitObjectRepository,
    head: str,
) -> None:
    top = Path(contract._git_text(git, "rev-parse", "--show-toplevel")).resolve()
    if top != REPOSITORY_ROOT.resolve():
        raise CaptureError("C2 capture is not running at repository root")
    if contract._git_text(git, "branch", "--show-current") != "main":
        raise CaptureError("C2 equivalence capture must run directly on main")
    if contract._git_text(git, "rev-parse", "HEAD") != head:
        raise CaptureError("repository HEAD changed during C2 equivalence capture")
    status = contract._status_entries(
        contract._git_bytes(
            git, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
    )
    if set(status) != DIRTY_PATHS or any(code != "??" for code in status.values()):
        raise CaptureError(
            "C2 capture requires exactly runtime2, test1, and the evidence claim"
        )
    index = repository.tree_index(head)
    if any(path in index for path in DIRTY_PATHS):
        raise CaptureError("a C2 capture path already exists in immutable C1 HEAD")


def _result_blind_binding(
    git: contract.authority.GitExecutable,
    repository: contract.authority.GitObjectRepository,
    head: str,
) -> contract.authority.ResultBlindStageBinding:
    try:
        anchor = repository.blob_at(head, contract.DEVELOPMENT_ANCHOR_PATH)
        return contract.authority.resolve_result_blind_stage_binding(
            anchor_repository=REPOSITORY_ROOT,
            anchor_commit=head,
            anchor_path=contract.DEVELOPMENT_ANCHOR_PATH,
            anchor_sha256=_sha256(anchor.data),
            git_executable=git,
        )
    except contract.authority.AuthorityError as error:
        raise CaptureError(f"result-blind C1 binding failed: {error}") from error


def _verify_c0_bindings(
    binding: contract.authority.ResultBlindStageBinding,
) -> tuple[str, bytes]:
    environment = contract._read_regular(contract.ENVIRONMENT_LOCK_PATH)
    if _sha256(environment) != binding.environment_lock_sha256:
        raise CaptureError("live environment lock differs from immutable C0 authority")
    local_options_sha256 = contract._verify_local_options()
    if local_options_sha256 != binding.local_options_sha256:
        raise CaptureError("live local options differ from immutable C0 authority")
    return local_options_sha256, environment


def _verify_live_c0_protocol(
    repository: contract.authority.GitObjectRepository,
    binding: contract.authority.ResultBlindStageBinding,
) -> tuple[dict[str, Any], ...]:
    paths = tuple(sorted(C0_PROTOCOL_PATHS))
    records = _git_records(repository, binding.c0_source_commit, paths)
    for record in records:
        payload = contract._read_regular(record["path"])
        if (
            _sha256(payload) != record["sha256"]
            or len(payload) != record["byte_length"]
        ):
            raise CaptureError(f"live C0 protocol differs from Git: {record['path']}")
    return records


def _runtime_authority(environment_lock_bytes: bytes) -> RuntimeAuthority:
    document = contract._strict_object(environment_lock_bytes, "C0 environment lock")
    julia = document.get("julia")
    execution = document.get("execution")
    if not isinstance(julia, dict) or not isinstance(execution, dict):
        raise CaptureError("environment lock Julia authority is malformed")
    executable_value = julia.get("runtime_executable")
    runtime_tree = julia.get("runtime_tree")
    depot_tree = julia.get("depot_tree")
    locked_environment = execution.get("julia_environment")
    if (
        not isinstance(executable_value, str)
        or not isinstance(runtime_tree, dict)
        or not isinstance(depot_tree, dict)
        or not isinstance(locked_environment, dict)
    ):
        raise CaptureError("environment lock runtime/tree/environment is malformed")
    executable = Path(executable_value)
    runtime_root_value = runtime_tree.get("root")
    depot_root_value = depot_tree.get("root")
    if not isinstance(runtime_root_value, str) or not isinstance(depot_root_value, str):
        raise CaptureError("environment lock Julia roots are malformed")
    runtime_root = Path(runtime_root_value)
    depot_root = Path(depot_root_value)
    try:
        if (
            not executable.is_file()
            or _sha256(executable.read_bytes()) != julia.get("runtime_sha256")
            or executable.parent.parent.resolve() != runtime_root.resolve()
            or not depot_root.is_dir()
        ):
            raise CaptureError("pinned Julia runtime/depot identity differs")
    except OSError as error:
        raise CaptureError(f"cannot verify pinned Julia runtime: {error}") from error

    allowed_keys = (
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
    environment: list[tuple[str, str]] = []
    for key in allowed_keys:
        value = locked_environment.get(key)
        if not isinstance(value, str):
            raise CaptureError(f"locked Julia environment field is absent: {key}")
        environment.append((key, value))
    if execution.get("julia_depot_path") != str(depot_root):
        raise CaptureError("locked Julia depot path differs")
    environment.extend(
        (
            ("JULIA_DEPOT_PATH", str(depot_root)),
            ("JULIA_PKG_PRECOMPILE_AUTO", "0"),
        )
    )
    folded = [key.casefold() for key, _ in environment]
    if len(folded) != len(set(folded)):
        raise CaptureError("child environment contains duplicate names")

    grants: list[sandbox_broker.ReadGrant] = [
        sandbox_broker.ReadGrant(depot_root, recursive=False)
    ]
    for name in ("packages", "artifacts"):
        child = depot_root / name
        if not child.is_dir():
            raise CaptureError(f"pinned Julia depot is missing {name} authority")
        grants.append(sandbox_broker.ReadGrant(child, recursive=True))
    return RuntimeAuthority(
        executable=executable,
        runtime_root=runtime_root,
        depot_root=depot_root,
        base_environment=tuple(
            sorted(environment, key=lambda item: item[0].casefold())
        ),
        depot_grants=tuple(grants),
    )


def _capsule_source_paths(
    repository: contract.authority.GitObjectRepository,
    c0_source_commit: str,
) -> tuple[str, ...]:
    index = repository.tree_index(c0_source_commit)
    selected: list[str] = []
    fixed = {
        "julia/Project.toml",
        "julia/Manifest.toml",
        PLUGIN_SOURCE_PATH,
        CHILD_SOURCE_PATH,
        *FIXTURE_PATHS,
    }
    for relative, (mode, _oid) in index.items():
        package_source = any(
            relative == f"{package}/Project.toml"
            or relative.startswith(f"{package}/src/")
            for package in CAPSULE_PACKAGES
        )
        if relative in fixed or package_source:
            if mode != "100644":
                raise CaptureError(
                    f"baseline capsule path is not a regular blob: {relative}"
                )
            selected.append(relative)
    expected_fixed = fixed - set(selected)
    if expected_fixed:
        raise CaptureError(
            f"baseline capsule is missing C0 paths: {sorted(expected_fixed)}"
        )
    if MECHANISM_SOURCE_PATH in selected or MECHANISM_SOURCE_PATH in index:
        raise CaptureError("C2 mechanism exists in the C0 baseline source tree")
    return tuple(sorted(selected))


def _materialize_capsule(
    repository: contract.authority.GitObjectRepository,
    binding: contract.authority.ResultBlindStageBinding,
    root: Path,
) -> CapsuleAuthority:
    capsule = root / "immutable-c0-baseline-capsule"
    capsule.mkdir()
    records: list[dict[str, Any]] = []
    for relative in _capsule_source_paths(repository, binding.c0_source_commit):
        blob = repository.blob_at(binding.c0_source_commit, relative)
        destination = capsule.joinpath(*relative.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        durable_io.exclusive_write(destination, blob.data)
        records.append(_record(relative, blob.data))
    manifest = tuple(records)
    return CapsuleAuthority(
        root=capsule,
        files=manifest,
        manifest_sha256=_sha256(contract.canonical_bytes(list(manifest))),
    )


def _verify_capsule(capsule: CapsuleAuthority) -> None:
    observed: list[dict[str, Any]] = []
    for record in capsule.files:
        relative = record["path"]
        path = capsule.root.joinpath(*relative.split("/"))
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise CaptureError(
                f"cannot reread baseline capsule {relative}: {error}"
            ) from error
        observed.append(_record(relative, payload))
    if tuple(observed) != capsule.files:
        raise CaptureError("baseline capsule bytes changed during child execution")
    if _sha256(contract.canonical_bytes(observed)) != capsule.manifest_sha256:
        raise CaptureError("baseline capsule manifest changed during child execution")


def _validate_observed(payload: bytes, fixture_id: str, context: str) -> None:
    if not payload.endswith(b"\n") or payload.endswith(b"\n\n"):
        raise CaptureError(f"{context} is not one canonical JSON line")
    body = payload[:-1]
    try:
        document = contract.authority.strict_jcs_bytes(body, context=context)
    except contract.authority.AuthorityError as error:
        raise CaptureError(f"invalid {context}: {error}") from error
    expected_keys = {
        "schema_version",
        "fixture_id",
        "problem_hash",
        "compiled_cache_key",
        "compile_stats",
        "default_options",
        "canonical_validation_tolerance_bits",
        "initial_observation",
        "attempt",
        "canonical_validation",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise CaptureError(f"{context} observation object is not closed")
    validation = document.get("canonical_validation")
    attempt = document.get("attempt")
    if (
        document["schema_version"] != OBSERVATION_SCHEMA
        or document["fixture_id"] != fixture_id
        or not isinstance(attempt, dict)
        or attempt.get("accepted") is not True
        or not isinstance(validation, dict)
        or validation.get("accepted") is not True
        or validation.get("failure") != "CANDIDATE_VALIDATION_NONE"
    ):
        raise CaptureError(f"{context} did not complete accepted solve/validation")


def _child_environment(
    runtime: RuntimeAuthority, capsule: CapsuleAuthority
) -> tuple[tuple[str, str], ...]:
    environment = dict(runtime.base_environment)
    environment["JULIA_PROJECT"] = str(capsule.root / "julia")
    return tuple(sorted(environment.items(), key=lambda item: item[0].casefold()))


def _child_command(
    runtime: RuntimeAuthority,
    capsule: CapsuleAuthority,
    fixture: FixtureSpec,
    mode: str,
) -> tuple[str, ...]:
    command = (
        str(runtime.executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={capsule.root / 'julia'}",
        str(capsule.root.joinpath(*CHILD_SOURCE_PATH.split("/"))),
        mode,
        str(capsule.root.joinpath(*fixture.fixture_path.split("/"))),
        str(capsule.root.joinpath(*PLUGIN_SOURCE_PATH.split("/"))),
    )
    if mode == "mechanism-disabled":
        return (*command, str(_path(MECHANISM_SOURCE_PATH)))
    if mode != "reference":
        raise CaptureError(f"unknown equivalence child mode: {mode}")
    return command


def _isolated_test_environment(
    runtime: RuntimeAuthority,
) -> tuple[tuple[str, str], ...]:
    environment = dict(runtime.base_environment)
    environment["JULIA_PROJECT"] = str(REPOSITORY_ROOT / "julia")
    return tuple(sorted(environment.items(), key=lambda item: item[0].casefold()))


def _isolated_test_command(runtime: RuntimeAuthority) -> tuple[str, ...]:
    return (
        str(runtime.executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={REPOSITORY_ROOT / 'julia'}",
        str(_path(C2_TEST_SOURCE_PATHS[0])),
    )


def _isolated_test_grants(
    runtime: RuntimeAuthority,
) -> tuple[sandbox_broker.ReadGrant, ...]:
    """Return the closed, non-overlapping C2 Julia-test read authority."""

    grants: list[sandbox_broker.ReadGrant] = [
        sandbox_broker.ReadGrant(runtime.runtime_root, recursive=True),
        *runtime.depot_grants,
    ]
    project_root = _path("julia")
    if not REPOSITORY_ROOT.is_dir() or not project_root.is_dir():
        raise CaptureError("isolated-test Julia project discovery path is absent")
    grants.extend(
        (
            sandbox_broker.ReadGrant(REPOSITORY_ROOT, recursive=False),
            sandbox_broker.ReadGrant(project_root, recursive=False),
        )
    )
    for relative in TEST_PROJECT_GRANT_PATHS:
        path = _path(relative)
        if not path.is_file():
            raise CaptureError(f"isolated-test project authority is absent: {relative}")
        grants.append(sandbox_broker.ReadGrant(path, recursive=False))
    for relative in TEST_PACKAGE_GRANT_PATHS:
        path = _path(relative)
        recursive = relative.endswith("/src")
        if (recursive and not path.is_dir()) or (not recursive and not path.is_file()):
            raise CaptureError(f"isolated-test package authority is absent: {relative}")
        grants.append(sandbox_broker.ReadGrant(path, recursive=recursive))
    test_source = _path(C2_TEST_SOURCE_PATHS[0])
    if not test_source.is_file():
        raise CaptureError("isolated-test source is absent")
    grants.append(sandbox_broker.ReadGrant(test_source, recursive=False))
    return tuple(grants)


def _isolated_test_probes() -> tuple[sandbox_broker.AccessProbe, ...]:
    mechanism = _path(MECHANISM_SOURCE_PATH)
    test_source = _path(C2_TEST_SOURCE_PATHS[0])
    return (
        sandbox_broker.AccessProbe(test_source, sandbox_broker.PathProbeStatus.ALLOWED),
        sandbox_broker.AccessProbe(mechanism, sandbox_broker.PathProbeStatus.ALLOWED),
        sandbox_broker.AccessProbe(
            EXPERIMENT_ROOT, sandbox_broker.PathProbeStatus.DENIED
        ),
        sandbox_broker.AccessProbe(
            _path(contract.DEFAULT_EQUIVALENCE_PATH),
            sandbox_broker.PathProbeStatus.DENIED,
        ),
        sandbox_broker.AccessProbe(
            _path(C1_CANDIDATE_OUTCOME_PATH),
            sandbox_broker.PathProbeStatus.DENIED,
        ),
        sandbox_broker.AccessProbe(
            _path(C1_STAGE_VAULT_ANCHOR_PATH),
            sandbox_broker.PathProbeStatus.DENIED,
        ),
        sandbox_broker.AccessProbe(
            _path(C1_ATTEMPT_CLAIM_PATH), sandbox_broker.PathProbeStatus.DENIED
        ),
        *(
            sandbox_broker.AccessProbe(root, sandbox_broker.PathProbeStatus.DENIED)
            for root in _c1_external_denied_roots()
        ),
        sandbox_broker.AccessProbe(
            REPOSITORY_ROOT / ".git", sandbox_broker.PathProbeStatus.DENIED
        ),
    )


def _validate_sandbox_completion(
    request: sandbox_broker.SandboxRequest,
    read_identity: sandbox_broker.ReadIdentityManifest,
    result: sandbox_broker.SandboxResult,
    *,
    context: str,
    require_nonempty_stdout: bool,
) -> None:
    attestation = result.attestation
    denied_probe_count = sum(
        probe.expected is sandbox_broker.PathProbeStatus.DENIED
        for probe in request.access_probes
    )
    try:
        Path(attestation.profile_storage_path).lstat()
    except FileNotFoundError:
        profile_storage_absent = True
    except OSError as error:
        raise CaptureError(
            f"cannot verify deleted AppContainer profile storage: {error}"
        ) from error
    else:
        profile_storage_absent = False
    if (
        result.command != request.command
        or result.return_code != 0
        or result.termination_reason is not sandbox_broker.TerminationReason.COMPLETED
        or result.stderr != b""
        or (require_nonempty_stdout and not result.stdout)
        or result.preexit is not None
        or result.total_processes != 1
        or result.terminated_processes != 0
        or attestation.claim_reference != request.claim_reference
        or attestation.allowed_read_paths
        != tuple(str(grant.path) for grant in request.allowed_read)
        or attestation.read_identity_manifest_sha256 != read_identity.sha256
        or attestation.read_identity_manifest_entry_count != read_identity.entry_count
        or attestation.read_identity_manifest_entry_count
        != attestation.read_only_probe_entry_count
        or attestation.scratch_directory != str(request.scratch_directory)
        or attestation.capabilities != ()
        or not attestation.token_is_appcontainer
        or not attestation.token_appcontainer_sid_verified
        or attestation.token_elevated
        or attestation.token_capability_count != 0
        or attestation.max_processes != 1
        or not attestation.child_process_restricted
        or not attestation.job_assigned_at_creation
        or not attestation.job_membership_verified
        or attestation.breakaway_allowed
        or not attestation.kill_on_job_close
        or not attestation.job_empty
        or attestation.denied_probe_entry_count < denied_probe_count
        or not _is_sha256(attestation.denied_probe_manifest_sha256)
        or attestation.read_only_probe_entry_count < 1
        or not _is_sha256(attestation.read_only_probe_manifest_sha256)
        or not _is_sha256(attestation.scratch_access_probe_manifest_sha256)
        or attestation.acl_entry_count != attestation.read_only_probe_entry_count + 1
        or attestation.original_acl_manifest_sha256
        != attestation.restored_acl_manifest_sha256
        or not attestation.acl_exactly_restored
        or not attestation.scratch_emptied
        or not attestation.profile_deleted
        or not attestation.profile_storage_deleted
        or not profile_storage_absent
    ):
        raise CaptureError(f"{context} did not close cleanly")
    observed_probe_bindings = tuple(
        (item.path, item.expected, item.observed, item.winerror)
        for item in attestation.access_probes
    )
    expected_probe_bindings = tuple(
        (
            str(probe.path),
            probe.expected,
            probe.expected,
            0 if probe.expected is sandbox_broker.PathProbeStatus.ALLOWED else 5,
        )
        for probe in request.access_probes
    )
    if observed_probe_bindings != expected_probe_bindings:
        raise CaptureError(f"{context} ACL probes differ")


def _run_isolated_test(
    runtime: RuntimeAuthority,
    scratch: Path,
    claim_reference: str,
) -> IsolatedTestObservation:
    scratch.mkdir()
    allowed_read = _isolated_test_grants(runtime)
    read_identity = sandbox_broker.capture_read_identity_manifest(
        executable=runtime.executable,
        allowed_read=allowed_read,
    )
    request = sandbox_broker.SandboxRequest(
        command=_isolated_test_command(runtime),
        allowed_read=allowed_read,
        scratch_directory=scratch,
        claim_reference=claim_reference,
        expected_read_identity_manifest_sha256=read_identity.sha256,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        stdout_limit_bytes=CHILD_OUTPUT_LIMIT,
        stderr_limit_bytes=CHILD_OUTPUT_LIMIT,
        max_processes=1,
        environment=_isolated_test_environment(runtime),
        access_probes=_isolated_test_probes(),
    )
    try:
        result = sandbox_broker.run_sandboxed(request)
    except sandbox_broker.SandboxError as error:
        raise CaptureError(f"isolated C2 Julia test sandbox failed: {error}") from error
    _validate_sandbox_completion(
        request,
        read_identity,
        result,
        context="isolated C2 Julia test",
        require_nonempty_stdout=False,
    )
    return IsolatedTestObservation(request, result)


def _run_observation(
    runtime: RuntimeAuthority,
    capsule: CapsuleAuthority,
    fixture: FixtureSpec,
    mode: str,
    scratch: Path,
    claim_reference: str,
) -> Observation:
    scratch.mkdir()
    fixture_path = capsule.root.joinpath(*fixture.fixture_path.split("/"))
    golden_path = _path(fixture.golden_path)
    mechanism_path = _path(MECHANISM_SOURCE_PATH)
    grants = [
        sandbox_broker.ReadGrant(runtime.runtime_root, recursive=True),
        *runtime.depot_grants,
        sandbox_broker.ReadGrant(capsule.root, recursive=True),
    ]
    probes = [
        sandbox_broker.AccessProbe(
            fixture_path, sandbox_broker.PathProbeStatus.ALLOWED
        ),
        sandbox_broker.AccessProbe(golden_path, sandbox_broker.PathProbeStatus.DENIED),
    ]
    if mode == "reference":
        probes.append(
            sandbox_broker.AccessProbe(
                mechanism_path, sandbox_broker.PathProbeStatus.DENIED
            )
        )
    elif mode == "mechanism-disabled":
        grants.append(sandbox_broker.ReadGrant(mechanism_path, recursive=False))
        probes.append(
            sandbox_broker.AccessProbe(
                mechanism_path, sandbox_broker.PathProbeStatus.ALLOWED
            )
        )
    else:
        raise CaptureError(f"unknown equivalence child mode: {mode}")
    # The final evidence file is the launcher's live, irreversible claim.
    # Neither it nor its parent outcome namespace may be read or mutated by
    # any untrusted equivalence child, even through ambient package ACLs.
    probes.extend(
        (
            sandbox_broker.AccessProbe(
                EXPERIMENT_ROOT, sandbox_broker.PathProbeStatus.DENIED
            ),
            sandbox_broker.AccessProbe(
                _path(contract.DEFAULT_EQUIVALENCE_PATH),
                sandbox_broker.PathProbeStatus.DENIED,
            ),
            sandbox_broker.AccessProbe(
                _path(C1_CANDIDATE_OUTCOME_PATH),
                sandbox_broker.PathProbeStatus.DENIED,
            ),
            sandbox_broker.AccessProbe(
                _path(C1_STAGE_VAULT_ANCHOR_PATH),
                sandbox_broker.PathProbeStatus.DENIED,
            ),
            sandbox_broker.AccessProbe(
                _path(C1_ATTEMPT_CLAIM_PATH),
                sandbox_broker.PathProbeStatus.DENIED,
            ),
            *(
                sandbox_broker.AccessProbe(root, sandbox_broker.PathProbeStatus.DENIED)
                for root in _c1_external_denied_roots()
            ),
            sandbox_broker.AccessProbe(
                REPOSITORY_ROOT / ".git",
                sandbox_broker.PathProbeStatus.DENIED,
            ),
        )
    )
    allowed_read = tuple(grants)
    read_identity = sandbox_broker.capture_read_identity_manifest(
        executable=runtime.executable,
        allowed_read=allowed_read,
    )
    request = sandbox_broker.SandboxRequest(
        command=_child_command(runtime, capsule, fixture, mode),
        allowed_read=allowed_read,
        scratch_directory=scratch,
        claim_reference=claim_reference,
        expected_read_identity_manifest_sha256=read_identity.sha256,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        stdout_limit_bytes=CHILD_OUTPUT_LIMIT,
        stderr_limit_bytes=CHILD_OUTPUT_LIMIT,
        max_processes=1,
        environment=_child_environment(runtime, capsule),
        access_probes=tuple(probes),
    )
    try:
        result = sandbox_broker.run_sandboxed(request)
    except sandbox_broker.SandboxError as error:
        raise CaptureError(
            f"{fixture.fixture_id} {mode} sandbox failed: {error}"
        ) from error
    attestation = result.attestation
    denied_probe_count = sum(
        probe.expected is sandbox_broker.PathProbeStatus.DENIED
        for probe in request.access_probes
    )
    try:
        Path(attestation.profile_storage_path).lstat()
    except FileNotFoundError:
        profile_storage_absent = True
    except OSError as error:
        raise CaptureError(
            f"cannot verify deleted AppContainer profile storage: {error}"
        ) from error
    else:
        profile_storage_absent = False
    if (
        result.command != request.command
        or result.return_code != 0
        or result.termination_reason is not sandbox_broker.TerminationReason.COMPLETED
        or result.stderr != b""
        or result.preexit is not None
        or result.total_processes != 1
        or result.terminated_processes != 0
        or attestation.claim_reference != claim_reference
        or attestation.allowed_read_paths
        != tuple(str(grant.path) for grant in request.allowed_read)
        or attestation.read_identity_manifest_sha256 != read_identity.sha256
        or attestation.read_identity_manifest_entry_count != read_identity.entry_count
        or attestation.read_identity_manifest_entry_count
        != attestation.read_only_probe_entry_count
        or attestation.scratch_directory != str(scratch)
        or attestation.capabilities != ()
        or not attestation.token_is_appcontainer
        or not attestation.token_appcontainer_sid_verified
        or attestation.token_elevated
        or attestation.token_capability_count != 0
        or attestation.max_processes != 1
        or not attestation.child_process_restricted
        or not attestation.job_assigned_at_creation
        or not attestation.job_membership_verified
        or attestation.breakaway_allowed
        or not attestation.kill_on_job_close
        or not attestation.job_empty
        or attestation.denied_probe_entry_count < denied_probe_count
        or not _is_sha256(attestation.denied_probe_manifest_sha256)
        or attestation.read_only_probe_entry_count < 1
        or not _is_sha256(attestation.read_only_probe_manifest_sha256)
        or not _is_sha256(attestation.scratch_access_probe_manifest_sha256)
        or attestation.acl_entry_count != attestation.read_only_probe_entry_count + 1
        or attestation.original_acl_manifest_sha256
        != attestation.restored_acl_manifest_sha256
        or not attestation.acl_exactly_restored
        or not attestation.scratch_emptied
        or not attestation.profile_deleted
        or not attestation.profile_storage_deleted
        or not profile_storage_absent
    ):
        raise CaptureError(f"{fixture.fixture_id} {mode} child did not close cleanly")
    _validate_observed(
        result.stdout, fixture.fixture_id, f"{fixture.fixture_id} {mode} stdout"
    )
    expected_probes = tuple(probe.expected for probe in request.access_probes)
    observed_probe_bindings = tuple(
        (item.path, item.expected, item.observed, item.winerror)
        for item in result.attestation.access_probes
    )
    expected_probe_bindings = tuple(
        (
            str(probe.path),
            probe.expected,
            expected,
            0 if expected is sandbox_broker.PathProbeStatus.ALLOWED else 5,
        )
        for probe, expected in zip(request.access_probes, expected_probes, strict=True)
    )
    if observed_probe_bindings != expected_probe_bindings:
        raise CaptureError(f"{fixture.fixture_id} {mode} ACL probes differ")
    return Observation(fixture, mode, result)


def _environment_record(environment: Sequence[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"name": key, "value": value} for key, value in environment]


def _attestation_record(
    attestation: sandbox_broker.SandboxAttestation,
) -> dict[str, Any]:
    return {
        "schema_version": attestation.schema_version,
        "claim_reference": attestation.claim_reference,
        "profile_name": attestation.profile_name,
        "package_sid": attestation.package_sid,
        "profile_storage_path": attestation.profile_storage_path,
        "capabilities": list(attestation.capabilities),
        "allowed_read_paths": list(attestation.allowed_read_paths),
        "read_identity_manifest_entry_count": (
            attestation.read_identity_manifest_entry_count
        ),
        "read_identity_manifest_sha256": attestation.read_identity_manifest_sha256,
        "scratch_directory": attestation.scratch_directory,
        "environment": _environment_record(attestation.environment),
        "inherited_handle_roles": list(attestation.inherited_handle_roles),
        "process_id": attestation.process_id,
        "token_is_appcontainer": attestation.token_is_appcontainer,
        "token_appcontainer_sid_verified": (
            attestation.token_appcontainer_sid_verified
        ),
        "token_integrity_rid": attestation.token_integrity_rid,
        "token_elevated": attestation.token_elevated,
        "token_capability_count": attestation.token_capability_count,
        "access_probes": [
            {
                "path": item.path,
                "expected": item.expected.value,
                "observed": item.observed.value,
                "winerror": item.winerror,
            }
            for item in attestation.access_probes
        ],
        "denied_probe_entry_count": attestation.denied_probe_entry_count,
        "denied_probe_manifest_sha256": (attestation.denied_probe_manifest_sha256),
        "read_only_probe_entry_count": attestation.read_only_probe_entry_count,
        "read_only_probe_manifest_sha256": (
            attestation.read_only_probe_manifest_sha256
        ),
        "scratch_access_probe_manifest_sha256": (
            attestation.scratch_access_probe_manifest_sha256
        ),
        "max_processes": attestation.max_processes,
        "child_process_restricted": attestation.child_process_restricted,
        "job_assigned_at_creation": attestation.job_assigned_at_creation,
        "job_membership_verified": attestation.job_membership_verified,
        "job_limit_flags": attestation.job_limit_flags,
        "breakaway_allowed": attestation.breakaway_allowed,
        "kill_on_job_close": attestation.kill_on_job_close,
        "job_empty": attestation.job_empty,
        "acl_entry_count": attestation.acl_entry_count,
        "original_acl_manifest_sha256": (attestation.original_acl_manifest_sha256),
        "restored_acl_manifest_sha256": (attestation.restored_acl_manifest_sha256),
        "acl_exactly_restored": attestation.acl_exactly_restored,
        "scratch_emptied": attestation.scratch_emptied,
        "profile_deleted": attestation.profile_deleted,
        "profile_storage_deleted": attestation.profile_storage_deleted,
    }


def _execution_record(observation: Observation) -> dict[str, Any]:
    result = observation.result
    return {
        "mode": observation.mode,
        "mechanism_source_granted": observation.mode == "mechanism-disabled",
        "command": list(result.command),
        "environment": _environment_record(result.attestation.environment),
        "return_code": result.return_code,
        "termination_reason": result.termination_reason.value,
        "stdout": {
            "sha256": _sha256(result.stdout),
            "byte_length": len(result.stdout),
        },
        "stderr": {
            "sha256": _sha256(result.stderr),
            "byte_length": len(result.stderr),
        },
        "wall_time_nanoseconds": result.wall_time_ns,
        "total_user_time_100ns": result.total_user_time_100ns,
        "total_kernel_time_100ns": result.total_kernel_time_100ns,
        "total_processes": result.total_processes,
        "terminated_processes": result.terminated_processes,
        "io_accounting": {
            "read_operation_count": result.read_operation_count,
            "write_operation_count": result.write_operation_count,
            "other_operation_count": result.other_operation_count,
            "read_transfer_count": result.read_transfer_count,
            "write_transfer_count": result.write_transfer_count,
            "other_transfer_count": result.other_transfer_count,
        },
        "sandbox": _attestation_record(result.attestation),
    }


def _read_grant_record(
    grants: Sequence[sandbox_broker.ReadGrant],
) -> list[dict[str, Any]]:
    return [{"path": str(grant.path), "recursive": grant.recursive} for grant in grants]


def _isolated_test_execution_record(
    observation: IsolatedTestObservation,
) -> dict[str, Any]:
    result = observation.result
    request = observation.request
    return {
        "mode": "isolated-test",
        "mechanism_source_granted": True,
        "command": list(result.command),
        "environment": _environment_record(result.attestation.environment),
        "read_grants": _read_grant_record(request.allowed_read),
        "return_code": result.return_code,
        "termination_reason": result.termination_reason.value,
        "stdout": {
            "sha256": _sha256(result.stdout),
            "byte_length": len(result.stdout),
        },
        "stderr": {
            "sha256": _sha256(result.stderr),
            "byte_length": len(result.stderr),
        },
        "wall_time_nanoseconds": result.wall_time_ns,
        "total_user_time_100ns": result.total_user_time_100ns,
        "total_kernel_time_100ns": result.total_kernel_time_100ns,
        "total_processes": result.total_processes,
        "terminated_processes": result.terminated_processes,
        "io_accounting": {
            "read_operation_count": result.read_operation_count,
            "write_operation_count": result.write_operation_count,
            "other_operation_count": result.other_operation_count,
            "read_transfer_count": result.read_transfer_count,
            "write_transfer_count": result.write_transfer_count,
            "other_transfer_count": result.other_transfer_count,
        },
        "sandbox": _attestation_record(result.attestation),
    }


def _comparison(
    fixture: FixtureSpec,
    reference: Observation,
    disabled: Observation,
) -> dict[str, Any]:
    fixture_bytes = contract._read_regular(fixture.fixture_path)
    golden_bytes = contract._read_regular(fixture.golden_path)
    _validate_observed(
        golden_bytes, fixture.fixture_id, f"{fixture.fixture_id} C0 golden"
    )
    if reference.result.stdout != golden_bytes:
        raise CaptureError(f"{fixture.fixture_id} reference differs from C0 golden")
    if disabled.result.stdout != golden_bytes:
        raise CaptureError(
            f"{fixture.fixture_id} disabled mechanism differs from C0 golden"
        )
    if reference.result.stdout != disabled.result.stdout:
        raise CaptureError(f"{fixture.fixture_id} independent child bytes differ")
    return {
        "fixture_id": fixture.fixture_id,
        "fixture": _record(fixture.fixture_path, fixture_bytes),
        "golden": _record(fixture.golden_path, golden_bytes),
        "reference_execution": _execution_record(reference),
        "mechanism_disabled_execution": _execution_record(disabled),
        "golden_output_sha256": _sha256(golden_bytes),
        "reference_output_sha256": _sha256(reference.result.stdout),
        "mechanism_disabled_output_sha256": _sha256(disabled.result.stdout),
        "output_byte_length": len(golden_bytes),
        "reference_matches_golden": True,
        "mechanism_disabled_matches_golden": True,
        "byte_identical": True,
    }


def _build_evidence(
    binding: contract.authority.ResultBlindStageBinding,
    *,
    claim_reference: str,
    local_options_sha256: str,
    runtime_records: Sequence[Mapping[str, Any]],
    test_records: Sequence[Mapping[str, Any]],
    fixture_records: Sequence[Mapping[str, Any]],
    golden_records: Sequence[Mapping[str, Any]],
    protocol_records: Sequence[Mapping[str, Any]],
    capsule: CapsuleAuthority,
    comparisons: Sequence[Mapping[str, Any]],
    isolated_test_execution: Mapping[str, Any],
) -> dict[str, Any]:
    source_manifest = {
        "runtime_sources": list(runtime_records),
        "test_sources": list(test_records),
        "fixture_sources": list(fixture_records),
        "golden_sources": list(golden_records),
        "c0_protocol_sources": list(protocol_records),
    }
    protocol_manifest = _sha256(contract.canonical_bytes(list(protocol_records)))
    evidence = {
        "schema_version": "geotarget.exp-local-003.c2-default-equivalence/v1",
        "experiment_id": contract.EXPERIMENT_ID,
        "card_sha256": contract.CARD_SHA256,
        "stage": "development",
        "stage_input_anchor_commit": binding.anchor_commit,
        "stage_input_anchor_sha256": binding.anchor_file.sha256,
        "preimplementation_lock_sha256": binding.preimplementation_lock_sha256,
        "local_options_sha256": local_options_sha256,
        "claim_reference": claim_reference,
        "baseline_variant": "L0-SEMANTIC",
        "candidate_mechanism_enabled": False,
        "runtime_sources": list(runtime_records),
        "test_sources": list(test_records),
        "fixture_sources": list(fixture_records),
        "golden_sources": list(golden_records),
        "c0_reference_authority": {
            "source_lock_commit": binding.source_lock_commit,
            "c0_source_commit": binding.c0_source_commit,
            "c0_source_tree": binding.c0_source_tree,
            "environment_lock_sha256": binding.environment_lock_sha256,
            "capsule_origin": "immutable-main-git-c0-source-tree",
            "capsule_files": list(capsule.files),
            "capsule_manifest_sha256": capsule.manifest_sha256,
            "protocol_sources": list(protocol_records),
            "protocol_manifest_sha256": protocol_manifest,
            "reference_child_c2_source_access": "kernel-denied",
        },
        "source_manifest_sha256": _sha256(contract.canonical_bytes(source_manifest)),
        "comparisons": list(comparisons),
        "comparison_manifest_sha256": _sha256(
            contract.canonical_bytes(list(comparisons))
        ),
        "isolated_test_execution": dict(isolated_test_execution),
        "isolated_test_execution_manifest_sha256": _sha256(
            contract.canonical_bytes(dict(isolated_test_execution))
        ),
        "passed": True,
    }
    contract._validate_schema(
        evidence,
        "c2-default-equivalence.schema.json",
        "captured C2 default-equivalence evidence",
    )
    return evidence


def _verify_launcher_context() -> None:
    if (
        len(sys.argv) != 1
        or Path(sys.argv[0]).resolve()
        != (SOURCE_ROOT / "launch_c2_equivalence.py").resolve()
    ):
        raise CaptureError("C2 capture helper may only run through its launcher")
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode is not True
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
        or Path.cwd().resolve() != REPOSITORY_ROOT.resolve()
    ):
        raise CaptureError(
            "formal C2 capture requires repository-root `python -I -B -S`"
        )


def _claim_reference(claim_identity: contract.ClaimIdentity) -> str:
    payload = {
        "path": contract.DEFAULT_EQUIVALENCE_PATH,
        "device": claim_identity.device,
        "inode": claim_identity.inode,
        "creation_nanoseconds": claim_identity.creation_nanoseconds,
    }
    return f"sha256:{_sha256(contract.canonical_bytes(payload))}"


def _remove_workspace(root: Path) -> None:
    try:
        shutil.rmtree(root)
    except OSError as error:
        raise CaptureError(f"cannot remove equivalence workspace: {error}") from error
    if root.exists():
        raise CaptureError("equivalence workspace remains after cleanup")


def capture(*, claim_already_created: bool) -> Path:
    """Capture five isolated children and fill the launcher's claim once."""

    if claim_already_created is not True:
        raise CaptureError("C2 capture helper requires a prior durable claim")
    claim_identity = contract._verify_empty_claim(contract.DEFAULT_EQUIVALENCE_PATH)
    try:
        contract.environment_contract.verify_frozen_environment()
    except contract.environment_contract.MaterializationError as error:
        raise CaptureError(
            f"frozen environment verification failed: {error}"
        ) from error
    _verify_launcher_context()

    git = contract._environment_lock_git()
    head = contract._git_text(git, "rev-parse", "HEAD")
    repository = contract.authority.GitObjectRepository(REPOSITORY_ROOT, git)
    _validate_repository_state(git, repository, head)
    binding = _result_blind_binding(git, repository, head)
    local_options_sha256, environment_lock_bytes = _verify_c0_bindings(binding)
    protocol_records = _verify_live_c0_protocol(repository, binding)
    runtime_records = _working_records(C2_RUNTIME_SOURCE_PATHS)
    test_records = _working_records(C2_TEST_SOURCE_PATHS)
    fixture_records = _working_records(tuple(sorted(FIXTURE_PATHS)))
    golden_records = _working_records(tuple(sorted(GOLDEN_PATHS)))
    runtime = _runtime_authority(environment_lock_bytes)
    claim_reference = _claim_reference(claim_identity)

    workspace = Path(
        tempfile.mkdtemp(prefix="geotarget-exp-local-003-c2-equivalence-")
    ).absolute()
    if any(
        _is_within(workspace, forbidden)
        for forbidden in (
            REPOSITORY_ROOT,
            runtime.runtime_root,
            runtime.depot_root,
        )
    ):
        _remove_workspace(workspace)
        raise CaptureError(
            "equivalence workspace overlaps repository or a runtime read authority"
        )
    comparisons: list[dict[str, Any]] = []
    observations: list[Observation] = []
    isolated_test: IsolatedTestObservation | None = None
    capsule: CapsuleAuthority | None = None
    try:
        capsule = _materialize_capsule(repository, binding, workspace)
        for index, fixture in enumerate(FIXTURES):
            reference = _run_observation(
                runtime,
                capsule,
                fixture,
                "reference",
                workspace / f"scratch-{index}-reference",
                claim_reference,
            )
            disabled = _run_observation(
                runtime,
                capsule,
                fixture,
                "mechanism-disabled",
                workspace / f"scratch-{index}-mechanism-disabled",
                claim_reference,
            )
            observations.extend((reference, disabled))
            comparisons.append(_comparison(fixture, reference, disabled))
        isolated_test = _run_isolated_test(
            runtime,
            workspace / "scratch-isolated-test",
            claim_reference,
        )
        all_results = [
            *(item.result for item in observations),
            isolated_test.result,
        ]
        profiles = [item.attestation.profile_name for item in all_results]
        package_sids = [item.attestation.package_sid for item in all_results]
        scratch_paths = [item.attestation.scratch_directory for item in all_results]
        if (
            len(observations) != 4
            or len(all_results) != 5
            or len(set(profiles)) != 5
            or len(set(package_sids)) != 5
            or len(set(scratch_paths)) != 5
        ):
            raise CaptureError(
                "equivalence/test observations did not use five fresh AppContainers"
            )
        _verify_capsule(capsule)
    finally:
        _remove_workspace(workspace)
    if capsule is None:
        raise CaptureError("baseline capsule was not materialized")
    if isolated_test is None:
        raise CaptureError("isolated C2 Julia test was not executed")

    if _working_records(C2_RUNTIME_SOURCE_PATHS) != runtime_records:
        raise CaptureError("C2 runtime source bytes changed during equivalence capture")
    if _working_records(C2_TEST_SOURCE_PATHS) != test_records:
        raise CaptureError("C2 test source bytes changed during equivalence capture")
    if _working_records(tuple(sorted(FIXTURE_PATHS))) != fixture_records:
        raise CaptureError("C0 fixture bytes changed during equivalence capture")
    if _working_records(tuple(sorted(GOLDEN_PATHS))) != golden_records:
        raise CaptureError("C0 golden bytes changed during equivalence capture")
    if contract._read_regular(contract.ENVIRONMENT_LOCK_PATH) != environment_lock_bytes:
        raise CaptureError(
            "C0 environment-lock bytes changed during equivalence capture"
        )
    if _verify_live_c0_protocol(repository, binding) != protocol_records:
        raise CaptureError("C0 protocol bytes changed during equivalence capture")
    _validate_repository_state(git, repository, head)
    if (
        contract._verify_empty_claim(contract.DEFAULT_EQUIVALENCE_PATH)
        != claim_identity
    ):
        raise CaptureError("C2 evidence claim identity changed during child capture")
    try:
        contract.environment_contract.verify_frozen_environment()
    except contract.environment_contract.MaterializationError as error:
        raise CaptureError(
            f"post-capture environment verification failed: {error}"
        ) from error
    _validate_repository_state(git, repository, head)
    if (
        _working_records(C2_RUNTIME_SOURCE_PATHS) != runtime_records
        or _working_records(C2_TEST_SOURCE_PATHS) != test_records
        or contract._read_regular(contract.ENVIRONMENT_LOCK_PATH)
        != environment_lock_bytes
        or contract._verify_empty_claim(contract.DEFAULT_EQUIVALENCE_PATH)
        != claim_identity
    ):
        raise CaptureError("formal state changed during post-capture verification")
    evidence = _build_evidence(
        binding,
        claim_reference=claim_reference,
        local_options_sha256=local_options_sha256,
        runtime_records=runtime_records,
        test_records=test_records,
        fixture_records=fixture_records,
        golden_records=golden_records,
        protocol_records=protocol_records,
        capsule=capsule,
        comparisons=comparisons,
        isolated_test_execution=_isolated_test_execution_record(isolated_test),
    )
    _validate_repository_state(git, repository, head)
    if (
        _working_records(C2_RUNTIME_SOURCE_PATHS) != runtime_records
        or _working_records(C2_TEST_SOURCE_PATHS) != test_records
        or _working_records(tuple(sorted(FIXTURE_PATHS))) != fixture_records
        or _working_records(tuple(sorted(GOLDEN_PATHS))) != golden_records
        or _verify_live_c0_protocol(repository, binding) != protocol_records
        or contract._read_regular(contract.ENVIRONMENT_LOCK_PATH)
        != environment_lock_bytes
        or contract._verify_empty_claim(contract.DEFAULT_EQUIVALENCE_PATH)
        != claim_identity
    ):
        raise CaptureError("formal state changed after evidence construction")
    contract._write_claimed(contract.DEFAULT_EQUIVALENCE_PATH, evidence, claim_identity)
    return _path(contract.DEFAULT_EQUIVALENCE_PATH)


def main() -> int:
    raise CaptureError("direct execution is prohibited; use launch_c2_equivalence.py")


if __name__ == "__main__":
    raise SystemExit(main())
