"""Seal one EXP-LOCAL-003 main-repository stage without ambient Git policy.

This file is C0 protocol source.  The command has exactly one positional
argument (the closed stage name), has no retry/force/output option, and adds
only that stage's immutable files.  It deliberately does not call ``git add``
or ``git commit``: working bytes are written as raw Git blobs, installed in
the index with mode 100644, committed with one explicit parent, and finally
published by an atomic compare-and-swap of ``refs/heads/main``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final, Literal, TypeAlias, cast


sys.dont_write_bytecode = True

SOURCE_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = SOURCE_ROOT.parent
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
ENVIRONMENT_LOCK_PATH = EXPERIMENT_ROOT / "environment-lock.json"
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


def _verify_preimport_hygiene() -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
        or "site" in sys.modules
    ):
        raise RuntimeError("stage sealing requires exact `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise RuntimeError(f"stage sealing has injection environment: {blocked}")
    if any("site-packages" in value.casefold() for value in sys.path):
        raise RuntimeError("site-packages was active before stage sealing")
    expected = Path(__file__).resolve(strict=True)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if (
        len(sys.argv) != 2
        or sys.argv[1]
        not in {"c0-environment", "c0-lock", "c1", "c2", "c3", "c4", "c5", "c6"}
        or Path(sys.argv[0]).resolve(strict=True) != expected
        or not isinstance(main_file, str)
        or Path(main_file).resolve(strict=True) != expected
        or Path.cwd().resolve(strict=True) != REPOSITORY_ROOT.resolve(strict=True)
    ):
        raise RuntimeError("stage sealing invocation/path is not exact")
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise RuntimeError(f"stale project bytecode exists under {current}")


def _activate_formal_import_paths() -> None:
    executable = Path(sys.executable).resolve(strict=True)
    venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise RuntimeError("stage sealing is not using the fixed project venv")
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise RuntimeError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


if __name__ == "__main__":
    _verify_preimport_hygiene()
    _activate_formal_import_paths()
else:
    for _import_root in (PYTHON_SOURCE, SOURCE_ROOT):
        if str(_import_root) not in sys.path:
            sys.path.insert(0, str(_import_root))

import materialize_development as materialization  # noqa: E402


Stage: TypeAlias = Literal[
    "c0-environment", "c0-lock", "c1", "c2", "c3", "c4", "c5", "c6"
]

STAGES: Final[tuple[Stage, ...]] = (
    "c0-environment",
    "c0-lock",
    "c1",
    "c2",
    "c3",
    "c4",
    "c5",
    "c6",
)

_BASE: Final = "research/experiments/EXP-LOCAL-003"
_DEVELOPMENT_CANDIDATE: Final = f"{_BASE}/development-candidate-inputs"
_LOCKED_CANDIDATE: Final = f"{_BASE}/locked-candidate-inputs"

_STAGE_PATHS: Final[Mapping[Stage, tuple[str, ...]]] = {
    "c0-environment": (f"{_BASE}/environment-lock.json",),
    "c0-lock": (f"{_BASE}/preimplementation-lock.json",),
    "c1": (
        f"{_BASE}/C1_ATTEMPT_CLAIM.json",
        f"{_BASE}/C1_PRIVATE_AUDIT_ANCHOR.json",
        f"{_BASE}/C1_STAGE_VAULT_ANCHOR.json",
        f"{_DEVELOPMENT_CANDIDATE}/ONE_SHOT_COMPLETE.json",
        f"{_DEVELOPMENT_CANDIDATE}/development-candidate-inputs.json.gz",
        f"{_DEVELOPMENT_CANDIDATE}/manifest.json",
        f"{_DEVELOPMENT_CANDIDATE}/plugin/Local3FixturePlugin.jl",
    ),
    "c2": (
        "julia/GeoTargetCore/src/local_model_transform.jl",
        "julia/GeoTargetCore/test/test_local_model_transform.jl",
        f"{_BASE}/C2_L0_DEFAULT_EQUIVALENCE.json",
        f"{_BASE}/candidate-execution-lock.json",
        f"{_BASE}/source/candidate_runner.jl",
    ),
    "c3": (f"{_BASE}/C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json",),
    "c4": (
        f"{_BASE}/C4_LOCKED_PRIVATE_AUDIT_ANCHOR.json",
        f"{_BASE}/C4_LOCKED_STAGE_VAULT_ANCHOR.json",
        f"{_BASE}/LOCKED_ATTEMPT_CLAIM.json",
        f"{_LOCKED_CANDIDATE}/ONE_SHOT_COMPLETE.json",
        f"{_LOCKED_CANDIDATE}/locked-candidate-inputs.json.gz",
        f"{_LOCKED_CANDIDATE}/locked-selection.json",
        f"{_LOCKED_CANDIDATE}/manifest.json",
        f"{_LOCKED_CANDIDATE}/plugin/Local3FixturePlugin.jl",
    ),
    "c5": (f"{_BASE}/locked-candidate-execution-lock.json",),
    "c6": (f"{_BASE}/C6_FINAL_CONNECTION_ANCHOR.json",),
}

_PREVIOUS_STAGE: Final[Mapping[Stage, Stage | None]] = {
    stage: (None if index == 0 else STAGES[index - 1])
    for index, stage in enumerate(STAGES)
}

_STAGE_MARKER: Final[Mapping[Stage, str]] = {
    "c0-environment": f"{_BASE}/environment-lock.json",
    "c0-lock": f"{_BASE}/preimplementation-lock.json",
    "c1": f"{_BASE}/C1_ATTEMPT_CLAIM.json",
    "c2": f"{_BASE}/candidate-execution-lock.json",
    "c3": f"{_BASE}/C3_DEVELOPMENT_AUTHORIZATION_ANCHOR.json",
    "c4": f"{_BASE}/LOCKED_ATTEMPT_CLAIM.json",
    "c5": f"{_BASE}/locked-candidate-execution-lock.json",
    "c6": f"{_BASE}/C6_FINAL_CONNECTION_ANCHOR.json",
}

_COMMIT_MESSAGES: Final[Mapping[Stage, str]] = {
    "c0-environment": "research(local): freeze LOCAL003 execution environment",
    "c0-lock": "research(local): lock LOCAL003 before C1",
    "c1": "research(local): seal LOCAL003 development inputs",
    "c2": "research(local): freeze LOCAL003 candidate mechanism",
    "c3": "research(local): authorize LOCAL003 development result",
    "c4": "research(local): seal LOCAL003 locked inputs",
    "c5": "research(local): freeze LOCAL003 locked execution",
    "c6": "research(local): close LOCAL003 locked validation",
}

_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MainStageSealError(RuntimeError):
    """A formal stage boundary or Git transaction failed closed."""


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_pinned_git() -> Path:
    try:
        document = json.loads(ENVIRONMENT_LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MainStageSealError(
            f"cannot read the C0 environment lock: {error}"
        ) from error
    if not isinstance(document, dict):
        raise MainStageSealError("the C0 environment lock is not an object")
    tools = document.get("tools")
    if not isinstance(tools, dict):
        raise MainStageSealError("the C0 environment lock has no closed tool record")
    executable_value = tools.get("git_executable")
    expected_sha256 = tools.get("git_sha256")
    if (
        not isinstance(executable_value, str)
        or not isinstance(expected_sha256, str)
        or _SHA256.fullmatch(expected_sha256) is None
    ):
        raise MainStageSealError("the C0 Git executable authority is malformed")
    executable = Path(executable_value)
    if not executable.is_absolute() or not executable.is_file():
        raise MainStageSealError("the environment-locked Git executable is unavailable")
    if _sha256_path(executable) != expected_sha256:
        raise MainStageSealError("the environment-locked Git executable changed")
    return executable


def _closed_git_environment(git: Path) -> dict[str, str]:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment = {
        "SystemRoot": str(system_root),
        "WINDIR": str(system_root),
        "COMSPEC": str(system_root / "System32" / "cmd.exe"),
        "PATH": os.pathsep.join((str(git.parent), str(system_root / "System32"))),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_AUTHOR_NAME": "GeoTarget formal protocol",
        "GIT_AUTHOR_EMAIL": "geotarget-formal@invalid",
        "GIT_COMMITTER_NAME": "GeoTarget formal protocol",
        "GIT_COMMITTER_EMAIL": "geotarget-formal@invalid",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for name in ("TEMP", "TMP"):
        if value := os.environ.get(name):
            environment[name] = value
    return environment


class _Git:
    """Pinned Git invoked with a closed configuration and environment."""

    def __init__(self, executable: Path) -> None:
        self.executable = executable
        self.environment = _closed_git_environment(executable)
        self.prefix = (
            str(executable),
            "--no-replace-objects",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgSign=false",
            "-c",
            "tag.gpgSign=false",
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
        )

    def run(
        self,
        *arguments: str,
        input_bytes: bytes | None = None,
        allowed_returncodes: Iterable[int] = (0,),
        extra_environment: Mapping[str, str] | None = None,
    ) -> bytes:
        environment = dict(self.environment)
        if extra_environment:
            environment.update(extra_environment)
        completed = subprocess.run(
            [*self.prefix, *arguments],
            cwd=REPOSITORY_ROOT,
            env=environment,
            input=input_bytes,
            capture_output=True,
            check=False,
        )
        if completed.returncode not in set(allowed_returncodes):
            detail = completed.stderr.decode("utf-8", "replace").strip()
            raise MainStageSealError(
                f"pinned Git {' '.join(arguments)} failed "
                f"({completed.returncode}): {detail}"
            )
        return bytes(completed.stdout)

    def text(self, *arguments: str, **kwargs: object) -> str:
        output = self.run(*arguments, **kwargs)
        try:
            return output.decode("utf-8", "strict").strip()
        except UnicodeDecodeError as error:
            raise MainStageSealError("pinned Git emitted non-UTF-8 metadata") from error


def _parse_name_status(payload: bytes, *, context: str) -> dict[str, str]:
    fields = payload.split(b"\0")
    if fields[-1:] == [b""]:
        fields.pop()
    if len(fields) % 2:
        raise MainStageSealError(f"{context} name/status output is malformed")
    result: dict[str, str] = {}
    for index in range(0, len(fields), 2):
        try:
            status = fields[index].decode("ascii", "strict")
            path = fields[index + 1].decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise MainStageSealError(
                f"{context} contains undecodable metadata"
            ) from error
        if path in result or status not in {"A", "D", "M", "T", "U"}:
            raise MainStageSealError(f"{context} contains unsupported change metadata")
        result[path] = status
    return result


def _parse_porcelain(payload: bytes, *, required_status: bytes) -> set[str]:
    fields = payload.split(b"\0")
    if fields[-1:] == [b""]:
        fields.pop()
    result: set[str] = set()
    for field in fields:
        if len(field) < 4 or field[:3] != required_status:
            raise MainStageSealError(
                "worktree/index status is not the expected additions"
            )
        try:
            path = field[3:].decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise MainStageSealError("worktree status path is not UTF-8") from error
        if path in result:
            raise MainStageSealError("worktree status contains a duplicate path")
        result.add(path)
    return result


def _parents(git: _Git, commit: str) -> tuple[str, ...]:
    fields = git.text("rev-list", "--parents", "-n", "1", commit).split()
    if (
        not fields
        or fields[0] != commit
        or any(_OBJECT_ID.fullmatch(field) is None for field in fields)
    ):
        raise MainStageSealError("Git commit parent metadata is malformed")
    return tuple(fields[1:])


def _tree_entry(git: _Git, commit: str, path: str) -> tuple[str, str, str]:
    payload = git.run("ls-tree", "-z", commit, "--", path)
    fields = payload.split(b"\0")
    if len(fields) != 2 or fields[1] != b"":
        raise MainStageSealError(f"Git tree has no unique entry for {path}")
    metadata, separator, observed_path = fields[0].partition(b"\t")
    pieces = metadata.split()
    if separator != b"\t" or len(pieces) != 3:
        raise MainStageSealError(f"Git tree entry is malformed for {path}")
    try:
        mode, kind, object_id = (piece.decode("ascii", "strict") for piece in pieces)
        decoded_path = observed_path.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise MainStageSealError(f"Git tree entry is undecodable for {path}") from error
    if decoded_path != path or _OBJECT_ID.fullmatch(object_id) is None:
        raise MainStageSealError(f"Git tree entry path/object differs for {path}")
    return mode, kind, object_id


def _verify_previous_stage(git: _Git, stage: Stage, head: str) -> None:
    previous = _PREVIOUS_STAGE[stage]
    if previous is None:
        return
    parents = _parents(git, head)
    if len(parents) != 1:
        raise MainStageSealError("the preceding stage commit is not single-parent")
    changes = _parse_name_status(
        git.run(
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-z",
            head,
        ),
        context="preceding stage",
    )
    expected = set(_STAGE_PATHS[previous])
    if changes != {path: "A" for path in expected}:
        raise MainStageSealError(
            f"HEAD did not introduce exactly the preceding {previous} stage"
        )
    marker = _STAGE_MARKER[previous]
    if marker not in changes:
        raise MainStageSealError(
            "the preceding stage marker was not introduced by HEAD"
        )
    for path in expected:
        mode, kind, _object_id = _tree_entry(git, head, path)
        if mode != "100644" or kind != "blob":
            raise MainStageSealError(
                f"preceding stage path is not a regular 100644 blob: {path}"
            )


def _is_link_or_reparse(path: Path) -> bool:
    metadata = path.lstat()
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _verify_direct_object_database(git: _Git) -> None:
    expected_git_dir = REPOSITORY_ROOT / ".git"
    expected_objects = expected_git_dir / "objects"
    git_dir = Path(git.text("rev-parse", "--absolute-git-dir"))
    common_dir = Path(
        git.text("rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    if (
        git_dir.resolve() != expected_git_dir.resolve()
        or common_dir.resolve() != expected_git_dir.resolve()
        or not expected_git_dir.is_dir()
        or not expected_objects.is_dir()
    ):
        raise MainStageSealError(
            "formal sealing requires the repository's direct .git object database"
        )
    current = expected_objects
    while True:
        if _is_link_or_reparse(current):
            raise MainStageSealError(
                "the formal .git object-database ancestry contains a link/reparse point"
            )
        if current.parent == current:
            break
        current = current.parent
    info = expected_objects / "info"
    if info.exists() and _is_link_or_reparse(info):
        raise MainStageSealError(
            "the formal object info directory is a link/reparse point"
        )
    for name in ("alternates", "http-alternates"):
        if os.path.lexists(info / name):
            raise MainStageSealError("Git object-database alternates are forbidden")


def _verify_regular_working_file(relative: str) -> None:
    path = REPOSITORY_ROOT / relative
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError as error:
        raise MainStageSealError(
            f"stage path escapes the repository: {relative}"
        ) from error
    if not path.is_file() or _is_link_or_reparse(path):
        raise MainStageSealError(f"stage path is not a regular file: {relative}")
    current = path.parent
    while True:
        if _is_link_or_reparse(current):
            raise MainStageSealError(
                f"stage path traverses a link/reparse point: {relative}"
            )
        if current == REPOSITORY_ROOT:
            break
        if current.parent == current:
            raise MainStageSealError(
                f"stage path ancestry escaped the repository: {relative}"
            )
        current = current.parent


def _verify_repository_boundary(git: _Git, stage: Stage) -> str:
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise MainStageSealError("stage sealing must run from the repository root")
    root = Path(git.text("rev-parse", "--show-toplevel"))
    if root.resolve() != REPOSITORY_ROOT.resolve():
        raise MainStageSealError("pinned Git resolved a different repository root")
    _verify_direct_object_database(git)
    if git.text("symbolic-ref", "--quiet", "HEAD") != "refs/heads/main":
        raise MainStageSealError("stage sealing requires the main branch")
    head = git.text("rev-parse", "--verify", "HEAD")
    if _OBJECT_ID.fullmatch(head) is None:
        raise MainStageSealError("HEAD is not a valid Git object id")
    head_tree = git.text("show", "-s", "--format=%T", head)
    if _OBJECT_ID.fullmatch(head_tree) is None:
        raise MainStageSealError("the HEAD tree id is malformed")
    git.run(
        "diff",
        "--cached",
        "--quiet",
        head,
        "--",
    )
    # Ask for the exact name/status form as a second clean-index check.
    if git.run("diff", "--cached", "--name-status", "-z", head, "--"):
        raise MainStageSealError("stage sealing requires an index equal to HEAD")
    if git.run("for-each-ref", "--format=%(refname)", "refs/replace"):
        raise MainStageSealError("Git replace refs are forbidden in a formal run")
    expected = set(_STAGE_PATHS[stage])
    observed = _parse_porcelain(
        git.run("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        required_status=b"?? ",
    )
    if observed != expected:
        raise MainStageSealError(
            "worktree additions differ from the closed stage set: "
            f"missing={sorted(expected - observed)}, extra={sorted(observed - expected)}"
        )
    for relative in expected:
        _verify_regular_working_file(relative)
    _verify_previous_stage(git, stage, head)
    return head


def _verify_index_additions(
    git: _Git,
    *,
    parent: str,
    expected_objects: Mapping[str, str],
) -> str:
    expected_paths = set(expected_objects)
    changes = _parse_name_status(
        git.run("diff", "--cached", "--name-status", "-z", parent, "--"),
        context="staged stage",
    )
    if changes != {path: "A" for path in expected_paths}:
        raise MainStageSealError("the index differs from the exact stage additions")
    staged_status = _parse_porcelain(
        git.run("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        required_status=b"A  ",
    )
    if staged_status != expected_paths:
        raise MainStageSealError("staged status differs from the exact stage additions")
    for path, expected_object in expected_objects.items():
        mode, index_stage, observed_object = _index_tree_entry(git, path)
        if (mode, index_stage, observed_object) != ("100644", "0", expected_object):
            raise MainStageSealError(f"index entry differs for {path}")
        working_bytes = (REPOSITORY_ROOT / path).read_bytes()
        if git.run("cat-file", "blob", expected_object) != working_bytes:
            raise MainStageSealError(f"staged blob differs from working bytes: {path}")
        observed_hash = git.text("hash-object", "--no-filters", "--", path)
        if observed_hash != expected_object:
            raise MainStageSealError(f"working bytes changed while staging: {path}")
    tree = git.text("write-tree")
    if _OBJECT_ID.fullmatch(tree) is None:
        raise MainStageSealError("staged tree id is malformed")
    return tree


def _verify_commit(
    git: _Git,
    *,
    commit: str,
    parent: str,
    tree: str,
    expected_objects: Mapping[str, str],
) -> None:
    if (
        _OBJECT_ID.fullmatch(commit) is None
        or git.text("cat-file", "-t", commit) != "commit"
    ):
        raise MainStageSealError("new stage commit is not a valid commit object")
    if _parents(git, commit) != (parent,):
        raise MainStageSealError(
            "new stage commit does not have exactly the expected parent"
        )
    if git.text("show", "-s", "--format=%T", commit) != tree:
        raise MainStageSealError("new stage commit tree differs from the staged tree")
    changes = _parse_name_status(
        git.run(
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-z",
            commit,
        ),
        context="new stage commit",
    )
    if changes != {path: "A" for path in expected_objects}:
        raise MainStageSealError("new commit differs from the exact stage additions")
    for path, object_id in expected_objects.items():
        mode, kind, observed_object = _tree_entry(git, commit, path)
        if (mode, kind, observed_object) != ("100644", "blob", object_id):
            raise MainStageSealError(f"new commit tree differs for {path}")


def _index_tree_entry(git: _Git, path: str) -> tuple[str, str, str]:
    payload = git.run("ls-files", "--stage", "-z", "--", path)
    fields = payload.split(b"\0")
    if len(fields) != 2 or fields[1] != b"":
        raise MainStageSealError(f"Git index has no unique entry for {path}")
    metadata, separator, observed_path = fields[0].partition(b"\t")
    pieces = metadata.split()
    if separator != b"\t" or len(pieces) != 3:
        raise MainStageSealError(f"Git index entry is malformed for {path}")
    try:
        mode = pieces[0].decode("ascii", "strict")
        object_id = pieces[1].decode("ascii", "strict")
        index_stage = pieces[2].decode("ascii", "strict")
        decoded_path = observed_path.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise MainStageSealError(
            f"Git index entry is undecodable for {path}"
        ) from error
    if decoded_path != path or _OBJECT_ID.fullmatch(object_id) is None:
        raise MainStageSealError(f"Git index path/object differs for {path}")
    return mode, index_stage, object_id


def _stage_raw_blobs(git: _Git, stage: Stage) -> dict[str, str]:
    objects: dict[str, str] = {}
    for relative in _STAGE_PATHS[stage]:
        object_id = git.text("hash-object", "-w", "--no-filters", "--", relative)
        if _OBJECT_ID.fullmatch(object_id) is None:
            raise MainStageSealError(f"Git returned an invalid blob id for {relative}")
        git.run(
            "update-index",
            "--add",
            "--cacheinfo",
            "100644",
            object_id,
            relative,
        )
        mode, index_stage, indexed_object = _index_tree_entry(git, relative)
        if (mode, index_stage, indexed_object) != ("100644", "0", object_id):
            raise MainStageSealError(
                f"Git did not install the exact index blob: {relative}"
            )
        objects[relative] = object_id
    return objects


def seal_stage(stage: Stage) -> str:
    """Verify, build, and publish one closed main-repository stage commit."""

    if stage not in STAGES:
        raise MainStageSealError(f"unsupported formal stage: {stage}")
    git = _Git(_load_pinned_git())
    parent = _verify_repository_boundary(git, stage)

    materialization.verify_frozen_environment()

    # The full runtime verification is intentionally before the first Git
    # mutation.  Recheck every repository precondition afterwards so the
    # verifier cannot widen the transaction boundary.
    if _load_pinned_git() != git.executable:
        raise MainStageSealError(
            "the pinned Git executable changed during verification"
        )
    if _verify_repository_boundary(git, stage) != parent:
        raise MainStageSealError("HEAD changed during frozen-environment verification")

    objects = _stage_raw_blobs(git, stage)
    tree = _verify_index_additions(
        git,
        parent=parent,
        expected_objects=objects,
    )

    parent_epoch_text = git.text("show", "-s", "--format=%ct", parent)
    try:
        parent_epoch = int(parent_epoch_text)
    except ValueError as error:
        raise MainStageSealError("parent commit timestamp is malformed") from error
    deterministic_date = f"{parent_epoch + 1} +0000"
    commit = git.text(
        "commit-tree",
        tree,
        "-p",
        parent,
        "-m",
        _COMMIT_MESSAGES[stage],
        extra_environment={
            "GIT_AUTHOR_DATE": deterministic_date,
            "GIT_COMMITTER_DATE": deterministic_date,
        },
    )
    _verify_commit(
        git,
        commit=commit,
        parent=parent,
        tree=tree,
        expected_objects=objects,
    )
    git.run(
        "update-ref",
        "-m",
        f"EXP-LOCAL-003 {stage} formal seal",
        "refs/heads/main",
        commit,
        parent,
    )

    if git.text("rev-parse", "--verify", "HEAD") != commit:
        raise MainStageSealError("main did not advance to the new stage commit")
    _verify_commit(
        git,
        commit=commit,
        parent=parent,
        tree=tree,
        expected_objects=objects,
    )
    if git.run("status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise MainStageSealError("repository is not clean after the stage commit")
    if git.text("write-tree") != tree:
        raise MainStageSealError("index tree changed after the stage commit")
    return commit


def _verify_cli_invocation() -> None:
    flags = sys.flags
    if (
        flags.isolated != 1
        or flags.ignore_environment != 1
        or flags.no_user_site != 1
        or flags.safe_path is not True
        or flags.dont_write_bytecode is not True
        or flags.no_site != 1
        or flags.optimize != 0
    ):
        raise MainStageSealError(
            "formal stage sealing requires Python -I -B -S with optimization disabled"
        )
    if not sys.argv or Path(sys.argv[0]).resolve() != Path(__file__).resolve():
        raise MainStageSealError(
            "formal stage sealing must execute this script directly"
        )
    if Path.cwd().resolve() != REPOSITORY_ROOT.resolve():
        raise MainStageSealError(
            "formal stage sealing must start at the repository root"
        )


def main(arguments: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if len(values) != 1 or values[0] not in STAGES:
        choices = ", ".join(STAGES)
        raise MainStageSealError(
            f"usage: seal_main_stage.py <stage>; stage must be one of: {choices}"
        )
    _verify_cli_invocation()
    stage = cast(Stage, values[0])
    commit = seal_stage(stage)
    print(f"sealed EXP-LOCAL-003 {stage}: {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
