#!/usr/bin/env python3
"""Truth-blind exact-coordinate fallback for one Float64 v15 endpoint.

The ordinary target-only HP authority remains primary.  This worker is a
failure-only lane: it independently refines every source coordinate at 768
and 1024 bits, proposes bounded algebraic descriptors, and accepts a target
only after both the frozen v15 evaluator replays source guards, branches and
hard feasibility at three precision lanes, and FLINT QQBar replays source
constraints, guards, bounds, and the raw answer exactly.
"""

from __future__ import annotations

import argparse
import ctypes
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence

from candidate import certify_exact_coordinate_witness


HERE = Path(__file__).resolve().parent
WORKSPACE = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
PYTHON = WORKSPACE / "python/.venv/bin/python"
REFINER_ROOT = WORKSPACE / "research/experiments/EXP-REAL61-001"
REFINER = REFINER_ROOT / "refine_proposals_worker.py"
SCHEMA = "geotarget.v15-243-exact-coordinate-fallback/v1"
TRIAL_LABEL = "truth-blind exact-coordinate fallback"
THREAD_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_GC_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
}


class FallbackFailure(RuntimeError):
    """The optional lane could not establish exact source authority."""


def _pdeathsig() -> int:
    value = ctypes.c_int(0)
    if ctypes.CDLL(None, use_errno=True).prctl(2, ctypes.byref(value), 0, 0, 0) != 0:
        return -1
    return int(value.value)


def _valid_isolator(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    left = value.get("left")
    right = value.get("right")
    multiplicity = value.get("multiplicity")
    root_index = value.get("real_root_index")
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or not isinstance(multiplicity, int)
        or isinstance(multiplicity, bool)
        or multiplicity != 1
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
    ):
        return False
    try:
        return Fraction(left) <= Fraction(right)
    except (ValueError, ZeroDivisionError):
        return False


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _endpoint_sha256(endpoint: Sequence[float]) -> str:
    values = tuple(float(value) for value in endpoint)
    payload = struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )
    return _sha256(payload)


def _source_contract(
    source: Path,
    source_sha256: str,
    endpoint: Sequence[float],
    endpoint_sha256: str,
) -> tuple[bytes, dict[str, Any]]:
    payload = source.read_bytes()
    if _sha256(payload) != source_sha256:
        raise FallbackFailure("source SHA-256 mismatch")
    if _endpoint_sha256(endpoint) != endpoint_sha256:
        raise FallbackFailure("Float64 endpoint SHA-256 mismatch")
    document = json.loads(payload)
    variables = document.get("variables") if isinstance(document, Mapping) else None
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if (
        not isinstance(document, dict)
        or document.get("task") != "solve"
        or not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or len(names) != len(endpoint)
        or document.get("post_process") not in (None, "")
    ):
        raise FallbackFailure("untouched raw-answer solve JSON is required")
    return payload, document


def _proposal_contract(
    document: Mapping[str, Any],
    proposal_document: Mapping[str, Any],
    endpoint: Sequence[float],
    source_sha256: str,
) -> dict[str, Any]:
    names = list((document.get("variables") or {}).get("names") or [])
    proposals = proposal_document.get("proposals")
    common = bool(
        proposal_document.get("schema_version")
        == "geotarget.real61-refined-proposals/v1"
        and proposal_document.get("authority")
        == "DEVELOPMENT_PROPOSALS_ONLY"
        and proposal_document.get("truth_status") == "NOT_MATERIALIZED"
        and proposal_document.get("accuracy_claims_permitted") is False
        and proposal_document.get("completeness_claims_permitted") is False
        and proposal_document.get("case_sha256") == source_sha256
        and proposal_document.get("input_seed_count") == 1
        and isinstance(proposals, list)
        and len(proposals) == 1
    )
    if not common:
        raise FallbackFailure("independent refinement terminal contract failed")
    proposal = proposals[0]
    source = proposal.get("source") if isinstance(proposal, Mapping) else None
    lane_methods = (
        proposal.get("lane_methods") if isinstance(proposal, Mapping) else None
    )
    lane_working = (
        proposal.get("lane_working_decimal_digits")
        if isinstance(proposal, Mapping)
        else None
    )
    lane_source_replay = (
        proposal.get("lane_source_replay")
        if isinstance(proposal, Mapping)
        else None
    )
    float_source_replay = (
        proposal.get("float_source_replay")
        if isinstance(proposal, Mapping)
        else None
    )
    coordinate_a = (
        proposal.get("coordinates_768bit_minimum")
        if isinstance(proposal, Mapping)
        else None
    )
    coordinate_b = (
        proposal.get("coordinates_1024bit_minimum")
        if isinstance(proposal, Mapping)
        else None
    )
    if (
        not isinstance(proposal, dict)
        or proposal.get("status") != "PSLQ_PROPOSAL"
        or proposal.get("independent_precision_lanes") is not True
        or not isinstance(float_source_replay, Mapping)
        or float_source_replay.get("evaluation_defined") is not True
        or float_source_replay.get("guard_ok") is not True
        or float_source_replay.get("hard_feasible") is not True
        or float_source_replay.get("residual_is_authority") is not False
        or not isinstance(float_source_replay.get("residual_inf"), (int, float))
        or isinstance(float_source_replay.get("residual_inf"), bool)
        or not math.isfinite(float(float_source_replay.get("residual_inf")))
        or float(float_source_replay.get("residual_inf")) < 0.0
        or not isinstance(source, Mapping)
        or source.get("source_candidate") != TRIAL_LABEL
        or source.get("endpoint") != [float(value) for value in endpoint]
        or not isinstance(lane_methods, Mapping)
        or set(lane_methods) != {"155", "232", "320"}
        or not all(isinstance(value, str) for value in lane_methods.values())
        or not isinstance(lane_working, Mapping)
        or set(lane_working) != {"155", "232", "320"}
        or any(
            not isinstance(lane_working[key], int)
            or isinstance(lane_working[key], bool)
            or lane_working[key] < int(key)
            for key in ("155", "232", "320")
        )
        or not isinstance(lane_source_replay, Mapping)
        or set(lane_source_replay) != {"155", "232", "320"}
        or any(
            not isinstance(lane_source_replay[key], Mapping)
            or lane_source_replay[key]
            != {
                "replay_decimal_digits": int(key),
                "guard_replay_decimal_digits": int(key),
                "hard_feasibility_replay_decimal_digits": int(key),
                "residual_replay_decimal_digits": int(key),
                "answer_replay_decimal_digits": int(key),
                "residual_threshold": {
                    "155": "1e-100",
                    "232": "1e-150",
                    "320": "1e-200",
                }[key],
                "guard_ok": True,
                "hard_feasible": True,
                "residual_reached": True,
                "answer_defined": True,
            }
            for key in ("155", "232", "320")
        )
        or not isinstance(coordinate_a, list)
        or not isinstance(coordinate_b, list)
        or len(coordinate_a) != len(names)
        or len(coordinate_b) != len(names)
        or not all(isinstance(value, str) for value in coordinate_a)
        or not all(isinstance(value, str) for value in coordinate_b)
        or not isinstance(proposal.get("answer_768bit_minimum"), str)
        or not isinstance(proposal.get("answer_1024bit_minimum"), str)
    ):
        raise FallbackFailure("independent refinement proposal contract failed")
    return proposal


def _run_refiner(
    source: Path,
    source_sha256: str,
    endpoint: Sequence[float],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    trial = {
        "accuracy_claims_permitted": False,
        "candidate": TRIAL_LABEL,
        "validations": [
            {
                "safe": True,
                "endpoint": [float(value) for value in endpoint],
                "residual_inf": 0.0,
                "diagnostic_target": None,
            }
        ],
    }
    environment = os.environ.copy()
    environment.update(THREAD_ENVIRONMENT)
    with tempfile.TemporaryDirectory(prefix="exact-coordinate-fallback-") as name:
        root = Path(name)
        trial_path = root / "trial.json"
        output_path = root / "proposals.json"
        trial_path.write_text(
            json.dumps(trial, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [
                    str(PYTHON),
                    str(REFINER),
                    "--case",
                    str(source.resolve()),
                    "--case-sha256",
                    source_sha256,
                    "--trial",
                    str(trial_path),
                    "--output",
                    str(output_path),
                ],
                cwd=REFINER_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(0.25, timeout_seconds),
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise FallbackFailure("independent coordinate refinement timed out") from error
        if completed.returncode != 0 or not output_path.is_file():
            raise FallbackFailure(
                "independent coordinate refinement failed: "
                + completed.stderr[-400:]
            )
        result = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise FallbackFailure("independent refinement emitted no document")
    return result


def _normalized_descriptor(
    exact: Mapping[str, Any], proposal: Mapping[str, Any]
) -> dict[str, Any]:
    target = exact.get("exact_target_descriptor")
    attestation = exact.get("target_root_attestation")
    if not isinstance(target, Mapping):
        raise FallbackFailure("exact target descriptor is absent")
    polynomial = target.get("coefficients_high_to_low")
    isolator = target.get("isolating_interval")
    root_index = isolator.get("real_root_index") if isinstance(isolator, Mapping) else None
    if (
        exact.get("root_ordinal_attestation_complete") is not True
        or exact.get("root_ordinal_policy")
        != "ZERO_BASED_STRICTLY_INCREASING_REAL_QQBAR_V1"
        or exact.get("root_ordinal_attestation_backend")
        != "NEMO_QQBAR_SORTED_REAL_ROOTS"
        or not isinstance(polynomial, list)
        or len(polynomial) < 2
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in polynomial
        )
        or not _valid_isolator(isolator)
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
        or not isinstance(attestation, Mapping)
        or not isinstance(attestation.get("claimed_real_root_index"), int)
        or isinstance(attestation.get("claimed_real_root_index"), bool)
        or attestation.get("claimed_real_root_index") != root_index
        or not isinstance(attestation.get("attested_real_root_index"), int)
        or isinstance(attestation.get("attested_real_root_index"), bool)
        or attestation.get("attested_real_root_index") != root_index
        or not isinstance(attestation.get("real_root_count"), int)
        or isinstance(attestation.get("real_root_count"), bool)
        or attestation.get("real_root_count") <= root_index
        or not isinstance(attestation.get("multiplicity"), int)
        or isinstance(attestation.get("multiplicity"), bool)
        or attestation.get("multiplicity") != 1
        or attestation.get("interval_unique") is not True
        or attestation.get("index_match") is not True
    ):
        raise FallbackFailure("exact target descriptor is malformed")
    low_to_high = list(reversed(polynomial))
    return {
        "minimal_polynomial_high_to_low": list(polynomial),
        "selected_real_root_index": root_index,
        "isolating_interval": dict(isolator),
        "proposal_relation_low_to_high": low_to_high,
        "confirmation_relation_low_to_high": low_to_high,
        "target_512": proposal.get("answer_512bit_minimum"),
        "target_768": proposal.get("answer_768bit_minimum"),
        "target_1024": proposal.get("answer_1024bit_minimum"),
    }


def run_fallback(
    *,
    source: Path,
    source_sha256: str,
    endpoint: Sequence[float],
    endpoint_sha256: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    base = {
        "schema_version": SCHEMA,
        "completed": True,
        "source_sha256": source_sha256,
        "endpoint_float64_sha256": endpoint_sha256,
        "truth_used": False,
        "case_family_known_target_count_routing": False,
        "source_or_problem_modified": False,
        "bounds_added_or_inferred": False,
        "coordinate_reparameterization": False,
        "target_set_completeness_claim": False,
        "containment": {
            "same_process_group": os.getpgid(0) == os.getpgid(os.getppid()),
            "pdeathsig": _pdeathsig(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
        },
    }
    try:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.5:
            raise FallbackFailure("fallback wall budget is invalid")
        source_payload, document = _source_contract(
            source,
            source_sha256,
            endpoint,
            endpoint_sha256,
        )
        # Leave a fixed two-second tail for bounded recognition, exact replay,
        # and atomic finalization.  The outer formal deadline is stricter.
        refine_seconds = max(0.25, timeout_seconds - 2.0)
        proposals = _run_refiner(
            source,
            source_sha256,
            endpoint,
            timeout_seconds=refine_seconds,
        )
        proposal = _proposal_contract(
            document,
            proposals,
            endpoint,
            source_sha256,
        )
        remaining = timeout_seconds - (time.monotonic() - started) - 0.20
        if remaining <= 0.25:
            raise FallbackFailure("no exact replay budget remains")
        exact = certify_exact_coordinate_witness(
            document,
            proposal["coordinates_768bit_minimum"],
            proposal["coordinates_1024bit_minimum"],
            proposal["answer_768bit_minimum"],
            proposal["answer_1024bit_minimum"],
            timeout_seconds=remaining,
        )
        if (
            exact.get("status") != "EXACT_TARGET_AUTHORITY_READY"
            or exact.get("authority_pass") is not True
            or exact.get("source_raw_answer_exact") is not True
            or exact.get("target_link_exact") is not True
            or exact.get("post_process_used") is not False
            or exact.get("target_set_completeness_claim") is not False
            or exact.get("combined_numeric_and_exact_authority_required")
            is not True
            or exact.get("standalone_operational_v15_parity_claim")
            is not False
        ):
            raise FallbackFailure(
                "exact coordinate source replay rejected: "
                + str(exact.get("failure", exact.get("status")))[:300]
            )
        descriptor = _normalized_descriptor(exact, proposal)
        if source.read_bytes() != source_payload:
            raise FallbackFailure("source bytes changed during fallback")
        result = {
            **base,
            "status": "EXACT_COORDINATE_TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": descriptor,
            "exact_coordinate_authority": exact,
            "independent_coordinate_lanes": [768, 1024],
            "exact_replay_backend": "FLINT_QQBAR_VIA_NEMO",
            "numeric_guard_branch_replay_is_authority": True,
            "numeric_target_nearness_is_authority": False,
            "numeric_float_residual_is_authority": False,
            "numeric_source_replay": {
                "schema_version": (
                    "geotarget.v15-243-frozen-numeric-source-replay/v1"
                ),
                "refiner_sha256": _sha256(REFINER.read_bytes()),
                "source_sha256": source_sha256,
                "proposal_status": proposal.get("status"),
                "float_source_replay": dict(proposal["float_source_replay"]),
                "precision_lanes_decimal_digits": [155, 232, 320],
                "lane_methods": dict(proposal["lane_methods"]),
                "lane_working_decimal_digits": dict(
                    proposal["lane_working_decimal_digits"]
                ),
                "lane_source_replay": {
                    key: dict(value)
                    for key, value in proposal["lane_source_replay"].items()
                },
                "float_endpoint_source_replay_required": True,
                "all_precision_lanes_guard_and_hard_feasible": True,
                "all_precision_lanes_source_residual_reached": True,
                "coordinates_linked_to_exact_roots_by_independent_lanes": (
                    True
                ),
                "branch_and_guard_parity_is_not_inferred_from_qqbar": True,
            },
        }
    except Exception as error:
        result = {
            **base,
            "status": "EXACT_COORDINATE_FALLBACK_REJECTED",
            "authority_pass": False,
            "descriptor": None,
            "failure_type": type(error).__name__,
            "failure": str(error)[:600],
        }
    result["elapsed_wall_seconds"] = time.monotonic() - started
    result["within_fallback_wall_budget"] = (
        result["elapsed_wall_seconds"] <= timeout_seconds
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--endpoint-sha256", required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    try:
        raw_endpoint = json.loads(arguments.endpoint)
        if not isinstance(raw_endpoint, list):
            raise ValueError("endpoint is not an array")
        endpoint = tuple(float(value) for value in raw_endpoint)
        if not all(math.isfinite(value) for value in endpoint):
            raise ValueError("endpoint contains non-finite values")
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid endpoint: {error}") from error
    result = run_fallback(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        endpoint=endpoint,
        endpoint_sha256=arguments.endpoint_sha256,
        timeout_seconds=arguments.timeout_seconds,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=arguments.output.parent,
        delete=False,
    ) as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, arguments.output)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
