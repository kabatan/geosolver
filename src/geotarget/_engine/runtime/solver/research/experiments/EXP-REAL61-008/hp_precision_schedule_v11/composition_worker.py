#!/usr/bin/env python3
"""Drop-in numerical-v3 worker for the reviewed two-prefix/four-stage primary.

The output deliberately retains the existing endpoint-bridge composition
shape so the finalist descriptor and authority checks remain unchanged.  No
fallback is run in this first comparison.  A failed primary is represented by
``authority_pass=false`` and can never produce a target descriptor.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUNNER_PATH = HERE / "run_candidate_one.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import atomic_write_json


def _load_runner():
    name = "geotarget_exp008_hp_precision_schedule_reviewed_runner"
    specification = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(RUNNER_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def compose_primary_only(
    primary: Mapping[str, object],
    *,
    source_sha256: str,
    endpoint_sha256: str,
    elapsed_seconds: float,
    deadline_seconds: float,
) -> dict[str, object]:
    """Wrap one direct authority without creating fallback authority."""

    passed = bool(
        primary.get("authority_pass") is True
        and primary.get("source_raw_sha256") == source_sha256
        and primary.get("endpoint_float64_sha256") == endpoint_sha256
    )
    status = primary.get("status")
    return {
        "schema_version": "geotarget.exp008-target-first-fallback-composition/v1",
        "status": status,
        "authority_pass": passed,
        "winner": "TWO_PREFIX_FOUR_STAGE_PRIMARY" if passed else None,
        "final_result": dict(primary),
        "attempts": [
            {
                "name": "TWO_PREFIX_FOUR_STAGE_PRIMARY",
                "attempted": True,
                "authority_pass": passed,
                "status": status,
                "source_raw_sha256": primary.get("source_raw_sha256"),
                "endpoint_float64_sha256": primary.get(
                    "endpoint_float64_sha256"
                ),
                "elapsed_seconds": elapsed_seconds,
            }
        ],
        "fallback_decision": {
            "primary_authority_failed": not passed,
            "remaining_budget_sufficient": False,
            "fallback_eligible": False,
            "fallback_enabled": False,
            "case_identity_read": False,
            "family_read": False,
            "truth_read": False,
            "known_target_count_read": False,
            "failure_status_subtype_read": False,
        },
        "input_contract": {
            "same_source_bytes_both_attempts": True,
            "same_float64_endpoint_both_attempts": True,
            "source_or_problem_modified": False,
            "bounds_added": False,
            "gauge_or_symmetry_reduction": False,
        },
        "deadline_seconds": float(deadline_seconds),
        "primary_cap_seconds": float(deadline_seconds),
        "elapsed_seconds": elapsed_seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--deadline-seconds", type=float, default=23.0)
    # Accepted only for drop-in command parity.  With fallback disabled, the
    # caller passes this equal to deadline_seconds and the full primary budget
    # is used by the reviewed candidate.
    parser.add_argument("--primary-cap-seconds", type=float, default=23.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    if (
        not math.isfinite(arguments.deadline_seconds)
        or not math.isfinite(arguments.primary_cap_seconds)
        or arguments.deadline_seconds <= 0.0
        or arguments.primary_cap_seconds <= 0.0
        or arguments.primary_cap_seconds > arguments.deadline_seconds
    ):
        raise SystemExit("invalid primary deadline")
    endpoint = json.loads(arguments.endpoint)
    if not isinstance(endpoint, list):
        raise SystemExit("endpoint must be a JSON array")

    runner = _load_runner()
    started = time.monotonic()
    primary = runner.build_candidate_authority(
        arguments.source.read_bytes(),
        arguments.source_sha256,
        endpoint,
        strict_stage_count=4,
        deadline_seconds=arguments.deadline_seconds,
    )
    elapsed = time.monotonic() - started
    endpoint_sha256 = primary.get("endpoint_float64_sha256")
    if not isinstance(endpoint_sha256, str):
        raise RuntimeError("direct authority omitted the endpoint digest")
    composition = compose_primary_only(
        primary,
        source_sha256=arguments.source_sha256,
        endpoint_sha256=endpoint_sha256,
        elapsed_seconds=elapsed,
        deadline_seconds=arguments.deadline_seconds,
    )
    atomic_write_json(arguments.output, composition)


if __name__ == "__main__":
    main()
