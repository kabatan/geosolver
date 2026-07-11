"""Read-only formal C6 verifier for the complete EXP-LOCAL-003 authority chain."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, cast


sys.dont_write_bytecode = True

CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"
EXPERIMENT_ID = "EXP-LOCAL-003"
SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
C6_RELATIVE_PATH = "research/experiments/EXP-LOCAL-003/C6_FINAL_CONNECTION_ANCHOR.json"
SUMMARY_SCHEMA = "geotarget.exp-local-003.final-authorization-verification/v1"
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


class FinalVerificationError(RuntimeError):
    """The committed terminal authority is missing, mutable, or inconsistent."""


def _verify_preimport_hygiene() -> None:
    """Prove that verification begins outside every supported injection path."""

    if sys.flags.no_site != 1 or "site" in sys.modules:
        raise FinalVerificationError(
            "formal final verification requires site-disabled `python -I -B -S`"
        )
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise FinalVerificationError(
            f"formal final verification has injection environment: {blocked}"
        )
    if any("site-packages" in value.casefold() for value in sys.path):
        raise FinalVerificationError(
            "site-packages was active before final authority verification"
        )
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise FinalVerificationError(
                    f"stale project bytecode exists under {current}"
                )


def _activate_formal_import_paths() -> None:
    """Expose fixed dependencies directly, without ``site`` or ``.pth`` code."""

    try:
        executable = Path(sys.executable).resolve(strict=True)
        venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    except OSError as error:
        raise FinalVerificationError(
            "fixed project venv cannot be resolved for final verification"
        ) from error
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise FinalVerificationError(
            "formal final verification is not using the fixed project venv"
        )
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise FinalVerificationError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


@dataclass(frozen=True, slots=True)
class Layout:
    """The nine fixed repositories required by the terminal resolver/audit."""

    main: Path
    environment_lock: Path
    development_input: Path
    development_private: Path
    development_candidate: Path
    development_output: Path
    locked_input: Path
    locked_private: Path
    locked_candidate: Path
    locked_output: Path

    @classmethod
    def fixed(cls, repository_root: Path = REPOSITORY_ROOT) -> Layout:
        main = repository_root.absolute()
        experiment = main / "research" / "experiments" / EXPERIMENT_ID
        vault = main.with_name(f"{main.name}-vault") / EXPERIMENT_ID
        private = main.with_name(f"{main.name}-private-audit") / EXPERIMENT_ID
        runs = main.with_name(f"{main.name}-run-evidence") / EXPERIMENT_ID
        assessments = main.with_name(f"{main.name}-assessment-evidence") / EXPERIMENT_ID
        return cls(
            main=main,
            environment_lock=experiment / "environment-lock.json",
            development_input=vault / "development-assessor-vault",
            development_private=private / "development-generator-private-vault",
            development_candidate=runs / "development-candidate-run",
            development_output=assessments / "development-assessor-output",
            locked_input=vault / "locked-assessor-vault",
            locked_private=private / "locked-generator-private-vault",
            locked_candidate=runs / "locked-candidate-run",
            locked_output=assessments / "locked-assessor-output",
        )


@dataclass(frozen=True, slots=True)
class BootstrapGit:
    """Pure-stdlib Git identity resolved before project modules are imported."""

    path: Path
    sha256: str


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise FinalVerificationError(f"{context} is not a JSON object")
    return cast(Mapping[str, Any], value)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise FinalVerificationError(
            f"cannot inspect formal path {path}: {error}"
        ) from error
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


def _import_frozen(name: str, path: Path) -> ModuleType:
    if not path.is_file() or _is_link_or_reparse(path):
        raise FinalVerificationError(f"frozen module is unavailable: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise FinalVerificationError(f"cannot load frozen module: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _load_contract_modules() -> tuple[ModuleType, ModuleType, ModuleType]:
    for path in (PYTHON_SOURCE, SOURCE_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    materializer = _import_frozen(
        "local3_final_environment", SOURCE_ROOT / "materialize_development.py"
    )
    authority = _import_frozen("local3_final_authority", SOURCE_ROOT / "authority.py")
    assessor = _import_frozen("local3_final_assessor", SOURCE_ROOT / "assessor.py")
    return materializer, authority, assessor


def _bootstrap_pinned_git(layout: Layout) -> BootstrapGit:
    """Resolve Git from strict environment JSON without project imports."""

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
        raise FinalVerificationError(
            f"cannot bootstrap the formal environment lock: {error}"
        ) from error
    if not isinstance(document, dict):
        raise FinalVerificationError("formal environment lock is not an object")
    tools = document.get("tools")
    if (
        document.get("schema_version") != "exp-local-003-environment-lock/v1"
        or document.get("card_sha256") != CARD_SHA256
        or not isinstance(tools, dict)
        or not isinstance(tools.get("git_executable"), str)
        or not isinstance(tools.get("git_sha256"), str)
    ):
        raise FinalVerificationError("environment-lock Git authority is malformed")
    path = Path(tools["git_executable"])
    digest = tools["git_sha256"]
    try:
        if (
            not path.is_absolute()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise FinalVerificationError("environment-locked Git executable drift")
    except OSError as error:
        raise FinalVerificationError(
            f"cannot read environment-locked Git executable: {error}"
        ) from error
    return BootstrapGit(path=path, sha256=digest)


def _verify_contract_sources_at_head(
    layout: Layout, git_executable: Any, head: str
) -> None:
    for name in (
        "verify_final_authorization.py",
        "materialize_development.py",
        "authority.py",
        "assessor.py",
    ):
        relative = f"research/experiments/EXP-LOCAL-003/source/{name}"
        path = layout.main.joinpath(*relative.split("/"))
        committed = _git_bytes(
            git_executable,
            layout.main,
            "cat-file",
            "blob",
            f"{head}:{relative}",
        )
        if (
            not path.is_file()
            or _is_link_or_reparse(path)
            or path.read_bytes() != committed
        ):
            raise FinalVerificationError(
                f"formal contract source differs from clean main HEAD: {relative}"
            )


def _pinned_git(layout: Layout, authority_module: ModuleType) -> Any:
    try:
        payload = layout.environment_lock.read_bytes()
        document = _mapping(
            authority_module.strict_jcs_bytes(payload, context="environment lock"),
            "environment lock",
        )
    except OSError as error:
        raise FinalVerificationError("environment lock is unavailable") from error
    tools = _mapping(document.get("tools"), "environment lock tools")
    path_value = tools.get("git_executable")
    digest = tools.get("git_sha256")
    if (
        document.get("schema_version") != "exp-local-003-environment-lock/v1"
        or document.get("card_sha256") != CARD_SHA256
        or not isinstance(path_value, str)
        or not isinstance(digest, str)
    ):
        raise FinalVerificationError("environment-locked Git identity is malformed")
    try:
        return authority_module.pin_git_executable(Path(path_value), digest)
    except Exception as error:
        raise FinalVerificationError(
            "environment-locked Git executable drift"
        ) from error


def _closed_git_environment(git_path: Path) -> dict[str, str]:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment = {
        "PATH": os.pathsep.join((str(git_path.parent), str(system_root / "System32"))),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for name in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP"):
        if (value := os.environ.get(name)) is not None:
            environment[name] = value
    return environment


def _git_bytes(git_executable: Any, repository: Path, *arguments: str) -> bytes:
    if not repository.is_dir() or _is_link_or_reparse(repository):
        raise FinalVerificationError(f"formal repository is unavailable: {repository}")
    dot_git = repository / ".git"
    if not dot_git.is_dir() or _is_link_or_reparse(dot_git):
        raise FinalVerificationError(f"formal repository is not direct: {repository}")
    completed = subprocess.run(
        [
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
            "core.bare=false",
            "-c",
            f"core.worktree={repository}",
            "-c",
            "core.sparseCheckout=false",
            "-c",
            "core.sparseCheckoutCone=false",
            "-C",
            str(repository),
            *arguments,
        ],
        check=False,
        capture_output=True,
        env=_closed_git_environment(Path(git_executable.path)),
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise FinalVerificationError(
            f"closed Git command failed in {repository} ({' '.join(arguments)}): "
            f"{message}"
        )
    return bytes(completed.stdout)


def _git_text(git_executable: Any, repository: Path, *arguments: str) -> str:
    try:
        return (
            _git_bytes(git_executable, repository, *arguments)
            .decode("utf-8", errors="strict")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise FinalVerificationError("closed Git output is not UTF-8") from error


def _clean_head(git_executable: Any, repository: Path) -> tuple[str, str]:
    status = _git_bytes(
        git_executable,
        repository,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if status:
        raise FinalVerificationError(f"formal repository is not clean: {repository}")
    commit = _git_text(git_executable, repository, "rev-parse", "HEAD")
    tree = _git_text(git_executable, repository, "rev-parse", "HEAD^{tree}")
    _verify_repository_storage_and_worktree(git_executable, repository, commit)
    return commit, tree


def _lexists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise FinalVerificationError(
            f"cannot inspect formal path {path}: {error}"
        ) from error
    return True


def _raw_git_blob_oid(payload: bytes, algorithm: str) -> str:
    if algorithm not in ("sha1", "sha256"):
        raise FinalVerificationError(
            f"unsupported formal Git object format: {algorithm}"
        )
    digest = hashlib.new(algorithm)
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)
    return digest.hexdigest()


def _tree_blobs(
    git_executable: Any, repository: Path, commit: str
) -> dict[str, tuple[str, str]]:
    raw = _git_bytes(git_executable, repository, "ls-tree", "-r", "-z", commit)
    blobs: dict[str, tuple[str, str]] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        try:
            identity, path_bytes = entry.split(b"\t", 1)
            mode, kind, oid = identity.decode("ascii").split(" ")
            relative = path_bytes.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError) as error:
            raise FinalVerificationError(
                "formal Git tree listing is malformed"
            ) from error
        if (
            mode not in ("100644", "100755")
            or kind != "blob"
            or not relative
            or "\\" in relative
            or relative.startswith("/")
            or any(part in ("", ".", "..") for part in relative.split("/"))
            or relative in blobs
        ):
            raise FinalVerificationError(
                f"formal Git tree has an unsupported entry: {relative!r}"
            )
        blobs[relative] = (mode, oid)
    return blobs


def _verify_repository_storage_and_worktree(
    git_executable: Any, repository: Path, commit: str
) -> None:
    """Independently match a direct worktree to every raw HEAD blob."""

    root = repository.absolute()
    dot_git = root / ".git"
    forbidden_storage = (
        dot_git / "commondir",
        dot_git / "shallow",
        dot_git / "info" / "grafts",
        dot_git / "objects" / "info" / "alternates",
        dot_git / "objects" / "info" / "http-alternates",
    )
    if any(_lexists(path) for path in forbidden_storage):
        raise FinalVerificationError(
            f"formal repository uses redirected/incomplete Git storage: {root}"
        )
    if _git_bytes(
        git_executable,
        root,
        "for-each-ref",
        "--format=%(refname)",
        "refs/replace",
    ):
        raise FinalVerificationError(f"formal repository has replacement refs: {root}")
    top = Path(_git_text(git_executable, root, "rev-parse", "--show-toplevel"))
    git_dir = Path(_git_text(git_executable, root, "rev-parse", "--absolute-git-dir"))
    try:
        if not os.path.samefile(top, root) or not os.path.samefile(git_dir, dot_git):
            raise FinalVerificationError(
                f"formal repository top/Git directory is redirected: {root}"
            )
    except OSError as error:
        raise FinalVerificationError(
            f"cannot compare formal repository storage identity: {error}"
        ) from error

    for current, directory_names, file_names in os.walk(dot_git, followlinks=False):
        for name in (*directory_names, *file_names):
            path = Path(current) / name
            if _is_link_or_reparse(path):
                raise FinalVerificationError(
                    f"formal .git storage contains a link/reparse point: {path}"
                )

    object_format = _git_text(git_executable, root, "rev-parse", "--show-object-format")
    expected_files = _tree_blobs(git_executable, root, commit)
    expected_directories = {
        "/".join(parts[:index])
        for relative in expected_files
        for parts in (relative.split("/"),)
        for index in range(1, len(parts))
    }
    actual_files: dict[str, Path] = {}
    actual_directories: set[str] = set()
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        if current_path == root:
            if ".git" not in directory_names:
                raise FinalVerificationError(
                    f"formal repository lost direct .git: {root}"
                )
            directory_names.remove(".git")
        for name in directory_names:
            path = current_path / name
            if _is_link_or_reparse(path):
                raise FinalVerificationError(
                    f"formal worktree contains a directory link/reparse point: {path}"
                )
            actual_directories.add(path.relative_to(root).as_posix())
        for name in file_names:
            path = current_path / name
            metadata = path.lstat()
            attributes = getattr(metadata, "st_file_attributes", 0)
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or attributes & reparse
                or metadata.st_nlink != 1
            ):
                raise FinalVerificationError(
                    f"formal worktree entry is not an unaliased regular file: {path}"
                )
            actual_files[path.relative_to(root).as_posix()] = path
    if (
        set(actual_files) != set(expected_files)
        or actual_directories != expected_directories
    ):
        raise FinalVerificationError(
            f"formal worktree inventory differs from HEAD tree: {root}"
        )
    for relative, path in actual_files.items():
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise FinalVerificationError(
                f"cannot read formal worktree file {path}: {error}"
            ) from error
        if _raw_git_blob_oid(payload, object_format) != expected_files[relative][1]:
            raise FinalVerificationError(
                f"formal worktree bytes differ from raw HEAD blob: {path}"
            )


def _main_c6_head(layout: Layout, git_executable: Any) -> tuple[str, str]:
    if _git_text(git_executable, layout.main, "branch", "--show-current") != "main":
        raise FinalVerificationError("formal final verification requires main branch")
    commit, tree = _clean_head(git_executable, layout.main)
    introduction = _git_text(
        git_executable,
        layout.main,
        "log",
        "-1",
        "--diff-filter=A",
        "--format=%H",
        "HEAD",
        "--",
        C6_RELATIVE_PATH,
    )
    if introduction != commit:
        raise FinalVerificationError(
            "main HEAD is not the C6 final-anchor introduction commit"
        )
    return commit, tree


def _require_bound_head(
    git_executable: Any,
    repository: Path,
    expected_commit: str,
    expected_tree: str,
) -> None:
    commit, tree = _clean_head(git_executable, repository)
    if commit != expected_commit or tree != expected_tree:
        raise FinalVerificationError(
            f"formal repository HEAD/tree differs from C6 authority: {repository}"
        )


_PRIVATE_ANCHOR_KEYS = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "source_lock_commit",
    "materialization_attempt_claim_sha256",
    "stage_vault_anchor_sha256",
    "generator_private_vault_git_commit",
    "generator_private_vault_git_tree",
    "generator_private_vault_manifest_sha256",
    "generator_private_vault_completion_sha256",
    "generator_private_manifest_sha256",
    "candidate_manifest_sha256",
    "candidate_visible",
    "formal_assessor_input",
    "rerun_permitted",
}


def _lower_hex(value: Any, lengths: tuple[int, ...], context: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) not in lengths
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FinalVerificationError(f"{context} is not canonical lowercase hex")
    return value


def _private_anchor_binding(
    layout: Layout,
    git_executable: Any,
    authority_module: ModuleType,
    stage_record: Any,
    stage: str,
) -> tuple[str, str, Mapping[str, Any]]:
    """Resolve an audit-only private vault from the immutable C1/C4 blob."""

    if stage not in ("development", "locked"):
        raise FinalVerificationError("private-audit stage is unsupported")
    name = (
        "C1_PRIVATE_AUDIT_ANCHOR.json"
        if stage == "development"
        else "C4_LOCKED_PRIVATE_AUDIT_ANCHOR.json"
    )
    relative = f"research/experiments/{EXPERIMENT_ID}/{name}"
    try:
        payload = _git_bytes(
            git_executable,
            layout.main,
            "cat-file",
            "blob",
            f"{stage_record.anchor_commit}:{relative}",
        )
        anchor = _mapping(
            authority_module.strict_jcs_bytes(
                payload, context=f"{stage} private-audit anchor"
            ),
            f"{stage} private-audit anchor",
        )
    except FinalVerificationError:
        raise
    except Exception as error:
        raise FinalVerificationError(
            f"{stage} private-audit anchor is invalid: {error}"
        ) from error
    if set(anchor) != _PRIVATE_ANCHOR_KEYS:
        raise FinalVerificationError(f"{stage} private-audit anchor field set differs")
    if (
        anchor["schema_version"]
        != "geotarget.exp-local-003.generator-private-vault-anchor/v1"
        or anchor["experiment_id"] != EXPERIMENT_ID
        or anchor["card_sha256"] != CARD_SHA256
        or anchor["stage"] != stage
        or anchor["candidate_visible"] is not False
        or anchor["formal_assessor_input"] is not False
        or anchor["rerun_permitted"] is not False
    ):
        raise FinalVerificationError(
            f"{stage} private-audit anchor identity/policy differs"
        )
    for field in (
        "materialization_attempt_claim_sha256",
        "stage_vault_anchor_sha256",
        "generator_private_vault_manifest_sha256",
        "generator_private_vault_completion_sha256",
        "generator_private_manifest_sha256",
        "candidate_manifest_sha256",
    ):
        _lower_hex(anchor[field], (64,), f"{stage} private anchor.{field}")
    commit = _lower_hex(
        anchor["generator_private_vault_git_commit"],
        (40, 64),
        f"{stage} private anchor.commit",
    )
    tree = _lower_hex(
        anchor["generator_private_vault_git_tree"],
        (40, 64),
        f"{stage} private anchor.tree",
    )
    if len(commit) != len(tree):
        raise FinalVerificationError(
            f"{stage} private-audit commit/tree object formats differ"
        )
    public_anchor = _mapping(stage_record.anchor, f"{stage} stage anchor")
    expected_pairs = {
        "source_lock_commit": stage_record.source_lock_commit,
        "materialization_attempt_claim_sha256": public_anchor.get(
            "materialization_attempt_claim_sha256"
        ),
        "stage_vault_anchor_sha256": stage_record.anchor_file.sha256,
        "candidate_manifest_sha256": public_anchor.get("candidate_manifest_sha256"),
    }
    if any(anchor[field] != expected for field, expected in expected_pairs.items()):
        raise FinalVerificationError(
            f"{stage} private-audit anchor is split from its formal stage anchor"
        )
    return commit, tree, anchor


def _verify_private_repository(
    git_executable: Any,
    repository: Path,
    commit: str,
    tree: str,
    anchor: Mapping[str, Any],
    stage: str,
) -> None:
    """Verify the clean private root commit and all anchor-bound audit blobs."""

    if _git_text(git_executable, repository, "branch", "--show-current") != (
        "private-evidence"
    ):
        raise FinalVerificationError(f"{stage} private-audit repository branch differs")
    parents = _git_text(
        git_executable, repository, "rev-list", "--parents", "-n", "1", "HEAD"
    ).split()
    if parents != [commit]:
        raise FinalVerificationError(
            f"{stage} private-audit seal is not an orphan root commit"
        )
    bound_blobs = {
        "generator_private_vault_manifest_sha256": "manifest.json",
        "generator_private_vault_completion_sha256": "ONE_SHOT_COMPLETE.json",
        "generator_private_manifest_sha256": "generator-private/manifest.json",
    }
    for field, relative in bound_blobs.items():
        payload = _git_bytes(
            git_executable,
            repository,
            "cat-file",
            "blob",
            f"{commit}:{relative}",
        )
        if hashlib.sha256(payload).hexdigest() != anchor[field]:
            raise FinalVerificationError(
                f"{stage} private-audit anchor hash mismatch: {relative}"
            )


def verify(
    *,
    layout: Layout | None = None,
    materializer_module: ModuleType | None = None,
    authority_module: ModuleType | None = None,
    assessor_module: ModuleType | None = None,
    git_executable: Any | None = None,
) -> bytes:
    """Resolve C6, verify all nine clean HEADs, and return canonical summary."""

    selected = layout or Layout.fixed()
    bootstrap_git = git_executable or _bootstrap_pinned_git(selected)
    c6_commit, c6_tree = _main_c6_head(selected, bootstrap_git)
    must_load_modules = (
        materializer_module is None
        or authority_module is None
        or assessor_module is None
    )
    if must_load_modules:
        _verify_contract_sources_at_head(selected, bootstrap_git, c6_commit)
    if (
        materializer_module is None
        or authority_module is None
        or assessor_module is None
    ):
        loaded_materializer, loaded_authority, loaded_assessor = (
            _load_contract_modules()
        )
        materializer_module = materializer_module or loaded_materializer
        authority_module = authority_module or loaded_authority
        assessor_module = assessor_module or loaded_assessor

    verify_environment = getattr(materializer_module, "verify_frozen_environment", None)
    if not callable(verify_environment):
        raise FinalVerificationError(
            "C0 materializer lacks public frozen-environment verification"
        )
    try:
        verify_environment()
    except Exception as error:
        raise FinalVerificationError(
            f"frozen environment verification failed: {error}"
        ) from error
    git = git_executable or _pinned_git(selected, authority_module)
    if (
        Path(git.path).resolve() != Path(bootstrap_git.path).resolve()
        or git.sha256 != bootstrap_git.sha256
    ):
        raise FinalVerificationError(
            "typed Git authority differs from the pre-import bootstrap"
        )
    if _main_c6_head(selected, git) != (c6_commit, c6_tree):
        raise FinalVerificationError(
            "main C6 HEAD/tree changed during environment/module verification"
        )
    try:
        resolved = authority_module.resolve_locked_authorization(
            selected.main,
            selected.development_input,
            selected.development_candidate,
            selected.development_output,
            selected.locked_input,
            selected.locked_candidate,
            selected.locked_output,
            authorization_anchor_commit=c6_commit,
            assess=assessor_module.assess,
            build_development_decision=(
                assessor_module.build_development_decision_record
            ),
            finalize_product_connection=assessor_module.finalize_product_connection,
            git_executable=git,
        )
    except Exception as error:
        raise FinalVerificationError(
            f"complete C6 authority resolution failed: {error}"
        ) from error

    development_decision_commit = resolved.development.assessor_output.decision_commit
    development_decision_tree = resolved.development.assessor_output.decision_tree
    if not isinstance(development_decision_commit, str) or not isinstance(
        development_decision_tree, str
    ):
        raise FinalVerificationError("development decision HEAD is unavailable")
    development_private_commit, development_private_tree, development_private = (
        _private_anchor_binding(
            selected,
            git,
            authority_module,
            resolved.development.stage_input,
            "development",
        )
    )
    locked_private_commit, locked_private_tree, locked_private = (
        _private_anchor_binding(
            selected,
            git,
            authority_module,
            resolved.stage_input,
            "locked",
        )
    )
    bindings = (
        (
            selected.main,
            resolved.authorization_anchor_commit,
            resolved.authorization_anchor_tree,
        ),
        (
            selected.development_input,
            resolved.development.stage_input.assessor_vault_commit,
            resolved.development.stage_input.assessor_vault_tree,
        ),
        (
            selected.development_private,
            development_private_commit,
            development_private_tree,
        ),
        (
            selected.development_candidate,
            resolved.development.candidate_run.vault_commit,
            resolved.development.candidate_run.vault_tree,
        ),
        (
            selected.development_output,
            development_decision_commit,
            development_decision_tree,
        ),
        (
            selected.locked_input,
            resolved.stage_input.assessor_vault_commit,
            resolved.stage_input.assessor_vault_tree,
        ),
        (
            selected.locked_private,
            locked_private_commit,
            locked_private_tree,
        ),
        (
            selected.locked_candidate,
            resolved.candidate_run.vault_commit,
            resolved.candidate_run.vault_tree,
        ),
        (
            selected.locked_output,
            resolved.final_connection_commit,
            resolved.final_connection_tree,
        ),
    )
    if (
        resolved.authorization_anchor_commit != c6_commit
        or resolved.authorization_anchor_tree != c6_tree
    ):
        raise FinalVerificationError("resolved C6 authority differs from main HEAD")
    for repository, commit, tree in bindings:
        _require_bound_head(git, repository, commit, tree)
    _verify_private_repository(
        git,
        selected.development_private,
        development_private_commit,
        development_private_tree,
        development_private,
        "development",
    )
    _verify_private_repository(
        git,
        selected.locked_private,
        locked_private_commit,
        locked_private_tree,
        locked_private,
        "locked",
    )
    if _git_text(git, selected.main, "branch", "--show-current") != "main":
        raise FinalVerificationError("main branch changed during final verification")

    allowed = resolved.product_connection_allowed
    if not isinstance(allowed, bool):
        raise FinalVerificationError(
            "terminal product-connection result is not boolean"
        )
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "card_sha256": CARD_SHA256,
        "c6_final_connection_anchor_commit": c6_commit,
        "c6_final_connection_anchor_sha256": (
            resolved.authorization_anchor_file.sha256
        ),
        "final_connection_commit": resolved.final_connection_commit,
        "final_connection_sha256": resolved.final_connection_file.sha256,
        "product_connection_allowed": allowed,
        "terminal_closure": True,
        "rerun_permitted": False,
    }
    payload = authority_module.canonical_bytes(summary)
    return payload


def _verify_formal_invocation(argv: list[str]) -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
    ):
        raise FinalVerificationError(
            "formal final verification requires exact Python flags -I -B -S"
        )
    if len(argv) != 1:
        raise FinalVerificationError(
            "usage: python -I -B -S verify_final_authorization.py"
        )
    try:
        script = Path(argv[0]).resolve(strict=True)
        cwd = Path.cwd().resolve(strict=True)
    except OSError as error:
        raise FinalVerificationError("formal CLI path resolution failed") from error
    if script != Path(__file__).resolve(strict=True):
        raise FinalVerificationError("formal CLI script path differs")
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if not isinstance(main_file, str) or Path(main_file).resolve(strict=True) != script:
        raise FinalVerificationError(
            "formal final verification must execute this script directly"
        )
    if not os.path.samefile(cwd, REPOSITORY_ROOT):
        raise FinalVerificationError("formal CLI cwd must be the main repository root")
    _verify_preimport_hygiene()


def main(argv: list[str] | None = None) -> int:
    _verify_formal_invocation(list(sys.argv if argv is None else argv))
    _activate_formal_import_paths()
    payload = verify()
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FinalVerificationError as error:
        print(f"formal-final-verification-failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
