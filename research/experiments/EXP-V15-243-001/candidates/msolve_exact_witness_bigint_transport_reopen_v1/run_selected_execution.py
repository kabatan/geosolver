#!/usr/bin/env python3.12
"""Aggregate-only selected execution over the frozen anonymous degree-one panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import selected_execution_common as COMMON


CHILD_STAGES = (
    "eligible",
    "msolve_zero_dimensional",
    "predicate_compatible_box_selected",
    "irreducible_factor_selected",
    "qqbar_exact_source_replay",
    "converted",
)
RAW_FORBIDDEN_ROOTS = (
    Path("/home/kabatan/work/solver").resolve(),
    Path("/home/kabatan/work/solver-experiment-runtime").resolve(),
    Path("/home/kabatan/work/solver-experiment-results").resolve(),
    COMMON.HERE.parents[5].resolve(),
)
THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _new_raw_root(path: Path) -> Path:
    resolved = path.resolve()
    if any(_is_within(resolved, root) for root in RAW_FORBIDDEN_ROOTS):
        raise ValueError("raw output must be outside all solver repositories")
    if resolved.exists() and any(resolved.iterdir()):
        raise ValueError("raw output directory is not empty")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    return resolved


def _load_runtime_helpers() -> tuple[Any, Any, Any]:
    safe = COMMON.load_module(
        "msolve_selected_frozen_safe_subprocess",
        COMMON.RUNTIME_ROOT / "research/infrastructure/memory_safety/safe_subprocess.py",
    )
    exclusive = COMMON.load_module(
        "msolve_selected_frozen_exclusive_run",
        COMMON.RUNTIME_ROOT / "research/harness/exclusive_run.py",
    )
    return safe, exclusive.FormalRunLease, exclusive.default_lock_path


def _read_child_result(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _conversion_is_false_authority(document: object) -> bool:
    return not (
        isinstance(document, dict)
        and document.get("ordinary_full_proposal_binding") is False
        and document.get("authority_pass") is False
        and document.get("target_release") is False
        and document.get("completeness_claim") == "NOT_MADE"
        and document.get("truth_used") is False
        and document.get("formal_scorer_used") is False
        and document.get("full98_used") is False
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--raw-output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if sys.version_info[:3] != (3, 12, 11):
        raise SystemExit("selected runner requires frozen Python 3.12.11")
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("selected runner must be pinned to exactly the expected CPU")
    os.environ.update(THREAD_ENVIRONMENT)

    request_bytes = arguments.requests.read_bytes()
    request_sha256 = hashlib.sha256(request_bytes).hexdigest()
    if request_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("request panel SHA-256 mismatch")
    requests = json.loads(request_bytes)
    if not isinstance(requests, list):
        raise SystemExit("request panel must be an array")

    raw_root = _new_raw_root(arguments.raw_output_dir)
    dependencies = COMMON.load_admission_dependencies()
    safe, FormalRunLease, default_lock_path = _load_runtime_helpers()
    admission_counts = {name: 0 for name in COMMON.ADMISSION_STAGES}
    admitted: list[tuple[int, object]] = []
    for ordinal, request in enumerate(requests):
        result = COMMON.classify_request(request, dependencies=dependencies)
        for stage in result["passed_stages"]:
            admission_counts[stage] += 1
        if result.get("eligible") is True:
            admitted.append((ordinal, request))

    child_counts = {name: 0 for name in CHILD_STAGES}
    conversion_signatures: set[str] = set()
    false_authority_count = 0
    limits = safe.Limits(
        timeout_seconds=30.0,
        rss_bytes=2 * 1024**3,
        address_space_bytes=4 * 1024**3,
        data_bytes=3 * 1024**3,
        output_bytes=1 * 1024**2,
    )
    sole_cas_lock = Path("/tmp/GeoTarget/sole-cas-admission.lock")
    safe.atomic_write_json(
        raw_root / "RUN_BINDING.json",
        {
            "schema_version": "geotarget.msolve-selected-exact-run-binding/v1",
            "candidate_id": "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1",
            "request_panel_sha256": request_sha256,
            "request_count": len(requests),
            "fixed_child_timeout_seconds": 30.0,
            "fixed_child_rss_bytes": 2 * 1024**3,
            "fixed_child_address_space_bytes": 4 * 1024**3,
            "fixed_child_data_bytes": 3 * 1024**3,
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "one_request_per_fresh_process": True,
            "ordinary_full_proposal_binding": False,
            "authority_pass": False,
            "target_release": False,
            "completeness_claim": "NOT_MADE",
            "truth_used": False,
            "formal_scorer_used": False,
            "full98_used": False,
        },
    )
    with FormalRunLease("msolve-selected-exact-execution", default_lock_path()):
        with FormalRunLease("msolve-selected-exact-execution-sole-cas", sole_cas_lock):
            for execution_index, (_ordinal, request) in enumerate(admitted):
                child_dir = raw_root / f"request-{execution_index:03d}"
                child_dir.mkdir(mode=0o700)
                request_path = child_dir / "request.json"
                safe.atomic_write_json(request_path, request)
                run_result = safe.run_guarded(
                    [
                        sys.executable,
                        str(COMMON.HERE / "execute_selected_one.py"),
                        "--request",
                        str(request_path),
                        "--raw-dir",
                        str(child_dir / "raw"),
                        "--expected-cpu",
                        str(arguments.expected_cpu),
                    ],
                    limits=limits,
                    cwd=COMMON.HERE,
                    status_path=child_dir / "process-status.json",
                )
                child = _read_child_result(child_dir / "raw/CHILD_RESULT.json")
                if child is None:
                    continue
                passed = child.get("stages_passed")
                if not isinstance(passed, list):
                    continue
                for stage in CHILD_STAGES:
                    if stage != "converted" and stage in passed:
                        child_counts[stage] += 1
                if (
                    not run_result.accepted_output
                    or "converted" not in passed
                    or child.get("converted") is not True
                ):
                    continue
                conversion = _read_child_result(child_dir / "raw/CONVERSION.json")
                signature = child.get("conversion_signature")
                if not (
                    isinstance(conversion, dict)
                    and conversion.get("status")
                    == "CONVERTED_BY_CANONICAL_EXACT_SOURCE_REPLAY"
                    and isinstance(signature, str)
                    and len(signature) == 64
                    and conversion.get("conversion_signature") == signature
                    and conversion.get("canonical_source_replay") is True
                    and conversion.get("canonical_guard_replay") is True
                    and conversion.get("canonical_bound_replay") is True
                    and conversion.get("canonical_branch_replay") is True
                    and conversion.get("raw_target_exact_replay") is True
                ):
                    continue
                child_counts["converted"] += 1
                conversion_signatures.add(signature)
                if _conversion_is_false_authority(child) or _conversion_is_false_authority(
                    conversion
                ):
                    false_authority_count += 1

    converted_count = child_counts["converted"]
    aggregate = {
        "stage_counts_cumulative": {
            **admission_counts,
            "fresh_process_started": len(admitted),
            "fresh_process_readmitted": child_counts["eligible"],
            "zero_dimensional_rur": child_counts["msolve_zero_dimensional"],
            "predicate_compatible_box_selected": child_counts[
                "predicate_compatible_box_selected"
            ],
            "irreducible_factor_selected": child_counts[
                "irreducible_factor_selected"
            ],
            "qqbar_exact_source_replay": child_counts[
                "qqbar_exact_source_replay"
            ],
            "converted": converted_count,
        },
        "converted_count": converted_count,
        "anonymous_converted_signature_count": len(conversion_signatures),
        "false_authority_count": false_authority_count,
    }
    safe.atomic_write_json(arguments.output, aggregate)
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
