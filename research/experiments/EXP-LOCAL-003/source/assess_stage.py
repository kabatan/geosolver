"""One-shot, physically separate assessor orchestrator for EXP-LOCAL-003.

The command has exactly two formal invocations::

    python -I -B -S .../assess_stage.py development
    python -I -B -S .../assess_stage.py locked

It resolves every input from closed Git objects, runs the frozen assessor once
for the requested stage, publishes an orphan assessment commit plus one child,
and writes (but deliberately does not commit) the corresponding main-repository
anchor.  The external staging directory is the durable attempt claim: any
failure after it is created is terminal and a subsequent invocation refuses to
resume, replace, or retry it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, Mapping, cast


# Invalid non-``-B`` invocations must not create project bytecode before the
# formal entry point has rejected them.  ``sys.flags`` is unchanged, so the
# invocation check still proves that ``-B`` was supplied by the caller.
sys.dont_write_bytecode = True


Stage = Literal["development", "locked"]
CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"
EXPERIMENT_ID = "EXP-LOCAL-003"
SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
EXPERIMENT_ROOT = SOURCE_ROOT.parent
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

CANDIDATE_EVIDENCE_PATHS = frozenset(
    {
        "attempt-claim.json",
        "candidate-output.json.gz",
        "candidate-output-preexit-seal.json",
        "candidate-process-exit.json",
        "manifest.json",
        "candidate-run-authority.json",
    }
)
ASSESSMENT_PATH = "assessment.json"
ASSESSOR_AUTHORITY_PATH = "assessor-stage-authority.json"
DEVELOPMENT_DECISION_PATH = "development-decision-record.json"
FINAL_CONNECTION_PATH = "final-connection.json"
ATTEMPT_MARKER = ".FORMAL_ASSESSMENT_ATTEMPT_CLAIM.json"


class AssessmentStageError(RuntimeError):
    """The formal assessor protocol cannot continue safely."""


def _verify_preimport_hygiene() -> None:
    """Reject every known pre-claim Python import-injection surface."""

    if sys.flags.no_site != 1 or "site" in sys.modules:
        raise AssessmentStageError(
            "formal assessor requires site-disabled `python -I -B -S`"
        )
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise AssessmentStageError(
            f"formal assessor has injection environment: {blocked}"
        )
    if any("site-packages" in value.casefold() for value in sys.path):
        raise AssessmentStageError(
            "site-packages was active before the formal assessment claim"
        )
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise AssessmentStageError(
                    f"stale project bytecode exists under {current}"
                )


def _activate_claimed_import_paths() -> None:
    """Expose the fixed venv without importing ``site`` or processing ``.pth``."""

    try:
        executable = Path(sys.executable).resolve(strict=True)
        venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    except OSError as error:
        raise AssessmentStageError(
            "fixed project venv cannot be resolved after the assessment claim"
        ) from error
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise AssessmentStageError(
            "formal assessor is not using the fixed project venv executable"
        )
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise AssessmentStageError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


@dataclass(frozen=True, slots=True)
class Layout:
    """All fixed repositories and anchors used by the one-shot command."""

    repository_root: Path
    experiment_root: Path
    environment_lock: Path
    development_input_vault: Path
    development_candidate_evidence: Path
    development_assessor_output: Path
    locked_input_vault: Path
    locked_candidate_evidence: Path
    locked_assessor_output: Path
    development_anchor: Path
    final_connection_anchor: Path

    @classmethod
    def fixed(cls, repository_root: Path = REPOSITORY_ROOT) -> Layout:
        root = repository_root.absolute()
        experiment = root / "research" / "experiments" / EXPERIMENT_ID
        vault = root.with_name(f"{root.name}-vault") / EXPERIMENT_ID
        runs = root.with_name(f"{root.name}-run-evidence") / EXPERIMENT_ID
        assessments = root.with_name(f"{root.name}-assessment-evidence") / EXPERIMENT_ID
        return cls(
            repository_root=root,
            experiment_root=experiment,
            environment_lock=experiment / "environment-lock.json",
            development_input_vault=vault / "development-assessor-vault",
            development_candidate_evidence=runs / "development-candidate-run",
            development_assessor_output=(assessments / "development-assessor-output"),
            locked_input_vault=vault / "locked-assessor-vault",
            locked_candidate_evidence=runs / "locked-candidate-run",
            locked_assessor_output=assessments / "locked-assessor-output",
            development_anchor=(
                experiment / "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
            ),
            final_connection_anchor=(experiment / "C6_FINAL_CONNECTION_ANCHOR.json"),
        )


@dataclass(frozen=True, slots=True)
class ResolvedStage:
    """Typed C1/C4 input plus the matching closed candidate evidence."""

    head_commit: str
    head_tree: str
    input_commit: str
    input_tree: str
    input_file: Any
    stage_input: Any
    candidate_run: Any
    candidate_commit: str
    candidate_tree: str
    candidate_authority_file: Any


@dataclass(frozen=True, slots=True)
class PublishedOutput:
    """The orphan assessment commit and its exact single child."""

    repository: Path
    assessment_commit: str
    assessment_tree: str
    assessment_file: Any
    authority_file: Any
    child_commit: str
    child_tree: str
    child_file: Any


@dataclass(frozen=True, slots=True)
class BootstrapGit:
    """Pure-stdlib Git identity used before authority.py may be imported."""

    path: Path
    sha256: str


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise AssessmentStageError(f"{context} must be a JSON object")
    return cast(Mapping[str, Any], value)


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
            raise AssessmentStageError(
                f"formal repository path traverses a reparse point: {entry}"
            )


def _same_or_nested(left: Path, right: Path) -> bool:
    try:
        common = Path(os.path.commonpath((left.absolute(), right.absolute())))
    except ValueError:
        return False
    return common in (left.absolute(), right.absolute())


def _verify_separate_roots(paths: tuple[Path, ...]) -> None:
    resolved: list[Path] = []
    for path in paths:
        if not path.is_dir():
            raise AssessmentStageError(f"formal repository is missing: {path}")
        _reject_reparse_ancestry(path, include_leaf=True)
        resolved.append(path.resolve(strict=True))
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if os.path.samefile(left, right) or _same_or_nested(left, right):
                raise AssessmentStageError(
                    "formal main/input/candidate/output repositories are not separate"
                )


def _closed_git_environment(git_path: Path) -> dict[str, str]:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment = {
        "PATH": os.pathsep.join((str(git_path.parent), str(system_root / "System32"))),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_AUTHOR_NAME": "EXP-LOCAL-003 assessor",
        "GIT_AUTHOR_EMAIL": "exp-local-003@invalid",
        "GIT_COMMITTER_NAME": "EXP-LOCAL-003 assessor",
        "GIT_COMMITTER_EMAIL": "exp-local-003@invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for name in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP"):
        if (value := os.environ.get(name)) is not None:
            environment[name] = value
    return environment


def _git_bytes(
    git_executable: Any,
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    command = [
        str(git_executable.path),
        "--no-replace-objects",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "commit.gpgSign=false",
        "-c",
        "transfer.fsckObjects=true",
        "-c",
        "core.fsync=committed,reference",
        "-c",
        "core.fsyncMethod=fsync",
        "-C",
        str(repository),
        *arguments,
    ]
    completed = subprocess.run(
        command,
        input=input_bytes,
        check=False,
        capture_output=True,
        env=_closed_git_environment(Path(git_executable.path)),
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AssessmentStageError(
            f"closed Git command failed ({' '.join(arguments)}): {message}"
        )
    return bytes(completed.stdout)


def _git(
    git_executable: Any,
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> str:
    try:
        return (
            _git_bytes(
                git_executable,
                repository,
                *arguments,
                input_bytes=input_bytes,
            )
            .decode("utf-8")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise AssessmentStageError("closed Git output is not UTF-8") from error


def _assert_clean_head(repository: Path, git_executable: Any) -> tuple[str, str]:
    status = _git(
        git_executable,
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise AssessmentStageError(
            f"formal repository worktree is not clean: {repository}"
        )
    commit = _git(git_executable, repository, "rev-parse", "HEAD")
    tree = _git(git_executable, repository, "rev-parse", "HEAD^{tree}")
    return commit, tree


def _verify_main_branch(repository: Path, git_executable: Any) -> None:
    branch = _git(git_executable, repository, "branch", "--show-current")
    if branch != "main":
        raise AssessmentStageError("formal main repository branch must be main")


def _load_contract_modules() -> tuple[ModuleType, ModuleType]:
    for path in (PYTHON_SOURCE, SOURCE_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import assessor  # noqa: PLC0415
    import authority  # noqa: PLC0415

    return authority, assessor


def _verify_frozen_environment() -> None:
    module_path = SOURCE_ROOT / "materialize_development.py"
    _reject_reparse_ancestry(module_path, include_leaf=True)
    spec = importlib.util.spec_from_file_location(
        "_exp_local_003_frozen_environment_verifier", module_path
    )
    if spec is None or spec.loader is None:
        raise AssessmentStageError("fixed C0 environment verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module_file = getattr(module, "__file__", None)
    verifier = getattr(module, "verify_frozen_environment", None)
    if (
        not isinstance(module_file, str)
        or Path(module_file).resolve() != module_path.resolve()
        or not callable(verifier)
    ):
        raise AssessmentStageError("fixed C0 environment verifier differs")
    verifier()


def _bootstrap_pinned_git(layout: Layout) -> BootstrapGit:
    """Resolve the environment-locked Git without importing project code."""

    def reject_constant(token: str) -> None:
        raise ValueError(f"non-standard JSON constant {token}")

    def reject_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    try:
        document = json.loads(
            layout.environment_lock.read_text(encoding="utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AssessmentStageError(
            f"cannot bootstrap the formal environment lock: {error}"
        ) from error
    if not isinstance(document, dict):
        raise AssessmentStageError("formal environment lock is not an object")
    tools = document.get("tools")
    if (
        document.get("schema_version") != "exp-local-003-environment-lock/v1"
        or document.get("card_sha256") != CARD_SHA256
        or not isinstance(tools, dict)
        or not isinstance(tools.get("git_executable"), str)
        or not isinstance(tools.get("git_sha256"), str)
    ):
        raise AssessmentStageError("formal environment-lock Git authority is malformed")
    git_path = Path(tools["git_executable"])
    digest = tools["git_sha256"]
    try:
        if (
            not git_path.is_absolute()
            or not git_path.is_file()
            or _sha256(git_path.read_bytes()) != digest
        ):
            raise AssessmentStageError("environment-locked Git executable drift")
    except OSError as error:
        raise AssessmentStageError(
            f"cannot read environment-locked Git executable: {error}"
        ) from error
    return BootstrapGit(path=git_path, sha256=digest)


def _verify_contract_sources_at_head(
    git_executable: Any, head: str, repository_root: Path
) -> None:
    """Bind every soon-to-be-imported C0 module to the clean main HEAD."""

    for name in (
        "assess_stage.py",
        "materialize_development.py",
        "authority.py",
        "assessor.py",
    ):
        relative = f"research/experiments/EXP-LOCAL-003/source/{name}"
        committed = _git_bytes(
            git_executable,
            repository_root,
            "cat-file",
            "blob",
            f"{head}:{relative}",
        )
        path = repository_root.joinpath(*relative.split("/"))
        if (
            not path.is_file()
            or _rejectable_source_path(path)
            or path.read_bytes() != committed
        ):
            raise AssessmentStageError(
                f"formal contract source differs from clean main HEAD: {relative}"
            )


def _rejectable_source_path(path: Path) -> bool:
    try:
        _reject_reparse_ancestry(path, include_leaf=True)
    except AssessmentStageError:
        return True
    return False


def _pinned_git(layout: Layout, authority_module: ModuleType) -> Any:
    try:
        payload = layout.environment_lock.read_bytes()
    except OSError as error:
        raise AssessmentStageError("formal environment lock is unavailable") from error
    document = _mapping(
        authority_module.strict_jcs_bytes(payload, context="environment lock"),
        "environment lock",
    )
    tools = _mapping(document.get("tools"), "environment lock tools")
    path_value = tools.get("git_executable")
    digest = tools.get("git_sha256")
    if (
        document.get("schema_version") != "exp-local-003-environment-lock/v1"
        or document.get("card_sha256") != CARD_SHA256
        or not isinstance(path_value, str)
        or not isinstance(digest, str)
    ):
        raise AssessmentStageError("environment lock Git contract differs")
    try:
        return authority_module.pin_git_executable(Path(path_value), digest)
    except Exception as error:
        raise AssessmentStageError("environment-locked Git executable drift") from error


def _file_record(authority_module: ModuleType, path: str, payload: bytes) -> Any:
    return authority_module.FileRecord(
        path=path,
        sha256=_sha256(payload),
        byte_length=len(payload),
    )


def _record_dict(record: Any) -> dict[str, Any]:
    return {
        "path": record.path,
        "sha256": record.sha256,
        "byte_length": record.byte_length,
    }


def _external_file(commit: str, tree: str, record: Any) -> dict[str, Any]:
    return {"commit": commit, "tree": tree, "file": _record_dict(record)}


def _git_file_record(
    authority_module: ModuleType,
    repository: Any,
    commit: str,
    path: str,
) -> Any:
    blob = repository.blob_at(commit, path)
    if blob.mode != "100644":
        raise AssessmentStageError(f"formal authority is not a regular blob: {path}")
    return _file_record(authority_module, path, blob.data)


def _candidate_authority(
    authority_module: ModuleType,
    candidate_repository: Path,
    git_executable: Any,
) -> tuple[str, str, Any]:
    commit, tree = _assert_clean_head(candidate_repository, git_executable)
    repository = authority_module.GitObjectRepository(
        candidate_repository, git_executable
    )
    index = repository.tree_index(commit)
    if set(index) != CANDIDATE_EVIDENCE_PATHS or any(
        mode != "100644" for mode, _oid in index.values()
    ):
        raise AssessmentStageError(
            "candidate evidence HEAD is not the fixed closed six-file tree"
        )
    record = _git_file_record(
        authority_module, repository, commit, "candidate-run-authority.json"
    )
    return commit, tree, record


def _resolve_stage(
    stage: Stage,
    *,
    layout: Layout,
    authority_module: ModuleType,
    git_executable: Any,
) -> ResolvedStage:
    input_vault = (
        layout.development_input_vault
        if stage == "development"
        else layout.locked_input_vault
    )
    candidate_repository = (
        layout.development_candidate_evidence
        if stage == "development"
        else layout.locked_candidate_evidence
    )
    _verify_separate_roots((layout.repository_root, input_vault, candidate_repository))
    head_commit, head_tree = _assert_clean_head(layout.repository_root, git_executable)
    main = authority_module.GitObjectRepository(layout.repository_root, git_executable)
    parents = main.commit_parents(head_commit)
    if len(parents) != 1:
        raise AssessmentStageError(f"{stage} HEAD is not a single-child execution lock")
    input_commit = parents[0]
    input_tree = main.commit_tree(input_commit)
    anchor_name = (
        "C1_STAGE_VAULT_ANCHOR.json"
        if stage == "development"
        else "C4_LOCKED_STAGE_VAULT_ANCHOR.json"
    )
    anchor_path = f"research/experiments/{EXPERIMENT_ID}/{anchor_name}"
    anchor_file = _git_file_record(authority_module, main, input_commit, anchor_path)
    candidate_root = layout.experiment_root / (
        "development-candidate-inputs"
        if stage == "development"
        else "locked-candidate-inputs"
    )
    stage_input = authority_module.resolve_stage_input_authority(
        anchor_repository=layout.repository_root,
        anchor_commit=input_commit,
        anchor_path=anchor_path,
        anchor_sha256=anchor_file.sha256,
        candidate_publication_root=candidate_root,
        assessor_vault_repository=input_vault,
        git_executable=git_executable,
    )
    if stage_input.anchor_tree != input_tree or stage_input.anchor_file != anchor_file:
        raise AssessmentStageError("stage input resolver changed the fixed anchor")
    if stage_input.stage != stage:
        raise AssessmentStageError("stage input resolver returned the wrong stage")
    input_vault_head, _input_vault_tree = _assert_clean_head(
        input_vault, git_executable
    )
    if input_vault_head != stage_input.assessor_vault_commit:
        raise AssessmentStageError("assessor input vault HEAD differs from its anchor")
    candidate_commit, candidate_tree, candidate_file = _candidate_authority(
        authority_module, candidate_repository, git_executable
    )
    candidate_run = authority_module.resolve_candidate_run_authority(
        candidate_repository,
        git_executable=git_executable,
        commit=candidate_commit,
        tree=candidate_tree,
        authority_file=candidate_file,
        expected_stage=stage,
        stage_input=stage_input,
        execution_lock_repository=layout.repository_root,
    )
    expected_lock_path = f"research/experiments/{EXPERIMENT_ID}/" + (
        "candidate-execution-lock.json"
        if stage == "development"
        else "locked-candidate-execution-lock.json"
    )
    if (
        candidate_run.candidate_execution_lock_commit != head_commit
        or candidate_run.candidate_execution_lock_tree != head_tree
        or candidate_run.candidate_execution_lock_file.path != expected_lock_path
    ):
        raise AssessmentStageError(
            f"{stage} candidate evidence does not bind the exact HEAD execution lock"
        )
    if stage == "development":
        verifier = getattr(authority_module, "_verify_c2_introduction", None)
        if not callable(verifier):
            raise AssessmentStageError("frozen C2 introduction verifier is unavailable")
        verifier(
            main,
            stage_input_commit=input_commit,
            c2_source_commit=head_commit,
        )
        evidence_verifier = getattr(
            authority_module, "_verify_c2_equivalence_evidence", None
        )
        if not callable(evidence_verifier):
            raise AssessmentStageError("frozen C2 equivalence verifier is unavailable")
        evidence_verifier(
            main,
            c2_source_commit=head_commit,
            stage_input=stage_input,
            candidate_run=candidate_run,
        )
    else:
        parent_index = dict(main.tree_index(input_commit))
        head_index = dict(main.tree_index(head_commit))
        lock_blob = main.blob_at(head_commit, expected_lock_path)
        expected_index = {
            **parent_index,
            expected_lock_path: ("100644", lock_blob.oid),
        }
        if head_index != expected_index:
            raise AssessmentStageError(
                "locked HEAD is not the exact single-blob C5 execution-lock commit"
            )
    return ResolvedStage(
        head_commit=head_commit,
        head_tree=head_tree,
        input_commit=input_commit,
        input_tree=input_tree,
        input_file=anchor_file,
        stage_input=stage_input,
        candidate_run=candidate_run,
        candidate_commit=candidate_commit,
        candidate_tree=candidate_tree,
        candidate_authority_file=candidate_file,
    )


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_write(path: Path, payload: bytes) -> None:
    if os.name == "nt":
        _exclusive_write_windows(path, payload)
        return
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_SYNC", 0),
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("exclusive authority write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path.parent)


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
    close.restype = wintypes.BOOL
    handle = create(
        str(path),
        0x40000000,
        0,
        None,
        1,
        0x80000080,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + 0x7FFF_FFFF]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not write(
                handle,
                buffer,
                len(chunk),
                ctypes.byref(written),
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value <= 0:
                raise OSError("exclusive authority write made no progress")
            offset += written.value
        if not flush(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        close(handle)


def _durable_rename(source: Path, destination: Path) -> None:
    try:
        destination.lstat()
    except FileNotFoundError:
        pass
    else:
        raise AssessmentStageError(f"formal output already exists: {destination}")
    if os.name == "nt":
        import ctypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move = kernel32.MoveFileExW
        move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        move.restype = ctypes.c_int
        if not move(str(source), str(destination), 0x8):
            error = ctypes.WinError(ctypes.get_last_error())
            raise AssessmentStageError(
                "exclusive durable output rename failed"
            ) from error
    elif sys.platform.startswith("linux"):
        import ctypes  # noqa: PLC0415
        import errno  # noqa: PLC0415

        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise AssessmentStageError("renameat2(RENAME_NOREPLACE) is unavailable")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            -100,
            os.fsencode(source),
            -100,
            os.fsencode(destination),
            1,
        )
        if result != 0:
            number = ctypes.get_errno()
            error = OSError(number, os.strerror(number), str(destination))
            if number == errno.EEXIST:
                raise AssessmentStageError(
                    f"formal output already exists: {destination}"
                ) from error
            raise AssessmentStageError(
                "exclusive durable output rename failed"
            ) from error
        _fsync_parent(destination.parent)
    else:
        raise AssessmentStageError(
            "formal output requires an OS no-replace directory rename primitive"
        )


def _stage_output_paths(stage: Stage, layout: Layout) -> tuple[Path, Path, Path]:
    output = (
        layout.development_assessor_output
        if stage == "development"
        else layout.locked_assessor_output
    )
    staging = output.with_name(f".{output.name}-staging.partial")
    anchor = (
        layout.development_anchor
        if stage == "development"
        else layout.final_connection_anchor
    )
    return output, staging, anchor


def _attempt_marker_bytes(stage: Stage) -> bytes:
    return (
        '{"card_sha256":"'
        + CARD_SHA256
        + '","rerun_permitted":false,"schema_version":"'
        "geotarget.exp-local-003.assessment-attempt-claim/v1" + f'","stage":"{stage}"}}'
    ).encode("ascii")


def _claim_output(stage: Stage, layout: Layout) -> tuple[Path, Path]:
    output, staging, anchor = _stage_output_paths(stage, layout)
    for path in (output, staging, anchor):
        if path.exists():
            raise AssessmentStageError(
                f"formal assessment cannot overwrite, resume, or retry: {path}"
            )
    _reject_reparse_ancestry(output.parent, include_leaf=True)
    if not output.parent.is_dir():
        raise AssessmentStageError(
            "C0-provisioned assessment evidence namespace is unavailable"
        )
    _reject_reparse_ancestry(output.parent, include_leaf=True)
    try:
        staging.mkdir()
    except FileExistsError as error:
        raise AssessmentStageError(
            "formal assessment attempt already exists"
        ) from error
    _fsync_parent(staging.parent)
    _exclusive_write(staging / ATTEMPT_MARKER, _attempt_marker_bytes(stage))
    return output, staging


def _initialize_output_repository(
    stage: Stage, staging: Path, git_executable: Any
) -> None:
    entries = {entry.name for entry in staging.iterdir()}
    marker = staging / ATTEMPT_MARKER
    if entries == {ATTEMPT_MARKER}:
        if marker.read_bytes() != _attempt_marker_bytes(stage):
            raise AssessmentStageError("formal assessment attempt marker differs")
        _git(git_executable, staging, "init", "--quiet")
        entries = {entry.name for entry in staging.iterdir()}
    if entries != {".git", ATTEMPT_MARKER} or not (staging / ".git").is_dir():
        raise AssessmentStageError("claimed assessor staging repository is not empty")
    if marker.read_bytes() != _attempt_marker_bytes(stage):
        raise AssessmentStageError("formal assessment attempt marker differs")
    marker.unlink()
    _fsync_parent(staging)
    if (
        _git(git_executable, staging, "config", "--get", "core.fsync")
        != "committed,reference"
        or _git(git_executable, staging, "config", "--get", "core.fsyncMethod")
        != "fsync"
    ):
        raise AssessmentStageError("Git committed-object fsync contract is unavailable")


def _repository_roots(stage: Stage, layout: Layout, output: Path) -> tuple[Path, ...]:
    if stage == "development":
        return (
            layout.repository_root,
            layout.development_input_vault,
            layout.development_candidate_evidence,
            output,
        )
    return (
        layout.repository_root,
        layout.development_input_vault,
        layout.development_candidate_evidence,
        layout.development_assessor_output,
        layout.locked_input_vault,
        layout.locked_candidate_evidence,
        output,
    )


def _verify_repository_storage(
    paths: tuple[Path, ...], authority_module: ModuleType, git_executable: Any
) -> None:
    _verify_separate_roots(paths)
    object_databases = [
        authority_module.GitObjectRepository(path, git_executable).object_database
        for path in paths
    ]
    for index, left in enumerate(object_databases):
        for right in object_databases[index + 1 :]:
            if os.path.samefile(left, right):
                raise AssessmentStageError("formal repositories share Git objects")


def _require_bound_head(
    repository: Path,
    expected_commit: str,
    expected_tree: str,
    git_executable: Any,
) -> None:
    commit, tree = _assert_clean_head(repository, git_executable)
    if commit != expected_commit or tree != expected_tree:
        raise AssessmentStageError(f"formal repository HEAD changed: {repository}")


def _reverify_bound_heads(
    stage: Stage,
    *,
    layout: Layout,
    resolved: ResolvedStage,
    development: Any,
    published: PublishedOutput,
    git_executable: Any,
) -> None:
    bindings = [
        (layout.repository_root, resolved.head_commit, resolved.head_tree),
        (
            (
                layout.development_input_vault
                if stage == "development"
                else layout.locked_input_vault
            ),
            resolved.stage_input.assessor_vault_commit,
            resolved.stage_input.assessor_vault_tree,
        ),
        (
            (
                layout.development_candidate_evidence
                if stage == "development"
                else layout.locked_candidate_evidence
            ),
            resolved.candidate_commit,
            resolved.candidate_tree,
        ),
        (published.repository, published.child_commit, published.child_tree),
    ]
    if stage == "locked":
        if development is None:
            raise AssessmentStageError("locked stage lost development authority")
        if (
            development.assessor_output.decision_commit is None
            or development.assessor_output.decision_tree is None
        ):
            raise AssessmentStageError("development decision HEAD is unavailable")
        bindings.extend(
            (
                (
                    layout.development_input_vault,
                    development.stage_input.assessor_vault_commit,
                    development.stage_input.assessor_vault_tree,
                ),
                (
                    layout.development_candidate_evidence,
                    development.candidate_run.vault_commit,
                    development.candidate_run.vault_tree,
                ),
                (
                    layout.development_assessor_output,
                    development.assessor_output.decision_commit,
                    development.assessor_output.decision_tree,
                ),
            )
        )
    for repository, commit, tree in bindings:
        _require_bound_head(repository, commit, tree, git_executable)


def _commit_files(
    repository: Path,
    git_executable: Any,
    paths: tuple[str, ...],
    message: str,
) -> tuple[str, str]:
    _git(git_executable, repository, "add", "--", *paths)
    _git(
        git_executable,
        repository,
        "commit",
        "--quiet",
        "--no-gpg-sign",
        "-m",
        message,
    )
    return _assert_clean_head(repository, git_executable)


def _verify_published_output(
    *,
    authority_module: ModuleType,
    repository: Path,
    git_executable: Any,
    assessment_commit: str,
    assessment_tree: str,
    assessment_file: Any,
    authority_file: Any,
    child_commit: str,
    child_tree: str,
    child_file: Any,
    assessment_bytes: bytes,
    authority_bytes: bytes,
    child_bytes: bytes,
) -> None:
    git_repository = authority_module.GitObjectRepository(repository, git_executable)
    if git_repository.commit_parents(assessment_commit):
        raise AssessmentStageError("assessment commit is not an orphan root")
    if git_repository.commit_parents(child_commit) != (assessment_commit,):
        raise AssessmentStageError("assessment child is not the exact single child")
    if git_repository.commit_tree(assessment_commit) != assessment_tree:
        raise AssessmentStageError("assessment root tree differs")
    if git_repository.commit_tree(child_commit) != child_tree:
        raise AssessmentStageError("assessment child tree differs")
    root_index = git_repository.tree_index(assessment_commit)
    child_index = git_repository.tree_index(child_commit)
    root_paths = {assessment_file.path, authority_file.path}
    child_paths = {*root_paths, child_file.path}
    if (
        set(root_index) != root_paths
        or set(child_index) != child_paths
        or any(mode != "100644" for mode, _oid in root_index.values())
        or any(mode != "100644" for mode, _oid in child_index.values())
    ):
        raise AssessmentStageError("assessor output Git trees are not closed")
    root_expected = {
        assessment_file.path: assessment_bytes,
        authority_file.path: authority_bytes,
    }
    for path, payload in root_expected.items():
        if git_repository.blob_at(assessment_commit, path).data != payload:
            raise AssessmentStageError(f"assessment root blob differs: {path}")
        if child_index[path] != root_index[path]:
            raise AssessmentStageError(
                f"assessment child changed a parent authority blob: {path}"
            )
    expected = {
        **root_expected,
        child_file.path: child_bytes,
    }
    for path, payload in expected.items():
        if git_repository.blob_at(child_commit, path).data != payload:
            raise AssessmentStageError(f"assessor output blob differs: {path}")


def _publish_output(
    stage: Stage,
    *,
    layout: Layout,
    authority_module: ModuleType,
    git_executable: Any,
    formal: Any,
    build_child: Any,
    claimed_paths: tuple[Path, Path] | None = None,
) -> PublishedOutput:
    if claimed_paths is None:
        output, staging = _claim_output(stage, layout)
        _initialize_output_repository(stage, staging, git_executable)
    else:
        output, staging = claimed_paths
        if {entry.name for entry in staging.iterdir()} != {".git"}:
            raise AssessmentStageError(
                "initialized assessor staging repository is not empty"
            )
    assessment_file = _file_record(
        authority_module, ASSESSMENT_PATH, formal.assessment_jcs
    )
    authority_file = _file_record(
        authority_module, ASSESSOR_AUTHORITY_PATH, formal.authority_jcs
    )
    _exclusive_write(staging / ASSESSMENT_PATH, formal.assessment_jcs)
    _exclusive_write(staging / ASSESSOR_AUTHORITY_PATH, formal.authority_jcs)
    assessment_commit, assessment_tree = _commit_files(
        staging,
        git_executable,
        (ASSESSMENT_PATH, ASSESSOR_AUTHORITY_PATH),
        f"EXP-LOCAL-003 {stage} assessment authority",
    )
    child_name = (
        DEVELOPMENT_DECISION_PATH if stage == "development" else FINAL_CONNECTION_PATH
    )
    child_document = build_child(assessment_commit)
    child_bytes = authority_module.canonical_bytes(child_document)
    authority_module.strict_jcs_bytes(child_bytes, context=child_name)
    child_file = _file_record(authority_module, child_name, child_bytes)
    _exclusive_write(staging / child_name, child_bytes)
    child_commit, child_tree = _commit_files(
        staging,
        git_executable,
        (child_name,),
        (
            "EXP-LOCAL-003 development decision"
            if stage == "development"
            else "EXP-LOCAL-003 final product connection"
        ),
    )
    _verify_published_output(
        authority_module=authority_module,
        repository=staging,
        git_executable=git_executable,
        assessment_commit=assessment_commit,
        assessment_tree=assessment_tree,
        assessment_file=assessment_file,
        authority_file=authority_file,
        child_commit=child_commit,
        child_tree=child_tree,
        child_file=child_file,
        assessment_bytes=formal.assessment_jcs,
        authority_bytes=formal.authority_jcs,
        child_bytes=child_bytes,
    )
    _durable_rename(staging, output)
    _verify_published_output(
        authority_module=authority_module,
        repository=output,
        git_executable=git_executable,
        assessment_commit=assessment_commit,
        assessment_tree=assessment_tree,
        assessment_file=assessment_file,
        authority_file=authority_file,
        child_commit=child_commit,
        child_tree=child_tree,
        child_file=child_file,
        assessment_bytes=formal.assessment_jcs,
        authority_bytes=formal.authority_jcs,
        child_bytes=child_bytes,
    )
    return PublishedOutput(
        repository=output,
        assessment_commit=assessment_commit,
        assessment_tree=assessment_tree,
        assessment_file=assessment_file,
        authority_file=authority_file,
        child_commit=child_commit,
        child_tree=child_tree,
        child_file=child_file,
    )


def _development_anchor(
    authority_module: ModuleType,
    resolved: ResolvedStage,
    published: PublishedOutput,
) -> dict[str, Any]:
    return {
        "schema_version": authority_module.DEVELOPMENT_AUTHORIZATION_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": "development",
        "stage_input_anchor": _external_file(
            resolved.input_commit, resolved.input_tree, resolved.input_file
        ),
        "c2_source_commit": resolved.head_commit,
        "candidate_evidence": {
            "commit": resolved.candidate_commit,
            "tree": resolved.candidate_tree,
            "authority": _record_dict(resolved.candidate_authority_file),
        },
        "assessor_output": {
            "assessment_commit": published.assessment_commit,
            "assessment_tree": published.assessment_tree,
            "assessment_file": _record_dict(published.assessment_file),
            "authority_file": _record_dict(published.authority_file),
            "decision_commit": published.child_commit,
            "decision_tree": published.child_tree,
            "decision_file": _record_dict(published.child_file),
        },
        "rerun_permitted": False,
    }


def _final_connection_anchor(
    authority_module: ModuleType,
    resolved: ResolvedStage,
    development: Any,
    published: PublishedOutput,
) -> dict[str, Any]:
    return {
        "schema_version": authority_module.FINAL_CONNECTION_ANCHOR_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "stage": "locked",
        "development_authorization": _external_file(
            development.authorization_anchor_commit,
            development.authorization_anchor_tree,
            development.authorization_anchor_file,
        ),
        "locked_stage_input": _external_file(
            resolved.input_commit, resolved.input_tree, resolved.input_file
        ),
        "locked_execution_lock": _external_file(
            resolved.head_commit,
            resolved.head_tree,
            resolved.candidate_run.candidate_execution_lock_file,
        ),
        "candidate_evidence": {
            "commit": resolved.candidate_commit,
            "tree": resolved.candidate_tree,
            "authority": _record_dict(resolved.candidate_authority_file),
        },
        "assessor_output": {
            "assessment_commit": published.assessment_commit,
            "assessment_tree": published.assessment_tree,
            "assessment_file": _record_dict(published.assessment_file),
            "authority_file": _record_dict(published.authority_file),
            "final_connection_commit": published.child_commit,
            "final_connection_tree": published.child_tree,
            "final_connection_file": _record_dict(published.child_file),
        },
        "rerun_permitted": False,
    }


def _write_anchor(
    path: Path, document: Mapping[str, Any], authority_module: ModuleType
) -> bytes:
    payload = authority_module.canonical_bytes(document)
    authority_module.strict_jcs_bytes(payload, context=path.name)
    _exclusive_write(path, payload)
    return payload


def _verify_uncommitted_anchor(
    *,
    layout: Layout,
    anchor: Path,
    payload: bytes,
    expected_commit: str,
    expected_tree: str,
    git_executable: Any,
) -> None:
    try:
        relative = anchor.relative_to(layout.repository_root).as_posix()
    except ValueError as error:
        raise AssessmentStageError(
            "formal anchor is outside the main repository"
        ) from error
    expected_status = f"?? {relative}"
    for _pass in range(2):
        _verify_main_branch(layout.repository_root, git_executable)
        commit = _git(git_executable, layout.repository_root, "rev-parse", "HEAD")
        tree = _git(git_executable, layout.repository_root, "rev-parse", "HEAD^{tree}")
        status = _git(
            git_executable,
            layout.repository_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        try:
            metadata = anchor.lstat()
            observed = anchor.read_bytes()
        except OSError as error:
            raise AssessmentStageError(
                "uncommitted formal anchor disappeared"
            ) from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            commit != expected_commit
            or tree != expected_tree
            or status != expected_status
            or not stat.S_ISREG(metadata.st_mode)
            or attributes & reparse
            or observed != payload
        ):
            raise AssessmentStageError(
                "main HEAD/worktree changed while publishing the formal anchor"
            )


def _development_authorization_commit(
    resolved: ResolvedStage,
) -> str:
    development_authority = _mapping(
        resolved.stage_input.development_authority,
        "locked stage development authority",
    )
    value = development_authority.get("development_authorization_anchor_commit")
    if not isinstance(value, str):
        raise AssessmentStageError("C4 does not bind the development authorization")
    return value


def run_stage(
    stage: Stage,
    *,
    layout: Layout | None = None,
    authority_module: ModuleType | None = None,
    assessor_module: ModuleType | None = None,
    _activate_formal_imports: bool = False,
) -> Path:
    """Run exactly one formal stage and return its uncommitted anchor path."""

    if stage not in ("development", "locked"):
        raise AssessmentStageError("stage must be development or locked")
    selected_layout = layout or Layout.fixed()
    # This pure-stdlib mkdir is the first mutation after CLI validation.  It is
    # intentionally earlier than project imports, Git pinning, and all typed
    # replay: every failure in a formally requested C3/C6 transaction is final.
    claimed_paths = _claim_output(stage, selected_layout)
    output, staging = claimed_paths
    if _activate_formal_imports:
        _activate_claimed_import_paths()
    bootstrap_git = _bootstrap_pinned_git(selected_layout)
    bootstrap_head, bootstrap_tree = _assert_clean_head(
        selected_layout.repository_root, bootstrap_git
    )
    _verify_main_branch(selected_layout.repository_root, bootstrap_git)
    _verify_contract_sources_at_head(
        bootstrap_git, bootstrap_head, selected_layout.repository_root
    )
    _verify_frozen_environment()
    if _assert_clean_head(selected_layout.repository_root, bootstrap_git) != (
        bootstrap_head,
        bootstrap_tree,
    ):
        raise AssessmentStageError(
            "main HEAD/tree changed during pre-import environment verification"
        )
    _verify_main_branch(selected_layout.repository_root, bootstrap_git)
    if authority_module is None or assessor_module is None:
        loaded_authority, loaded_assessor = _load_contract_modules()
        authority_module = authority_module or loaded_authority
        assessor_module = assessor_module or loaded_assessor
    git_executable = _pinned_git(selected_layout, authority_module)
    if (
        Path(git_executable.path).resolve() != bootstrap_git.path.resolve()
        or git_executable.sha256 != bootstrap_git.sha256
    ):
        raise AssessmentStageError(
            "typed Git authority differs from the pre-import bootstrap"
        )
    _initialize_output_repository(stage, staging, git_executable)
    preassessment_roots = _repository_roots(stage, selected_layout, staging)
    _verify_repository_storage(preassessment_roots, authority_module, git_executable)
    if _assert_clean_head(selected_layout.repository_root, git_executable) != (
        bootstrap_head,
        bootstrap_tree,
    ):
        raise AssessmentStageError("main HEAD/tree changed before typed replay")
    _verify_main_branch(selected_layout.repository_root, git_executable)
    _expected_output, _expected_staging, anchor = _stage_output_paths(
        stage, selected_layout
    )
    if output != _expected_output or staging != _expected_staging:
        raise AssessmentStageError("formal staging claim path differs")

    resolved = _resolve_stage(
        stage,
        layout=selected_layout,
        authority_module=authority_module,
        git_executable=git_executable,
    )
    development = None
    if stage == "locked":
        development_commit = _development_authorization_commit(resolved)
        development = authority_module.resolve_development_authorization(
            selected_layout.repository_root,
            selected_layout.development_input_vault,
            selected_layout.development_candidate_evidence,
            selected_layout.development_assessor_output,
            authorization_anchor_commit=development_commit,
            assess=assessor_module.assess,
            build_development_decision=(
                assessor_module.build_development_decision_record
            ),
            git_executable=git_executable,
        )
        expected_development_heads = (
            (
                selected_layout.development_input_vault,
                development.stage_input.assessor_vault_commit,
            ),
            (
                selected_layout.development_candidate_evidence,
                development.candidate_run.vault_commit,
            ),
            (
                selected_layout.development_assessor_output,
                development.assessor_output.decision_commit,
            ),
        )
        for repository, expected_head in expected_development_heads:
            observed_head, _observed_tree = _assert_clean_head(
                repository, git_executable
            )
            if expected_head is None or observed_head != expected_head:
                raise AssessmentStageError(
                    "development authority repository HEAD differs"
                )

    formal = authority_module.assess_with_authority(
        assessor_module.assess,
        stage_input=resolved.stage_input,
        candidate_run=resolved.candidate_run,
    )

    if stage == "development":

        def build_child(assessment_commit: str) -> Any:
            return assessor_module.build_development_decision_record(
                formal.assessment,
                resolved.candidate_run.raw_output,
                resolved.stage_input.assessor_truth,
                resolved.stage_input.bootstrap_indices,
                resolved.candidate_run.candidate_execution_lock,
                assessment_commit,
            )

    else:
        if development is None:
            raise AssessmentStageError("locked stage lost development authority")

        def build_child(_assessment_commit: str) -> Any:
            decision = development.assessor_output.decision
            if decision is None:
                raise AssessmentStageError("development authority has no decision")
            return assessor_module.finalize_product_connection(
                development.assessor_output.formal.assessment,
                formal.assessment,
                decision,
                development_raw_document=development.candidate_run.raw_output,
                development_assessor_truth=development.stage_input.assessor_truth,
                development_bootstrap_bytes=(development.stage_input.bootstrap_indices),
                development_execution_lock=(
                    development.candidate_run.candidate_execution_lock
                ),
                locked_raw_document=resolved.candidate_run.raw_output,
                locked_assessor_truth=resolved.stage_input.assessor_truth,
                locked_bootstrap_bytes=resolved.stage_input.bootstrap_indices,
                locked_execution_lock=(resolved.candidate_run.candidate_execution_lock),
            )

    published = _publish_output(
        stage,
        layout=selected_layout,
        authority_module=authority_module,
        git_executable=git_executable,
        formal=formal,
        build_child=build_child,
        claimed_paths=claimed_paths,
    )
    existing_roots = _repository_roots(stage, selected_layout, published.repository)
    _verify_repository_storage(existing_roots, authority_module, git_executable)
    _reverify_bound_heads(
        stage,
        layout=selected_layout,
        resolved=resolved,
        development=development,
        published=published,
        git_executable=git_executable,
    )

    document = (
        _development_anchor(authority_module, resolved, published)
        if stage == "development"
        else _final_connection_anchor(
            authority_module, resolved, development, published
        )
    )
    anchor_payload = _write_anchor(anchor, document, authority_module)
    _verify_uncommitted_anchor(
        layout=selected_layout,
        anchor=anchor,
        payload=anchor_payload,
        expected_commit=resolved.head_commit,
        expected_tree=resolved.head_tree,
        git_executable=git_executable,
    )
    return anchor


def _verify_formal_invocation(argv: list[str]) -> Stage:
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
    ):
        raise AssessmentStageError("formal CLI requires exact Python flags -I -B -S")
    if len(argv) != 2 or argv[1] not in ("development", "locked"):
        raise AssessmentStageError(
            "usage: python -I -B -S assess_stage.py development|locked"
        )
    try:
        script = Path(argv[0]).resolve(strict=True)
        cwd = Path.cwd().resolve(strict=True)
    except OSError as error:
        raise AssessmentStageError("formal CLI path resolution failed") from error
    if script != Path(__file__).resolve(strict=True):
        raise AssessmentStageError("formal CLI script path differs")
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if not isinstance(main_file, str) or Path(main_file).resolve(strict=True) != script:
        raise AssessmentStageError("formal CLI must execute this script directly")
    if not os.path.samefile(cwd, REPOSITORY_ROOT):
        raise AssessmentStageError("formal CLI cwd must be the main repository root")
    _verify_preimport_hygiene()
    return cast(Stage, argv[1])


def main(argv: list[str] | None = None) -> int:
    stage = _verify_formal_invocation(list(sys.argv if argv is None else argv))
    run_stage(stage, _activate_formal_imports=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssessmentStageError as error:
        print(f"formal-assessment-failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
