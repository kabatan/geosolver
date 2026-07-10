"""Verify the hash-only terminal closure for the failed EXP-JAC-003 run.

Only the closure, terminal summary, and checksum index are decoded as JSON.
All captured run, safety, Gold/K0, host, and forensic artifacts are opaque byte
strings: this verifier checks their paths, sizes, and SHA-256 digests only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


CLOSURE_SCHEMA = "exp-jac-003-formal-failure-closure/v1"
SUMMARY_SCHEMA = "exp-jac-003-terminal-summary/v1"
CHECKSUM_SCHEMA = "exp-jac-003-terminal-artifact-checksums/v1"
FROZEN_HEAD = "2601dce271368e67ecafe57f4465de9415151cae"
CLASSIFICATION = "terminal-protocol-or-infrastructure-failure"
RAW_ROOT = "research/results/.EXP-JAC-003-development-abba-staging.partial"
CLOSURE_PATH = "research/experiments/EXP-JAC-003/formal-failure-closure.json"
SUMMARY_PATH = "research/results/EXP-JAC-003/summary.json"
CHECKSUM_PATH = "research/results/EXP-JAC-003/artifact-checksums.json"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

EXPECTED_RAW_RELATIVE_PATHS = frozenset(
    {
        "candidate-safety.json",
        "current-public-surface.json",
        "logs/environment.stderr.log",
        "logs/environment.stdout.log",
        "logs/julia-tests.stderr.log",
        "logs/julia-tests.stdout.log",
        "logs/public-surface.stderr.log",
        "logs/public-surface.stdout.log",
        "logs/python-tests.stderr.log",
        "logs/python-tests.stdout.log",
        "logs/safety-assessment.stderr.log",
        "logs/safety-assessment.stdout.log",
        "logs/safety-capture.stderr.log",
        "logs/safety-capture.stdout.log",
    }
)
EXPECTED_BINDING_ROLES = {
    "research/results/EXP-JAC-003/pre-binding-audit.json": "pre-binding-audit",
    "research/results/EXP-JAC-003/development-host-observation.ready.json": (
        "host-ready-receipt"
    ),
    "research/results/EXP-JAC-003-development-formal-run-audit.json": (
        "outer-run-audit"
    ),
    "research/results/EXP-JAC-003-development-host-observation.json": (
        "host-observation"
    ),
    "research/results/EXP-JAC-003/development-failed-v0/CLAIM_BOUNDARY.md": (
        "forensic-record"
    ),
    "research/results/EXP-JAC-003/development-failed-v0/forensic-analysis.json": (
        "forensic-record"
    ),
}
EXPECTED_NO_RETRY_AUTHORITY = frozenset(
    {
        "research/experiments/EXP-JAC-003/formal-execution-closure-amendment-a3.json",
        "research/experiments/EXP-JAC-003/formal-chain-final-amendment-a4.json",
    }
)
EXPECTED_ABSENT_PATHS = frozenset(
    {
        f"{RAW_ROOT}/capture.json",
        f"{RAW_ROOT}/k0-preflight.json",
        f"{RAW_ROOT}/k0-replay-assessment.json",
        f"{RAW_ROOT}/safety-assessment.json",
        "research/results/EXP-JAC-003-development-abba-staging",
        "research/results/EXP-JAC-003-development-source-observation.json",
        "research/results/EXP-JAC-003/assessment-execution-audit-a3.json",
        "research/results/EXP-JAC-003/development-abba-v0",
        "research/results/EXP-JAC-003/development-abba-v0/development-summary.json",
        "research/results/EXP-JAC-003/development-abba-v0/formal-archive-receipt-a2.json",
        "research/results/EXP-JAC-003/development-abba-v0/formal-execution-closure-receipt-a3.json",
        "research/results/EXP-JAC-003/development-abba-v0/formal-publication-seal-a2.json",
        "research/results/EXP-JAC-003/development-abba-v0/formal-run-manifest.json",
        "research/results/EXP-JAC-003/development-abba-v0/segments/segment-0.json",
        "research/results/EXP-JAC-003/development-abba-v0/segments/segment-1.json",
        "research/results/EXP-JAC-003/development-abba-v0/segments/segment-2.json",
        "research/results/EXP-JAC-003/development-abba-v0/segments/segment-3.json",
        "research/results/EXP-JAC-003/finalizer-execution-audit-a2.json",
        "research/results/EXP-JAC-003/publication-anchor-a2.json",
        "research/results/EXP-JAC-003/source-window-receipt-a3.json",
    }
)
EXPECTED_CRITICAL_BLOBS = frozenset(
    {
        "research/experiments/EXP-JAC-003/Manifest.toml",
        "research/experiments/EXP-JAC-003/development-inputs/development-assessor-truth.json.gz",
        "research/experiments/EXP-JAC-003/development-inputs/development-candidate-inputs.json.gz",
        "research/experiments/EXP-JAC-003/development-inputs/development-k0-control-traces.json.gz",
        "research/experiments/EXP-JAC-003/development-inputs/manifest.json",
        "research/experiments/EXP-JAC-003/development-source-lock.json",
        "research/experiments/EXP-JAC-003/source/assess_development.py",
        "research/experiments/EXP-JAC-003/source/assess_safety_only.py",
        "research/experiments/EXP-JAC-003/source/assessor.py",
        "research/experiments/EXP-JAC-003/source/capture_safety.jl",
        "research/experiments/EXP-JAC-003/source/formal_abba.py",
    }
)


class ClosureVerificationError(RuntimeError):
    """The terminal closure is incomplete, inconsistent, or byte-drifted."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ClosureVerificationError(message)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _load_metadata(path: Path, schema: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ClosureVerificationError(f"cannot load metadata {path}: {exc}") from exc
    _require(isinstance(document, dict), f"metadata is not an object: {path}")
    _require(document.get("schema_version") == schema, f"schema drift: {path}")
    return document


def _relative_file(repo: Path, relative: str) -> Path:
    _require(isinstance(relative, str), "artifact path is not a string")
    pure = PurePosixPath(relative)
    _require(not pure.is_absolute(), f"absolute artifact path: {relative}")
    _require(
        relative == pure.as_posix() and "\\" not in relative,
        f"noncanonical artifact path: {relative}",
    )
    _require(".." not in pure.parts, f"escaping artifact path: {relative}")
    target = repo.joinpath(*pure.parts).resolve()
    try:
        target.relative_to(repo)
    except ValueError as exc:
        raise ClosureVerificationError(
            f"artifact path escapes repository: {relative}"
        ) from exc
    return target


def _binding(row: Mapping[str, Any], label: str) -> tuple[str, str, int]:
    path = row.get("path")
    digest = row.get("sha256")
    size = row.get("size")
    _require(isinstance(path, str), f"{label} path is malformed")
    _require(
        isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest) is not None,
        f"{label} digest is malformed",
    )
    _require(
        isinstance(size, int) and not isinstance(size, bool) and size >= 0,
        f"{label} size is malformed",
    )
    return path, digest, size


def _verify_terminal_state(
    closure: Mapping[str, Any], summary: Mapping[str, Any]
) -> None:
    _require(closure.get("experiment_id") == "EXP-JAC-003", "experiment drift")
    _require(closure.get("status") == "terminal-closed", "closure is not terminal")
    _require(closure.get("classification") == CLASSIFICATION, "class drift")

    run = closure.get("formal_run")
    _require(isinstance(run, dict), "formal_run is malformed")
    expected_run = {
        "frozen_head": FROZEN_HEAD,
        "formal_attempt_count": 1,
        "execution_outcome": "failed-before-k0-and-abba",
        "failure_stage": "independent-safety-assessment-before-k0-preflight",
        "formal_retry_authorized": False,
        "formal_retry_performed": False,
        "k0_preflight_completed": False,
        "k0_control_opened_by_this_closure": False,
        "abba_segment_count": 0,
        "segment_payload_opened_by_this_closure": False,
        "capture_completed": False,
        "official_result_published": False,
        "formal_summary_produced": False,
    }
    for key, value in expected_run.items():
        _require(run.get(key) == value, f"formal state drift: {key}")

    decision = closure.get("decision")
    _require(isinstance(decision, dict), "decision is malformed")
    expected_decision = {
        "efficacy_conclusion": None,
        "formal_safety_conclusion": None,
        "formal_timing_conclusion": None,
        "locked": False,
        "product_connected": False,
        "promotion_authorized": False,
    }
    for key, value in expected_decision.items():
        _require(decision.get(key) is value, f"decision drift: {key}")

    cause = closure.get("failure_cause")
    _require(isinstance(cause, dict), "failure cause is malformed")
    _require(
        cause.get("primary")
        == "cross-language-json-number-runtime-exact-float-contract-mismatch",
        "failure cause drift",
    )
    _require(
        cause.get("stage") == "independent-safety-assessment-before-k0-preflight",
        "failure-cause stage drift",
    )
    _require(cause.get("candidate_efficacy_implication") is None, "cause claim drift")

    host = closure.get("host_invalidation")
    _require(isinstance(host, dict), "host invalidation is malformed")
    expected_host = {
        "host_contention_event_count": 158,
        "monitor_failure_count": 1,
        "clear_snapshot_count": 0,
        "wall_claim_eligible": False,
    }
    _require(host == expected_host, "host invalidation drift")

    forensic = closure.get("forensic_boundary")
    _require(isinstance(forensic, dict), "forensic boundary is malformed")
    for key in (
        "authoritative",
        "formal_evidence",
        "may_establish_candidate_efficacy",
        "may_establish_formal_safety",
    ):
        _require(forensic.get(key) is False, f"forensic boundary drift: {key}")

    successor = closure.get("successor_gate")
    _require(isinstance(successor, dict), "successor gate is malformed")
    for key in (
        "required",
        "same_experiment_retry_forbidden",
        "new_experiment_id_required",
        "new_result_blind_preregistration_required",
        "new_input_and_source_freeze_required",
        "numeric_json_contract_preflight_required",
        "host_validity_strategy_required",
    ):
        _require(successor.get(key) is True, f"successor gate drift: {key}")
    _require(
        successor.get("failed_attempt_claims_may_be_inherited") is False,
        "failed-attempt claims became inheritable",
    )

    contract = closure.get("verification_contract")
    _require(isinstance(contract, dict), "verification contract is malformed")
    for key in (
        "numerical_payloads_parsed",
        "gold_or_k0_payloads_parsed",
        "segment_payloads_parsed",
    ):
        _require(contract.get(key) is False, f"payload boundary drift: {key}")

    _require(summary.get("experiment_id") == "EXP-JAC-003", "summary experiment")
    _require(summary.get("status") == "terminal-closed", "summary status")
    _require(summary.get("classification") == CLASSIFICATION, "summary class")
    _require(summary.get("formal_run") == run, "summary formal state drift")
    _require(summary.get("decision") == decision, "summary decision drift")
    _require(summary.get("failure_cause") == cause, "summary failure-cause drift")
    _require(summary.get("host_invalidation") == host, "summary host drift")
    _require(summary.get("successor_gate") == successor, "summary successor drift")


def _closure_bindings(closure: Mapping[str, Any]) -> dict[str, tuple[str, int]]:
    artifacts = closure.get("artifact_bindings")
    _require(isinstance(artifacts, dict), "artifact_bindings is malformed")
    bindings: dict[str, tuple[str, int]] = {}
    for key in (
        "pre_binding_audit",
        "host_ready_receipt",
        "outer_run_audit",
        "host_observation",
    ):
        row = artifacts.get(key)
        _require(isinstance(row, dict), f"binding is malformed: {key}")
        path, digest, size = _binding(row, key)
        _require(path not in bindings, f"duplicate binding: {path}")
        bindings[path] = (digest, size)

    forensic = artifacts.get("forensic_records")
    _require(isinstance(forensic, list), "forensic bindings are malformed")
    for index, row in enumerate(forensic):
        _require(isinstance(row, dict), f"forensic binding {index} is malformed")
        path, digest, size = _binding(row, f"forensic binding {index}")
        _require(path not in bindings, f"duplicate binding: {path}")
        bindings[path] = (digest, size)

    raw = artifacts.get("raw_partial")
    _require(isinstance(raw, dict), "raw partial binding is malformed")
    _require(raw.get("root") == RAW_ROOT, "raw partial root drift")
    rows = raw.get("files")
    _require(isinstance(rows, list), "raw partial rows are malformed")
    raw_relative: set[str] = set()
    byte_count = 0
    inventory: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"raw binding {index} is malformed")
        relative, digest, size = _binding(row, f"raw binding {index}")
        _require(relative not in raw_relative, f"duplicate raw path: {relative}")
        raw_relative.add(relative)
        path = f"{RAW_ROOT}/{relative}"
        bindings[path] = (digest, size)
        byte_count += size
        inventory.append({"bytes": size, "path": relative, "sha256": digest})
    _require(raw_relative == EXPECTED_RAW_RELATIVE_PATHS, "raw file-set drift")
    _require(raw.get("file_count") == 14, "raw file count drift")
    _require(raw.get("byte_count") == byte_count, "raw byte count drift")
    expected_inventory = _sha256(
        _canonical(sorted(inventory, key=lambda row: row["path"]))
    )
    _require(
        raw.get("inventory_sha256") == expected_inventory,
        "raw inventory digest drift",
    )
    _require(
        set(bindings) - {f"{RAW_ROOT}/{path}" for path in raw_relative}
        == set(EXPECTED_BINDING_ROLES),
        "receipt or forensic binding-set drift",
    )
    return bindings


def _verify_raw_file_set(repo: Path) -> None:
    root = _relative_file(repo, RAW_ROOT)
    _require(root.is_dir(), "raw partial directory is absent")
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    _require(actual == EXPECTED_RAW_RELATIVE_PATHS, "raw partial file-set drift")


def _verify_no_retry_authority(repo: Path, closure: Mapping[str, Any]) -> int:
    rows = closure.get("no_retry_authority")
    _require(isinstance(rows, list), "no-retry authority is malformed")
    seen: set[str] = set()
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"no-retry authority {index} is malformed")
        path, digest, size = _binding(row, f"no-retry authority {index}")
        _require(path not in seen, f"duplicate no-retry authority: {path}")
        seen.add(path)
        target = _relative_file(repo, path)
        _require(target.is_file(), f"no-retry authority is absent: {path}")
        payload = target.read_bytes()
        _require(len(payload) == size, f"no-retry authority size drift: {path}")
        _require(_sha256(payload) == digest, f"no-retry authority drift: {path}")
    _require(seen == EXPECTED_NO_RETRY_AUTHORITY, "no-retry authority set drift")
    return len(rows)


def _verify_absence(repo: Path, relative_paths: Sequence[str]) -> None:
    _require(set(relative_paths) == EXPECTED_ABSENT_PATHS, "absence set drift")
    for relative in relative_paths:
        _require(
            not _relative_file(repo, relative).exists(),
            f"required-absent path exists: {relative}",
        )


def _verify_artifact_index(
    repo: Path,
    checksum: Mapping[str, Any],
    bindings: Mapping[str, tuple[str, int]],
    absent_paths: Sequence[str],
) -> int:
    _require(checksum.get("experiment_id") == "EXP-JAC-003", "index experiment")
    _require(checksum.get("hash_algorithm") == "sha256", "index algorithm")
    _require(checksum.get("self_included") is False, "checksum self-inclusion")
    _require(
        checksum.get("required_absent_paths") == list(absent_paths), "index absence"
    )
    rows = checksum.get("artifacts")
    _require(isinstance(rows, list), "checksum artifacts are malformed")
    _require(checksum.get("artifact_count") == len(rows), "index count drift")

    expected_roles = {
        **EXPECTED_BINDING_ROLES,
        **{
            f"{RAW_ROOT}/{relative}": "raw-partial"
            for relative in EXPECTED_RAW_RELATIVE_PATHS
        },
        CLOSURE_PATH: "failure-closure",
        SUMMARY_PATH: "terminal-summary",
    }
    actual: dict[str, tuple[str, int]] = {}
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"checksum row {index} is malformed")
        path, digest, size = _binding(row, f"checksum row {index}")
        _require(path not in actual, f"duplicate checksum path: {path}")
        _require(row.get("role") == expected_roles.get(path), f"role drift: {path}")
        target = _relative_file(repo, path)
        _require(target.is_file(), f"artifact is absent: {path}")
        payload = target.read_bytes()
        _require(len(payload) == size, f"artifact size drift: {path}")
        _require(_sha256(payload) == digest, f"artifact digest drift: {path}")
        actual[path] = (digest, size)
    _require(set(actual) == set(expected_roles), "checksum path-set drift")
    for path, expected in bindings.items():
        _require(actual.get(path) == expected, f"closure/index binding drift: {path}")
    return len(rows)


def _git(repo: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ClosureVerificationError(f"git {' '.join(arguments)} failed: {message}")
    return result.stdout


def _git_text(repo: Path, *arguments: str) -> str:
    return _git(repo, *arguments).decode("ascii").strip()


def _verify_frozen_git(repo: Path, closure: Mapping[str, Any]) -> int:
    frozen = closure.get("frozen_git")
    _require(isinstance(frozen, dict), "frozen_git is malformed")
    commit = frozen.get("commit")
    _require(commit == FROZEN_HEAD, "frozen commit drift")
    _require(_git_text(repo, "cat-file", "-t", commit) == "commit", "missing commit")
    _require(
        _git_text(repo, "rev-parse", f"{commit}^") == frozen.get("parent"),
        "frozen parent drift",
    )
    _require(
        _git_text(repo, "rev-parse", f"{commit}^{{tree}}") == frozen.get("tree"),
        "frozen tree drift",
    )
    rows = frozen.get("critical_blobs")
    _require(isinstance(rows, list), "critical blob list is malformed")
    seen: set[str] = set()
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"critical blob {index} is malformed")
        path, digest, size = _binding(row, f"critical blob {index}")
        _require(path not in seen, f"duplicate critical blob: {path}")
        seen.add(path)
        oid = _git_text(repo, "rev-parse", f"{commit}:{path}")
        _require(oid == row.get("git_oid"), f"frozen blob OID drift: {path}")
        payload = _git(repo, "cat-file", "blob", oid)
        _require(len(payload) == size, f"frozen blob size drift: {path}")
        _require(_sha256(payload) == digest, f"frozen blob digest drift: {path}")
    _require(seen == EXPECTED_CRITICAL_BLOBS, "critical blob path-set drift")
    return len(rows)


def verify(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    closure_path = _relative_file(repo, CLOSURE_PATH)
    summary_path = _relative_file(repo, SUMMARY_PATH)
    checksum_path = _relative_file(repo, CHECKSUM_PATH)
    closure = _load_metadata(closure_path, CLOSURE_SCHEMA)
    summary = _load_metadata(summary_path, SUMMARY_SCHEMA)
    checksum = _load_metadata(checksum_path, CHECKSUM_SCHEMA)

    _verify_terminal_state(closure, summary)
    closure_digest = _sha256(closure_path.read_bytes())
    _require(
        summary.get("formal_failure_closure_sha256") == closure_digest,
        "summary closure digest drift",
    )
    absent = closure.get("required_absent_paths")
    _require(isinstance(absent, list), "required_absent_paths is malformed")
    _verify_absence(repo, absent)
    bindings = _closure_bindings(closure)
    _verify_raw_file_set(repo)
    authority_count = _verify_no_retry_authority(repo, closure)
    artifact_count = _verify_artifact_index(repo, checksum, bindings, absent)
    frozen_blob_count = _verify_frozen_git(repo, closure)
    return {
        "schema_version": "exp-jac-003-terminal-closure-verification/v1",
        "experiment_id": "EXP-JAC-003",
        "status": "passed",
        "classification": CLASSIFICATION,
        "artifact_count": artifact_count,
        "no_retry_authority_count": authority_count,
        "frozen_blob_count": frozen_blob_count,
        "numerical_payloads_parsed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="repository root (defaults to the root containing this verifier)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = verify(arguments.repo)
    except ClosureVerificationError as exc:
        print(f"terminal closure verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
