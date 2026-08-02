#!/usr/bin/env python3
"""Run one endpoint through public-gate-aligned numerical-v3 authority."""

from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ADAPTER_PATH = HERE.parent / "dev41_target_hp_adapter/adapter.py"
CANDIDATE_PATH = HERE / "candidate.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import atomic_write_json


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def build_public_gate_authority(
    source_payload: bytes,
    source_sha256: str,
    endpoint: list[object],
    *,
    deadline_seconds: float = 23.0,
) -> dict[str, object]:
    """Use the unchanged adapter; replace only its refinement candidate."""

    adapter = _load("geotarget_exp008_public_gate_hp_adapter", ADAPTER_PATH)
    candidate = _load("geotarget_exp008_public_gate_hp_candidate", CANDIDATE_PATH)
    started = time.monotonic()
    runtime = replace(adapter._load_runtime(), candidate=candidate)
    candidate.POSTPOLISH_STAGE_COUNT = 0
    first = adapter._build_with_runtime(
        source_payload,
        source_sha256,
        endpoint,
        deadline_seconds=deadline_seconds,
        runtime=runtime,
    )
    attempts = [
        {
            "stage_count": 0,
            "status": first.get("status"),
            "authority_pass": first.get("authority_pass") is True,
            "failure_reasons": first.get("failure_reasons"),
            "elapsed_seconds": first.get("elapsed_seconds"),
        }
    ]
    result = first
    elapsed = time.monotonic() - started
    remaining = float(deadline_seconds) - elapsed
    replay = first.get("original_numerical_replay")
    retry_eligible = bool(
        first.get("authority_pass") is not True
        and first.get("failure_reasons") == ["target_relation_authority"]
        and isinstance(replay, dict)
        and replay.get("numeric_v3_ready") is True
        and math.isfinite(remaining)
        and remaining >= 3.0
    )
    if retry_eligible:
        # Continue the exact in-memory prefix session.  Both independently
        # initialized lanes, their opaque evaluator, and all callback caches
        # are reused; the Float64 endpoint is not reparsed or recomputed.
        raw = candidate.last_session_raw_evaluator()
        source, variable_names = adapter._strict_source(
            source_payload, source_sha256
        )
        intrinsic_checks = adapter._compile_intrinsic_domains(
            source, variable_names
        )
        for slice_ordinal in range(1, 5):
            remaining = float(deadline_seconds) - (time.monotonic() - started)
            if remaining < 1.25:
                break
            # Short slices put actual original-DSL + owned-PSLQ authority
            # between polish advances.  One opaque Jacobian may finish just
            # beyond the soft slice; the outer memory-safe process deadline
            # remains the hard wall authority.
            slice_seconds = min(2.0, max(0.25, remaining - 1.0))
            corrected_refinement = candidate.continue_relation_corrective(
                deadline_seconds=slice_seconds
            )
            lane_points = [
                row["point"]
                for row in corrected_refinement.get("lanes", [])
                if row.get("point") is not None
                and row.get("status") in {"SUCCESS", "TARGET_STABILITY_REACHED"}
            ]
            replay = runtime.frozen_worker._original_replay(
                raw, lane_points, runtime.high_precision_mode
            )
            replay = adapter._apply_intrinsic_domains_to_replay(
                replay, intrinsic_checks, variable_names
            )
            authority = runtime.frozen_worker._target_authority(source, replay)
            authority_pass, failures = adapter._authority_gate(replay, authority)
            second = {
                **first,
                "status": (
                    "TARGET_AUTHORITY_READY"
                    if authority_pass
                    else authority.get(
                        "status", replay.get("status", "HP_REJECTED")
                    )
                ),
                "refinement": adapter._refinement_summary(corrected_refinement),
                "original_numerical_replay": replay,
                "target_authority": authority,
                "authority_pass": authority_pass,
                "failure_reasons": failures,
                "callback_counts": dict(getattr(raw, "counts", {})),
            }
            second = runtime.frozen_worker._jsonable(second)
            progressive = corrected_refinement.get("progressive_postprefix", {})
            attempts.append(
                {
                    "stage_count": 2,
                    "slice_ordinal": slice_ordinal,
                    "slice_seconds": slice_seconds,
                    "prefix_recomputed": False,
                    "status": second.get("status"),
                    "authority_pass": second.get("authority_pass") is True,
                    "failure_reasons": second.get("failure_reasons"),
                    "resume_eligible": progressive.get("resume_eligible"),
                    "elapsed_seconds": corrected_refinement.get("elapsed_seconds"),
                }
            )
            result = second
            if authority_pass:
                break
            if progressive.get("resume_eligible") is not True:
                break
    result["elapsed_seconds"] = time.monotonic() - started
    result["public_gate_progressive_experiment"] = {
        "independent_refinement_bits": [512, 768],
        "fresh_original_dsl_replay_bits": [512, 768, 1024],
        "configuration_residual_target_gate": "1e-100",
        "owned_pslq_proposal_confirmation_bits": [768, 1024],
        "internal_1e_195_gate_required": False,
        "attempts": attempts,
        "general_target_relation_retry_eligible": retry_eligible,
        "failure_subtype_used_only_for_general_corrective": retry_eligible,
        "source_or_problem_modified": False,
        "bounds_gauge_symmetry_or_reparameterization_added": False,
        "truth_case_family_or_target_count_read": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--deadline-seconds", type=float, default=23.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    endpoint = json.loads(arguments.endpoint)
    if not isinstance(endpoint, list):
        raise SystemExit("endpoint must be a JSON array")
    result = build_public_gate_authority(
        arguments.source.read_bytes(),
        arguments.source_sha256,
        endpoint,
        deadline_seconds=arguments.deadline_seconds,
    )
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
