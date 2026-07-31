#!/usr/bin/env python3.12
"""Root-side builder for the frozen four-record ordinary binding panel.

This script is supplied for the benchmark owner to run.  Candidate owners do
not run or inspect its outputs.  It joins the anonymous degree-one projection
panel to the already-frozen ordinary control artifacts, extracts one complete
ordinary HP attempt per match, and writes only anonymous ordinal artifacts in
the dedicated repository-external custody root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping

import ordinary_proposal_binding as binding


APPROVED_ORIGINAL_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/"
    "formal-control-development145-180-seed0/artifacts"
).resolve()
DEGREE1_REQUEST_KEYS = frozenset(
    {"source_path", "endpoint", "candidate_relation_high_to_low"}
)
FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "case_id",
        "problem_id",
        "slug",
        "family",
        "truth",
        "answer",
        "target",
        "outcome",
        "result",
        "score",
        "known_count",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--degree1-requests", type=Path, required=True)
    parser.add_argument("--degree1-requests-sha256", required=True)
    parser.add_argument("--original-artifact-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--proposal-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=4)
    parser.add_argument("--expected-cpu", type=int, default=14)
    return parser


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = binding.canonical_bytes(value) + b"\n"
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _source_path(source_root: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("source path is malformed")
    path = Path(value).resolve()
    if path.parent != source_root or path.suffix != ".json" or not path.is_file():
        raise ValueError("source path escaped anonymous panel root")
    return path


def _result_paths(root: Path) -> list[Path]:
    paths = []
    for path in root.glob("**/RESULT.json"):
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise RuntimeError("ordinary result symlink escaped frozen root") from error
        if resolved.is_file():
            paths.append(resolved)
    return sorted(set(paths))


def _matching_attempts(
    result: Mapping[str, object],
    *,
    source_sha256: str,
    endpoint_sha256: str,
    identity: tuple[tuple[int, int], int],
) -> list[Mapping[str, object]]:
    if result.get("source_sha256") != source_sha256:
        return []
    attempts = result.get("hp_attempts")
    if not isinstance(attempts, list):
        return []
    matches = []
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            continue
        if (
            attempt.get("status") != "TARGET_AUTHORITY_READY"
            or attempt.get("authority_pass") is not True
            or attempt.get("endpoint_float64_sha256") != endpoint_sha256
        ):
            continue
        if binding.BOUNDARY.descriptor_identity(attempt.get("descriptor")) != identity:
            continue
        if binding.BOUNDARY.exact_descriptor(attempt.get("descriptor")) is None:
            continue
        matches.append(attempt)
    return matches


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("manifest builder must be pinned to expected CPU")
    source_root = arguments.source_root.resolve()
    proposal_root = arguments.proposal_root.resolve()
    original_root = arguments.original_artifact_root.resolve()
    manifest = arguments.manifest.resolve()
    if source_root != binding.APPROVED_SOURCE_ROOT or not source_root.is_dir():
        raise SystemExit("source root is not the approved anonymous panel")
    if proposal_root != binding.APPROVED_PROPOSAL_ROOT:
        raise SystemExit("proposal root is not the approved dedicated custody root")
    if original_root != APPROVED_ORIGINAL_ROOT or not original_root.is_dir():
        raise SystemExit("ordinary result root is not the approved frozen control")
    if manifest != binding.APPROVED_PANEL_ROOT / "requests.json":
        raise SystemExit("selected manifest path is outside approved custody")
    if proposal_root.exists() and any(proposal_root.iterdir()):
        raise SystemExit("proposal custody root must start empty")
    if manifest.exists():
        raise SystemExit("selected manifest already exists")

    request_payload = arguments.degree1_requests.read_bytes()
    if _sha256(request_payload) != arguments.degree1_requests_sha256.lower():
        raise SystemExit("degree-one request SHA-256 mismatch")
    degree1_requests = json.loads(request_payload)
    if not isinstance(degree1_requests, list):
        raise SystemExit("degree-one requests must be an array")

    ordinary_results = []
    for path in _result_paths(original_root):
        payload = path.read_bytes()
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(document, Mapping):
            ordinary_results.append((payload, document))

    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    used_attempt_hashes: set[str] = set()
    for request in degree1_requests:
        if (
            not isinstance(request, Mapping)
            or set(request) != DEGREE1_REQUEST_KEYS
            or FORBIDDEN_KEYS & set(request)
        ):
            raise SystemExit("degree-one request crossed identity/truth boundary")
        source_path = _source_path(source_root, request["source_path"])
        source_payload = source_path.read_bytes()
        source_sha256 = _sha256(source_payload)
        source_document = json.loads(source_payload)
        if not isinstance(
            source_document, Mapping
        ) or binding.FORBIDDEN_SOURCE_KEYS & set(source_document):
            raise SystemExit("source document crossed identity/truth boundary")
        endpoint = tuple(float(value) for value in request["endpoint"])
        endpoint_sha256 = binding.endpoint_float64_sha256(endpoint)
        identity = binding.descriptor_identity(
            {
                "minimal_polynomial_high_to_low": request[
                    "candidate_relation_high_to_low"
                ],
                "selected_real_root_index": 0,
            }
        )
        matches: list[tuple[bytes, Mapping[str, object]]] = []
        for result_payload, result in ordinary_results:
            for attempt in _matching_attempts(
                result,
                source_sha256=source_sha256,
                endpoint_sha256=endpoint_sha256,
                identity=identity,
            ):
                matches.append((result_payload, attempt))
        if not matches:
            continue
        if len(matches) != 1:
            raise SystemExit("duplicate ordinary proposal match rejected")
        result_payload, attempt = matches[0]
        attempt_sha256 = binding.canonical_sha256(attempt)
        if attempt_sha256 in used_attempt_hashes:
            raise SystemExit("ordinary proposal reused by multiple selected rows")
        used_attempt_hashes.add(attempt_sha256)
        wrapper = {
            "schema_version": binding.PROPOSAL_SCHEMA,
            "source_sha256": source_sha256,
            "endpoint_float64_sha256": endpoint_sha256,
            "original_result_sha256": _sha256(result_payload),
            "ordinary_attempt_sha256": attempt_sha256,
            "ordinary_attempt": dict(attempt),
            "truth_used": False,
            "case_family_target_count_routing": False,
        }
        row = {
            "source_rel": source_path.name,
            "source_sha256": source_sha256,
            "endpoint_float64_bits_hex": binding.endpoint_bits_hex(endpoint),
            "endpoint_float64_sha256": endpoint_sha256,
            "degree1_descriptor": {
                "minimal_polynomial_high_to_low": list(identity[0]),
                "selected_real_root_index": identity[1],
            },
            "proposal_result_rel": "",  # assigned after frozen ordering
            "proposal_sha256": "",  # assigned after serialization
        }
        selected.append((row, wrapper))

    if len(selected) != arguments.expected_count:
        raise SystemExit("ordinary degree-one selected count mismatch")
    proposal_root.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for ordinal, (row, wrapper) in enumerate(selected):
        relative = f"{ordinal:04d}.json"
        path = proposal_root / relative
        _atomic_write(path, wrapper)
        frozen_row = dict(row)
        frozen_row["proposal_result_rel"] = relative
        frozen_row["proposal_sha256"] = _sha256(path.read_bytes())
        manifest_rows.append(frozen_row)
    _atomic_write(manifest, manifest_rows)
    summary = {
        "selected_count": len(manifest_rows),
        "proposal_artifact_count": len(manifest_rows),
        "selected_manifest_sha256": _sha256(manifest.read_bytes()),
        "individual_records_emitted_to_stdout": False,
        "identifiers_families_truth_outcomes_emitted": False,
    }
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
