"""Final crash-safe receipt layer for the frozen EXP-JAC-003 execution chain.

This module reuses the immutable A3 implementation.  Before assessment it reads
only provenance JSON and opaque bytes; it never parses a segment trace.  A4
adds a first-sample source-monitor barrier and pre-launch receipts so a crashed
publication or assessment cannot be retried as if it had never started.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import types
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


AMENDMENT_SCHEMA = "exp-jac-003-formal-chain-final-amendment-a4/v1"
PUBLICATION_INTENT_SCHEMA = "exp-jac-003-publication-start-intent-a4/v1"
PUBLICATION_RECEIPT_SCHEMA = "exp-jac-003-publication-final-receipt-a4/v1"
ARCHIVE_RECEIPT_SCHEMA = "exp-jac-003-formal-chain-archive-receipt-a4/v1"
ASSESSMENT_INTENT_SCHEMA = "exp-jac-003-assessment-start-intent-a4/v1"
ASSESSMENT_RECEIPT_SCHEMA = "exp-jac-003-assessment-final-receipt-a4/v1"


class FinalChainError(RuntimeError):
    """A terminal A4 provenance or one-shot violation."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
        raise FinalChainError(f"invalid {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise FinalChainError(f"{label} must contain one object")
    return value


def _read_once(path: Path, label: str) -> tuple[bytes, str, dict[str, Any]]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise FinalChainError(f"cannot read {label}: {error}") from error
    return payload, _sha(payload), _json_bytes(payload, label)


def _git(repo: Path, *arguments: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _load_a3(path: Path, expected_sha: str) -> types.ModuleType:
    payload = path.read_bytes()
    if _sha(payload) != expected_sha:
        raise FinalChainError("A3 checker hash drift")
    module = types.ModuleType("exp_jac_003_execution_closure_a3_approved")
    module.__file__ = str(path)
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


def _load_amendment(path: Path) -> tuple[Path, dict[str, Any], str]:
    absolute = Path(os.path.abspath(path))
    payload = absolute.read_bytes()
    amendment = _json_bytes(payload, "A4 amendment")
    if amendment.get("schema_version") != AMENDMENT_SCHEMA:
        raise FinalChainError("A4 amendment schema drift")
    if amendment.get("experiment_id") != "EXP-JAC-003":
        raise FinalChainError("A4 experiment mismatch")
    if (
        amendment.get("outcome_blind_attestation", {}).get("any_outcome_opened")
        is not False
    ):
        raise FinalChainError("A4 was not frozen outcome-blind")
    return absolute, amendment, _sha(payload)


def _paths(amendment: Mapping[str, Any]) -> dict[str, Path]:
    root = Path(amendment["authority_repository_root"])
    execution = amendment["execution"]
    return {
        "root": root,
        "amendment": root / PurePosixPath(amendment["amendment_relative_path"]),
        "checker": root / PurePosixPath(amendment["checker"]["relative_path"]),
        "a3_amendment": root
        / PurePosixPath(amendment["a3_authority"]["amendment_relative_path"]),
        "a3_checker": root
        / PurePosixPath(amendment["a3_authority"]["checker_relative_path"]),
        "pre": Path(execution["v1_pre_audit_path"]),
        "publication_intent": Path(execution["publication_intent_path"]),
        "publication_receipt": Path(execution["publication_receipt_path"]),
        "archive_receipt": Path(execution["archive_receipt_path"]),
        "assessment_intent": Path(execution["assessment_intent_path"]),
        "assessment_receipt": Path(execution["assessment_receipt_path"]),
    }


def _authority(
    amendment_path: Path,
    amendment: Mapping[str, Any],
    amendment_sha: str,
    paths: Mapping[str, Path],
) -> dict[str, str]:
    root = paths["root"]
    if amendment_path != paths["amendment"]:
        raise FinalChainError("A4 amendment path mismatch")
    if Path(_git(root, "rev-parse", "--show-toplevel")) != root:
        raise FinalChainError("A4 authority root mismatch")
    checker_sha = _file_sha(paths["checker"])
    if checker_sha != amendment["checker"]["sha256"]:
        raise FinalChainError("A4 checker hash mismatch")
    if _file_sha(Path(__file__).resolve()) != checker_sha:
        raise FinalChainError("executing A4 checker differs from authority")
    relatives = [
        paths[key].relative_to(root).as_posix() for key in ("amendment", "checker")
    ]
    for relative in relatives:
        _git(root, "ls-files", "--error-unmatch", "--", relative)
    if _git(root, "status", "--porcelain", "--", *relatives):
        raise FinalChainError("A4 authority files are not committed and clean")
    commits = [_git(root, "log", "-1", "--format=%H", "--", rel) for rel in relatives]
    if not commits[0] or commits[0] != commits[1]:
        raise FinalChainError("A4 authority lacks one joint commit")
    a3 = amendment["a3_authority"]
    if _file_sha(paths["a3_amendment"]) != a3["amendment_sha256"]:
        raise FinalChainError("A3 amendment hash drift")
    if _file_sha(paths["a3_checker"]) != a3["checker_sha256"]:
        raise FinalChainError("A3 checker hash drift")
    return {
        "amendment_commit": commits[0],
        "amendment_sha256": amendment_sha,
        "checker_commit": commits[1],
        "checker_sha256": checker_sha,
        "a3_amendment_sha256": a3["amendment_sha256"],
        "a3_checker_sha256": a3["checker_sha256"],
    }


def _context(
    amendment_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Path],
    dict[str, str],
    types.ModuleType,
    dict[str, Any],
    dict[str, Path],
    dict[str, str],
    types.ModuleType,
]:
    path, amendment, amendment_sha = _load_amendment(amendment_path)
    paths = _paths(amendment)
    authority = _authority(path, amendment, amendment_sha, paths)
    a3 = _load_a3(paths["a3_checker"], amendment["a3_authority"]["checker_sha256"])
    a3_amendment, a3_paths, a3_authority, a2 = a3._context(paths["a3_amendment"])
    return amendment, paths, authority, a3, a3_amendment, a3_paths, a3_authority, a2


class BarrierSourceWindow:
    """A3 source monitor with a completed first-sample barrier."""

    def __init__(
        self,
        a3: types.ModuleType,
        amendment: Mapping[str, Any],
        paths: Mapping[str, Path],
    ):
        self.a3 = a3
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
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None

    def __enter__(self) -> "BarrierSourceWindow":
        self.initial = self.a3._monitor_rows(self.amendment, self.paths)
        self.started_at = _utc_now()

        def run() -> None:
            try:
                first = self.a3._monitor_rows(self.amendment, self.paths)
                self.samples = 1
                if first != self.initial:
                    self.events.append(
                        {"observed_at_utc": _utc_now(), "phase": "barrier"}
                    )
                self._ready.set()
                while not self._stop.wait(self.interval):
                    current = self.a3._monitor_rows(self.amendment, self.paths)
                    self.samples += 1
                    if current != self.initial:
                        self.events.append(
                            {"observed_at_utc": _utc_now(), "phase": "window"}
                        )
            except BaseException as error:
                self._error = error
                self._ready.set()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        if not self._ready.wait(30.0):
            raise FinalChainError("A4 source-monitor first-sample barrier timed out")
        if self._error is not None:
            raise FinalChainError(
                f"A4 source monitor failed before barrier: {self._error}"
            )
        if self.events:
            raise FinalChainError("A4 source changed before first-sample barrier")
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self.final = self.a3._monitor_rows(self.amendment, self.paths)
        self.ended_at = _utc_now()
        if self._error is not None:
            raise FinalChainError(f"A4 source monitor failed: {self._error}")
        if self.events or self.final != self.initial:
            raise FinalChainError("A4 source mutation detected")

    def receipt(self) -> dict[str, Any]:
        if (
            not self.ended_at
            or self.events
            or self.final != self.initial
            or self.samples < 1
        ):
            raise FinalChainError("A4 source monitor did not close cleanly")
        return {
            "barrier_completed": True,
            "ended_at_utc": self.ended_at,
            "event_count": 0,
            "final_snapshot_sha256": _sha(_canonical(self.final)),
            "initial_snapshot_sha256": _sha(_canonical(self.initial)),
            "interval_seconds": self.interval,
            "sample_count": self.samples,
            "started_at_utc": self.started_at,
        }


def build_pre(amendment_path: Path) -> tuple[dict[str, Any], Path, types.ModuleType]:
    amendment, paths, authority, a3, _a3_amendment, _a3_paths, _a3_authority, a2 = (
        _context(amendment_path)
    )
    for key in (
        "publication_intent",
        "publication_receipt",
        "archive_receipt",
        "assessment_intent",
        "assessment_receipt",
    ):
        if os.path.lexists(paths[key]):
            raise FinalChainError(f"terminal pre-existing A4 path: {key}")
    document, output, _approved_a2 = a3.build_pre(paths["a3_amendment"])
    document["formal_chain_final_a4"] = {
        "authority": authority,
        "outcome_data_inspected": False,
        "passed": True,
        "schema_version": AMENDMENT_SCHEMA,
    }
    return document, output, a2


def _require_source_fields(
    source: Mapping[str, Any], authority: Mapping[str, str], pre_sha: str
) -> None:
    if (
        source.get("formal_chain_final_amendment_a4_sha256")
        != authority["amendment_sha256"]
        or source.get("formal_chain_final_checker_a4_sha256")
        != authority["checker_sha256"]
        or source.get("formal_chain_final_pre_audit_sha256") != pre_sha
        or source.get("outcomes_inspected") is not False
    ):
        raise FinalChainError("source observation lacks A4 authority bindings")


def _publication_inputs(
    a3_paths: Mapping[str, Path], authority: Mapping[str, str], pre_sha: str
) -> tuple[dict[str, bytes], dict[str, str], dict[str, dict[str, Any]]]:
    source_path = (
        a3_paths["repo"]
        / "research/results/EXP-JAC-003-development-source-observation.json"
    )
    outer_path = (
        a3_paths["repo"]
        / "research/results/EXP-JAC-003-development-formal-run-audit.json"
    )
    inputs: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    documents: dict[str, dict[str, Any]] = {}
    for name, path in (
        ("source", source_path),
        ("host", a3_paths["host_receipt"]),
        ("outer", outer_path),
    ):
        payload, digest, document = _read_once(path, f"{name} publication input")
        inputs[name] = payload
        hashes[name] = digest
        documents[name] = document
    _require_source_fields(documents["source"], authority, pre_sha)
    if (
        documents["host"].get("host_contention_event_count") != 0
        or documents["host"].get("lease_loss_count") != 0
        or documents["host"].get("all_formal_pids_ended") is not True
        or documents["host"].get("outcomes_inspected") is not False
    ):
        raise FinalChainError("host receipt is not clean")
    if (
        documents["outer"].get("outcome") != "completed"
        or documents["outer"].get("exit_code") != 0
        or documents["outer"].get("error") is not None
    ):
        raise FinalChainError("outer formal audit is not complete")
    return inputs, hashes, documents


def publish(amendment_path: Path, pre_path: Path) -> dict[str, Any]:
    amendment, paths, authority, a3, a3_amendment, a3_paths, _a3_authority, a2 = (
        _context(amendment_path)
    )
    if Path(os.path.abspath(pre_path)) != paths["pre"]:
        raise FinalChainError("A4 publish pre path mismatch")
    pre_payload = paths["pre"].read_bytes()
    pre = _json_bytes(pre_payload, "A4 pre receipt")
    if pre.get("formal_chain_final_a4", {}).get("authority") != authority:
        raise FinalChainError("pre receipt lacks current A4 authority")
    for key in ("publication_intent", "publication_receipt"):
        if os.path.lexists(paths[key]):
            raise FinalChainError(f"terminal existing A4 publication path: {key}")
    _inputs, hashes, _documents = _publication_inputs(
        a3_paths, authority, _sha(pre_payload)
    )
    intent = {
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "input_sha256": hashes,
        "outcome_data_inspected": False,
        "pre_audit_sha256": _sha(pre_payload),
        "schema_version": PUBLICATION_INTENT_SCHEMA,
        "single_writer_required": True,
    }
    intent_sha = a2._write_json_no_replace(paths["publication_intent"], intent)
    with BarrierSourceWindow(a3, a3_amendment, a3_paths) as window:
        result = a3.publish(paths["a3_amendment"], paths["pre"])
    _inputs_after, hashes_after, _documents_after = _publication_inputs(
        a3_paths, authority, _sha(pre_payload)
    )
    if hashes_after != hashes:
        raise FinalChainError("publication input bytes changed")
    _anchor_payload, anchor_sha, anchor = _read_once(a3_paths["anchor"], "A2 anchor")
    anchor_hashes = anchor.get("artifact_hashes", {})
    expected_anchor = {
        "source_observation_sha256": hashes["source"],
        "host_observation_sha256": hashes["host"],
        "outer_audit_sha256": hashes["outer"],
    }
    if any(anchor_hashes.get(key) != value for key, value in expected_anchor.items()):
        raise FinalChainError("A2 anchor does not bind A4 publication inputs")
    official_hashes: dict[str, str] = {}
    for name, relative in (
        ("source", "audit/source-observation.json"),
        ("host", "audit/host-observation.json"),
        ("outer", "audit/formal-run-audit.json"),
    ):
        target = a3_paths["official"].joinpath(*PurePosixPath(relative).parts)
        official_hashes[name] = _file_sha(target)
        if official_hashes[name] != hashes[name]:
            raise FinalChainError(
                f"official {name} copy differs from publication intent"
            )
    receipt = {
        "a2_anchor_sha256": anchor_sha,
        "a3_publish_result": result,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "input_sha256": hashes,
        "intent_sha256": intent_sha,
        "monitor": window.receipt(),
        "official_copy_sha256": official_hashes,
        "outcome_data_inspected": False,
        "passed": True,
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
    }
    receipt_sha = a2._write_json_no_replace(paths["publication_receipt"], receipt)
    return {"passed": True, "publication_receipt_sha256": receipt_sha}


def _stable_inventory(a3: types.ModuleType, official: Path) -> dict[str, Any]:
    before, _ = a3._inventory_with_bytes(official, set())
    after, _ = a3._inventory_with_bytes(official, set())
    if before != after:
        raise FinalChainError("official archive changed between inventory passes")
    return after


def archive(amendment_path: Path) -> dict[str, Any]:
    _amendment, paths, authority, a3, _a3_amendment, a3_paths, _a3_authority, a2 = (
        _context(amendment_path)
    )
    if os.path.lexists(paths["archive_receipt"]):
        raise FinalChainError("terminal existing A4 archive receipt")
    _intent_payload, intent_sha, intent = _read_once(
        paths["publication_intent"], "A4 publication intent"
    )
    _publish_payload, publish_sha, publish_receipt = _read_once(
        paths["publication_receipt"], "A4 publication receipt"
    )
    if (
        intent.get("authority") != authority
        or publish_receipt.get("authority") != authority
        or publish_receipt.get("intent_sha256") != intent_sha
        or publish_receipt.get("passed") is not True
    ):
        raise FinalChainError("A4 publication receipts are not authoritative")
    result = a3.archive(paths["a3_amendment"])
    a3_payload, a3_sha, a3_receipt = _read_once(
        a3_paths["a3_archive"], "A3 archive receipt"
    )
    if (
        a3_receipt.get("passed") is not True
        or a3_receipt.get("assessment_authorized") is not True
        or result.get("archive_receipt_sha256") != a3_sha
    ):
        raise FinalChainError("A3 archive did not close cleanly")
    inventory = _stable_inventory(a3, a3_paths["official"])
    rows_without_a3 = [
        row for row in inventory["files"] if row["path"] != a3_paths["a3_archive"].name
    ]
    if (
        _sha(_canonical(rows_without_a3))
        != a3_receipt["archive_inventory"]["root_sha256"]
    ):
        raise FinalChainError("A3 receipt is not bound to current official inventory")
    for name, relative in (
        ("source", "audit/source-observation.json"),
        ("host", "audit/host-observation.json"),
        ("outer", "audit/formal-run-audit.json"),
    ):
        target = a3_paths["official"].joinpath(*PurePosixPath(relative).parts)
        if _file_sha(target) != intent["input_sha256"][name]:
            raise FinalChainError(f"official {name} changed after publication")
    receipt = {
        "a3_archive_receipt_sha256": _sha(a3_payload),
        "assessment_authorized": True,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "official_inventory": inventory,
        "outcome_data_inspected": False,
        "passed": True,
        "publication_intent_sha256": intent_sha,
        "publication_receipt_sha256": publish_sha,
        "schema_version": ARCHIVE_RECEIPT_SCHEMA,
    }
    receipt_sha = a2._write_json_no_replace(paths["archive_receipt"], receipt)
    return {
        "archive_receipt_sha256": receipt_sha,
        "assessment_authorized": True,
        "passed": True,
    }


def assess(amendment_path: Path) -> dict[str, Any]:
    _amendment, paths, authority, a3, a3_amendment, a3_paths, _a3_authority, a2 = (
        _context(amendment_path)
    )
    if os.path.lexists(paths["assessment_intent"]):
        raise FinalChainError(
            "terminal existing A4 assessment start intent; retry forbidden"
        )
    if os.path.lexists(paths["assessment_receipt"]):
        raise FinalChainError("terminal existing A4 assessment final receipt")
    archive_payload, archive_sha, archive_receipt = _read_once(
        paths["archive_receipt"], "A4 archive receipt"
    )
    if (
        archive_receipt.get("authority") != authority
        or archive_receipt.get("passed") is not True
        or archive_receipt.get("assessment_authorized") is not True
    ):
        raise FinalChainError("A4 archive receipt does not authorize assessment")
    inventory = _stable_inventory(a3, a3_paths["official"])
    if inventory != archive_receipt["official_inventory"]:
        raise FinalChainError("official archive changed after A4 closure")
    if os.path.lexists(a3_paths["summary"]) or os.path.lexists(
        a3_paths["assessment_audit"]
    ):
        raise FinalChainError("unbound assessment output already exists")
    a3_tokens = a3_amendment["execution"]["exact_assess_command_tokens"]
    intent = {
        "a3_assess_command_sha256": _sha(_canonical(a3_tokens)),
        "a3_assess_command_tokens": a3_tokens,
        "a4_archive_receipt_sha256": _sha(archive_payload),
        "authority": authority,
        "created_at_utc": _utc_now(),
        "experiment_id": "EXP-JAC-003",
        "one_shot": True,
        "output_absent_before_launch": True,
        "schema_version": ASSESSMENT_INTENT_SCHEMA,
    }
    intent_sha = a2._write_json_no_replace(paths["assessment_intent"], intent)
    result = a3.assess(paths["a3_amendment"])
    _audit_payload, audit_sha, audit = _read_once(
        a3_paths["assessment_audit"], "A3 assessment audit"
    )
    summary_payload, summary_sha, summary = _read_once(
        a3_paths["summary"], "development summary"
    )
    decision = summary.get("decision")
    if decision not in ("PASS", "FAIL"):
        raise FinalChainError("assessment summary decision is invalid")
    if (
        audit.get("passed") is not True
        or audit.get("output_sha256") != summary_sha
        or result.get("output_sha256") != summary_sha
        or result.get("decision") != decision
    ):
        raise FinalChainError("A3 assessment audit/summary binding mismatch")
    receipt = {
        "a3_assessment_audit_sha256": audit_sha,
        "assessment_intent_sha256": intent_sha,
        "authority": authority,
        "created_at_utc": _utc_now(),
        "decision": decision,
        "experiment_id": "EXP-JAC-003",
        "output_sha256": _sha(summary_payload),
        "passed": True,
        "schema_version": ASSESSMENT_RECEIPT_SCHEMA,
    }
    receipt_sha = a2._write_json_no_replace(paths["assessment_receipt"], receipt)
    return {
        "assessment_receipt_sha256": receipt_sha,
        "decision": decision,
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
            child.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        _path, amendment, _amendment_sha = _load_amendment(arguments.amendment)
        actual = [str(Path(sys.executable).resolve()), str(Path(__file__).resolve())]
        actual.extend(sys.argv[1:] if argv is None else list(argv))
        expected = amendment["execution"][f"exact_{arguments.phase}_command_tokens"]
        if actual != expected:
            raise FinalChainError("actual A4 command tokens differ from frozen plan")
        if arguments.phase == "pre":
            document, output, a2 = build_pre(arguments.amendment)
            if Path(os.path.abspath(arguments.output)) != output:
                raise FinalChainError("A4 pre output path mismatch")
            a2._write_json_no_replace(output, document)
            result = {"passed": True, "pre_audit_path": str(output)}
        elif arguments.phase == "publish":
            result = publish(arguments.amendment, arguments.pre_audit)
        elif arguments.phase == "archive":
            paths = _paths(amendment)
            if Path(os.path.abspath(arguments.output)) != paths["archive_receipt"]:
                raise FinalChainError("A4 archive output path mismatch")
            result = archive(arguments.amendment)
        else:
            paths = _paths(amendment)
            if Path(os.path.abspath(arguments.output)) != paths["assessment_receipt"]:
                raise FinalChainError("A4 assessment output path mismatch")
            result = assess(arguments.amendment)
    except BaseException as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
