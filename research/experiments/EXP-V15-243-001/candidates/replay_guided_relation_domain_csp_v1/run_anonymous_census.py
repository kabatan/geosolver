#!/usr/bin/env python3
"""Root-guarded aggregate-only census over the frozen degree-one panel."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


SCHEMA = "geotarget.relation-domain-csp-degree1-census/v1"
REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
CANDIDATE_SHA256 = "da92a984d6d3e4452649a87207835dca0bdbce28306108fd787aa6a35a60776e"
GUARD_SHA256 = "e7d5bb89ae2a296c6c7f5f43d532a9cc384f092504008d052f733060e9510901"
SAFE_SHA256 = "76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5"
REQUEST_COUNT = 85
ROW_SECONDS = 3.0
ROW_RSS_BYTES = 512 * 1024**2
ROW_OUTPUT_BYTES = 16 * 1024
HERE = Path(__file__).resolve().parent
ROW_WORKER = HERE / "anonymous_census_row.py"
CANDIDATE = HERE / "candidate.py"
SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
APPROVED_RESULT_ROOT = Path("/home/kabatan/work/solver-experiment-results").resolve()
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver").resolve()
GUARD_PATH = RUNTIME_ROOT / (
    "research/experiments/EXP-V15-243-001/candidates/hp_lock_scheduler/"
    "root_scoped_subprocess.py"
)
SAFE_PATH = RUNTIME_ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"


class CensusRejected(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _guard_modules():
    if _sha256(GUARD_PATH) != GUARD_SHA256 or _sha256(SAFE_PATH) != SAFE_SHA256:
        raise CensusRejected("ROOT_GUARD_FREEZE_MISMATCH")
    if str(RUNTIME_ROOT) not in sys.path:
        sys.path.insert(0, str(RUNTIME_ROOT))
    guard = _load("relation_domain_root_scoped_guard", GUARD_PATH)
    from research.infrastructure.memory_safety import safe_subprocess as safe

    return guard, safe


def _source_path(value: object, index: int) -> Path:
    try:
        path = Path(str(value)).resolve(strict=True)
    except OSError as error:
        raise CensusRejected("SOURCE_PATH_REJECTED") from error
    if path.parent != SOURCE_ROOT or path.name != f"{index:04d}.json" or path.is_symlink():
        raise CensusRejected("SOURCE_CUSTODY_REJECTED")
    return path


def run(requests_path: Path, output_root: Path, cpu: int) -> dict[str, Any]:
    if _sha256(requests_path) != REQUESTS_SHA256:
        raise CensusRejected("REQUEST_PANEL_SHA256_MISMATCH")
    if _sha256(CANDIDATE) != CANDIDATE_SHA256:
        raise CensusRejected("CANDIDATE_SHA256_MISMATCH")
    requests = json.loads(requests_path.read_bytes())
    if not isinstance(requests, list) or len(requests) != REQUEST_COUNT:
        raise CensusRejected("REQUEST_PANEL_SHAPE_REJECTED")
    output_root = output_root.resolve()
    try:
        output_root.relative_to(APPROVED_RESULT_ROOT)
    except ValueError as error:
        raise CensusRejected("OUTPUT_ROOT_REJECTED") from error
    if output_root.exists():
        raise CensusRejected("OUTPUT_ROOT_EXISTS")
    output_root.mkdir()
    (output_root / "rows").mkdir()
    (output_root / "status").mkdir()
    guard, safe = _guard_modules()
    limits = safe.Limits(
        timeout_seconds=ROW_SECONDS,
        rss_bytes=ROW_RSS_BYTES,
        address_space_bytes=2 * 1024**3,
        data_bytes=1536 * 1024**2,
        output_bytes=ROW_OUTPUT_BYTES,
        tail_bytes=4096,
        poll_seconds=0.02,
        terminate_grace_seconds=0.25,
    )
    environment = dict(os.environ)
    environment.update(safe.THREAD_ENV)
    environment["PYTHONHASHSEED"] = "0"
    classifications: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    ready = full_replay_ready = proposals = 0
    authority_violations = selection_violations = malformed_rows = 0
    ready_signatures: set[str] = set()
    peak_rss = 0
    maximum_row_seconds = 0.0
    for index, request in enumerate(requests):
        if not isinstance(request, Mapping) or set(request) != {
            "source_path", "endpoint", "candidate_relation_high_to_low"
        }:
            raise CensusRejected("REQUEST_ROW_SHAPE_REJECTED")
        source = _source_path(request["source_path"], index)
        source_sha256 = _sha256(source)
        row_output = output_root / "rows" / f"{index:04d}.json"
        command = [
            sys.executable,
            str(ROW_WORKER),
            "--source",
            str(source),
            "--source-sha256",
            source_sha256,
            "--output",
            str(row_output),
        ]
        process = guard.run_guarded(
            command,
            limits=limits,
            process_group_rss_bytes=ROW_RSS_BYTES,
            environment=environment,
            cwd=HERE,
            status_path=output_root / "status" / f"{index:04d}.json",
        )
        classifications[process.classification] += 1
        peak_rss = max(peak_rss, int(process.peak_process_group_rss_bytes))
        maximum_row_seconds = max(maximum_row_seconds, float(process.elapsed_seconds))
        if not process.accepted_output or not row_output.is_file() or row_output.stat().st_size > ROW_OUTPUT_BYTES:
            malformed_rows += 1
            continue
        try:
            row = json.loads(row_output.read_bytes())
        except (OSError, json.JSONDecodeError):
            malformed_rows += 1
            continue
        if not isinstance(row, Mapping) or row.get("schema_version") != "geotarget.relation-domain-csp-anonymous-row/v1":
            malformed_rows += 1
            continue
        row_ready = row.get("status") == "PROPOSAL_READY_HOLD"
        ready += int(row_ready)
        proposals += int(row.get("proposal_count", 0)) if row_ready else 0
        replay_all = row.get("full_replay_all") is True
        full_replay_ready += int(replay_all)
        if replay_all:
            ready_signatures.add(str(row.get("structural_signature_sha256")))
        reasons[str(row.get("reason_category", "MALFORMED"))] += 1
        authority_violations += int(row.get("authority_or_release_violation") is not False)
        selection_violations += int(
            row.get("selection_read_raw_target") is not False
            or row.get("selection_used_case_id_family_truth_or_outcome") is not False
            or row.get("truth_score_outcome_read") is not False
            or row.get("formal_authority_invoked") is not False
        )
    gate = bool(
        full_replay_ready >= 3
        and len(ready_signatures) >= 3
        and authority_violations == 0
        and selection_violations == 0
        and malformed_rows == 0
    )
    result = {
        "schema_version": SCHEMA,
        "request_count": REQUEST_COUNT,
        "processed_row_count": sum(classifications.values()),
        "process_classifications": dict(sorted(classifications.items())),
        "proposal_ready_source_count": ready,
        "full_replay_ready_source_count": full_replay_ready,
        "full_replay_ready_signature_count": len(ready_signatures),
        "proposal_count": proposals,
        "failure_taxonomy": dict(sorted(reasons.items())),
        "malformed_or_resource_failed_row_count": malformed_rows,
        "authority_or_release_violation_count": authority_violations,
        "selection_or_truth_boundary_violation_count": selection_violations,
        "maximum_observed_process_group_rss_bytes": peak_rss,
        "maximum_observed_row_wall_seconds": maximum_row_seconds,
        "per_row_hard_wall_seconds": ROW_SECONDS,
        "per_row_rss_bytes": ROW_RSS_BYTES,
        "per_row_output_bytes": ROW_OUTPUT_BYTES,
        "requests_sha256": REQUESTS_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "root_guard_sha256": GUARD_SHA256,
        "individual_records_paths_ids_expressions_endpoints_targets_emitted": False,
        "endpoint_or_degree1_relation_used_for_candidate_routing": False,
        "truth_score_outcome_used": False,
        "formal_authority_invoked": False,
        "authority_pass": False,
        "target_release": False,
        "decision": "GO_HEADROOM_REVIEW_HOLD" if gate else "STOP_ANONYMOUS_CENSUS",
    }
    (output_root / "AGGREGATE.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    arguments = parser.parse_args()
    if arguments.requests_sha256 != REQUESTS_SHA256 or arguments.cpu != 14:
        raise CensusRejected("PREREGISTERED_CUSTODY_MISMATCH")
    result = run(arguments.requests, arguments.output_root, arguments.cpu)
    print(json.dumps(result, sort_keys=True))
    if result["decision"] != "GO_HEADROOM_REVIEW_HOLD":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
