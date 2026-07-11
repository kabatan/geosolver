"""C0-owned observer for one isolated EXP-LOCAL-003 candidate process.

This module is imported only after :mod:`launch_candidate` has durably claimed
the fixed external marker.  It verifies the frozen environment, immutable main
topology, C0 source authority, stage anchor, execution lock, and candidate
publication without opening assessor or generator-private content.  It then
publishes an append-only external Git history while the future C2 Julia runner
runs directly in a no-capability Windows AppContainer.

The broker's pre-exit callback is the ordering boundary: raw bytes and the
pre-exit seal are committed before the observer releases the ACK.  Process
exit, empty Job, exact ACL restoration, profile deletion, and denied vault
probes are C0 observations, never candidate self-attestations.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Final, Literal, TypeAlias, cast


sys.dont_write_bytecode = True


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
EXPERIMENT_ROOT = SOURCE_ROOT.parent
EXPERIMENT_ID: Final = "EXP-LOCAL-003"
ASSESSMENT_EVIDENCE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-assessment-evidence")
    / EXPERIMENT_ID
)
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
for _root in (PYTHON_SOURCE, SOURCE_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

import authority  # noqa: E402
import freeze_execution_lock as execution_contract  # noqa: E402
import materialize_development as environment_contract  # noqa: E402
import sandbox_broker  # noqa: E402
from durable_io import (  # noqa: E402
    durable_rename_noreplace,
    exclusive_write,
)


Stage: TypeAlias = Literal["development", "locked"]
C0_OBSERVER_OWNS_CANDIDATE_PROCESS: Final = True
CARD_SHA256: Final = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"
OBSERVER_PATH: Final = "research/experiments/EXP-LOCAL-003/source/candidate_observer.py"
LAUNCHER_PATH: Final = "research/experiments/EXP-LOCAL-003/source/launch_candidate.py"
BROKER_PATH: Final = "research/experiments/EXP-LOCAL-003/source/sandbox_broker.py"
RUNNER_PATH: Final = "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl"
TRANSFORM_PATH: Final = "julia/GeoTargetCore/src/local_model_transform.jl"
CANDIDATE_RUNTIME_SOURCE_PATHS: Final = (TRANSFORM_PATH, RUNNER_PATH)
CANDIDATE_TEST_SOURCE_PATHS: Final = (
    "julia/GeoTargetCore/test/test_local_model_transform.jl",
)
PREIMPLEMENTATION_PATH: Final = (
    "research/experiments/EXP-LOCAL-003/preimplementation-lock.json"
)
ATTEMPT_PATH: Final = "attempt-claim.json"
RAW_PATH: Final = "candidate-output.json.gz"
SEAL_PATH: Final = "candidate-output-preexit-seal.json"
EXIT_PATH: Final = "candidate-process-exit.json"
MANIFEST_PATH: Final = "manifest.json"
AUTHORITY_PATH: Final = "candidate-run-authority.json"
EVIDENCE_PATHS: Final = frozenset(
    (ATTEMPT_PATH, RAW_PATH, SEAL_PATH, EXIT_PATH, MANIFEST_PATH, AUTHORITY_PATH)
)
ATTEMPT_SCHEMA: Final = "geotarget.exp-local-003.candidate-run-attempt/v2"
PREEXIT_SCHEMA: Final = "geotarget.exp-local-003.candidate-output-preexit-seal/v2"
EXIT_SCHEMA: Final = "geotarget.exp-local-003.candidate-process-exit/v2"
AUTHORITY_SCHEMA: Final = "geotarget.exp-local-003.candidate-run-authority/v2"
CANDIDATE_TIMEOUT_SECONDS: Final = 21_600
STDOUT_LIMIT_BYTES: Final = 256 * 1024 * 1024
STDERR_LIMIT_BYTES: Final = 1024 * 1024
MAX_PROCESSES: Final = 1
PREEXIT_CALLBACK_DEADLINE_GUARD_NS: Final = 5_000_000_000
_OID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class CandidateObservationError(RuntimeError):
    """The claimed candidate process cannot be observed safely."""


@dataclass(frozen=True, slots=True)
class RunContext:
    """All result-blind authority fixed before the child is created."""

    stage: Stage
    git_executable: authority.GitExecutable
    head_commit: str
    head_tree: str
    stage_input_anchor: Mapping[str, Any]
    execution_lock: Mapping[str, Any]
    candidate_input_sha256: str
    candidate_publication_tree_sha256: str
    observer_authority: Mapping[str, Any]
    launcher_authority: Mapping[str, Any]
    broker_authority: Mapping[str, Any]
    sandbox_request: sandbox_broker.SandboxRequest
    sandbox_request_document: Mapping[str, Any]
    source_records: tuple[Mapping[str, str], ...]
    artifact_records: tuple[Mapping[str, str], ...]
    immutable_files: tuple[tuple[Path, str], ...]
    environment_lock_sha256: str


@dataclass(frozen=True, slots=True)
class PublishedRun:
    """Closed external authority repository produced by one observation."""

    repository: Path
    commit: str
    tree: str
    authority_file: authority.FileRecord


@dataclass(frozen=True, slots=True)
class _CommitRef:
    commit: str
    tree: str


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return authority.canonical_bytes(value)
    except (TypeError, ValueError) as error:
        raise CandidateObservationError(
            f"authority is not JCS encodable: {error}"
        ) from error


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise CandidateObservationError(f"{context} must be an object")
    return cast(Mapping[str, Any], value)


def _record(path: str, payload: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": _sha256(payload), "byte_length": len(payload)}


def _record_from_blob(path: str, blob: Any) -> dict[str, Any]:
    if blob.mode != "100644":
        raise CandidateObservationError(f"authority blob is not regular: {path}")
    return _record(path, blob.data)


def _external(commit: str, tree: str, record: Mapping[str, Any]) -> dict[str, Any]:
    return {"commit": commit, "tree": tree, "file": dict(record)}


def _claim_document(claim: Any) -> dict[str, Any]:
    identity = claim.identity
    return {
        "file": _record(claim.path.name, claim.payload),
        "nonce_sha256": claim.nonce_sha256,
        "filesystem_identity": {
            "device_decimal": str(identity.device),
            "inode_decimal": str(identity.inode),
            "empty_claim_ctime_nanoseconds_decimal": str(
                identity.empty_claim_ctime_nanoseconds
            ),
            "link_count": identity.link_count,
        },
    }


def _verify_claim_binding(stage: Stage, paths: Any, claim: Any) -> None:
    if claim.path != paths.attempt_marker or claim.identity.link_count != 1:
        raise CandidateObservationError("candidate launch claim path/link differs")
    _regular_file(claim.path, "candidate launch marker")
    info = claim.path.lstat()
    payload = claim.path.read_bytes()
    try:
        document = _mapping(
            authority.strict_jcs_bytes(payload, context="candidate launch marker"),
            "candidate launch marker",
        )
    except Exception as error:
        raise CandidateObservationError(
            f"candidate launch marker is invalid: {error}"
        ) from error
    if (
        info.st_dev != claim.identity.device
        or info.st_ino != claim.identity.inode
        or info.st_nlink != 1
        or payload != claim.payload
        or _sha256(payload) != claim.sha256
        or set(document)
        != {
            "schema_version",
            "card_sha256",
            "stage",
            "nonce",
            "rerun_permitted",
            "failure_is_terminal",
        }
        or document.get("schema_version")
        != "geotarget.exp-local-003.candidate-launch-attempt/v2"
        or document.get("card_sha256") != CARD_SHA256
        or document.get("stage") != stage
        or document.get("nonce") != claim.nonce
        or re.fullmatch(r"[0-9a-f]{64}", claim.nonce) is None
        or document.get("rerun_permitted") is not False
        or document.get("failure_is_terminal") is not True
        or _sha256(bytes.fromhex(claim.nonce)) != claim.nonce_sha256
    ):
        raise CandidateObservationError("candidate launch marker binding differs")


def _verify_launcher_context(stage: Stage) -> None:
    expected = SOURCE_ROOT / "launch_candidate.py"
    try:
        script = Path(sys.argv[0]).resolve(strict=True)
        main_script = Path(sys.modules["__main__"].__file__).resolve(strict=True)
        cwd = Path.cwd().resolve(strict=True)
    except (AttributeError, KeyError, OSError, TypeError) as error:
        raise CandidateObservationError(
            "candidate launcher context cannot resolve"
        ) from error
    if (
        len(sys.argv) != 2
        or sys.argv[1] != stage
        or script != expected.resolve(strict=True)
        or main_script != expected.resolve(strict=True)
        or cwd != REPOSITORY_ROOT.resolve(strict=True)
        or sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.no_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.optimize != 0
    ):
        raise CandidateObservationError(
            "formal observer requires repository-root launch_candidate.py "
            "under python -I -B -S"
        )


def _git_environment() -> dict[str, str]:
    null = "NUL" if os.name == "nt" else "/dev/null"
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": null,
        "GIT_CONFIG_SYSTEM": null,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
    }
    if os.name == "nt":
        for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP"):
            value = os.environ.get(key)
            if value:
                environment[key] = value
    return environment


def _remaining_deadline_seconds(deadline_ns: int | None, *, phase: str) -> float | None:
    """Return a positive subprocess timeout or fail before starting work."""

    if deadline_ns is None:
        return None
    remaining_ns = deadline_ns - time.perf_counter_ns()
    if remaining_ns <= 0:
        raise CandidateObservationError(
            f"pre-exit observer deadline elapsed before {phase}"
        )
    return remaining_ns / 1_000_000_000


def _check_deadline(deadline_ns: int | None, *, phase: str) -> None:
    _remaining_deadline_seconds(deadline_ns, phase=phase)


def _run_git(
    executable: authority.GitExecutable,
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
    extra_environment: Mapping[str, str] | None = None,
    deadline_ns: int | None = None,
) -> bytes:
    environment = _git_environment()
    if extra_environment:
        environment.update(extra_environment)
    command = [
        str(executable.path),
        f"--git-dir={repository / '.git'}",
        f"--work-tree={repository}",
        "-c",
        "core.hooksPath=NUL" if os.name == "nt" else "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgSign=false",
        "-c",
        "core.attributesFile=",
        "-c",
        "core.fsync=loose-object,index,reference",
        *arguments,
    ]
    timeout = _remaining_deadline_seconds(
        deadline_ns,
        phase=f"pinned Git {' '.join(arguments)}",
    )
    try:
        completed = subprocess.run(
            command,
            input=input_bytes,
            check=False,
            capture_output=True,
            env=environment,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise CandidateObservationError(
            "pre-exit observer deadline elapsed while pinned Git was running: "
            + " ".join(arguments)
        ) from error
    except OSError as error:
        raise CandidateObservationError(
            f"pinned Git could not execute: {error}"
        ) from error
    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", "replace").strip()
        raise CandidateObservationError(
            f"pinned Git rejected {' '.join(arguments)}: {diagnostic}"
        )
    return completed.stdout


def _git_text(
    executable: authority.GitExecutable,
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
    extra_environment: Mapping[str, str] | None = None,
    deadline_ns: int | None = None,
) -> str:
    try:
        return (
            _run_git(
                executable,
                repository,
                *arguments,
                input_bytes=input_bytes,
                extra_environment=extra_environment,
                deadline_ns=deadline_ns,
            )
            .decode("ascii", "strict")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise CandidateObservationError(
            "pinned Git emitted non-ASCII identity"
        ) from error


class _EvidenceGit:
    """Raw-blob, additive, single-parent evidence history builder."""

    def __init__(self, root: Path, executable: authority.GitExecutable) -> None:
        self.root = root
        self.executable = executable
        self.parent: str | None = None
        self.ordinal = 0
        self.files: dict[str, bytes] = {}
        try:
            root.mkdir()
        except OSError as error:
            raise CandidateObservationError(
                f"cannot create evidence staging root: {error}"
            ) from error
        environment = _git_environment()
        try:
            completed = subprocess.run(
                [
                    str(executable.path),
                    "-c",
                    "init.templateDir=",
                    "init",
                    "--quiet",
                    "--initial-branch=main",
                    str(root),
                ],
                check=False,
                capture_output=True,
                env=environment,
            )
        except OSError as error:
            raise CandidateObservationError(
                f"cannot initialize evidence Git: {error}"
            ) from error
        if completed.returncode != 0:
            raise CandidateObservationError(
                "cannot initialize evidence Git: "
                + completed.stderr.decode("utf-8", "replace").strip()
            )
        dot_git = root / ".git"
        if not dot_git.is_dir() or (dot_git / "objects/info/alternates").exists():
            raise CandidateObservationError("evidence repository storage is not direct")
        _run_git(executable, root, "read-tree", "--empty")

    def append(
        self,
        message: str,
        additions: Mapping[str, bytes],
        *,
        deadline_ns: int | None = None,
    ) -> _CommitRef:
        _check_deadline(deadline_ns, phase=f"{message} append")
        if not additions or set(additions) & set(self.files):
            raise CandidateObservationError("evidence event is not a nonempty addition")
        for path, payload in additions.items():
            if path not in EVIDENCE_PATHS or Path(path).name != path or not payload:
                raise CandidateObservationError(
                    f"invalid evidence path/payload: {path}"
                )
            _check_deadline(deadline_ns, phase=f"durable write of {path}")
            exclusive_write(self.root / path, payload, mode=0o444)
            _check_deadline(deadline_ns, phase=f"durable write of {path}")
            object_id = _git_text(
                self.executable,
                self.root,
                "hash-object",
                "-w",
                "--stdin",
                input_bytes=payload,
                deadline_ns=deadline_ns,
            )
            if _OID.fullmatch(object_id) is None:
                raise CandidateObservationError("Git returned a malformed blob id")
            _run_git(
                self.executable,
                self.root,
                "update-index",
                "--add",
                "--cacheinfo",
                "100644",
                object_id,
                path,
                deadline_ns=deadline_ns,
            )
            self.files[path] = payload
        tree = _git_text(
            self.executable,
            self.root,
            "write-tree",
            deadline_ns=deadline_ns,
        )
        if _OID.fullmatch(tree) is None:
            raise CandidateObservationError("Git returned a malformed tree id")
        self.ordinal += 1
        arguments = ["commit-tree", tree]
        if self.parent is not None:
            arguments.extend(("-p", self.parent))
        arguments.extend(("-m", message))
        date = f"{1_700_000_000 + self.ordinal} +0000"
        commit = _git_text(
            self.executable,
            self.root,
            *arguments,
            extra_environment={
                "GIT_AUTHOR_NAME": "EXP-LOCAL-003 C0 observer",
                "GIT_AUTHOR_EMAIL": "c0-observer@geotarget.invalid",
                "GIT_COMMITTER_NAME": "EXP-LOCAL-003 C0 observer",
                "GIT_COMMITTER_EMAIL": "c0-observer@geotarget.invalid",
                "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_DATE": date,
            },
            deadline_ns=deadline_ns,
        )
        if _OID.fullmatch(commit) is None:
            raise CandidateObservationError("Git returned a malformed commit id")
        old = self.parent or ("0" * len(commit))
        _run_git(
            self.executable,
            self.root,
            "update-ref",
            "refs/heads/main",
            commit,
            old,
            deadline_ns=deadline_ns,
        )
        self.parent = commit
        observed_tree = _git_text(
            self.executable,
            self.root,
            "show",
            "-s",
            "--format=%T",
            commit,
            deadline_ns=deadline_ns,
        )
        if observed_tree != tree:
            raise CandidateObservationError("persisted evidence commit/tree differs")
        parent_fields = _git_text(
            self.executable,
            self.root,
            "rev-list",
            "--parents",
            "-n",
            "1",
            commit,
            deadline_ns=deadline_ns,
        ).split()
        if (
            not parent_fields
            or parent_fields[0] != commit
            or any(_OID.fullmatch(value) is None for value in parent_fields)
        ):
            raise CandidateObservationError("persisted evidence parent is malformed")
        parents = tuple(parent_fields[1:])
        expected_parents = () if old == "0" * len(commit) else (old,)
        if parents != expected_parents:
            raise CandidateObservationError("persisted evidence parent differs")
        _check_deadline(deadline_ns, phase=f"{message} append verification")
        return _CommitRef(commit, tree)

    def verify_closed(self) -> tuple[str, str]:
        if self.parent is None or set(self.files) != EVIDENCE_PATHS:
            raise CandidateObservationError(
                "evidence repository is not the closed six-file set"
            )
        status = _run_git(
            self.executable,
            self.root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        )
        if status:
            raise CandidateObservationError("evidence repository is not clean")
        repository = authority.GitObjectRepository(
            self.root.absolute(), self.executable
        )
        tree = repository.commit_tree(self.parent)
        if set(repository.tree_index(self.parent)) != EVIDENCE_PATHS:
            raise CandidateObservationError("evidence HEAD path set differs")
        return self.parent, tree


def _main_git_bytes(git: authority.GitExecutable, *arguments: str) -> bytes:
    try:
        return execution_contract._git_bytes(git, *arguments)
    except Exception as error:
        raise CandidateObservationError(
            f"main Git verification failed: {error}"
        ) from error


def _main_git_text(git: authority.GitExecutable, *arguments: str) -> str:
    try:
        return execution_contract._git_text(git, *arguments)
    except Exception as error:
        raise CandidateObservationError(
            f"main Git verification failed: {error}"
        ) from error


def _regular_file(path: Path, context: str) -> None:
    try:
        info = path.lstat()
    except OSError as error:
        raise CandidateObservationError(f"{context} is unavailable: {error}") from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or attributes & reparse
    ):
        raise CandidateObservationError(f"{context} is not a regular non-reparse file")


def _reject_reparse_ancestry(path: Path, context: str) -> None:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for entry in (path.absolute(), *path.absolute().parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise CandidateObservationError(
                f"cannot inspect {context}: {error}"
            ) from error
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & reparse:
            raise CandidateObservationError(
                f"{context} traverses a reparse point: {entry}"
            )


def _verify_fixed_paths(stage: Stage, paths: Any) -> None:
    if not paths.root.is_absolute() or not paths.scratch_root.is_absolute():
        raise CandidateObservationError(
            "candidate evidence/scratch namespace is not absolute"
        )
    name = f"{stage}-candidate-run"
    expected = {
        "evidence_repository": paths.root / name,
        "staging_repository": paths.root / f".{name}-staging.partial",
        "attempt_marker": paths.root / f"{name}.attempt",
        "scratch_directory": paths.scratch_root / f".{name}-scratch.partial",
    }
    if any(getattr(paths, field) != value for field, value in expected.items()):
        raise CandidateObservationError("candidate evidence layout is not fixed")
    _reject_reparse_ancestry(paths.root, "candidate evidence namespace")
    _reject_reparse_ancestry(paths.scratch_root, "candidate scratch namespace")
    if not paths.root.is_dir():
        raise CandidateObservationError("candidate evidence namespace is unavailable")
    if not paths.scratch_root.is_dir():
        raise CandidateObservationError("candidate scratch namespace is unavailable")
    if (
        paths.scratch_root == paths.root
        or paths.scratch_root in paths.root.parents
        or paths.root in paths.scratch_root.parents
    ):
        raise CandidateObservationError("candidate evidence/scratch namespaces overlap")


def _closed_regular_tree(root: Path, context: str) -> set[str]:
    """Enumerate a tree without following links/reparse points or special files."""

    found: set[str] = set()
    pending = [root]
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    while pending:
        directory = pending.pop()
        try:
            entries = tuple(directory.iterdir())
        except OSError as error:
            raise CandidateObservationError(
                f"cannot enumerate {context}: {error}"
            ) from error
        for entry in entries:
            try:
                info = entry.lstat()
            except OSError as error:
                raise CandidateObservationError(
                    f"cannot inspect {context}: {error}"
                ) from error
            attributes = getattr(info, "st_file_attributes", 0)
            if stat.S_ISLNK(info.st_mode) or attributes & reparse:
                raise CandidateObservationError(
                    f"{context} contains a reparse point: {entry}"
                )
            if stat.S_ISDIR(info.st_mode):
                pending.append(entry)
            elif stat.S_ISREG(info.st_mode):
                found.add(entry.relative_to(root).as_posix())
            else:
                raise CandidateObservationError(
                    f"{context} contains a special file: {entry}"
                )
    return found


def _validate_main_state(
    git: authority.GitExecutable, expected_head: str | None = None
) -> str:
    try:
        top = Path(_main_git_text(git, "rev-parse", "--show-toplevel")).resolve()
    except OSError as error:
        raise CandidateObservationError(
            f"main repository path cannot resolve: {error}"
        ) from error
    if top != REPOSITORY_ROOT.resolve():
        raise CandidateObservationError(
            "candidate observer is not in the main repository"
        )
    if _main_git_text(git, "branch", "--show-current") != "main":
        raise CandidateObservationError("formal candidate must run on branch main")
    if _main_git_text(git, "for-each-ref", "--format=%(refname)", "refs/replace"):
        raise CandidateObservationError("Git replacement refs are forbidden")
    head = _main_git_text(git, "rev-parse", "HEAD")
    if expected_head is not None and head != expected_head:
        raise CandidateObservationError(
            "main HEAD changed during candidate observation"
        )
    if _main_git_bytes(git, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise CandidateObservationError(
            "formal candidate requires a clean main worktree"
        )
    return head


def _source_authority(
    repository: authority.GitObjectRepository,
    anchor: Mapping[str, Any],
    relative: str,
) -> tuple[dict[str, Any], str]:
    source_commit = anchor.get("source_lock_commit")
    if not isinstance(source_commit, str):
        raise CandidateObservationError("stage anchor source commit is malformed")
    pre_blob = repository.blob_at(source_commit, PREIMPLEMENTATION_PATH)
    pre = _mapping(
        authority.strict_jcs_bytes(pre_blob.data, context="preimplementation lock"),
        "preimplementation lock",
    )
    c0_commit = pre.get("c0_source_commit")
    c0_tree = pre.get("c0_source_tree")
    files = pre.get("files")
    if (
        anchor.get("preimplementation_lock_sha256") != _sha256(pre_blob.data)
        or pre.get("schema_version") != "exp-local-003-preimplementation-lock/v1"
        or pre.get("experiment_id") != EXPERIMENT_ID
        or pre.get("card_sha256") != CARD_SHA256
        or not isinstance(c0_commit, str)
        or not isinstance(c0_tree, str)
        or not isinstance(files, Mapping)
        or files.get(relative) is None
        or repository.commit_tree(c0_commit) != c0_tree
    ):
        raise CandidateObservationError("C0 source authority is malformed")
    if repository.commit_parents(source_commit) != (c0_commit,):
        raise CandidateObservationError("source lock is not the C0 source child")
    c0_index = dict(repository.tree_index(c0_commit))
    if PREIMPLEMENTATION_PATH in c0_index:
        raise CandidateObservationError("preimplementation lock existed in C0 source")
    if dict(repository.tree_index(source_commit)) != {
        **c0_index,
        PREIMPLEMENTATION_PATH: ("100644", pre_blob.oid),
    }:
        raise CandidateObservationError("source-lock commit changes more than its lock")
    blob = repository.blob_at(c0_commit, relative)
    record = _record_from_blob(relative, blob)
    if record["sha256"] != files[relative]:
        raise CandidateObservationError(f"C0 source digest differs: {relative}")
    live = REPOSITORY_ROOT.joinpath(*relative.split("/"))
    _regular_file(live, f"live C0 source {relative}")
    if _sha256(live.read_bytes()) != record["sha256"]:
        raise CandidateObservationError(f"live C0 source differs: {relative}")
    return _external(c0_commit, c0_tree, record), record["sha256"]


def _collapse_recursive_roots(paths: Sequence[Path]) -> tuple[Path, ...]:
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


def _sandbox_request_document(request: sandbox_broker.SandboxRequest) -> dict[str, Any]:
    environment = [{"name": key, "value": value} for key, value in request.environment]
    grants = [
        {"path": str(grant.path), "recursive": grant.recursive}
        for grant in request.allowed_read
    ]
    probes = [
        {"path": str(probe.path), "expected": probe.expected.value}
        for probe in request.access_probes
    ]
    return {
        "backend": "windows-classic-appcontainer",
        "claim_reference": request.claim_reference,
        "command": list(request.command),
        "command_sha256": _sha256(_canonical(list(request.command))),
        "working_directory": str(request.scratch_directory),
        "environment": environment,
        "environment_sha256": _sha256(_canonical(environment)),
        "allowed_read": grants,
        "allowed_read_manifest_sha256": _sha256(_canonical(grants)),
        "expected_read_identity_manifest_sha256": (
            request.expected_read_identity_manifest_sha256
        ),
        "access_probes": probes,
        "access_probe_manifest_sha256": _sha256(_canonical(probes)),
        "capabilities": [],
        "network_capabilities": [],
        "timeout_seconds": request.timeout_seconds,
        "stdout_limit_bytes": request.stdout_limit_bytes,
        "stderr_limit_bytes": request.stderr_limit_bytes,
        "preexit_payload_limit_bytes": request.preexit_payload_limit_bytes,
        "job": {
            "assigned_at_creation": True,
            "breakaway_allowed": False,
            "child_process_policy": "restricted-no-descendants",
            "kill_on_close": True,
            "max_processes": request.max_processes,
        },
    }


def _build_runtime_request(
    stage: Stage,
    paths: Any,
    claim: Any,
    environment_lock: Mapping[str, Any],
    lock_document: Mapping[str, Any],
    candidate_root: Path,
    artifact_records: Sequence[Mapping[str, str]],
) -> sandbox_broker.SandboxRequest:
    julia = _mapping(environment_lock.get("julia"), "environment Julia")
    julia_executable_value = julia.get("runtime_executable")
    runtime_tree = _mapping(julia.get("runtime_tree"), "Julia runtime tree")
    depot_tree = _mapping(julia.get("depot_tree"), "Julia depot tree")
    runtime_root_value = runtime_tree.get("root")
    depot_root_value = depot_tree.get("root")
    if not all(
        isinstance(value, str)
        for value in (julia_executable_value, runtime_root_value, depot_root_value)
    ):
        raise CandidateObservationError("pinned Julia runtime/depot is malformed")
    julia_executable = Path(julia_executable_value)
    julia_runtime_root = Path(cast(str, runtime_root_value))
    julia_depot_root = Path(cast(str, depot_root_value))
    _regular_file(julia_executable, "pinned Julia executable")
    if julia_runtime_root not in julia_executable.parents:
        raise CandidateObservationError(
            "pinned Julia executable is outside its runtime"
        )

    candidate_runner = REPOSITORY_ROOT.joinpath(*RUNNER_PATH.split("/"))
    project_root = REPOSITORY_ROOT / "julia"
    project_files = (project_root / "Project.toml", project_root / "Manifest.toml")
    package_roots = tuple(
        project_root / name
        for name in ("GeoTargetBase", "GeoTargetCore", "GeoTargetGeometry")
    )
    package_projects = tuple(root / "Project.toml" for root in package_roots)
    package_sources = tuple(root / "src" for root in package_roots)
    for file_path, context in (
        (candidate_runner, "C2 candidate runner"),
        *((path, "root Julia project authority") for path in project_files),
        *((path, "GeoTarget package project authority") for path in package_projects),
    ):
        _regular_file(file_path, context)
    if any(not path.is_dir() for path in package_sources):
        raise CandidateObservationError("GeoTarget runtime source tree is unavailable")

    recursive_roots = _collapse_recursive_roots(
        (
            julia_runtime_root,
            candidate_root,
            *package_sources,
        )
    )
    grants = [
        sandbox_broker.ReadGrant(root, recursive=True) for root in recursive_roots
    ]
    # The pinned runner needs installed package and artifact payloads, not
    # mutable depot state such as compiled caches, logs, or formal temp files.
    grants.append(sandbox_broker.ReadGrant(julia_depot_root, recursive=False))
    for name in ("packages", "artifacts"):
        child = julia_depot_root / name
        if child.exists():
            grants.append(sandbox_broker.ReadGrant(child, recursive=True))
    discovery_paths = (
        REPOSITORY_ROOT,
        project_root,
        candidate_runner,
        *project_files,
        *package_projects,
    )
    for discovery_path in discovery_paths:
        if not any(
            discovery_path == root or root in discovery_path.parents
            for root in recursive_roots
        ):
            grants.append(sandbox_broker.ReadGrant(discovery_path, recursive=False))

    vault_root = (
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-vault")
        / EXPERIMENT_ID
        / f"{stage}-assessor-vault"
    )
    private_root = (
        REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-private-audit")
        / EXPERIMENT_ID
        / f"{stage}-generator-private-vault"
    )
    assessor_probe = vault_root / "manifest.json"
    private_probe = private_root / "manifest.json"
    main_probe = REPOSITORY_ROOT.joinpath(*OBSERVER_PATH.split("/"))
    candidate_probe = candidate_root.joinpath(
        *artifact_records[0]["path"].removeprefix("candidate/").split("/")
    )
    # Metadata checks do not open secret payloads.  Kernel access is tested
    # with the suspended child's token by sandbox_broker before resume.
    for probe, context in (
        (candidate_probe, "candidate allowed probe"),
        (main_probe, "C0 main denied probe"),
        (assessor_probe, "assessor denied probe"),
        (private_probe, "private denied probe"),
    ):
        _regular_file(probe, context)
    probes = (
        sandbox_broker.AccessProbe(
            candidate_probe, sandbox_broker.PathProbeStatus.ALLOWED
        ),
        sandbox_broker.AccessProbe(main_probe, sandbox_broker.PathProbeStatus.DENIED),
        sandbox_broker.AccessProbe(vault_root, sandbox_broker.PathProbeStatus.DENIED),
        sandbox_broker.AccessProbe(private_root, sandbox_broker.PathProbeStatus.DENIED),
        # These C0-owned outcome paths remain inaccessible while the Julia
        # child is alive, including after stdout EOF while it awaits ACK.
        # Denying the namespace root also denies create/delete-child/rename
        # authority over the not-yet-published final repository name.
        sandbox_broker.AccessProbe(paths.root, sandbox_broker.PathProbeStatus.DENIED),
        sandbox_broker.AccessProbe(
            paths.staging_repository, sandbox_broker.PathProbeStatus.DENIED
        ),
        sandbox_broker.AccessProbe(
            paths.attempt_marker, sandbox_broker.PathProbeStatus.DENIED
        ),
        sandbox_broker.AccessProbe(
            ASSESSMENT_EVIDENCE_ROOT,
            sandbox_broker.PathProbeStatus.DENIED,
        ),
        # Repository history is never a candidate input.  Denying the Git
        # database prevents recovering C0/C1 Gold or private blobs by object ID.
        sandbox_broker.AccessProbe(
            REPOSITORY_ROOT / ".git", sandbox_broker.PathProbeStatus.DENIED
        ),
    )

    execution = _mapping(environment_lock.get("execution"), "environment execution")
    python_execution = _mapping(execution.get("python"), "Python execution authority")
    host = _mapping(python_execution.get("host_environment"), "host environment")
    system_root = host.get("SystemRoot") or host.get("WINDIR")
    if not isinstance(system_root, str):
        raise CandidateObservationError("environment lock has no Windows system root")
    environment = {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "PATH": os.pathsep.join(
            (
                str(julia_executable.parent),
                str(Path(system_root) / "System32"),
            )
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
        "GEOTARGET_EXECUTION_LOCK_SHA256": _sha256(_canonical(lock_document)),
        "GEOTARGET_C0_PREEXIT_PROTOCOL": (
            "u64be-frame-flush-close-stdout-crt-close-fd1-yield-read-ack/v3"
        ),
    }
    command = (
        str(julia_executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={project_root}",
        str(candidate_runner),
        "--formal-appcontainer-child",
        stage,
        str(candidate_root),
        str(paths.scratch_directory),
    )
    allowed_read = tuple(grants)
    read_identity = sandbox_broker.capture_read_identity_manifest(
        executable=julia_executable,
        allowed_read=allowed_read,
    )
    return sandbox_broker.SandboxRequest(
        command=command,
        allowed_read=allowed_read,
        scratch_directory=paths.scratch_directory,
        claim_reference=claim.sha256,
        expected_read_identity_manifest_sha256=read_identity.sha256,
        timeout_seconds=CANDIDATE_TIMEOUT_SECONDS,
        stdout_limit_bytes=STDOUT_LIMIT_BYTES,
        stderr_limit_bytes=STDERR_LIMIT_BYTES,
        preexit_payload_limit_bytes=STDOUT_LIMIT_BYTES - 8,
        max_processes=MAX_PROCESSES,
        environment=tuple(sorted(environment.items())),
        access_probes=probes,
    )


def _load_context(stage: Stage, paths: Any, claim: Any) -> RunContext:
    _verify_launcher_context(stage)
    try:
        environment_contract.verify_frozen_environment()
    except Exception as error:
        raise CandidateObservationError(
            f"frozen environment verification failed: {error}"
        ) from error
    git = execution_contract._environment_lock_git()
    head = _validate_main_state(git)
    repository = authority.GitObjectRepository(REPOSITORY_ROOT.absolute(), git)
    parents = repository.commit_parents(head)
    if len(parents) != 1:
        raise CandidateObservationError("execution-lock HEAD must have one parent")
    input_commit = parents[0]
    input_tree = repository.commit_tree(input_commit)
    head_tree = repository.commit_tree(head)
    lock_relative = (
        execution_contract.DEVELOPMENT_OUTPUT_PATH
        if stage == "development"
        else execution_contract.LOCKED_OUTPUT_PATH
    )
    lock_blob = repository.blob_at(head, lock_relative)
    lock_record = _record_from_blob(lock_relative, lock_blob)
    parent_index = dict(repository.tree_index(input_commit))
    head_index = dict(repository.tree_index(head))
    if stage == "development":
        additions = {
            *CANDIDATE_RUNTIME_SOURCE_PATHS,
            *CANDIDATE_TEST_SOURCE_PATHS,
            execution_contract.DEFAULT_EQUIVALENCE_PATH,
            lock_relative,
        }
        if set(head_index) != set(parent_index) | additions:
            raise CandidateObservationError(
                "C2 HEAD additions differ from exact topology"
            )
        if any(head_index[path] != identity for path, identity in parent_index.items()):
            raise CandidateObservationError("C2 HEAD modifies a C1 path")
        if any(head_index[path][0] != "100644" for path in additions):
            raise CandidateObservationError("C2 addition is not a regular blob")
    elif head_index != {**parent_index, lock_relative: ("100644", lock_blob.oid)}:
        raise CandidateObservationError("C5 HEAD is not the exact execution-lock child")
    lock_document = _mapping(
        authority.strict_jcs_bytes(lock_blob.data, context="candidate execution lock"),
        "candidate execution lock",
    )
    try:
        execution_contract._validate_schema(
            lock_document,
            "candidate-execution-lock.schema.json",
            "candidate execution lock",
        )
    except Exception as error:
        raise CandidateObservationError(
            f"execution lock schema failed: {error}"
        ) from error
    if lock_document.get("stage") != stage:
        raise CandidateObservationError("execution-lock stage differs")

    anchor_relative = (
        execution_contract.DEVELOPMENT_ANCHOR_PATH
        if stage == "development"
        else execution_contract.LOCKED_ANCHOR_PATH
    )
    anchor_blob = repository.blob_at(input_commit, anchor_relative)
    anchor_record = _record_from_blob(anchor_relative, anchor_blob)
    anchor = _mapping(
        authority.strict_jcs_bytes(anchor_blob.data, context="stage input anchor"),
        "stage input anchor",
    )
    try:
        execution_contract._validate_schema(
            anchor,
            "stage-vault-anchor.schema.json",
            "stage input anchor",
        )
    except Exception as error:
        raise CandidateObservationError(
            f"stage anchor schema failed: {error}"
        ) from error
    if (
        anchor.get("schema_version") != authority.ANCHOR_SCHEMA
        or anchor.get("card_sha256") != CARD_SHA256
        or anchor.get("stage") != stage
        or anchor.get("candidate_visible") is not False
        or anchor.get("rerun_permitted") is not False
        or lock_document.get("stage_input_anchor_sha256") != anchor_record["sha256"]
        or lock_document.get("stage_input_anchor_commit") != input_commit
    ):
        raise CandidateObservationError("stage anchor/execution-lock binding differs")

    source_records_raw = lock_document.get("allowed_sources")
    artifact_records_raw = lock_document.get("allowed_candidate_artifacts")
    if not isinstance(source_records_raw, list) or not isinstance(
        artifact_records_raw, list
    ):
        raise CandidateObservationError("execution-lock allowlists are malformed")
    source_records = tuple(
        _mapping(item, "allowed source") for item in source_records_raw
    )
    artifact_records = tuple(
        _mapping(item, "allowed artifact") for item in artifact_records_raw
    )
    if (
        tuple(item.get("path") for item in source_records)
        != CANDIDATE_RUNTIME_SOURCE_PATHS
    ):
        raise CandidateObservationError(
            "execution-lock runtime source order/set differs"
        )
    runner_records = [
        item for item in source_records if item.get("path") == RUNNER_PATH
    ]
    if (
        len(runner_records) != 1
        or lock_document.get("runner_source_path") != RUNNER_PATH
        or lock_document.get("runner_source_sha256") != runner_records[0].get("sha256")
        or lock_document.get("source_manifest_sha256")
        != _sha256(_canonical(list(source_records)))
    ):
        raise CandidateObservationError("execution-lock runner authority differs")
    immutable_files: list[tuple[Path, str]] = []
    for item in source_records:
        relative, digest = item.get("path"), item.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise CandidateObservationError("runtime source record is malformed")
        blob = repository.blob_at(head, relative)
        live = REPOSITORY_ROOT.joinpath(*relative.split("/"))
        _regular_file(live, f"runtime source {relative}")
        if (
            blob.mode != "100644"
            or _sha256(blob.data) != digest
            or _sha256(live.read_bytes()) != digest
        ):
            raise CandidateObservationError(f"runtime source differs: {relative}")
        immutable_files.append((live, digest))

    candidate_root_name = (
        "development-candidate-inputs"
        if stage == "development"
        else "locked-candidate-inputs"
    )
    candidate_root = EXPERIMENT_ROOT / candidate_root_name
    if not candidate_root.is_dir():
        raise CandidateObservationError("candidate publication root is unavailable")
    candidate_payloads: dict[str, bytes] = {}
    normalized_artifacts: list[Mapping[str, str]] = []
    for item in artifact_records:
        visible, digest = item.get("path"), item.get("sha256")
        if (
            not isinstance(visible, str)
            or not visible.startswith("candidate/")
            or not isinstance(digest, str)
        ):
            raise CandidateObservationError("candidate artifact record is malformed")
        relative = visible.removeprefix("candidate/")
        full_relative = (
            f"research/experiments/{EXPERIMENT_ID}/{candidate_root_name}/{relative}"
        )
        blob = repository.blob_at(input_commit, full_relative)
        live = candidate_root.joinpath(*relative.split("/"))
        _regular_file(live, f"candidate artifact {relative}")
        payload = live.read_bytes()
        if blob.mode != "100644" or blob.data != payload or _sha256(payload) != digest:
            raise CandidateObservationError(f"candidate artifact differs: {relative}")
        candidate_payloads[relative] = payload
        immutable_files.append((live, digest))
        normalized_artifacts.append(cast(Mapping[str, str], item))
    discovered = _closed_regular_tree(candidate_root, "candidate publication")
    if discovered != set(candidate_payloads):
        raise CandidateObservationError(
            "candidate publication is not a closed allowlist"
        )
    tree = dict(authority._publication_tree(candidate_payloads))
    anchor_tree = _mapping(anchor.get("candidate_publication_tree"), "candidate tree")
    if tree != dict(anchor_tree):
        raise CandidateObservationError(
            "candidate publication tree differs from anchor"
        )
    candidate_input_sha = lock_document.get("candidate_input_sha256")
    if not isinstance(candidate_input_sha, str):
        raise CandidateObservationError("candidate input digest is malformed")

    observer_authority, _ = _source_authority(repository, anchor, OBSERVER_PATH)
    launcher_authority, _ = _source_authority(repository, anchor, LAUNCHER_PATH)
    broker_authority, _ = _source_authority(repository, anchor, BROKER_PATH)
    environment_blob = repository.blob_at(
        head, execution_contract.ENVIRONMENT_LOCK_PATH
    )
    environment_lock = _mapping(
        authority.strict_jcs_bytes(environment_blob.data, context="environment lock"),
        "environment lock",
    )
    sandbox_request = _build_runtime_request(
        stage,
        paths,
        claim,
        environment_lock,
        lock_document,
        candidate_root,
        cast(Sequence[Mapping[str, str]], normalized_artifacts),
    )
    request_document = _sandbox_request_document(sandbox_request)
    immutable_files.extend(
        (
            (
                Path(sandbox_request.command[0]),
                _sha256(Path(sandbox_request.command[0]).read_bytes()),
            ),
            (
                REPOSITORY_ROOT.joinpath(*OBSERVER_PATH.split("/")),
                observer_authority["file"]["sha256"],
            ),
            (
                REPOSITORY_ROOT.joinpath(*LAUNCHER_PATH.split("/")),
                launcher_authority["file"]["sha256"],
            ),
            (
                REPOSITORY_ROOT.joinpath(*BROKER_PATH.split("/")),
                broker_authority["file"]["sha256"],
            ),
        )
    )
    return RunContext(
        stage=stage,
        git_executable=git,
        head_commit=head,
        head_tree=head_tree,
        stage_input_anchor=_external(input_commit, input_tree, anchor_record),
        execution_lock=_external(head, head_tree, lock_record),
        candidate_input_sha256=candidate_input_sha,
        candidate_publication_tree_sha256=cast(str, tree["sha256"]),
        observer_authority=observer_authority,
        launcher_authority=launcher_authority,
        broker_authority=broker_authority,
        sandbox_request=sandbox_request,
        sandbox_request_document=request_document,
        source_records=cast(tuple[Mapping[str, str], ...], source_records),
        artifact_records=cast(tuple[Mapping[str, str], ...], artifact_records),
        immutable_files=tuple(immutable_files),
        environment_lock_sha256=_sha256(environment_blob.data),
    )


def _revalidate_context(context: RunContext) -> None:
    _validate_main_state(context.git_executable, context.head_commit)
    for path, digest in context.immutable_files:
        _regular_file(path, f"immutable formal file {path}")
        if _sha256(path.read_bytes()) != digest:
            raise CandidateObservationError(
                f"formal file changed during candidate run: {path}"
            )
    environment_path = REPOSITORY_ROOT.joinpath(
        *execution_contract.ENVIRONMENT_LOCK_PATH.split("/")
    )
    if _sha256(environment_path.read_bytes()) != context.environment_lock_sha256:
        raise CandidateObservationError("environment lock changed during candidate run")


def _validate_raw(payload: bytes, context: RunContext) -> Mapping[str, Any]:
    try:
        document = _mapping(
            authority.strict_jcs_bytes(payload, context="candidate raw output"),
            "candidate raw output",
        )
        execution_contract._validate_schema(
            document,
            "candidate-output.schema.json",
            "candidate raw output",
        )
    except Exception as error:
        raise CandidateObservationError(
            f"candidate raw output is invalid: {error}"
        ) from error
    if (
        document.get("stage") != context.stage
        or document.get("candidate_input_sha256") != context.candidate_input_sha256
    ):
        raise CandidateObservationError("candidate raw output input/stage differs")
    # These C2 fields are checked for semantic consistency only.  Access
    # authority comes from the AppContainer attestation below.
    process = _mapping(document.get("candidate_process"), "candidate process report")
    runner_matches = [
        item for item in context.source_records if item.get("path") == RUNNER_PATH
    ]
    if (
        len(runner_matches) != 1
        or process.get("runner_source_path") != RUNNER_PATH
        or process.get("runner_source_sha256") != runner_matches[0].get("sha256")
        or process.get("observation_complete") is not True
        or process.get("source_manifest_sha256")
        != _sha256(_canonical(list(context.source_records)))
        or process.get("loaded_sources") != list(context.source_records)
        or process.get("opened_artifacts") != list(context.artifact_records)
    ):
        raise CandidateObservationError(
            "candidate semantic report differs from execution lock"
        )
    return document


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _attestation_document(value: sandbox_broker.SandboxAttestation) -> dict[str, Any]:
    return {
        "schema_version": value.schema_version,
        "claim_reference": value.claim_reference,
        "profile_name": value.profile_name,
        "package_sid": value.package_sid,
        "profile_storage_path": value.profile_storage_path,
        "capabilities": list(value.capabilities),
        "allowed_read_paths": list(value.allowed_read_paths),
        "read_identity_manifest_entry_count": (
            value.read_identity_manifest_entry_count
        ),
        "read_identity_manifest_sha256": value.read_identity_manifest_sha256,
        "scratch_directory": value.scratch_directory,
        "environment": [
            {"name": name, "value": item} for name, item in value.environment
        ],
        "inherited_handle_roles": list(value.inherited_handle_roles),
        "process_id": value.process_id,
        "token_is_appcontainer": value.token_is_appcontainer,
        "token_appcontainer_sid_verified": value.token_appcontainer_sid_verified,
        "token_integrity_rid": value.token_integrity_rid,
        "token_elevated": value.token_elevated,
        "token_capability_count": value.token_capability_count,
        "access_probes": [
            {
                "path": probe.path,
                "expected": probe.expected.value,
                "observed": probe.observed.value,
                "winerror": probe.winerror,
            }
            for probe in value.access_probes
        ],
        "denied_probe_entry_count": value.denied_probe_entry_count,
        "denied_probe_manifest_sha256": value.denied_probe_manifest_sha256,
        "read_only_probe_entry_count": value.read_only_probe_entry_count,
        "read_only_probe_manifest_sha256": value.read_only_probe_manifest_sha256,
        "scratch_access_probe_manifest_sha256": (
            value.scratch_access_probe_manifest_sha256
        ),
        "max_processes": value.max_processes,
        "child_process_restricted": value.child_process_restricted,
        "job_assigned_at_creation": value.job_assigned_at_creation,
        "job_membership_verified": value.job_membership_verified,
        "job_limit_flags": value.job_limit_flags,
        "breakaway_allowed": value.breakaway_allowed,
        "kill_on_job_close": value.kill_on_job_close,
        "job_empty": value.job_empty,
        "acl_entry_count": value.acl_entry_count,
        "original_acl_manifest_sha256": value.original_acl_manifest_sha256,
        "restored_acl_manifest_sha256": value.restored_acl_manifest_sha256,
        "acl_exactly_restored": value.acl_exactly_restored,
        "scratch_emptied": value.scratch_emptied,
        "profile_deleted": value.profile_deleted,
        "profile_storage_deleted": value.profile_storage_deleted,
    }


def _preexit_receipt_document(value: sandbox_broker.PreexitReceipt) -> dict[str, Any]:
    return {
        "payload_sha256": value.payload_sha256,
        "payload_byte_length": value.payload_byte_length,
        "ack_sha256": value.ack_sha256,
        "ack_byte_length": value.ack_byte_length,
        "active_processes_before_callback": value.active_processes_before_callback,
        "root_active_before_callback": value.root_active_before_callback,
        "active_processes_before_ack": value.active_processes_before_ack,
        "root_active_before_ack": value.root_active_before_ack,
        "callback_completed": value.callback_completed,
        "ack_released": value.ack_released,
    }


def _validate_sandbox_result(
    result: sandbox_broker.SandboxResult,
    context: RunContext,
    claim: Any,
    raw_payload: bytes,
    preexit_process_id: int,
    ack_sha256: str,
    ack_byte_length: int,
) -> None:
    attestation = result.attestation
    expected_probes = context.sandbox_request.access_probes
    probes = attestation.access_probes
    expected_grants = tuple(
        str(Path(os.path.abspath(grant.path)))
        for grant in context.sandbox_request.allowed_read
    )
    attested_environment = dict(attestation.environment)
    request_environment = dict(context.sandbox_request.environment)
    denied_probe_count = sum(
        probe.expected is sandbox_broker.PathProbeStatus.DENIED
        for probe in expected_probes
    )
    if (
        result.command != context.sandbox_request.command
        or result.return_code != 0
        or result.termination_reason is not sandbox_broker.TerminationReason.COMPLETED
        or result.stderr != b""
        or result.stdout != raw_payload
        or result.preexit is None
        or result.preexit.payload_sha256 != _sha256(raw_payload)
        or result.preexit.payload_byte_length != len(raw_payload)
        or result.preexit.ack_sha256 != ack_sha256
        or result.preexit.ack_byte_length != ack_byte_length
        or result.preexit.active_processes_before_callback != 1
        or result.preexit.active_processes_before_ack != 1
        or not result.preexit.root_active_before_callback
        or not result.preexit.root_active_before_ack
        or not result.preexit.callback_completed
        or not result.preexit.ack_released
        or attestation.claim_reference != claim.sha256
        or attestation.process_id != preexit_process_id
        or attestation.capabilities != ()
        or attestation.token_capability_count != 0
        or attestation.token_integrity_rid != 4096
        or attestation.allowed_read_paths != expected_grants
        or attestation.read_identity_manifest_sha256
        != context.sandbox_request.expected_read_identity_manifest_sha256
        or attestation.read_identity_manifest_entry_count
        != attestation.read_only_probe_entry_count
        or attestation.scratch_directory
        != str(Path(os.path.abspath(context.sandbox_request.scratch_directory)))
        or attestation.inherited_handle_roles != ("stdin", "stdout", "stderr")
        or any(
            attested_environment.get(key) != value
            for key, value in request_environment.items()
        )
        or attestation.denied_probe_entry_count < denied_probe_count
        or re.fullmatch(r"[0-9a-f]{64}", attestation.denied_probe_manifest_sha256)
        is None
        or attestation.read_only_probe_entry_count < 1
        or re.fullmatch(r"[0-9a-f]{64}", attestation.read_only_probe_manifest_sha256)
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}", attestation.scratch_access_probe_manifest_sha256
        )
        is None
        or not attestation.token_is_appcontainer
        or not attestation.token_appcontainer_sid_verified
        or attestation.token_elevated
        or not attestation.job_assigned_at_creation
        or not attestation.job_membership_verified
        or attestation.job_limit_flags != 0x00002008
        or attestation.max_processes != context.sandbox_request.max_processes
        or not attestation.child_process_restricted
        or attestation.breakaway_allowed
        or not attestation.kill_on_job_close
        or not attestation.job_empty
        or not attestation.acl_exactly_restored
        or attestation.original_acl_manifest_sha256
        != attestation.restored_acl_manifest_sha256
        or not attestation.scratch_emptied
        or not attestation.profile_deleted
        or not attestation.profile_storage_deleted
        or not Path(attestation.profile_storage_path).is_absolute()
        or os.path.lexists(attestation.profile_storage_path)
        or attestation.acl_entry_count != attestation.read_only_probe_entry_count + 1
        or result.total_processes != 1
        or result.terminated_processes != 0
        or len(probes) != len(expected_probes)
    ):
        raise CandidateObservationError(
            "AppContainer result does not prove the C0 policy"
        )
    for expected, observed in zip(expected_probes, probes, strict=True):
        expected_path = str(Path(os.path.abspath(expected.path)))
        if (
            observed.path != expected_path
            or observed.expected is not expected.expected
            or observed.observed is not expected.expected
            or (
                expected.expected is sandbox_broker.PathProbeStatus.DENIED
                and observed.winerror != 5
            )
            or (
                expected.expected is sandbox_broker.PathProbeStatus.ALLOWED
                and observed.winerror != 0
            )
        ):
            raise CandidateObservationError("kernel path-access probe differs")


def _validate_schema(document: Mapping[str, Any], name: str, context: str) -> None:
    try:
        execution_contract._validate_schema(document, name, context)
    except Exception as error:
        raise CandidateObservationError(f"{context} schema failed: {error}") from error


def observe_claimed(
    *,
    stage: Stage,
    paths: Any,
    claim: Any,
    context_loader: Callable[[Stage, Any, Any], RunContext] = _load_context,
    sandbox_runner: Callable[
        ..., sandbox_broker.SandboxResult
    ] = sandbox_broker.run_sandboxed,
    context_revalidator: Callable[[RunContext], None] = _revalidate_context,
) -> PublishedRun:
    """Observe one claimed candidate process and publish its closed authority."""

    if stage not in ("development", "locked") or claim.path != paths.attempt_marker:
        raise CandidateObservationError("candidate claim/stage boundary differs")
    _verify_fixed_paths(stage, paths)
    _verify_claim_binding(stage, paths, claim)
    context = context_loader(stage, paths, claim)
    if (
        context.stage != stage
        or context.sandbox_request.claim_reference != claim.sha256
    ):
        raise CandidateObservationError("loaded observer context differs from claim")
    context_revalidator(context)
    if any(
        os.path.lexists(path)
        for path in (
            paths.staging_repository,
            paths.evidence_repository,
            paths.scratch_directory,
        )
    ):
        raise CandidateObservationError(
            "candidate output/staging/scratch already exists"
        )
    try:
        paths.scratch_directory.mkdir()
    except OSError as error:
        raise CandidateObservationError(
            f"cannot create candidate scratch: {error}"
        ) from error
    _reject_reparse_ancestry(paths.scratch_directory, "candidate scratch")
    vault = _EvidenceGit(paths.staging_repository, context.git_executable)
    _reject_reparse_ancestry(paths.staging_repository, "candidate evidence staging")

    claim_document = _claim_document(claim)
    attempt = {
        "schema_version": ATTEMPT_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": stage,
        "candidate_input_sha256": context.candidate_input_sha256,
        "stage_input_anchor": dict(context.stage_input_anchor),
        "candidate_execution_lock": dict(context.execution_lock),
        "execution_source": {
            "commit": context.execution_lock["commit"],
            "tree": context.execution_lock["tree"],
        },
        "launcher_claim": claim_document,
        "launcher_authority": dict(context.launcher_authority),
        "observer_authority": dict(context.observer_authority),
        "sandbox_broker_authority": dict(context.broker_authority),
        "sandbox_request": dict(context.sandbox_request_document),
        "rerun_permitted": False,
        "prelaunch_state": {
            "launch_not_started": True,
            "candidate_process_created": False,
            "repository_control": "c0-observer",
            "runner_evaluated_by_observer": False,
            "assessor_started": False,
            "assessor_vault_opened": False,
            "generator_private_vault_opened": False,
        },
    }
    _validate_schema(attempt, "candidate-run-attempt.schema.json", "candidate attempt")
    attempt_bytes = _canonical(attempt)
    attempt_record = _record(ATTEMPT_PATH, attempt_bytes)
    attempt_ref = vault.append("candidate attempt claim", {ATTEMPT_PATH: attempt_bytes})

    raw_payload: bytes | None = None
    raw_record: dict[str, Any] | None = None
    raw_ref: _CommitRef | None = None
    seal_record: dict[str, Any] | None = None
    seal_ref: _CommitRef | None = None
    process_instance_id: str | None = None
    preexit_process_id: int | None = None
    ack = b"GEOTARGET-C0-SEALED " + secrets.token_hex(32).encode("ascii") + b"\n"
    ack_sha = _sha256(ack)
    request_sha = _sha256(_canonical(context.sandbox_request_document))

    def seal_before_ack(
        payload: bytes, preexit: sandbox_broker.PreexitContext
    ) -> bytes:
        nonlocal raw_payload, raw_record, raw_ref, seal_record, seal_ref
        nonlocal process_instance_id, preexit_process_id
        elapsed_ns = preexit.observer_elapsed_ns
        formal_timeout_ns = int(CANDIDATE_TIMEOUT_SECONDS * 1_000_000_000)
        if (
            not isinstance(elapsed_ns, int)
            or isinstance(elapsed_ns, bool)
            or elapsed_ns < 0
            or context.sandbox_request.timeout_seconds != CANDIDATE_TIMEOUT_SECONDS
        ):
            raise CandidateObservationError(
                "pre-exit observer timing authority is malformed"
            )
        remaining_ns = (
            formal_timeout_ns - elapsed_ns - PREEXIT_CALLBACK_DEADLINE_GUARD_NS
        )
        if remaining_ns <= 0:
            raise CandidateObservationError(
                "pre-exit observer deadline elapsed before the sealing callback"
            )
        callback_deadline_ns = time.perf_counter_ns() + remaining_ns
        _check_deadline(callback_deadline_ns, phase="pre-exit callback entry")
        if raw_payload is not None:
            raise CandidateObservationError(
                "candidate emitted more than one pre-exit frame"
            )
        _verify_claim_binding(stage, paths, claim)
        _check_deadline(callback_deadline_ns, phase="candidate claim revalidation")
        _validate_raw(payload, context)
        _check_deadline(callback_deadline_ns, phase="candidate raw validation")
        raw_payload = payload
        compressed = authority.deterministic_gzip(payload)
        _check_deadline(callback_deadline_ns, phase="candidate raw compression")
        raw_record = _record(RAW_PATH, compressed)
        raw_ref = vault.append(
            "candidate raw output",
            {RAW_PATH: compressed},
            deadline_ns=callback_deadline_ns,
        )
        _check_deadline(callback_deadline_ns, phase="candidate raw persistence")
        process_instance_id = _sha256(
            b"GTLOCAL3C0PROCESS1\0"
            + bytes.fromhex(claim.nonce)
            + str(preexit.process_id).encode("ascii")
            + bytes.fromhex(preexit.payload_sha256)
            + len(context.head_commit).to_bytes(1, "big")
            + bytes.fromhex(context.head_commit)
        )
        preexit_process_id = preexit.process_id
        seal = {
            "schema_version": PREEXIT_SCHEMA,
            "experiment_id": EXPERIMENT_ID,
            "card_sha256": CARD_SHA256,
            "stage": stage,
            "process_instance_id": process_instance_id,
            "candidate_input_sha256": context.candidate_input_sha256,
            "launcher_claim": claim_document,
            "observer_authority": dict(context.observer_authority),
            "sandbox_request_sha256": request_sha,
            "preexit_observation": {
                "process_id": preexit.process_id,
                "active_processes": preexit.active_processes,
                "root_process_still_active": preexit.root_process_still_active,
                "payload_sha256": preexit.payload_sha256,
                "payload_byte_length": preexit.payload_byte_length,
                "observer_elapsed_nanoseconds_decimal": str(
                    preexit.observer_elapsed_ns
                ),
                "runner_evaluated_by_observer": False,
                "raw_output_stream_closed_before_ack": True,
                "ack_pending": True,
                "assessor_started": False,
                "assessor_vault_opened": False,
                "generator_private_vault_opened": False,
            },
            "event": {
                "kind": "candidate-output-preexit-seal",
                "ordinal": 2,
                "parent": {
                    "kind": "candidate-raw-output",
                    "sha256": raw_record["sha256"],
                },
            },
            "raw_output": raw_record,
            "changed_paths": [RAW_PATH],
            "ack": {
                "token_sha256": ack_sha,
                "raw_closed_ordinal": 1,
                "seal_persisted_ordinal": 2,
                "ack_released_ordinal": 3,
            },
        }
        _validate_schema(
            seal,
            "candidate-output-preexit-seal.schema.json",
            "candidate pre-exit seal",
        )
        _check_deadline(callback_deadline_ns, phase="candidate pre-exit validation")
        seal_bytes = _canonical(seal)
        seal_record = _record(SEAL_PATH, seal_bytes)
        _check_deadline(callback_deadline_ns, phase="candidate pre-exit encoding")
        seal_ref = vault.append(
            "candidate preexit seal",
            {SEAL_PATH: seal_bytes},
            deadline_ns=callback_deadline_ns,
        )
        _check_deadline(callback_deadline_ns, phase="candidate ACK release")
        return ack

    try:
        result = sandbox_runner(context.sandbox_request, on_preexit=seal_before_ack)
    except TypeError:
        # A sandbox implementation with no callback API is never a formal
        # fallback.  Preserve the original TypeError and terminal evidence.
        raise
    if (
        raw_payload is None
        or raw_record is None
        or raw_ref is None
        or seal_record is None
        or seal_ref is None
        or process_instance_id is None
        or preexit_process_id is None
        or result.preexit is None
    ):
        raise CandidateObservationError(
            "candidate did not reach the sealed pre-exit boundary"
        )
    _validate_sandbox_result(
        result,
        context,
        claim,
        raw_payload,
        preexit_process_id,
        ack_sha,
        len(ack),
    )
    _verify_claim_binding(stage, paths, claim)
    try:
        environment_contract.verify_frozen_environment()
    except Exception as error:
        raise CandidateObservationError(
            f"post-candidate frozen environment verification failed: {error}"
        ) from error
    context_revalidator(context)

    attestation = _attestation_document(result.attestation)
    receipt = _preexit_receipt_document(result.preexit)
    sandbox_result = {
        "command_sha256": _sha256(_canonical(list(result.command))),
        "return_code": result.return_code,
        "termination_reason": result.termination_reason.value,
        "stdout_sha256": _sha256(result.stdout),
        "stdout_byte_length": len(result.stdout),
        "stderr_sha256": _sha256(result.stderr),
        "stderr_byte_length": len(result.stderr),
        "preexit_receipt": receipt,
        "job_accounting": {
            "wall_time_nanoseconds_decimal": str(result.wall_time_ns),
            "total_user_time_100ns_decimal": str(result.total_user_time_100ns),
            "total_kernel_time_100ns_decimal": str(result.total_kernel_time_100ns),
            "total_processes": result.total_processes,
            "terminated_processes": result.terminated_processes,
            "read_operation_count_decimal": str(result.read_operation_count),
            "write_operation_count_decimal": str(result.write_operation_count),
            "other_operation_count_decimal": str(result.other_operation_count),
            "read_transfer_count_decimal": str(result.read_transfer_count),
            "write_transfer_count_decimal": str(result.write_transfer_count),
            "other_transfer_count_decimal": str(result.other_transfer_count),
        },
        "appcontainer_attestation": attestation,
    }
    exit_document = {
        "schema_version": EXIT_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": stage,
        "process_instance_id": process_instance_id,
        "candidate_input_sha256": context.candidate_input_sha256,
        "launcher_claim": claim_document,
        "observer_authority": dict(context.observer_authority),
        "event": {
            "kind": "candidate-process-exit",
            "ordinal": 5,
            "parent": {
                "kind": "candidate-output-preexit-seal",
                "sha256": seal_record["sha256"],
            },
        },
        "raw_output": raw_record,
        "preexit_seal": seal_record,
        "changed_paths": [RAW_PATH],
        "ack": {
            "token_sha256": ack_sha,
            "ack_released_ordinal": 3,
            "successful_exit_after_ack_ordinal": 4,
            "job_empty_observed_ordinal": 5,
        },
        "exit_status": {"kind": "exited", "code": result.return_code},
        "candidate_accounting": {
            "process_cpu_nanoseconds_decimal": str(
                (result.total_user_time_100ns + result.total_kernel_time_100ns) * 100
            ),
            "observer_wall_nanoseconds_decimal": str(result.wall_time_ns),
            "host_exclusion_passed": True,
            "count_in_end_to_end_exactly_once": True,
        },
        "sandbox_result": sandbox_result,
        "termination_observation": {
            "wait_observed": True,
            "job_tree_empty": result.attestation.job_empty,
            "ack_sent_after_preexit_commit": result.preexit.ack_released,
            "candidate_access_revoked": result.attestation.acl_exactly_restored,
            "profile_deleted": result.attestation.profile_deleted,
            "scratch_emptied": result.attestation.scratch_emptied,
            "runner_evaluated_by_observer": False,
            "assessor_started": False,
            "assessor_vault_opened": False,
            "generator_private_vault_opened": False,
        },
    }
    _validate_schema(
        exit_document, "candidate-process-exit.schema.json", "candidate exit"
    )
    exit_bytes = _canonical(exit_document)
    exit_record = _record(EXIT_PATH, exit_bytes)
    exit_ref = vault.append("candidate process exit", {EXIT_PATH: exit_bytes})

    manifest = {
        "schema_version": authority.MANIFEST_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": stage,
        "kind": "candidate-run",
        "files": [
            {
                "role": "raw_output",
                "file": raw_record,
                "media_type": "application/json",
                "content_encoding": "deterministic-gzip",
            },
            {
                "role": "preexit_seal",
                "file": seal_record,
                "media_type": "application/json",
                "content_encoding": "identity",
            },
            {
                "role": "process_exit",
                "file": exit_record,
                "media_type": "application/json",
                "content_encoding": "identity",
            },
        ],
    }
    _validate_schema(
        manifest, "authority-file-manifest.schema.json", "candidate manifest"
    )
    manifest_bytes = _canonical(manifest)
    manifest_record = _record(MANIFEST_PATH, manifest_bytes)
    authority_document = {
        "schema_version": AUTHORITY_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": stage,
        "process_instance_id": process_instance_id,
        "candidate_input_sha256": context.candidate_input_sha256,
        "stage_input_anchor": dict(context.stage_input_anchor),
        "candidate_execution_lock": dict(context.execution_lock),
        "candidate_publication_tree_sha256": context.candidate_publication_tree_sha256,
        "launcher_claim_sha256": claim.sha256,
        "observer_authority": dict(context.observer_authority),
        "sandbox_broker_authority": dict(context.broker_authority),
        "sandbox_result_sha256": _sha256(_canonical(sandbox_result)),
        "attempt_claim": attempt_record,
        "history": {
            "attempt_claim": {"commit": attempt_ref.commit, "tree": attempt_ref.tree},
            "raw_output": {"commit": raw_ref.commit, "tree": raw_ref.tree},
            "preexit_seal": {"commit": seal_ref.commit, "tree": seal_ref.tree},
            "process_exit": {"commit": exit_ref.commit, "tree": exit_ref.tree},
        },
        "event": {
            "kind": "candidate-run-authority",
            "ordinal": 6,
            "parent": {
                "kind": "candidate-process-exit",
                "sha256": exit_record["sha256"],
            },
        },
        "raw_output": raw_record,
        "preexit_seal": seal_record,
        "process_exit": exit_record,
        "changed_paths": [RAW_PATH],
        "manifest": manifest_record,
    }
    _validate_schema(
        authority_document,
        "candidate-run-authority.schema.json",
        "candidate run authority",
    )
    authority_bytes = _canonical(authority_document)
    authority_record_dict = _record(AUTHORITY_PATH, authority_bytes)
    vault.append(
        "candidate run authority",
        {MANIFEST_PATH: manifest_bytes, AUTHORITY_PATH: authority_bytes},
    )
    commit, tree = vault.verify_closed()
    context_revalidator(context)
    _verify_claim_binding(stage, paths, claim)
    if any(paths.scratch_directory.iterdir()):
        raise CandidateObservationError(
            "candidate scratch is not empty after broker cleanup"
        )
    try:
        paths.scratch_directory.rmdir()
    except OSError as error:
        raise CandidateObservationError(
            f"cannot remove empty candidate scratch: {error}"
        ) from error
    durable_rename_noreplace(paths.staging_repository, paths.evidence_repository)
    repository = authority.GitObjectRepository(
        paths.evidence_repository.absolute(), context.git_executable
    )
    if (
        repository.commit_tree(commit) != tree
        or set(repository.tree_index(commit)) != EVIDENCE_PATHS
    ):
        raise CandidateObservationError("published candidate evidence differs")
    authority_file = authority.FileRecord(
        path=AUTHORITY_PATH,
        sha256=cast(str, authority_record_dict["sha256"]),
        byte_length=cast(int, authority_record_dict["byte_length"]),
    )
    return PublishedRun(paths.evidence_repository, commit, tree, authority_file)


def main() -> int:
    raise CandidateObservationError(
        "direct execution is prohibited; use launch_candidate.py"
    )


if __name__ == "__main__":
    raise SystemExit(main())
