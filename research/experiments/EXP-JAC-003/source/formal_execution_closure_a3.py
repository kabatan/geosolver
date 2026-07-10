"""A3 execution closure for the result-blind EXP-JAC-003 formal workflow.

A2 remains immutable.  A3 adds continuous source windows, a stable single-byte
archive verifier, a host-identity receipt binding, and an assessment blockade.
Segment JSON and compressed candidate/truth/K0 payloads are never parsed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import time
import types
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


AMENDMENT_SCHEMA = "exp-jac-003-formal-execution-closure-amendment-a3/v1"
SOURCE_WINDOW_SCHEMA = "exp-jac-003-source-window-receipt-a3/v1"
ARCHIVE_SCHEMA = "exp-jac-003-execution-closure-receipt-a3/v1"
ASSESSMENT_SCHEMA = "exp-jac-003-assessment-execution-audit-a3/v1"


class ExecutionClosureError(RuntimeError):
    """A terminal A3 execution-closure violation."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ExecutionClosureError(f"{label} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExecutionClosureError(f"invalid {label}") from error
    if parsed.tzinfo is None:
        raise ExecutionClosureError(f"{label} lacks timezone")
    return parsed


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutionClosureError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ExecutionClosureError(f"{label} must be one JSON object")
    return value


def _read_once(path: Path, label: str) -> tuple[bytes, str, dict[str, Any]]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ExecutionClosureError(f"cannot read {label}: {error}") from error
    return payload, _sha(payload), _json_bytes(payload, label)


def _load_a2(path: Path, expected_sha: str) -> types.ModuleType:
    payload = path.read_bytes()
    if _sha(payload) != expected_sha:
        raise ExecutionClosureError("A2 checker hash drift")
    module = types.ModuleType("exp_jac_003_publication_guard_a2_approved")
    module.__file__ = str(path)
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


def _load_amendment(path: Path) -> tuple[Path, dict[str, Any], str]:
    absolute = Path(os.path.abspath(path))
    payload = absolute.read_bytes()
    amendment = _json_bytes(payload, "A3 amendment")
    if amendment.get("schema_version") != AMENDMENT_SCHEMA:
        raise ExecutionClosureError("A3 amendment schema mismatch")
    if amendment.get("experiment_id") != "EXP-JAC-003":
        raise ExecutionClosureError("A3 experiment mismatch")
    if (
        amendment.get("outcome_blind_attestation", {}).get("any_outcome_opened")
        is not False
    ):
        raise ExecutionClosureError("A3 amendment is not outcome-blind")
    return absolute, amendment, _sha(payload)


def _paths(amendment: Mapping[str, Any]) -> dict[str, Path]:
    execution = amendment["execution"]
    root = Path(amendment["authority_repository_root"])
    repo = Path(amendment["frozen_repository_root"])
    official = repo / PurePosixPath(execution["official_relative_path"])
    staging = repo / PurePosixPath(execution["staging_relative_path"])
    return {
        "authority_root": root,
        "repo": repo,
        "amendment": root / PurePosixPath(amendment["amendment_relative_path"]),
        "checker": root / PurePosixPath(amendment["checker"]["relative_path"]),
        "a2_amendment": root
        / PurePosixPath(amendment["a2_authority"]["amendment_relative_path"]),
        "a2_checker": root
        / PurePosixPath(amendment["a2_authority"]["checker_relative_path"]),
        "v1_pre": Path(execution["v1_pre_audit_path"]),
        "source_window": Path(execution["source_window_receipt_path"]),
        "anchor": Path(execution["a2_anchor_path"]),
        "finalizer_execution": Path(execution["a2_execution_audit_path"]),
        "host_receipt": Path(execution["host_identity_receipt_path"]),
        "host_ready": Path(execution["host_ready_receipt_path"]),
        "staging": staging,
        "partial": repo / PurePosixPath(execution["partial_relative_path"]),
        "official": official,
        "a2_archive": official / execution["a2_archive_receipt_filename"],
        "seal": official / execution["a2_seal_filename"],
        "capture": official / "capture.json",
        "manifest": official / "formal-run-manifest.json",
        "a3_archive": official / execution["a3_archive_receipt_filename"],
        "summary": official / execution["assessment_output_filename"],
        "assessment_audit": Path(execution["assessment_audit_path"]),
        "python": Path(execution["python_executable"]),
        "assessor": repo / PurePosixPath(execution["assessor_relative_path"]),
        "input_manifest": repo
        / PurePosixPath(execution["input_manifest_relative_path"]),
        "candidate": repo / PurePosixPath(execution["candidate_relative_path"]),
        "truth": repo / PurePosixPath(execution["truth_relative_path"]),
        "frozen_k0": repo / PurePosixPath(execution["frozen_k0_relative_path"]),
    }


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _verify_authority(
    amendment_path: Path,
    amendment: Mapping[str, Any],
    amendment_sha: str,
    paths: Mapping[str, Path],
) -> dict[str, str]:
    if amendment_path != paths["amendment"]:
        raise ExecutionClosureError("A3 amendment authority path mismatch")
    root = paths["authority_root"]
    if Path(_git(root, "rev-parse", "--show-toplevel")) != root:
        raise ExecutionClosureError("A3 authority root mismatch")
    checker_sha = _file_sha(paths["checker"])
    if checker_sha != amendment["checker"]["sha256"]:
        raise ExecutionClosureError("A3 checker hash mismatch")
    if _file_sha(Path(__file__).resolve()) != checker_sha:
        raise ExecutionClosureError("executing A3 checker hash mismatch")
    relatives = [
        paths[key].relative_to(root).as_posix() for key in ("amendment", "checker")
    ]
    for relative in relatives:
        _git(root, "ls-files", "--error-unmatch", "--", relative)
    if _git(root, "status", "--porcelain", "--", *relatives):
        raise ExecutionClosureError("A3 authority files are not committed/clean")
    commits = [
        _git(root, "log", "-1", "--format=%H", "--", relative) for relative in relatives
    ]
    if not commits[0] or commits[0] != commits[1]:
        raise ExecutionClosureError("A3 amendment/checker lack joint commit")
    a2 = amendment["a2_authority"]
    if _file_sha(paths["a2_amendment"]) != a2["amendment_sha256"]:
        raise ExecutionClosureError("A2 amendment hash drift")
    if _file_sha(paths["a2_checker"]) != a2["checker_sha256"]:
        raise ExecutionClosureError("A2 checker hash drift")
    return {
        "amendment_commit": commits[0],
        "amendment_sha256": amendment_sha,
        "checker_commit": commits[1],
        "checker_sha256": checker_sha,
        "a2_amendment_sha256": a2["amendment_sha256"],
        "a2_checker_sha256": a2["checker_sha256"],
    }


def _context(
    amendment_path: Path,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, str], types.ModuleType]:
    path, amendment, amendment_sha = _load_amendment(amendment_path)
    paths = _paths(amendment)
    authority = _verify_authority(path, amendment, amendment_sha, paths)
    a2 = _load_a2(paths["a2_checker"], amendment["a2_authority"]["checker_sha256"])
    required = {
        "authority_root",
        "repo",
        "amendment",
        "checker",
        "a2_amendment",
        "a2_checker",
        "python",
        "assessor",
        "input_manifest",
        "candidate",
        "truth",
        "frozen_k0",
    }
    paths = {
        key: a2._plain_path(value, must_exist=key in required, label=f"A3 {key}")
        for key, value in paths.items()
    }
    normalized = [os.path.normcase(str(value)) for value in paths.values()]
    if len(normalized) != len(set(normalized)):
        raise ExecutionClosureError("A3 bound path aliases")
    return amendment, paths, authority, a2


def _directory_members(directory: Path) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    stack = [directory]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    while stack:
        parent = stack.pop()
        with os.scandir(parent) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            attributes = getattr(metadata, "st_file_attributes", 0)
            if entry.is_symlink() or attributes & reparse_flag:
                raise ExecutionClosureError(f"monitor directory reparse: {entry.path}")
            child = Path(entry.path)
            if stat.S_ISDIR(metadata.st_mode):
                stack.append(child)
            elif stat.S_ISREG(metadata.st_mode):
                members.append(
                    {
                        "path": child.relative_to(directory).as_posix(),
                        "sha256": _file_sha(child),
                        "size": metadata.st_size,
                    }
                )
            else:
                raise ExecutionClosureError(
                    f"monitor directory nonregular entry: {entry.path}"
                )
    members.sort(key=lambda row: row["path"])
    return members


def _monitor_rows(
    amendment: Mapping[str, Any], paths: Mapping[str, Path]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    descriptors = list(amendment["monitor"]["files"])
    lock_relative = amendment["monitor"]["source_lock_relative_path"]
    lock_path = paths["repo"] / PurePosixPath(lock_relative)
    lock = _json_bytes(lock_path.read_bytes(), "source lock monitor plan")
    frozen_relatives = set(lock["files"])
    frozen_relatives.update(
        {
            lock_relative,
            amendment["monitor"]["exclusive_runner_relative_path"],
            amendment["monitor"]["julia_manifest_relative_path"],
        }
    )
    descriptors.extend(
        {"root": "repo", "relative_path": relative}
        for relative in sorted(frozen_relatives)
    )
    for descriptor in descriptors:
        base = paths[descriptor["root"]]
        target = base / PurePosixPath(descriptor["relative_path"])
        rows.append(
            {
                "path": str(target),
                "sha256": _file_sha(target),
                "size": target.stat().st_size,
            }
        )
    for descriptor in amendment["monitor"]["directories"]:
        base = paths[descriptor["root"]]
        directory = base / PurePosixPath(descriptor["relative_path"])
        members = _directory_members(directory)
        rows.append(
            {
                "directory": str(directory),
                "membership_sha256": _sha(_canonical(members)),
                "member_count": len(members),
            }
        )
    rows.sort(key=lambda row: row.get("path", row.get("directory", "")))
    return rows


class SourceWindow:
    def __init__(
        self,
        amendment: Mapping[str, Any],
        paths: Mapping[str, Path],
    ) -> None:
        self.amendment = amendment
        self.paths = paths
        self.interval = float(amendment["monitor"]["interval_seconds"])
        self.initial: list[dict[str, Any]] = []
        self.final: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.samples = 0
        self.started_at = ""
        self.ended_at = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None

    def __enter__(self) -> "SourceWindow":
        self.initial = _monitor_rows(self.amendment, self.paths)
        self.started_at = _utc_now()

        def run() -> None:
            try:
                while not self._stop.wait(self.interval):
                    current = _monitor_rows(self.amendment, self.paths)
                    self.samples += 1
                    if current != self.initial:
                        self.events.append(
                            {
                                "observed_at_utc": _utc_now(),
                                "snapshot_sha256": _sha(_canonical(current)),
                            }
                        )
            except BaseException as error:
                self._error = error

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self._stop.set()
        assert self._thread is not None
        self._thread.join()
        self.final = _monitor_rows(self.amendment, self.paths)
        self.ended_at = _utc_now()
        if self._error is not None:
            raise ExecutionClosureError(f"source monitor failed: {self._error}")
        if self.events or self.final != self.initial:
            raise ExecutionClosureError("source-window mutation detected")

    def receipt(self) -> dict[str, Any]:
        if not self.ended_at or self.final != self.initial or self.events:
            raise ExecutionClosureError("source window is not closed cleanly")
        return self.audit()

    def audit(self) -> dict[str, Any]:
        return {
            "ended_at_utc": self.ended_at,
            "event_count": len(self.events),
            "final_snapshot_sha256": _sha(_canonical(self.final)),
            "initial_snapshot_sha256": _sha(_canonical(self.initial)),
            "interval_seconds": self.interval,
            "monitor_error": None
            if self._error is None
            else f"{type(self._error).__name__}: {self._error}",
            "passed": bool(
                self.ended_at
                and self._error is None
                and not self.events
                and self.final == self.initial
            ),
            "sample_count": self.samples,
            "started_at_utc": self.started_at,
        }


def build_pre(amendment_path: Path) -> tuple[dict[str, Any], Path, types.ModuleType]:
    amendment, paths, authority, a2 = _context(amendment_path)
    for key in (
        "source_window",
        "host_ready",
        "host_receipt",
        "a3_archive",
        "assessment_audit",
        "summary",
    ):
        if os.path.lexists(paths[key]):
            raise ExecutionClosureError(f"terminal pre-existing A3 path: {key}")
    document, output = a2.build_pre_receipt(paths["a2_amendment"])
    document["execution_closure_a3"] = {
        "authority": authority,
        "monitor_plan_sha256": _sha(_canonical(amendment["monitor"])),
        "outcome_data_inspected": False,
        "passed": True,
        "schema_version": AMENDMENT_SCHEMA,
    }
    return document, output, a2


def _verify_source_observation(
    amendment: Mapping[str, Any],
    paths: Mapping[str, Path],
    authority: Mapping[str, str],
) -> None:
    source_path = paths["repo"] / PurePosixPath(
        amendment["execution"]["source_observation_relative_path"]
    )
    _payload, _digest, source = _read_once(source_path, "source observation")
    pre_sha = _file_sha(paths["v1_pre"])
    if (
        source.get("formal_execution_closure_amendment_a3_sha256")
        != authority["amendment_sha256"]
        or source.get("formal_execution_closure_checker_a3_sha256")
        != authority["checker_sha256"]
        or source.get("formal_execution_closure_pre_audit_sha256") != pre_sha
        or source.get("outcomes_inspected") is not False
    ):
        raise ExecutionClosureError("source observation lacks exact A3 bindings")


def publish(amendment_path: Path, pre_path: Path) -> dict[str, Any]:
    amendment, paths, authority, a2 = _context(amendment_path)
    if Path(os.path.abspath(pre_path)) != paths["v1_pre"]:
        raise ExecutionClosureError("A3 publish pre path mismatch")
    pre = _json_bytes(paths["v1_pre"].read_bytes(), "v1/A3 pre receipt")
    if pre.get("execution_closure_a3", {}).get("authority") != authority:
        raise ExecutionClosureError("pre receipt lacks current A3 authority")
    if os.path.lexists(paths["source_window"]):
        raise ExecutionClosureError("terminal existing source-window receipt")
    _verify_source_observation(amendment, paths, authority)
    with SourceWindow(amendment, paths) as window:
        result = a2.publish(paths["a2_amendment"], paths["v1_pre"])
    hygiene = a2._verify_worktree_hygiene(
        paths["repo"],
        allowed_staging=amendment["execution"]["official_relative_path"],
        allowed_exact=amendment["execution"]["post_allowed_exact_paths"],
    )
    receipt = {
        "a2_anchor_sha256": result["anchor_sha256"],
        "a2_execution_audit_sha256": result["execution_audit_sha256"],
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "outcome_data_inspected": False,
        "passed": True,
        "post_hygiene": hygiene,
        "schema_version": SOURCE_WINDOW_SCHEMA,
        "window": window.receipt(),
    }
    receipt_sha = a2._write_json_no_replace(paths["source_window"], receipt)
    return {
        "official_path": result["official_path"],
        "outcome_data_inspected": False,
        "passed": True,
        "source_window_receipt_sha256": receipt_sha,
    }


def _inventory_with_bytes(
    root: Path, capture_paths: set[str]
) -> tuple[dict[str, Any], dict[str, bytes]]:
    rows: list[dict[str, Any]] = []
    captured: dict[str, bytes] = {}
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            attributes = getattr(metadata, "st_file_attributes", 0)
            if entry.is_symlink() or attributes & reparse_flag:
                raise ExecutionClosureError(f"archive reparse entry: {entry.path}")
            path = Path(entry.path)
            if stat.S_ISDIR(metadata.st_mode):
                stack.append(path)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ExecutionClosureError(f"archive nonregular entry: {entry.path}")
            relative = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            if relative in capture_paths:
                captured[relative] = payload
            rows.append(
                {"path": relative, "sha256": _sha(payload), "size": len(payload)}
            )
    rows.sort(key=lambda row: row["path"])
    return (
        {
            "file_count": len(rows),
            "files": rows,
            "root_sha256": _sha(_canonical(rows)),
            "total_bytes": sum(row["size"] for row in rows),
        },
        captured,
    )


def _host_binding(
    amendment: Mapping[str, Any],
    ready: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    ready_sha: str,
    outer_sha: str,
    capture_sha: str,
    outer: Mapping[str, Any],
    capture: Mapping[str, Any],
    authority_root: Path,
) -> None:
    expected = amendment["host_observer_binding"]
    bindings = receipt.get("bindings")
    if not isinstance(bindings, dict) or ready.get("bindings") != bindings:
        raise ExecutionClosureError("host ready/final bindings differ")
    if set(bindings) != {
        "settings",
        "paths",
        "backend",
        "observer_source",
        "command_tokens",
        "command_tokens_sha256",
    }:
        raise ExecutionClosureError("host bindings key set mismatch")
    if bindings.get("settings") != expected["settings"]:
        raise ExecutionClosureError("host settings mismatch")
    if bindings.get("paths") != expected["paths"]:
        raise ExecutionClosureError("host paths mismatch")
    if bindings.get("observer_source") != {
        "path": expected["observer_source"]["path"],
        "sha256": expected["observer_source"]["sha256"],
    }:
        raise ExecutionClosureError("host observer source binding mismatch")
    if (
        bindings.get("command_tokens") != expected["command_tokens"]
        or bindings.get("command_tokens_sha256") != expected["command_tokens_sha256"]
        or _sha(_canonical(bindings["command_tokens"]))
        != expected["command_tokens_sha256"]
    ):
        raise ExecutionClosureError("host observer command binding mismatch")
    source_relative = expected["observer_source"]["relative_path"]
    source_path = authority_root / PurePosixPath(source_relative)
    if (
        str(source_path) != expected["observer_source"]["path"]
        or _file_sha(source_path) != expected["observer_source"]["sha256"]
        or _git(authority_root, "log", "-1", "--format=%H", "--", source_relative)
        != expected["observer_source"]["last_change_commit"]
    ):
        raise ExecutionClosureError("host observer committed authority mismatch")
    backend = bindings.get("backend")
    if not isinstance(backend, dict):
        raise ExecutionClosureError("host backend binding missing")
    backend_expected = expected["backend"]
    for key, value in backend_expected.items():
        if backend.get(key) != value:
            raise ExecutionClosureError(f"host backend mismatch: {key}")
    expected_backend_keys = set(backend_expected) | {
        "script_sha256",
        "capability_probe_pid",
    }
    script_sha = backend.get("script_sha256")
    capability_pid = backend.get("capability_probe_pid")
    if (
        set(backend) != expected_backend_keys
        or not isinstance(script_sha, str)
        or len(script_sha) != 64
        or any(character not in "0123456789abcdef" for character in script_sha)
        or not isinstance(capability_pid, int)
        or isinstance(capability_pid, bool)
        or capability_pid <= 0
    ):
        raise ExecutionClosureError("host dynamic backend binding invalid")
    final_checks = {
        "schema_version": expected["receipt_schema_version"],
        "label": expected["settings"]["label"],
        "observer": expected["settings"]["observer"],
        "host_contention_event_count": 0,
        "lease_loss_count": 0,
        "all_formal_pids_ended": True,
        "outcomes_inspected": False,
        "template_only": False,
        "contention_events": [],
        "lease_loss_events": [],
        "monitor_failures": [],
        "outer_audit_sha256": outer_sha,
        "capture_metadata_sha256": capture_sha,
        "ready_receipt_sha256": ready_sha,
        "formal_outer_pid": outer.get("child_pid"),
        "formal_segment_pids": capture.get("child_pids"),
    }
    for key, value in final_checks.items():
        if receipt.get(key) != value:
            raise ExecutionClosureError(f"host final receipt mismatch: {key}")
    ready_checks = {
        "schema_version": expected["ready_schema_version"],
        "label": expected["settings"]["label"],
        "outcomes_inspected": False,
        "ready": True,
    }
    for key, value in ready_checks.items():
        if ready.get(key) != value:
            raise ExecutionClosureError(f"host ready receipt mismatch: {key}")
    if set(ready) != {
        "schema_version",
        "label",
        "observer_pid",
        "inventory_child_pid",
        "observation_started_at_utc",
        "outcomes_inspected",
        "ready",
        "bindings",
    }:
        raise ExecutionClosureError("host ready receipt key set mismatch")
    if set(receipt) != {
        "schema_version",
        "label",
        "observer",
        "observation_started_at_utc",
        "observation_ended_at_utc",
        "formal_outer_pid",
        "formal_segment_pids",
        "host_contention_event_count",
        "lease_loss_count",
        "all_formal_pids_ended",
        "excluded_heavy_work",
        "method",
        "outcomes_inspected",
        "template_only",
        "poll_gap_max_seconds",
        "raw_process_inventory_sha256",
        "raw_process_inventory_sample_count",
        "unexplained_cpu_cores_max",
        "contention_events",
        "lease_loss_events",
        "monitor_failures",
        "inventory_child_pid",
        "formal_process_identity_count",
        "formal_process_identities",
        "formal_process_identities_sha256",
        "formal_clear_snapshot_count",
        "formal_clear_snapshot_ticks",
        "bindings",
        "ready_receipt_sha256",
        "outer_audit_sha256",
        "capture_metadata_sha256",
    }:
        raise ExecutionClosureError("host final receipt key set mismatch")
    if (
        ready.get("observation_started_at_utc")
        != receipt.get("observation_started_at_utc")
        or not isinstance(ready.get("observer_pid"), int)
        or isinstance(ready.get("observer_pid"), bool)
        or ready.get("observer_pid") <= 0
        or not isinstance(ready.get("inventory_child_pid"), int)
        or isinstance(ready.get("inventory_child_pid"), bool)
        or ready.get("inventory_child_pid") <= 0
        or ready.get("inventory_child_pid") != receipt.get("inventory_child_pid")
        or not isinstance(receipt.get("raw_process_inventory_sample_count"), int)
        or isinstance(receipt.get("raw_process_inventory_sample_count"), bool)
        or receipt.get("raw_process_inventory_sample_count") <= 0
        or receipt.get("poll_gap_max_seconds")
        > expected["settings"]["max_poll_gap_seconds"]
        or _parse_time(receipt.get("observation_ended_at_utc"), "host end")
        < _parse_time(receipt.get("observation_started_at_utc"), "host start")
    ):
        raise ExecutionClosureError("host ready/final interval mismatch")
    for hash_key in (
        "raw_process_inventory_sha256",
        "formal_process_identities_sha256",
    ):
        value = receipt.get(hash_key)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ExecutionClosureError(f"host invalid SHA field: {hash_key}")
    identities = receipt.get("formal_process_identities")
    if not isinstance(identities, list):
        raise ExecutionClosureError("host process identities missing")
    identity_sha = _sha(_canonical(identities))
    clear_count = receipt.get("formal_clear_snapshot_count")
    clear_ticks = receipt.get("formal_clear_snapshot_ticks")
    required_pids = {outer.get("child_pid"), *capture.get("child_pids", [])}
    identity_pids = {row.get("pid") for row in identities if isinstance(row, dict)}
    if (
        len(identities) != receipt.get("formal_process_identity_count")
        or identity_sha != receipt.get("formal_process_identities_sha256")
        or not required_pids.issubset(identity_pids)
        or any(
            set(row) != {"pid", "start_ticks"}
            or not isinstance(row.get("pid"), int)
            or isinstance(row.get("pid"), bool)
            or row.get("pid") <= 0
            or not isinstance(row.get("start_ticks"), int)
            or isinstance(row.get("start_ticks"), bool)
            or row.get("start_ticks") <= 0
            for row in identities
            if isinstance(row, dict)
        )
        or any(not isinstance(row, dict) for row in identities)
        or not isinstance(clear_count, int)
        or isinstance(clear_count, bool)
        or clear_count < 2
        or not isinstance(clear_ticks, list)
        or len(clear_ticks) != clear_count
        or any(
            not isinstance(tick, int) or isinstance(tick, bool) or tick <= 0
            for tick in clear_ticks
        )
        or any(left >= right for left, right in zip(clear_ticks, clear_ticks[1:]))
    ):
        raise ExecutionClosureError("host formal identity binding mismatch")


def _exact_launch_intent(
    amendment: Mapping[str, Any], anchor: Mapping[str, Any]
) -> None:
    expected = amendment["execution"]["exact_finalizer_launch_intent"]
    intent = anchor.get("finalizer_launch_intent")
    if intent != expected:
        raise ExecutionClosureError("anchor finalizer launch intent mismatch")
    if intent.get("command_sha256") != _sha(_canonical(intent["exact_command_tokens"])):
        raise ExecutionClosureError("anchor finalizer token hash mismatch")


def archive(amendment_path: Path) -> dict[str, Any]:
    amendment, paths, authority, a2 = _context(amendment_path)
    for key in (
        "anchor",
        "finalizer_execution",
        "source_window",
        "host_ready",
        "host_receipt",
    ):
        if not paths[key].is_file():
            raise ExecutionClosureError(f"archive trust root missing: {key}")
    if os.path.lexists(paths["a2_archive"]):
        raise ExecutionClosureError("A2 archive receipt must remain absent")
    if os.path.lexists(paths["a3_archive"]):
        raise ExecutionClosureError("terminal existing A3 archive receipt")
    if os.path.lexists(paths["staging"]) or os.path.lexists(paths["partial"]):
        raise ExecutionClosureError("staging/partial remains")
    before_frozen = a2._snapshot_frozen(
        amendment,
        a2._paths(_json_bytes(paths["a2_amendment"].read_bytes(), "A2 amendment")),
    )
    hygiene = a2._verify_worktree_hygiene(
        paths["repo"],
        allowed_staging=amendment["execution"]["official_relative_path"],
        allowed_exact=amendment["execution"]["post_allowed_exact_paths"],
    )
    anchor_bytes, anchor_sha, anchor = _read_once(paths["anchor"], "A2 anchor")
    execution_bytes, execution_sha, execution = _read_once(
        paths["finalizer_execution"], "A2 finalizer execution audit"
    )
    source_window_bytes, source_window_sha, source_window = _read_once(
        paths["source_window"], "A3 source-window receipt"
    )
    host_bytes, host_sha, host = _read_once(
        paths["host_receipt"], "host identity receipt"
    )
    host_ready_bytes, host_ready_sha, host_ready = _read_once(
        paths["host_ready"], "host ready receipt"
    )
    capture_names = {
        amendment["execution"]["a2_seal_filename"],
        "capture.json",
        "formal-run-manifest.json",
        "audit/formal-run-audit.json",
        "audit/host-observation.json",
        "audit/source-observation.json",
        "formal-binding-post-audit.json",
    }
    inventory_before, payloads = _inventory_with_bytes(paths["official"], capture_names)
    missing = capture_names - set(payloads)
    if missing:
        raise ExecutionClosureError(
            f"archive named artifacts missing: {sorted(missing)}"
        )
    documents = {name: _json_bytes(payloads[name], name) for name in capture_names}
    artifact_hashes = anchor["artifact_hashes"]
    if _sha(payloads["capture.json"]) != artifact_hashes["capture_sha256"]:
        raise ExecutionClosureError("anchored capture hash mismatch")
    if (
        _sha(payloads["formal-binding-post-audit.json"])
        != artifact_hashes["v1_post_audit_sha256"]
    ):
        raise ExecutionClosureError("anchored v1 post hash mismatch")
    copy_keys = {
        "audit/formal-run-audit.json": "outer_audit_sha256",
        "audit/host-observation.json": "host_observation_sha256",
        "audit/source-observation.json": "source_observation_sha256",
    }
    for relative, key in copy_keys.items():
        if _sha(payloads[relative]) != artifact_hashes[key]:
            raise ExecutionClosureError(f"anchored audit hash mismatch: {relative}")
    if (
        _sha(payloads[amendment["execution"]["a2_seal_filename"]])
        != anchor["seal_sha256"]
    ):
        raise ExecutionClosureError("anchored seal hash mismatch")
    if (
        source_window.get("authority") != authority
        or source_window.get("passed") is not True
    ):
        raise ExecutionClosureError("source-window authority/state mismatch")
    window = source_window.get("window", {})
    if (
        source_window.get("schema_version") != SOURCE_WINDOW_SCHEMA
        or window.get("passed") is not True
        or window.get("event_count") != 0
        or not isinstance(window.get("sample_count"), int)
        or window.get("sample_count") < 1
        or window.get("initial_snapshot_sha256") != window.get("final_snapshot_sha256")
    ):
        raise ExecutionClosureError("source-window interval binding mismatch")
    if source_window.get("a2_anchor_sha256") != anchor_sha:
        raise ExecutionClosureError("source-window/anchor mismatch")
    if source_window.get("a2_execution_audit_sha256") != execution_sha:
        raise ExecutionClosureError("source-window/execution mismatch")
    if not (
        _parse_time(window.get("started_at_utc"), "source-window start")
        <= _parse_time(execution.get("started_at_utc"), "finalizer start")
        and _parse_time(window.get("ended_at_utc"), "source-window end")
        >= _parse_time(execution.get("ended_at_utc"), "finalizer end")
    ):
        raise ExecutionClosureError("source window does not cover finalizer execution")
    _exact_launch_intent(amendment, anchor)
    if (
        execution.get("command")
        != anchor["finalizer_launch_intent"]["exact_command_tokens"]
        or execution.get("cwd") != anchor["finalizer_launch_intent"]["cwd"]
        or execution.get("environment")
        != anchor["finalizer_launch_intent"]["environment"]
        or execution.get("one_shot") is not True
        or execution.get("outcome") != "completed"
        or execution.get("exit_code") != 0
        or execution.get("error") is not None
    ):
        raise ExecutionClosureError("finalizer execution/intent mismatch")
    _host_binding(
        amendment,
        host_ready,
        host,
        ready_sha=host_ready_sha,
        outer_sha=artifact_hashes["outer_audit_sha256"],
        capture_sha=artifact_hashes["capture_sha256"],
        outer=documents["audit/formal-run-audit.json"],
        capture=documents["capture.json"],
        authority_root=paths["authority_root"],
    )
    seal = documents[amendment["execution"]["a2_seal_filename"]]
    if seal["staging_inventory"]["root_sha256"] != anchor.get("inventory_root_sha256"):
        raise ExecutionClosureError("seal/anchor inventory-root mismatch")
    archived_source = documents["audit/source-observation.json"]
    if (
        archived_source.get("formal_execution_closure_amendment_a3_sha256")
        != authority["amendment_sha256"]
        or archived_source.get("formal_execution_closure_checker_a3_sha256")
        != authority["checker_sha256"]
        or archived_source.get("formal_execution_closure_pre_audit_sha256")
        != _file_sha(paths["v1_pre"])
    ):
        raise ExecutionClosureError("archived source observation A3 binding mismatch")
    sealed_rows = {row["path"]: row for row in seal["staging_inventory"]["files"]}
    actual_rows = {row["path"]: row for row in inventory_before["files"]}
    for relative, row in sealed_rows.items():
        if actual_rows.get(relative) != row:
            raise ExecutionClosureError(f"sealed archive member mismatch: {relative}")
    expected_members = set(sealed_rows) | {
        amendment["execution"]["a2_seal_filename"],
        "audit/formal-run-audit.json",
        "audit/host-observation.json",
        "audit/source-observation.json",
        "formal-run-manifest.json",
    }
    if set(actual_rows) != expected_members:
        raise ExecutionClosureError("official anchored membership mismatch")
    capture = documents["capture.json"]
    manifest = documents["formal-run-manifest.json"]
    if manifest.get("segments") != capture.get("segments"):
        raise ExecutionClosureError("capture/manifest segment metadata mismatch")
    for row in capture.get("segments", []):
        relative = row.get("trace_path")
        if not isinstance(relative, str) or actual_rows.get(relative, {}).get(
            "sha256"
        ) != row.get("trace_sha256"):
            raise ExecutionClosureError("opaque trace hash mismatch")
    inventory_after, _unused = _inventory_with_bytes(paths["official"], set())
    if inventory_before != inventory_after:
        raise ExecutionClosureError("official archive changed during validation")
    after_frozen = a2._snapshot_frozen(
        amendment,
        a2._paths(_json_bytes(paths["a2_amendment"].read_bytes(), "A2 amendment")),
    )
    if before_frozen != after_frozen:
        raise ExecutionClosureError(
            "frozen source/input changed during archive validation"
        )
    receipt = {
        "anchor_sha256": anchor_sha,
        "archive_inventory": inventory_after,
        "assessment_authorized": True,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "execution_audit_sha256": execution_sha,
        "experiment_id": "EXP-JAC-003",
        "frozen_snapshot": after_frozen,
        "host_identity_receipt_sha256": host_sha,
        "host_ready_receipt_sha256": host_ready_sha,
        "outcome_data_inspected": False,
        "passed": True,
        "schema_version": ARCHIVE_SCHEMA,
        "source_window_receipt_sha256": source_window_sha,
        "trust_root_byte_sha256": {
            "anchor": _sha(anchor_bytes),
            "execution": _sha(execution_bytes),
            "host": _sha(host_bytes),
            "host_ready": _sha(host_ready_bytes),
            "source_window": _sha(source_window_bytes),
        },
        "worktree_hygiene": hygiene,
    }
    receipt_sha = a2._write_json_no_replace(paths["a3_archive"], receipt)
    return {
        "archive_receipt_sha256": receipt_sha,
        "assessment_authorized": True,
        "outcome_data_inspected": False,
        "passed": True,
    }


def _assessment_environment(
    amendment: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    policy = amendment["execution"]["assessment_environment_policy"]
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in set(policy["removed_variables"])
    }
    environment.update(policy["fixed_overrides"])
    return environment, {
        "fixed_overrides": dict(policy["fixed_overrides"]),
        "policy_sha256": _sha(_canonical(policy)),
        "removed_variables": list(policy["removed_variables"]),
    }


def _summary_decision(summary: Mapping[str, Any]) -> str:
    decision = summary.get("decision")
    if decision not in ("PASS", "FAIL"):
        raise ExecutionClosureError("summary decision is not PASS/FAIL")
    return decision


def assess(amendment_path: Path) -> dict[str, Any]:
    amendment, paths, authority, a2 = _context(amendment_path)
    if not paths["a3_archive"].is_file():
        raise ExecutionClosureError("A3 archive receipt blockade")
    if os.path.lexists(paths["assessment_audit"]):
        raise ExecutionClosureError("terminal existing assessment audit")
    if os.path.lexists(paths["summary"]):
        raise ExecutionClosureError("unbound assessment output already exists")
    receipt_payload, receipt_sha, receipt = _read_once(
        paths["a3_archive"], "A3 archive receipt"
    )
    if (
        receipt.get("schema_version") != ARCHIVE_SCHEMA
        or receipt.get("authority") != authority
        or receipt.get("passed") is not True
        or receipt.get("assessment_authorized") is not True
    ):
        raise ExecutionClosureError("A3 archive receipt is not authorizing")
    inventory_before, _ = _inventory_with_bytes(paths["official"], set())
    receipt_row = next(
        row
        for row in inventory_before["files"]
        if row["path"] == paths["a3_archive"].name
    )
    without_receipt = [
        row
        for row in inventory_before["files"]
        if row["path"] != paths["a3_archive"].name
    ]
    if (
        receipt_row["sha256"] != receipt_sha
        or _sha(_canonical(without_receipt))
        != receipt["archive_inventory"]["root_sha256"]
    ):
        raise ExecutionClosureError("A3 receipt/archive stable binding mismatch")
    inventory_confirm, _ = _inventory_with_bytes(paths["official"], set())
    if inventory_confirm != inventory_before:
        raise ExecutionClosureError("archive is not stable before assessment")
    a2_paths = a2._paths(
        _json_bytes(paths["a2_amendment"].read_bytes(), "A2 amendment")
    )
    frozen_before = a2._snapshot_frozen(amendment, a2_paths)
    if frozen_before != receipt.get("frozen_snapshot"):
        raise ExecutionClosureError("archive receipt/frozen source binding mismatch")
    hygiene_before = a2._verify_worktree_hygiene(
        paths["repo"],
        allowed_staging=amendment["execution"]["official_relative_path"],
        allowed_exact=amendment["execution"]["post_allowed_exact_paths"],
    )
    tokens = amendment["execution"]["exact_assessor_command_tokens"]
    if tokens[:2] != [str(paths["python"]), str(paths["assessor"])]:
        raise ExecutionClosureError("assessor executable/script token mismatch")
    if _file_sha(paths["assessor"]) != amendment["execution"]["assessor_sha256"]:
        raise ExecutionClosureError("assessor source hash mismatch")
    environment, environment_audit = _assessment_environment(amendment)
    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    error_text: str | None = None
    window: SourceWindow | None = None
    try:
        with SourceWindow(amendment, paths) as window:
            process = subprocess.Popen(tokens, cwd=paths["repo"], env=environment)
            exit_code = process.wait()
    except BaseException as error:
        error_text = f"{type(error).__name__}: {error}"
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
    summary_sha: str | None = None
    decision: str | None = None
    if exit_code == 0 and error_text is None and paths["summary"].is_file():
        summary_payload, summary_sha, summary = _read_once(
            paths["summary"], "development summary"
        )
        try:
            decision = _summary_decision(summary)
        except ExecutionClosureError as error:
            error_text = f"ExecutionClosureError: {error}"
        if _sha(summary_payload) != summary_sha:
            raise AssertionError("unreachable summary hash mismatch")
    frozen_after = a2._snapshot_frozen(amendment, a2_paths)
    hygiene_after = a2._verify_worktree_hygiene(
        paths["repo"],
        allowed_staging=amendment["execution"]["official_relative_path"],
        allowed_exact=amendment["execution"]["post_allowed_exact_paths"],
    )
    if frozen_before != frozen_after:
        error_text = (
            "ExecutionClosureError: frozen source/input changed during assessment"
        )
    inventory_after, _ = _inventory_with_bytes(paths["official"], set())
    before_rows = {row["path"]: row for row in inventory_before["files"]}
    after_rows = {row["path"]: row for row in inventory_after["files"]}
    summary_row = after_rows.pop(paths["summary"].name, None)
    if (
        after_rows != before_rows
        or summary_row is None
        or summary_row["sha256"] != summary_sha
    ):
        error_text = "ExecutionClosureError: archive changed outside bound summary"
    audit = {
        "archive_receipt_sha256": _sha(receipt_payload),
        "authority": authority,
        "child_pid": None if process is None else process.pid,
        "command": tokens,
        "cwd": str(paths["repo"]),
        "decision": decision,
        "elapsed_ns": time.monotonic_ns() - started_ns,
        "ended_at_utc": _utc_now(),
        "environment": environment_audit,
        "error": error_text,
        "exit_code": exit_code,
        "experiment_id": "EXP-JAC-003",
        "frozen_snapshot_after": frozen_after,
        "frozen_snapshot_before": frozen_before,
        "one_shot": True,
        "outcome": "completed" if exit_code == 0 and error_text is None else "failed",
        "output_path": str(paths["summary"]),
        "output_sha256": summary_sha,
        "passed": exit_code == 0 and error_text is None,
        "schema_version": ASSESSMENT_SCHEMA,
        "source_window": None if window is None else window.audit(),
        "started_at_utc": started_at,
        "worktree_hygiene_after": hygiene_after,
        "worktree_hygiene_before": hygiene_before,
    }
    audit_sha = a2._write_json_no_replace(paths["assessment_audit"], audit)
    if audit["passed"] is not True:
        raise ExecutionClosureError("terminal assessor execution failure")
    return {
        "assessment_audit_sha256": audit_sha,
        "decision": decision,
        "output_sha256": summary_sha,
        "passed": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    phases = parser.add_subparsers(dest="phase", required=True)
    for name in ("pre", "publish", "archive", "assess"):
        child = phases.add_parser(name)
        child.add_argument("--amendment", required=True, type=Path)
        if name == "pre":
            child.add_argument("--output", required=True, type=Path)
        elif name == "publish":
            child.add_argument("--pre-audit", required=True, type=Path)
        elif name == "archive":
            child.add_argument("--output", required=True, type=Path)
        else:
            child.add_argument("--audit", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        _path, amendment, _sha256 = _load_amendment(arguments.amendment)
        actual = [str(Path(sys.executable).resolve()), str(Path(__file__).resolve())]
        actual.extend(sys.argv[1:] if argv is None else list(argv))
        expected = amendment["execution"][f"exact_{arguments.phase}_command_tokens"]
        if actual != expected:
            raise ExecutionClosureError(
                "actual A3 command tokens differ from frozen plan"
            )
        if arguments.phase == "pre":
            document, output, a2 = build_pre(arguments.amendment)
            if Path(os.path.abspath(arguments.output)) != output:
                raise ExecutionClosureError("A3 pre output path mismatch")
            a2._write_json_no_replace(output, document)
            result = {"passed": True, "pre_audit_path": str(output)}
        elif arguments.phase == "publish":
            result = publish(arguments.amendment, arguments.pre_audit)
        elif arguments.phase == "archive":
            paths = _paths(amendment)
            if Path(os.path.abspath(arguments.output)) != paths["a3_archive"]:
                raise ExecutionClosureError("A3 archive output path mismatch")
            result = archive(arguments.amendment)
        else:
            paths = _paths(amendment)
            if Path(os.path.abspath(arguments.audit)) != paths["assessment_audit"]:
                raise ExecutionClosureError("A3 assessment audit path mismatch")
            result = assess(arguments.amendment)
    except BaseException as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
