"""Immutable authority resolver for EXP-LOCAL-003 candidate/assessor stages.

This C0 module does not launch or observe a candidate process.  It verifies the
objects a C2 observer must persist and resolves them only from immutable Git
objects.  In particular, it never trusts a vault worktree, Git configuration,
or a candidate-authored statement about process lifetime.

The candidate protocol is a single-parent, append-only Git chain::

    attempt claim --> raw output --(observer seal/ACK)--> pre-exit seal
        --> process exit --> manifest + candidate-run authority

The assessor authority lives in a physically distinct Git repository.  A
stage anchor, itself addressed by repository/commit/path/digest, binds both
vault commits and trees.  Every final vault tree is closed to the attempt
claim, three outcome artifacts, manifest, and authority.
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
import time
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Callable, Final, Literal, TypeAlias, cast


_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_PYTHON_SOURCE = _REPOSITORY_ROOT / "python" / "src"
if str(_PYTHON_SOURCE) not in sys.path:
    sys.path.insert(0, str(_PYTHON_SOURCE))

from geotarget.canonical import canonical_bytes  # noqa: E402


Stage: TypeAlias = Literal["development", "locked"]

CARD_SHA256: Final = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"
EXPERIMENT_ID: Final = "EXP-LOCAL-003"
RUNNER_SOURCE_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl"
)
C2_REQUIRED_SOURCE_PATHS: Final = (
    "julia/GeoTargetCore/src/local_model_transform.jl",
    RUNNER_SOURCE_PATH,
)
C2_TEST_SOURCE_PATHS: Final = (
    "julia/GeoTargetCore/test/test_local_model_transform.jl",
)
C0_EQUIVALENCE_PROTOCOL_PATHS: Final = (
    "research/experiments/EXP-LOCAL-003/source/Local3FixturePlugin.jl",
    "research/experiments/EXP-LOCAL-003/source/c2-default-equivalence.schema.json",
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-fixtures/"
    "julia-core-default.json",
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-fixtures/"
    "opaque-plugin-default.json",
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-golden/"
    "julia-core-default.stdout.json",
    "research/experiments/EXP-LOCAL-003/source/c2-equivalence-golden/"
    "opaque-plugin-default.stdout.json",
    "research/experiments/EXP-LOCAL-003/source/c2_equivalence_child.jl",
    "research/experiments/EXP-LOCAL-003/source/sandbox_broker.py",
)
C0_EQUIVALENCE_FIXTURE_PATHS: Final = (
    C0_EQUIVALENCE_PROTOCOL_PATHS[2],
    C0_EQUIVALENCE_PROTOCOL_PATHS[3],
)
C0_EQUIVALENCE_GOLDEN_PATHS: Final = (
    C0_EQUIVALENCE_PROTOCOL_PATHS[4],
    C0_EQUIVALENCE_PROTOCOL_PATHS[5],
)
C0_EQUIVALENCE_CHILD_PATH: Final = C0_EQUIVALENCE_PROTOCOL_PATHS[6]
C0_SANDBOX_BROKER_PATH: Final = C0_EQUIVALENCE_PROTOCOL_PATHS[7]
C2_EQUIVALENCE_EVIDENCE_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/C2_L0_DEFAULT_EQUIVALENCE.json"
)
ENVIRONMENT_LOCK_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/environment-lock.json"
)
C1_CANDIDATE_OUTCOME_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/development-candidate-inputs"
)
C1_STAGE_VAULT_ANCHOR_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/C1_STAGE_VAULT_ANCHOR.json"
)
C1_ATTEMPT_CLAIM_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/C1_ATTEMPT_CLAIM.json"
)


def _c1_external_fixed_roots(root: Path = _REPOSITORY_ROOT) -> tuple[Path, ...]:
    """Return the five C1 truth/outcome namespaces in their protocol order."""

    return (
        root.with_name(f"{root.name}-vault")
        / EXPERIMENT_ID
        / "development-assessor-vault",
        root.with_name(f"{root.name}-private-audit")
        / EXPERIMENT_ID
        / "development-generator-private-vault",
        root.with_name(f"{root.name}-run-evidence") / EXPERIMENT_ID,
        root.with_name(f"{root.name}-assessment-evidence") / EXPERIMENT_ID,
        root.with_name(f"{root.name}-sandbox-scratch") / EXPERIMENT_ID,
    )


C2_EXECUTION_LOCK_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/candidate-execution-lock.json"
)
LOCKED_EXECUTION_LOCK_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/locked-candidate-execution-lock.json"
)
EXPECTED_FORBIDDEN_MECHANISM_PATHS: Final = (
    *C2_REQUIRED_SOURCE_PATHS,
    *C2_TEST_SOURCE_PATHS,
    C2_EQUIVALENCE_EVIDENCE_PATH,
    C2_EXECUTION_LOCK_PATH,
    LOCKED_EXECUTION_LOCK_PATH,
    "research/experiments/EXP-LOCAL-003/development-candidate-inputs",
)
C1_FORBIDDEN_MECHANISM_PATHS: Final = (
    *C2_REQUIRED_SOURCE_PATHS,
    *C2_TEST_SOURCE_PATHS,
    C2_EQUIVALENCE_EVIDENCE_PATH,
    C2_EXECUTION_LOCK_PATH,
    LOCKED_EXECUTION_LOCK_PATH,
)
C2_INTRODUCTION_PATHS: Final = frozenset(
    (
        *C2_REQUIRED_SOURCE_PATHS,
        *C2_TEST_SOURCE_PATHS,
        C2_EQUIVALENCE_EVIDENCE_PATH,
        C2_EXECUTION_LOCK_PATH,
    )
)

PREEXIT_SCHEMA: Final = "geotarget.exp-local-003.candidate-output-preexit-seal/v2"
ATTEMPT_SCHEMA: Final = "geotarget.exp-local-003.candidate-run-attempt/v2"
EXIT_SCHEMA: Final = "geotarget.exp-local-003.candidate-process-exit/v2"
MANIFEST_SCHEMA: Final = "geotarget.exp-local-003.authority-file-manifest/v1"
CANDIDATE_AUTHORITY_SCHEMA: Final = "geotarget.exp-local-003.candidate-run-authority/v2"
ASSESSOR_AUTHORITY_SCHEMA: Final = "geotarget.exp-local-003.assessor-stage-authority/v1"
ANCHOR_SCHEMA: Final = "geotarget.exp-local-003.stage-vault-anchor/v1"
DEVELOPMENT_AUTHORIZATION_SCHEMA: Final = (
    "geotarget.exp-local-003.development-authorization-anchor/v1"
)
FINAL_CONNECTION_ANCHOR_SCHEMA: Final = (
    "geotarget.exp-local-003.final-connection-anchor/v1"
)
LOCKED_AUTHORIZATION_SCHEMA: Final = FINAL_CONNECTION_ANCHOR_SCHEMA

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_PROCESS_ID = _SHA256
_GZIP_HEADER: Final = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"

_FILE_RECORD_KEYS: Final = {"path", "sha256", "byte_length"}
_PARENT_KEYS: Final = {"kind", "sha256"}
_COMMIT_TREE_KEYS: Final = {"commit", "tree"}
_ATTEMPT_KEYS: Final = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "candidate_input_sha256",
    "stage_input_anchor",
    "candidate_execution_lock",
    "execution_source",
    "launcher_claim",
    "launcher_authority",
    "observer_authority",
    "sandbox_broker_authority",
    "sandbox_request",
    "rerun_permitted",
    "prelaunch_state",
}
_PREEXIT_KEYS: Final = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "process_instance_id",
    "candidate_input_sha256",
    "launcher_claim",
    "observer_authority",
    "sandbox_request_sha256",
    "preexit_observation",
    "event",
    "raw_output",
    "changed_paths",
    "ack",
}
_EXIT_KEYS: Final = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "process_instance_id",
    "candidate_input_sha256",
    "launcher_claim",
    "observer_authority",
    "event",
    "raw_output",
    "preexit_seal",
    "changed_paths",
    "ack",
    "exit_status",
    "candidate_accounting",
    "sandbox_result",
    "termination_observation",
}
_CANDIDATE_AUTHORITY_KEYS: Final = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "process_instance_id",
    "candidate_input_sha256",
    "stage_input_anchor",
    "candidate_execution_lock",
    "candidate_publication_tree_sha256",
    "launcher_claim_sha256",
    "observer_authority",
    "sandbox_broker_authority",
    "sandbox_result_sha256",
    "attempt_claim",
    "history",
    "event",
    "raw_output",
    "preexit_seal",
    "process_exit",
    "changed_paths",
    "manifest",
}
_ASSESSOR_OUTPUT_KEYS: Final = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "stage_input_anchor_sha256",
    "candidate_run_authority_sha256",
    "candidate_execution_lock_sha256",
    "candidate_raw_output_sha256",
    "assessor_truth_sha256",
    "bootstrap_sha256",
    "assessment_sha256",
    "accounting",
}
_ANCHOR_KEYS: Final = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "source_lock_commit",
    "preimplementation_lock_sha256",
    "materialization_attempt_claim_sha256",
    "assessor_vault_git_commit",
    "assessor_vault_git_tree",
    "assessor_vault_manifest_sha256",
    "assessor_vault_completion_sha256",
    "assessor_manifest_sha256",
    "candidate_manifest_sha256",
    "candidate_completion_sha256",
    "candidate_publication_tree",
    "c1_phase_accounting",
    "candidate_visible",
    "rerun_permitted",
}


class AuthorityError(ValueError):
    """An authority object, immutable vault, or cross-binding is invalid."""


@dataclass(frozen=True, slots=True)
class FileRecord:
    """A byte-exact file identity inside one immutable Git tree."""

    path: str
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class GitExecutable:
    """A caller-verified Git binary pinned by absolute path and SHA-256."""

    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One closed manifest entry and its transport contract."""

    role: str
    file: FileRecord
    media_type: str
    content_encoding: Literal["identity", "deterministic-gzip"]


@dataclass(frozen=True, slots=True)
class CandidateRunRecord:
    """Fully verified candidate-process authority resolved from a vault commit."""

    stage: Stage
    process_instance_id: str
    candidate_input_sha256: str
    candidate_execution_lock_sha256: str
    candidate_execution_lock_commit: str
    candidate_execution_lock_tree: str
    candidate_execution_lock_file: FileRecord
    candidate_execution_lock_jcs: bytes
    candidate_execution_lock: Mapping[str, Any]
    candidate_process_cpu_nanoseconds: int
    candidate_observer_wall_nanoseconds: int
    vault_commit: str
    vault_tree: str
    authority_file: FileRecord
    manifest_file: FileRecord
    attempt_claim_file: FileRecord
    raw_output_file: FileRecord
    preexit_seal_file: FileRecord
    process_exit_file: FileRecord
    attempt_claim_jcs: bytes
    attempt_claim: Mapping[str, Any]
    raw_output_jcs: bytes
    raw_output: Mapping[str, Any]
    preexit_seal: Mapping[str, Any]
    process_exit: Mapping[str, Any]
    authority: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StageInputRecord:
    """C1/locked inputs proven to predate the candidate process."""

    stage: Stage
    anchor_commit: str
    anchor_tree: str
    anchor_file: FileRecord
    source_lock_commit: str
    preimplementation_lock_sha256: str
    candidate_publication_tree_sha256: str
    candidate_files: Mapping[str, FileRecord]
    candidate_input_sha256: str
    candidate_input_jcs: bytes
    candidate_input: Mapping[str, Any]
    assessor_vault_commit: str
    assessor_vault_tree: str
    assessor_truth_file: FileRecord
    assessor_truth_jcs: bytes
    assessor_truth: Mapping[str, Any]
    bootstrap_file: FileRecord
    bootstrap_indices: bytes
    development_authority: Mapping[str, Any] | None
    anchor: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ResultBlindStageBinding:
    """C1/C0 binding resolved without opening any outcome-bearing repository.

    This deliberately omits candidate input, assessor truth, private-vault, and
    publication-tree data.  It is the maximum authority available to the C2
    default-equivalence capture before its four sandboxed child processes run.
    """

    stage: Literal["development"]
    anchor_commit: str
    anchor_tree: str
    anchor_file: FileRecord
    source_lock_commit: str
    preimplementation_lock_sha256: str
    c0_source_commit: str
    c0_source_tree: str
    environment_lock_sha256: str
    local_options_sha256: str


@dataclass(frozen=True, slots=True)
class FormalAssessmentRecord:
    """Assessment plus observer-owned, exactly-once CPU/wall accounting."""

    stage: Stage
    assessment_jcs: bytes
    assessment: Mapping[str, Any]
    authority_jcs: bytes
    authority: Mapping[str, Any]
    end_to_end_cpu_nanoseconds: int
    end_to_end_wall_nanoseconds: int


@dataclass(frozen=True, slots=True)
class ResolvedAssessmentOutput:
    """Immutable assessment commit and optional single-child development decision."""

    formal: FormalAssessmentRecord
    assessment_commit: str
    assessment_tree: str
    assessment_file: FileRecord
    authority_file: FileRecord
    decision_commit: str | None
    decision_tree: str | None
    decision_file: FileRecord | None
    decision_jcs: bytes | None
    decision: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class DevelopmentAuthorization:
    """Complete immutable development chain authorized for locked generation."""

    authorization_anchor_commit: str
    authorization_anchor_tree: str
    authorization_anchor_file: FileRecord
    authorization_anchor: Mapping[str, Any]
    stage_input: StageInputRecord
    candidate_run: CandidateRunRecord
    assessor_output: ResolvedAssessmentOutput


@dataclass(frozen=True, slots=True)
class LockedAuthorization:
    """Complete immutable C4 -> C5 -> C6 product-connection authority."""

    authorization_anchor_commit: str
    authorization_anchor_tree: str
    authorization_anchor_file: FileRecord
    authorization_anchor: Mapping[str, Any]
    development: DevelopmentAuthorization
    stage_input: StageInputRecord
    candidate_run: CandidateRunRecord
    assessor_output: ResolvedAssessmentOutput
    final_connection_commit: str
    final_connection_tree: str
    final_connection_file: FileRecord
    final_connection_jcs: bytes
    final_connection: Mapping[str, Any]
    product_connection_allowed: bool


@dataclass(frozen=True, slots=True)
class _Blob:
    oid: str
    mode: str
    data: bytes


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _exact_keys(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        raise AuthorityError(
            f"{context} keys differ; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise AuthorityError(f"{context} must be a JSON object with string keys")
    return cast(Mapping[str, Any], value)


def _array(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuthorityError(f"{context} must be a JSON array")
    return value


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise AuthorityError(f"{context} must be a string")
    return value


def _integer(value: Any, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AuthorityError(f"{context} must be an integer >= {minimum}")
    return value


def _hex(value: Any, pattern: re.Pattern[str], context: str) -> str:
    text = _string(value, context)
    if pattern.fullmatch(text) is None:
        raise AuthorityError(f"{context} has invalid lowercase hexadecimal form")
    return text


def _stage(value: Any, context: str = "stage") -> Stage:
    if value not in ("development", "locked"):
        raise AuthorityError(f"{context} must be 'development' or 'locked'")
    return cast(Stage, value)


def _normal_path(value: Any, context: str) -> str:
    text = _string(value, context)
    if not text or "\\" in text or text.startswith("/") or text.endswith("/"):
        raise AuthorityError(f"{context} must be a normalized POSIX relative path")
    path = PurePosixPath(text)
    if path.as_posix() != text or any(part in ("", ".", "..") for part in path.parts):
        raise AuthorityError(f"{context} must be a normalized POSIX relative path")
    if any("\x00" in part for part in path.parts):
        raise AuthorityError(f"{context} contains NUL")
    return text


def strict_jcs_bytes(payload: bytes, *, context: str = "JSON authority") -> Any:
    """Decode exact UTF-8 RFC 8785 bytes, rejecting duplicate keys and extensions."""

    if not isinstance(payload, bytes):
        raise AuthorityError(f"{context} must be bytes")

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
        if canonical_bytes(value) != payload:
            raise AuthorityError(f"{context} is not exact RFC 8785 JCS")
    except AuthorityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise AuthorityError(f"invalid {context}: {error}") from error
    return value


def deterministic_gzip(payload: bytes) -> bytes:
    """Return C0's unique level-9, mtime=0, OS=255 gzip representation."""

    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    body = compressor.compress(payload) + compressor.flush()
    trailer = struct.pack(
        "<II", zlib.crc32(payload) & 0xFFFFFFFF, len(payload) & 0xFFFFFFFF
    )
    return _GZIP_HEADER + body + trailer


def decode_deterministic_gzip(payload: bytes, *, context: str) -> bytes:
    """Decode gzip only when its entire byte representation is deterministic."""

    try:
        decoded = zlib.decompress(payload, wbits=31)
    except zlib.error as error:
        raise AuthorityError(f"invalid {context} gzip: {error}") from error
    if deterministic_gzip(decoded) != payload:
        raise AuthorityError(f"{context} is not the frozen deterministic gzip encoding")
    return decoded


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _deep_freeze(child) for key, child in value.items()}
        )
    if isinstance(value, list):
        return tuple(_deep_freeze(child) for child in value)
    return value


def _file_record(value: Any, context: str) -> FileRecord:
    document = _mapping(value, context)
    _exact_keys(document, _FILE_RECORD_KEYS, context)
    return FileRecord(
        path=_normal_path(document["path"], f"{context}.path"),
        sha256=_hex(document["sha256"], _SHA256, f"{context}.sha256"),
        byte_length=_integer(document["byte_length"], f"{context}.byte_length"),
    )


def _file_record_json(record: FileRecord) -> dict[str, Any]:
    return {
        "path": record.path,
        "sha256": record.sha256,
        "byte_length": record.byte_length,
    }


def _verify_common(
    document: Mapping[str, Any], schema: str, stage: Stage, context: str
) -> None:
    if document.get("schema_version") != schema:
        raise AuthorityError(f"{context} schema version differs")
    if document.get("experiment_id") != EXPERIMENT_ID:
        raise AuthorityError(f"{context} experiment differs")
    if document.get("card_sha256") != CARD_SHA256:
        raise AuthorityError(f"{context} card differs")
    if _stage(document.get("stage"), f"{context}.stage") != stage:
        raise AuthorityError(f"{context} stage differs")


def _parent(value: Any, expected_kind: str, expected_sha256: str, context: str) -> None:
    parent = _mapping(value, context)
    _exact_keys(parent, _PARENT_KEYS, context)
    if parent["kind"] != expected_kind:
        raise AuthorityError(f"{context}.kind differs")
    if _hex(parent["sha256"], _SHA256, f"{context}.sha256") != expected_sha256:
        raise AuthorityError(f"{context}.sha256 differs")


def _changed_paths(value: Any, raw_path: str, context: str) -> tuple[str, ...]:
    paths = tuple(
        _normal_path(item, f"{context}[{index}]")
        for index, item in enumerate(_array(value, context))
    )
    if paths != (raw_path,):
        raise AuthorityError(
            f"{context} must contain exactly the single candidate-authored raw path"
        )
    return paths


def _verify_blob_record(blob: _Blob, record: FileRecord, context: str) -> None:
    if blob.mode != "100644":
        raise AuthorityError(f"{context} is not a regular non-executable Git blob")
    if len(blob.data) != record.byte_length or _sha256(blob.data) != record.sha256:
        raise AuthorityError(f"{context} byte length or SHA-256 differs")


def _reject_link_or_reparse(path: Path, context: str) -> None:
    try:
        info = path.lstat()
    except OSError as error:
        raise AuthorityError(f"cannot inspect {context}: {error}") from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(info.st_mode) or attributes & reparse:
        raise AuthorityError(f"{context} may not be a symlink or reparse point")


def _reject_reparse_ancestry(path: Path, context: str) -> None:
    current = path
    while not current.exists():
        if current.parent == current:
            raise AuthorityError(f"{context} has no existing ancestor")
        current = current.parent
    while True:
        _reject_link_or_reparse(current, context)
        if current.parent == current:
            return
        current = current.parent


class GitObjectRepository:
    """Read commits/trees/blobs through closed ``git cat-file`` invocations."""

    def __init__(self, root: Path, git_executable: GitExecutable) -> None:
        if not root.is_absolute():
            raise AuthorityError("vault repository path must be absolute")
        self.root = root
        _reject_reparse_ancestry(root, "vault repository ancestry")
        _reject_link_or_reparse(root, "vault repository root")
        dot_git = root / ".git"
        if dot_git.is_dir():
            _reject_link_or_reparse(dot_git, "vault .git directory")
            git_dir = dot_git
        elif (root / "objects").is_dir() and (root / "HEAD").is_file():
            git_dir = root
        else:
            raise AuthorityError(f"{root} is not a directly addressed Git repository")
        _reject_link_or_reparse(git_dir / "objects", "vault object database")
        alternates = git_dir / "objects" / "info" / "alternates"
        if alternates.exists():
            raise AuthorityError("authority repository may not use object alternates")
        for alternate_name in ("alternates", "http-alternates"):
            alternate = git_dir / "objects" / "info" / alternate_name
            if alternate.exists():
                raise AuthorityError(
                    "Git object alternates are forbidden for authority repos"
                )
        verified_git = pin_git_executable(git_executable.path, git_executable.sha256)
        self._git = str(verified_git.path)
        self._git_dir = str(git_dir.absolute())
        self.object_database = (git_dir / "objects").resolve()
        self.object_database_path = (git_dir / "objects").absolute()
        null_device = "NUL" if os.name == "nt" else "/dev/null"
        # Deliberately do not inherit HOME, hooks, aliases, protocol helpers, or
        # user/system Git configuration.  cat-file needs no worktree.
        self._environment = {
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
                    self._environment[key] = value

    def _cat_file(self, object_type: str, oid: str) -> bytes:
        _hex(oid, _GIT_OID, "Git object id")
        if object_type not in {"-t", "commit", "tree", "blob"}:
            raise AuthorityError("unsupported cat-file operation")
        try:
            completed = subprocess.run(
                [
                    self._git,
                    f"--git-dir={self._git_dir}",
                    "-c",
                    "core.pager=cat",
                    "-c",
                    "core.attributesFile=",
                    "cat-file",
                    object_type,
                    oid,
                ],
                check=False,
                capture_output=True,
                env=self._environment,
            )
        except OSError as error:
            raise AuthorityError(f"git cat-file could not execute: {error}") from error
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", "replace").strip()
            raise AuthorityError(f"git cat-file rejected {oid}: {message}")
        payload = completed.stdout
        if object_type in {"commit", "tree", "blob"}:
            algorithm = hashlib.sha1 if len(oid) == 40 else hashlib.sha256
            framed = (
                object_type.encode("ascii")
                + b" "
                + str(len(payload)).encode("ascii")
                + b"\0"
                + payload
            )
            if algorithm(framed).hexdigest() != oid:
                raise AuthorityError(
                    "git cat-file returned bytes that do not match object id"
                )
        return payload

    def commit_tree(self, commit: str) -> str:
        _hex(commit, _GIT_OID, "commit")
        if self._cat_file("-t", commit).rstrip(b"\r\n") != b"commit":
            raise AuthorityError("addressed Git object is not a commit")
        body = self._cat_file("commit", commit)
        first_line = body.split(b"\n", 1)[0]
        if not first_line.startswith(b"tree "):
            raise AuthorityError("Git commit has no leading tree authority")
        try:
            tree = first_line.removeprefix(b"tree ").decode("ascii")
        except UnicodeDecodeError as error:
            raise AuthorityError("Git tree id is not ASCII") from error
        return _hex(tree, _GIT_OID, "commit tree")

    def commit_parents(self, commit: str) -> tuple[str, ...]:
        if self._cat_file("-t", commit).rstrip(b"\r\n") != b"commit":
            raise AuthorityError("addressed Git object is not a commit")
        body = self._cat_file("commit", commit)
        parents: list[str] = []
        for line in body.split(b"\n"):
            if not line:
                break
            if line.startswith(b"parent "):
                try:
                    parent = line.removeprefix(b"parent ").decode("ascii")
                except UnicodeDecodeError as error:
                    raise AuthorityError("Git parent id is not ASCII") from error
                parents.append(_hex(parent, _GIT_OID, "commit parent"))
        return tuple(parents)

    def _tree_entries(self, tree_oid: str) -> tuple[tuple[str, str, str], ...]:
        raw = self._cat_file("tree", tree_oid)
        oid_bytes = len(tree_oid) // 2
        cursor = 0
        entries: list[tuple[str, str, str]] = []
        while cursor < len(raw):
            space = raw.find(b" ", cursor)
            nul = raw.find(b"\x00", space + 1)
            if space <= cursor or nul < 0:
                raise AuthorityError("malformed raw Git tree object")
            oid_start = nul + 1
            oid_end = oid_start + oid_bytes
            if oid_end > len(raw):
                raise AuthorityError("truncated raw Git tree object")
            try:
                mode = raw[cursor:space].decode("ascii")
                name = raw[space + 1 : nul].decode("utf-8")
            except UnicodeDecodeError as error:
                raise AuthorityError(
                    "Git tree mode/path is not canonical UTF-8"
                ) from error
            if (
                not name
                or name in (".", "..")
                or "/" in name
                or "\\" in name
                or "\x00" in name
            ):
                raise AuthorityError("Git tree contains an unsafe path component")
            entries.append((mode, name, raw[oid_start:oid_end].hex()))
            cursor = oid_end
        return tuple(entries)

    def blob_at(self, commit: str, path: str) -> _Blob:
        """Resolve one commit path without traversing unrelated main-repo entries."""

        parts = PurePosixPath(_normal_path(path, "Git blob path")).parts
        tree = self.commit_tree(commit)
        for index, part in enumerate(parts):
            matches = [entry for entry in self._tree_entries(tree) if entry[1] == part]
            if len(matches) != 1:
                raise AuthorityError(f"Git blob path component {part!r} is absent")
            mode, _, oid = matches[0]
            final = index == len(parts) - 1
            if final:
                if mode != "100644":
                    raise AuthorityError(
                        "addressed authority is not a regular non-executable blob"
                    )
                return _Blob(oid=oid, mode=mode, data=self._cat_file("blob", oid))
            if mode not in ("40000", "040000"):
                raise AuthorityError("Git authority path crosses a non-directory entry")
            tree = oid
        raise AssertionError("normalized Git path has no components")

    def tree_index(self, commit: str) -> Mapping[str, tuple[str, str]]:
        """Return immutable path -> (mode, oid) without worktree interpretation."""

        result: dict[str, tuple[str, str]] = {}

        def visit(tree: str, prefix: str) -> None:
            for mode, name, oid in self._tree_entries(tree):
                path = f"{prefix}/{name}" if prefix else name
                _normal_path(path, "Git tree path")
                if mode in ("40000", "040000"):
                    visit(oid, path)
                else:
                    if path in result:
                        raise AuthorityError("Git tree contains duplicate paths")
                    result[path] = (mode, oid)

        visit(self.commit_tree(commit), "")
        return MappingProxyType(result)

    def snapshot(self, commit: str, expected_tree: str) -> Mapping[str, _Blob]:
        actual_tree = self.commit_tree(commit)
        if actual_tree != _hex(expected_tree, _GIT_OID, "expected tree"):
            raise AuthorityError("vault commit tree differs from stage anchor")
        blobs: dict[str, _Blob] = {}

        def visit(tree_oid: str, prefix: str) -> None:
            for mode, name, oid in self._tree_entries(tree_oid):
                path = f"{prefix}/{name}" if prefix else name
                _normal_path(path, "Git tree path")
                if mode in ("40000", "040000"):
                    visit(oid, path)
                elif mode == "100644":
                    if path in blobs:
                        raise AuthorityError("Git tree contains duplicate paths")
                    blobs[path] = _Blob(
                        oid=oid, mode=mode, data=self._cat_file("blob", oid)
                    )
                elif mode in ("120000", "160000"):
                    raise AuthorityError("Git vault tree contains a symlink or gitlink")
                else:
                    raise AuthorityError(
                        f"Git vault tree contains forbidden mode {mode}"
                    )

        visit(actual_tree, "")
        return MappingProxyType(blobs)


def pin_git_executable(path: Path, expected_sha256: str) -> GitExecutable:
    """Validate an environment-lock Git path before any object resolution."""

    if not path.is_absolute():
        raise AuthorityError("Git executable path must be absolute")
    _reject_link_or_reparse(path, "Git executable")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise AuthorityError(f"cannot read pinned Git executable: {error}") from error
    digest = _hex(expected_sha256, _SHA256, "Git executable sha256")
    if _sha256(payload) != digest:
        raise AuthorityError("Git executable differs from environment lock")
    return GitExecutable(path=path, sha256=digest)


def _filesystem_snapshot(root: Path, expected_paths: set[str]) -> Mapping[str, bytes]:
    """Read a closed publication prefix while rejecting links and races."""

    if not root.is_absolute():
        raise AuthorityError("candidate publication root must be absolute")
    _reject_link_or_reparse(root, "candidate publication root")
    found: dict[str, bytes] = {}
    try:
        paths = sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        )
    except OSError as error:
        raise AuthorityError(
            f"cannot enumerate candidate publication: {error}"
        ) from error
    for path in paths:
        _reject_link_or_reparse(path, "candidate publication entry")
        relative = _normal_path(path.relative_to(root).as_posix(), "candidate path")
        if path.is_dir():
            continue
        if not path.is_file():
            raise AuthorityError("candidate publication contains a non-regular entry")
        try:
            before = path.stat()
            payload = path.read_bytes()
            after = path.stat()
        except OSError as error:
            raise AuthorityError(
                f"cannot read candidate publication: {error}"
            ) from error
        if (
            before.st_size != len(payload)
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise AuthorityError("candidate publication changed while being resolved")
        found[relative] = payload
    if set(found) != expected_paths:
        raise AuthorityError(
            "candidate publication prefix is not closed; "
            f"extra={sorted(set(found) - expected_paths)}, "
            f"missing={sorted(expected_paths - set(found))}"
        )
    return MappingProxyType(found)


def _publication_tree(files: Mapping[str, bytes]) -> Mapping[str, Any]:
    digest = hashlib.sha256(b"GTLOCAL3PUBLICATIONTREE1\0")
    total = 0
    for path in sorted(files):
        path_bytes = path.encode("utf-8")
        payload = files[path]
        total += len(payload)
        digest.update(struct.pack(">I", len(path_bytes)))
        digest.update(path_bytes)
        digest.update(struct.pack(">Q", len(payload)))
        digest.update(bytes.fromhex(_sha256(payload)))
    return MappingProxyType(
        {"file_count": len(files), "total_bytes": total, "sha256": digest.hexdigest()}
    )


def _snapshot_records(files: Mapping[str, bytes]) -> Mapping[str, FileRecord]:
    return MappingProxyType(
        {
            path: FileRecord(
                path=path, sha256=_sha256(payload), byte_length=len(payload)
            )
            for path, payload in files.items()
        }
    )


def _jcs_object(payload: bytes, context: str) -> Mapping[str, Any]:
    return _mapping(strict_jcs_bytes(payload, context=context), context)


def _c0_environment_authority(
    repository: GitObjectRepository,
    c0_commit: str,
    expected_sha256: str,
) -> tuple[Mapping[str, Any], Path, Path, Path, Mapping[str, Any]]:
    """Resolve the fixed Julia runtime/depot solely from the C0 environment blob."""

    blob = repository.blob_at(c0_commit, ENVIRONMENT_LOCK_PATH)
    if blob.mode != "100644" or _sha256(blob.data) != expected_sha256 or not blob.data:
        raise AuthorityError("C0 environment-lock authority differs")
    document = _jcs_object(blob.data, "C0 environment lock")
    julia = _mapping(document.get("julia"), "C0 environment Julia authority")
    execution = _mapping(
        document.get("execution"), "C0 environment execution authority"
    )
    runtime_tree = _mapping(julia.get("runtime_tree"), "C0 Julia runtime tree")
    depot_tree = _mapping(julia.get("depot_tree"), "C0 Julia depot tree")
    executable = Path(
        _string(julia.get("runtime_executable"), "C0 Julia runtime executable")
    )
    runtime_root = Path(_string(runtime_tree.get("root"), "C0 Julia runtime root"))
    depot_root = Path(_string(depot_tree.get("root"), "C0 Julia depot root"))
    if (
        not executable.is_absolute()
        or not runtime_root.is_absolute()
        or not depot_root.is_absolute()
        or not executable.is_file()
        or not depot_root.is_dir()
        or executable.parent.parent.resolve() != runtime_root.resolve()
        or _sha256(executable.read_bytes())
        != _hex(julia.get("runtime_sha256"), _SHA256, "C0 Julia runtime sha256")
        or execution.get("julia_depot_path") != str(depot_root)
    ):
        raise AuthorityError("C0 Julia runtime/depot authority differs")
    locked_environment = _mapping(
        execution.get("julia_environment"), "C0 locked Julia environment"
    )
    return document, executable, runtime_root, depot_root, locked_environment


def _collapse_recursive_roots(paths: Sequence[Path]) -> tuple[Path, ...]:
    """Independently reproduce the candidate observer's ordered root collapse."""

    unique: list[Path] = []
    for path in paths:
        absolute = Path(os.path.abspath(path))
        if absolute not in unique:
            unique.append(absolute)
    selected: list[Path] = []
    for candidate in sorted(
        unique, key=lambda item: (len(item.parts), str(item).casefold())
    ):
        if any(candidate == root or root in candidate.parents for root in selected):
            continue
        selected.append(candidate)
    return tuple(selected)


def _artifact_record(
    value: Any,
    *,
    path: str,
    compressed: bytes,
    context: str,
) -> tuple[bytes, Mapping[str, Any]]:
    record = _mapping(value, context)
    _exact_keys(
        record,
        {"path", "jcs_sha256", "gzip_sha256", "jcs_bytes", "gzip_bytes", "compression"},
        context,
    )
    if record["path"] != PurePosixPath(path).name:
        raise AuthorityError(f"{context}.path differs")
    if record["compression"] != "gzip-level-9-mtime-0":
        raise AuthorityError(f"{context}.compression differs")
    raw = decode_deterministic_gzip(compressed, context=context)
    if (
        record["jcs_sha256"] != _sha256(raw)
        or record["gzip_sha256"] != _sha256(compressed)
        or record["jcs_bytes"] != len(raw)
        or record["gzip_bytes"] != len(compressed)
    ):
        raise AuthorityError(f"{context} digest/length differs")
    return raw, _jcs_object(raw, context)


def _plain_artifact_record(
    value: Any,
    *,
    path: str,
    payload: bytes,
    context: str,
    extra_key: str | None = None,
    extra_value: str | None = None,
) -> None:
    expected = {"path", "sha256", "bytes"}
    if extra_key is not None:
        expected.add(extra_key)
    record = _mapping(value, context)
    _exact_keys(record, expected, context)
    if record["path"] != PurePosixPath(path).name and record["path"] != path:
        raise AuthorityError(f"{context}.path differs")
    if record["sha256"] != _sha256(payload) or record["bytes"] != len(payload):
        raise AuthorityError(f"{context} digest/length differs")
    if extra_key is not None and record[extra_key] != extra_value:
        raise AuthorityError(f"{context}.{extra_key} differs")


def _git_snapshot(
    root: Path,
    commit: str,
    tree: str,
    expected_paths: set[str],
    git_executable: GitExecutable,
    context: str,
) -> Mapping[str, _Blob]:
    snapshot = GitObjectRepository(root, git_executable).snapshot(commit, tree)
    if set(snapshot) != expected_paths:
        raise AuthorityError(
            f"{context} Git tree is not closed; "
            f"extra={sorted(set(snapshot) - expected_paths)}, "
            f"missing={sorted(expected_paths - set(snapshot))}"
        )
    return snapshot


def _verify_c2_introduction(
    repository: GitObjectRepository,
    *,
    stage_input_commit: str,
    c2_source_commit: str,
) -> None:
    """Require C2 to add only its frozen sources/lock to the immutable C1 tree."""

    if repository.commit_parents(c2_source_commit) != (stage_input_commit,):
        raise AuthorityError("C2 source commit is not the single child of C1 inputs")
    parent_index = dict(repository.tree_index(stage_input_commit))
    c2_index = dict(repository.tree_index(c2_source_commit))
    additions = set(C2_INTRODUCTION_PATHS)
    if additions & set(parent_index):
        raise AuthorityError("a frozen C2 addition already exists in the C1 tree")
    if set(c2_index) != set(parent_index) | additions:
        raise AuthorityError("C2 source additions differ from the frozen set")
    for path, identity in parent_index.items():
        if c2_index[path] != identity:
            raise AuthorityError(f"C2 modifies frozen C1 path {path}")
    for path in additions:
        if c2_index[path][0] != "100644":
            raise AuthorityError(f"C2 source is not a regular blob: {path}")


def _verify_c2_equivalence_evidence(
    repository: GitObjectRepository,
    *,
    c2_source_commit: str,
    stage_input: StageInputRecord,
    candidate_run: CandidateRunRecord,
) -> None:
    """Replay the result-blind two-fixture L0 default-equivalence proof."""

    def records(paths: tuple[str, ...], context: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in sorted(paths):
            blob = repository.blob_at(c2_source_commit, path)
            if blob.mode != "100644" or not blob.data:
                raise AuthorityError(
                    f"{context} is not a nonempty regular blob: {path}"
                )
            result.append(
                {
                    "path": path,
                    "sha256": _sha256(blob.data),
                    "byte_length": len(blob.data),
                }
            )
        return result

    def checked_records(
        value: Any, expected: Sequence[Mapping[str, Any]], context: str
    ) -> list[dict[str, Any]]:
        items = _array(value, context)
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(items):
            record = _mapping(raw, f"{context}[{index}]")
            _exact_keys(record, _FILE_RECORD_KEYS, f"{context}[{index}]")
            normalized.append(
                {
                    "path": _normal_path(record["path"], f"{context}[{index}].path"),
                    "sha256": _hex(
                        record["sha256"], _SHA256, f"{context}[{index}].sha256"
                    ),
                    "byte_length": _integer(
                        record["byte_length"],
                        f"{context}[{index}].byte_length",
                        minimum=1,
                    ),
                }
            )
        if normalized != list(expected):
            raise AuthorityError(f"{context} differs from immutable authority")
        return normalized

    runtime_records = records(C2_REQUIRED_SOURCE_PATHS, "C2 runtime source")
    test_records = records(C2_TEST_SOURCE_PATHS, "C2 test source")
    evidence_blob = repository.blob_at(c2_source_commit, C2_EQUIVALENCE_EVIDENCE_PATH)
    if evidence_blob.mode != "100644":
        raise AuthorityError("C2 default-equivalence evidence is not a regular blob")
    evidence = _jcs_object(evidence_blob.data, "C2 default-equivalence evidence")
    evidence_keys = {
        "schema_version",
        "experiment_id",
        "card_sha256",
        "stage",
        "stage_input_anchor_commit",
        "stage_input_anchor_sha256",
        "preimplementation_lock_sha256",
        "local_options_sha256",
        "claim_reference",
        "baseline_variant",
        "candidate_mechanism_enabled",
        "runtime_sources",
        "test_sources",
        "fixture_sources",
        "golden_sources",
        "c0_reference_authority",
        "source_manifest_sha256",
        "comparisons",
        "comparison_manifest_sha256",
        "isolated_test_execution",
        "isolated_test_execution_manifest_sha256",
        "passed",
    }
    _exact_keys(evidence, evidence_keys, "C2 default-equivalence evidence")
    execution_lock = candidate_run.candidate_execution_lock

    lock_path = "research/experiments/EXP-LOCAL-003/preimplementation-lock.json"
    preimplementation_blob = repository.blob_at(
        stage_input.source_lock_commit, lock_path
    )
    if (
        preimplementation_blob.mode != "100644"
        or _sha256(preimplementation_blob.data)
        != stage_input.preimplementation_lock_sha256
    ):
        raise AuthorityError("C2 evidence cannot resolve immutable C0 lock")
    preimplementation = _jcs_object(
        preimplementation_blob.data, "C0 preimplementation lock"
    )
    c0_commit = _hex(
        preimplementation.get("c0_source_commit"), _GIT_OID, "C0 source commit"
    )
    c0_tree = _hex(preimplementation.get("c0_source_tree"), _GIT_OID, "C0 source tree")
    environment_lock_sha = _hex(
        preimplementation.get("environment_lock_sha256"),
        _SHA256,
        "C0 environment-lock sha256",
    )
    local_options_sha = _hex(
        preimplementation.get("local_options_sha256"),
        _SHA256,
        "C0 local-options sha256",
    )
    if repository.commit_tree(c0_commit) != c0_tree:
        raise AuthorityError("C0 source commit/tree binding differs")
    (
        _environment_document,
        c2_julia_executable,
        c2_runtime_root,
        c2_depot_root,
        c2_locked_environment,
    ) = _c0_environment_authority(repository, c0_commit, environment_lock_sha)
    c2_environment_keys = (
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
    c2_base_environment: dict[str, str] = {
        key: _string(
            c2_locked_environment.get(key), f"C0 locked Julia environment {key}"
        )
        for key in c2_environment_keys
    }
    c2_base_environment.update(
        {
            "JULIA_DEPOT_PATH": str(c2_depot_root),
            "JULIA_PKG_PRECOMPILE_AUTO": "0",
        }
    )

    claim_reference = _string(evidence["claim_reference"], "claim_reference")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", claim_reference) is None:
        raise AuthorityError("C2 evidence claim reference is malformed")
    if (
        evidence["schema_version"]
        != "geotarget.exp-local-003.c2-default-equivalence/v1"
        or evidence["experiment_id"] != EXPERIMENT_ID
        or evidence["card_sha256"] != CARD_SHA256
        or evidence["stage"] != "development"
        or evidence["stage_input_anchor_commit"] != stage_input.anchor_commit
        or evidence["stage_input_anchor_sha256"] != stage_input.anchor_file.sha256
        or evidence["preimplementation_lock_sha256"]
        != stage_input.preimplementation_lock_sha256
        or evidence["local_options_sha256"] != local_options_sha
        or evidence["local_options_sha256"] != execution_lock["local_options_sha256"]
        or evidence["baseline_variant"] != "L0-SEMANTIC"
        or evidence["candidate_mechanism_enabled"] is not False
        or evidence["passed"] is not True
    ):
        raise AuthorityError("C2 default-equivalence identity/binding differs")
    checked_records(evidence["runtime_sources"], runtime_records, "runtime_sources")
    checked_records(evidence["test_sources"], test_records, "test_sources")

    fixture_records = records(C0_EQUIVALENCE_FIXTURE_PATHS, "C0 fixture")
    golden_records = records(C0_EQUIVALENCE_GOLDEN_PATHS, "C0 golden")
    # The fixture/golden records are C0 blobs, not C2 redefinitions.
    for record in (*fixture_records, *golden_records):
        blob = repository.blob_at(c0_commit, record["path"])
        if (
            blob.mode != "100644"
            or _sha256(blob.data) != record["sha256"]
            or len(blob.data) != record["byte_length"]
        ):
            raise AuthorityError(f"C0 equivalence blob changed: {record['path']}")
    checked_records(evidence["fixture_sources"], fixture_records, "fixture_sources")
    checked_records(evidence["golden_sources"], golden_records, "golden_sources")

    protocol_records: list[dict[str, Any]] = []
    for path in sorted(C0_EQUIVALENCE_PROTOCOL_PATHS):
        blob = repository.blob_at(c0_commit, path)
        if blob.mode != "100644" or not blob.data:
            raise AuthorityError(f"C0 equivalence protocol blob differs: {path}")
        protocol_records.append(
            {"path": path, "sha256": _sha256(blob.data), "byte_length": len(blob.data)}
        )
    reference = _mapping(evidence["c0_reference_authority"], "C0 reference authority")
    reference_keys = {
        "source_lock_commit",
        "c0_source_commit",
        "c0_source_tree",
        "environment_lock_sha256",
        "capsule_origin",
        "capsule_files",
        "capsule_manifest_sha256",
        "protocol_sources",
        "protocol_manifest_sha256",
        "reference_child_c2_source_access",
    }
    _exact_keys(reference, reference_keys, "C0 reference authority")
    if (
        reference["source_lock_commit"] != stage_input.source_lock_commit
        or reference["c0_source_commit"] != c0_commit
        or reference["c0_source_tree"] != c0_tree
        or reference["environment_lock_sha256"] != environment_lock_sha
        or reference["capsule_origin"] != "immutable-main-git-c0-source-tree"
        or reference["reference_child_c2_source_access"] != "kernel-denied"
    ):
        raise AuthorityError("C0 reference authority binding differs")
    checked_records(
        reference["protocol_sources"], protocol_records, "C0 protocol_sources"
    )
    if reference["protocol_manifest_sha256"] != _sha256(
        canonical_bytes(protocol_records)
    ):
        raise AuthorityError("C0 protocol manifest digest differs")

    c0_index = repository.tree_index(c0_commit)
    fixed_capsule = {
        "julia/Project.toml",
        "julia/Manifest.toml",
        C0_EQUIVALENCE_CHILD_PATH,
        C0_EQUIVALENCE_PROTOCOL_PATHS[0],
        *C0_EQUIVALENCE_FIXTURE_PATHS,
    }
    package_roots = (
        "julia/GeoTargetBase",
        "julia/GeoTargetCore",
        "julia/GeoTargetGeometry",
    )
    selected_capsule_paths: list[str] = []
    for path, (mode, _oid) in c0_index.items():
        selected = path in fixed_capsule or any(
            path == f"{root}/Project.toml" or path.startswith(f"{root}/src/")
            for root in package_roots
        )
        if not selected:
            continue
        if mode != "100644":
            raise AuthorityError(f"C0 capsule source is not a regular blob: {path}")
        selected_capsule_paths.append(path)
    capsule_paths = tuple(sorted(selected_capsule_paths))
    if not fixed_capsule.issubset(capsule_paths):
        raise AuthorityError("C0 reference capsule is missing a fixed source")
    capsule_records: list[dict[str, Any]] = []
    for path in capsule_paths:
        blob = repository.blob_at(c0_commit, path)
        capsule_records.append(
            {"path": path, "sha256": _sha256(blob.data), "byte_length": len(blob.data)}
        )
    checked_records(reference["capsule_files"], capsule_records, "C0 capsule_files")
    if reference["capsule_manifest_sha256"] != _sha256(
        canonical_bytes(capsule_records)
    ):
        raise AuthorityError("C0 capsule manifest digest differs")

    source_manifest = {
        "runtime_sources": runtime_records,
        "test_sources": test_records,
        "fixture_sources": fixture_records,
        "golden_sources": golden_records,
        "c0_protocol_sources": protocol_records,
    }
    if evidence["source_manifest_sha256"] != _sha256(canonical_bytes(source_manifest)):
        raise AuthorityError("C2 evidence source-manifest digest differs")

    def verify_execution(
        value: Any,
        mode: str,
        context: str,
        *,
        fixture_index: int,
        fixture_path: str,
        golden_path: str,
    ) -> Mapping[str, Any]:
        execution = _mapping(value, context)
        keys = {
            "mode",
            "mechanism_source_granted",
            "command",
            "environment",
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
        _exact_keys(execution, keys, context)
        if (
            execution["mode"] != mode
            or execution["mechanism_source_granted"]
            is not (mode == "mechanism-disabled")
            or execution["return_code"] != 0
            or execution["termination_reason"] != "completed"
            or execution["total_processes"] != 1
            or execution["terminated_processes"] != 0
        ):
            raise AuthorityError(f"{context} process boundary differs")
        command = _array(execution["command"], f"{context}.command")
        sandbox = _mapping(execution["sandbox"], f"{context}.sandbox")
        scratch = Path(
            _string(sandbox.get("scratch_directory"), f"{context}.scratch_directory")
        )
        expected_scratch = scratch.parent / f"scratch-{fixture_index}-{mode}"
        capsule_root = scratch.parent / "immutable-c0-baseline-capsule"
        expected_command = [
            str(c2_julia_executable),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            f"--project={capsule_root / 'julia'}",
            str(capsule_root.joinpath(*C0_EQUIVALENCE_CHILD_PATH.split("/"))),
            mode,
            str(capsule_root.joinpath(*fixture_path.split("/"))),
            str(capsule_root.joinpath(*C0_EQUIVALENCE_PROTOCOL_PATHS[0].split("/"))),
        ]
        if mode == "mechanism-disabled":
            expected_command.append(
                str(_REPOSITORY_ROOT.joinpath(*C2_REQUIRED_SOURCE_PATHS[0].split("/")))
            )
        if (
            not scratch.is_absolute()
            or scratch != expected_scratch
            or command != expected_command
        ):
            raise AuthorityError(f"{context} command/scratch boundary differs")

        request_environment = dict(c2_base_environment)
        request_environment["JULIA_PROJECT"] = str(capsule_root / "julia")
        environment_by_folded_name = {
            name.casefold(): (name, value)
            for name, value in request_environment.items()
        }
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        environment_defaults = {
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
        for name, value in environment_defaults.items():
            environment_by_folded_name.setdefault(name.casefold(), (name, value))
        expected_environment = [
            {"name": name, "value": value}
            for name, value in sorted(
                environment_by_folded_name.values(),
                key=lambda item: (item[0].casefold(), item[0]),
            )
        ]
        environment = _array(execution["environment"], f"{context}.environment")
        normalized_environment: list[dict[str, str]] = []
        for index, item in enumerate(environment):
            entry = _mapping(item, f"{context}.environment[{index}]")
            _exact_keys(entry, {"name", "value"}, f"{context}.environment[{index}]")
            normalized_environment.append(
                {
                    "name": _string(
                        entry["name"], f"{context}.environment[{index}].name"
                    ),
                    "value": _string(
                        entry["value"], f"{context}.environment[{index}].value"
                    ),
                }
            )
        if normalized_environment != expected_environment:
            raise AuthorityError(f"{context} environment differs from C0 authority")
        stdout = _mapping(execution["stdout"], f"{context}.stdout")
        stderr = _mapping(execution["stderr"], f"{context}.stderr")
        for stream, stream_context in ((stdout, "stdout"), (stderr, "stderr")):
            _exact_keys(
                stream, {"sha256", "byte_length"}, f"{context}.{stream_context}"
            )
            _hex(stream["sha256"], _SHA256, f"{context}.{stream_context}.sha256")
            _integer(
                stream["byte_length"],
                f"{context}.{stream_context}.byte_length",
                minimum=0,
            )
        if (
            stderr
            != {
                "sha256": _sha256(b""),
                "byte_length": 0,
            }
            or stdout["byte_length"] == 0
        ):
            raise AuthorityError(f"{context} stream evidence differs")
        _integer(execution["wall_time_nanoseconds"], f"{context}.wall", minimum=1)
        _integer(execution["total_user_time_100ns"], f"{context}.user", minimum=0)
        _integer(execution["total_kernel_time_100ns"], f"{context}.kernel", minimum=0)
        accounting = _mapping(execution["io_accounting"], f"{context}.io_accounting")
        accounting_keys = {
            "read_operation_count",
            "write_operation_count",
            "other_operation_count",
            "read_transfer_count",
            "write_transfer_count",
            "other_transfer_count",
        }
        _exact_keys(accounting, accounting_keys, f"{context}.io_accounting")
        for key in accounting_keys:
            _integer(accounting[key], f"{context}.io_accounting.{key}", minimum=0)
        sandbox_keys = {
            "schema_version",
            "claim_reference",
            "profile_name",
            "package_sid",
            "profile_storage_path",
            "capabilities",
            "allowed_read_paths",
            "read_identity_manifest_entry_count",
            "read_identity_manifest_sha256",
            "scratch_directory",
            "environment",
            "inherited_handle_roles",
            "process_id",
            "token_is_appcontainer",
            "token_appcontainer_sid_verified",
            "token_integrity_rid",
            "token_elevated",
            "token_capability_count",
            "access_probes",
            "denied_probe_entry_count",
            "denied_probe_manifest_sha256",
            "read_only_probe_entry_count",
            "read_only_probe_manifest_sha256",
            "scratch_access_probe_manifest_sha256",
            "max_processes",
            "child_process_restricted",
            "job_assigned_at_creation",
            "job_membership_verified",
            "job_limit_flags",
            "breakaway_allowed",
            "kill_on_job_close",
            "job_empty",
            "acl_entry_count",
            "original_acl_manifest_sha256",
            "restored_acl_manifest_sha256",
            "acl_exactly_restored",
            "scratch_emptied",
            "profile_deleted",
            "profile_storage_deleted",
        }
        _exact_keys(sandbox, sandbox_keys, f"{context}.sandbox")
        expected_allowed_read = [str(c2_runtime_root), str(c2_depot_root)]
        for name in ("packages", "artifacts"):
            child = c2_depot_root / name
            if child.exists():
                expected_allowed_read.append(str(child))
        expected_allowed_read.append(str(capsule_root))
        if mode == "mechanism-disabled":
            expected_allowed_read.append(
                str(_REPOSITORY_ROOT.joinpath(*C2_REQUIRED_SOURCE_PATHS[0].split("/")))
            )
        if (
            sandbox["schema_version"]
            != "geotarget.exp-local-003.appcontainer-attestation/v2"
            or sandbox["claim_reference"] != claim_reference
            or sandbox["capabilities"] != []
            or sandbox["environment"] != expected_environment
            or sandbox["allowed_read_paths"] != expected_allowed_read
            or sandbox["inherited_handle_roles"] != ["stdin", "stdout", "stderr"]
            or sandbox["token_is_appcontainer"] is not True
            or sandbox["token_appcontainer_sid_verified"] is not True
            or sandbox["token_integrity_rid"] != 4096
            or sandbox["token_elevated"] is not False
            or sandbox["token_capability_count"] != 0
            or sandbox["max_processes"] != 1
            or sandbox["child_process_restricted"] is not True
            or sandbox["job_assigned_at_creation"] is not True
            or sandbox["job_membership_verified"] is not True
            or sandbox["job_limit_flags"] != 0x00002008
            or sandbox["breakaway_allowed"] is not False
            or sandbox["kill_on_job_close"] is not True
            or sandbox["job_empty"] is not True
            or sandbox["acl_exactly_restored"] is not True
            or sandbox["scratch_emptied"] is not True
            or sandbox["profile_deleted"] is not True
            or sandbox["profile_storage_deleted"] is not True
            or sandbox["original_acl_manifest_sha256"]
            != sandbox["restored_acl_manifest_sha256"]
        ):
            raise AuthorityError(f"{context} AppContainer attestation differs")
        _integer(sandbox["process_id"], f"{context}.sandbox.process_id", minimum=1)
        profile_name = _string(
            sandbox["profile_name"], f"{context}.sandbox.profile_name"
        )
        package_sid = _string(sandbox["package_sid"], f"{context}.sandbox.package_sid")
        profile_storage = _string(
            sandbox["profile_storage_path"],
            f"{context}.sandbox.profile_storage_path",
        )
        if (
            not profile_name.startswith("GeoTarget.EXPLOCAL003.")
            or re.fullmatch(r"S-[0-9-]+", package_sid) is None
            or os.path.lexists(profile_storage)
        ):
            raise AuthorityError(f"{context} AppContainer identity/cleanup differs")
        for key in (
            "read_identity_manifest_sha256",
            "denied_probe_manifest_sha256",
            "read_only_probe_manifest_sha256",
            "scratch_access_probe_manifest_sha256",
            "original_acl_manifest_sha256",
            "restored_acl_manifest_sha256",
        ):
            _hex(sandbox[key], _SHA256, f"{context}.sandbox.{key}")
        _integer(
            sandbox["read_identity_manifest_entry_count"],
            f"{context}.sandbox.read_identity_manifest_entry_count",
            minimum=1,
        )
        read_count = _integer(
            sandbox["read_only_probe_entry_count"],
            f"{context}.sandbox.read_only_probe_entry_count",
            minimum=1,
        )
        identity_count = _integer(
            sandbox["read_identity_manifest_entry_count"],
            f"{context}.sandbox.read_identity_manifest_entry_count",
            minimum=1,
        )
        acl_count = _integer(
            sandbox["acl_entry_count"],
            f"{context}.sandbox.acl_entry_count",
            minimum=2,
        )
        if identity_count != read_count or acl_count != read_count + 1:
            raise AuthorityError(f"{context} ACL accounting differs")
        probes = _array(sandbox["access_probes"], f"{context}.sandbox.access_probes")
        experiment_root = _REPOSITORY_ROOT.joinpath(
            "research", "experiments", EXPERIMENT_ID
        )
        mechanism_state = "denied" if mode == "reference" else "allowed"
        expected_probe_states = (
            (command[8], "allowed", "allowed", 0),
            (
                str(_REPOSITORY_ROOT.joinpath(*golden_path.split("/"))),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C2_REQUIRED_SOURCE_PATHS[0].split("/"))),
                mechanism_state,
                mechanism_state,
                5 if mode == "reference" else 0,
            ),
            (str(experiment_root), "denied", "denied", 5),
            (
                str(
                    _REPOSITORY_ROOT.joinpath(*C2_EQUIVALENCE_EVIDENCE_PATH.split("/"))
                ),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C1_CANDIDATE_OUTCOME_PATH.split("/"))),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C1_STAGE_VAULT_ANCHOR_PATH.split("/"))),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C1_ATTEMPT_CLAIM_PATH.split("/"))),
                "denied",
                "denied",
                5,
            ),
            *(
                (str(root), "denied", "denied", 5)
                for root in _c1_external_fixed_roots()
            ),
            (str(_REPOSITORY_ROOT / ".git"), "denied", "denied", 5),
        )
        if len(probes) != len(expected_probe_states):
            raise AuthorityError(f"{context} access-probe count differs")
        for index, (raw_probe, expected_probe) in enumerate(
            zip(probes, expected_probe_states, strict=True)
        ):
            probe = _mapping(raw_probe, f"{context}.sandbox.access_probes[{index}]")
            _exact_keys(
                probe,
                {"path", "expected", "observed", "winerror"},
                f"{context}.sandbox.access_probes[{index}]",
            )
            if (
                probe["path"],
                probe["expected"],
                probe["observed"],
                probe["winerror"],
            ) != expected_probe:
                raise AuthorityError(f"{context} kernel access probe differs")
        denied_target_count = sum(
            expected == "denied" for _, expected, _, _ in expected_probe_states
        )
        _integer(
            sandbox["denied_probe_entry_count"],
            f"{context}.sandbox.denied_probe_entry_count",
            minimum=denied_target_count,
        )
        if not command[8].endswith(
            str(Path(*fixture_path.split("/")).as_posix()).replace("/", os.sep)
        ):
            raise AuthorityError(f"{context} fixture command path differs")
        return execution

    def verify_isolated_test_execution(value: Any) -> tuple[str, str, str]:
        context = "C2 isolated-test execution"
        execution = _mapping(value, context)
        execution_keys = {
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
        _exact_keys(execution, execution_keys, context)
        if evidence["isolated_test_execution_manifest_sha256"] != _sha256(
            canonical_bytes(execution)
        ):
            raise AuthorityError("C2 isolated-test execution manifest differs")
        if (
            execution["mode"] != "isolated-test"
            or execution["mechanism_source_granted"] is not True
            or execution["return_code"] != 0
            or execution["termination_reason"] != "completed"
            or execution["total_processes"] != 1
            or execution["terminated_processes"] != 0
        ):
            raise AuthorityError(f"{context} process boundary differs")
        command = _array(execution["command"], f"{context}.command")
        expected_command = [
            str(c2_julia_executable),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            f"--project={_REPOSITORY_ROOT / 'julia'}",
            str(_REPOSITORY_ROOT.joinpath(*C2_TEST_SOURCE_PATHS[0].split("/"))),
        ]
        if command != expected_command:
            raise AuthorityError(f"{context} command differs")
        sandbox = _mapping(execution["sandbox"], f"{context}.sandbox")
        scratch = Path(
            _string(sandbox.get("scratch_directory"), f"{context}.scratch_directory")
        )
        if (
            not scratch.is_absolute()
            or scratch.name != "scratch-isolated-test"
            or os.path.lexists(scratch)
        ):
            raise AuthorityError(f"{context} scratch boundary differs")
        request_environment = dict(c2_base_environment)
        request_environment["JULIA_PROJECT"] = str(_REPOSITORY_ROOT / "julia")
        environment_by_folded_name = {
            name.casefold(): (name, value)
            for name, value in request_environment.items()
        }
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        environment_defaults = {
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
        for name, environment_value in environment_defaults.items():
            environment_by_folded_name.setdefault(
                name.casefold(), (name, environment_value)
            )
        expected_environment = [
            {"name": name, "value": environment_value}
            for name, environment_value in sorted(
                environment_by_folded_name.values(),
                key=lambda item: (item[0].casefold(), item[0]),
            )
        ]
        environment = _array(execution["environment"], f"{context}.environment")
        normalized_environment: list[dict[str, str]] = []
        for index, raw in enumerate(environment):
            entry = _mapping(raw, f"{context}.environment[{index}]")
            _exact_keys(entry, {"name", "value"}, f"{context}.environment[{index}]")
            normalized_environment.append(
                {
                    "name": _string(
                        entry["name"], f"{context}.environment[{index}].name"
                    ),
                    "value": _string(
                        entry["value"], f"{context}.environment[{index}].value"
                    ),
                }
            )
        if normalized_environment != expected_environment:
            raise AuthorityError(f"{context} environment differs")
        project_paths = ("julia/Project.toml", "julia/Manifest.toml")
        package_paths = tuple(
            path
            for package in (
                "julia/GeoTargetBase",
                "julia/GeoTargetCore",
                "julia/GeoTargetGeometry",
            )
            for path in (f"{package}/Project.toml", f"{package}/src")
        )
        expected_grants = [
            {"path": str(c2_runtime_root), "recursive": True},
            {"path": str(c2_depot_root), "recursive": False},
            {"path": str(c2_depot_root / "packages"), "recursive": True},
            {"path": str(c2_depot_root / "artifacts"), "recursive": True},
            {"path": str(_REPOSITORY_ROOT), "recursive": False},
            {"path": str(_REPOSITORY_ROOT / "julia"), "recursive": False},
            *(
                {
                    "path": str(_REPOSITORY_ROOT.joinpath(*path.split("/"))),
                    "recursive": False,
                }
                for path in project_paths
            ),
            *(
                {
                    "path": str(_REPOSITORY_ROOT.joinpath(*path.split("/"))),
                    "recursive": path.endswith("/src"),
                }
                for path in package_paths
            ),
            {
                "path": str(
                    _REPOSITORY_ROOT.joinpath(*C2_TEST_SOURCE_PATHS[0].split("/"))
                ),
                "recursive": False,
            },
        ]
        grants = _array(execution["read_grants"], f"{context}.read_grants")
        normalized_grants: list[dict[str, Any]] = []
        for index, raw in enumerate(grants):
            grant = _mapping(raw, f"{context}.read_grants[{index}]")
            _exact_keys(grant, {"path", "recursive"}, f"{context}.read_grants[{index}]")
            recursive = grant["recursive"]
            if not isinstance(recursive, bool):
                raise AuthorityError(
                    f"{context}.read_grants[{index}] recursion differs"
                )
            normalized_grants.append(
                {
                    "path": _string(
                        grant["path"], f"{context}.read_grants[{index}].path"
                    ),
                    "recursive": recursive,
                }
            )
        if normalized_grants != expected_grants:
            raise AuthorityError(f"{context} read grants differ")
        stdout = _mapping(execution["stdout"], f"{context}.stdout")
        stderr = _mapping(execution["stderr"], f"{context}.stderr")
        for stream, stream_name in ((stdout, "stdout"), (stderr, "stderr")):
            _exact_keys(stream, {"sha256", "byte_length"}, f"{context}.{stream_name}")
            _hex(stream["sha256"], _SHA256, f"{context}.{stream_name}.sha256")
            _integer(
                stream["byte_length"],
                f"{context}.{stream_name}.byte_length",
                minimum=0,
            )
        if stderr != {"sha256": _sha256(b""), "byte_length": 0}:
            raise AuthorityError(f"{context} stderr differs")
        _integer(execution["wall_time_nanoseconds"], f"{context}.wall", minimum=1)
        _integer(execution["total_user_time_100ns"], f"{context}.user", minimum=0)
        _integer(execution["total_kernel_time_100ns"], f"{context}.kernel", minimum=0)
        accounting = _mapping(execution["io_accounting"], f"{context}.io_accounting")
        accounting_keys = {
            "read_operation_count",
            "write_operation_count",
            "other_operation_count",
            "read_transfer_count",
            "write_transfer_count",
            "other_transfer_count",
        }
        _exact_keys(accounting, accounting_keys, f"{context}.io_accounting")
        for key in accounting_keys:
            _integer(accounting[key], f"{context}.io_accounting.{key}", minimum=0)
        sandbox_keys = {
            "schema_version",
            "claim_reference",
            "profile_name",
            "package_sid",
            "profile_storage_path",
            "capabilities",
            "allowed_read_paths",
            "read_identity_manifest_entry_count",
            "read_identity_manifest_sha256",
            "scratch_directory",
            "environment",
            "inherited_handle_roles",
            "process_id",
            "token_is_appcontainer",
            "token_appcontainer_sid_verified",
            "token_integrity_rid",
            "token_elevated",
            "token_capability_count",
            "access_probes",
            "denied_probe_entry_count",
            "denied_probe_manifest_sha256",
            "read_only_probe_entry_count",
            "read_only_probe_manifest_sha256",
            "scratch_access_probe_manifest_sha256",
            "max_processes",
            "child_process_restricted",
            "job_assigned_at_creation",
            "job_membership_verified",
            "job_limit_flags",
            "breakaway_allowed",
            "kill_on_job_close",
            "job_empty",
            "acl_entry_count",
            "original_acl_manifest_sha256",
            "restored_acl_manifest_sha256",
            "acl_exactly_restored",
            "scratch_emptied",
            "profile_deleted",
            "profile_storage_deleted",
        }
        _exact_keys(sandbox, sandbox_keys, f"{context}.sandbox")
        if (
            sandbox["schema_version"]
            != "geotarget.exp-local-003.appcontainer-attestation/v2"
            or sandbox["claim_reference"] != claim_reference
            or sandbox["capabilities"] != []
            or sandbox["allowed_read_paths"]
            != [grant["path"] for grant in expected_grants]
            or sandbox["environment"] != expected_environment
            or sandbox["inherited_handle_roles"] != ["stdin", "stdout", "stderr"]
            or sandbox["token_is_appcontainer"] is not True
            or sandbox["token_appcontainer_sid_verified"] is not True
            or sandbox["token_integrity_rid"] != 4096
            or sandbox["token_elevated"] is not False
            or sandbox["token_capability_count"] != 0
            or sandbox["max_processes"] != 1
            or sandbox["child_process_restricted"] is not True
            or sandbox["job_assigned_at_creation"] is not True
            or sandbox["job_membership_verified"] is not True
            or sandbox["job_limit_flags"] != 0x00002008
            or sandbox["breakaway_allowed"] is not False
            or sandbox["kill_on_job_close"] is not True
            or sandbox["job_empty"] is not True
            or sandbox["acl_exactly_restored"] is not True
            or sandbox["scratch_emptied"] is not True
            or sandbox["profile_deleted"] is not True
            or sandbox["profile_storage_deleted"] is not True
            or sandbox["original_acl_manifest_sha256"]
            != sandbox["restored_acl_manifest_sha256"]
        ):
            raise AuthorityError(f"{context} AppContainer attestation differs")
        _integer(sandbox["process_id"], f"{context}.sandbox.process_id", minimum=1)
        profile_name = _string(sandbox["profile_name"], f"{context}.profile_name")
        package_sid = _string(sandbox["package_sid"], f"{context}.package_sid")
        profile_storage = _string(
            sandbox["profile_storage_path"], f"{context}.profile_storage_path"
        )
        if (
            not profile_name.startswith("GeoTarget.EXPLOCAL003.")
            or re.fullmatch(r"S-[0-9-]+", package_sid) is None
            or os.path.lexists(profile_storage)
        ):
            raise AuthorityError(f"{context} profile identity/cleanup differs")
        for key in (
            "read_identity_manifest_sha256",
            "denied_probe_manifest_sha256",
            "read_only_probe_manifest_sha256",
            "scratch_access_probe_manifest_sha256",
            "original_acl_manifest_sha256",
            "restored_acl_manifest_sha256",
        ):
            _hex(sandbox[key], _SHA256, f"{context}.sandbox.{key}")
        read_count = _integer(
            sandbox["read_only_probe_entry_count"],
            f"{context}.sandbox.read_only_probe_entry_count",
            minimum=1,
        )
        identity_count = _integer(
            sandbox["read_identity_manifest_entry_count"],
            f"{context}.sandbox.read_identity_manifest_entry_count",
            minimum=1,
        )
        acl_count = _integer(
            sandbox["acl_entry_count"],
            f"{context}.sandbox.acl_entry_count",
            minimum=2,
        )
        if identity_count != read_count or acl_count != read_count + 1:
            raise AuthorityError(f"{context} read identity/ACL accounting differs")
        expected_probe_states = (
            (expected_command[6], "allowed", "allowed", 0),
            (
                str(_REPOSITORY_ROOT.joinpath(*C2_REQUIRED_SOURCE_PATHS[0].split("/"))),
                "allowed",
                "allowed",
                0,
            ),
            (
                str(_REPOSITORY_ROOT / "research" / "experiments" / EXPERIMENT_ID),
                "denied",
                "denied",
                5,
            ),
            (
                str(
                    _REPOSITORY_ROOT.joinpath(*C2_EQUIVALENCE_EVIDENCE_PATH.split("/"))
                ),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C1_CANDIDATE_OUTCOME_PATH.split("/"))),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C1_STAGE_VAULT_ANCHOR_PATH.split("/"))),
                "denied",
                "denied",
                5,
            ),
            (
                str(_REPOSITORY_ROOT.joinpath(*C1_ATTEMPT_CLAIM_PATH.split("/"))),
                "denied",
                "denied",
                5,
            ),
            *(
                (str(root), "denied", "denied", 5)
                for root in _c1_external_fixed_roots()
            ),
            (str(_REPOSITORY_ROOT / ".git"), "denied", "denied", 5),
        )
        probes = _array(sandbox["access_probes"], f"{context}.sandbox.access_probes")
        if len(probes) != len(expected_probe_states):
            raise AuthorityError(f"{context} access-probe count differs")
        for index, (raw_probe, expected_probe) in enumerate(
            zip(probes, expected_probe_states, strict=True)
        ):
            probe = _mapping(raw_probe, f"{context}.sandbox.access_probes[{index}]")
            _exact_keys(
                probe,
                {"path", "expected", "observed", "winerror"},
                f"{context}.sandbox.access_probes[{index}]",
            )
            if (
                probe["path"],
                probe["expected"],
                probe["observed"],
                probe["winerror"],
            ) != expected_probe:
                raise AuthorityError(f"{context} recursive namespace probe differs")
        denied_count = sum(item[1] == "denied" for item in expected_probe_states)
        _integer(
            sandbox["denied_probe_entry_count"],
            f"{context}.sandbox.denied_probe_entry_count",
            minimum=denied_count,
        )
        return profile_name, package_sid, str(scratch)

    comparisons = _array(evidence["comparisons"], "C2 evidence comparisons")
    expected_fixture_ids = ("JULIA-CORE-DEFAULT", "OPAQUE-PLUGIN-DEFAULT")
    if len(comparisons) != len(expected_fixture_ids):
        raise AuthorityError("C2 evidence comparison count differs")
    comparison_keys = {
        "fixture_id",
        "fixture",
        "golden",
        "reference_execution",
        "mechanism_disabled_execution",
        "golden_output_sha256",
        "reference_output_sha256",
        "mechanism_disabled_output_sha256",
        "output_byte_length",
        "reference_matches_golden",
        "mechanism_disabled_matches_golden",
        "byte_identical",
    }
    sandbox_identities: list[tuple[str, str, str]] = []
    for index, (value, fixture_id) in enumerate(
        zip(comparisons, expected_fixture_ids, strict=True)
    ):
        comparison = _mapping(value, f"C2 evidence comparison {index}")
        _exact_keys(comparison, comparison_keys, f"C2 evidence comparison {index}")
        if comparison["fixture_id"] != fixture_id:
            raise AuthorityError("C2 evidence fixture order/identity differs")
        fixture = checked_records(
            [comparison["fixture"]],
            [fixture_records[index]],
            f"comparison {index} fixture",
        )[0]
        golden = checked_records(
            [comparison["golden"]],
            [golden_records[index]],
            f"comparison {index} golden",
        )[0]
        reference_execution = verify_execution(
            comparison["reference_execution"],
            "reference",
            f"comparison {index} reference",
            fixture_index=index,
            fixture_path=fixture["path"],
            golden_path=golden["path"],
        )
        disabled_execution = verify_execution(
            comparison["mechanism_disabled_execution"],
            "mechanism-disabled",
            f"comparison {index} mechanism-disabled",
            fixture_index=index,
            fixture_path=fixture["path"],
            golden_path=golden["path"],
        )
        for execution in (reference_execution, disabled_execution):
            sandbox = _mapping(execution["sandbox"], "comparison sandbox identity")
            sandbox_identities.append(
                (
                    _string(sandbox["profile_name"], "sandbox profile name"),
                    _string(sandbox["package_sid"], "sandbox package SID"),
                    _string(sandbox["scratch_directory"], "sandbox scratch directory"),
                )
            )
        del fixture
        golden_blob = repository.blob_at(c0_commit, golden["path"])
        golden_sha = _sha256(golden_blob.data)
        output_length = len(golden_blob.data)
        if (
            comparison["golden_output_sha256"] != golden_sha
            or comparison["reference_output_sha256"] != golden_sha
            or comparison["mechanism_disabled_output_sha256"] != golden_sha
            or comparison["output_byte_length"] != output_length
            or reference_execution["stdout"]
            != {"sha256": golden_sha, "byte_length": output_length}
            or disabled_execution["stdout"]
            != {"sha256": golden_sha, "byte_length": output_length}
            or comparison["reference_matches_golden"] is not True
            or comparison["mechanism_disabled_matches_golden"] is not True
            or comparison["byte_identical"] is not True
        ):
            raise AuthorityError("C2 evidence does not prove C0-golden byte identity")
    sandbox_identities.append(
        verify_isolated_test_execution(evidence["isolated_test_execution"])
    )
    if (
        len(sandbox_identities) != 5
        or len({value[0] for value in sandbox_identities}) != 5
        or len({value[1] for value in sandbox_identities}) != 5
        or len({value[2] for value in sandbox_identities}) != 5
    ):
        raise AuthorityError("C2 evidence did not use five fresh AppContainers")
    if evidence["comparison_manifest_sha256"] != _sha256(canonical_bytes(comparisons)):
        raise AuthorityError("C2 evidence comparison-manifest digest differs")
    allowed_sources = [
        dict(_mapping(item, f"candidate allowed source {index}"))
        for index, item in enumerate(execution_lock["allowed_sources"])
    ]
    expected_allowed_sources = [
        {"path": item["path"], "sha256": item["sha256"]} for item in runtime_records
    ]
    if allowed_sources != expected_allowed_sources:
        raise AuthorityError("candidate runtime allowlist is not the exact C2 set")


def _c1_accounting(value: Any, context: str) -> Mapping[str, Any]:
    document = _mapping(value, context)
    keys = {
        "parent_process_cpu_nanoseconds_decimal",
        "validation_child_cpu_nanoseconds_decimal",
        "julia_capture_cpu_nanoseconds_decimal",
        "total_process_cpu_nanoseconds_decimal",
        "monotonic_elapsed_nanoseconds_decimal",
        "epoch_started_nanoseconds_decimal",
        "epoch_ended_nanoseconds_decimal",
        "host_exclusion_observed",
        "primary_oracle_work_included",
        "count_in_end_to_end_exactly_once",
    }
    _exact_keys(document, keys, context)

    def decimal(name: str) -> int:
        text = _string(document[name], f"{context}.{name}")
        if re.fullmatch(r"(?:0|[1-9][0-9]*)", text) is None:
            raise AuthorityError(
                f"{context}.{name} is not canonical decimal nanoseconds"
            )
        return int(text)

    parent = decimal("parent_process_cpu_nanoseconds_decimal")
    validation = decimal("validation_child_cpu_nanoseconds_decimal")
    julia = decimal("julia_capture_cpu_nanoseconds_decimal")
    total = decimal("total_process_cpu_nanoseconds_decimal")
    decimal("monotonic_elapsed_nanoseconds_decimal")
    started = decimal("epoch_started_nanoseconds_decimal")
    ended = decimal("epoch_ended_nanoseconds_decimal")
    if total != parent + validation + julia or ended < started:
        raise AuthorityError(f"{context} CPU/epoch arithmetic differs")
    if (
        document["host_exclusion_observed"] is not False
        or document["primary_oracle_work_included"] is not False
        or document["count_in_end_to_end_exactly_once"] is not True
    ):
        raise AuthorityError(f"{context} accounting flags differ")
    return document


def _verify_materialization_attempt_claim(payload: bytes, stage: Stage) -> None:
    claim = _jcs_object(payload, f"{stage} materialization attempt claim")
    _exact_keys(
        claim,
        {
            "schema_version",
            "card_sha256",
            "attempt_ordinal",
            "rerun_permitted",
            "failure_is_terminal",
            "authority_validation_occurs_after_claim",
        },
        f"{stage} materialization attempt claim",
    )
    expected_schema = (
        "exp-local-003-c1-attempt-claim/v1"
        if stage == "development"
        else "exp-local-003-locked-attempt-claim/v1"
    )
    if dict(claim) != {
        "schema_version": expected_schema,
        "card_sha256": CARD_SHA256,
        "attempt_ordinal": 0,
        "rerun_permitted": False,
        "failure_is_terminal": True,
        "authority_validation_occurs_after_claim": True,
    }:
        raise AuthorityError(f"{stage} materialization attempt claim differs")


def resolve_result_blind_stage_binding(
    *,
    anchor_repository: Path,
    anchor_commit: str,
    anchor_path: str,
    anchor_sha256: str,
    git_executable: GitExecutable,
) -> ResultBlindStageBinding:
    """Resolve only immutable main-Git C0/C1 data needed by C2 equivalence.

    The implementation never constructs a repository for candidate,
    assessor, or private data and never reads their committed blobs.  It does
    verify the closed C1 topology by path/mode identity so a result-bearing
    path cannot be substituted for a protocol path.
    """

    repository = GitObjectRepository(anchor_repository, git_executable)
    normalized_anchor_path = _normal_path(anchor_path, "stage anchor path")
    fixed_anchor_path = "research/experiments/EXP-LOCAL-003/C1_STAGE_VAULT_ANCHOR.json"
    if normalized_anchor_path != fixed_anchor_path:
        raise AuthorityError("result-blind binding requires the fixed C1 anchor")
    anchor_tree = repository.commit_tree(anchor_commit)
    anchor_blob = repository.blob_at(anchor_commit, normalized_anchor_path)
    expected_anchor_sha = _hex(anchor_sha256, _SHA256, "stage anchor sha256")
    if anchor_blob.mode != "100644" or _sha256(anchor_blob.data) != expected_anchor_sha:
        raise AuthorityError("stage anchor mode/digest differs")
    anchor_file = FileRecord(
        path=normalized_anchor_path,
        sha256=expected_anchor_sha,
        byte_length=len(anchor_blob.data),
    )
    anchor = _jcs_object(anchor_blob.data, "stage vault anchor")
    _exact_keys(anchor, set(_ANCHOR_KEYS), "stage vault anchor")
    _verify_common(anchor, ANCHOR_SCHEMA, "development", "stage vault anchor")
    if (
        anchor["stage"] != "development"
        or anchor["candidate_visible"] is not False
        or anchor["rerun_permitted"] is not False
    ):
        raise AuthorityError("result-blind C1 anchor identity/visibility differs")

    source_commit = _hex(anchor["source_lock_commit"], _GIT_OID, "source lock commit")
    preimplementation_sha = _hex(
        anchor["preimplementation_lock_sha256"],
        _SHA256,
        "preimplementation lock sha256",
    )
    lock_path = "research/experiments/EXP-LOCAL-003/preimplementation-lock.json"
    lock_blob = repository.blob_at(source_commit, lock_path)
    if lock_blob.mode != "100644" or _sha256(lock_blob.data) != preimplementation_sha:
        raise AuthorityError("preimplementation lock blob differs from stage anchor")
    preimplementation = _jcs_object(lock_blob.data, "preimplementation lock")
    _exact_keys(
        preimplementation,
        {
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
        },
        "preimplementation lock",
    )
    if (
        preimplementation["schema_version"] != "exp-local-003-preimplementation-lock/v1"
        or preimplementation["experiment_id"] != EXPERIMENT_ID
        or preimplementation["status"]
        != "frozen-before-one-shot-development-materialization"
        or preimplementation["card_sha256"] != CARD_SHA256
    ):
        raise AuthorityError("preimplementation lock identity/status differs")
    c0_source_commit = _hex(
        preimplementation["c0_source_commit"], _GIT_OID, "c0 source commit"
    )
    c0_source_tree = _hex(
        preimplementation["c0_source_tree"], _GIT_OID, "c0 source tree"
    )
    if repository.commit_parents(source_commit) != (c0_source_commit,):
        raise AuthorityError("source lock commit is not the single child of C0 source")
    if repository.commit_tree(c0_source_commit) != c0_source_tree:
        raise AuthorityError("preimplementation C0 source tree differs")
    c0_index = dict(repository.tree_index(c0_source_commit))
    if lock_path in c0_index:
        raise AuthorityError("preimplementation lock existed in C0 source tree")
    if dict(repository.tree_index(source_commit)) != {
        **c0_index,
        lock_path: ("100644", lock_blob.oid),
    }:
        raise AuthorityError(
            "source lock commit changes more than the single lock blob"
        )

    files = preimplementation["files"]
    if not isinstance(files, dict):
        raise AuthorityError("preimplementation files map differs")
    normalized_files: dict[str, str] = {}
    for path_value, digest_value in files.items():
        path = _normal_path(path_value, "preimplementation files path")
        digest = _hex(digest_value, _SHA256, f"preimplementation files[{path}]")
        blob = repository.blob_at(c0_source_commit, path)
        if blob.mode != "100644" or _sha256(blob.data) != digest:
            raise AuthorityError(f"preimplementation file differs from C0 tree: {path}")
        normalized_files[path] = digest
    source_files_raw = preimplementation["experiment_source_files"]
    if not isinstance(source_files_raw, list):
        raise AuthorityError("preimplementation source file list differs")
    source_files = [
        _normal_path(value, f"experiment_source_files[{index}]")
        for index, value in enumerate(source_files_raw)
    ]
    expected_source_files = sorted(
        path
        for path in normalized_files
        if path.startswith("research/experiments/EXP-LOCAL-003/source/")
    )
    if source_files != expected_source_files or source_files != sorted(
        set(source_files)
    ):
        raise AuthorityError(
            "preimplementation source file list is not the locked C0 set"
        )
    for path in C0_EQUIVALENCE_PROTOCOL_PATHS:
        if path not in normalized_files or path not in c0_index:
            raise AuthorityError(
                f"C0 equivalence authority is absent from lock: {path}"
            )

    forbidden_raw = preimplementation["forbidden_mechanism_paths"]
    if not isinstance(forbidden_raw, list):
        raise AuthorityError("preimplementation forbidden path list differs")
    forbidden = tuple(
        _normal_path(value, f"forbidden_mechanism_paths[{index}]")
        for index, value in enumerate(forbidden_raw)
    )
    if forbidden != EXPECTED_FORBIDDEN_MECHANISM_PATHS:
        raise AuthorityError("preimplementation forbidden mechanism set differs")
    if any(
        any(indexed == path or indexed.startswith(f"{path}/") for indexed in c0_index)
        for path in forbidden
    ):
        raise AuthorityError("candidate mechanism exists in frozen C0 tree")

    environment_sha = _hex(
        preimplementation["environment_lock_sha256"],
        _SHA256,
        "preimplementation environment lock sha256",
    )
    local_options_sha = _hex(
        preimplementation["local_options_sha256"],
        _SHA256,
        "preimplementation local options sha256",
    )
    if repository.commit_parents(anchor_commit) != (source_commit,):
        raise AuthorityError("C1 stage anchor is not the single child of source lock")
    candidate_prefix = "research/experiments/EXP-LOCAL-003/development-candidate-inputs"
    expected_additions = {
        fixed_anchor_path,
        "research/experiments/EXP-LOCAL-003/C1_ATTEMPT_CLAIM.json",
        "research/experiments/EXP-LOCAL-003/C1_PRIVATE_AUDIT_ANCHOR.json",
        *(
            f"{candidate_prefix}/{name}"
            for name in (
                "ONE_SHOT_COMPLETE.json",
                "development-candidate-inputs.json.gz",
                "manifest.json",
                "plugin/Local3FixturePlugin.jl",
            )
        ),
    }
    source_index = dict(repository.tree_index(source_commit))
    anchor_index = dict(repository.tree_index(anchor_commit))
    if set(anchor_index) != set(source_index) | expected_additions:
        raise AuthorityError(
            "C1 commit additions differ from the closed publication set"
        )
    for path, identity in source_index.items():
        if anchor_index[path] != identity:
            raise AuthorityError(f"C1 commit modifies frozen source path {path}")
    for path in expected_additions:
        if anchor_index[path][0] != "100644":
            raise AuthorityError(f"C1 addition is not a regular blob: {path}")
    if any(path in anchor_index for path in C1_FORBIDDEN_MECHANISM_PATHS):
        raise AuthorityError("candidate mechanism exists in pre-outcome C1 tree")
    claim_blob = repository.blob_at(
        anchor_commit,
        "research/experiments/EXP-LOCAL-003/C1_ATTEMPT_CLAIM.json",
    )
    if _sha256(claim_blob.data) != anchor["materialization_attempt_claim_sha256"]:
        raise AuthorityError("C1 attempt claim differs from stage anchor")
    _verify_materialization_attempt_claim(claim_blob.data, "development")

    return ResultBlindStageBinding(
        stage="development",
        anchor_commit=anchor_commit,
        anchor_tree=anchor_tree,
        anchor_file=anchor_file,
        source_lock_commit=source_commit,
        preimplementation_lock_sha256=preimplementation_sha,
        c0_source_commit=c0_source_commit,
        c0_source_tree=c0_source_tree,
        environment_lock_sha256=environment_sha,
        local_options_sha256=local_options_sha,
    )


def resolve_stage_input_authority(
    *,
    anchor_repository: Path,
    anchor_commit: str,
    anchor_path: str,
    anchor_sha256: str,
    candidate_publication_root: Path,
    assessor_vault_repository: Path,
    git_executable: GitExecutable,
) -> StageInputRecord:
    """Resolve the pre-outcome C1/locked anchor and its formal input split."""

    anchor_root = anchor_repository.absolute()
    assessor_root = assessor_vault_repository.absolute()
    try:
        if os.path.samefile(anchor_root, assessor_root):
            raise AuthorityError(
                "anchor and assessor vault must be separate repositories"
            )
    except FileNotFoundError as error:
        raise AuthorityError(
            f"formal authority repository is unavailable: {error}"
        ) from error
    anchor_repo = GitObjectRepository(anchor_repository, git_executable)
    anchor_tree = anchor_repo.commit_tree(anchor_commit)
    normalized_anchor_path = _normal_path(anchor_path, "stage anchor path")
    anchor_blob = anchor_repo.blob_at(anchor_commit, normalized_anchor_path)
    expected_anchor_sha = _hex(anchor_sha256, _SHA256, "stage anchor sha256")
    if _sha256(anchor_blob.data) != expected_anchor_sha:
        raise AuthorityError("stage anchor digest differs")
    anchor_file = FileRecord(
        path=normalized_anchor_path,
        sha256=expected_anchor_sha,
        byte_length=len(anchor_blob.data),
    )
    anchor = _jcs_object(anchor_blob.data, "stage vault anchor")
    stage = _stage(anchor["stage"], "stage vault anchor.stage")
    expected_anchor_keys = set(_ANCHOR_KEYS)
    if stage == "locked":
        expected_anchor_keys.add("development_authority")
    _exact_keys(anchor, expected_anchor_keys, "stage vault anchor")
    _verify_common(anchor, ANCHOR_SCHEMA, stage, "stage vault anchor")
    if (
        anchor["candidate_visible"] is not False
        or anchor["rerun_permitted"] is not False
    ):
        raise AuthorityError("stage anchor visibility/rerun flags differ")
    _hex(
        anchor["materialization_attempt_claim_sha256"],
        _SHA256,
        "materialization attempt claim",
    )
    source_commit = _hex(anchor["source_lock_commit"], _GIT_OID, "source lock commit")
    preimplementation_sha = _hex(
        anchor["preimplementation_lock_sha256"],
        _SHA256,
        "preimplementation lock sha256",
    )
    lock_blob = anchor_repo.blob_at(
        source_commit,
        "research/experiments/EXP-LOCAL-003/preimplementation-lock.json",
    )
    if _sha256(lock_blob.data) != preimplementation_sha:
        raise AuthorityError("preimplementation lock blob differs from stage anchor")
    preimplementation = _jcs_object(lock_blob.data, "preimplementation lock")
    _exact_keys(
        preimplementation,
        {
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
        },
        "preimplementation lock",
    )
    if (
        preimplementation["schema_version"] != "exp-local-003-preimplementation-lock/v1"
        or preimplementation["experiment_id"] != EXPERIMENT_ID
        or preimplementation["status"]
        != "frozen-before-one-shot-development-materialization"
        or preimplementation["card_sha256"] != CARD_SHA256
    ):
        raise AuthorityError("preimplementation lock identity/status differs")
    c0_source_commit = _hex(
        preimplementation["c0_source_commit"], _GIT_OID, "c0 source commit"
    )
    c0_source_tree = _hex(
        preimplementation["c0_source_tree"], _GIT_OID, "c0 source tree"
    )
    if anchor_repo.commit_parents(source_commit) != (c0_source_commit,):
        raise AuthorityError("source lock commit is not the single child of C0 source")
    if anchor_repo.commit_tree(c0_source_commit) != c0_source_tree:
        raise AuthorityError("preimplementation C0 source tree differs")
    lock_path = "research/experiments/EXP-LOCAL-003/preimplementation-lock.json"
    base_index = dict(anchor_repo.tree_index(c0_source_commit))
    if lock_path in base_index:
        raise AuthorityError("preimplementation lock existed in C0 source tree")
    expected_lock_index = {
        **base_index,
        lock_path: ("100644", lock_blob.oid),
    }
    if dict(anchor_repo.tree_index(source_commit)) != expected_lock_index:
        raise AuthorityError(
            "source lock commit changes more than the single lock blob"
        )
    for field in ("environment_lock_sha256", "local_options_sha256"):
        _hex(preimplementation[field], _SHA256, f"preimplementation lock.{field}")
    if not isinstance(preimplementation["files"], dict):
        raise AuthorityError("preimplementation files map differs")
    c0_index = anchor_repo.tree_index(c0_source_commit)
    for path_value, digest_value in preimplementation["files"].items():
        path = _normal_path(path_value, "preimplementation files path")
        digest = _hex(digest_value, _SHA256, f"preimplementation files[{path}]")
        blob = anchor_repo.blob_at(c0_source_commit, path)
        if _sha256(blob.data) != digest:
            raise AuthorityError(f"preimplementation file differs from C0 tree: {path}")
    if not isinstance(preimplementation["experiment_source_files"], list):
        raise AuthorityError("preimplementation source file list differs")
    source_files = [
        _normal_path(value, f"experiment_source_files[{index}]")
        for index, value in enumerate(preimplementation["experiment_source_files"])
    ]
    if source_files != sorted(set(source_files)) or any(
        path not in c0_index for path in source_files
    ):
        raise AuthorityError("preimplementation source file list is not a C0 set")
    expected_source_files = sorted(
        path
        for path in preimplementation["files"]
        if path.startswith("research/experiments/EXP-LOCAL-003/source/")
    )
    if source_files != expected_source_files:
        raise AuthorityError("experiment source files differ from locked file map")
    if not isinstance(preimplementation["forbidden_mechanism_paths"], list):
        raise AuthorityError("preimplementation forbidden path list differs")
    forbidden_paths = [
        _normal_path(value, f"forbidden_mechanism_paths[{index}]")
        for index, value in enumerate(preimplementation["forbidden_mechanism_paths"])
    ]
    if tuple(forbidden_paths) != EXPECTED_FORBIDDEN_MECHANISM_PATHS:
        raise AuthorityError("preimplementation forbidden mechanism set differs")
    if any(
        any(indexed == path or indexed.startswith(f"{path}/") for indexed in c0_index)
        for path in forbidden_paths
    ):
        raise AuthorityError("candidate mechanism exists in frozen C0 tree")
    accounting = _c1_accounting(anchor["c1_phase_accounting"], "anchor c1 accounting")
    development_authority: Mapping[str, Any] | None = None
    if stage == "locked":
        development_authority = _mapping(
            anchor["development_authority"], "development authority"
        )
        development_keys = {
            "development_authorization_anchor_commit",
            "development_authorization_anchor_sha256",
            "development_stage_input_anchor_sha256",
            "development_candidate_run_authority_sha256",
            "development_assessor_stage_authority_sha256",
            "development_assessment_commit",
            "development_assessment_sha256",
            "development_decision_commit",
            "development_decision_record_sha256",
            "selected_variant",
            "selected_path",
        }
        _exact_keys(development_authority, development_keys, "development authority")
        for field in (
            "development_authorization_anchor_sha256",
            "development_stage_input_anchor_sha256",
            "development_candidate_run_authority_sha256",
            "development_assessor_stage_authority_sha256",
            "development_assessment_sha256",
            "development_decision_record_sha256",
        ):
            _hex(
                development_authority[field], _SHA256, f"development authority.{field}"
            )
        for field in (
            "development_authorization_anchor_commit",
            "development_assessment_commit",
            "development_decision_commit",
        ):
            _hex(
                development_authority[field], _GIT_OID, f"development authority.{field}"
            )
        if development_authority["selected_variant"] not in (
            "LX-BOUNDS",
            "LR-MODEL",
            "LXR-BOUNDS-MODEL",
        ) or development_authority["selected_path"] not in ("recall", "efficiency"):
            raise AuthorityError("development authority selection differs")

    candidate_input_name = f"{stage}-candidate-inputs.json.gz"
    candidate_expected = {
        "manifest.json",
        "ONE_SHOT_COMPLETE.json",
        candidate_input_name,
        "plugin/Local3FixturePlugin.jl",
    }
    if stage == "locked":
        candidate_expected.add("locked-selection.json")
    candidate_files = _filesystem_snapshot(
        candidate_publication_root, candidate_expected
    )
    if stage == "development":
        experiment_prefix = "research/experiments/EXP-LOCAL-003"
        fixed_anchor_path = f"{experiment_prefix}/C1_STAGE_VAULT_ANCHOR.json"
        attempt_path = f"{experiment_prefix}/C1_ATTEMPT_CLAIM.json"
        private_anchor_path = f"{experiment_prefix}/C1_PRIVATE_AUDIT_ANCHOR.json"
        candidate_prefix = f"{experiment_prefix}/development-candidate-inputs"
        if normalized_anchor_path != fixed_anchor_path:
            raise AuthorityError(
                "development stage anchor path differs from C1 protocol"
            )
        expected_candidate_root = (
            anchor_repository
            / "research"
            / "experiments"
            / "EXP-LOCAL-003"
            / "development-candidate-inputs"
        ).absolute()
        if os.path.normcase(
            str(candidate_publication_root.absolute())
        ) != os.path.normcase(str(expected_candidate_root)):
            raise AuthorityError("development candidate publication root is not fixed")
        if anchor_repo.commit_parents(anchor_commit) != (source_commit,):
            raise AuthorityError(
                "C1 stage anchor is not the single child of source lock"
            )
        additions = {
            fixed_anchor_path,
            attempt_path,
            private_anchor_path,
            *(f"{candidate_prefix}/{path}" for path in candidate_expected),
        }
        source_index = dict(anchor_repo.tree_index(source_commit))
        anchor_index = dict(anchor_repo.tree_index(anchor_commit))
        if set(anchor_index) != set(source_index) | additions:
            raise AuthorityError(
                "C1 commit additions differ from the closed publication set"
            )
        for path, identity in source_index.items():
            if anchor_index[path] != identity:
                raise AuthorityError(f"C1 commit modifies frozen source path {path}")
        for path in additions:
            if anchor_index[path][0] != "100644":
                raise AuthorityError(f"C1 addition is not a regular blob: {path}")
        claim_blob = anchor_repo.blob_at(anchor_commit, attempt_path)
        if _sha256(claim_blob.data) != anchor["materialization_attempt_claim_sha256"]:
            raise AuthorityError("C1 attempt claim differs from stage anchor")
        _verify_materialization_attempt_claim(claim_blob.data, "development")
        # The private anchor is deliberately not decoded by the formal resolver;
        # only its isolated, immutable existence is part of the C1 topology.
        anchor_repo.blob_at(anchor_commit, private_anchor_path)
        for relative, payload in candidate_files.items():
            committed = anchor_repo.blob_at(
                anchor_commit, f"{candidate_prefix}/{relative}"
            )
            if committed.data != payload:
                raise AuthorityError(
                    f"live candidate publication differs from C1 blob: {relative}"
                )
        if any(
            any(
                indexed == path or indexed.startswith(f"{path}/")
                for indexed in anchor_index
            )
            for path in C1_FORBIDDEN_MECHANISM_PATHS
        ):
            raise AuthorityError("candidate mechanism exists in pre-outcome C1 tree")
    else:
        experiment_prefix = "research/experiments/EXP-LOCAL-003"
        fixed_anchor_path = f"{experiment_prefix}/C4_LOCKED_STAGE_VAULT_ANCHOR.json"
        attempt_path = f"{experiment_prefix}/LOCKED_ATTEMPT_CLAIM.json"
        private_anchor_path = f"{experiment_prefix}/C4_LOCKED_PRIVATE_AUDIT_ANCHOR.json"
        candidate_prefix = f"{experiment_prefix}/locked-candidate-inputs"
        if normalized_anchor_path != fixed_anchor_path:
            raise AuthorityError("locked stage anchor path differs from C4 protocol")
        expected_candidate_root = (
            anchor_repository
            / "research"
            / "experiments"
            / "EXP-LOCAL-003"
            / "locked-candidate-inputs"
        ).absolute()
        if os.path.normcase(
            str(candidate_publication_root.absolute())
        ) != os.path.normcase(str(expected_candidate_root)):
            raise AuthorityError("locked candidate publication root is not fixed")
        development_commit = _string(
            development_authority["development_authorization_anchor_commit"],
            "development authorization anchor commit",
        )
        if anchor_repo.commit_parents(anchor_commit) != (development_commit,):
            raise AuthorityError("C4 stage anchor is not the development child commit")
        development_path = (
            f"{experiment_prefix}/C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
        )
        development_blob = anchor_repo.blob_at(development_commit, development_path)
        if (
            _sha256(development_blob.data)
            != development_authority["development_authorization_anchor_sha256"]
        ):
            raise AuthorityError("C4 does not bind the development authorization blob")
        additions = {
            fixed_anchor_path,
            attempt_path,
            private_anchor_path,
            *(f"{candidate_prefix}/{path}" for path in candidate_expected),
        }
        parent_index = dict(anchor_repo.tree_index(development_commit))
        anchor_index = dict(anchor_repo.tree_index(anchor_commit))
        if set(anchor_index) != set(parent_index) | additions:
            raise AuthorityError(
                "C4 commit additions differ from the locked publication set"
            )
        for path, identity in parent_index.items():
            if anchor_index[path] != identity:
                raise AuthorityError(f"C4 commit modifies prior authority path {path}")
        for path in additions:
            if anchor_index[path][0] != "100644":
                raise AuthorityError(f"C4 addition is not a regular blob: {path}")
        claim_blob = anchor_repo.blob_at(anchor_commit, attempt_path)
        if _sha256(claim_blob.data) != anchor["materialization_attempt_claim_sha256"]:
            raise AuthorityError("C4 attempt claim differs from stage anchor")
        _verify_materialization_attempt_claim(claim_blob.data, "locked")
        anchor_repo.blob_at(anchor_commit, private_anchor_path)
        for relative, payload in candidate_files.items():
            committed = anchor_repo.blob_at(
                anchor_commit, f"{candidate_prefix}/{relative}"
            )
            if committed.data != payload:
                raise AuthorityError(
                    f"live locked candidate publication differs from C4 blob: {relative}"
                )
    observed_tree = _publication_tree(candidate_files)
    tree_authority = _mapping(anchor["candidate_publication_tree"], "candidate tree")
    _exact_keys(
        tree_authority, {"file_count", "total_bytes", "sha256"}, "candidate tree"
    )
    if dict(observed_tree) != dict(tree_authority):
        raise AuthorityError("candidate publication tree differs from stage anchor")

    candidate_manifest_bytes = candidate_files["manifest.json"]
    candidate_manifest_sha = _sha256(candidate_manifest_bytes)
    if candidate_manifest_sha != anchor["candidate_manifest_sha256"]:
        raise AuthorityError("candidate manifest differs from stage anchor")
    candidate_manifest = _jcs_object(candidate_manifest_bytes, "candidate manifest")
    candidate_manifest_keys = {
        "schema_version",
        "experiment_id",
        "partition",
        "case_count",
        "starts_per_case",
        "calibration_points_per_case",
        "card_sha256",
        "preimplementation_lock_sha256",
        "candidate_input_sha256",
        "artifact",
        "fixture_plugin_artifact",
        "locked_selection_artifact",
        "visible_tree",
    }
    _exact_keys(candidate_manifest, candidate_manifest_keys, "candidate manifest")
    expected_counts = (64, 32, 64) if stage == "development" else (96, 32, 64)
    if (
        candidate_manifest["schema_version"] != "exp-local-003-candidate-manifest/v1"
        or candidate_manifest["experiment_id"] != EXPERIMENT_ID
        or candidate_manifest["partition"] != stage
        or candidate_manifest["card_sha256"] != CARD_SHA256
        or candidate_manifest["preimplementation_lock_sha256"] != preimplementation_sha
        or (
            candidate_manifest["case_count"],
            candidate_manifest["starts_per_case"],
            candidate_manifest["calibration_points_per_case"],
        )
        != expected_counts
        or candidate_manifest["visible_tree"] != "candidate-only"
    ):
        raise AuthorityError("candidate manifest fixed fields differ")
    candidate_input_jcs, candidate_input = _artifact_record(
        candidate_manifest["artifact"],
        path=candidate_input_name,
        compressed=candidate_files[candidate_input_name],
        context="candidate input artifact",
    )
    candidate_input_sha = _sha256(candidate_input_jcs)
    if candidate_manifest["candidate_input_sha256"] != candidate_input_sha:
        raise AuthorityError("candidate input semantic digest differs")
    expected_input_schema = (
        "exp-local-003-candidate-inputs/v1"
        if stage == "development"
        else "exp-local-003-locked-candidate-inputs/v1"
    )
    if (
        candidate_input.get("schema_version") != expected_input_schema
        or candidate_input.get("card_sha256") != CARD_SHA256
    ):
        raise AuthorityError("candidate input stage/card differs")
    _plain_artifact_record(
        candidate_manifest["fixture_plugin_artifact"],
        path="plugin/Local3FixturePlugin.jl",
        payload=candidate_files["plugin/Local3FixturePlugin.jl"],
        context="fixture plugin artifact",
    )
    selection = candidate_manifest["locked_selection_artifact"]
    if stage == "development":
        if selection is not None:
            raise AuthorityError(
                "development candidate manifest exposes locked selection"
            )
    else:
        _plain_artifact_record(
            selection,
            path="locked-selection.json",
            payload=candidate_files["locked-selection.json"],
            context="locked selection artifact",
        )
        selection_document = _jcs_object(
            candidate_files["locked-selection.json"], "locked selection"
        )
        _exact_keys(
            selection_document,
            {
                "schema_version",
                "experiment_id",
                "card_sha256",
                "stage",
                "selected_variant",
                "candidate_input_sha256",
            },
            "locked selection",
        )
        if (
            selection_document["schema_version"]
            != "geotarget.exp-local-003.locked-selection/v1"
            or selection_document["experiment_id"] != EXPERIMENT_ID
            or selection_document["card_sha256"] != CARD_SHA256
            or selection_document["stage"] != "locked"
            or selection_document["selected_variant"]
            != development_authority["selected_variant"]
            or selection_document["candidate_input_sha256"] != candidate_input_sha
        ):
            raise AuthorityError("locked selection differs from development authority")
    candidate_completion_bytes = candidate_files["ONE_SHOT_COMPLETE.json"]
    if _sha256(candidate_completion_bytes) != anchor["candidate_completion_sha256"]:
        raise AuthorityError("candidate completion differs from stage anchor")
    candidate_completion = _jcs_object(
        candidate_completion_bytes, "candidate completion"
    )
    _exact_keys(
        candidate_completion,
        {
            "schema_version",
            "partition",
            "candidate_manifest_sha256",
            "source_lock_commit",
            "rerun_permitted",
            "contains_assessor_digest",
        },
        "candidate completion",
    )
    if (
        candidate_completion["schema_version"]
        != "exp-local-003-candidate-one-shot-completion/v1"
        or candidate_completion["partition"] != stage
        or candidate_completion["candidate_manifest_sha256"] != candidate_manifest_sha
        or candidate_completion["source_lock_commit"] != source_commit
        or candidate_completion["rerun_permitted"] is not False
        or candidate_completion["contains_assessor_digest"] is not False
    ):
        raise AuthorityError("candidate completion cross-binding differs")

    assessor_commit = _hex(
        anchor["assessor_vault_git_commit"], _GIT_OID, "assessor vault commit"
    )
    assessor_tree = _hex(
        anchor["assessor_vault_git_tree"], _GIT_OID, "assessor vault tree"
    )
    truth_path = f"assessor/{stage}-assessor-truth.json.gz"
    bootstrap_path = f"assessor/{stage}-bootstrap-indices.bin"
    assessor_expected = {
        "manifest.json",
        "ONE_SHOT_COMPLETE.json",
        "assessor/manifest.json",
        truth_path,
        bootstrap_path,
    }
    assessor_repository = GitObjectRepository(assessor_vault_repository, git_executable)
    if assessor_repository.commit_parents(assessor_commit):
        raise AuthorityError("assessor input vault commit is not an orphan root")
    assessor_snapshot = _git_snapshot(
        assessor_vault_repository,
        assessor_commit,
        assessor_tree,
        assessor_expected,
        git_executable,
        "assessor vault",
    )
    assessor_root_bytes = assessor_snapshot["manifest.json"].data
    assessor_root_sha = _sha256(assessor_root_bytes)
    if assessor_root_sha != anchor["assessor_vault_manifest_sha256"]:
        raise AuthorityError("assessor vault manifest differs from stage anchor")
    assessor_root_manifest = _jcs_object(assessor_root_bytes, "assessor vault manifest")
    root_keys = {
        "schema_version",
        "experiment_id",
        "partition",
        "card_sha256",
        "preimplementation_lock_sha256",
        "source_lock_commit",
        "candidate_manifest_sha256",
        "assessor_manifest_sha256",
        "c1_materialization_times",
        "candidate_process_argument",
        "candidate_repository_contains_vault",
        "assessor_open_order",
        "rerun_permitted",
        "locked_inputs_materialized",
        "locked_authority",
    }
    _exact_keys(assessor_root_manifest, root_keys, "assessor vault manifest")
    if (
        assessor_root_manifest["schema_version"]
        != "exp-local-003-assessor-vault-manifest/v1"
        or assessor_root_manifest["experiment_id"] != EXPERIMENT_ID
        or assessor_root_manifest["partition"] != stage
        or assessor_root_manifest["card_sha256"] != CARD_SHA256
        or assessor_root_manifest["preimplementation_lock_sha256"]
        != preimplementation_sha
        or assessor_root_manifest["source_lock_commit"] != source_commit
        or assessor_root_manifest["candidate_manifest_sha256"] != candidate_manifest_sha
        or assessor_root_manifest["candidate_repository_contains_vault"] is not False
        or assessor_root_manifest["assessor_open_order"]
        != "after sealed candidate raw output and process exit"
        or assessor_root_manifest["rerun_permitted"] is not False
        or assessor_root_manifest["locked_inputs_materialized"] != (stage == "locked")
        or dict(
            _c1_accounting(
                assessor_root_manifest["c1_materialization_times"],
                "assessor manifest c1 accounting",
            )
        )
        != dict(accounting)
    ):
        raise AuthorityError("assessor vault manifest fixed/cross fields differ")
    if stage == "development":
        if assessor_root_manifest["locked_authority"] is not None:
            raise AuthorityError("development assessor manifest has locked authority")
    else:
        locked_authority = _mapping(
            assessor_root_manifest["locked_authority"], "locked authority"
        )
        _exact_keys(
            locked_authority,
            {
                "development_assessment_sha256",
                "development_decision_record_sha256",
                "decision_commit",
                "selected_variant",
                "selected_path",
                "locked_selection_sha256",
            },
            "locked authority",
        )
        if (
            locked_authority["development_assessment_sha256"]
            != development_authority["development_assessment_sha256"]
            or locked_authority["development_decision_record_sha256"]
            != development_authority["development_decision_record_sha256"]
            or locked_authority["decision_commit"]
            != development_authority["development_assessment_commit"]
            or locked_authority["selected_variant"]
            != development_authority["selected_variant"]
            or locked_authority["selected_path"]
            != development_authority["selected_path"]
            or locked_authority["locked_selection_sha256"]
            != _sha256(candidate_files["locked-selection.json"])
        ):
            raise AuthorityError("locked assessor manifest authority differs")
    nested_manifest_bytes = assessor_snapshot["assessor/manifest.json"].data
    nested_manifest_sha = _sha256(nested_manifest_bytes)
    if (
        nested_manifest_sha != anchor["assessor_manifest_sha256"]
        or nested_manifest_sha != assessor_root_manifest["assessor_manifest_sha256"]
    ):
        raise AuthorityError("assessor nested manifest cross-binding differs")
    nested = _jcs_object(nested_manifest_bytes, "assessor manifest")
    nested_keys = {
        "schema_version",
        "experiment_id",
        "partition",
        "primary_case_count",
        "safety_case_count",
        "card_sha256",
        "preimplementation_lock_sha256",
        "truth_artifact",
        "bootstrap_artifact",
        "visible_tree",
    }
    _exact_keys(nested, nested_keys, "assessor manifest")
    expected_case_counts = (48, 16) if stage == "development" else (96, 0)
    if (
        nested["schema_version"] != "exp-local-003-assessor-manifest/v1"
        or nested["experiment_id"] != EXPERIMENT_ID
        or nested["partition"] != stage
        or (nested["primary_case_count"], nested["safety_case_count"])
        != expected_case_counts
        or nested["card_sha256"] != CARD_SHA256
        or nested["preimplementation_lock_sha256"] != preimplementation_sha
        or nested["visible_tree"] != "assessor-only-after-candidate-seal"
    ):
        raise AuthorityError("assessor manifest fixed fields differ")
    truth_compressed = assessor_snapshot[truth_path].data
    truth_jcs, truth = _artifact_record(
        nested["truth_artifact"],
        path=truth_path,
        compressed=truth_compressed,
        context="assessor truth artifact",
    )
    bootstrap = assessor_snapshot[bootstrap_path].data
    _plain_artifact_record(
        nested["bootstrap_artifact"],
        path=bootstrap_path,
        payload=bootstrap,
        context="bootstrap artifact",
        extra_key="format",
        extra_value=f"GTLOCAL3BOOT1-{stage}",
    )
    if not bootstrap:
        raise AuthorityError("bootstrap authority is empty")
    if (
        truth.get("stage") != stage
        or truth.get("candidate_input_sha256") != candidate_input_sha
        or truth.get("bootstrap_sha256") != _sha256(bootstrap)
    ):
        raise AuthorityError("assessor truth input/bootstrap binding differs")
    if stage == "locked":
        locked_decision = _mapping(
            truth.get("locked_decision"), "truth.locked_decision"
        )
        _exact_keys(
            locked_decision,
            {
                "candidate_id",
                "development_path",
                "development_assessment_sha256",
                "development_decision_record_sha256",
            },
            "truth.locked_decision",
        )
        if (
            locked_decision["candidate_id"] != development_authority["selected_variant"]
            or locked_decision["development_path"]
            != development_authority["selected_path"]
            or locked_decision["development_assessment_sha256"]
            != development_authority["development_assessment_sha256"]
            or locked_decision["development_decision_record_sha256"]
            != development_authority["development_decision_record_sha256"]
        ):
            raise AuthorityError(
                "locked truth decision differs from development authority"
            )
    elif truth.get("locked_decision") is not None:
        raise AuthorityError("development truth contains locked decision")
    completion_bytes = assessor_snapshot["ONE_SHOT_COMPLETE.json"].data
    if _sha256(completion_bytes) != anchor["assessor_vault_completion_sha256"]:
        raise AuthorityError("assessor vault completion differs from stage anchor")
    completion = _jcs_object(completion_bytes, "assessor vault completion")
    _exact_keys(
        completion,
        {
            "schema_version",
            "partition",
            "manifest_sha256",
            "source_lock_commit",
            "rerun_permitted",
        },
        "assessor vault completion",
    )
    if (
        completion["schema_version"]
        != "exp-local-003-assessor-vault-one-shot-completion/v1"
        or completion["partition"] != stage
        or completion["manifest_sha256"] != assessor_root_sha
        or completion["source_lock_commit"] != source_commit
        or completion["rerun_permitted"] is not False
    ):
        raise AuthorityError("assessor vault completion cross-binding differs")

    records = _snapshot_records(candidate_files)
    return StageInputRecord(
        stage=stage,
        anchor_commit=anchor_commit,
        anchor_tree=anchor_tree,
        anchor_file=anchor_file,
        source_lock_commit=source_commit,
        preimplementation_lock_sha256=preimplementation_sha,
        candidate_publication_tree_sha256=_string(
            tree_authority["sha256"], "candidate tree sha256"
        ),
        candidate_files=records,
        candidate_input_sha256=candidate_input_sha,
        candidate_input_jcs=candidate_input_jcs,
        candidate_input=_deep_freeze(candidate_input),
        assessor_vault_commit=assessor_commit,
        assessor_vault_tree=assessor_tree,
        assessor_truth_file=FileRecord(
            path=truth_path,
            sha256=_sha256(truth_compressed),
            byte_length=len(truth_compressed),
        ),
        assessor_truth_jcs=truth_jcs,
        assessor_truth=_deep_freeze(truth),
        bootstrap_file=FileRecord(
            path=bootstrap_path,
            sha256=_sha256(bootstrap),
            byte_length=len(bootstrap),
        ),
        bootstrap_indices=bootstrap,
        development_authority=(
            None
            if development_authority is None
            else _deep_freeze(development_authority)
        ),
        anchor=_deep_freeze(anchor),
    )


def _manifest(
    blob: _Blob,
    record: FileRecord,
    *,
    stage: Stage,
    kind: Literal["candidate-run", "assessor-stage"],
) -> tuple[Mapping[str, Any], Mapping[str, ManifestEntry]]:
    _verify_blob_record(blob, record, f"{kind} manifest")
    document = _mapping(
        strict_jcs_bytes(blob.data, context=f"{kind} manifest"), "manifest"
    )
    _exact_keys(
        document,
        {"schema_version", "experiment_id", "card_sha256", "stage", "kind", "files"},
        "manifest",
    )
    _verify_common(document, MANIFEST_SCHEMA, stage, "manifest")
    if document["kind"] != kind:
        raise AuthorityError("manifest kind differs")
    expected_roles = (
        ("raw_output", "preexit_seal", "process_exit")
        if kind == "candidate-run"
        else ("assessor_truth", "bootstrap_indices")
    )
    entries: dict[str, ManifestEntry] = {}
    for index, value in enumerate(_array(document["files"], "manifest.files")):
        entry = _mapping(value, f"manifest.files[{index}]")
        _exact_keys(
            entry,
            {"role", "file", "media_type", "content_encoding"},
            f"manifest.files[{index}]",
        )
        role = _string(entry["role"], f"manifest.files[{index}].role")
        if role in entries:
            raise AuthorityError(f"manifest role {role!r} is duplicated")
        encoding = entry["content_encoding"]
        if encoding not in ("identity", "deterministic-gzip"):
            raise AuthorityError("manifest content encoding differs")
        entries[role] = ManifestEntry(
            role=role,
            file=_file_record(entry["file"], f"manifest.files[{index}].file"),
            media_type=_string(
                entry["media_type"], f"manifest.files[{index}].media_type"
            ),
            content_encoding=cast(Literal["identity", "deterministic-gzip"], encoding),
        )
    if tuple(entries) != expected_roles:
        raise AuthorityError(
            f"{kind} manifest roles/order differ; expected {expected_roles!r}"
        )
    expected_transport = {
        "raw_output": ("application/json", "deterministic-gzip"),
        "preexit_seal": ("application/json", "identity"),
        "process_exit": ("application/json", "identity"),
        "assessor_truth": ("application/json", "deterministic-gzip"),
        "bootstrap_indices": ("application/octet-stream", "identity"),
    }
    for role, manifest_entry in entries.items():
        if (
            manifest_entry.media_type,
            manifest_entry.content_encoding,
        ) != expected_transport[role]:
            raise AuthorityError(f"manifest transport for {role} differs")
    return document, MappingProxyType(entries)


def _blob_for(snapshot: Mapping[str, _Blob], record: FileRecord, context: str) -> _Blob:
    try:
        blob = snapshot[record.path]
    except KeyError as error:
        raise AuthorityError(f"{context} path is absent from immutable tree") from error
    _verify_blob_record(blob, record, context)
    return blob


def _external_file_ref(value: Any, context: str) -> tuple[str, str, FileRecord]:
    document = _mapping(value, context)
    _exact_keys(document, {"commit", "tree", "file"}, context)
    return (
        _hex(document["commit"], _GIT_OID, f"{context}.commit"),
        _hex(document["tree"], _GIT_OID, f"{context}.tree"),
        _file_record(document["file"], f"{context}.file"),
    )


def _commit_tree_ref(value: Any, context: str) -> tuple[str, str]:
    document = _mapping(value, context)
    _exact_keys(document, _COMMIT_TREE_KEYS, context)
    return (
        _hex(document["commit"], _GIT_OID, f"{context}.commit"),
        _hex(document["tree"], _GIT_OID, f"{context}.tree"),
    )


def _verify_candidate_history(
    repo: GitObjectRepository,
    *,
    final_commit: str,
    final_tree: str,
    history: Mapping[str, Any],
    attempt_record: FileRecord,
    raw_record: FileRecord,
    seal_record: FileRecord,
    exit_record: FileRecord,
    manifest_record: FileRecord,
    authority_record: FileRecord,
) -> None:
    """Verify the raw Git commit/tree proof of candidate-process ordering.

    JSON event ordinals are descriptive only.  This append-only history is the
    authority: an orphan claim, three exact one-file child additions, then one
    child adding only the manifest and authority.  ``_cat_file`` re-hashes the
    raw commit and tree bytes before these relationships are interpreted.
    """

    _exact_keys(
        history,
        {"attempt_claim", "raw_output", "preexit_seal", "process_exit"},
        "authority.history",
    )
    refs = (
        _commit_tree_ref(history["attempt_claim"], "authority.history.attempt_claim"),
        _commit_tree_ref(history["raw_output"], "authority.history.raw_output"),
        _commit_tree_ref(history["preexit_seal"], "authority.history.preexit_seal"),
        _commit_tree_ref(history["process_exit"], "authority.history.process_exit"),
    )
    commits = tuple(reference[0] for reference in refs)
    if len(set(commits)) != len(commits):
        raise AuthorityError("candidate history reuses a Git commit")
    if repo.commit_parents(commits[0]):
        raise AuthorityError("candidate attempt claim must be an orphan root commit")
    for index in range(1, len(commits)):
        if repo.commit_parents(commits[index]) != (commits[index - 1],):
            raise AuthorityError(
                "candidate history is not the required single-parent chain"
            )
    if repo.commit_parents(final_commit) != (commits[-1],):
        raise AuthorityError("candidate final authority is not the process-exit child")
    for commit_oid, declared_tree in refs:
        # Reading both objects through these methods verifies their framed raw
        # bytes against their Git object ids, not merely their printed ids.
        if repo.commit_tree(commit_oid) != declared_tree:
            raise AuthorityError("candidate history commit/tree binding differs")
        repo.tree_index(commit_oid)
    if repo.commit_tree(final_commit) != final_tree:
        raise AuthorityError("candidate final commit/tree binding differs")

    expected_paths = (
        (attempt_record.path,),
        (attempt_record.path, raw_record.path),
        (attempt_record.path, raw_record.path, seal_record.path),
        (
            attempt_record.path,
            raw_record.path,
            seal_record.path,
            exit_record.path,
        ),
        (
            attempt_record.path,
            raw_record.path,
            seal_record.path,
            exit_record.path,
            manifest_record.path,
            authority_record.path,
        ),
    )
    indexes = [repo.tree_index(commit_oid) for commit_oid in commits]
    indexes.append(repo.tree_index(final_commit))
    for index, (tree_index, paths) in enumerate(
        zip(indexes, expected_paths, strict=True)
    ):
        if set(tree_index) != set(paths):
            raise AuthorityError(
                "candidate history does not have the exact additive path set "
                f"at step {index}; extra={sorted(set(tree_index) - set(paths))}, "
                f"missing={sorted(set(paths) - set(tree_index))}"
            )
        if any(mode != "100644" for mode, _oid in tree_index.values()):
            raise AuthorityError("candidate history contains a non-regular Git entry")
        if index:
            previous = indexes[index - 1]
            for path, identity in previous.items():
                if tree_index[path] != identity:
                    raise AuthorityError(
                        f"candidate history changed an earlier blob: {path}"
                    )


def resolve_candidate_run_authority(
    repository: Path,
    *,
    git_executable: GitExecutable,
    commit: str,
    tree: str,
    authority_file: FileRecord,
    expected_stage: Stage,
    stage_input: StageInputRecord,
    execution_lock_repository: Path,
) -> CandidateRunRecord:
    """Resolve one closed candidate vault without reading its worktree."""

    repo = GitObjectRepository(repository, git_executable)
    snapshot = repo.snapshot(commit, tree)
    authority_blob = _blob_for(snapshot, authority_file, "candidate-run authority")
    authority = _mapping(
        strict_jcs_bytes(authority_blob.data, context="candidate-run authority"),
        "candidate-run authority",
    )
    _exact_keys(authority, _CANDIDATE_AUTHORITY_KEYS, "candidate-run authority")
    _verify_common(
        authority, CANDIDATE_AUTHORITY_SCHEMA, expected_stage, "candidate-run authority"
    )
    if stage_input.stage != expected_stage:
        raise AuthorityError("candidate run and input authority stages differ")
    process_id = _hex(
        authority["process_instance_id"], _PROCESS_ID, "process_instance_id"
    )
    candidate_input = _hex(
        authority["candidate_input_sha256"], _SHA256, "candidate_input_sha256"
    )
    if candidate_input != stage_input.candidate_input_sha256:
        raise AuthorityError("candidate run input differs from pre-outcome anchor")
    if (
        authority["candidate_publication_tree_sha256"]
        != stage_input.candidate_publication_tree_sha256
    ):
        raise AuthorityError(
            "candidate run publication tree differs from pre-outcome anchor"
        )
    input_commit, input_tree, input_file = _external_file_ref(
        authority["stage_input_anchor"], "authority.stage_input_anchor"
    )
    if (
        input_commit != stage_input.anchor_commit
        or input_tree != stage_input.anchor_tree
        or input_file != stage_input.anchor_file
    ):
        raise AuthorityError("candidate run does not bind the exact pre-outcome anchor")
    lock_commit, lock_tree, lock_file = _external_file_ref(
        authority["candidate_execution_lock"], "authority.candidate_execution_lock"
    )
    lock_repo = GitObjectRepository(execution_lock_repository, git_executable)
    if lock_repo.commit_tree(lock_commit) != lock_tree:
        raise AuthorityError("candidate execution-lock commit tree differs")
    lock_blob = lock_repo.blob_at(lock_commit, lock_file.path)
    _verify_blob_record(lock_blob, lock_file, "candidate execution lock")
    execution_lock = lock_file.sha256
    execution_document = _jcs_object(lock_blob.data, "candidate execution lock")
    _exact_keys(
        execution_document,
        {
            "schema_version",
            "card_sha256",
            "stage",
            "candidate_input_sha256",
            "local_options_sha256",
            "stage_input_anchor_sha256",
            "stage_input_anchor_commit",
            "runner_source_path",
            "runner_source_sha256",
            "source_manifest_sha256",
            "allowed_sources",
            "allowed_candidate_artifacts",
        },
        "candidate execution lock",
    )
    if (
        execution_document.get("schema_version")
        != "geotarget.exp-local-003.candidate-execution-lock/v1"
        or execution_document.get("card_sha256") != CARD_SHA256
        or execution_document.get("stage") != expected_stage
        or execution_document.get("candidate_input_sha256") != candidate_input
        or execution_document.get("stage_input_anchor_sha256")
        != stage_input.anchor_file.sha256
        or execution_document.get("stage_input_anchor_commit")
        != stage_input.anchor_commit
    ):
        raise AuthorityError(
            "candidate execution lock does not bind formal stage inputs"
        )
    sources = _array(execution_document["allowed_sources"], "allowed_sources")
    normalized_sources: list[dict[str, str]] = []
    for index, value in enumerate(sources):
        item = _mapping(value, f"allowed_sources[{index}]")
        _exact_keys(item, {"path", "sha256"}, f"allowed_sources[{index}]")
        normalized_sources.append(
            {
                "path": _normal_path(item["path"], f"allowed_sources[{index}].path"),
                "sha256": _hex(item["sha256"], _SHA256, "source sha256"),
            }
        )
    if normalized_sources != sorted(normalized_sources, key=lambda item: item["path"]):
        raise AuthorityError("execution lock sources are not sorted")
    if len({item["path"] for item in normalized_sources}) != len(normalized_sources):
        raise AuthorityError("execution lock sources are not unique")
    if {item["path"] for item in normalized_sources} != set(C2_REQUIRED_SOURCE_PATHS):
        raise AuthorityError("execution lock runtime sources differ from frozen C2")
    if (
        _sha256(canonical_bytes(normalized_sources))
        != execution_document["source_manifest_sha256"]
    ):
        raise AuthorityError("execution lock source manifest digest differs")
    for item in normalized_sources:
        source_blob = lock_repo.blob_at(lock_commit, item["path"])
        if source_blob.mode != "100644":
            raise AuthorityError("execution source is not a regular Git blob")
        if _sha256(source_blob.data) != item["sha256"]:
            raise AuthorityError(
                f"execution source differs from C2 commit: {item['path']}"
            )
    runner_binding = (
        execution_document["runner_source_path"],
        execution_document["runner_source_sha256"],
    )
    if runner_binding[0] != RUNNER_SOURCE_PATH:
        raise AuthorityError("execution lock runner path is not the frozen C2 runner")
    if (
        sum(
            (item["path"], item["sha256"]) == runner_binding
            for item in normalized_sources
        )
        != 1
    ):
        raise AuthorityError("execution lock does not bind exactly one runner source")
    opened = _array(
        execution_document.get("allowed_candidate_artifacts"),
        "execution lock allowed_candidate_artifacts",
    )
    artifact_pairs: list[tuple[str, str]] = []
    for index, value in enumerate(opened):
        item = _mapping(value, f"allowed_candidate_artifacts[{index}]")
        _exact_keys(item, {"path", "sha256"}, f"allowed_candidate_artifacts[{index}]")
        path = _normal_path(item["path"], f"allowed_candidate_artifacts[{index}].path")
        if not path.startswith("candidate/"):
            raise AuthorityError("allowed candidate artifact is outside candidate root")
        artifact_pairs.append(
            (
                path.removeprefix("candidate/"),
                _hex(item["sha256"], _SHA256, "candidate artifact sha256"),
            )
        )
    expected_pairs = sorted(
        (path, record.sha256) for path, record in stage_input.candidate_files.items()
    )
    if artifact_pairs != expected_pairs:
        raise AuthorityError(
            "execution lock artifact allowlist differs from C1 publication"
        )

    preimplementation_path = (
        "research/experiments/EXP-LOCAL-003/preimplementation-lock.json"
    )
    preimplementation_blob = lock_repo.blob_at(
        stage_input.source_lock_commit, preimplementation_path
    )
    if (
        preimplementation_blob.mode != "100644"
        or _sha256(preimplementation_blob.data)
        != stage_input.preimplementation_lock_sha256
    ):
        raise AuthorityError("candidate run cannot resolve immutable C0 authority")
    preimplementation = _jcs_object(
        preimplementation_blob.data, "C0 preimplementation lock"
    )
    c0_commit = _hex(
        preimplementation.get("c0_source_commit"), _GIT_OID, "C0 source commit"
    )
    c0_tree = _hex(preimplementation.get("c0_source_tree"), _GIT_OID, "C0 source tree")
    if lock_repo.commit_tree(c0_commit) != c0_tree:
        raise AuthorityError("candidate run C0 commit/tree authority differs")
    environment_lock_sha = _hex(
        preimplementation.get("environment_lock_sha256"),
        _SHA256,
        "C0 environment-lock sha256",
    )
    (
        environment_document,
        julia_executable,
        julia_runtime_root,
        julia_depot_root,
        _locked_julia_environment,
    ) = _c0_environment_authority(lock_repo, c0_commit, environment_lock_sha)

    def expected_c0_authority(value: Any, path: str, context: str) -> Mapping[str, Any]:
        external = _mapping(value, context)
        commit_value, tree_value, file_value = _external_file_ref(external, context)
        blob = lock_repo.blob_at(c0_commit, path)
        expected_file = FileRecord(path, _sha256(blob.data), len(blob.data))
        if (
            blob.mode != "100644"
            or commit_value != c0_commit
            or tree_value != c0_tree
            or file_value != expected_file
        ):
            raise AuthorityError(f"{context} differs from immutable C0 source")
        return external

    attempt_record = _file_record(authority["attempt_claim"], "authority.attempt_claim")
    raw_record = _file_record(authority["raw_output"], "authority.raw_output")
    seal_record = _file_record(authority["preexit_seal"], "authority.preexit_seal")
    exit_record = _file_record(authority["process_exit"], "authority.process_exit")
    manifest_record = _file_record(authority["manifest"], "authority.manifest")
    history = _mapping(authority["history"], "authority.history")
    _verify_candidate_history(
        repo,
        final_commit=commit,
        final_tree=tree,
        history=history,
        attempt_record=attempt_record,
        raw_record=raw_record,
        seal_record=seal_record,
        exit_record=exit_record,
        manifest_record=manifest_record,
        authority_record=authority_file,
    )
    _changed_paths(
        authority["changed_paths"], raw_record.path, "authority.changed_paths"
    )
    event = _mapping(authority["event"], "authority.event")
    _exact_keys(event, {"kind", "ordinal", "parent"}, "authority.event")
    if (
        event["kind"] != "candidate-run-authority"
        or _integer(event["ordinal"], "authority.event.ordinal") != 6
    ):
        raise AuthorityError("candidate-run authority event identity differs")
    _parent(
        event["parent"],
        "candidate-process-exit",
        exit_record.sha256,
        "authority.event.parent",
    )

    _, entries = _manifest(
        _blob_for(snapshot, manifest_record, "candidate-run manifest"),
        manifest_record,
        stage=expected_stage,
        kind="candidate-run",
    )
    records = {
        "raw_output": raw_record,
        "preexit_seal": seal_record,
        "process_exit": exit_record,
    }
    for role, expected in records.items():
        if entries[role].file != expected:
            raise AuthorityError(
                f"candidate authority and manifest disagree for {role}"
            )

    allowed_paths = {
        authority_file.path,
        manifest_record.path,
        attempt_record.path,
        *(record.path for record in records.values()),
    }
    if len(allowed_paths) != 6:
        raise AuthorityError("candidate-run authority/manifest/artifact paths overlap")
    if set(snapshot) != allowed_paths:
        raise AuthorityError(
            "candidate vault tree is not closed; "
            f"extra={sorted(set(snapshot) - allowed_paths)}, "
            f"missing={sorted(allowed_paths - set(snapshot))}"
        )

    attempt_blob = _blob_for(snapshot, attempt_record, "candidate attempt claim")
    attempt = _mapping(
        strict_jcs_bytes(attempt_blob.data, context="candidate attempt claim"),
        "candidate attempt claim",
    )
    _exact_keys(attempt, _ATTEMPT_KEYS, "candidate attempt claim")
    _verify_common(
        attempt,
        ATTEMPT_SCHEMA,
        expected_stage,
        "candidate attempt claim",
    )
    if attempt["candidate_input_sha256"] != candidate_input:
        raise AuthorityError("candidate attempt input digest differs")
    attempt_input_commit, attempt_input_tree, attempt_input_file = _external_file_ref(
        attempt["stage_input_anchor"], "attempt.stage_input_anchor"
    )
    if (
        attempt_input_commit != input_commit
        or attempt_input_tree != input_tree
        or attempt_input_file != input_file
    ):
        raise AuthorityError("candidate attempt does not bind the stage input anchor")
    attempt_lock_commit, attempt_lock_tree, attempt_lock_file = _external_file_ref(
        attempt["candidate_execution_lock"], "attempt.candidate_execution_lock"
    )
    if (
        attempt_lock_commit != lock_commit
        or attempt_lock_tree != lock_tree
        or attempt_lock_file != lock_file
    ):
        raise AuthorityError("candidate attempt does not bind the execution lock")
    execution_commit, execution_tree = _commit_tree_ref(
        attempt["execution_source"], "attempt.execution_source"
    )
    if execution_commit != lock_commit or execution_tree != lock_tree:
        raise AuthorityError(
            "candidate attempt execution source differs from execution lock"
        )
    expected_repository_name = f"{expected_stage}-candidate-run"
    if repository.name != expected_repository_name:
        raise AuthorityError("candidate evidence repository name is not fixed")
    marker_path = repository.parent / f"{expected_repository_name}.attempt"
    try:
        marker_before = marker_path.lstat()
        marker_bytes = marker_path.read_bytes()
        marker_after = marker_path.lstat()
    except OSError as error:
        raise AuthorityError(
            f"candidate launcher claim is unavailable: {error}"
        ) from error
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(marker_before.st_mode)
        or stat.S_ISLNK(marker_before.st_mode)
        or getattr(marker_before, "st_file_attributes", 0) & reparse
        or marker_before.st_nlink != 1
        or marker_before.st_dev != marker_after.st_dev
        or marker_before.st_ino != marker_after.st_ino
        or marker_before.st_nlink != marker_after.st_nlink
        or marker_before.st_size != marker_after.st_size
        or marker_before.st_mtime_ns != marker_after.st_mtime_ns
        or len(marker_bytes) != marker_before.st_size
    ):
        raise AuthorityError("candidate launcher claim identity changed or is unsafe")
    marker = _jcs_object(marker_bytes, "candidate launcher claim")
    _exact_keys(
        marker,
        {
            "schema_version",
            "card_sha256",
            "stage",
            "nonce",
            "rerun_permitted",
            "failure_is_terminal",
        },
        "candidate launcher claim",
    )
    nonce = _hex(marker["nonce"], _SHA256, "candidate launcher nonce")
    if dict(marker) != {
        "schema_version": "geotarget.exp-local-003.candidate-launch-attempt/v2",
        "card_sha256": CARD_SHA256,
        "stage": expected_stage,
        "nonce": nonce,
        "rerun_permitted": False,
        "failure_is_terminal": True,
    }:
        raise AuthorityError("candidate launcher claim semantics differ")
    marker_sha = _sha256(marker_bytes)
    launcher_claim = _mapping(attempt["launcher_claim"], "attempt.launcher_claim")
    _exact_keys(
        launcher_claim,
        {"file", "nonce_sha256", "filesystem_identity"},
        "attempt.launcher_claim",
    )
    if _file_record(
        launcher_claim["file"], "attempt.launcher_claim.file"
    ) != FileRecord(marker_path.name, marker_sha, len(marker_bytes)):
        raise AuthorityError("candidate attempt launcher-claim file differs")
    if launcher_claim["nonce_sha256"] != _sha256(bytes.fromhex(nonce)):
        raise AuthorityError("candidate attempt launcher nonce binding differs")
    marker_identity = _mapping(
        launcher_claim["filesystem_identity"],
        "attempt.launcher_claim.filesystem_identity",
    )
    _exact_keys(
        marker_identity,
        {
            "device_decimal",
            "inode_decimal",
            "empty_claim_ctime_nanoseconds_decimal",
            "link_count",
        },
        "attempt.launcher_claim.filesystem_identity",
    )

    def identity_decimal(name: str) -> int:
        value = _string(
            marker_identity[name], f"attempt.launcher_claim.filesystem_identity.{name}"
        )
        if re.fullmatch(r"(?:0|[1-9][0-9]*)", value) is None:
            raise AuthorityError(f"candidate launcher identity {name} is not canonical")
        return int(value)

    if (
        identity_decimal("device_decimal") != marker_before.st_dev
        or identity_decimal("inode_decimal") != marker_before.st_ino
        or identity_decimal("empty_claim_ctime_nanoseconds_decimal") < 0
        or marker_identity["link_count"] != 1
        or authority["launcher_claim_sha256"] != marker_sha
    ):
        raise AuthorityError("candidate launcher filesystem identity differs")

    launcher_authority = expected_c0_authority(
        attempt["launcher_authority"],
        "research/experiments/EXP-LOCAL-003/source/launch_candidate.py",
        "attempt.launcher_authority",
    )
    observer_authority = expected_c0_authority(
        attempt["observer_authority"],
        "research/experiments/EXP-LOCAL-003/source/candidate_observer.py",
        "attempt.observer_authority",
    )
    broker_authority = expected_c0_authority(
        attempt["sandbox_broker_authority"],
        C0_SANDBOX_BROKER_PATH,
        "attempt.sandbox_broker_authority",
    )
    del launcher_authority
    if (
        authority["observer_authority"] != observer_authority
        or authority["sandbox_broker_authority"] != broker_authority
    ):
        raise AuthorityError("candidate final C0 authority binding differs")

    sandbox_request = _mapping(attempt["sandbox_request"], "attempt.sandbox_request")
    request_keys = {
        "backend",
        "claim_reference",
        "expected_read_identity_manifest_sha256",
        "command",
        "command_sha256",
        "working_directory",
        "environment",
        "environment_sha256",
        "allowed_read",
        "allowed_read_manifest_sha256",
        "access_probes",
        "access_probe_manifest_sha256",
        "capabilities",
        "network_capabilities",
        "timeout_seconds",
        "stdout_limit_bytes",
        "stderr_limit_bytes",
        "preexit_payload_limit_bytes",
        "job",
    }
    _exact_keys(sandbox_request, request_keys, "attempt.sandbox_request")
    command = _array(sandbox_request["command"], "attempt.sandbox_request.command")
    environment = _array(
        sandbox_request["environment"], "attempt.sandbox_request.environment"
    )
    grants = _array(
        sandbox_request["allowed_read"], "attempt.sandbox_request.allowed_read"
    )
    probes = _array(
        sandbox_request["access_probes"], "attempt.sandbox_request.access_probes"
    )
    for index, entry_value in enumerate(environment):
        entry = _mapping(entry_value, f"sandbox environment[{index}]")
        _exact_keys(entry, {"name", "value"}, f"sandbox environment[{index}]")
        _string(entry["name"], f"sandbox environment[{index}].name")
        _string(entry["value"], f"sandbox environment[{index}].value")
    environment_by_folded_name: dict[str, tuple[str, str]] = {}
    for index, entry_value in enumerate(environment):
        entry = _mapping(entry_value, f"sandbox environment[{index}]")
        name = cast(str, entry["name"])
        folded = name.casefold()
        if folded in environment_by_folded_name:
            raise AuthorityError("sandbox request has a duplicate environment name")
        environment_by_folded_name[folded] = (name, cast(str, entry["value"]))
    scratch_path = Path(cast(str, sandbox_request["working_directory"]))
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    environment_defaults = {
        "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"),
        "PATH": str(Path(system_root) / "System32"),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "SystemRoot": system_root,
        "HOME": str(scratch_path),
        "HOMEDRIVE": scratch_path.drive,
        "HOMEPATH": str(scratch_path)[len(scratch_path.drive) :],
        "USERPROFILE": str(scratch_path),
        "LOCALAPPDATA": str(scratch_path),
        "APPDATA": str(scratch_path),
        "TEMP": str(scratch_path),
        "TMP": str(scratch_path),
        "WINDIR": system_root,
    }
    for name, value in environment_defaults.items():
        environment_by_folded_name.setdefault(name.casefold(), (name, value))
    expected_attested_environment = [
        {"name": name, "value": value}
        for name, value in sorted(
            environment_by_folded_name.values(),
            key=lambda item: (item[0].casefold(), item[0]),
        )
    ]
    normalized_grants: list[dict[str, Any]] = []
    for index, grant_value in enumerate(grants):
        grant = _mapping(grant_value, f"sandbox read grant[{index}]")
        _exact_keys(grant, {"path", "recursive"}, f"sandbox read grant[{index}]")
        path = _string(grant["path"], f"sandbox read grant[{index}].path")
        if not isinstance(grant["recursive"], bool):
            raise AuthorityError("sandbox read-grant recursive flag is not boolean")
        normalized_grants.append(
            {"path": path, "recursive": cast(bool, grant["recursive"])}
        )
    candidate_root_name = (
        "development-candidate-inputs"
        if expected_stage == "development"
        else "locked-candidate-inputs"
    )
    expected_candidate_root = _REPOSITORY_ROOT.joinpath(
        "research", "experiments", EXPERIMENT_ID, candidate_root_name
    )
    expected_scratch = (
        _REPOSITORY_ROOT.with_name(f"{_REPOSITORY_ROOT.name}-sandbox-scratch")
        / EXPERIMENT_ID
        / f".{expected_stage}-candidate-run-scratch.partial"
    )
    project_root = _REPOSITORY_ROOT / "julia"
    project_files = (project_root / "Project.toml", project_root / "Manifest.toml")
    package_roots = tuple(
        project_root / name
        for name in ("GeoTargetBase", "GeoTargetCore", "GeoTargetGeometry")
    )
    package_projects = tuple(root / "Project.toml" for root in package_roots)
    package_sources = tuple(root / "src" for root in package_roots)
    candidate_runner = _REPOSITORY_ROOT.joinpath(*RUNNER_SOURCE_PATH.split("/"))
    recursive_roots = _collapse_recursive_roots(
        (julia_runtime_root, expected_candidate_root, *package_sources)
    )
    expected_grants: list[dict[str, Any]] = [
        {"path": str(root), "recursive": True} for root in recursive_roots
    ]
    expected_grants.append({"path": str(julia_depot_root), "recursive": False})
    for name in ("packages", "artifacts"):
        child = julia_depot_root / name
        if child.exists():
            expected_grants.append({"path": str(child), "recursive": True})
    discovery_paths = (
        _REPOSITORY_ROOT,
        project_root,
        candidate_runner,
        *project_files,
        *package_projects,
    )
    for file_path in discovery_paths:
        if not any(
            file_path == root or root in file_path.parents for root in recursive_roots
        ):
            expected_grants.append({"path": str(file_path), "recursive": False})

    expected_input_name = (
        "development-candidate-inputs.json.gz"
        if expected_stage == "development"
        else "locked-candidate-inputs.json.gz"
    )
    artifact_paths = {path for path, _digest in artifact_pairs}
    if not {"plugin/Local3FixturePlugin.jl", expected_input_name}.issubset(
        artifact_paths
    ):
        raise AuthorityError("candidate plugin/input codec authority is incomplete")

    environment_execution = _mapping(
        environment_document.get("execution"), "C0 environment execution"
    )
    python_execution = _mapping(
        environment_execution.get("python"), "C0 Python execution"
    )
    host_environment = _mapping(
        python_execution.get("host_environment"), "C0 host environment"
    )
    locked_system_root = host_environment.get("SystemRoot") or host_environment.get(
        "WINDIR"
    )
    if not isinstance(locked_system_root, str) or not locked_system_root:
        raise AuthorityError("C0 environment has no Windows system root")
    expected_environment_mapping = {
        "SystemRoot": locked_system_root,
        "WINDIR": locked_system_root,
        "PATH": os.pathsep.join(
            (str(julia_executable.parent), str(Path(locked_system_root) / "System32"))
        ),
        "JULIA_DEPOT_PATH": str(julia_depot_root),
        "JULIA_LOAD_PATH": os.pathsep.join(("@", "@stdlib")),
        "JULIA_NUM_THREADS": "1",
        "JULIA_CPU_TARGET": "generic",
        "JULIA_PKG_OFFLINE": "true",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "LC_ALL": "C",
        "LANG": "C",
        "GEOTARGET_JULIA_PROJECT": str(project_root),
        "GEOTARGET_EXECUTION_LOCK_SHA256": _sha256(canonical_bytes(execution_document)),
        "GEOTARGET_C0_PREEXIT_PROTOCOL": (
            "u64be-frame-flush-close-stdout-crt-close-fd1-yield-read-ack/v3"
        ),
    }
    expected_environment = [
        {"name": name, "value": value}
        for name, value in sorted(expected_environment_mapping.items())
    ]
    expected_command = [
        str(julia_executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={project_root}",
        str(candidate_runner),
        "--formal-appcontainer-child",
        expected_stage,
        str(expected_candidate_root),
        str(expected_scratch),
    ]
    expected_probe_bindings = (
        (
            str(expected_candidate_root.joinpath(*artifact_pairs[0][0].split("/"))),
            "allowed",
        ),
        (
            str(
                _REPOSITORY_ROOT.joinpath(
                    "research",
                    "experiments",
                    EXPERIMENT_ID,
                    "source",
                    "candidate_observer.py",
                )
            ),
            "denied",
        ),
        (
            str(
                _REPOSITORY_ROOT.with_name(f"{_REPOSITORY_ROOT.name}-vault")
                / EXPERIMENT_ID
                / f"{expected_stage}-assessor-vault"
            ),
            "denied",
        ),
        (
            str(
                _REPOSITORY_ROOT.with_name(f"{_REPOSITORY_ROOT.name}-private-audit")
                / EXPERIMENT_ID
                / f"{expected_stage}-generator-private-vault"
            ),
            "denied",
        ),
        (str(repository.parent.absolute()), "denied"),
        (
            str(
                repository.parent.absolute()
                / f".{expected_stage}-candidate-run-staging.partial"
            ),
            "denied",
        ),
        (str(marker_path.absolute()), "denied"),
        (
            str(
                _REPOSITORY_ROOT.with_name(
                    f"{_REPOSITORY_ROOT.name}-assessment-evidence"
                )
                / EXPERIMENT_ID
            ),
            "denied",
        ),
        (str(_REPOSITORY_ROOT / ".git"), "denied"),
    )
    if len(probes) != len(expected_probe_bindings):
        raise AuthorityError("candidate sandbox request probe count differs")
    for index, (probe_value, binding) in enumerate(
        zip(probes, expected_probe_bindings, strict=True)
    ):
        probe = _mapping(probe_value, f"sandbox request probe[{index}]")
        _exact_keys(probe, {"path", "expected"}, f"sandbox request probe[{index}]")
        path, state = binding
        if (
            _string(probe["path"], f"sandbox request probe[{index}].path") != path
            or probe["expected"] != state
        ):
            raise AuthorityError("candidate sandbox request probe policy differs")
    if (
        sandbox_request["backend"] != "windows-classic-appcontainer"
        or sandbox_request["claim_reference"] != marker_sha
        or _SHA256.fullmatch(
            _string(
                sandbox_request["expected_read_identity_manifest_sha256"],
                "sandbox expected read-identity manifest",
            )
        )
        is None
        or command != expected_command
        or sandbox_request["working_directory"] != str(expected_scratch)
        or environment != expected_environment
        or normalized_grants != expected_grants
        or sandbox_request["command_sha256"] != _sha256(canonical_bytes(command))
        or sandbox_request["environment_sha256"]
        != _sha256(canonical_bytes(environment))
        or sandbox_request["allowed_read_manifest_sha256"]
        != _sha256(canonical_bytes(grants))
        or sandbox_request["access_probe_manifest_sha256"]
        != _sha256(canonical_bytes(probes))
        or sandbox_request["capabilities"] != []
        or sandbox_request["network_capabilities"] != []
        or sandbox_request["timeout_seconds"] != 21_600
        or sandbox_request["stdout_limit_bytes"] != 256 * 1024 * 1024
        or sandbox_request["stderr_limit_bytes"] != 1024 * 1024
        or sandbox_request["preexit_payload_limit_bytes"] != 256 * 1024 * 1024 - 8
    ):
        raise AuthorityError("candidate sandbox request semantics differ")
    request_job = _mapping(sandbox_request["job"], "attempt.sandbox_request.job")
    _exact_keys(
        request_job,
        {
            "assigned_at_creation",
            "breakaway_allowed",
            "child_process_policy",
            "kill_on_close",
            "max_processes",
        },
        "attempt.sandbox_request.job",
    )
    if dict(request_job) != {
        "assigned_at_creation": True,
        "breakaway_allowed": False,
        "child_process_policy": "restricted-no-descendants",
        "kill_on_close": True,
        "max_processes": 1,
    }:
        raise AuthorityError("candidate sandbox Job policy differs")
    if attempt["rerun_permitted"] is not False:
        raise AuthorityError("candidate attempt must permanently forbid rerun")
    prelaunch = _mapping(attempt["prelaunch_state"], "attempt.prelaunch_state")
    _exact_keys(
        prelaunch,
        {
            "launch_not_started",
            "candidate_process_created",
            "repository_control",
            "runner_evaluated_by_observer",
            "assessor_started",
            "assessor_vault_opened",
            "generator_private_vault_opened",
        },
        "attempt.prelaunch_state",
    )
    if dict(prelaunch) != {
        "launch_not_started": True,
        "candidate_process_created": False,
        "repository_control": "c0-observer",
        "runner_evaluated_by_observer": False,
        "assessor_started": False,
        "assessor_vault_opened": False,
        "generator_private_vault_opened": False,
    }:
        raise AuthorityError(
            "candidate attempt is not an observer-owned prelaunch claim"
        )

    raw_compressed = _blob_for(snapshot, raw_record, "candidate raw output").data
    raw_jcs = decode_deterministic_gzip(raw_compressed, context="candidate raw output")
    raw = _mapping(
        strict_jcs_bytes(raw_jcs, context="candidate raw output"),
        "candidate raw output",
    )
    _exact_keys(
        raw,
        {
            "schema_version",
            "stage",
            "candidate_input_sha256",
            "candidate_process",
            "cases",
            "report_only_times",
        },
        "candidate raw output",
    )
    if (
        raw.get("schema_version") != "geotarget.exp-local-003.candidate-output/v1"
        or raw.get("stage") != expected_stage
    ):
        raise AuthorityError("candidate raw output stage differs")
    if raw.get("candidate_input_sha256") != candidate_input:
        raise AuthorityError("candidate raw output input digest differs")
    raw_process = _mapping(raw.get("candidate_process"), "candidate raw process")
    _exact_keys(
        raw_process,
        {
            "runner_source_path",
            "runner_source_sha256",
            "observation_complete",
            "source_manifest_sha256",
            "loaded_sources",
            "opened_artifacts",
        },
        "candidate raw process",
    )
    if (
        raw_process["runner_source_path"] != execution_document["runner_source_path"]
        or raw_process["runner_source_sha256"]
        != execution_document["runner_source_sha256"]
        or raw_process["observation_complete"] is not True
        or raw_process["source_manifest_sha256"]
        != execution_document["source_manifest_sha256"]
        or raw_process["loaded_sources"] != execution_document["allowed_sources"]
        or raw_process["opened_artifacts"]
        != execution_document["allowed_candidate_artifacts"]
    ):
        raise AuthorityError("candidate raw process authority differs from lock")

    seal_blob = _blob_for(snapshot, seal_record, "candidate pre-exit seal")
    seal = _mapping(
        strict_jcs_bytes(seal_blob.data, context="candidate pre-exit seal"),
        "candidate pre-exit seal",
    )
    _exact_keys(seal, _PREEXIT_KEYS, "candidate pre-exit seal")
    _verify_common(seal, PREEXIT_SCHEMA, expected_stage, "candidate pre-exit seal")
    if (
        seal["process_instance_id"] != process_id
        or seal["candidate_input_sha256"] != candidate_input
    ):
        raise AuthorityError("pre-exit seal process/input identity differs")
    if seal["launcher_claim"] != launcher_claim:
        raise AuthorityError("pre-exit launcher claim differs")
    if seal["observer_authority"] != observer_authority:
        raise AuthorityError("pre-exit observer authority differs")
    request_sha = _sha256(canonical_bytes(sandbox_request))
    if seal["sandbox_request_sha256"] != request_sha:
        raise AuthorityError("pre-exit sandbox-request binding differs")
    observation = _mapping(seal["preexit_observation"], "seal.preexit_observation")
    _exact_keys(
        observation,
        {
            "process_id",
            "active_processes",
            "root_process_still_active",
            "payload_sha256",
            "payload_byte_length",
            "observer_elapsed_nanoseconds_decimal",
            "runner_evaluated_by_observer",
            "raw_output_stream_closed_before_ack",
            "ack_pending",
            "assessor_started",
            "assessor_vault_opened",
            "generator_private_vault_opened",
        },
        "seal.preexit_observation",
    )
    preexit_pid = _integer(
        observation["process_id"], "seal.preexit_observation.process_id", minimum=1
    )
    raw_payload_sha = _sha256(raw_jcs)
    elapsed_text = _string(
        observation["observer_elapsed_nanoseconds_decimal"],
        "seal.preexit_observation.observer_elapsed_nanoseconds_decimal",
    )
    if re.fullmatch(r"(?:0|[1-9][0-9]*)", elapsed_text) is None:
        raise AuthorityError("pre-exit elapsed time is not canonical decimal")
    if (
        observation["active_processes"] != 1
        or observation["root_process_still_active"] is not True
        or observation["payload_sha256"] != raw_payload_sha
        or observation["payload_byte_length"] != len(raw_jcs)
        or observation["runner_evaluated_by_observer"] is not False
        or observation["raw_output_stream_closed_before_ack"] is not True
        or observation["ack_pending"] is not True
        or observation["assessor_started"] is not False
        or observation["assessor_vault_opened"] is not False
        or observation["generator_private_vault_opened"] is not False
    ):
        raise AuthorityError("pre-exit kernel/observer evidence differs")
    expected_process_id = _sha256(
        b"GTLOCAL3C0PROCESS1\0"
        + bytes.fromhex(nonce)
        + str(preexit_pid).encode("ascii")
        + bytes.fromhex(raw_payload_sha)
        + len(lock_commit).to_bytes(1, "big")
        + bytes.fromhex(lock_commit)
    )
    if process_id != expected_process_id:
        raise AuthorityError("candidate process-instance id cannot be reproduced")
    if _file_record(seal["raw_output"], "seal.raw_output") != raw_record:
        raise AuthorityError("pre-exit seal raw record differs")
    _changed_paths(seal["changed_paths"], raw_record.path, "seal.changed_paths")
    seal_event = _mapping(seal["event"], "seal.event")
    _exact_keys(seal_event, {"kind", "ordinal", "parent"}, "seal.event")
    if (
        seal_event["kind"] != "candidate-output-preexit-seal"
        or _integer(seal_event["ordinal"], "seal.event.ordinal") != 2
    ):
        raise AuthorityError("pre-exit seal event identity differs")
    _parent(
        seal_event["parent"],
        "candidate-raw-output",
        raw_record.sha256,
        "seal.event.parent",
    )
    seal_ack = _mapping(seal["ack"], "seal.ack")
    _exact_keys(
        seal_ack,
        {
            "token_sha256",
            "raw_closed_ordinal",
            "seal_persisted_ordinal",
            "ack_released_ordinal",
        },
        "seal.ack",
    )
    ack_token = _hex(seal_ack["token_sha256"], _SHA256, "seal.ack.token_sha256")
    seal_order = (
        _integer(seal_ack["raw_closed_ordinal"], "seal.ack.raw_closed_ordinal"),
        _integer(seal_ack["seal_persisted_ordinal"], "seal.ack.seal_persisted_ordinal"),
        _integer(seal_ack["ack_released_ordinal"], "seal.ack.ack_released_ordinal"),
    )
    if seal_order != (1, 2, 3):
        raise AuthorityError("pre-exit seal/ACK ordering differs")

    exit_blob = _blob_for(snapshot, exit_record, "candidate process exit")
    exit_document = _mapping(
        strict_jcs_bytes(exit_blob.data, context="candidate process exit"),
        "candidate process exit",
    )
    _exact_keys(exit_document, _EXIT_KEYS, "candidate process exit")
    _verify_common(exit_document, EXIT_SCHEMA, expected_stage, "candidate process exit")
    if (
        exit_document["process_instance_id"] != process_id
        or exit_document["candidate_input_sha256"] != candidate_input
    ):
        raise AuthorityError("process-exit process/input identity differs")
    if exit_document["launcher_claim"] != launcher_claim:
        raise AuthorityError("process-exit launcher claim differs")
    if exit_document["observer_authority"] != observer_authority:
        raise AuthorityError("process-exit observer authority differs")
    termination = _mapping(
        exit_document["termination_observation"], "exit.termination_observation"
    )
    termination_keys = {
        "wait_observed",
        "job_tree_empty",
        "ack_sent_after_preexit_commit",
        "candidate_access_revoked",
        "profile_deleted",
        "scratch_emptied",
        "runner_evaluated_by_observer",
        "assessor_started",
        "assessor_vault_opened",
        "generator_private_vault_opened",
    }
    _exact_keys(termination, termination_keys, "exit.termination_observation")
    expected_termination = {
        "wait_observed": True,
        "job_tree_empty": True,
        "ack_sent_after_preexit_commit": True,
        "candidate_access_revoked": True,
        "profile_deleted": True,
        "scratch_emptied": True,
        "runner_evaluated_by_observer": False,
        "assessor_started": False,
        "assessor_vault_opened": False,
        "generator_private_vault_opened": False,
    }
    if dict(termination) != expected_termination:
        raise AuthorityError("candidate termination evidence differs")
    if _file_record(exit_document["raw_output"], "exit.raw_output") != raw_record:
        raise AuthorityError("process-exit raw record differs")
    if _file_record(exit_document["preexit_seal"], "exit.preexit_seal") != seal_record:
        raise AuthorityError("process-exit seal record differs")
    _changed_paths(
        exit_document["changed_paths"], raw_record.path, "exit.changed_paths"
    )
    exit_event = _mapping(exit_document["event"], "exit.event")
    _exact_keys(exit_event, {"kind", "ordinal", "parent"}, "exit.event")
    if (
        exit_event["kind"] != "candidate-process-exit"
        or _integer(exit_event["ordinal"], "exit.event.ordinal") != 5
    ):
        raise AuthorityError("process-exit event identity differs")
    _parent(
        exit_event["parent"],
        "candidate-output-preexit-seal",
        seal_record.sha256,
        "exit.event.parent",
    )
    exit_ack = _mapping(exit_document["ack"], "exit.ack")
    _exact_keys(
        exit_ack,
        {
            "token_sha256",
            "ack_released_ordinal",
            "successful_exit_after_ack_ordinal",
            "job_empty_observed_ordinal",
        },
        "exit.ack",
    )
    if _hex(exit_ack["token_sha256"], _SHA256, "exit.ack.token_sha256") != ack_token:
        raise AuthorityError("process-exit ACK token differs")
    exit_order = (
        _integer(exit_ack["ack_released_ordinal"], "exit.ack.ack_released_ordinal"),
        _integer(
            exit_ack["successful_exit_after_ack_ordinal"],
            "exit.ack.successful_exit_after_ack_ordinal",
        ),
        _integer(
            exit_ack["job_empty_observed_ordinal"],
            "exit.ack.job_empty_observed_ordinal",
        ),
    )
    if exit_order != (3, 4, 5):
        raise AuthorityError("candidate ACK/exit ordering differs")
    exit_status = _mapping(exit_document["exit_status"], "exit.exit_status")
    _exact_keys(exit_status, {"kind", "code"}, "exit.exit_status")
    if (
        exit_status["kind"] != "exited"
        or _integer(exit_status["code"], "exit.exit_status.code") != 0
    ):
        raise AuthorityError("formal candidate process did not exit successfully")

    sandbox_result = _mapping(exit_document["sandbox_result"], "exit.sandbox_result")
    _exact_keys(
        sandbox_result,
        {
            "command_sha256",
            "return_code",
            "termination_reason",
            "stdout_sha256",
            "stdout_byte_length",
            "stderr_sha256",
            "stderr_byte_length",
            "preexit_receipt",
            "job_accounting",
            "appcontainer_attestation",
        },
        "exit.sandbox_result",
    )
    if (
        sandbox_result["command_sha256"] != sandbox_request["command_sha256"]
        or sandbox_result["return_code"] != 0
        or sandbox_result["termination_reason"] != "completed"
        or sandbox_result["stdout_sha256"] != raw_payload_sha
        or sandbox_result["stdout_byte_length"] != len(raw_jcs)
        or sandbox_result["stderr_sha256"] != _sha256(b"")
        or sandbox_result["stderr_byte_length"] != 0
        or authority["sandbox_result_sha256"]
        != _sha256(canonical_bytes(sandbox_result))
    ):
        raise AuthorityError("candidate sandbox result stream/authority differs")

    receipt = _mapping(
        sandbox_result["preexit_receipt"], "exit.sandbox_result.preexit_receipt"
    )
    _exact_keys(
        receipt,
        {
            "payload_sha256",
            "payload_byte_length",
            "ack_sha256",
            "ack_byte_length",
            "active_processes_before_callback",
            "root_active_before_callback",
            "active_processes_before_ack",
            "root_active_before_ack",
            "callback_completed",
            "ack_released",
        },
        "exit.sandbox_result.preexit_receipt",
    )
    if (
        receipt["payload_sha256"] != raw_payload_sha
        or receipt["payload_byte_length"] != len(raw_jcs)
        or receipt["ack_sha256"] != ack_token
        or _integer(receipt["ack_byte_length"], "preexit receipt ack length", minimum=1)
        < 1
        or receipt["active_processes_before_callback"] != 1
        or receipt["root_active_before_callback"] is not True
        or receipt["active_processes_before_ack"] != 1
        or receipt["root_active_before_ack"] is not True
        or receipt["callback_completed"] is not True
        or receipt["ack_released"] is not True
    ):
        raise AuthorityError("candidate pre-exit ACK receipt differs")

    job_accounting = _mapping(
        sandbox_result["job_accounting"], "exit.sandbox_result.job_accounting"
    )
    job_accounting_keys = {
        "wall_time_nanoseconds_decimal",
        "total_user_time_100ns_decimal",
        "total_kernel_time_100ns_decimal",
        "total_processes",
        "terminated_processes",
        "read_operation_count_decimal",
        "write_operation_count_decimal",
        "other_operation_count_decimal",
        "read_transfer_count_decimal",
        "write_transfer_count_decimal",
        "other_transfer_count_decimal",
    }
    _exact_keys(
        job_accounting,
        job_accounting_keys,
        "exit.sandbox_result.job_accounting",
    )

    def job_decimal(name: str) -> int:
        text = _string(job_accounting[name], f"job_accounting.{name}")
        if re.fullmatch(r"(?:0|[1-9][0-9]*)", text) is None:
            raise AuthorityError(f"job accounting {name} is not canonical")
        return int(text)

    for decimal_name in job_accounting_keys - {
        "total_processes",
        "terminated_processes",
    }:
        job_decimal(decimal_name)
    if (
        job_accounting["total_processes"] != 1
        or job_accounting["terminated_processes"] != 0
    ):
        raise AuthorityError("candidate Job process accounting differs")

    attestation = _mapping(
        sandbox_result["appcontainer_attestation"],
        "exit.sandbox_result.appcontainer_attestation",
    )
    attestation_keys = {
        "schema_version",
        "claim_reference",
        "profile_name",
        "package_sid",
        "profile_storage_path",
        "capabilities",
        "allowed_read_paths",
        "read_identity_manifest_entry_count",
        "read_identity_manifest_sha256",
        "scratch_directory",
        "environment",
        "inherited_handle_roles",
        "process_id",
        "token_is_appcontainer",
        "token_appcontainer_sid_verified",
        "token_integrity_rid",
        "token_elevated",
        "token_capability_count",
        "access_probes",
        "denied_probe_entry_count",
        "denied_probe_manifest_sha256",
        "read_only_probe_entry_count",
        "read_only_probe_manifest_sha256",
        "scratch_access_probe_manifest_sha256",
        "max_processes",
        "child_process_restricted",
        "job_assigned_at_creation",
        "job_membership_verified",
        "job_limit_flags",
        "breakaway_allowed",
        "kill_on_job_close",
        "job_empty",
        "acl_entry_count",
        "original_acl_manifest_sha256",
        "restored_acl_manifest_sha256",
        "acl_exactly_restored",
        "scratch_emptied",
        "profile_deleted",
        "profile_storage_deleted",
    }
    _exact_keys(attestation, attestation_keys, "AppContainer attestation")
    expected_allowed_read = [item["path"] for item in grants]
    if (
        attestation["schema_version"]
        != "geotarget.exp-local-003.appcontainer-attestation/v2"
        or attestation["claim_reference"] != marker_sha
        or attestation["capabilities"] != []
        or attestation["allowed_read_paths"] != expected_allowed_read
        or attestation["read_identity_manifest_sha256"]
        != sandbox_request["expected_read_identity_manifest_sha256"]
        or attestation["scratch_directory"] != sandbox_request["working_directory"]
        or attestation["environment"] != expected_attested_environment
        or attestation["inherited_handle_roles"] != ["stdin", "stdout", "stderr"]
        or attestation["process_id"] != preexit_pid
        or attestation["token_is_appcontainer"] is not True
        or attestation["token_appcontainer_sid_verified"] is not True
        or attestation["token_integrity_rid"] != 4096
        or attestation["token_elevated"] is not False
        or attestation["token_capability_count"] != 0
        or attestation["max_processes"] != 1
        or attestation["child_process_restricted"] is not True
        or attestation["job_assigned_at_creation"] is not True
        or attestation["job_membership_verified"] is not True
        or attestation["job_limit_flags"] != 0x00002008
        or attestation["breakaway_allowed"] is not False
        or attestation["kill_on_job_close"] is not True
        or attestation["job_empty"] is not True
        or attestation["acl_exactly_restored"] is not True
        or attestation["scratch_emptied"] is not True
        or attestation["profile_deleted"] is not True
        or attestation["profile_storage_deleted"] is not True
        or attestation["original_acl_manifest_sha256"]
        != attestation["restored_acl_manifest_sha256"]
    ):
        raise AuthorityError("candidate AppContainer security policy differs")
    profile_storage_path = _string(
        attestation["profile_storage_path"], "AppContainer profile storage path"
    )
    profile_name = _string(attestation["profile_name"], "AppContainer profile name")
    package_sid = _string(attestation["package_sid"], "AppContainer package SID")
    if (
        not profile_name.startswith("GeoTarget.EXPLOCAL003.")
        or re.fullmatch(r"S-1-15-2-(?:[0-9]+-)*[0-9]+", package_sid) is None
        or not Path(profile_storage_path).is_absolute()
        or os.path.lexists(profile_storage_path)
    ):
        raise AuthorityError("AppContainer identity or deleted storage differs")
    for digest_name in (
        "read_identity_manifest_sha256",
        "denied_probe_manifest_sha256",
        "read_only_probe_manifest_sha256",
        "scratch_access_probe_manifest_sha256",
        "original_acl_manifest_sha256",
        "restored_acl_manifest_sha256",
    ):
        _hex(attestation[digest_name], _SHA256, f"attestation.{digest_name}")
    _integer(
        attestation["read_identity_manifest_entry_count"],
        "attestation.read_identity_manifest_entry_count",
        minimum=1,
    )
    read_only_count = _integer(
        attestation["read_only_probe_entry_count"],
        "attestation.read_only_probe_entry_count",
        minimum=1,
    )
    denied_target_count = sum(
        probe["expected"] == "denied"
        for probe in (
            _mapping(value, "candidate requested access probe") for value in probes
        )
    )
    _integer(
        attestation["denied_probe_entry_count"],
        "attestation.denied_probe_entry_count",
        minimum=denied_target_count,
    )
    if (
        attestation["read_identity_manifest_entry_count"] != read_only_count
        or attestation["acl_entry_count"] != read_only_count + 1
    ):
        raise AuthorityError("candidate AppContainer ACL accounting differs")
    observed_probes = _array(attestation["access_probes"], "attested access probes")
    if len(observed_probes) != len(probes):
        raise AuthorityError("candidate AppContainer access probe count differs")
    for index, (requested_value, observed_value) in enumerate(
        zip(probes, observed_probes, strict=True)
    ):
        requested = _mapping(requested_value, f"requested access probe {index}")
        observed = _mapping(observed_value, f"attested access probe {index}")
        _exact_keys(
            observed,
            {"path", "expected", "observed", "winerror"},
            f"attested access probe {index}",
        )
        expected_state = requested["expected"]
        expected_winerror = 0 if expected_state == "allowed" else 5
        if (
            observed["path"] != requested["path"]
            or observed["expected"] != expected_state
            or observed["observed"] != expected_state
            or observed["winerror"] != expected_winerror
        ):
            raise AuthorityError("candidate AppContainer kernel probe differs")

    candidate_accounting = _mapping(
        exit_document["candidate_accounting"], "exit.candidate_accounting"
    )
    _exact_keys(
        candidate_accounting,
        {
            "process_cpu_nanoseconds_decimal",
            "observer_wall_nanoseconds_decimal",
            "host_exclusion_passed",
            "count_in_end_to_end_exactly_once",
        },
        "exit.candidate_accounting",
    )

    def accounting_decimal(name: str) -> int:
        text = _string(candidate_accounting[name], f"exit.candidate_accounting.{name}")
        if re.fullmatch(r"(?:0|[1-9][0-9]*)", text) is None:
            raise AuthorityError(f"candidate accounting {name} is not canonical")
        return int(text)

    candidate_cpu = accounting_decimal("process_cpu_nanoseconds_decimal")
    candidate_wall = accounting_decimal("observer_wall_nanoseconds_decimal")
    if (
        candidate_accounting["host_exclusion_passed"] is not True
        or candidate_accounting["count_in_end_to_end_exactly_once"] is not True
        or candidate_cpu
        != (
            job_decimal("total_user_time_100ns_decimal")
            + job_decimal("total_kernel_time_100ns_decimal")
        )
        * 100
        or candidate_wall != job_decimal("wall_time_nanoseconds_decimal")
        or int(elapsed_text) > candidate_wall
    ):
        raise AuthorityError("candidate observer accounting flags differ")

    return CandidateRunRecord(
        stage=expected_stage,
        process_instance_id=process_id,
        candidate_input_sha256=candidate_input,
        candidate_execution_lock_sha256=execution_lock,
        candidate_execution_lock_commit=lock_commit,
        candidate_execution_lock_tree=lock_tree,
        candidate_execution_lock_file=lock_file,
        candidate_execution_lock_jcs=lock_blob.data,
        candidate_execution_lock=_deep_freeze(execution_document),
        candidate_process_cpu_nanoseconds=candidate_cpu,
        candidate_observer_wall_nanoseconds=candidate_wall,
        vault_commit=commit,
        vault_tree=tree,
        authority_file=authority_file,
        manifest_file=manifest_record,
        attempt_claim_file=attempt_record,
        raw_output_file=raw_record,
        preexit_seal_file=seal_record,
        process_exit_file=exit_record,
        attempt_claim_jcs=attempt_blob.data,
        attempt_claim=_deep_freeze(attempt),
        raw_output_jcs=raw_jcs,
        raw_output=_deep_freeze(raw),
        preexit_seal=_deep_freeze(seal),
        process_exit=_deep_freeze(exit_document),
        authority=_deep_freeze(authority),
    )


def assess_with_authority(
    assess: Callable[[Any, Any, bytes, Any], Any],
    *,
    stage_input: StageInputRecord,
    candidate_run: CandidateRunRecord,
) -> FormalAssessmentRecord:
    """Run the frozen assessor and account C1/candidate/assessor exactly once."""

    if candidate_run.stage != stage_input.stage:
        raise AuthorityError("assessment authorities have different stages")
    execution_lock = _mapping(
        strict_jcs_bytes(
            candidate_run.candidate_execution_lock_jcs,
            context="candidate execution lock",
        ),
        "candidate execution lock",
    )
    if (
        _sha256(candidate_run.candidate_execution_lock_jcs)
        != candidate_run.candidate_execution_lock_sha256
    ):
        raise AuthorityError(
            "assessment execution-lock bytes differ from candidate run"
        )
    raw = _mapping(
        strict_jcs_bytes(candidate_run.raw_output_jcs, context="sealed candidate raw"),
        "sealed candidate raw",
    )
    truth = _mapping(
        strict_jcs_bytes(
            stage_input.assessor_truth_jcs, context="sealed assessor truth"
        ),
        "sealed assessor truth",
    )
    cpu_started = time.process_time_ns()
    wall_started = time.perf_counter_ns()
    try:
        result = assess(raw, truth, stage_input.bootstrap_indices, execution_lock)
    except Exception as error:
        raise AuthorityError(f"formal assessor failed: {error}") from error
    assessor_cpu = time.process_time_ns() - cpu_started
    assessor_wall = time.perf_counter_ns() - wall_started
    try:
        assessment_jcs = canonical_bytes(result)
    except (TypeError, ValueError) as error:
        raise AuthorityError(
            f"formal assessment is not JCS encodable: {error}"
        ) from error
    assessment = _mapping(
        strict_jcs_bytes(assessment_jcs, context="formal assessment"),
        "formal assessment",
    )
    assessment_times = _mapping(
        assessment.get("report_only_times"), "assessment.report_only_times"
    )
    if (
        assessment_times.get("host_exclusion_passed") is not False
        or assessment_times.get("formal_wall_seconds") is not None
    ):
        raise AuthorityError(
            "formal wall must be null when all-phase host exclusion is not proven"
        )
    c1 = _mapping(stage_input.anchor["c1_phase_accounting"], "c1 accounting")
    c1_cpu = int(c1["total_process_cpu_nanoseconds_decimal"])
    c1_wall = int(c1["monotonic_elapsed_nanoseconds_decimal"])
    total_cpu = c1_cpu + candidate_run.candidate_process_cpu_nanoseconds + assessor_cpu
    total_wall = (
        c1_wall + candidate_run.candidate_observer_wall_nanoseconds + assessor_wall
    )
    authority = {
        "schema_version": ASSESSOR_AUTHORITY_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": stage_input.stage,
        "stage_input_anchor_sha256": stage_input.anchor_file.sha256,
        "candidate_run_authority_sha256": candidate_run.authority_file.sha256,
        "candidate_execution_lock_sha256": candidate_run.candidate_execution_lock_sha256,
        "candidate_raw_output_sha256": candidate_run.raw_output_file.sha256,
        "assessor_truth_sha256": stage_input.assessor_truth_file.sha256,
        "bootstrap_sha256": stage_input.bootstrap_file.sha256,
        "assessment_sha256": _sha256(assessment_jcs),
        "accounting": {
            "c1_cpu_nanoseconds_decimal": str(c1_cpu),
            "candidate_cpu_nanoseconds_decimal": str(
                candidate_run.candidate_process_cpu_nanoseconds
            ),
            "assessor_cpu_nanoseconds_decimal": str(assessor_cpu),
            "end_to_end_cpu_nanoseconds_decimal": str(total_cpu),
            "c1_wall_nanoseconds_decimal": str(c1_wall),
            "candidate_wall_nanoseconds_decimal": str(
                candidate_run.candidate_observer_wall_nanoseconds
            ),
            "assessor_wall_nanoseconds_decimal": str(assessor_wall),
            "end_to_end_wall_nanoseconds_decimal": str(total_wall),
            "formal_wall_host_exclusion_passed": False,
            "formal_wall_nanoseconds_decimal": None,
            "exactly_once_components": ["c1", "candidate", "assessor"],
        },
    }
    authority_jcs = canonical_bytes(authority)
    return FormalAssessmentRecord(
        stage=stage_input.stage,
        assessment_jcs=assessment_jcs,
        assessment=_deep_freeze(assessment),
        authority_jcs=authority_jcs,
        authority=_deep_freeze(authority),
        end_to_end_cpu_nanoseconds=total_cpu,
        end_to_end_wall_nanoseconds=total_wall,
    )


def resolve_assessor_stage_output(
    repository: Path,
    *,
    assess: Callable[[Any, Any, bytes, Any], Any],
    build_development_decision: Callable[..., Any] | None,
    assessment_commit: str,
    assessment_tree: str,
    assessment_file: FileRecord,
    authority_file: FileRecord,
    stage_input: StageInputRecord,
    candidate_run: CandidateRunRecord,
    git_executable: GitExecutable,
    decision_commit: str | None = None,
    decision_tree: str | None = None,
    decision_file: FileRecord | None = None,
) -> ResolvedAssessmentOutput:
    """Resolve the two-file assessment commit and its optional decision child."""

    if candidate_run.stage != stage_input.stage:
        raise AuthorityError("assessor output inputs have different stages")
    repo = GitObjectRepository(repository, git_executable)
    if repo.commit_parents(assessment_commit):
        raise AuthorityError("assessment authority commit must be an orphan root")
    assessment_snapshot = repo.snapshot(assessment_commit, assessment_tree)
    expected_assessment_paths = {assessment_file.path, authority_file.path}
    if (
        assessment_file.path == authority_file.path
        or set(assessment_snapshot) != expected_assessment_paths
    ):
        raise AuthorityError(
            "assessment commit tree is not the exact two-file authority"
        )
    assessment_blob = _blob_for(
        assessment_snapshot, assessment_file, "persisted assessment"
    )
    authority_blob = _blob_for(
        assessment_snapshot, authority_file, "persisted assessor-stage authority"
    )
    assessment = _jcs_object(assessment_blob.data, "persisted assessment")
    authority_document = _jcs_object(
        authority_blob.data, "persisted assessor-stage authority"
    )
    _exact_keys(
        authority_document,
        _ASSESSOR_OUTPUT_KEYS,
        "persisted assessor-stage authority",
    )
    _verify_common(
        authority_document,
        ASSESSOR_AUTHORITY_SCHEMA,
        stage_input.stage,
        "persisted assessor-stage authority",
    )
    expected_hashes = {
        "stage_input_anchor_sha256": stage_input.anchor_file.sha256,
        "candidate_run_authority_sha256": candidate_run.authority_file.sha256,
        "candidate_execution_lock_sha256": candidate_run.candidate_execution_lock_sha256,
        "candidate_raw_output_sha256": candidate_run.raw_output_file.sha256,
        "assessor_truth_sha256": stage_input.assessor_truth_file.sha256,
        "bootstrap_sha256": stage_input.bootstrap_file.sha256,
        "assessment_sha256": assessment_file.sha256,
    }
    for field, expected in expected_hashes.items():
        if authority_document[field] != expected:
            raise AuthorityError(f"assessor-stage authority {field} differs")
    if assessment.get("stage") != stage_input.stage:
        raise AuthorityError("persisted assessment stage differs")
    recomputed = assess(
        _mapping(
            strict_jcs_bytes(
                candidate_run.raw_output_jcs, context="verified candidate raw"
            ),
            "verified candidate raw",
        ),
        _mapping(
            strict_jcs_bytes(
                stage_input.assessor_truth_jcs, context="verified assessor truth"
            ),
            "verified assessor truth",
        ),
        stage_input.bootstrap_indices,
        _mapping(
            strict_jcs_bytes(
                candidate_run.candidate_execution_lock_jcs,
                context="verified execution lock",
            ),
            "verified execution lock",
        ),
    )
    if canonical_bytes(recomputed) != assessment_blob.data:
        raise AuthorityError("persisted assessment differs from frozen recomputation")
    assessment_times = _mapping(
        assessment.get("report_only_times"), "assessment.report_only_times"
    )
    if (
        assessment_times.get("host_exclusion_passed") is not False
        or assessment_times.get("formal_wall_seconds") is not None
    ):
        raise AuthorityError("persisted assessment misstates formal wall validity")

    accounting = _mapping(authority_document["accounting"], "authority.accounting")
    accounting_keys = {
        "c1_cpu_nanoseconds_decimal",
        "candidate_cpu_nanoseconds_decimal",
        "assessor_cpu_nanoseconds_decimal",
        "end_to_end_cpu_nanoseconds_decimal",
        "c1_wall_nanoseconds_decimal",
        "candidate_wall_nanoseconds_decimal",
        "assessor_wall_nanoseconds_decimal",
        "end_to_end_wall_nanoseconds_decimal",
        "formal_wall_host_exclusion_passed",
        "formal_wall_nanoseconds_decimal",
        "exactly_once_components",
    }
    _exact_keys(accounting, accounting_keys, "authority.accounting")

    def decimal(name: str) -> int:
        text = _string(accounting[name], f"authority.accounting.{name}")
        if re.fullmatch(r"(?:0|[1-9][0-9]*)", text) is None:
            raise AuthorityError(f"authority accounting {name} is not canonical")
        return int(text)

    c1_cpu = decimal("c1_cpu_nanoseconds_decimal")
    candidate_cpu = decimal("candidate_cpu_nanoseconds_decimal")
    assessor_cpu = decimal("assessor_cpu_nanoseconds_decimal")
    total_cpu = decimal("end_to_end_cpu_nanoseconds_decimal")
    c1_wall = decimal("c1_wall_nanoseconds_decimal")
    candidate_wall = decimal("candidate_wall_nanoseconds_decimal")
    assessor_wall = decimal("assessor_wall_nanoseconds_decimal")
    total_wall = decimal("end_to_end_wall_nanoseconds_decimal")
    anchor_accounting = _mapping(
        stage_input.anchor["c1_phase_accounting"], "stage c1 accounting"
    )
    if (
        c1_cpu != int(anchor_accounting["total_process_cpu_nanoseconds_decimal"])
        or candidate_cpu != candidate_run.candidate_process_cpu_nanoseconds
        or total_cpu != c1_cpu + candidate_cpu + assessor_cpu
        or c1_wall != int(anchor_accounting["monotonic_elapsed_nanoseconds_decimal"])
        or candidate_wall != candidate_run.candidate_observer_wall_nanoseconds
        or total_wall != c1_wall + candidate_wall + assessor_wall
        or accounting["formal_wall_host_exclusion_passed"] is not False
        or accounting["formal_wall_nanoseconds_decimal"] is not None
        or accounting["exactly_once_components"] != ["c1", "candidate", "assessor"]
    ):
        raise AuthorityError("assessor-stage exactly-once accounting differs")
    formal = FormalAssessmentRecord(
        stage=stage_input.stage,
        assessment_jcs=assessment_blob.data,
        assessment=_deep_freeze(assessment),
        authority_jcs=authority_blob.data,
        authority=_deep_freeze(authority_document),
        end_to_end_cpu_nanoseconds=total_cpu,
        end_to_end_wall_nanoseconds=total_wall,
    )

    decision_jcs: bytes | None = None
    decision_document: Mapping[str, Any] | None = None
    if stage_input.stage == "development":
        if build_development_decision is None:
            raise AuthorityError("development output requires frozen decision builder")
        if decision_commit is None or decision_tree is None or decision_file is None:
            raise AuthorityError("development assessment requires one decision child")
        if repo.commit_parents(decision_commit) != (assessment_commit,):
            raise AuthorityError(
                "development decision is not a single child of assessment"
            )
        decision_snapshot = repo.snapshot(decision_commit, decision_tree)
        expected_decision_paths = {*expected_assessment_paths, decision_file.path}
        if (
            decision_file.path in expected_assessment_paths
            or set(decision_snapshot) != expected_decision_paths
        ):
            raise AuthorityError("development decision tree is not closed")
        for record in (assessment_file, authority_file):
            _verify_blob_record(
                decision_snapshot[record.path], record, "decision parent authority"
            )
        decision_blob = _blob_for(
            decision_snapshot, decision_file, "development decision record"
        )
        decision_jcs = decision_blob.data
        decision_document = _jcs_object(decision_jcs, "development decision record")
        decision_keys = {
            "schema_version",
            "experiment_id",
            "card_sha256",
            "development_gate_passed",
            "selected_variant",
            "selected_path",
            "safety16_disagreement_count",
            "candidate_input_sha256",
            "development_assessment_sha256",
            "decision_commit",
        }
        _exact_keys(decision_document, decision_keys, "development decision record")
        if (
            decision_document["schema_version"]
            != "geotarget.exp-local-003.development-decision-record/v1"
            or decision_document["experiment_id"] != EXPERIMENT_ID
            or decision_document["card_sha256"] != CARD_SHA256
            or decision_document["candidate_input_sha256"]
            != stage_input.candidate_input_sha256
            or decision_document["development_assessment_sha256"]
            != assessment_file.sha256
            or decision_document["decision_commit"] != assessment_commit
        ):
            raise AuthorityError("development decision cross-binding differs")
        expected_decision = build_development_decision(
            assessment,
            _mapping(
                strict_jcs_bytes(
                    candidate_run.raw_output_jcs, context="verified candidate raw"
                ),
                "verified candidate raw",
            ),
            _mapping(
                strict_jcs_bytes(
                    stage_input.assessor_truth_jcs,
                    context="verified assessor truth",
                ),
                "verified assessor truth",
            ),
            stage_input.bootstrap_indices,
            _mapping(
                strict_jcs_bytes(
                    candidate_run.candidate_execution_lock_jcs,
                    context="verified execution lock",
                ),
                "verified execution lock",
            ),
            assessment_commit,
        )
        if canonical_bytes(expected_decision) != decision_jcs:
            raise AuthorityError(
                "development decision differs from frozen recomputation"
            )
    elif any(
        item is not None for item in (decision_commit, decision_tree, decision_file)
    ):
        raise AuthorityError("locked assessment must not carry a development decision")
    elif build_development_decision is not None:
        raise AuthorityError(
            "locked output must not receive a development decision builder"
        )

    return ResolvedAssessmentOutput(
        formal=formal,
        assessment_commit=assessment_commit,
        assessment_tree=assessment_tree,
        assessment_file=assessment_file,
        authority_file=authority_file,
        decision_commit=decision_commit,
        decision_tree=decision_tree,
        decision_file=decision_file,
        decision_jcs=decision_jcs,
        decision=(
            None if decision_document is None else _deep_freeze(decision_document)
        ),
    )


resolve_stage_authority = resolve_stage_input_authority


def resolve_development_authorization(
    main_repository: Path,
    assessor_input_vault: Path,
    candidate_evidence_repository: Path,
    assessor_output_repository: Path,
    *,
    authorization_anchor_commit: str,
    assess: Callable[[Any, Any, bytes, Any], Any],
    build_development_decision: Callable[..., Any],
    git_executable: GitExecutable,
) -> DevelopmentAuthorization:
    """Compose the immutable C1 -> C2 -> C3 development authority chain."""

    roots = tuple(
        path.absolute()
        for path in (
            main_repository,
            assessor_input_vault,
            candidate_evidence_repository,
            assessor_output_repository,
        )
    )
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            try:
                if os.path.samefile(left, right):
                    raise AuthorityError(
                        "main/input/candidate-evidence/assessor-output repositories "
                        "must be physically separate"
                    )
            except FileNotFoundError as error:
                raise AuthorityError(
                    f"development authority repository missing: {error}"
                ) from error
            try:
                common = Path(os.path.commonpath((left, right)))
            except ValueError:
                continue
            if common == left or common == right:
                raise AuthorityError(
                    "authority repositories may not contain one another"
                )
    object_databases = [
        GitObjectRepository(path, git_executable).object_database for path in roots
    ]
    for index, left in enumerate(object_databases):
        for right in object_databases[index + 1 :]:
            if os.path.samefile(left, right):
                raise AuthorityError(
                    "authority repositories share a Git object database"
                )
    repositories = tuple(GitObjectRepository(path, git_executable) for path in roots)
    for index, left in enumerate(repositories):
        for right in repositories[index + 1 :]:
            if os.path.samefile(left.object_database_path, right.object_database_path):
                raise AuthorityError(
                    "authority repositories share a Git object database"
                )
    main = repositories[0]
    authorization_tree = main.commit_tree(authorization_anchor_commit)
    authorization_path = (
        "research/experiments/EXP-LOCAL-003/C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
    )
    authorization_blob = main.blob_at(authorization_anchor_commit, authorization_path)
    authorization_file = FileRecord(
        path=authorization_path,
        sha256=_sha256(authorization_blob.data),
        byte_length=len(authorization_blob.data),
    )
    anchor = _jcs_object(authorization_blob.data, "development authorization anchor")
    anchor_keys = {
        "schema_version",
        "experiment_id",
        "card_sha256",
        "stage",
        "stage_input_anchor",
        "c2_source_commit",
        "candidate_evidence",
        "assessor_output",
        "rerun_permitted",
    }
    _exact_keys(anchor, anchor_keys, "development authorization anchor")
    if (
        anchor["schema_version"] != DEVELOPMENT_AUTHORIZATION_SCHEMA
        or anchor["experiment_id"] != EXPERIMENT_ID
        or anchor["card_sha256"] != CARD_SHA256
        or anchor["stage"] != "development"
        or anchor["rerun_permitted"] is not False
    ):
        raise AuthorityError("development authorization anchor identity differs")
    c2_commit = _hex(anchor["c2_source_commit"], _GIT_OID, "C2 source commit")
    if main.commit_parents(authorization_anchor_commit) != (c2_commit,):
        raise AuthorityError(
            "authorization anchor is not the single child of C2 source"
        )
    c2_index = dict(main.tree_index(c2_commit))
    if authorization_path in c2_index:
        raise AuthorityError("development authorization anchor predates C3")
    expected_authorization_index = {
        **c2_index,
        authorization_path: ("100644", authorization_blob.oid),
    }
    if (
        dict(main.tree_index(authorization_anchor_commit))
        != expected_authorization_index
    ):
        raise AuthorityError("C3 authorization commit changes more than its anchor")

    input_commit, input_tree, input_file = _external_file_ref(
        anchor["stage_input_anchor"], "authorization.stage_input_anchor"
    )

    _verify_c2_introduction(
        main,
        stage_input_commit=input_commit,
        c2_source_commit=c2_commit,
    )
    input_index = dict(main.tree_index(input_commit))
    c2_index = dict(main.tree_index(c2_commit))
    for path, identity in input_index.items():
        if c2_index.get(path) != identity:
            raise AuthorityError(f"C2 modifies or removes frozen C1 path: {path}")
    candidate_publication_root = (
        main_repository
        / "research"
        / "experiments"
        / "EXP-LOCAL-003"
        / "development-candidate-inputs"
    )
    stage_input = resolve_stage_input_authority(
        anchor_repository=main_repository,
        anchor_commit=input_commit,
        anchor_path=input_file.path,
        anchor_sha256=input_file.sha256,
        candidate_publication_root=candidate_publication_root,
        assessor_vault_repository=assessor_input_vault,
        git_executable=git_executable,
    )
    if stage_input.anchor_tree != input_tree or stage_input.anchor_file != input_file:
        raise AuthorityError("C3 anchor stage-input reference differs")
    if stage_input.stage != "development":
        raise AuthorityError(
            "development authorization references non-development inputs"
        )

    candidate_ref = _mapping(anchor["candidate_evidence"], "candidate evidence")
    _exact_keys(candidate_ref, {"commit", "tree", "authority"}, "candidate evidence")
    candidate_commit = _hex(candidate_ref["commit"], _GIT_OID, "candidate commit")
    candidate_tree = _hex(candidate_ref["tree"], _GIT_OID, "candidate tree")
    candidate_file = _file_record(candidate_ref["authority"], "candidate authority")
    candidate_run = resolve_candidate_run_authority(
        candidate_evidence_repository,
        git_executable=git_executable,
        commit=candidate_commit,
        tree=candidate_tree,
        authority_file=candidate_file,
        expected_stage="development",
        stage_input=stage_input,
        execution_lock_repository=main_repository,
    )
    if candidate_run.candidate_execution_lock_commit != c2_commit:
        raise AuthorityError("candidate run execution lock is not the C2 source commit")
    _verify_c2_equivalence_evidence(
        main,
        c2_source_commit=c2_commit,
        stage_input=stage_input,
        candidate_run=candidate_run,
    )

    output_ref = _mapping(anchor["assessor_output"], "assessor output")
    output_keys = {
        "assessment_commit",
        "assessment_tree",
        "assessment_file",
        "authority_file",
        "decision_commit",
        "decision_tree",
        "decision_file",
    }
    _exact_keys(output_ref, output_keys, "assessor output")
    assessment_output = resolve_assessor_stage_output(
        assessor_output_repository,
        assess=assess,
        build_development_decision=build_development_decision,
        assessment_commit=_hex(
            output_ref["assessment_commit"], _GIT_OID, "assessment commit"
        ),
        assessment_tree=_hex(
            output_ref["assessment_tree"], _GIT_OID, "assessment tree"
        ),
        assessment_file=_file_record(output_ref["assessment_file"], "assessment file"),
        authority_file=_file_record(output_ref["authority_file"], "authority file"),
        stage_input=stage_input,
        candidate_run=candidate_run,
        git_executable=git_executable,
        decision_commit=_hex(
            output_ref["decision_commit"], _GIT_OID, "decision commit"
        ),
        decision_tree=_hex(output_ref["decision_tree"], _GIT_OID, "decision tree"),
        decision_file=_file_record(output_ref["decision_file"], "decision file"),
    )
    return DevelopmentAuthorization(
        authorization_anchor_commit=authorization_anchor_commit,
        authorization_anchor_tree=authorization_tree,
        authorization_anchor_file=authorization_file,
        authorization_anchor=_deep_freeze(anchor),
        stage_input=stage_input,
        candidate_run=candidate_run,
        assessor_output=assessment_output,
    )


def _verify_single_blob_child(
    repository: GitObjectRepository,
    *,
    parent_commit: str,
    child_commit: str,
    added_path: str,
    added_blob: _Blob,
    context: str,
) -> str:
    if repository.commit_parents(child_commit) != (parent_commit,):
        raise AuthorityError(f"{context} is not the required single child")
    parent_index = dict(repository.tree_index(parent_commit))
    if added_path in parent_index:
        raise AuthorityError(f"{context} addition already exists in its parent")
    expected = {**parent_index, added_path: ("100644", added_blob.oid)}
    child_index = dict(repository.tree_index(child_commit))
    if child_index != expected:
        raise AuthorityError(f"{context} changes more than its one frozen blob")
    return repository.commit_tree(child_commit)


def resolve_locked_authorization(
    main_repository: Path,
    development_assessor_input_vault: Path,
    development_candidate_evidence_repository: Path,
    development_assessor_output_repository: Path,
    locked_assessor_input_vault: Path,
    locked_candidate_evidence_repository: Path,
    locked_assessor_output_repository: Path,
    *,
    authorization_anchor_commit: str,
    assess: Callable[[Any, Any, bytes, Any], Any],
    build_development_decision: Callable[..., Any],
    finalize_product_connection: Callable[..., Any],
    git_executable: GitExecutable,
) -> LockedAuthorization:
    """Compose and replay the immutable development + C4/C5/C6 chain."""

    roots = tuple(
        path.absolute()
        for path in (
            main_repository,
            development_assessor_input_vault,
            development_candidate_evidence_repository,
            development_assessor_output_repository,
            locked_assessor_input_vault,
            locked_candidate_evidence_repository,
            locked_assessor_output_repository,
        )
    )
    repositories = tuple(GitObjectRepository(path, git_executable) for path in roots)
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if os.path.samefile(left, right):
                raise AuthorityError("locked authority repositories are not separate")
            try:
                common = Path(os.path.commonpath((left, right)))
            except ValueError:
                continue
            if common == left or common == right:
                raise AuthorityError(
                    "locked authority repositories contain one another"
                )
    for index, left in enumerate(repositories):
        for right in repositories[index + 1 :]:
            if os.path.samefile(left.object_database, right.object_database):
                raise AuthorityError(
                    "locked authority repositories share object storage"
                )

    main = repositories[0]
    c6_path = "research/experiments/EXP-LOCAL-003/C6_FINAL_CONNECTION_ANCHOR.json"
    c6_blob = main.blob_at(authorization_anchor_commit, c6_path)
    c6_file = FileRecord(
        path=c6_path,
        sha256=_sha256(c6_blob.data),
        byte_length=len(c6_blob.data),
    )
    anchor = _jcs_object(c6_blob.data, "locked authorization anchor")
    anchor_keys = {
        "schema_version",
        "experiment_id",
        "card_sha256",
        "stage",
        "development_authorization",
        "locked_stage_input",
        "locked_execution_lock",
        "candidate_evidence",
        "assessor_output",
        "rerun_permitted",
    }
    _exact_keys(anchor, anchor_keys, "locked authorization anchor")
    if (
        anchor["schema_version"] != LOCKED_AUTHORIZATION_SCHEMA
        or anchor["experiment_id"] != EXPERIMENT_ID
        or anchor["card_sha256"] != CARD_SHA256
        or anchor["stage"] != "locked"
        or anchor["rerun_permitted"] is not False
    ):
        raise AuthorityError("locked authorization anchor identity differs")

    development_commit, development_tree, development_file = _external_file_ref(
        anchor["development_authorization"],
        "locked authorization.development_authorization",
    )
    expected_development_path = (
        "research/experiments/EXP-LOCAL-003/C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
    )
    if development_file.path != expected_development_path:
        raise AuthorityError("locked authorization development path differs")
    development = resolve_development_authorization(
        main_repository,
        development_assessor_input_vault,
        development_candidate_evidence_repository,
        development_assessor_output_repository,
        authorization_anchor_commit=development_commit,
        assess=assess,
        build_development_decision=build_development_decision,
        git_executable=git_executable,
    )
    if (
        development.authorization_anchor_tree != development_tree
        or development.authorization_anchor_file != development_file
    ):
        raise AuthorityError("locked authorization development reference differs")

    c4_commit, c4_tree, c4_file = _external_file_ref(
        anchor["locked_stage_input"], "locked authorization.locked_stage_input"
    )
    expected_c4_path = (
        "research/experiments/EXP-LOCAL-003/C4_LOCKED_STAGE_VAULT_ANCHOR.json"
    )
    if c4_file.path != expected_c4_path:
        raise AuthorityError("locked stage-input path differs")
    locked_candidate_root = (
        main_repository
        / "research"
        / "experiments"
        / "EXP-LOCAL-003"
        / "locked-candidate-inputs"
    )
    stage_input = resolve_stage_input_authority(
        anchor_repository=main_repository,
        anchor_commit=c4_commit,
        anchor_path=c4_file.path,
        anchor_sha256=c4_file.sha256,
        candidate_publication_root=locked_candidate_root,
        assessor_vault_repository=locked_assessor_input_vault,
        git_executable=git_executable,
    )
    if (
        stage_input.anchor_tree != c4_tree
        or stage_input.anchor_file != c4_file
        or stage_input.stage != "locked"
    ):
        raise AuthorityError("locked stage-input reference differs")

    development_decision = development.assessor_output.decision
    development_decision_file = development.assessor_output.decision_file
    development_decision_commit = development.assessor_output.decision_commit
    if (
        development_decision is None
        or development_decision_file is None
        or development_decision_commit is None
    ):
        raise AuthorityError("development authorization has no closed decision")
    expected_development_authority = {
        "development_authorization_anchor_commit": (
            development.authorization_anchor_commit
        ),
        "development_authorization_anchor_sha256": (
            development.authorization_anchor_file.sha256
        ),
        "development_stage_input_anchor_sha256": (
            development.stage_input.anchor_file.sha256
        ),
        "development_candidate_run_authority_sha256": (
            development.candidate_run.authority_file.sha256
        ),
        "development_assessor_stage_authority_sha256": (
            development.assessor_output.authority_file.sha256
        ),
        "development_assessment_commit": (
            development.assessor_output.assessment_commit
        ),
        "development_assessment_sha256": (
            development.assessor_output.assessment_file.sha256
        ),
        "development_decision_commit": development_decision_commit,
        "development_decision_record_sha256": development_decision_file.sha256,
        "selected_variant": development_decision["selected_variant"],
        "selected_path": development_decision["selected_path"],
    }
    if dict(stage_input.development_authority or {}) != expected_development_authority:
        raise AuthorityError("C4 development authority differs from recomputation")

    c5_commit, c5_tree, c5_lock_file = _external_file_ref(
        anchor["locked_execution_lock"],
        "locked authorization.locked_execution_lock",
    )
    if c5_lock_file.path != LOCKED_EXECUTION_LOCK_PATH:
        raise AuthorityError("C5 locked execution-lock path differs")
    c5_lock_blob = main.blob_at(c5_commit, c5_lock_file.path)
    _verify_blob_record(c5_lock_blob, c5_lock_file, "C5 locked execution lock")
    observed_c5_tree = _verify_single_blob_child(
        main,
        parent_commit=c4_commit,
        child_commit=c5_commit,
        added_path=LOCKED_EXECUTION_LOCK_PATH,
        added_blob=c5_lock_blob,
        context="C5 locked execution-lock commit",
    )
    if observed_c5_tree != c5_tree:
        raise AuthorityError("C5 locked execution-lock tree differs")

    c6_tree = _verify_single_blob_child(
        main,
        parent_commit=c5_commit,
        child_commit=authorization_anchor_commit,
        added_path=c6_path,
        added_blob=c6_blob,
        context="C6 locked authorization commit",
    )

    candidate_ref = _mapping(anchor["candidate_evidence"], "locked candidate evidence")
    _exact_keys(
        candidate_ref,
        {"commit", "tree", "authority"},
        "locked candidate evidence",
    )
    candidate_run = resolve_candidate_run_authority(
        locked_candidate_evidence_repository,
        git_executable=git_executable,
        commit=_hex(candidate_ref["commit"], _GIT_OID, "locked candidate commit"),
        tree=_hex(candidate_ref["tree"], _GIT_OID, "locked candidate tree"),
        authority_file=_file_record(
            candidate_ref["authority"], "locked candidate authority"
        ),
        expected_stage="locked",
        stage_input=stage_input,
        execution_lock_repository=main_repository,
    )
    if (
        candidate_run.candidate_execution_lock_commit != c5_commit
        or candidate_run.candidate_execution_lock_tree != c5_tree
        or candidate_run.candidate_execution_lock_file != c5_lock_file
    ):
        raise AuthorityError("locked candidate does not bind the exact C5 lock")

    output_ref = _mapping(anchor["assessor_output"], "locked assessor output")
    output_keys = {
        "assessment_commit",
        "assessment_tree",
        "assessment_file",
        "authority_file",
        "final_connection_commit",
        "final_connection_tree",
        "final_connection_file",
    }
    _exact_keys(output_ref, output_keys, "locked assessor output")
    assessment_commit = _hex(
        output_ref["assessment_commit"], _GIT_OID, "locked assessment commit"
    )
    assessment_tree = _hex(
        output_ref["assessment_tree"], _GIT_OID, "locked assessment tree"
    )
    assessment_file = _file_record(
        output_ref["assessment_file"], "locked assessment file"
    )
    authority_file = _file_record(
        output_ref["authority_file"], "locked assessor authority file"
    )
    assessor_output = resolve_assessor_stage_output(
        locked_assessor_output_repository,
        assess=assess,
        build_development_decision=None,
        assessment_commit=assessment_commit,
        assessment_tree=assessment_tree,
        assessment_file=assessment_file,
        authority_file=authority_file,
        stage_input=stage_input,
        candidate_run=candidate_run,
        git_executable=git_executable,
    )

    final_commit = _hex(
        output_ref["final_connection_commit"],
        _GIT_OID,
        "final connection commit",
    )
    final_tree = _hex(
        output_ref["final_connection_tree"], _GIT_OID, "final connection tree"
    )
    final_file = _file_record(
        output_ref["final_connection_file"], "final connection file"
    )
    if final_file.path != "final-connection.json":
        raise AuthorityError("final-connection file path differs")
    locked_output_repo = repositories[6]
    final_blob = locked_output_repo.blob_at(final_commit, final_file.path)
    _verify_blob_record(final_blob, final_file, "final connection")
    observed_final_tree = _verify_single_blob_child(
        locked_output_repo,
        parent_commit=assessment_commit,
        child_commit=final_commit,
        added_path=final_file.path,
        added_blob=final_blob,
        context="final-connection commit",
    )
    if observed_final_tree != final_tree:
        raise AuthorityError("final-connection tree differs")
    final_document = _jcs_object(final_blob.data, "final connection")
    final_keys = {
        "schema_version",
        "experiment_id",
        "card_sha256",
        "development_assessment_sha256",
        "development_decision_record_sha256",
        "locked_assessment_sha256",
        "selected_variant",
        "selected_path",
        "development_safety16_clear",
        "locked_stage_passed",
        "product_connection_allowed",
    }
    _exact_keys(final_document, final_keys, "final connection")
    if (
        final_document["schema_version"]
        != "geotarget.exp-local-003.final-connection/v1"
        or final_document["experiment_id"] != EXPERIMENT_ID
        or final_document["card_sha256"] != CARD_SHA256
        or final_document["development_assessment_sha256"]
        != development.assessor_output.assessment_file.sha256
        or final_document["development_decision_record_sha256"]
        != development_decision_file.sha256
        or final_document["locked_assessment_sha256"] != assessment_file.sha256
        or final_document["selected_variant"]
        != development_decision["selected_variant"]
        or final_document["selected_path"] != development_decision["selected_path"]
        or not isinstance(final_document["development_safety16_clear"], bool)
        or not isinstance(final_document["locked_stage_passed"], bool)
        or not isinstance(final_document["product_connection_allowed"], bool)
    ):
        raise AuthorityError("final connection fields differ from the closed chain")

    def fresh(payload: bytes, context: str) -> Mapping[str, Any]:
        return _mapping(strict_jcs_bytes(payload, context=context), context)

    expected_final = finalize_product_connection(
        fresh(
            development.assessor_output.formal.assessment_jcs,
            "development assessment",
        ),
        fresh(assessor_output.formal.assessment_jcs, "locked assessment"),
        fresh(development.assessor_output.decision_jcs or b"", "development decision"),
        development_raw_document=fresh(
            development.candidate_run.raw_output_jcs, "development raw"
        ),
        development_assessor_truth=fresh(
            development.stage_input.assessor_truth_jcs, "development truth"
        ),
        development_bootstrap_bytes=development.stage_input.bootstrap_indices,
        development_execution_lock=fresh(
            development.candidate_run.candidate_execution_lock_jcs,
            "development execution lock",
        ),
        locked_raw_document=fresh(candidate_run.raw_output_jcs, "locked raw"),
        locked_assessor_truth=fresh(stage_input.assessor_truth_jcs, "locked truth"),
        locked_bootstrap_bytes=stage_input.bootstrap_indices,
        locked_execution_lock=fresh(
            candidate_run.candidate_execution_lock_jcs, "locked execution lock"
        ),
    )
    if canonical_bytes(expected_final) != final_blob.data:
        raise AuthorityError("final connection differs from frozen recomputation")

    return LockedAuthorization(
        authorization_anchor_commit=authorization_anchor_commit,
        authorization_anchor_tree=c6_tree,
        authorization_anchor_file=c6_file,
        authorization_anchor=_deep_freeze(anchor),
        development=development,
        stage_input=stage_input,
        candidate_run=candidate_run,
        assessor_output=assessor_output,
        final_connection_commit=final_commit,
        final_connection_tree=final_tree,
        final_connection_file=final_file,
        final_connection_jcs=final_blob.data,
        final_connection=_deep_freeze(final_document),
        product_connection_allowed=final_document["product_connection_allowed"],
    )


__all__ = [
    "ANCHOR_SCHEMA",
    "ASSESSOR_AUTHORITY_SCHEMA",
    "ATTEMPT_SCHEMA",
    "AuthorityError",
    "CANDIDATE_AUTHORITY_SCHEMA",
    "CandidateRunRecord",
    "DEVELOPMENT_AUTHORIZATION_SCHEMA",
    "DevelopmentAuthorization",
    "EXIT_SCHEMA",
    "FileRecord",
    "FINAL_CONNECTION_ANCHOR_SCHEMA",
    "FormalAssessmentRecord",
    "GitExecutable",
    "GitObjectRepository",
    "LOCKED_AUTHORIZATION_SCHEMA",
    "LOCKED_EXECUTION_LOCK_PATH",
    "LockedAuthorization",
    "MANIFEST_SCHEMA",
    "ManifestEntry",
    "PREEXIT_SCHEMA",
    "ResolvedAssessmentOutput",
    "StageInputRecord",
    "assess_with_authority",
    "decode_deterministic_gzip",
    "deterministic_gzip",
    "pin_git_executable",
    "resolve_candidate_run_authority",
    "resolve_development_authorization",
    "resolve_locked_authorization",
    "resolve_assessor_stage_output",
    "resolve_stage_input_authority",
    "resolve_stage_authority",
    "strict_jcs_bytes",
]
