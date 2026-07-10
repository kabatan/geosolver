"""Outcome-safe forensic closure for the failed EXP-JAC-003 formal run.

This post-outcome tool does not execute a numerical segment.  It verifies and
executes the exact frozen safety assessor after repairing one JSON
representation mismatch on a deep copy of the raw safety capture.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import re
import tempfile
import types
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "EXP-JAC-003"
LABEL = "EXP-JAC-003-development-abba"
ASSESSOR_RELATIVE_PATH = "research/experiments/EXP-JAC-003/source/assess_development.py"
MANIFEST_RELATIVE_PATH = (
    "research/experiments/EXP-JAC-003/development-inputs/manifest.json"
)
TRUTH_RELATIVE_PATH = (
    "research/experiments/EXP-JAC-003/development-inputs/"
    "development-assessor-truth.json.gz"
)
TYPE_FAILURE = re.compile(
    rb"assess_development\.AssessmentError: dense [^\r\n]+ value type\r?$",
    re.MULTILINE,
)


class ForensicError(RuntimeError):
    """A provenance, privacy, or terminal-state invariant failed."""


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(document: Any) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ForensicError(detail)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def write_once(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"forensic output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _matrix_documents(document: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield only matrices consumed by frozen ``assess_safety``."""

    for case in document.get("cases", []):
        for start in case.get("starts", []):
            yield start["dense"]
            yield start["colored"]
    for control in document.get("incomplete_pattern_controls", []):
        yield control["dense"]
        yield control["colored"]
    for control in document.get("fallback_controls", []):
        yield control["matrix"]


def normalize_matrix_integer_tokens(
    raw_document: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize only exact JSON integer -1/0/1 matrix-entry values.

    Row and column indexes and matrix shapes remain integers.  Any other
    integer in the value position is a hard failure rather than a widening of
    the repair boundary.
    """

    normalized = copy.deepcopy(raw_document)
    integer_counts: Counter[int] = Counter()
    matrix_entry_count = 0
    for matrix in _matrix_documents(normalized):
        entries = matrix.get("entries")
        require(isinstance(entries, list), "matrix entries are not a list")
        for entry in entries:
            require(
                isinstance(entry, list) and len(entry) == 3,
                "matrix entry shape is invalid",
            )
            matrix_entry_count += 1
            value = entry[2]
            if type(value) is int:
                if value not in {-1, 0, 1}:
                    raise ForensicError(
                        "matrix value contains an integer outside {-1,0,1}"
                    )
                integer_counts[value] += 1
                entry[2] = float(value)
    normalization_count = sum(integer_counts.values())
    require(normalization_count > 0, "no repairable matrix integer token found")
    return normalized, {
        "matrix_entry_count": matrix_entry_count,
        "normalization_count": normalization_count,
        "normalized_integer_counts": {
            str(value): integer_counts[value] for value in sorted(integer_counts)
        },
        "observed_integer_values": sorted(integer_counts),
    }


def load_frozen_assessor(path: Path, expected_sha256: str) -> tuple[Any, str]:
    payload = path.read_bytes()
    observed_sha256 = sha256(payload)
    require(observed_sha256 == expected_sha256, "frozen assessor hash mismatch")
    module = types.ModuleType("geotarget_exp_jac_003_frozen_failed_formal")
    module.__file__ = str(path)
    module.__package__ = None
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module, observed_sha256


def partial_inventory(partial: Path) -> dict[str, Any]:
    require(partial.is_dir(), "formal partial directory is absent")
    segment_root = partial / "segments"
    segment_files = (
        sorted(path for path in segment_root.rglob("*") if path.is_file())
        if segment_root.exists()
        else []
    )
    # Do not open, hash, parse, or otherwise inspect a segment trace.
    require(not segment_files, "segment trace exists; this closure must not read it")
    entries: list[dict[str, Any]] = []
    for path in sorted(
        candidate for candidate in partial.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(partial).as_posix()
        payload = path.read_bytes()
        entries.append(
            {"bytes": len(payload), "path": relative, "sha256": sha256(payload)}
        )
    require(entries, "formal partial directory is empty")
    return {
        "byte_count": sum(entry["bytes"] for entry in entries),
        "file_count": len(entries),
        "files": entries,
        "inventory_sha256": sha256(canonical_bytes(entries)),
        "segment_trace_file_count": 0,
    }


def aggregate_host_categories(host: dict[str, Any]) -> list[dict[str, Any]]:
    events = host.get("contention_events")
    require(isinstance(events, list), "host contention events are malformed")
    counts: Counter[tuple[str, str]] = Counter()
    for event in events:
        require(isinstance(event, dict), "host contention event is malformed")
        category = event.get("category")
        name = event.get("name")
        require(isinstance(category, str), "host event category is malformed")
        # Aggregate-only observer events (for example aggregate CPU samples)
        # intentionally have no process name.  Preserve that absence as a
        # non-identifying category label rather than exposing event detail.
        if name is None:
            name = "<none>"
        require(isinstance(name, str), "host event name is malformed")
        counts[(category, name)] += 1
    require(
        host.get("host_contention_event_count") == len(events),
        "host contention aggregate count mismatch",
    )
    return [
        {"category": category, "count": count, "name": name}
        for (category, name), count in sorted(counts.items())
    ]


def classify_failure(
    outer: dict[str, Any], partial: Path, inventory: dict[str, Any]
) -> dict[str, Any]:
    require(
        outer.get("schema") == "geotarget.formal-performance-run/v1", "outer schema"
    )
    require(outer.get("label") == LABEL, "outer label")
    require(outer.get("outcome") == "child_failed", "outer outcome is not child_failed")
    require(outer.get("exit_code") == 1, "outer child exit code is not one")
    require(outer.get("error") is None, "outer runner reported its own error")
    paths = {entry["path"] for entry in inventory["files"]}
    required = {
        "candidate-safety.json",
        "logs/safety-assessment.stderr.log",
        "logs/safety-capture.stderr.log",
    }
    require(required <= paths, "failed formal partial lacks safety evidence")
    require(
        "safety-assessment.json" not in paths,
        "safety assessment unexpectedly completed",
    )
    require("k0-preflight.json" not in paths, "K0 preflight unexpectedly exists")
    require("capture.json" not in paths, "terminal capture receipt unexpectedly exists")
    error_path = partial / "logs" / "safety-assessment.stderr.log"
    error_payload = error_path.read_bytes()
    require(
        TYPE_FAILURE.search(error_payload) is not None,
        "unexpected formal failure traceback",
    )
    return {
        "assessor_exception_class": "AssessmentError",
        "assessor_exception_detail": "matrix-entry-value-type",
        "error_log_sha256": sha256(error_payload),
        "failure_stage": "independent-safety-assessment-before-k0-preflight",
        "protocol_subcategory": "json-number-representation-contract",
        "terminal_category": "terminal-infrastructure-or-protocol-failure",
    }


def verify_truth(
    truth_path: Path,
    manifest: dict[str, Any],
    source_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor = manifest["artifacts"]["assessor"]
    compressed = truth_path.read_bytes()
    compressed_sha256 = sha256(compressed)
    require(
        compressed_sha256 == descriptor["compressed_sha256"],
        "truth compressed manifest hash mismatch",
    )
    require(
        compressed_sha256 == source_lock["files"][TRUTH_RELATIVE_PATH],
        "truth compressed source-lock file hash mismatch",
    )
    require(
        compressed_sha256
        == source_lock["input_artifacts"]["assessor_compressed_sha256"],
        "truth compressed source-lock input hash mismatch",
    )
    require(len(compressed) == descriptor["compressed_bytes"], "truth compressed size")
    raw = gzip.decompress(compressed)
    raw_sha256 = sha256(raw)
    require(raw_sha256 == descriptor["uncompressed_sha256"], "truth raw manifest hash")
    require(
        raw_sha256 == source_lock["input_artifacts"]["assessor_uncompressed_sha256"],
        "truth raw source-lock hash mismatch",
    )
    require(len(raw) == descriptor["uncompressed_bytes"], "truth raw size")
    return json.loads(raw), {
        "compressed_bytes": len(compressed),
        "compressed_sha256": compressed_sha256,
        "uncompressed_bytes": len(raw),
        "uncompressed_sha256": raw_sha256,
    }


def build_claim_boundary(analysis: dict[str, Any]) -> str:
    normalization = analysis["safety_assessment"]["representation_normalization"]
    counts = analysis["safety_assessment"]["aggregate_counts"]
    aggregate_lines = "\n".join(
        f"- `{name}`: {value}" for name, value in sorted(counts.items())
    )
    integer_values = ", ".join(
        str(value) for value in normalization["observed_integer_values"]
    )
    return f"""# EXP-JAC-003 failed-formal claim boundary

## Decision

This capture is closed as a **terminal infrastructure/protocol failure**.  It
failed in the frozen safety assessor before K0 preflight and before any ABBA
segment.  No formal retry is authorized by this closure.  `locked=false` and
`product_connected=false`.

## What was established

- The raw partial directory, outer audit, host receipt, pre-binding audit, and
  observer-ready receipt are hash-bound by `forensic-analysis.json`.
- The exact frozen assessor bytes were hash-verified and executed.
- The official gzipped truth was checked against both the official manifest
  and source lock before it was parsed.  The frozen assessor read its safety
  reference matrices and statuses; no individual reference value is emitted.
- On a deep copy only, matrix-entry values whose exact Python type was `int`
  were converted to `float` only for the observed values {{{integer_values}}}.
  The normalization count was {normalization["normalization_count"]}.
- The frozen safety assessor returned `passed={str(analysis["safety_assessment"]["passed"]).lower()}`
  with aggregate counts:

{aggregate_lines}

## What was not established

- No K0 or K1 segment ran; the partial archive contains zero segment traces.
- No segment trace or K0 control outcome was opened.  No scalar target Gold
  value, safety-reference value, or individual case value is reported by this
  forensic closure.
- There is no ABBA timing, correctness, coverage, speed, or efficacy conclusion.
- The safety-only aggregate is not evidence that the candidate improves the
  solver and does not authorize product integration.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--partial", required=True, type=Path)
    parser.add_argument("--outer-audit", required=True, type=Path)
    parser.add_argument("--host-observation", required=True, type=Path)
    parser.add_argument("--pre-binding-audit", required=True, type=Path)
    parser.add_argument("--ready-receipt", required=True, type=Path)
    parser.add_argument("--source-lock", required=True, type=Path)
    parser.add_argument("--input-manifest", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--claim-boundary", required=True, type=Path)
    return parser


def analyze(arguments: argparse.Namespace) -> tuple[dict[str, Any], str]:
    repo = arguments.repo.resolve()
    source_lock_path = arguments.source_lock.resolve()
    manifest_path = arguments.input_manifest.resolve()
    truth_path = arguments.truth.resolve()
    assessor_path = repo / ASSESSOR_RELATIVE_PATH

    pre_payload = arguments.pre_binding_audit.read_bytes()
    pre = json.loads(pre_payload)
    require(
        pre.get("schema_version") == "exp-jac-003-formal-binding-audit/v1", "pre schema"
    )
    require(pre.get("phase") == "pre" and pre.get("passed") is True, "pre audit")
    require(pre.get("outcome_payload_files_opened") is False, "pre outcome boundary")

    source_lock_payload = source_lock_path.read_bytes()
    source_lock_sha256 = sha256(source_lock_payload)
    source_lock = json.loads(source_lock_payload)
    require(source_lock.get("experiment_id") == EXPERIMENT_ID, "source-lock experiment")
    require(
        source_lock_sha256 == pre["frozen_binding"]["source_lock_sha256"],
        "pre/source-lock hash mismatch",
    )

    manifest_payload = manifest_path.read_bytes()
    manifest_sha256 = sha256(manifest_payload)
    require(
        manifest_sha256 == source_lock["files"][MANIFEST_RELATIVE_PATH],
        "manifest source-lock file hash mismatch",
    )
    require(
        manifest_sha256
        == source_lock["input_artifacts"]["development_manifest_sha256"],
        "manifest source-lock input hash mismatch",
    )
    manifest = json.loads(manifest_payload)
    require(manifest.get("experiment_id") == EXPERIMENT_ID, "manifest experiment")

    truth, truth_binding = verify_truth(truth_path, manifest, source_lock)
    expected_assessor_sha256 = source_lock["files"][ASSESSOR_RELATIVE_PATH]
    frozen, assessor_sha256 = load_frozen_assessor(
        assessor_path, expected_assessor_sha256
    )

    inventory = partial_inventory(arguments.partial.resolve())
    partial = arguments.partial.resolve()
    raw_safety_path = partial / "candidate-safety.json"
    raw_safety_payload = raw_safety_path.read_bytes()
    raw_safety = json.loads(raw_safety_payload)
    normalized_safety, normalization = normalize_matrix_integer_tokens(raw_safety)
    frozen_result = frozen.assess_safety(normalized_safety, truth)
    require(isinstance(frozen_result, dict), "frozen assessor result is malformed")
    require(
        isinstance(frozen_result.get("counts"), dict), "frozen safety counts missing"
    )
    require(isinstance(frozen_result.get("passed"), bool), "frozen safety pass missing")

    outer_payload = arguments.outer_audit.read_bytes()
    outer_sha256 = sha256(outer_payload)
    outer = json.loads(outer_payload)
    failure = classify_failure(outer, partial, inventory)

    ready_payload = arguments.ready_receipt.read_bytes()
    ready_sha256 = sha256(ready_payload)
    ready = json.loads(ready_payload)
    require(
        ready.get("schema_version") == "geotarget.formal-host-ready/v1", "ready schema"
    )
    require(ready.get("label") == LABEL and ready.get("ready") is True, "ready receipt")

    host_payload = arguments.host_observation.read_bytes()
    host_sha256 = sha256(host_payload)
    host = json.loads(host_payload)
    require(
        host.get("schema_version") == "exp-jac-003-host-observation/v1", "host schema"
    )
    require(host.get("label") == LABEL, "host label")
    require(host.get("outer_audit_sha256") == outer_sha256, "host/outer hash mismatch")
    require(
        host.get("ready_receipt_sha256") == ready_sha256, "host/ready hash mismatch"
    )
    host_aggregate = aggregate_host_categories(host)

    analysis = {
        "artifact_bindings": {
            "candidate_safety_sha256": sha256(raw_safety_payload),
            "frozen_assessor_sha256": assessor_sha256,
            "host_observation_sha256": host_sha256,
            "input_manifest_sha256": manifest_sha256,
            "outer_audit_sha256": outer_sha256,
            "pre_binding_audit_sha256": sha256(pre_payload),
            "raw_partial_inventory_sha256": inventory["inventory_sha256"],
            "ready_receipt_sha256": ready_sha256,
            "source_lock_sha256": source_lock_sha256,
            "truth": truth_binding,
        },
        "decision": {
            "abba_segment_count": 0,
            "efficacy_conclusion": "none",
            "formal_retry_authorized": False,
            "locked": False,
            "product_connected": False,
            "terminal_classification": "terminal-infrastructure-or-protocol-failure",
        },
        "experiment_id": EXPERIMENT_ID,
        "formal_failure": failure,
        "host_receipt": {
            "contention_category_name_aggregate": host_aggregate,
        },
        "privacy_boundary": {
            "individual_case_values_reported": False,
            "k0_control_outcomes_opened": False,
            "safety_truth_artifact_parsed": True,
            "safety_truth_references_read_by_frozen_assessor": True,
            "safety_truth_values_reported": False,
            "scalar_target_gold_values_reported": False,
            "segment_trace_files_opened": False,
        },
        "raw_partial_inventory": inventory,
        "safety_assessment": {
            "aggregate_counts": dict(sorted(frozen_result["counts"].items())),
            "passed": frozen_result["passed"],
            "representation_normalization": normalization,
        },
        "schema_version": "exp-jac-003-failed-formal-forensic-analysis/v1",
    }
    claim = build_claim_boundary(analysis)
    return analysis, claim


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.output.exists() or arguments.claim_boundary.exists():
        raise FileExistsError("forensic closure output already exists")
    analysis, claim = analyze(arguments)
    payload = (
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    write_once(arguments.output, payload)
    write_once(arguments.claim_boundary, claim.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
