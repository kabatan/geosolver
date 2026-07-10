"""Outcome-blind publication binding supplement for EXP-JAC-003.

The v1 binding amendment and checker remain immutable.  This supplement calls
their result-blind pre/post builders, publishes their receipts without a
replace race, seals every staging file as opaque bytes, launches the already
frozen finalizer as its exact direct child, and verifies the resulting archive
before assessment is permitted.

No gzip input or segment JSON is decompressed or parsed by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import types
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


AMENDMENT_SCHEMA = "exp-jac-003-formal-publication-binding-amendment-a2/v1"
SEAL_SCHEMA = "exp-jac-003-formal-publication-seal-a2/v1"
ANCHOR_SCHEMA = "exp-jac-003-formal-publication-anchor-a2/v1"
EXECUTION_SCHEMA = "exp-jac-003-finalizer-execution-audit-a2/v1"
ARCHIVE_SCHEMA = "exp-jac-003-formal-archive-receipt-a2/v1"
RUN_SCHEMA = "exp-jac-003-formal-abba-run/v1"


class PublicationBindingError(RuntimeError):
    """A terminal, fail-closed publication-binding violation."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublicationBindingError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise PublicationBindingError(f"{label} must be one JSON object")
    return value


def _assert_plain_components(path: Path, label: str) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            break
        metadata = os.lstat(current)
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_flag:
            raise PublicationBindingError(
                f"{label} traverses a symlink/reparse point: {current}"
            )


def _plain_path(path: Path, *, must_exist: bool, label: str) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    absolute = Path(os.path.abspath(candidate))
    _assert_plain_components(absolute, label)
    if must_exist and not absolute.exists():
        raise PublicationBindingError(f"{label} does not exist: {absolute}")
    resolved = absolute.resolve(strict=must_exist)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(absolute)):
        raise PublicationBindingError(f"{label} is not a canonical plain path")
    return absolute


def _repo_path(repo: Path, relative: str, *, must_exist: bool, label: str) -> Path:
    if not relative or "\\" in relative:
        raise PublicationBindingError(f"{label} must be a POSIX relative path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise PublicationBindingError(f"{label} is not canonical")
    target = _plain_path(
        repo.joinpath(*pure.parts), must_exist=must_exist, label=label
    )
    try:
        target.relative_to(repo)
    except ValueError as error:
        raise PublicationBindingError(f"{label} escapes repository") from error
    return target


def _write_json_no_replace(path: Path, document: Mapping[str, Any]) -> str:
    """Atomically publish JSON without ever replacing an existing target."""

    target = _plain_path(path, must_exist=False, label="receipt output")
    if os.path.lexists(target):
        raise PublicationBindingError(f"terminal existing receipt: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    _assert_plain_components(target.parent, "receipt parent")
    payload = (
        json.dumps(
            dict(document),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    linked = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
            linked = True
        except FileExistsError as error:
            raise PublicationBindingError(
                f"terminal receipt creation race: {target}"
            ) from error
        if target.read_bytes() != payload:
            raise PublicationBindingError(f"receipt read-back mismatch: {target}")
    finally:
        temporary.unlink(missing_ok=True)
    if not linked:
        raise PublicationBindingError(f"receipt was not linked: {target}")
    return _sha256_bytes(payload)


def _git(repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise PublicationBindingError(
            f"git {' '.join(arguments)} failed: {error.stderr.strip()}"
        ) from error
    return result.stdout.strip()


def _git_z_paths(repo: Path, *arguments: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *arguments, "-z"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise PublicationBindingError(f"git path inventory failed: {detail}") from error
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _load_amendment(path: Path) -> tuple[Path, dict[str, Any], str]:
    amendment_path = _plain_path(path, must_exist=True, label="A2 amendment")
    payload = amendment_path.read_bytes()
    amendment = _read_json(amendment_path, "A2 amendment")
    if amendment.get("schema_version") != AMENDMENT_SCHEMA:
        raise PublicationBindingError("A2 amendment schema mismatch")
    if amendment.get("experiment_id") != "EXP-JAC-003":
        raise PublicationBindingError("A2 experiment mismatch")
    attestation = amendment.get("outcome_blind_attestation", {})
    if attestation.get("any_outcome_opened") is not False:
        raise PublicationBindingError("A2 amendment is not outcome-blind")
    return amendment_path, amendment, _sha256_bytes(payload)


def _paths(amendment: Mapping[str, Any]) -> dict[str, Path]:
    root = _plain_path(
        Path(amendment["authority_repository_root"]),
        must_exist=True,
        label="authority root",
    )
    repo = _plain_path(
        Path(amendment["frozen_repository_root"]),
        must_exist=True,
        label="frozen repository",
    )
    execution = amendment["execution"]
    result: dict[str, Path] = {
        "authority_root": root,
        "repo": repo,
        "amendment": _repo_path(
            root,
            amendment["amendment_relative_path"],
            must_exist=True,
            label="A2 amendment authority path",
        ),
        "checker": _repo_path(
            root,
            amendment["checker"]["relative_path"],
            must_exist=True,
            label="A2 checker authority path",
        ),
        "v1_amendment": _repo_path(
            root,
            amendment["v1_authority"]["amendment_relative_path"],
            must_exist=True,
            label="v1 amendment",
        ),
        "v1_checker": _repo_path(
            root,
            amendment["v1_authority"]["checker_relative_path"],
            must_exist=True,
            label="v1 checker",
        ),
    }
    repository_relative = {
        "staging": "staging_relative_path",
        "partial": "partial_relative_path",
        "official": "official_relative_path",
        "outer": "outer_audit_relative_path",
        "host": "host_observation_relative_path",
        "source": "source_observation_relative_path",
        "finalizer": "finalizer_relative_path",
    }
    for key, field in repository_relative.items():
        result[key] = _repo_path(
            repo,
            execution[field],
            must_exist=key == "finalizer",
            label=key,
        )
    result["v1_pre"] = _plain_path(
        Path(execution["v1_pre_audit_path"]),
        must_exist=False,
        label="v1 pre audit",
    )
    result["v1_post"] = _plain_path(
        result["staging"] / execution["v1_post_audit_filename"],
        must_exist=False,
        label="v1 post audit",
    )
    result["seal"] = _plain_path(
        result["staging"] / execution["seal_filename"],
        must_exist=False,
        label="publication seal",
    )
    result["anchor"] = _plain_path(
        Path(execution["anchor_path"]), must_exist=False, label="publication anchor"
    )
    result["execution"] = _plain_path(
        Path(execution["execution_audit_path"]),
        must_exist=False,
        label="execution audit",
    )
    result["archive_receipt"] = _plain_path(
        result["official"] / execution["archive_receipt_filename"],
        must_exist=False,
        label="archive receipt",
    )
    result["python"] = _plain_path(
        Path(execution["python_executable"]),
        must_exist=True,
        label="Python executable",
    )
    normalized = [os.path.normcase(str(value)) for value in result.values()]
    if len(normalized) != len(set(normalized)):
        raise PublicationBindingError("A2 bound paths contain aliases")
    return result


def _verify_authority(
    amendment_path: Path,
    amendment: Mapping[str, Any],
    amendment_sha: str,
    paths: Mapping[str, Path],
) -> dict[str, str]:
    if paths["amendment"] != amendment_path:
        raise PublicationBindingError("invoked A2 amendment is not authority path")
    root = paths["authority_root"]
    discovered = _plain_path(
        Path(_git(root, "rev-parse", "--show-toplevel")),
        must_exist=True,
        label="authority git root",
    )
    if discovered != root:
        raise PublicationBindingError("authority git root mismatch")
    checker_sha = _sha256_file(paths["checker"])
    if checker_sha != amendment["checker"]["sha256"]:
        raise PublicationBindingError("A2 checker hash mismatch")
    if _sha256_file(Path(__file__).resolve()) != checker_sha:
        raise PublicationBindingError("executing A2 checker hash mismatch")
    relative_amendment = paths["amendment"].relative_to(root).as_posix()
    relative_checker = paths["checker"].relative_to(root).as_posix()
    for relative in (relative_amendment, relative_checker):
        _git(root, "ls-files", "--error-unmatch", "--", relative)
    if _git(
        root,
        "status",
        "--porcelain",
        "--",
        relative_amendment,
        relative_checker,
    ):
        raise PublicationBindingError("A2 amendment/checker are modified")
    amendment_commit = _git(
        root, "log", "-1", "--format=%H", "--", relative_amendment
    )
    checker_commit = _git(root, "log", "-1", "--format=%H", "--", relative_checker)
    if not amendment_commit or amendment_commit != checker_commit:
        raise PublicationBindingError("A2 amendment/checker lack joint commit")
    v1 = amendment["v1_authority"]
    if _sha256_file(paths["v1_amendment"]) != v1["amendment_sha256"]:
        raise PublicationBindingError("v1 amendment hash drift")
    if _sha256_file(paths["v1_checker"]) != v1["checker_sha256"]:
        raise PublicationBindingError("v1 checker hash drift")
    return {
        "amendment_commit": amendment_commit,
        "amendment_sha256": amendment_sha,
        "checker_commit": checker_commit,
        "checker_sha256": checker_sha,
        "v1_amendment_sha256": v1["amendment_sha256"],
        "v1_checker_sha256": v1["checker_sha256"],
    }


def _load_v1(amendment: Mapping[str, Any], paths: Mapping[str, Path]) -> types.ModuleType:
    expected = amendment["v1_authority"]["checker_sha256"]
    payload = paths["v1_checker"].read_bytes()
    if _sha256_bytes(payload) != expected:
        raise PublicationBindingError("v1 checker changed before import")
    module = types.ModuleType("exp_jac_003_formal_binding_guard_v1_approved")
    module.__file__ = str(paths["v1_checker"])
    exec(compile(payload, str(paths["v1_checker"]), "exec"), module.__dict__)
    return module


def _allowed_output(path: str, staging: str, exact: set[str]) -> bool:
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        return False
    normalized = pure.as_posix()
    return normalized in exact or normalized.startswith(f"{staging}/")


def _verify_worktree_hygiene(
    repo: Path,
    *,
    allowed_staging: str | None,
    allowed_exact: Sequence[str] = (),
) -> dict[str, Any]:
    tracked = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=no"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    if tracked:
        raise PublicationBindingError("frozen tracked worktree or index changed")
    ordinary = _git_z_paths(repo, "ls-files", "--others", "--exclude-standard")
    ignored = _git_z_paths(
        repo, "ls-files", "--others", "--ignored", "--exclude-standard"
    )
    discovered = sorted(set(ordinary) | set(ignored))
    exact = set(allowed_exact)
    rejected = [
        path
        for path in discovered
        if allowed_staging is None
        or not _allowed_output(path, allowed_staging, exact)
    ]
    if rejected:
        raise PublicationBindingError(
            f"untracked/ignored leakage outside exact outputs: {rejected}"
        )
    for relative in amendment_sensitive_roots():
        root = repo.joinpath(*PurePosixPath(relative).parts)
        if root.exists():
            _assert_no_reparse_tree(root, f"sensitive root {relative}")
    return {
        "ignored_file_count": len(set(ignored)),
        "ordinary_untracked_file_count": len(set(ordinary)),
        "output_file_count": len(discovered),
        "rejected_file_count": 0,
    }


def amendment_sensitive_roots() -> tuple[str, ...]:
    return (
        "julia/GeoTargetCore/src",
        "research/experiments/EXP-JAC-003/source",
        "research/harness",
    )


def _assert_no_reparse_tree(root: Path, label: str) -> None:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                metadata = entry.stat(follow_symlinks=False)
                attributes = getattr(metadata, "st_file_attributes", 0)
                if entry.is_symlink() or attributes & reparse_flag:
                    raise PublicationBindingError(
                        f"{label} contains symlink/reparse: {entry.path}"
                    )
                if stat.S_ISDIR(metadata.st_mode):
                    stack.append(Path(entry.path))


def _inventory(root: Path) -> dict[str, Any]:
    root = _plain_path(root, must_exist=True, label="inventory root")
    if not root.is_dir():
        raise PublicationBindingError("inventory root is not a directory")
    rows: list[dict[str, Any]] = []
    stack = [root]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                metadata = entry.stat(follow_symlinks=False)
                attributes = getattr(metadata, "st_file_attributes", 0)
                if entry.is_symlink() or attributes & reparse_flag:
                    raise PublicationBindingError(
                        f"inventory contains symlink/reparse: {entry.path}"
                    )
                path = Path(entry.path)
                if stat.S_ISDIR(metadata.st_mode):
                    stack.append(path)
                elif stat.S_ISREG(metadata.st_mode):
                    rows.append(
                        {
                            "path": path.relative_to(root).as_posix(),
                            "sha256": _sha256_file(path),
                            "size": metadata.st_size,
                        }
                    )
                else:
                    raise PublicationBindingError(
                        f"inventory contains nonregular entry: {entry.path}"
                    )
    rows.sort(key=lambda row: row["path"])
    return {
        "file_count": len(rows),
        "files": rows,
        "root_sha256": _sha256_bytes(_canonical_bytes(rows)),
        "total_bytes": sum(row["size"] for row in rows),
    }


def _verify_inventory_rows(root: Path, expected: Mapping[str, Any]) -> None:
    actual = _inventory(root)
    if actual != expected:
        raise PublicationBindingError("opaque inventory mutation or membership drift")


def _snapshot_frozen(
    amendment: Mapping[str, Any], paths: Mapping[str, Path]
) -> dict[str, Any]:
    v1 = _read_json(paths["v1_amendment"], "v1 amendment")
    repo = paths["repo"]
    lock = _repo_path(
        repo,
        v1["execution_plan"]["source_lock_relative_path"],
        must_exist=True,
        label="source lock",
    )
    lock_document = _read_json(lock, "source lock")
    relatives = set(lock_document["files"])
    relatives.add(v1["execution_plan"]["source_lock_relative_path"])
    relatives.add(v1["execution_plan"]["julia_manifest_relative_path"])
    relatives.add(v1["execution_plan"]["exclusive_runner_relative_path"])
    rows = []
    for relative in sorted(relatives):
        target = _repo_path(
            repo, relative, must_exist=True, label=f"frozen snapshot {relative}"
        )
        rows.append(
            {
                "path": relative,
                "sha256": _sha256_file(target),
                "size": target.stat().st_size,
            }
        )
    return {
        "file_count": len(rows),
        "files": rows,
        "root_sha256": _sha256_bytes(_canonical_bytes(rows)),
    }


def _future_paths_absent(paths: Mapping[str, Path]) -> None:
    for key in (
        "staging",
        "partial",
        "official",
        "outer",
        "host",
        "source",
        "v1_pre",
        "v1_post",
        "seal",
        "anchor",
        "execution",
        "archive_receipt",
    ):
        if os.path.lexists(paths[key]):
            raise PublicationBindingError(f"terminal pre-existing {key}: {paths[key]}")


def _phase_tokens(
    amendment: Mapping[str, Any], phase: str
) -> list[str]:
    tokens = amendment["execution"][f"exact_{phase}_command_tokens"]
    if not isinstance(tokens, list) or not all(isinstance(item, str) for item in tokens):
        raise PublicationBindingError(f"invalid exact {phase} tokens")
    return list(tokens)


def _finalizer_tokens(
    amendment: Mapping[str, Any], paths: Mapping[str, Path]
) -> list[str]:
    tokens = list(amendment["execution"]["exact_finalizer_command_tokens"])
    v1 = _read_json(paths["v1_amendment"], "v1 amendment")
    if tokens != v1["execution_plan"]["exact_finalizer_command_tokens"]:
        raise PublicationBindingError("A2/v1 finalizer token mismatch")
    if tokens[:2] != [str(paths["python"]), str(paths["finalizer"])]:
        raise PublicationBindingError("finalizer executable/script token mismatch")
    for flag in (
        "--repo",
        "--source-lock",
        "--staging",
        "--official",
        "--outer-audit",
        "--host-observation",
        "--source-observation",
    ):
        if tokens.count(flag) != 1:
            raise PublicationBindingError(f"finalizer flag is not unique: {flag}")
    return tokens


def _a2_context(
    amendment_path: Path,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, str], types.ModuleType]:
    path, amendment, amendment_sha = _load_amendment(amendment_path)
    paths = _paths(amendment)
    authority = _verify_authority(path, amendment, amendment_sha, paths)
    v1 = _load_v1(amendment, paths)
    return amendment, paths, authority, v1


def build_pre_receipt(amendment_path: Path) -> tuple[dict[str, Any], Path]:
    amendment, paths, authority, v1 = _a2_context(amendment_path)
    _future_paths_absent(paths)
    hygiene = _verify_worktree_hygiene(paths["repo"], allowed_staging=None)
    document = v1.build_pre_audit(paths["v1_amendment"])
    document["publication_binding_a2"] = {
        "authority": authority,
        "hygiene": hygiene,
        "outcome_data_inspected": False,
        "passed": True,
        "schema_version": AMENDMENT_SCHEMA,
    }
    if Path(document["required_output_path"]) != paths["v1_pre"]:
        raise PublicationBindingError("v1 pre output path drift")
    return document, paths["v1_pre"]


def _relative_outputs(paths: Mapping[str, Path]) -> tuple[str, set[str]]:
    repo = paths["repo"]
    staging = paths["staging"].relative_to(repo).as_posix()
    exact = {
        paths[key].relative_to(repo).as_posix() for key in ("outer", "host", "source")
    }
    return staging, exact


def _artifact_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {
        "capture_sha256": _sha256_file(paths["staging"] / "capture.json"),
        "host_observation_sha256": _sha256_file(paths["host"]),
        "outer_audit_sha256": _sha256_file(paths["outer"]),
        "source_observation_sha256": _sha256_file(paths["source"]),
        "v1_post_audit_sha256": _sha256_file(paths["v1_post"]),
    }


def _finalizer_environment(amendment: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    policy = amendment["execution"]["finalizer_environment_policy"]
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in set(policy["removed_variables"])
    }
    environment.update(policy["fixed_overrides"])
    return environment, {
        "fixed_overrides": dict(policy["fixed_overrides"]),
        "policy_sha256": _sha256_bytes(_canonical_bytes(policy)),
        "removed_variables": list(policy["removed_variables"]),
    }


def publish(amendment_path: Path, pre_audit_path: Path) -> dict[str, Any]:
    amendment, paths, authority, v1 = _a2_context(amendment_path)
    pre_path = _plain_path(pre_audit_path, must_exist=True, label="v1 pre receipt")
    if pre_path != paths["v1_pre"]:
        raise PublicationBindingError("publish pre receipt path mismatch")
    pre = _read_json(pre_path, "v1 pre receipt")
    if pre.get("publication_binding_a2", {}).get("authority") != authority:
        raise PublicationBindingError("v1 pre receipt lacks current A2 authority")
    for key in ("anchor", "execution", "official", "partial", "v1_post", "seal"):
        if os.path.lexists(paths[key]):
            raise PublicationBindingError(f"terminal pre-existing publish path: {key}")
    staging_relative, exact_outputs = _relative_outputs(paths)
    hygiene_before = _verify_worktree_hygiene(
        paths["repo"],
        allowed_staging=staging_relative,
        allowed_exact=sorted(exact_outputs),
    )
    frozen_before = _snapshot_frozen(amendment, paths)
    post_document = v1.build_post_audit(paths["v1_amendment"], pre_path)
    hygiene_after = _verify_worktree_hygiene(
        paths["repo"],
        allowed_staging=staging_relative,
        allowed_exact=sorted(exact_outputs),
    )
    frozen_after = _snapshot_frozen(amendment, paths)
    if frozen_before != frozen_after:
        raise PublicationBindingError("frozen source/input changed during v1 post")
    post_document["publication_binding_a2"] = {
        "authority": authority,
        "frozen_snapshot": frozen_after,
        "hygiene_after": hygiene_after,
        "hygiene_before": hygiene_before,
        "outcome_data_inspected": False,
        "passed": True,
    }
    if Path(post_document["required_output_path"]) != paths["v1_post"]:
        raise PublicationBindingError("v1 post output path drift")
    post_sha = _write_json_no_replace(paths["v1_post"], post_document)
    artifacts = _artifact_hashes(paths)
    if artifacts["v1_post_audit_sha256"] != post_sha:
        raise PublicationBindingError("v1 post receipt write/hash mismatch")
    inventory = _inventory(paths["staging"])
    finalizer_tokens = _finalizer_tokens(amendment, paths)
    environment, environment_audit = _finalizer_environment(amendment)
    seal = {
        "artifact_hashes": artifacts,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "finalizer_command_sha256": _sha256_bytes(_canonical_bytes(finalizer_tokens)),
        "frozen_snapshot": frozen_after,
        "outcome_data_inspected": False,
        "outcome_payload_files_opened": False,
        "passed": True,
        "schema_version": SEAL_SCHEMA,
        "segment_json_parsed": False,
        "staging_inventory": inventory,
    }
    seal_sha = _write_json_no_replace(paths["seal"], seal)
    anchor = {
        "artifact_hashes": artifacts,
        "assessment_authorized": False,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "finalizer_launch_intent": {
            "command_sha256": _sha256_bytes(_canonical_bytes(finalizer_tokens)),
            "cwd": str(paths["repo"]),
            "environment": environment_audit,
            "exact_command_tokens": finalizer_tokens,
            "one_shot": True,
        },
        "inventory_root_sha256": inventory["root_sha256"],
        "outcome_data_inspected": False,
        "passed": True,
        "schema_version": ANCHOR_SCHEMA,
        "seal_sha256": seal_sha,
    }
    anchor_sha = _write_json_no_replace(paths["anchor"], anchor)
    if _sha256_file(paths["seal"]) != seal_sha:
        raise PublicationBindingError("seal changed after external anchoring")
    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    error_text: str | None = None
    try:
        process = subprocess.Popen(
            finalizer_tokens,
            cwd=paths["repo"],
            env=environment,
        )
        exit_code = process.wait()
    except BaseException as error:
        error_text = f"{type(error).__name__}: {error}"
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
    ended_ns = time.monotonic_ns()
    execution = {
        "anchor_sha256": anchor_sha,
        "child_pid": None if process is None else process.pid,
        "command": finalizer_tokens,
        "cwd": str(paths["repo"]),
        "elapsed_ns": ended_ns - started_ns,
        "ended_at_utc": _utc_now(),
        "environment": environment_audit,
        "error": error_text,
        "exit_code": exit_code,
        "experiment_id": "EXP-JAC-003",
        "one_shot": True,
        "outcome": "completed" if exit_code == 0 and error_text is None else "failed",
        "outcome_data_inspected": False,
        "schema_version": EXECUTION_SCHEMA,
        "seal_sha256": seal_sha,
        "started_at_utc": started_at,
    }
    execution_sha = _write_json_no_replace(paths["execution"], execution)
    if execution["outcome"] != "completed":
        raise PublicationBindingError("terminal frozen finalizer failure; rerun forbidden")
    if not paths["official"].is_dir() or os.path.lexists(paths["staging"]):
        raise PublicationBindingError("finalizer did not produce exact official archive")
    return {
        "anchor_sha256": anchor_sha,
        "execution_audit_sha256": execution_sha,
        "official_path": str(paths["official"]),
        "outcome_data_inspected": False,
        "passed": True,
        "seal_sha256": seal_sha,
    }


def _verify_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or _sha256_file(path) != expected:
        raise PublicationBindingError(f"{label} hash mismatch")


def archive(amendment_path: Path, anchor_path: Path, execution_path: Path) -> dict[str, Any]:
    amendment, paths, authority, _v1 = _a2_context(amendment_path)
    anchor_file = _plain_path(anchor_path, must_exist=True, label="A2 anchor")
    execution_file = _plain_path(
        execution_path, must_exist=True, label="A2 execution audit"
    )
    if anchor_file != paths["anchor"] or execution_file != paths["execution"]:
        raise PublicationBindingError("archive trust-root path mismatch")
    if os.path.lexists(paths["staging"]) or os.path.lexists(paths["partial"]):
        raise PublicationBindingError("staging/partial remains after finalization")
    if not paths["official"].is_dir():
        raise PublicationBindingError("official archive is absent")
    if os.path.lexists(paths["archive_receipt"]):
        raise PublicationBindingError("terminal existing archive receipt")
    anchor_sha = _sha256_file(anchor_file)
    anchor_document = _read_json(anchor_file, "A2 anchor")
    execution_sha = _sha256_file(execution_file)
    execution = _read_json(execution_file, "A2 execution audit")
    if anchor_document.get("schema_version") != ANCHOR_SCHEMA:
        raise PublicationBindingError("anchor schema mismatch")
    if (
        anchor_document.get("authority") != authority
        or anchor_document.get("passed") is not True
        or anchor_document.get("assessment_authorized") is not False
        or anchor_document.get("outcome_data_inspected") is not False
    ):
        raise PublicationBindingError("anchor authority mismatch")
    if execution.get("schema_version") != EXECUTION_SCHEMA:
        raise PublicationBindingError("execution schema mismatch")
    if (
        execution.get("anchor_sha256") != anchor_sha
        or execution.get("outcome") != "completed"
        or execution.get("exit_code") != 0
        or execution.get("error") is not None
        or execution.get("command") != _finalizer_tokens(amendment, paths)
        or execution.get("cwd") != str(paths["repo"])
        or not isinstance(execution.get("child_pid"), int)
        or isinstance(execution.get("child_pid"), bool)
        or execution.get("child_pid") <= 0
        or execution.get("one_shot") is not True
        or execution.get("outcome_data_inspected") is not False
        or execution.get("environment")
        != anchor_document["finalizer_launch_intent"]["environment"]
    ):
        raise PublicationBindingError("finalizer execution audit is not exact/successful")
    seal_path = _plain_path(
        paths["official"] / amendment["execution"]["seal_filename"],
        must_exist=True,
        label="archived A2 seal",
    )
    seal_sha = anchor_document["seal_sha256"]
    _verify_file_hash(seal_path, seal_sha, "archived seal")
    if execution.get("seal_sha256") != seal_sha:
        raise PublicationBindingError("execution/seal binding mismatch")
    seal = _read_json(seal_path, "archived A2 seal")
    if (
        seal.get("schema_version") != SEAL_SCHEMA
        or seal.get("authority") != authority
        or seal.get("passed") is not True
        or seal.get("outcome_data_inspected") is not False
        or seal.get("outcome_payload_files_opened") is not False
        or seal.get("segment_json_parsed") is not False
    ):
        raise PublicationBindingError("archived seal authority/schema mismatch")
    if seal["staging_inventory"]["root_sha256"] != anchor_document[
        "inventory_root_sha256"
    ]:
        raise PublicationBindingError("anchor inventory-root mismatch")
    expected_rows = seal["staging_inventory"]["files"]
    expected_map = {row["path"]: row for row in expected_rows}
    for relative, row in expected_map.items():
        target = _repo_path(
            paths["official"], relative, must_exist=True, label="archived inventory file"
        )
        _verify_file_hash(target, row["sha256"], f"archived {relative}")
        if target.stat().st_size != row["size"]:
            raise PublicationBindingError(f"archived {relative} size mismatch")
    artifacts = anchor_document["artifact_hashes"]
    if artifacts != seal["artifact_hashes"]:
        raise PublicationBindingError("anchor/seal artifact hashes differ")
    _verify_file_hash(
        paths["official"] / "capture.json", artifacts["capture_sha256"], "capture"
    )
    _verify_file_hash(
        paths["official"] / amendment["execution"]["v1_post_audit_filename"],
        artifacts["v1_post_audit_sha256"],
        "v1 post receipt",
    )
    copy_map = {
        "audit/formal-run-audit.json": (paths["outer"], "outer_audit_sha256"),
        "audit/host-observation.json": (paths["host"], "host_observation_sha256"),
        "audit/source-observation.json": (paths["source"], "source_observation_sha256"),
    }
    for relative, (external, hash_key) in copy_map.items():
        _verify_file_hash(external, artifacts[hash_key], f"external {relative}")
        _verify_file_hash(
            paths["official"].joinpath(*PurePosixPath(relative).parts),
            artifacts[hash_key],
            f"archived {relative}",
        )
    capture = _read_json(paths["official"] / "capture.json", "capture metadata")
    manifest_path = paths["official"] / "formal-run-manifest.json"
    manifest = _read_json(manifest_path, "formal run manifest")
    if (
        manifest.get("schema_version") != RUN_SCHEMA
        or manifest.get("atomically_published") is not True
        or manifest.get("segments") != capture.get("segments")
        or manifest.get("sequence") != capture.get("sequence")
        or manifest.get("child_exit_codes") != [0, 0, 0, 0]
        or manifest.get("candidate_input_uncompressed_sha256")
        != capture.get("candidate_input_uncompressed_sha256")
        or manifest.get("input_manifest_sha256")
        != capture.get("input_manifest_sha256")
        or manifest.get("julia_manifest_sha256")
        != capture.get("julia_manifest_sha256")
        or manifest.get("source_lock_sha256")
        != capture.get("source_lock_sha256")
        or manifest.get("fresh_process_count") != 4
        or manifest.get("fresh_writable_depot_count") != 4
        or manifest.get("source_hash_mismatch_count") != 0
        or manifest.get("input_hash_mismatch_count") != 0
        or manifest.get("staging_mismatch_count") != 0
        or manifest.get("host_contention_event_count") != 0
        or manifest.get("lease_loss_count") != 0
        or manifest.get("audit_sha256")
        != {
            "formal": artifacts["outer_audit_sha256"],
            "host": artifacts["host_observation_sha256"],
            "source": artifacts["source_observation_sha256"],
        }
    ):
        raise PublicationBindingError("formal run manifest/capture binding mismatch")
    segments = capture.get("segments")
    if not isinstance(segments, list) or len(segments) != 4:
        raise PublicationBindingError("capture segment metadata topology mismatch")
    for row in segments:
        relative = row.get("trace_path")
        expected = row.get("trace_sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise PublicationBindingError("capture trace metadata is invalid")
        trace = _repo_path(
            paths["official"], relative, must_exist=True, label="opaque segment trace"
        )
        _verify_file_hash(trace, expected, "opaque segment trace")
    current_inventory = _inventory(paths["official"])
    current_paths = {row["path"] for row in current_inventory["files"]}
    expected_paths = set(expected_map) | {
        amendment["execution"]["seal_filename"],
        "audit/formal-run-audit.json",
        "audit/host-observation.json",
        "audit/source-observation.json",
        "formal-run-manifest.json",
    }
    if current_paths != expected_paths:
        raise PublicationBindingError("official archive membership mismatch")
    receipt = {
        "anchor_sha256": anchor_sha,
        "archived_file_count_before_receipt": current_inventory["file_count"],
        "archived_inventory_root_sha256_before_receipt": current_inventory[
            "root_sha256"
        ],
        "assessment_authorized": True,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "execution_audit_sha256": execution_sha,
        "experiment_id": "EXP-JAC-003",
        "numerical_rerun_performed": False,
        "outcome_data_inspected": False,
        "outcome_payload_files_opened": False,
        "passed": True,
        "schema_version": ARCHIVE_SCHEMA,
        "seal_sha256": seal_sha,
        "segment_json_parsed": False,
    }
    receipt_sha = _write_json_no_replace(paths["archive_receipt"], receipt)
    return {
        "archive_receipt_path": str(paths["archive_receipt"]),
        "archive_receipt_sha256": receipt_sha,
        "assessment_authorized": True,
        "outcome_data_inspected": False,
        "passed": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    phases = parser.add_subparsers(dest="phase", required=True)
    pre = phases.add_parser("pre")
    pre.add_argument("--amendment", required=True, type=Path)
    pre.add_argument("--output", required=True, type=Path)
    publish_parser = phases.add_parser("publish")
    publish_parser.add_argument("--amendment", required=True, type=Path)
    publish_parser.add_argument("--pre-audit", required=True, type=Path)
    archive_parser = phases.add_parser("archive")
    archive_parser.add_argument("--amendment", required=True, type=Path)
    archive_parser.add_argument("--anchor", required=True, type=Path)
    archive_parser.add_argument("--execution-audit", required=True, type=Path)
    archive_parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        _path, amendment, _sha = _load_amendment(arguments.amendment)
        actual = [str(Path(sys.executable).resolve()), str(Path(__file__).resolve())]
        actual.extend(sys.argv[1:] if argv is None else list(argv))
        if actual != _phase_tokens(amendment, arguments.phase):
            raise PublicationBindingError(
                f"actual {arguments.phase} command tokens differ from frozen plan"
            )
        if arguments.phase == "pre":
            document, required = build_pre_receipt(arguments.amendment)
            supplied = _plain_path(arguments.output, must_exist=False, label="pre output")
            if supplied != required:
                raise PublicationBindingError("pre output is not fixed v1 path")
            _write_json_no_replace(required, document)
            result: dict[str, Any] = {
                "outcome_data_inspected": False,
                "passed": True,
                "pre_audit_path": str(required),
            }
        elif arguments.phase == "publish":
            result = publish(arguments.amendment, arguments.pre_audit)
        else:
            supplied = _plain_path(
                arguments.output, must_exist=False, label="archive output"
            )
            paths = _paths(amendment)
            if supplied != paths["archive_receipt"]:
                raise PublicationBindingError("archive output is not fixed receipt path")
            result = archive(
                arguments.amendment, arguments.anchor, arguments.execution_audit
            )
    except BaseException as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
