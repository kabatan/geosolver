"""Outcome-blind execution binding for the frozen EXP-JAC-003 formal run.

This checker is deliberately not a wrapper around ``formal_abba.py``.  Run the
``pre`` phase before the exclusive runner and the ``post`` phase after it has
exited.  Neither phase decompresses candidate/truth/K0 artifacts or opens a
segment trace.
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
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


AMENDMENT_SCHEMA = "exp-jac-003-formal-binding-amendment/v1"
AUDIT_SCHEMA = "exp-jac-003-formal-binding-audit/v1"
SOURCE_LOCK_SCHEMA = "exp-jac-003-development-source-lock/v1"
CAPTURE_SCHEMA = "exp-jac-003-formal-abba-capture/v1"
OUTER_AUDIT_SCHEMA = "geotarget.formal-performance-run/v1"
HOST_SCHEMA = "exp-jac-003-host-observation/v1"
SOURCE_OBSERVATION_SCHEMA = "exp-jac-003-source-observation/v1"


class BindingError(RuntimeError):
    """A fail-closed execution-binding violation."""


class Checks:
    """Retain the successful prefix and the first fail-closed check."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def require(self, condition: bool, code: str, detail: str) -> None:
        self.rows.append({"code": code, "detail": detail, "passed": bool(condition)})
        if not condition:
            raise BindingError(f"{code}: {detail}")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BindingError(f"cannot read {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise BindingError(f"{label} must contain one JSON object")
    return value


def _write_json_once(path: Path, document: Mapping[str, Any]) -> None:
    path = _absolute_plain_path(path, must_exist=False, kind="audit output")
    if os.path.lexists(path):
        raise BindingError(f"audit output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_plain_components(path.parent, "audit output parent")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        payload = (
            json.dumps(
                dict(document),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _assert_plain_components(path: Path, label: str) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    components = absolute.parts[1:] if absolute.anchor else absolute.parts
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for component in components:
        current /= component
        if not os.path.lexists(current):
            break
        metadata = os.lstat(current)
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_flag:
            raise BindingError(f"{label} traverses a symlink/reparse point: {current}")


def _absolute_plain_path(path: Path, *, must_exist: bool, kind: str) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    absolute = Path(os.path.abspath(expanded))
    _assert_plain_components(absolute, kind)
    if must_exist and not absolute.exists():
        raise BindingError(f"{kind} does not exist: {absolute}")
    resolved = absolute.resolve(strict=must_exist)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(absolute)):
        raise BindingError(f"{kind} is not a canonical plain path: {absolute}")
    return absolute


def _relative_repo_path(
    repo: Path, relative: str, *, must_exist: bool, kind: str
) -> Path:
    if not relative or "\\" in relative:
        raise BindingError(f"{kind} must be a nonempty POSIX relative path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise BindingError(f"{kind} is not a canonical repository-relative path")
    target = repo.joinpath(*pure.parts)
    target = _absolute_plain_path(target, must_exist=must_exist, kind=kind)
    try:
        target.relative_to(repo)
    except ValueError as error:
        raise BindingError(f"{kind} escapes the frozen repository") from error
    return target


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
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise BindingError(f"git {' '.join(arguments)} failed: {detail}") from error
    return result.stdout.strip()


def _load_amendment(path: Path, checks: Checks) -> tuple[Path, dict[str, Any], str]:
    amendment_path = _absolute_plain_path(path, must_exist=True, kind="amendment")
    payload = amendment_path.read_bytes()
    amendment = _read_json(amendment_path, "amendment")
    checks.require(
        amendment.get("schema_version") == AMENDMENT_SCHEMA,
        "amendment-schema",
        "formal binding amendment schema must be frozen v1",
    )
    checks.require(
        amendment.get("experiment_id") == "EXP-JAC-003",
        "amendment-experiment",
        "amendment must bind EXP-JAC-003",
    )
    checks.require(
        amendment.get("status") == "frozen-outcome-blind-before-formal-run",
        "amendment-status",
        "amendment must be frozen before formal outcomes",
    )
    checks.require(
        amendment.get("outcome_blind_attestation", {}).get("any_outcome_opened")
        is False,
        "amendment-outcome-blind",
        "amendment attestation must deny all outcome access",
    )
    return amendment_path, amendment, _sha256_bytes(payload)


def _verify_checker_authority(
    amendment_path: Path,
    amendment: Mapping[str, Any],
    amendment_sha256: str,
    checks: Checks,
) -> dict[str, str]:
    authority_root = _absolute_plain_path(
        Path(amendment["authority_repository_root"]),
        must_exist=True,
        kind="authority repository",
    )
    discovered_root = _absolute_plain_path(
        Path(_git(authority_root, "rev-parse", "--show-toplevel")),
        must_exist=True,
        kind="authority git root",
    )
    checks.require(
        discovered_root == authority_root,
        "authority-root",
        "authority repository root must be exact",
    )
    expected_amendment = _relative_repo_path(
        authority_root,
        amendment["amendment_relative_path"],
        must_exist=True,
        kind="committed amendment",
    )
    checks.require(
        expected_amendment == amendment_path,
        "amendment-path",
        "invoked amendment path must equal the frozen authority path",
    )
    checker = _relative_repo_path(
        authority_root,
        amendment["checker"]["relative_path"],
        must_exist=True,
        kind="binding checker",
    )
    expected_checker_sha = amendment["checker"]["sha256"]
    checks.require(
        _sha256_file(checker) == expected_checker_sha,
        "checker-hash",
        "authority checker hash must match amendment",
    )
    checks.require(
        _sha256_file(Path(__file__).resolve()) == expected_checker_sha,
        "executing-checker-hash",
        "executing checker bytes must match the committed authority checker",
    )
    relative_amendment = amendment_path.relative_to(authority_root).as_posix()
    relative_checker = checker.relative_to(authority_root).as_posix()
    for relative in (relative_amendment, relative_checker):
        _git(authority_root, "ls-files", "--error-unmatch", "--", relative)
    tracked_diff = _git(
        authority_root,
        "status",
        "--porcelain",
        "--",
        relative_amendment,
        relative_checker,
    )
    checks.require(
        tracked_diff == "",
        "authority-clean-files",
        "amendment and checker must be committed and unmodified",
    )
    amendment_commit = _git(
        authority_root, "log", "-1", "--format=%H", "--", relative_amendment
    )
    checker_commit = _git(
        authority_root, "log", "-1", "--format=%H", "--", relative_checker
    )
    checks.require(
        bool(amendment_commit) and bool(checker_commit),
        "authority-commits",
        "amendment and checker must have committed provenance",
    )
    checks.require(
        amendment_commit == checker_commit,
        "joint-authority-commit",
        "amendment and checker must be frozen by the same pre-outcome commit",
    )
    return {
        "amendment_commit": amendment_commit,
        "amendment_sha256": amendment_sha256,
        "checker_commit": checker_commit,
        "checker_sha256": expected_checker_sha,
    }


def _expected_paths(amendment: Mapping[str, Any], checks: Checks) -> dict[str, Path]:
    frozen = amendment["frozen_execution"]
    repo = _absolute_plain_path(
        Path(frozen["repository_root"]), must_exist=True, kind="frozen repository"
    )
    paths: dict[str, Path] = {"repo": repo}
    for key, descriptor in amendment["official_inputs"].items():
        paths[key] = _relative_repo_path(
            repo,
            descriptor["relative_path"],
            must_exist=True,
            kind=f"official input {key}",
        )
    execution = amendment["execution_plan"]
    for key in (
        "source_lock",
        "julia_manifest",
        "formal_runner",
        "finalizer",
        "exclusive_runner",
    ):
        paths[key] = _relative_repo_path(
            repo,
            execution[f"{key}_relative_path"],
            must_exist=True,
            kind=key.replace("_", " "),
        )
    for key in (
        "staging",
        "partial",
        "official",
        "outer_audit",
        "host_observation",
        "source_observation",
    ):
        paths[key] = _relative_repo_path(
            repo,
            execution[f"{key}_relative_path"],
            must_exist=False,
            kind=key.replace("_", " "),
        )
    paths["pre_binding_audit"] = _absolute_plain_path(
        Path(execution["pre_binding_audit_path"]),
        must_exist=False,
        kind="pre-binding audit output",
    )
    paths["post_binding_audit"] = _absolute_plain_path(
        paths["staging"] / execution["post_binding_audit_filename"],
        must_exist=False,
        kind="post-binding audit output",
    )
    paths["python"] = _absolute_plain_path(
        Path(execution["python_executable"]), must_exist=True, kind="Python executable"
    )
    paths["julia"] = _absolute_plain_path(
        Path(execution["julia_executable"]), must_exist=True, kind="Julia executable"
    )
    checks.require(
        len({os.path.normcase(str(path)) for path in paths.values()}) == len(paths),
        "path-aliases",
        "all bound roles must resolve to distinct canonical paths",
    )
    return paths


def _verify_frozen_repository(
    amendment: Mapping[str, Any],
    paths: Mapping[str, Path],
    checks: Checks,
    *,
    pre: bool,
) -> dict[str, Any]:
    frozen = amendment["frozen_execution"]
    repo = paths["repo"]
    head = _git(repo, "rev-parse", "HEAD")
    parent = _git(repo, "rev-parse", "HEAD^")
    checks.require(
        head == frozen["head_commit"],
        "frozen-head",
        "frozen worktree HEAD must equal the source-lock commit",
    )
    checks.require(
        parent == frozen["source_commit"],
        "frozen-parent",
        "source-lock commit must be the sole child of the source commit",
    )
    status_arguments = ["status", "--porcelain"]
    if not pre:
        status_arguments.append("--untracked-files=no")
    status = _git(repo, *status_arguments)
    checks.require(
        status == "",
        "frozen-worktree-clean" if pre else "frozen-tracked-files-clean",
        "pre-run worktree must be fully clean"
        if pre
        else "post-run tracked files and index must be unchanged",
    )
    relative_lock = paths["source_lock"].relative_to(repo).as_posix()
    lock_commit = _git(repo, "log", "-1", "--format=%H", "--", relative_lock)
    checks.require(
        lock_commit == head,
        "source-lock-commit",
        "HEAD must be the commit that introduced the source lock",
    )
    source_lock_sha = _sha256_file(paths["source_lock"])
    checks.require(
        source_lock_sha == frozen["source_lock_sha256"],
        "source-lock-hash",
        "source lock bytes must match the amendment",
    )
    source_lock = _read_json(paths["source_lock"], "source lock")
    checks.require(
        source_lock.get("schema_version") == SOURCE_LOCK_SCHEMA,
        "source-lock-schema",
        "source lock schema must be frozen v1",
    )
    checks.require(
        source_lock.get("source_commit") == frozen["source_commit"],
        "source-lock-lineage",
        "source lock embedded source commit must match",
    )
    mismatches: list[str] = []
    for relative, expected in source_lock["files"].items():
        target = _relative_repo_path(
            repo, relative, must_exist=True, kind=f"source-lock file {relative}"
        )
        if _sha256_file(target) != expected:
            mismatches.append(relative)
    checks.require(
        not mismatches,
        "source-lock-files",
        f"all {len(source_lock['files'])} locked files must match; mismatches={mismatches}",
    )
    checks.require(
        _sha256_file(paths["julia_manifest"]) == frozen["julia_manifest_sha256"],
        "julia-manifest-hash",
        "Julia Manifest must match the frozen environment",
    )
    checks.require(
        _sha256_file(paths["formal_runner"])
        == amendment["execution_plan"]["formal_runner_sha256"],
        "formal-runner-hash",
        "formal runner must match its frozen bytes",
    )
    checks.require(
        _sha256_file(paths["finalizer"])
        == amendment["execution_plan"]["finalizer_sha256"],
        "finalizer-hash",
        "finalizer must match its frozen bytes",
    )
    checks.require(
        _sha256_file(paths["exclusive_runner"])
        == amendment["execution_plan"]["exclusive_runner_sha256"],
        "exclusive-runner-hash",
        "exclusive runner must match its outcome-blind binding",
    )
    artifact_lock_fields = {
        "manifest": "development_manifest_sha256",
        "candidate": "candidate_compressed_sha256",
        "truth": "assessor_compressed_sha256",
        "frozen_k0": "k0_compressed_sha256",
    }
    for key, lock_field in artifact_lock_fields.items():
        expected = amendment["official_inputs"][key]["sha256"]
        checks.require(
            _sha256_file(paths[key]) == expected,
            f"official-{key}-hash",
            f"official {key} must match amendment hash",
        )
        checks.require(
            source_lock["input_artifacts"][lock_field] == expected,
            f"source-lock-{key}-binding",
            f"source lock must bind official {key}",
        )
    manifest = _read_json(paths["manifest"], "development input manifest")
    descriptor_keys = {
        "candidate": "candidate",
        "truth": "assessor",
        "frozen_k0": "k0_control",
    }
    for key, descriptor_key in descriptor_keys.items():
        descriptor = manifest["artifacts"][descriptor_key]
        expected = amendment["official_inputs"][key]
        checks.require(
            descriptor["path"] == PurePosixPath(expected["relative_path"]).name
            and descriptor["compressed_sha256"] == expected["sha256"]
            and descriptor["uncompressed_sha256"] == expected["uncompressed_sha256"],
            f"manifest-{key}-binding",
            f"manifest descriptor must bind official {key} without opening its payload",
        )
    return {
        "head_commit": head,
        "locked_file_count": len(source_lock["files"]),
        "locked_file_hash_mismatch_count": len(mismatches),
        "source_commit": parent,
        "source_lock_sha256": source_lock_sha,
    }


def _command_plan(
    amendment: Mapping[str, Any], paths: Mapping[str, Path], checks: Checks
) -> dict[str, Any]:
    execution = amendment["execution_plan"]
    child = [
        str(paths["python"]),
        str(paths["formal_runner"]),
        "--repo",
        str(paths["repo"]),
        "--source-lock",
        str(paths["source_lock"]),
        "--input-manifest",
        str(paths["manifest"]),
        "--candidate",
        str(paths["candidate"]),
        "--truth",
        str(paths["truth"]),
        "--frozen-k0",
        str(paths["frozen_k0"]),
        "--staging",
        str(paths["staging"]),
        "--julia",
        str(paths["julia"]),
    ]
    exclusive = [
        str(paths["python"]),
        str(paths["exclusive_runner"]),
        "--label",
        execution["label"],
        "--audit",
        str(paths["outer_audit"]),
        "--cwd",
        str(paths["repo"]),
        "--",
        *child,
    ]
    finalizer = [
        str(paths["python"]),
        str(paths["finalizer"]),
        "--repo",
        str(paths["repo"]),
        "--source-lock",
        str(paths["source_lock"]),
        "--staging",
        str(paths["staging"]),
        "--official",
        str(paths["official"]),
        "--outer-audit",
        str(paths["outer_audit"]),
        "--host-observation",
        str(paths["host_observation"]),
        "--source-observation",
        str(paths["source_observation"]),
    ]
    checks.require(
        child == execution["exact_child_command_tokens"],
        "exact-child-command",
        "computed direct-child command must equal the frozen token array",
    )
    checks.require(
        exclusive == execution["exact_exclusive_command_tokens"],
        "exact-exclusive-command",
        "computed exclusive command must equal the frozen token array",
    )
    checks.require(
        finalizer == execution["exact_finalizer_command_tokens"],
        "exact-finalizer-command",
        "computed finalizer command must equal the frozen token array",
    )
    for flag in (
        "--repo",
        "--source-lock",
        "--input-manifest",
        "--candidate",
        "--truth",
        "--frozen-k0",
        "--staging",
        "--julia",
    ):
        checks.require(
            child.count(flag) == 1,
            f"unique-{flag[2:]}",
            f"{flag} must occur exactly once; duplicate flags are forbidden",
        )
    return {
        "child_command_tokens": child,
        "cwd": str(paths["repo"]),
        "exclusive_command_tokens": exclusive,
        "finalizer_command_tokens": finalizer,
        "label": execution["label"],
    }


def build_pre_audit(
    amendment_path: Path, *, checks: Checks | None = None
) -> dict[str, Any]:
    checks = checks or Checks()
    path, amendment, amendment_sha = _load_amendment(amendment_path, checks)
    authority = _verify_checker_authority(path, amendment, amendment_sha, checks)
    paths = _expected_paths(amendment, checks)
    frozen = _verify_frozen_repository(amendment, paths, checks, pre=True)
    for key in (
        "staging",
        "partial",
        "official",
        "outer_audit",
        "host_observation",
        "source_observation",
        "pre_binding_audit",
        "post_binding_audit",
    ):
        checks.require(
            not os.path.lexists(paths[key]),
            f"absent-{key}",
            f"pre-run {key.replace('_', ' ')} path must not exist",
        )
    plan = _command_plan(amendment, paths, checks)
    return {
        "authority": authority,
        "checks": checks.rows,
        "command_plan": plan,
        "experiment_id": "EXP-JAC-003",
        "frozen_binding": frozen,
        "generated_at_utc": _utc_now(),
        "outcome_data_inspected": False,
        "outcome_payload_files_opened": False,
        "passed": True,
        "phase": "pre",
        "required_output_path": str(paths["pre_binding_audit"]),
        "schema_version": AUDIT_SCHEMA,
    }


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise BindingError(f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise BindingError(f"{label} is not ISO-8601") from error
    if parsed.tzinfo is None:
        raise BindingError(f"{label} must include a timezone")
    return parsed


def build_post_audit(
    amendment_path: Path,
    pre_audit_path: Path,
    *,
    checks: Checks | None = None,
) -> dict[str, Any]:
    checks = checks or Checks()
    path, amendment, amendment_sha = _load_amendment(amendment_path, checks)
    authority = _verify_checker_authority(path, amendment, amendment_sha, checks)
    paths = _expected_paths(amendment, checks)
    frozen = _verify_frozen_repository(amendment, paths, checks, pre=False)
    plan = _command_plan(amendment, paths, checks)

    pre_path = _absolute_plain_path(
        pre_audit_path, must_exist=True, kind="pre-binding audit"
    )
    checks.require(
        pre_path == paths["pre_binding_audit"],
        "pre-audit-path",
        "post phase must consume the amendment-frozen pre-audit path",
    )
    pre_sha = _sha256_file(pre_path)
    pre = _read_json(pre_path, "pre-binding audit")
    checks.require(
        pre.get("schema_version") == AUDIT_SCHEMA
        and pre.get("phase") == "pre"
        and pre.get("passed") is True
        and pre.get("outcome_data_inspected") is False
        and pre.get("outcome_payload_files_opened") is False,
        "pre-audit-state",
        "pre-binding audit must be a successful outcome-blind v1 audit",
    )
    checks.require(
        pre.get("authority") == authority,
        "pre-audit-authority",
        "pre-binding amendment/checker authority must be unchanged",
    )
    checks.require(
        pre.get("frozen_binding") == frozen,
        "pre-audit-frozen-binding",
        "frozen HEAD/source/input binding must be unchanged",
    )
    checks.require(
        pre.get("command_plan") == plan,
        "pre-audit-command",
        "formal command plan must be byte-for-byte equivalent",
    )

    checks.require(
        paths["staging"].is_dir(),
        "staging-present",
        "completed nonofficial staging directory must exist",
    )
    checks.require(
        not os.path.lexists(paths["partial"]),
        "partial-absent",
        "partial staging directory must not remain",
    )
    checks.require(
        not os.path.lexists(paths["official"]),
        "official-absent",
        "official result must not exist before binding and finalization",
    )
    checks.require(
        not os.path.lexists(paths["post_binding_audit"]),
        "post-audit-absent",
        "post-binding audit must be created exactly once by this invocation",
    )
    outer = _read_json(
        _absolute_plain_path(paths["outer_audit"], must_exist=True, kind="outer audit"),
        "outer audit",
    )
    checks.require(
        outer.get("schema") == OUTER_AUDIT_SCHEMA,
        "outer-audit-schema",
        "exclusive-run audit schema must match",
    )
    checks.require(
        outer.get("label") == plan["label"],
        "outer-audit-label",
        "exclusive-run label must match exactly",
    )
    checks.require(
        outer.get("cwd") == plan["cwd"],
        "outer-audit-cwd",
        "exclusive-run cwd must be the canonical frozen repository",
    )
    checks.require(
        outer.get("command") == plan["child_command_tokens"],
        "outer-audit-command",
        "executed direct-child tokens must exactly match the precommitted plan",
    )
    checks.require(
        outer.get("outcome") == "completed"
        and outer.get("exit_code") == 0
        and outer.get("error") is None,
        "outer-audit-completion",
        "exclusive run must complete once with exit code zero",
    )
    outer_child_pid = outer.get("child_pid")
    checks.require(
        isinstance(outer_child_pid, int)
        and not isinstance(outer_child_pid, bool)
        and outer_child_pid > 0,
        "outer-child-pid",
        "outer audit must bind the direct formal runner PID",
    )

    capture_path = _absolute_plain_path(
        paths["staging"] / "capture.json", must_exist=True, kind="capture metadata"
    )
    capture = _read_json(capture_path, "capture metadata")
    expected_sequence = amendment["execution_plan"]["abba_sequence"]
    checks.require(
        capture.get("schema_version") == CAPTURE_SCHEMA
        and capture.get("experiment_id") == "EXP-JAC-003"
        and capture.get("capture_complete") is True
        and capture.get("outcomes_inspected_by_orchestrator") is False,
        "capture-state",
        "capture must be complete and outcome-blind",
    )
    checks.require(
        capture.get("lock_commit") == amendment["frozen_execution"]["head_commit"]
        and capture.get("source_lock_sha256") == frozen["source_lock_sha256"]
        and capture.get("input_manifest_sha256")
        == amendment["official_inputs"]["manifest"]["sha256"]
        and capture.get("candidate_input_uncompressed_sha256")
        == amendment["official_inputs"]["candidate"]["uncompressed_sha256"]
        and capture.get("julia_manifest_sha256")
        == amendment["frozen_execution"]["julia_manifest_sha256"],
        "capture-hash-bindings",
        "capture metadata must bind the exact frozen source and official inputs",
    )
    child_pids = capture.get("child_pids")
    segment_metadata = capture.get("segments")
    checks.require(
        capture.get("sequence") == expected_sequence
        and capture.get("child_exit_codes") == [0, 0, 0, 0]
        and capture.get("fresh_process_count") == 4
        and capture.get("fresh_writable_depot_count") == 4
        and isinstance(child_pids, list)
        and len(child_pids) == 4
        and all(
            isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
            for pid in child_pids
        )
        and len(set(child_pids)) == 4,
        "capture-topology",
        "capture must bind one complete fresh-process ABBA sequence",
    )
    checks.require(
        isinstance(segment_metadata, list)
        and len(segment_metadata) == 4
        and [row.get("slot") for row in segment_metadata] == [0, 1, 2, 3]
        and [row.get("variant") for row in segment_metadata] == expected_sequence
        and [row.get("child_pid") for row in segment_metadata] == child_pids
        and [row.get("exit_code") for row in segment_metadata] == [0, 0, 0, 0],
        "capture-segment-metadata",
        "capture metadata must bind ordered variants, PIDs and zero exits without opening traces",
    )

    host = _read_json(
        _absolute_plain_path(
            paths["host_observation"], must_exist=True, kind="host observation"
        ),
        "host observation",
    )
    checks.require(
        host.get("schema_version") == HOST_SCHEMA
        and host.get("label") == plan["label"]
        and host.get("template_only") is False,
        "host-observation-schema",
        "host observation must be a completed non-template record",
    )
    checks.require(
        host.get("formal_outer_pid") == outer_child_pid
        and host.get("formal_segment_pids") == child_pids,
        "host-observation-pids",
        "host observer must bind outer and segment PIDs",
    )
    checks.require(
        host.get("host_contention_event_count") == 0
        and host.get("lease_loss_count") == 0
        and host.get("all_formal_pids_ended") is True
        and host.get("outcomes_inspected") is False,
        "host-observation-safety",
        "host observer must report no contention, lease loss, live PID or outcome access",
    )
    checks.require(
        _parse_utc(host.get("observation_started_at_utc"), "host start")
        <= _parse_utc(outer.get("started_at_utc"), "outer start")
        and _parse_utc(host.get("observation_ended_at_utc"), "host end")
        >= _parse_utc(outer.get("ended_at_utc"), "outer end"),
        "host-observation-interval",
        "host observation must cover the complete exclusive-run interval",
    )

    source = _read_json(
        _absolute_plain_path(
            paths["source_observation"], must_exist=True, kind="source observation"
        ),
        "source observation",
    )
    checks.require(
        source.get("schema_version") == SOURCE_OBSERVATION_SCHEMA
        and source.get("template_only") is False,
        "source-observation-schema",
        "source observation must be a completed non-template record",
    )
    checks.require(
        source.get("head_commit") == frozen["head_commit"]
        and source.get("source_lock_sha256") == frozen["source_lock_sha256"]
        and source.get("source_hash_mismatch_count") == 0,
        "source-observation-source",
        "source observer must bind the frozen HEAD and exact source lock",
    )
    checks.require(
        source.get("manifest_match") is True and source.get("input_match") is True,
        "source-observation-inputs",
        "manifest_match and input_match must both be explicitly true",
    )
    checks.require(
        source.get("outcomes_inspected") is False,
        "source-observation-outcome-blind",
        "source observer must not inspect outcomes",
    )
    checks.require(
        source.get("formal_binding_amendment_sha256") == amendment_sha
        and source.get("formal_binding_checker_sha256") == authority["checker_sha256"]
        and source.get("formal_binding_pre_audit_sha256") == pre_sha,
        "source-observation-binding-chain",
        "source observation must hash-bind amendment, checker and pre-audit",
    )

    return {
        "authority": authority,
        "checks": checks.rows,
        "command_plan_sha256": _sha256_bytes(_canonical_bytes(plan)),
        "experiment_id": "EXP-JAC-003",
        "frozen_binding": frozen,
        "generated_at_utc": _utc_now(),
        "host_and_source_binding_valid": True,
        "input_binding_valid": True,
        "outcome_data_inspected": False,
        "outcome_payload_files_opened": False,
        "passed": True,
        "phase": "post",
        "pre_audit_sha256": pre_sha,
        "required_output_path": str(paths["post_binding_audit"]),
        "schema_version": AUDIT_SCHEMA,
        "segment_trace_files_opened": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="phase", required=True)
    for phase in ("pre", "post"):
        child = subparsers.add_parser(phase)
        child.add_argument("--amendment", required=True, type=Path)
        child.add_argument("--output", required=True, type=Path)
        if phase == "post":
            child.add_argument("--pre-audit", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    checks = Checks()
    try:
        if arguments.phase == "pre":
            document = build_pre_audit(arguments.amendment, checks=checks)
        else:
            document = build_post_audit(
                arguments.amendment, arguments.pre_audit, checks=checks
            )
        supplied_output = _absolute_plain_path(
            arguments.output, must_exist=False, kind="requested audit output"
        )
        checks.require(
            str(supplied_output) == document["required_output_path"],
            "audit-output-path",
            "audit output must equal the amendment-frozen phase path",
        )
    except BaseException as error:
        document = {
            "checks": checks.rows,
            "error": f"{type(error).__name__}: {error}",
            "experiment_id": "EXP-JAC-003",
            "generated_at_utc": _utc_now(),
            "outcome_data_inspected": False,
            "outcome_payload_files_opened": False,
            "passed": False,
            "phase": arguments.phase,
            "schema_version": AUDIT_SCHEMA,
            "segment_trace_files_opened": False,
        }
        try:
            _write_json_once(arguments.output, document)
        except BaseException as write_error:
            print(
                f"binding guard failed and audit write failed: {write_error}",
                file=sys.stderr,
            )
        print(document["error"], file=sys.stderr)
        return 2
    _write_json_once(arguments.output, document)
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
