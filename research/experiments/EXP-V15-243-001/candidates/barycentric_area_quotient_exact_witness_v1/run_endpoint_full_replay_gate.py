#!/usr/bin/env python3
"""Bounded aggregate-only endpoint gate for the barycentric witness.

The candidate is run before the stored baseline terminal is opened.  The
stored terminal is consulted only for candidate-ready sources and only to
count whether an already-existing exact target was present.  No descriptor,
target, endpoint, source identity, path, or per-source outcome is emitted.
This gate never grants formal authority or target release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence

import candidate
import scan_prevalence as prevalence


SCHEMA = "geotarget.barycentric-area-quotient-endpoint-gate/v1"
APPROVED_RESULT_ROOT = Path("/home/kabatan/work/solver-experiment-results").resolve()
MAX_SOURCE_FILES = 145
MAX_ENDPOINTS_PER_SOURCE = 64
MAX_TOTAL_ENDPOINTS = MAX_SOURCE_FILES * MAX_ENDPOINTS_PER_SOURCE
EXPECTED_ACTIVATED_SOURCES = 7


class GateRejected(ValueError):
    pass


def _approved_directory(path: Path) -> Path:
    if path.is_symlink():
        raise GateRejected("ROOT_IS_SYMLINK")
    resolved = path.resolve()
    try:
        resolved.relative_to(APPROVED_RESULT_ROOT)
    except ValueError as error:
        raise GateRejected("ROOT_OUTSIDE_APPROVED_RESULTS") from error
    if not resolved.is_dir():
        raise GateRejected("ROOT_NOT_DIRECTORY")
    return resolved


def _regular_json_files(root: Path) -> tuple[Path, ...]:
    files = tuple(
        path
        for path in sorted(root.iterdir())
        if not path.is_symlink()
        and path.is_file()
        and path.suffix == ".json"
        and stat.S_ISREG(path.lstat().st_mode)
    )
    if len(files) > MAX_SOURCE_FILES:
        raise GateRejected("SOURCE_FILE_CAP")
    return files


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_source(path: Path) -> tuple[bytes, Mapping[str, Any]]:
    payload = path.read_bytes()
    if len(payload) > prevalence.MAX_SOURCE_BYTES:
        raise GateRejected("SOURCE_BYTE_CAP")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateRejected("SOURCE_JSON_REJECTED") from error
    if not isinstance(document, Mapping):
        raise GateRejected("SOURCE_NOT_MAPPING")
    return payload, document


def _endpoint_plans(case_root: Path) -> tuple[tuple[Path, tuple[float, ...]], ...]:
    if case_root.is_symlink() or not case_root.is_dir():
        return ()
    result = []
    for path in sorted(case_root.glob("reservoir-batch-*/hp/*/PLAN.json")):
        if len(result) >= MAX_ENDPOINTS_PER_SOURCE:
            break
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
            continue
        try:
            plan = json.loads(path.read_bytes())
            endpoint = tuple(float(value) for value in plan["endpoint"])
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            continue
        if endpoint and all(math.isfinite(value) for value in endpoint):
            result.append((path, endpoint))
    return tuple(result)


def _baseline_exact_target_count(result_path: Path, source_sha256: str) -> int | None:
    """Read a baseline terminal only after the caller has a ready candidate."""

    if result_path.is_symlink() or not result_path.is_file():
        return None
    try:
        result = json.loads(result_path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(result, Mapping):
        return None
    targets = result.get("distinct_exact_targets")
    accepted_envelope = bool(
        result.get("schema_version")
        == "geotarget.exp008-finalist-numeric-worker-v15/v1"
        and result.get("completed") is True
        and result.get("source_sha256") == source_sha256
        and result.get("source_bytes_unchanged") is True
        and result.get("within_total_wall_budget") is True
        and isinstance(targets, list)
        and result.get("truth_case_family_known_target_count_read") is False
        and result.get("source_or_problem_modified") is False
        and result.get("variables_or_equations_removed") is False
        and result.get("bounds_added_or_inferred") is False
        and result.get("gauge_or_symmetry_reduction") is False
        and result.get("coordinate_reparameterization") is False
    )
    return len(targets) if accepted_envelope else None


def run(source_root: Path, artifact_root: Path) -> dict[str, Any]:
    source_root = _approved_directory(source_root)
    artifact_root = _approved_directory(artifact_root)
    source_files = _regular_json_files(source_root)

    activated_sources = 0
    activated_endpoints = 0
    candidate_ready_sources = 0
    candidate_ready_endpoints = 0
    candidate_proposals = 0
    candidate_full_replay_failures = 0
    candidate_authority_or_release_violations = 0
    baseline_reads = 0
    baseline_malformed_after_ready = 0
    baseline_exact_ready_sources = 0
    pure_gain_sources = 0
    malformed_sources = 0
    endpoint_count = 0
    activated_signatures: set[str] = set()
    candidate_ready_signatures: set[str] = set()
    pure_gain_signatures: set[str] = set()
    custody_rows: list[tuple[str, tuple[str, ...]]] = []

    for source_path in source_files:
        try:
            payload, document = _load_source(source_path)
        except GateRejected:
            malformed_sources += 1
            continue
        source_sha256 = _sha256_bytes(payload)
        quotient_sites = prevalence._quotients(document)
        if not quotient_sites:
            continue
        signatures = tuple(sorted({signature for _node, signature in quotient_sites}))
        quotient_nodes = tuple(node for node, _signature in quotient_sites)
        plans = _endpoint_plans(artifact_root / source_path.stem)
        endpoint_count += len(plans)
        if endpoint_count > MAX_TOTAL_ENDPOINTS:
            raise GateRejected("TOTAL_ENDPOINT_CAP")
        active = tuple(
            (path, endpoint)
            for path, endpoint in plans
            if prevalence._rational_activation(document, endpoint, quotient_nodes)
        )
        if not active:
            continue
        activated_sources += 1
        activated_endpoints += len(active)
        activated_signatures.update(signatures)

        ready = None
        for plan_path, endpoint in active:
            # Candidate-first: this exact reconstruction and untouched-source
            # prototype replay happens before RESULT.json is opened below.
            proposal = candidate.propose(document, endpoint)
            if proposal.get("status") != "PROPOSAL_READY_HOLD":
                continue
            candidate_ready_endpoints += 1
            proposals = proposal.get("proposals")
            if not isinstance(proposals, list) or not proposals:
                candidate_full_replay_failures += 1
                continue
            candidate_proposals += len(proposals)
            candidate_full_replay_failures += sum(
                not isinstance(item, Mapping)
                or item.get("untouched_source_raw_target_replay_pass") is not True
                for item in proposals
            )
            candidate_authority_or_release_violations += int(
                proposal.get("authority_pass") is not False
                or proposal.get("target_release") is not False
                or any(
                    not isinstance(item, Mapping)
                    or item.get("authority_pass") is not False
                    or item.get("target_release") is not False
                    for item in proposals
                )
            )
            ready = proposal
            break
        custody_rows.append(
            (
                source_sha256,
                tuple(_sha256_bytes(path.read_bytes()) for path, _endpoint in active),
            )
        )
        if ready is None:
            continue

        candidate_ready_sources += 1
        candidate_ready_signatures.update(signatures)

        # This is the first and only stored baseline-terminal read for this
        # source.  Non-ready sources never cross this line.
        baseline_reads += 1
        baseline_count = _baseline_exact_target_count(
            artifact_root / source_path.stem / "RESULT.json", source_sha256
        )
        if baseline_count is None:
            baseline_malformed_after_ready += 1
        elif baseline_count > 0:
            baseline_exact_ready_sources += 1
        else:
            pure_gain_sources += 1
            pure_gain_signatures.update(signatures)

    custody_payload = json.dumps(
        sorted(custody_rows), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    gate_pass = bool(
        len(source_files) == MAX_SOURCE_FILES
        and malformed_sources == 0
        and activated_sources == EXPECTED_ACTIVATED_SOURCES
        and candidate_ready_sources >= 2
        and pure_gain_sources >= 2
        and len(pure_gain_signatures) >= 2
        and candidate_full_replay_failures == 0
        and candidate_authority_or_release_violations == 0
        and baseline_malformed_after_ready == 0
        and baseline_reads == candidate_ready_sources
    )
    return {
        "schema_version": SCHEMA,
        "source_count_scanned": len(source_files),
        "malformed_source_count": malformed_sources,
        "saved_endpoint_count_bounded": endpoint_count,
        "activated_source_count": activated_sources,
        "activated_endpoint_count": activated_endpoints,
        "activated_signature_count": len(activated_signatures),
        "candidate_ready_source_count": candidate_ready_sources,
        "candidate_ready_endpoint_count": candidate_ready_endpoints,
        "candidate_ready_signature_count": len(candidate_ready_signatures),
        "candidate_proposal_count": candidate_proposals,
        "candidate_full_replay_failure_count": candidate_full_replay_failures,
        "candidate_authority_or_release_violation_count": (
            candidate_authority_or_release_violations
        ),
        "baseline_terminal_read_count_after_candidate_ready": baseline_reads,
        "baseline_terminal_read_count_before_candidate_ready": 0,
        "baseline_malformed_count_after_candidate_ready": baseline_malformed_after_ready,
        "baseline_exact_ready_source_count": baseline_exact_ready_sources,
        "pure_gain_source_count": pure_gain_sources,
        "pure_gain_signature_count": len(pure_gain_signatures),
        "expected_activated_source_count": EXPECTED_ACTIVATED_SOURCES,
        "minimum_pure_gain_source_count": 2,
        "minimum_pure_gain_signature_count": 2,
        "candidate_first_exact_reconstruction": True,
        "baseline_read_only_after_candidate_ready": True,
        "individual_records_paths_ids_expressions_endpoints_targets_emitted": False,
        "truth_score_outcome_used": False,
        "canonical_formal_authority_invoked": False,
        "authority_pass": False,
        "target_release": False,
        "input_custody_sha256": hashlib.sha256(custody_payload).hexdigest(),
        "candidate_sha256": _sha256_bytes(Path(candidate.__file__).read_bytes()),
        "decision": "GO_PROTOTYPE_FULL_REPLAY_HOLD" if gate_pass else "STOP_ENDPOINT_GATE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output_parent = _approved_directory(arguments.output.parent)
    output = (output_parent / arguments.output.name).resolve()
    if output.parent != output_parent or output.suffix != ".json" or output.exists():
        raise GateRejected("OUTPUT_PATH_MALFORMED_OR_EXISTS")
    result = run(arguments.source_root, arguments.artifact_root)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if result["decision"] != "GO_PROTOTYPE_FULL_REPLAY_HOLD":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
