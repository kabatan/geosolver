"""Terminal one-shot materializer for EXP-LOCAL-003 locked inputs.

This file is C0 protocol source.  Importing it has no side effect and its CLI
must not be invoked before the development candidate process has exited, its
raw output and assessor authorities have been sealed in the private vault, and
the external C3 authority anchor has been committed.  The first mutation made
by :func:`materialize` is an exclusive durable attempt claim.  Every later
failure is terminal; there is no force, resume, replacement, or output option.

The candidate-visible selection is intentionally only the selected variant.
Development assessment/decision hashes remain outside the candidate process
and are cross-bound to that minimal artifact by the external locked anchor.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import re
import stat
import struct
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


# Invalid non-``-B`` invocations still must not create project bytecode before
# the formal entry point can durably claim and reject them.  ``sys.flags``
# remains unchanged, so :func:`_verify_formal_python_invocation` can prove the
# caller actually supplied the frozen interpreter flags.
sys.dont_write_bytecode = True


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
SOURCE_ROOT = EXPERIMENT_ROOT / "source"
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
for _source_path in (PYTHON_SOURCE, SOURCE_ROOT):
    if str(_source_path) not in sys.path:
        sys.path.insert(0, str(_source_path))

from geotarget.canonical import canonical_bytes, canonical_hash  # noqa: E402
from durable_io import durable_write, exclusive_write  # noqa: E402


CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"
CARD_PATH = EXPERIMENT_ROOT.parent / "EXP-LOCAL-003.json"
PREIMPLEMENTATION_LOCK_PATH = EXPERIMENT_ROOT / "preimplementation-lock.json"

ASSESSOR_VAULT_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-vault")
    / "EXP-LOCAL-003"
    / "development-assessor-vault"
)
PRIVATE_VAULT_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-private-audit")
    / "EXP-LOCAL-003"
    / "development-generator-private-vault"
)
STAGE_ANCHOR_PATH = EXPERIMENT_ROOT / "C1_STAGE_VAULT_ANCHOR.json"
PRIVATE_AUDIT_ANCHOR_PATH = EXPERIMENT_ROOT / "C1_PRIVATE_AUDIT_ANCHOR.json"
DEVELOPMENT_AUTHORIZATION_ANCHOR_PATH = (
    EXPERIMENT_ROOT / "C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json"
)
DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-run-evidence")
    / "EXP-LOCAL-003"
    / "development-candidate-run"
)
DEVELOPMENT_ASSESSOR_OUTPUT_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-assessment-evidence")
    / "EXP-LOCAL-003"
    / "development-assessor-output"
)
LOCKED_CANDIDATE_EVIDENCE_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-run-evidence")
    / "EXP-LOCAL-003"
    / "locked-candidate-run"
)
LOCKED_ASSESSOR_OUTPUT_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-assessment-evidence")
    / "EXP-LOCAL-003"
    / "locked-assessor-output"
)
DEVELOPMENT_EXECUTION_LOCK_PATH = EXPERIMENT_ROOT / "candidate-execution-lock.json"

ATTEMPT_PATH = EXPERIMENT_ROOT / "LOCKED_ATTEMPT_CLAIM.json"
FAILURE_PATH = EXPERIMENT_ROOT / "LOCKED_TERMINAL_FAILURE.json"
LOCKED_STAGE_ANCHOR_PATH = EXPERIMENT_ROOT / "C4_LOCKED_STAGE_VAULT_ANCHOR.json"
LOCKED_PRIVATE_ANCHOR_PATH = EXPERIMENT_ROOT / "C4_LOCKED_PRIVATE_AUDIT_ANCHOR.json"
CANDIDATE_OUTPUT_PATH = EXPERIMENT_ROOT / "locked-candidate-inputs"
CANDIDATE_STAGING_PATH = EXPERIMENT_ROOT / ".locked-candidate-inputs.partial"
LOCKED_ASSESSOR_VAULT_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-vault")
    / "EXP-LOCAL-003"
    / "locked-assessor-vault"
)
LOCKED_PRIVATE_VAULT_ROOT = (
    REPOSITORY_ROOT.with_name(f"{REPOSITORY_ROOT.name}-private-audit")
    / "EXP-LOCAL-003"
    / "locked-generator-private-vault"
)
ASSESSOR_VAULT_OUTPUT_PATH = LOCKED_ASSESSOR_VAULT_ROOT
ASSESSOR_VAULT_STAGING_PATH = LOCKED_ASSESSOR_VAULT_ROOT.with_name(
    f".{LOCKED_ASSESSOR_VAULT_ROOT.name}-staging.partial"
)
PRIVATE_VAULT_OUTPUT_PATH = LOCKED_PRIVATE_VAULT_ROOT
PRIVATE_VAULT_STAGING_PATH = LOCKED_PRIVATE_VAULT_ROOT.with_name(
    f".{LOCKED_PRIVATE_VAULT_ROOT.name}-staging.partial"
)
COMPLETION_NAME = "ONE_SHOT_COMPLETE.json"

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
LOCKED_SOURCE_GROUPS = (2, 3, 4, 5)
LOCKED_GROUP_INDEX_MAP = {2: 0, 3: 1, 4: 2, 5: 3}
LOCKED_CASE_COUNT = 96
FORBIDDEN_MECHANISM_PATHS = (
    "julia/GeoTargetCore/src/local_model_transform.jl",
    "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl",
    "julia/GeoTargetCore/test/test_local_model_transform.jl",
    "research/experiments/EXP-LOCAL-003/C2_L0_DEFAULT_EQUIVALENCE.json",
    "research/experiments/EXP-LOCAL-003/candidate-execution-lock.json",
    "research/experiments/EXP-LOCAL-003/locked-candidate-execution-lock.json",
    "research/experiments/EXP-LOCAL-003/development-candidate-inputs",
)
C2_REQUIRED_SOURCE_PATHS = frozenset(FORBIDDEN_MECHANISM_PATHS[:2])
C2_TEST_SOURCE_PATHS = frozenset(FORBIDDEN_MECHANISM_PATHS[2:3])
C2_POST_C0_SOURCE_PATHS = C2_REQUIRED_SOURCE_PATHS | C2_TEST_SOURCE_PATHS
C0_CLOSED_TREE_ROOTS = (
    SOURCE_ROOT,
    REPOSITORY_ROOT / "schemas",
    REPOSITORY_ROOT / "python" / "src" / "geotarget",
    REPOSITORY_ROOT / "julia" / "GeoTargetBase" / "src",
    REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "src",
    REPOSITORY_ROOT / "julia" / "GeoTargetGeometry" / "src",
)
EXPECTED_CANDIDATE_FILES = {
    "ONE_SHOT_COMPLETE.json",
    "locked-candidate-inputs.json.gz",
    "locked-selection.json",
    "manifest.json",
    "plugin/Local3FixturePlugin.jl",
}
EXPECTED_ASSESSOR_PUBLICATION_FILES = {
    "ONE_SHOT_COMPLETE.json",
    "assessor/locked-assessor-truth.json.gz",
    "assessor/locked-bootstrap-indices.bin",
    "assessor/manifest.json",
    "manifest.json",
}
EXPECTED_PRIVATE_PUBLICATION_FILES = {
    "ONE_SHOT_COMPLETE.json",
    "generator-private/locked-calibration-capture.json.gz",
    "generator-private/locked-generator-assessor-projection.json.gz",
    "generator-private/locked-generator-private.json.gz",
    "generator-private/manifest.json",
    "manifest.json",
}
EXPECTED_DEVELOPMENT_PRIVATE_FILES = {
    "ONE_SHOT_COMPLETE.json",
    "generator-private/development-calibration-capture.json.gz",
    "generator-private/development-generator-assessor-projection.json.gz",
    "generator-private/development-generator-private.json.gz",
    "generator-private/manifest.json",
    "manifest.json",
}
LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_PINNED_GIT: Path | None = None

DECISION_FIELDS = {
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
FORMAL_LOCKED_DECISION_FIELDS = {
    "candidate_id",
    "development_path",
    "development_assessment_sha256",
    "development_decision_record_sha256",
}
SELECTION_FIELDS = {
    "schema_version",
    "experiment_id",
    "card_sha256",
    "stage",
    "selected_variant",
    "candidate_input_sha256",
}


class LockedMaterializationError(RuntimeError):
    """A one-shot authorization, authority, or publication invariant failed."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as error:
        raise LockedMaterializationError(f"cannot hash {path}: {error}") from error


def _raw_canonical_hash(value: Any) -> str:
    digest = canonical_hash(value)
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise LockedMaterializationError("canonical hash implementation drift")
    raw = digest.removeprefix("sha256:")
    if LOWER_SHA256.fullmatch(raw) is None:
        raise LockedMaterializationError("canonical hash is not lowercase SHA-256")
    return raw


def _strict_json_bytes(payload: bytes, *, context: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant {value}")

    def reject_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    try:
        document = json.loads(
            payload.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise LockedMaterializationError(f"invalid {context}: {error}") from error
    try:
        if canonical_bytes(document) != payload:
            raise LockedMaterializationError(f"{context} is not exact RFC 8785 JCS")
    except (TypeError, ValueError) as error:
        raise LockedMaterializationError(f"non-canonical {context}: {error}") from error
    return document


def _load_jcs(path: Path, *, context: str) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise LockedMaterializationError(f"cannot read {context}: {error}") from error
    document = _strict_json_bytes(payload, context=context)
    if not isinstance(document, dict):
        raise LockedMaterializationError(f"{context} is not a JSON object")
    return document


def _load_gzip_jcs(path: Path, *, context: str) -> dict[str, Any]:
    try:
        compressed = path.read_bytes()
        payload = gzip.decompress(compressed)
    except (OSError, EOFError, gzip.BadGzipFile) as error:
        raise LockedMaterializationError(f"cannot read {context}: {error}") from error
    document = _strict_json_bytes(payload, context=context)
    if not isinstance(document, dict):
        raise LockedMaterializationError(f"{context} is not a JSON object")
    return document


def _exclusive_write_json(path: Path, document: Any) -> None:
    try:
        exclusive_write(path, canonical_bytes(document))
    except OSError as error:
        raise LockedMaterializationError(
            f"exclusive authority creation failed for {path}: {error}"
        ) from error


def _write_json(path: Path, document: Any) -> None:
    durable_write(path, canonical_bytes(document))


def _pinned_git() -> Path:
    global _PINNED_GIT
    if _PINNED_GIT is not None:
        return _PINNED_GIT
    environment_path = EXPERIMENT_ROOT / "environment-lock.json"
    document = _load_jcs(environment_path, context="environment lock Git bootstrap")
    tools = document.get("tools")
    if not isinstance(tools, dict):
        raise LockedMaterializationError("environment lock has no tools record")
    path_value = tools.get("git_executable")
    digest = tools.get("git_sha256")
    if not isinstance(path_value, str) or not isinstance(digest, str):
        raise LockedMaterializationError("environment lock Git identity is malformed")
    path = Path(path_value)
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise LockedMaterializationError("pinned Git executable is unavailable")
    if LOWER_SHA256.fullmatch(digest) is None or _sha256_path(path) != digest:
        raise LockedMaterializationError("pinned Git executable hash drift")
    _PINNED_GIT = path
    return path


def _closed_git_environment(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment = {
        "SystemRoot": str(system_root),
        "WINDIR": str(system_root),
        "COMSPEC": str(system_root / "System32" / "cmd.exe"),
        "PATH": os.pathsep.join(
            (str(_pinned_git().parent), str(system_root / "System32"))
        ),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for name in ("TEMP", "TMP"):
        if value := os.environ.get(name):
            environment[name] = value
    if extra is not None:
        environment.update(extra)
    return environment


def _git_command(root: Path, arguments: tuple[str, ...]) -> list[str]:
    dot_git = root / ".git"
    if not dot_git.is_dir() or dot_git.is_symlink():
        raise LockedMaterializationError(f"Git root is not a direct repository: {root}")
    return [
        str(_pinned_git()),
        "--no-replace-objects",
        f"--git-dir={dot_git}",
        f"--work-tree={root}",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "commit.gpgSign=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.fsync=committed,reference",
        "-c",
        "core.fsyncMethod=fsync",
        "-c",
        f"core.attributesFile={os.devnull}",
        *arguments,
    ]


def _git_run(
    root: Path,
    *arguments: str,
    environment: Mapping[str, str] | None = None,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        _git_command(root, arguments),
        cwd=root,
        env=_closed_git_environment(environment),
        check=False,
        capture_output=True,
        text=text,
    )


def _git(
    root: Path, *arguments: str, environment: Mapping[str, str] | None = None
) -> str:
    completed = _git_run(root, *arguments, environment=environment, text=True)
    if completed.returncode != 0:
        raise LockedMaterializationError(
            f"git {' '.join(arguments)} failed in {root}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = _git_run(
        root, "merge-base", "--is-ancestor", ancestor, descendant, text=True
    )
    if completed.returncode not in (0, 1):
        raise LockedMaterializationError(
            f"Git ancestry check failed: {completed.stderr.strip()}"
        )
    return completed.returncode == 0


def _import_frozen(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise LockedMaterializationError(f"cannot import frozen source {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _refuse_previous_attempt(
    *,
    attempt_path: Path = ATTEMPT_PATH,
    failure_path: Path = FAILURE_PATH,
    stage_anchor_path: Path = LOCKED_STAGE_ANCHOR_PATH,
    private_anchor_path: Path = LOCKED_PRIVATE_ANCHOR_PATH,
    candidate_output: Path = CANDIDATE_OUTPUT_PATH,
    candidate_staging: Path = CANDIDATE_STAGING_PATH,
    assessor_vault_output: Path = ASSESSOR_VAULT_OUTPUT_PATH,
    assessor_vault_staging: Path = ASSESSOR_VAULT_STAGING_PATH,
    private_vault_output: Path = PRIVATE_VAULT_OUTPUT_PATH,
    private_vault_staging: Path = PRIVATE_VAULT_STAGING_PATH,
) -> None:
    evidence = (
        attempt_path,
        failure_path,
        stage_anchor_path,
        private_anchor_path,
        candidate_output,
        candidate_staging,
        assessor_vault_output,
        assessor_vault_staging,
        private_vault_output,
        private_vault_staging,
    )
    existing = [str(path) for path in evidence if path.exists()]
    if existing:
        raise LockedMaterializationError(
            "locked one-shot was already claimed or has residual evidence; "
            f"retry refused: {existing}"
        )


def _claim_locked_attempt(path: Path = ATTEMPT_PATH) -> None:
    """Make the first durable mutation; callers must not perform preflight I/O."""

    _exclusive_write_json(
        path,
        {
            "schema_version": "exp-local-003-locked-attempt-claim/v1",
            "card_sha256": CARD_SHA256,
            "attempt_ordinal": 0,
            "rerun_permitted": False,
            "failure_is_terminal": True,
            "authority_validation_occurs_after_claim": True,
        },
    )


def _verify_locked_attempt_claim(path: Path = ATTEMPT_PATH) -> None:
    expected = {
        "schema_version": "exp-local-003-locked-attempt-claim/v1",
        "card_sha256": CARD_SHA256,
        "attempt_ordinal": 0,
        "rerun_permitted": False,
        "failure_is_terminal": True,
        "authority_validation_occurs_after_claim": True,
    }
    if path.read_bytes() != canonical_bytes(expected):
        raise LockedMaterializationError(
            "locked launcher claim bytes differ from frozen authority"
        )


def _record_terminal_failure(
    error: BaseException,
    *,
    path: Path = FAILURE_PATH,
    attempt_path: Path = ATTEMPT_PATH,
) -> None:
    if path.exists():
        return
    try:
        _exclusive_write_json(
            path,
            {
                "schema_version": "exp-local-003-locked-terminal-failure/v1",
                "card_sha256": CARD_SHA256,
                "attempt_claim_sha256": _sha256_path(attempt_path),
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:1000],
                "rerun_permitted": False,
            },
        )
    except (OSError, LockedMaterializationError):
        # The exclusive claim alone is sufficient to make every retry illegal.
        pass


def _relative_repository_path(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as error:
        raise LockedMaterializationError(
            f"path is outside repository: {path}"
        ) from error


def _verify_repository_after_claim() -> str:
    """Require a committed C3 anchor while allowing only our fresh claim dirty."""

    expected_status = f"?? {_relative_repository_path(ATTEMPT_PATH)}"
    status = _git(REPOSITORY_ROOT, "status", "--porcelain=v1", "--untracked-files=all")
    if status.strip() != expected_status:
        raise LockedMaterializationError(
            "repository must be clean before the locked claim; after claiming, "
            f"only {expected_status!r} is allowed, observed {status!r}"
        )
    if _git(REPOSITORY_ROOT, "branch", "--show-current") != "main":
        raise LockedMaterializationError("formal locked materialization requires main")
    for required_path in (
        STAGE_ANCHOR_PATH,
        PRIVATE_AUDIT_ANCHOR_PATH,
        DEVELOPMENT_AUTHORIZATION_ANCHOR_PATH,
        DEVELOPMENT_EXECUTION_LOCK_PATH,
    ):
        relative = _relative_repository_path(required_path)
        _git(REPOSITORY_ROOT, "ls-files", "--error-unmatch", "--", relative)
    head = _git(REPOSITORY_ROOT, "rev-parse", "HEAD")
    if GIT_OBJECT.fullmatch(head) is None:
        raise LockedMaterializationError("repository HEAD is not a Git object")
    return head


def _verify_formal_python_invocation() -> None:
    required_flags = {
        "isolated": sys.flags.isolated,
        "ignore_environment": sys.flags.ignore_environment,
        "no_user_site": sys.flags.no_user_site,
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "no_site": sys.flags.no_site,
    }
    if any(value != 1 for value in required_flags.values()):
        raise LockedMaterializationError(
            "formal locked entry requires `python -I -B -S materialize_locked.py`; "
            f"observed flags {required_flags}"
        )
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise LockedMaterializationError(
            "formal locked entry working directory must be the repository root"
        )


def _normalized_locked_path(relative: Any, *, context: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or Path(relative).is_absolute()
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise LockedMaterializationError(f"{context} is not a normalized repo path")
    path = REPOSITORY_ROOT.joinpath(*relative.split("/"))
    try:
        path.resolve().relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as error:
        raise LockedMaterializationError(f"{context} escapes the repository") from error
    return path


def _verify_c0_lock_for_locked_stage(
    repository_head: str,
) -> tuple[str, str, frozenset[str]]:
    """Verify every frozen C0 blob while permitting separately locked C2 files."""

    lock = _load_jcs(PREIMPLEMENTATION_LOCK_PATH, context="C0 preimplementation lock")
    required = {
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
    if set(lock) != required:
        raise LockedMaterializationError("C0 preimplementation lock is not closed")
    if lock["schema_version"] != "exp-local-003-preimplementation-lock/v1":
        raise LockedMaterializationError("C0 preimplementation lock schema drift")
    if lock["experiment_id"] != "EXP-LOCAL-003":
        raise LockedMaterializationError("C0 preimplementation lock experiment drift")
    if lock["status"] != "frozen-before-one-shot-development-materialization":
        raise LockedMaterializationError("C0 preimplementation lock status drift")
    if lock["card_sha256"] != CARD_SHA256:
        raise LockedMaterializationError("C0 preimplementation lock card mismatch")
    c0_commit = lock["c0_source_commit"]
    c0_tree = lock["c0_source_tree"]
    if (
        not isinstance(c0_commit, str)
        or GIT_OBJECT.fullmatch(c0_commit) is None
        or not isinstance(c0_tree, str)
        or GIT_OBJECT.fullmatch(c0_tree) is None
    ):
        raise LockedMaterializationError("C0 Git authority is malformed")
    _git(REPOSITORY_ROOT, "cat-file", "-e", f"{c0_commit}^{{commit}}")
    if _git(REPOSITORY_ROOT, "rev-parse", f"{c0_commit}^{{tree}}") != c0_tree:
        raise LockedMaterializationError("C0 source tree does not match C0 commit")
    if not _git_is_ancestor(REPOSITORY_ROOT, c0_commit, repository_head):
        raise LockedMaterializationError("C0 source commit is not an ancestor of C3")

    files = lock["files"]
    if not isinstance(files, dict) or not files:
        raise LockedMaterializationError("C0 lock has no frozen file inventory")
    committed_paths = set(
        _git(REPOSITORY_ROOT, "ls-tree", "-r", "--name-only", c0_commit).splitlines()
    )
    fixed_required = {
        "research/experiments/EXP-LOCAL-003.json",
        "research/experiments/EXP-LOCAL-003/visibility-contract.json",
        "research/experiments/EXP-LOCAL-003/numeric-json-domain.json",
        "research/experiments/EXP-LOCAL-003/local-options-contract.json",
        "research/experiments/EXP-LOCAL-003/environment-lock.json",
        "docs/research/EXP-LOCAL-003.md",
        "toolchain.toml",
        ".julia-version",
        ".python-version",
        ".gitattributes",
        "julia/Project.toml",
        "julia/Manifest.toml",
        "python/pyproject.toml",
        "python/uv.lock",
        "julia/GeoTargetBase/Project.toml",
        "julia/GeoTargetCore/Project.toml",
        "julia/GeoTargetGeometry/Project.toml",
    }
    frozen_prefixes = (
        "research/experiments/EXP-LOCAL-003/source/",
        "schemas/",
        "python/src/geotarget/",
        "julia/GeoTargetBase/src/",
        "julia/GeoTargetCore/src/",
        "julia/GeoTargetGeometry/src/",
    )
    expected_files = fixed_required | {
        relative for relative in committed_paths if relative.startswith(frozen_prefixes)
    }
    if set(files) != expected_files:
        raise LockedMaterializationError(
            "C0 frozen file inventory is not the exact required set"
        )
    for relative, digest in files.items():
        path = _normalized_locked_path(relative, context="C0 file path")
        if not isinstance(digest, str) or LOWER_SHA256.fullmatch(digest) is None:
            raise LockedMaterializationError(f"C0 file hash is invalid: {relative}")
        if not path.is_file() or path.is_symlink():
            raise LockedMaterializationError(
                f"frozen C0 file is unavailable: {relative}"
            )
        if _sha256_path(path) != digest:
            raise LockedMaterializationError(f"frozen C0 blob changed: {relative}")
        immutable = _immutable_blob(
            c0_commit,
            path,
            context=f"frozen C0 blob {relative}",
        )
        if _sha256_bytes(immutable) != digest:
            raise LockedMaterializationError(
                f"C0 lock digest differs from source commit blob: {relative}"
            )

    source_files = lock["experiment_source_files"]
    if (
        not isinstance(source_files, list)
        or source_files != sorted(source_files)
        or len(source_files) != len(set(source_files))
    ):
        raise LockedMaterializationError("C0 experiment source inventory is malformed")
    source_prefix = SOURCE_ROOT.relative_to(REPOSITORY_ROOT).as_posix() + "/"
    declared_source_files = {
        relative for relative in files if relative.startswith(source_prefix)
    }
    if set(source_files) != declared_source_files:
        raise LockedMaterializationError(
            "C0 experiment source inventory differs from frozen blobs"
        )
    if lock["forbidden_mechanism_paths"] != list(FORBIDDEN_MECHANISM_PATHS):
        raise LockedMaterializationError("C0 forbidden-mechanism path contract drift")
    critical = {
        f"{source_prefix}{name}"
        for name in (
            "Local3FixturePlugin.jl",
            "assessor.py",
            "authority.py",
            "bootstrap_indices.py",
            "capture_calibration_truth.jl",
            "generator.py",
            "materialize_development.py",
            "materialize_locked.py",
        )
    }
    if not critical <= set(files):
        raise LockedMaterializationError(
            f"C0 lock omits locked-stage critical blobs: {sorted(critical - set(files))}"
        )
    for digest_field in ("environment_lock_sha256", "local_options_sha256"):
        digest = lock[digest_field]
        if not isinstance(digest, str) or LOWER_SHA256.fullmatch(digest) is None:
            raise LockedMaterializationError(f"C0 {digest_field} is invalid")
    environment_path = EXPERIMENT_ROOT / "environment-lock.json"
    if lock["environment_lock_sha256"] != _sha256_path(environment_path):
        raise LockedMaterializationError("C0 environment-lock digest drift")

    relative_lock = _relative_repository_path(PREIMPLEMENTATION_LOCK_PATH)
    _git(REPOSITORY_ROOT, "ls-files", "--error-unmatch", "--", relative_lock)
    lock_commit = _git(
        REPOSITORY_ROOT,
        "log",
        "-1",
        "--format=%H",
        "--",
        relative_lock,
    )
    if GIT_OBJECT.fullmatch(lock_commit) is None:
        raise LockedMaterializationError("C0 lock introduction commit is invalid")
    if _git(REPOSITORY_ROOT, "rev-parse", f"{lock_commit}^") != c0_commit:
        raise LockedMaterializationError(
            "C0 lock introduction parent differs from frozen C0 source commit"
        )
    changed_paths = set(
        _git(
            REPOSITORY_ROOT,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            lock_commit,
        ).splitlines()
    )
    if changed_paths != {relative_lock}:
        raise LockedMaterializationError(
            "C0 lock introduction commit changed files other than the lock"
        )
    if not _git_is_ancestor(REPOSITORY_ROOT, lock_commit, repository_head):
        raise LockedMaterializationError(
            "C0 lock introduction commit is not an ancestor of C3"
        )
    introduction_document = _strict_json_bytes(
        _git(REPOSITORY_ROOT, "show", f"{lock_commit}:{relative_lock}").encode("utf-8"),
        context="introduced C0 preimplementation lock",
    )
    if introduction_document != lock:
        raise LockedMaterializationError(
            "C0 lock changed after its introduction commit"
        )
    committed = _strict_json_bytes(
        _git(REPOSITORY_ROOT, "show", f"HEAD:{relative_lock}").encode("utf-8"),
        context="committed C0 preimplementation lock",
    )
    if committed != lock:
        raise LockedMaterializationError("working C0 lock differs from committed HEAD")
    return (
        lock_commit,
        _sha256_path(PREIMPLEMENTATION_LOCK_PATH),
        frozenset(files),
    )


def _verify_c2_source_extras(
    frozen_c0_files: frozenset[str],
    execution_lock: Mapping[str, Any],
    *,
    execution_lock_commit: str,
) -> None:
    """Allow post-C0 source only through the sealed C2 execution allowlist."""

    records = execution_lock.get("allowed_sources")
    if not isinstance(records, list) or not records:
        raise LockedMaterializationError("development execution lock has no sources")
    allowed: dict[str, str] = {}
    normalized_records: list[dict[str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise LockedMaterializationError(
                f"development execution source {index} is malformed"
            )
        relative = record["path"]
        digest = record["sha256"]
        _normalized_locked_path(relative, context="development execution source")
        if not isinstance(digest, str) or LOWER_SHA256.fullmatch(digest) is None:
            raise LockedMaterializationError(
                "development execution source hash is invalid"
            )
        if relative in allowed:
            raise LockedMaterializationError(
                "development execution source is duplicated"
            )
        path = REPOSITORY_ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise LockedMaterializationError(
                f"development execution source is unavailable: {relative}"
            )
        if _sha256_path(path) != digest:
            raise LockedMaterializationError(
                f"development execution source hash drift: {relative}"
            )
        immutable = _immutable_blob(
            execution_lock_commit,
            path,
            context=f"C2 execution source {relative}",
        )
        if _sha256_bytes(immutable) != digest:
            raise LockedMaterializationError(
                f"C2 source is not bound by execution-lock commit: {relative}"
            )
        allowed[relative] = digest
        normalized_records.append({"path": relative, "sha256": digest})
    if normalized_records != sorted(normalized_records, key=lambda item: item["path"]):
        raise LockedMaterializationError("development execution sources are not sorted")
    if execution_lock.get("source_manifest_sha256") != _sha256_bytes(
        canonical_bytes(normalized_records)
    ):
        raise LockedMaterializationError("development execution source manifest drift")
    runner_path = execution_lock.get("runner_source_path")
    runner_sha = execution_lock.get("runner_source_sha256")
    if allowed.get(runner_path) != runner_sha:
        raise LockedMaterializationError("development runner is not source-bound")
    if set(allowed) != C2_REQUIRED_SOURCE_PATHS:
        raise LockedMaterializationError(
            "development execution lock runtime source set differs: "
            f"expected={sorted(C2_REQUIRED_SOURCE_PATHS)}, observed={sorted(allowed)}"
        )
    cache_paths = [
        path
        for root in C0_CLOSED_TREE_ROOTS
        for path in root.rglob("*")
        if path.is_file() and ("__pycache__" in path.parts or path.suffix == ".pyc")
    ]
    if cache_paths:
        raise LockedMaterializationError(
            f"formal source tree contains Python cache artifacts: {cache_paths}"
        )
    current_source_files = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for root in C0_CLOSED_TREE_ROOTS
        for path in root.rglob("*")
        if path.is_file()
    }
    extras = current_source_files - set(frozen_c0_files)
    expected_extras = (set(C2_POST_C0_SOURCE_PATHS) & current_source_files) - set(
        frozen_c0_files
    )
    for relative in expected_extras:
        path = REPOSITORY_ROOT / relative
        immutable = _immutable_blob(
            execution_lock_commit,
            path,
            context=f"C2 post-C0 source {relative}",
        )
        if immutable != path.read_bytes():
            raise LockedMaterializationError(
                f"C2 post-C0 source changed after C2: {relative}"
            )
    if extras != expected_extras:
        raise LockedMaterializationError(
            "post-C0 experiment source differs from the frozen C2 set: "
            f"unbound={sorted(extras - expected_extras)}, "
            f"stale={sorted(expected_extras - extras)}"
        )


def _immutable_blob(commit: str, path: Path, *, context: str) -> bytes:
    relative = _relative_repository_path(path)
    completed = _git_run(REPOSITORY_ROOT, "show", f"{commit}:{relative}", text=False)
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise LockedMaterializationError(f"cannot resolve {context}: {message}")
    return bytes(completed.stdout)


def _introduction_commit(path: Path, descendant: str) -> str:
    relative = _relative_repository_path(path)
    commit = _git(
        REPOSITORY_ROOT,
        "log",
        "-1",
        "--diff-filter=A",
        "--format=%H",
        descendant,
        "--",
        relative,
    )
    if GIT_OBJECT.fullmatch(commit) is None:
        raise LockedMaterializationError(f"path has no introduction commit: {relative}")
    return commit


def _verify_private_audit_anchor(
    *,
    repository_head: str,
    stage_anchor_commit: str,
    stage_anchor_sha256: str,
    source_lock_commit: str,
) -> tuple[str, str, str]:
    """Resolve the audit-only C1 private anchor from its introduction commit."""

    commit = _introduction_commit(PRIVATE_AUDIT_ANCHOR_PATH, repository_head)
    if commit != stage_anchor_commit:
        raise LockedMaterializationError(
            "C1 private and formal anchors were not introduced atomically"
        )
    if not _git_is_ancestor(REPOSITORY_ROOT, commit, repository_head):
        raise LockedMaterializationError("C1 private-audit anchor is not in main")
    payload = _immutable_blob(
        commit, PRIVATE_AUDIT_ANCHOR_PATH, context="C1 private-audit anchor"
    )
    current_payload = _immutable_blob(
        repository_head,
        PRIVATE_AUDIT_ANCHOR_PATH,
        context="current C1 private-audit anchor",
    )
    if payload != current_payload:
        raise LockedMaterializationError(
            "C1 private-audit anchor changed after creation"
        )
    anchor = _strict_json_bytes(payload, context="C1 private-audit anchor")
    if not isinstance(anchor, dict):
        raise LockedMaterializationError("C1 private-audit anchor is not an object")
    required = {
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
    if set(anchor) != required:
        raise LockedMaterializationError("C1 private-audit anchor is not closed")
    if (
        anchor["schema_version"]
        != "geotarget.exp-local-003.generator-private-vault-anchor/v1"
        or anchor["experiment_id"] != "EXP-LOCAL-003"
        or anchor["card_sha256"] != CARD_SHA256
        or anchor["stage"] != "development"
        or anchor["source_lock_commit"] != source_lock_commit
        or anchor["candidate_visible"] is not False
        or anchor["formal_assessor_input"] is not False
        or anchor["rerun_permitted"] is not False
    ):
        raise LockedMaterializationError("C1 private-audit anchor identity drift")
    if anchor["stage_vault_anchor_sha256"] != stage_anchor_sha256:
        raise LockedMaterializationError(
            "C1 private-audit anchor does not bind formal stage anchor"
        )
    for field in (
        "materialization_attempt_claim_sha256",
        "stage_vault_anchor_sha256",
        "generator_private_vault_manifest_sha256",
        "generator_private_vault_completion_sha256",
        "generator_private_manifest_sha256",
        "candidate_manifest_sha256",
    ):
        if (
            not isinstance(anchor[field], str)
            or LOWER_SHA256.fullmatch(anchor[field]) is None
        ):
            raise LockedMaterializationError(f"C1 private anchor {field} is invalid")
    stage_blob = _immutable_blob(
        commit, STAGE_ANCHOR_PATH, context="C1 formal stage anchor"
    )
    if _sha256_bytes(stage_blob) != stage_anchor_sha256:
        raise LockedMaterializationError(
            "private anchor/formal stage anchor split drift"
        )
    claim_blob = _immutable_blob(
        commit,
        EXPERIMENT_ROOT / "C1_ATTEMPT_CLAIM.json",
        context="C1 attempt claim",
    )
    if _sha256_bytes(claim_blob) != anchor["materialization_attempt_claim_sha256"]:
        raise LockedMaterializationError("C1 private anchor attempt binding drift")
    candidate_manifest_blob = _immutable_blob(
        commit,
        EXPERIMENT_ROOT / "development-candidate-inputs" / "manifest.json",
        context="C1 candidate manifest",
    )
    if _sha256_bytes(candidate_manifest_blob) != anchor["candidate_manifest_sha256"]:
        raise LockedMaterializationError("C1 private anchor candidate binding drift")
    private_commit = anchor["generator_private_vault_git_commit"]
    private_tree = anchor["generator_private_vault_git_tree"]
    if (
        not isinstance(private_commit, str)
        or GIT_OBJECT.fullmatch(private_commit) is None
        or not isinstance(private_tree, str)
        or GIT_OBJECT.fullmatch(private_tree) is None
    ):
        raise LockedMaterializationError("C1 private vault Git identity is invalid")
    for other in (REPOSITORY_ROOT, ASSESSOR_VAULT_ROOT):
        try:
            if os.path.samefile(PRIVATE_VAULT_ROOT, other):
                raise LockedMaterializationError(
                    "generator-private vault is not physically separate"
                )
        except FileNotFoundError as error:
            raise LockedMaterializationError(
                f"authority repository missing: {error}"
            ) from error
    private_objects = PRIVATE_VAULT_ROOT / ".git" / "objects"
    if (private_objects / "info" / "alternates").exists():
        raise LockedMaterializationError("generator-private object DB uses alternates")
    for other in (REPOSITORY_ROOT, ASSESSOR_VAULT_ROOT):
        other_objects = other / ".git" / "objects"
        try:
            if os.path.samefile(private_objects, other_objects):
                raise LockedMaterializationError(
                    "generator-private vault shares a Git object database"
                )
        except FileNotFoundError as error:
            raise LockedMaterializationError(
                f"Git object database missing: {error}"
            ) from error
    if _git(PRIVATE_VAULT_ROOT, "status", "--porcelain=v1", "--untracked-files=all"):
        raise LockedMaterializationError("C1 generator-private vault is dirty")
    if _git(PRIVATE_VAULT_ROOT, "rev-parse", "HEAD") != private_commit:
        raise LockedMaterializationError("C1 private anchor does not bind private HEAD")
    if _git(PRIVATE_VAULT_ROOT, "rev-parse", "HEAD^{tree}") != private_tree:
        raise LockedMaterializationError("C1 private anchor does not bind private tree")
    if _git(
        PRIVATE_VAULT_ROOT, "rev-list", "--parents", "-n", "1", private_commit
    ).split() != [private_commit]:
        raise LockedMaterializationError(
            "C1 private vault is not an orphan root commit"
        )
    paths = set(
        _git(
            PRIVATE_VAULT_ROOT, "ls-tree", "-r", "--name-only", private_commit
        ).splitlines()
    )
    if paths != EXPECTED_DEVELOPMENT_PRIVATE_FILES:
        raise LockedMaterializationError("C1 private vault immutable file set drift")
    expected_hashes = {
        "generator_private_vault_manifest_sha256": "manifest.json",
        "generator_private_vault_completion_sha256": COMPLETION_NAME,
        "generator_private_manifest_sha256": "generator-private/manifest.json",
    }
    for field, relative in expected_hashes.items():
        blob = _git_run(
            PRIVATE_VAULT_ROOT,
            "show",
            f"{private_commit}:{relative}",
            text=False,
        )
        if blob.returncode != 0 or _sha256_bytes(bytes(blob.stdout)) != anchor[field]:
            raise LockedMaterializationError(
                f"C1 private anchor hash mismatch: {field}"
            )
    return private_commit, private_tree, _sha256_bytes(payload)


def _resolve_development_authorization(
    authority_module: ModuleType,
    assessor_module: ModuleType,
    *,
    authorization_anchor_commit: str,
) -> Any:
    """Resolve the four-repository, typed C1 -> C2 -> C3 authority chain."""

    resolve = getattr(authority_module, "resolve_development_authorization", None)
    pin_git = getattr(authority_module, "pin_git_executable", None)
    assess = getattr(assessor_module, "assess", None)
    build_decision = getattr(assessor_module, "build_development_decision_record", None)
    if not all(callable(item) for item in (resolve, pin_git, assess, build_decision)):
        raise LockedMaterializationError(
            "frozen authority/assessor modules lack the C3 resolver API"
        )
    try:
        git_executable = pin_git(_pinned_git(), _sha256_path(_pinned_git()))
        authorization = resolve(
            REPOSITORY_ROOT,
            ASSESSOR_VAULT_ROOT,
            DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT,
            DEVELOPMENT_ASSESSOR_OUTPUT_ROOT,
            authorization_anchor_commit=authorization_anchor_commit,
            assess=assess,
            build_development_decision=build_decision,
            git_executable=git_executable,
        )
    except Exception as error:
        raise LockedMaterializationError(
            f"development authorization resolution failed: {error}"
        ) from error
    required_attributes = (
        "authorization_anchor_commit",
        "authorization_anchor_file",
        "stage_input",
        "candidate_run",
        "assessor_output",
    )
    if any(not hasattr(authorization, name) for name in required_attributes):
        raise LockedMaterializationError(
            "development authorization is not the frozen typed record"
        )
    if authorization.authorization_anchor_commit != authorization_anchor_commit:
        raise LockedMaterializationError("resolved C3 authorization commit drift")
    authorization_file = authorization.authorization_anchor_file
    if (
        getattr(authorization_file, "path", None)
        != _relative_repository_path(DEVELOPMENT_AUTHORIZATION_ANCHOR_PATH)
        or LOWER_SHA256.fullmatch(getattr(authorization_file, "sha256", "")) is None
    ):
        raise LockedMaterializationError("C3 authorization anchor identity drift")
    stage_input = authorization.stage_input
    if getattr(stage_input, "stage", None) != "development":
        raise LockedMaterializationError("resolved stage input is not development")
    anchor_file = getattr(stage_input, "anchor_file", None)
    if (
        anchor_file is None
        or getattr(anchor_file, "path", None)
        != _relative_repository_path(STAGE_ANCHOR_PATH)
        or LOWER_SHA256.fullmatch(getattr(anchor_file, "sha256", "")) is None
    ):
        raise LockedMaterializationError("development stage-input identity drift")
    return authorization


def _direct_repository_object_database(root: Path) -> Path:
    """Return one non-alternating direct repository's physical object DB."""

    if not root.is_dir():
        raise LockedMaterializationError(
            f"development authority repository is unavailable: {root}"
        )
    _reject_reparse_ancestry(root)
    dot_git = root / ".git"
    if not dot_git.is_dir() or _is_link_or_reparse(dot_git):
        raise LockedMaterializationError(
            f"development authority repository is not direct: {root}"
        )
    objects = dot_git / "objects"
    if not objects.is_dir():
        raise LockedMaterializationError(
            f"development authority object database is unavailable: {root}"
        )
    _reject_reparse_ancestry(objects)
    for name in ("alternates", "http-alternates"):
        if (objects / "info" / name).exists():
            raise LockedMaterializationError(
                f"development authority repository uses object alternates: {root}"
            )
    return objects.resolve(strict=True)


def _verify_repository_paths_are_separate(paths: tuple[Path, ...]) -> None:
    """Reject aliases and nesting across current and future authority roots."""

    resolved: list[Path] = []
    for path in paths:
        _reject_reparse_ancestry(path)
        resolved.append(path.resolve(strict=False))
    for index, left in enumerate(resolved):
        left_key = os.path.normcase(str(left))
        for right in resolved[index + 1 :]:
            right_key = os.path.normcase(str(right))
            try:
                common = os.path.normcase(os.path.commonpath((left, right)))
            except ValueError:
                continue
            if left_key == right_key or common in (left_key, right_key):
                raise LockedMaterializationError(
                    "main/development/private/locked authority roots overlap"
                )


def _verify_bound_development_repositories(authorization: Any) -> None:
    """Pin all three C3 external HEADs before locked entropy is requested."""

    stage_input = authorization.stage_input
    candidate_run = authorization.candidate_run
    assessor_output = authorization.assessor_output
    decision_commit = assessor_output.decision_commit
    decision_tree = assessor_output.decision_tree
    bindings = (
        (
            ASSESSOR_VAULT_ROOT,
            stage_input.assessor_vault_commit,
            stage_input.assessor_vault_tree,
            "development assessor-input vault",
        ),
        (
            DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT,
            candidate_run.vault_commit,
            candidate_run.vault_tree,
            "development candidate evidence",
        ),
        (
            DEVELOPMENT_ASSESSOR_OUTPUT_ROOT,
            decision_commit,
            decision_tree,
            "development assessor output",
        ),
    )
    for _root, commit, tree, context in bindings:
        if (
            not isinstance(commit, str)
            or GIT_OBJECT.fullmatch(commit) is None
            or not isinstance(tree, str)
            or GIT_OBJECT.fullmatch(tree) is None
        ):
            raise LockedMaterializationError(f"{context} typed Git identity is invalid")

    future_roots = (
        LOCKED_ASSESSOR_VAULT_ROOT,
        ASSESSOR_VAULT_STAGING_PATH,
        LOCKED_PRIVATE_VAULT_ROOT,
        PRIVATE_VAULT_STAGING_PATH,
        LOCKED_CANDIDATE_EVIDENCE_ROOT,
        LOCKED_CANDIDATE_EVIDENCE_ROOT.with_name(
            f".{LOCKED_CANDIDATE_EVIDENCE_ROOT.name}-staging.partial"
        ),
        LOCKED_ASSESSOR_OUTPUT_ROOT,
        LOCKED_ASSESSOR_OUTPUT_ROOT.with_name(
            f".{LOCKED_ASSESSOR_OUTPUT_ROOT.name}-staging.partial"
        ),
    )
    for path in future_roots:
        if path.exists():
            raise LockedMaterializationError(
                f"future locked authority repository already exists: {path}"
            )
    _verify_repository_paths_are_separate(
        (
            REPOSITORY_ROOT,
            ASSESSOR_VAULT_ROOT,
            PRIVATE_VAULT_ROOT,
            DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT,
            DEVELOPMENT_ASSESSOR_OUTPUT_ROOT,
            *future_roots,
        )
    )

    existing_roots = (
        REPOSITORY_ROOT,
        ASSESSOR_VAULT_ROOT,
        PRIVATE_VAULT_ROOT,
        DEVELOPMENT_CANDIDATE_EVIDENCE_ROOT,
        DEVELOPMENT_ASSESSOR_OUTPUT_ROOT,
    )
    object_databases = [
        _direct_repository_object_database(root) for root in existing_roots
    ]
    for index, left in enumerate(object_databases):
        for right in object_databases[index + 1 :]:
            if os.path.samefile(left, right):
                raise LockedMaterializationError(
                    "development authority repositories share an object database"
                )

    for root, expected_commit, expected_tree, context in bindings:
        status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        if status:
            raise LockedMaterializationError(f"{context} worktree is not clean")
        observed_commit = _git(root, "rev-parse", "HEAD")
        observed_tree = _git(root, "rev-parse", "HEAD^{tree}")
        if observed_commit != expected_commit or observed_tree != expected_tree:
            raise LockedMaterializationError(
                f"{context} HEAD/tree differs from the typed C3 authority"
            )


def _authorization_decisions(
    authorization: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project the typed, recomputed authority into the two locked decisions."""

    assessor_output = authorization.assessor_output
    formal = assessor_output.formal
    assessment_jcs = formal.assessment_jcs
    decision_jcs = assessor_output.decision_jcs
    if not isinstance(assessment_jcs, bytes) or not isinstance(decision_jcs, bytes):
        raise LockedMaterializationError("authorization JCS payloads are not bytes")
    assessment = _strict_json_bytes(
        assessment_jcs, context="authorized development assessment"
    )
    decision = _strict_json_bytes(
        decision_jcs, context="authorized development decision"
    )
    if not isinstance(assessment, dict) or not isinstance(decision, dict):
        raise LockedMaterializationError("authorization payloads are not objects")
    assessment_sha = _sha256_bytes(assessment_jcs)
    decision_sha = _sha256_bytes(decision_jcs)
    if (
        assessor_output.assessment_file.sha256 != assessment_sha
        or assessor_output.decision_file is None
        or assessor_output.decision_file.sha256 != decision_sha
        or assessor_output.decision_commit is None
        or decision.get("decision_commit") != assessor_output.assessment_commit
    ):
        raise LockedMaterializationError("typed authorization digest drift")
    if set(decision) != DECISION_FIELDS:
        raise LockedMaterializationError("development decision record is not closed")
    if (
        assessment.get("stage") != "development"
        or assessment.get("stage_passed") is not True
        or assessment.get("global_hard_safety_passed") is not True
        or assessment.get("locked_materialization_eligible") is not True
        or decision.get("development_gate_passed") is not True
    ):
        raise LockedMaterializationError(
            "recomputed development authority does not pass the locked gate"
        )
    safety_count = decision.get("safety16_disagreement_count")
    if (
        not isinstance(safety_count, int)
        or isinstance(safety_count, bool)
        or safety_count < 0
    ):
        raise LockedMaterializationError("development Safety16 count is invalid")
    if (
        decision.get("development_assessment_sha256") != assessment_sha
        or decision.get("candidate_input_sha256")
        != assessment.get("candidate_input_sha256")
        or decision.get("selected_variant") != assessment.get("selected_variant")
        or decision.get("selected_path") != assessment.get("selected_path")
        or safety_count != assessment.get("orthogonal_safety_disagreement_count")
    ):
        raise LockedMaterializationError(
            "development decision does not exactly bind recomputed assessment"
        )
    formal_locked_decision = {
        "candidate_id": decision["selected_variant"],
        "development_path": decision["selected_path"],
        "development_assessment_sha256": assessment_sha,
        "development_decision_record_sha256": decision_sha,
    }
    if set(formal_locked_decision) != FORMAL_LOCKED_DECISION_FIELDS:
        raise AssertionError("internal formal locked-decision field drift")
    canonical_bytes(formal_locked_decision)
    return decision, formal_locked_decision


def _execution_lock_from_authorization(authorization: Any) -> dict[str, Any]:
    candidate = authorization.candidate_run
    commit = candidate.candidate_execution_lock_commit
    payload = candidate.candidate_execution_lock_jcs
    if (
        not isinstance(commit, str)
        or GIT_OBJECT.fullmatch(commit) is None
        or not isinstance(payload, bytes)
    ):
        raise LockedMaterializationError(
            "candidate execution-lock authority is invalid"
        )
    document = _strict_json_bytes(
        payload, context="immutable development candidate execution lock"
    )
    if not isinstance(document, dict):
        raise LockedMaterializationError("candidate execution lock is not an object")
    if _sha256_bytes(payload) != candidate.candidate_execution_lock_sha256:
        raise LockedMaterializationError(
            "candidate run authority does not bind execution lock blob"
        )
    return document


def _verify_locked_documents(
    documents: Any,
    *,
    master_secret: bytes,
    development_decision: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(documents, dict) or set(documents) != {
        "candidate",
        "assessor",
        "generator_private",
    }:
        raise LockedMaterializationError("locked generator returned wrong projections")
    for name in documents:
        if not isinstance(documents[name], dict):
            raise LockedMaterializationError(
                f"locked projection {name} is not an object"
            )
        canonical_bytes(documents[name])
    candidate_cases = documents["candidate"].get("cases")
    assessor_cases = documents["assessor"].get("cases")
    private_cases = documents["generator_private"].get("cases")
    if not all(
        isinstance(cases, list)
        for cases in (candidate_cases, assessor_cases, private_cases)
    ):
        raise LockedMaterializationError("locked projection case arrays are malformed")
    if not all(
        len(cases) == LOCKED_CASE_COUNT
        for cases in (candidate_cases, assessor_cases, private_cases)
    ):
        raise LockedMaterializationError("locked projection is not exactly 96 cases")

    def keys(cases: list[Any], context: str) -> list[str]:
        result: list[str] = []
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                raise LockedMaterializationError(f"{context} case {index} is malformed")
            key = case.get("opaque_case_key")
            if not isinstance(key, str) or LOWER_SHA256.fullmatch(key) is None:
                raise LockedMaterializationError(
                    f"{context} case {index} key is invalid"
                )
            result.append(key)
        if result != sorted(result) or len(result) != len(set(result)):
            raise LockedMaterializationError(f"{context} keys are not sorted/unique")
        return result

    candidate_keys = keys(candidate_cases, "candidate")
    assessor_keys = keys(assessor_cases, "assessor")
    private_keys = keys(private_cases, "generator-private")
    if candidate_keys != assessor_keys or candidate_keys != private_keys:
        raise LockedMaterializationError("locked opaque projection joins differ")

    allocation: Counter[tuple[str, int, str]] = Counter()
    for case in assessor_cases:
        family = case.get("family_id")
        group = case.get("latent_group")
        representation = case.get("representation")
        if family not in FAMILY_IDS or group not in LOCKED_SOURCE_GROUPS:
            raise LockedMaterializationError("locked family/group topology drift")
        if representation not in PRIMARY_REPRESENTATIONS:
            raise LockedMaterializationError(
                "locked projection contains Safety/nonprimary"
            )
        if case.get("expected_invariant") is not True:
            raise LockedMaterializationError("locked primary is not invariant")
        allocation[(family, group, representation)] += 1
    expected = {
        (family, group, representation)
        for family in FAMILY_IDS
        for group in LOCKED_SOURCE_GROUPS
        for representation in PRIMARY_REPRESENTATIONS
    }
    if set(allocation) != expected or any(count != 1 for count in allocation.values()):
        raise LockedMaterializationError("locked allocation differs from 8x4x3")

    private = documents["generator_private"]
    if private.get("master_secret_hex") != master_secret.hex():
        raise LockedMaterializationError("locked generator-private secret mismatch")
    if private.get("locked_decision") != dict(development_decision):
        raise LockedMaterializationError(
            "generator-private decision differs from C3 development authority"
        )
    expected_decision_hash = canonical_hash(dict(development_decision))
    if private.get("locked_decision_sha256") != expected_decision_hash:
        raise LockedMaterializationError("generator-private decision hash mismatch")
    return documents


def _verify_candidate_selection_bindings(
    candidate_root: Path,
    assessor_vault_root: Path,
    private_vault_root: Path,
    expected_selection: Mapping[str, Any],
    development_decision: Mapping[str, Any],
) -> dict[str, str]:
    """Verify common publication cross-binds the minimal candidate selection."""

    if set(expected_selection) != SELECTION_FIELDS:
        raise LockedMaterializationError("candidate selection is not minimal/closed")
    selection_path = candidate_root / "locked-selection.json"
    selection = _load_jcs(selection_path, context="locked candidate selection")
    if selection != dict(expected_selection):
        raise LockedMaterializationError(
            "candidate selection differs from validated development champion"
        )
    selection_record = {
        "path": selection_path.name,
        "sha256": _sha256_path(selection_path),
        "bytes": selection_path.stat().st_size,
    }

    candidate_manifest_path = candidate_root / "manifest.json"
    candidate_manifest = _load_jcs(
        candidate_manifest_path, context="locked candidate manifest"
    )
    if candidate_manifest.get("partition") != "locked":
        raise LockedMaterializationError("candidate manifest is not locked")
    if (
        candidate_manifest.get("candidate_input_sha256")
        != expected_selection["candidate_input_sha256"]
    ):
        raise LockedMaterializationError("candidate manifest input hash drift")
    if candidate_manifest.get("locked_selection_artifact") != selection_record:
        raise LockedMaterializationError("candidate manifest does not bind selection")
    candidate_manifest_sha = _sha256_path(candidate_manifest_path)

    candidate_completion_path = candidate_root / COMPLETION_NAME
    candidate_completion = _load_jcs(
        candidate_completion_path, context="locked candidate completion"
    )
    if candidate_completion.get("partition") != "locked":
        raise LockedMaterializationError("candidate completion is not locked")
    if candidate_completion.get("candidate_manifest_sha256") != candidate_manifest_sha:
        raise LockedMaterializationError("candidate completion does not bind manifest")

    assessor_manifest_path = assessor_vault_root / "manifest.json"
    assessor_manifest = _load_jcs(
        assessor_manifest_path, context="locked assessor-vault manifest"
    )
    if assessor_manifest.get("partition") != "locked":
        raise LockedMaterializationError("assessor-vault manifest is not locked")
    if assessor_manifest.get("candidate_manifest_sha256") != candidate_manifest_sha:
        raise LockedMaterializationError(
            "assessor-vault manifest does not bind candidate manifest"
        )
    expected_authority = {
        "development_assessment_sha256": development_decision[
            "development_assessment_sha256"
        ],
        "development_decision_record_sha256": _sha256_bytes(
            canonical_bytes(dict(development_decision))
        ),
        "decision_commit": development_decision["decision_commit"],
        "selected_variant": development_decision["selected_variant"],
        "selected_path": development_decision["selected_path"],
        "locked_selection_sha256": selection_record["sha256"],
    }
    if assessor_manifest.get("locked_authority") != expected_authority:
        raise LockedMaterializationError(
            "assessor-vault manifest does not cross-bind decision and selection"
        )
    assessor_manifest_sha = _sha256_path(assessor_manifest_path)

    assessor_completion_path = assessor_vault_root / COMPLETION_NAME
    assessor_completion = _load_jcs(
        assessor_completion_path, context="locked assessor-vault completion"
    )
    if assessor_completion.get("partition") != "locked":
        raise LockedMaterializationError("assessor-vault completion is not locked")
    if assessor_completion.get("manifest_sha256") != assessor_manifest_sha:
        raise LockedMaterializationError(
            "assessor-vault completion does not bind manifest"
        )

    private_manifest_path = private_vault_root / "manifest.json"
    private_manifest = _load_jcs(
        private_manifest_path, context="locked generator-private-vault manifest"
    )
    if private_manifest.get("partition") != "locked":
        raise LockedMaterializationError(
            "generator-private-vault manifest is not locked"
        )
    private_stage_manifest = private_vault_root / "generator-private" / "manifest.json"
    if private_manifest.get("generator_private_manifest_sha256") != _sha256_path(
        private_stage_manifest
    ):
        raise LockedMaterializationError(
            "generator-private-vault manifest does not bind private projection"
        )
    private_manifest_sha = _sha256_path(private_manifest_path)
    private_completion_path = private_vault_root / COMPLETION_NAME
    private_completion = _load_jcs(
        private_completion_path, context="locked generator-private-vault completion"
    )
    if private_completion.get("partition") != "locked":
        raise LockedMaterializationError("generator-private completion is not locked")
    if private_completion.get("manifest_sha256") != private_manifest_sha:
        raise LockedMaterializationError(
            "generator-private completion does not bind manifest"
        )
    return {
        "selection_sha256": selection_record["sha256"],
        "candidate_manifest_sha256": candidate_manifest_sha,
        "candidate_completion_sha256": _sha256_path(candidate_completion_path),
        "assessor_manifest_sha256": assessor_manifest_sha,
        "assessor_completion_sha256": _sha256_path(assessor_completion_path),
        "private_manifest_sha256": private_manifest_sha,
        "private_completion_sha256": _sha256_path(private_completion_path),
    }


def _tree_digest(root: Path) -> tuple[str, int]:
    if not root.is_dir() or _is_link_or_reparse(root):
        raise LockedMaterializationError(f"tree root is unavailable: {root}")
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256(b"GTLOCAL3FILETREE1\0")
    for path in files:
        if _is_link_or_reparse(path):
            raise LockedMaterializationError(f"tree contains a link/reparse: {path}")
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(struct.pack(">I", len(relative)))
        digest.update(relative)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest(), len(files)


def _relative_file_set(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }


def _is_link_or_reparse(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _reject_reparse_ancestry(path: Path) -> None:
    current = path
    while not current.exists():
        if current.parent == current:
            raise LockedMaterializationError(
                f"publication root has no ancestor: {path}"
            )
        current = current.parent
    while True:
        if _is_link_or_reparse(current):
            raise LockedMaterializationError(
                f"publication ancestry contains link/reparse: {current}"
            )
        if current.parent == current:
            break
        current = current.parent


def _verify_publication_root_separation(*paths: Path) -> None:
    resolved: list[Path] = []
    for path in paths:
        _reject_reparse_ancestry(path)
        resolved.append(path.resolve(strict=False))
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            try:
                common = Path(os.path.commonpath((left, right)))
            except ValueError:
                continue
            if common == left or common == right or left == right:
                raise LockedMaterializationError(
                    "candidate/assessor/private publication roots overlap"
                )


def _verify_physical_split(
    candidate_root: Path,
    assessor_vault_root: Path,
    private_vault_root: Path,
) -> None:
    if _relative_file_set(candidate_root) != EXPECTED_CANDIDATE_FILES:
        raise LockedMaterializationError("locked candidate file set drift")
    if _relative_file_set(assessor_vault_root) != EXPECTED_ASSESSOR_PUBLICATION_FILES:
        raise LockedMaterializationError("locked assessor-vault file set drift")
    if _relative_file_set(private_vault_root) != EXPECTED_PRIVATE_PUBLICATION_FILES:
        raise LockedMaterializationError("locked private-vault file set drift")
    if not (assessor_vault_root / "assessor").is_dir():
        raise LockedMaterializationError("locked assessor tree is missing")
    if not (private_vault_root / "generator-private").is_dir():
        raise LockedMaterializationError("locked generator-private tree is missing")
    forbidden = {
        "assessor",
        "gold",
        "truth",
        "generator",
        "private",
        "family",
        "latent",
        "representation",
        "decision",
        "assessment",
    }
    for path in candidate_root.rglob("*"):
        if _is_link_or_reparse(path):
            raise LockedMaterializationError("candidate tree contains a link/reparse")
        tokens = {
            token
            for part in path.relative_to(candidate_root).parts
            for token in re.split(r"[^a-z0-9]+", part.lower())
            if token
        }
        # ``locked-selection.json`` is a deliberate opaque candidate handoff;
        # it contains only the selected public variant and no decision identity.
        if path.name == "locked-selection.json":
            continue
        if tokens & forbidden:
            raise LockedMaterializationError(
                f"identity-bearing path escaped into candidate tree: {path}"
            )


def _seal_locked_vault(
    root: Path,
    *,
    source_lock_commit: str,
    message: str,
) -> tuple[str, str]:
    if not root.is_dir() or _is_link_or_reparse(root) or (root / ".git").exists():
        raise LockedMaterializationError("locked vault staging root is not fresh")
    commit_date = _git(
        REPOSITORY_ROOT, "show", "-s", "--format=%cI", source_lock_commit
    )
    git_path = _pinned_git()
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment = {
        "SystemRoot": str(system_root),
        "WINDIR": str(system_root),
        "PATH": os.pathsep.join((str(git_path.parent), str(system_root / "System32"))),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "GeoTarget Research Vault",
        "GIT_AUTHOR_EMAIL": "research-vault@invalid",
        "GIT_COMMITTER_NAME": "GeoTarget Research Vault",
        "GIT_COMMITTER_EMAIL": "research-vault@invalid",
        "GIT_AUTHOR_DATE": commit_date,
        "GIT_COMMITTER_DATE": commit_date,
    }
    common = (
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "commit.gpgSign=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "core.fsync=committed,reference",
        "-c",
        "core.fsyncMethod=fsync",
    )
    init = subprocess.run(
        [
            str(git_path),
            "--no-replace-objects",
            *common,
            "init",
            "--initial-branch=private-evidence",
        ],
        cwd=root,
        env=_closed_git_environment(environment),
        check=False,
        capture_output=True,
        text=True,
    )
    if init.returncode != 0:
        raise LockedMaterializationError(
            f"locked vault Git init failed: {init.stderr.strip()}"
        )
    if (root / ".git" / "objects" / "info" / "alternates").exists():
        raise LockedMaterializationError(
            "locked vault unexpectedly uses object alternates"
        )
    _git(root, *common, "add", "--all", environment=environment)
    _git(
        root,
        *common,
        "commit",
        "-m",
        message,
        environment=environment,
    )
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    parent_count = _git(root, "rev-list", "--parents", "-1", "HEAD").split()
    if len(parent_count) != 1:
        raise LockedMaterializationError("locked vault root commit has a parent")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise LockedMaterializationError("locked vault is dirty after commit")
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        completed = _git_run(
            root,
            "show",
            f"HEAD:{relative}",
            environment=environment,
            text=False,
        )
        if completed.returncode != 0 or completed.stdout != path.read_bytes():
            raise LockedMaterializationError(
                f"committed vault blob differs from working authority: {relative}"
            )
    return commit, tree


def _invoke_common_materializer(
    materializer_module: ModuleType,
    *,
    documents: dict[str, dict[str, Any]],
    assessor_module: ModuleType,
    bootstrap_bytes: bytes,
    development_decision: dict[str, Any],
    master_secret: bytes,
    timing_started: tuple[int, int, int],
    lock_sha256: str,
    lock_commit: str,
) -> None:
    materialize_stage = getattr(
        materializer_module, "materialize_stage_documents", None
    )
    if not callable(materialize_stage):
        raise LockedMaterializationError(
            "frozen common materializer lacks materialize_stage_documents"
        )
    try:
        result = materialize_stage(
            documents=documents,
            stage="locked",
            assessor_module=assessor_module,
            bootstrap_bytes=bootstrap_bytes,
            candidate_publication=CANDIDATE_STAGING_PATH,
            vault_publication=ASSESSOR_VAULT_STAGING_PATH,
            private_vault_publication=PRIVATE_VAULT_STAGING_PATH,
            candidate_final_path=CANDIDATE_OUTPUT_PATH,
            group_index_map=dict(LOCKED_GROUP_INDEX_MAP),
            locked_decision=development_decision,
            master_secret=master_secret,
            timing_started=timing_started,
            lock_sha256=lock_sha256,
            lock_commit=lock_commit,
        )
    except Exception as error:
        raise LockedMaterializationError(
            f"common locked-stage materialization failed: {error}"
        ) from error
    if result is not None:
        raise LockedMaterializationError("common materializer return contract drift")


def materialize(*, claim_already_created: bool = False) -> Path:
    """Consume the locked one-shot exactly once after a committed passing C3."""

    # No authority, runtime, repository, or environment preflight is permitted
    # before the durable claim.  A caller invoking this entry point has entered
    # the formal locked transaction; every subsequent failure stands.
    if not claim_already_created:
        raise LockedMaterializationError(
            "formal locked stage must enter through launch_locked.py"
        )
    _verify_locked_attempt_claim()
    accounting_active = False
    end_accounting: Any = None
    try:
        _verify_formal_python_invocation()
        repository_head = _verify_repository_after_claim()
        (
            c0_lock_commit,
            lock_sha,
            frozen_source_files,
        ) = _verify_c0_lock_for_locked_stage(repository_head)
        materializer_module = _import_frozen(
            "local3_common_materializer", SOURCE_ROOT / "materialize_development.py"
        )
        verify_environment = getattr(
            materializer_module, "verify_frozen_environment", None
        )
        local_options_sha = getattr(materializer_module, "_local_options_sha256", None)
        if not callable(verify_environment) or not callable(local_options_sha):
            raise LockedMaterializationError(
                "common materializer lacks frozen environment/local-options checks"
            )
        verify_environment()
        c0_lock = _load_jcs(
            PREIMPLEMENTATION_LOCK_PATH, context="C0 preimplementation lock replay"
        )
        if local_options_sha() != c0_lock["local_options_sha256"]:
            raise LockedMaterializationError("frozen LocalSolveOptions authority drift")
        authority_module = _import_frozen(
            "local3_stage_authority", SOURCE_ROOT / "authority.py"
        )
        assessor_module = _import_frozen(
            "local3_locked_assessor", SOURCE_ROOT / "assessor.py"
        )
        authorization_anchor_commit = _introduction_commit(
            DEVELOPMENT_AUTHORIZATION_ANCHOR_PATH, repository_head
        )
        if repository_head != authorization_anchor_commit:
            raise LockedMaterializationError(
                "locked materialization must start at the exact C3 authorization commit"
            )
        authorization = _resolve_development_authorization(
            authority_module,
            assessor_module,
            authorization_anchor_commit=authorization_anchor_commit,
        )
        _verify_bound_development_repositories(authorization)
        stage_input = authorization.stage_input
        _development_assessor_commit = stage_input.assessor_vault_commit
        stage_anchor_sha = stage_input.anchor_file.sha256
        (
            _development_private_commit,
            _development_private_tree,
            _private_anchor_sha,
        ) = _verify_private_audit_anchor(
            repository_head=repository_head,
            stage_anchor_commit=stage_input.anchor_commit,
            stage_anchor_sha256=stage_anchor_sha,
            source_lock_commit=c0_lock_commit,
        )
        if _sha256_path(CARD_PATH) != CARD_SHA256:
            raise LockedMaterializationError("EXP-LOCAL-003 card identity drift")
        execution_lock = _execution_lock_from_authorization(authorization)
        _verify_c2_source_extras(
            frozen_source_files,
            execution_lock,
            execution_lock_commit=(
                authorization.candidate_run.candidate_execution_lock_commit
            ),
        )
        bootstrap_module = _import_frozen(
            "bootstrap_indices", SOURCE_ROOT / "bootstrap_indices.py"
        )
        generator_module = _import_frozen(
            "local3_locked_generator", SOURCE_ROOT / "generator.py"
        )
        (
            development_decision,
            formal_locked_decision,
        ) = _authorization_decisions(authorization)

        begin_accounting = getattr(
            materializer_module, "_begin_validation_child_accounting", None
        )
        end_accounting = getattr(
            materializer_module, "_end_validation_child_accounting", None
        )
        if not callable(begin_accounting) or not callable(end_accounting):
            raise LockedMaterializationError(
                "common materializer lacks formal child-accounting controls"
            )
        timing_started = (
            time.process_time_ns(),
            time.perf_counter_ns(),
            time.time_ns(),
        )
        begin_accounting()
        accounting_active = True

        secret = os.urandom(32)
        if type(secret) is not bytes or len(secret) != 32:
            raise LockedMaterializationError(
                "OS entropy source did not return 32 bytes"
            )
        build_locked = getattr(generator_module, "build_locked_documents", None)
        if not callable(build_locked):
            raise LockedMaterializationError("frozen generator lacks locked builder")
        documents = build_locked(
            master_secret=secret,
            locked_decision=development_decision,
        )
        checked_documents = _verify_locked_documents(
            documents,
            master_secret=secret,
            development_decision=development_decision,
        )
        candidate_selection = {
            "schema_version": "geotarget.exp-local-003.locked-selection/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "stage": "locked",
            "selected_variant": development_decision["selected_variant"],
            "candidate_input_sha256": _raw_canonical_hash(
                checked_documents["candidate"]
            ),
        }
        if set(candidate_selection) != SELECTION_FIELDS:
            raise AssertionError("internal candidate-selection field drift")
        canonical_bytes(candidate_selection)

        make_bootstrap = getattr(bootstrap_module, "bootstrap_index_bytes", None)
        parse_bootstrap = getattr(bootstrap_module, "parse_bootstrap_index_bytes", None)
        if not callable(make_bootstrap) or not callable(parse_bootstrap):
            raise LockedMaterializationError("frozen bootstrap API is unavailable")
        bootstrap_bytes = make_bootstrap("locked")
        if not isinstance(bootstrap_bytes, bytes):
            raise LockedMaterializationError("locked bootstrap is not bytes")
        parse_bootstrap(
            bootstrap_bytes,
            expected_stage="locked",
            expected_sha256=_sha256_bytes(bootstrap_bytes),
        )

        if any(
            path.exists()
            for path in (
                CANDIDATE_STAGING_PATH,
                ASSESSOR_VAULT_STAGING_PATH,
                PRIVATE_VAULT_STAGING_PATH,
            )
        ):
            raise LockedMaterializationError("locked staging appeared after claim")
        _verify_publication_root_separation(
            CANDIDATE_STAGING_PATH,
            ASSESSOR_VAULT_STAGING_PATH,
            PRIVATE_VAULT_STAGING_PATH,
        )
        repository_resolved = REPOSITORY_ROOT.resolve()
        for external_root in (
            ASSESSOR_VAULT_STAGING_PATH,
            PRIVATE_VAULT_STAGING_PATH,
        ):
            resolved = external_root.resolve(strict=False)
            if (
                Path(os.path.commonpath((repository_resolved, resolved)))
                == repository_resolved
            ):
                raise LockedMaterializationError(
                    "locked authority vault is inside the candidate repository"
                )
        ASSESSOR_VAULT_STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRIVATE_VAULT_STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
        _invoke_common_materializer(
            materializer_module,
            documents=checked_documents,
            assessor_module=assessor_module,
            bootstrap_bytes=bootstrap_bytes,
            development_decision=development_decision,
            master_secret=secret,
            timing_started=timing_started,
            lock_sha256=lock_sha,
            lock_commit=c0_lock_commit,
        )
        end_accounting()
        accounting_active = False
        binding = _verify_candidate_selection_bindings(
            CANDIDATE_STAGING_PATH,
            ASSESSOR_VAULT_STAGING_PATH,
            PRIVATE_VAULT_STAGING_PATH,
            candidate_selection,
            development_decision,
        )
        _verify_physical_split(
            CANDIDATE_STAGING_PATH,
            ASSESSOR_VAULT_STAGING_PATH,
            PRIVATE_VAULT_STAGING_PATH,
        )
        _candidate_tree_sha, candidate_file_count = _tree_digest(CANDIDATE_STAGING_PATH)
        publication_tree = getattr(
            materializer_module, "_publication_tree_record", None
        )
        if not callable(publication_tree):
            raise LockedMaterializationError(
                "common materializer lacks publication tree authority"
            )
        candidate_publication_tree = publication_tree(CANDIDATE_STAGING_PATH)
        if (
            not isinstance(candidate_publication_tree, dict)
            or candidate_publication_tree.get("file_count") != candidate_file_count
        ):
            raise LockedMaterializationError("candidate publication tree record drift")
        _assessor_stage_tree_sha, _assessor_stage_file_count = _tree_digest(
            ASSESSOR_VAULT_STAGING_PATH
        )
        _private_stage_tree_sha, _private_stage_file_count = _tree_digest(
            PRIVATE_VAULT_STAGING_PATH
        )

        if any(
            path.exists()
            for path in (
                CANDIDATE_OUTPUT_PATH,
                ASSESSOR_VAULT_OUTPUT_PATH,
                PRIVATE_VAULT_OUTPUT_PATH,
            )
        ):
            raise LockedMaterializationError("locked output appeared during staging")
        locked_private_commit, locked_private_tree = _seal_locked_vault(
            PRIVATE_VAULT_STAGING_PATH,
            source_lock_commit=c0_lock_commit,
            message="research(local): seal locked generator-private authority",
        )
        locked_assessor_commit, locked_assessor_tree = _seal_locked_vault(
            ASSESSOR_VAULT_STAGING_PATH,
            source_lock_commit=c0_lock_commit,
            message="research(local): seal locked assessor authority",
        )
        locked_stage_anchor = {
            "schema_version": "geotarget.exp-local-003.stage-vault-anchor/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "stage": "locked",
            "source_lock_commit": c0_lock_commit,
            "preimplementation_lock_sha256": lock_sha,
            "materialization_attempt_claim_sha256": _sha256_path(ATTEMPT_PATH),
            "assessor_vault_git_commit": locked_assessor_commit,
            "assessor_vault_git_tree": locked_assessor_tree,
            "assessor_vault_manifest_sha256": binding["assessor_manifest_sha256"],
            "assessor_vault_completion_sha256": binding["assessor_completion_sha256"],
            "assessor_manifest_sha256": _sha256_path(
                ASSESSOR_VAULT_STAGING_PATH / "assessor" / "manifest.json"
            ),
            "candidate_manifest_sha256": binding["candidate_manifest_sha256"],
            "candidate_completion_sha256": binding["candidate_completion_sha256"],
            "candidate_publication_tree": candidate_publication_tree,
            "c1_phase_accounting": _load_jcs(
                ASSESSOR_VAULT_STAGING_PATH / "manifest.json",
                context="locked assessor-vault manifest accounting",
            )["c1_materialization_times"],
            "development_authority": {
                "development_authorization_anchor_commit": (
                    authorization.authorization_anchor_commit
                ),
                "development_authorization_anchor_sha256": (
                    authorization.authorization_anchor_file.sha256
                ),
                "development_stage_input_anchor_sha256": stage_anchor_sha,
                "development_candidate_run_authority_sha256": (
                    authorization.candidate_run.authority_file.sha256
                ),
                "development_assessor_stage_authority_sha256": (
                    authorization.assessor_output.authority_file.sha256
                ),
                "development_assessment_commit": (
                    authorization.assessor_output.assessment_commit
                ),
                "development_assessment_sha256": formal_locked_decision[
                    "development_assessment_sha256"
                ],
                "development_decision_commit": (
                    authorization.assessor_output.decision_commit
                ),
                "development_decision_record_sha256": formal_locked_decision[
                    "development_decision_record_sha256"
                ],
                "selected_variant": development_decision["selected_variant"],
                "selected_path": development_decision["selected_path"],
            },
            "candidate_visible": False,
            "rerun_permitted": False,
        }
        validate_schema = getattr(materializer_module, "_validate_schema", None)
        if not callable(validate_schema):
            raise LockedMaterializationError(
                "common materializer lacks schema validator"
            )
        validate_schema(locked_stage_anchor, "stage-vault-anchor.schema.json")
        _exclusive_write_json(LOCKED_STAGE_ANCHOR_PATH, locked_stage_anchor)
        locked_stage_anchor_sha = _sha256_path(LOCKED_STAGE_ANCHOR_PATH)
        locked_private_anchor = {
            "schema_version": (
                "geotarget.exp-local-003.generator-private-vault-anchor/v1"
            ),
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "stage": "locked",
            "source_lock_commit": c0_lock_commit,
            "materialization_attempt_claim_sha256": _sha256_path(ATTEMPT_PATH),
            "stage_vault_anchor_sha256": locked_stage_anchor_sha,
            "generator_private_vault_git_commit": locked_private_commit,
            "generator_private_vault_git_tree": locked_private_tree,
            "generator_private_vault_manifest_sha256": binding[
                "private_manifest_sha256"
            ],
            "generator_private_vault_completion_sha256": binding[
                "private_completion_sha256"
            ],
            "generator_private_manifest_sha256": _sha256_path(
                PRIVATE_VAULT_STAGING_PATH / "generator-private" / "manifest.json"
            ),
            "candidate_manifest_sha256": binding["candidate_manifest_sha256"],
            "candidate_visible": False,
            "formal_assessor_input": False,
            "rerun_permitted": False,
        }
        validate_schema(
            locked_private_anchor, "generator-private-vault-anchor.schema.json"
        )
        _exclusive_write_json(
            LOCKED_PRIVATE_ANCHOR_PATH,
            locked_private_anchor,
        )
        durable_rename = getattr(materializer_module, "_durable_directory_rename", None)
        if not callable(durable_rename):
            raise LockedMaterializationError(
                "common materializer lacks durable directory publication"
            )
        durable_rename(ASSESSOR_VAULT_STAGING_PATH, ASSESSOR_VAULT_OUTPUT_PATH)
        durable_rename(PRIVATE_VAULT_STAGING_PATH, PRIVATE_VAULT_OUTPUT_PATH)
        durable_rename(CANDIDATE_STAGING_PATH, CANDIDATE_OUTPUT_PATH)
        return CANDIDATE_OUTPUT_PATH
    except BaseException as error:
        if accounting_active and callable(end_accounting):
            end_accounting()
        _record_terminal_failure(error)
        raise


def main() -> int:
    raise LockedMaterializationError(
        "direct execution is forbidden; use `python -I -B -S launch_locked.py`"
    )


if __name__ == "__main__":
    raise SystemExit(main())
