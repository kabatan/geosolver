"""Bridge one finalist case into independent refinement and owned PSLQ proposals."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any, Callable

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = HERE.parents[1] / "EXP-REAL61-001"
OWNED = HERE.parents[1] / "EXP-REAL61-003" / "owned_pslq"
for path in (HERE, ROOT, BASELINE, OWNED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bridge import canonical_sha256, collect_seed_records  # noqa: E402
from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    atomic_write_json,
)


SCHEMA = "geotarget.real61-refinement-bridge-case/v1"
LANES = ((155, "512"), (232, "768"), (320, "1024"))
PHASES = (
    "input_ingest",
    "component_load",
    "runtime_build",
    "canonical_float_replay",
    "independent_lane_512",
    "independent_lane_768",
    "independent_lane_1024",
    "owned_pslq",
    "result_build",
)
THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_module(name: str, path: Path):
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load component module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_components() -> dict[str, Any]:
    legacy = _load_module(
        "real61_refinement_bridge_legacy_worker",
        BASELINE / "refine_proposals_worker.py",
    )
    (
        load_problem_bundle,
        build_ir_evaluator,
        float_candidate_class,
        evaluation_status,
        refiner_class,
        target_reached,
        config_class,
    ) = legacy._install_legacy_imports()
    return {
        "load_problem_bundle": load_problem_bundle,
        "build_ir_evaluator": build_ir_evaluator,
        "float_candidate_class": float_candidate_class,
        "evaluation_status": evaluation_status,
        "refiner_class": refiner_class,
        "target_reached": target_reached,
        "config_class": config_class,
        "lane": legacy._lane,
        "mp_text": legacy._mp_text,
    }


def _load_owned_processor() -> Callable[..., dict[str, Any]]:
    adapter = _load_module(
        "real61_refinement_bridge_owned_pslq_batch",
        OWNED / "batch_adapter.py",
    )
    return adapter.process_source


def _validate_owned_result(
    document: object,
    *,
    case_id: str,
    case_sha256: str,
    source_artifact_sha256: str,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("owned PSLQ result is not an object")
    required = {
        "schema_version": "geotarget.target-only-owned-pslq-case/v1",
        "authority": False,
        "truth_status": "NOT_MATERIALIZED",
        "accuracy_claims_permitted": False,
        "completeness_claims_permitted": False,
        "case_id": case_id,
        "case_sha256": case_sha256,
        "source_artifact_sha256": source_artifact_sha256,
        "original_dsl_exact_replay": "NOT_RUN",
        "target_image_completeness": "NOT_RUN",
    }
    mismatches = {
        key: {"expected": expected, "observed": document.get(key)}
        for key, expected in required.items()
        if document.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"owned PSLQ result violates bridge contract: {mismatches}")
    return document


def _component_sources() -> list[dict[str, str]]:
    paths = (
        BASELINE / "refine_proposals_worker.py",
        OWNED / "owned_pslq.py",
        OWNED / "batch_adapter.py",
        HERE / "bridge.py",
        Path(__file__).resolve(),
    )
    return [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256(path.read_bytes()),
        }
        for path in paths
    ]


def _elapsed(started: float) -> float:
    return max(0.0, time.monotonic() - started)


def _refine_seed(
    seed: dict[str, object],
    *,
    candidate_id: int,
    bundle,
    evaluator,
    components: dict[str, Any],
    aggregate_timing: dict[str, float],
) -> dict[str, object]:
    endpoint = tuple(float(value) for value in seed["endpoint"])
    timing = {
        "canonical_float_replay": 0.0,
        "independent_lane_512": 0.0,
        "independent_lane_768": 0.0,
        "independent_lane_1024": 0.0,
    }
    started = time.monotonic()
    observation = evaluator.evaluate_float_residual(endpoint)
    guard_ok, guard_violations = evaluator.evaluate_guard(endpoint)
    hard = evaluator.evaluate_float_hard_feasibility(endpoint)
    timing["canonical_float_replay"] = _elapsed(started)
    aggregate_timing["canonical_float_replay"] += timing[
        "canonical_float_replay"
    ]
    valid = bool(
        observation.evaluation_status is components["evaluation_status"].OK
        and guard_ok
        and hard.hard_feasible
        and math.isfinite(float(observation.residual_norm_float))
    )
    source = {
        **seed,
        "canonical_float_replay": {
            "finite": bool(
                observation.evaluation_status is components["evaluation_status"].OK
            ),
            "guard_ok": bool(guard_ok),
            "guard_violations": list(guard_violations),
            "hard_feasible": bool(hard.hard_feasible),
            "hard_failure_tags": list(hard.failure_tags),
            "residual_inf": (
                float(observation.residual_norm_float)
                if math.isfinite(float(observation.residual_norm_float))
                else None
            ),
        },
    }
    if not valid:
        return {
            "source": source,
            "status": "CANONICAL_FLOAT_REPLAY_REJECTED",
            "independent_precision_lanes": False,
            "phase_timing_seconds": timing,
            "original_dsl_exact_replay": "NOT_RUN",
            "exact_descriptor_authority": False,
        }

    bindings = seed["source_bindings"]
    origin_seed = min(int(binding["seed"]) for binding in bindings)
    lane_start = {
        "kind": "same_canonical_float64_endpoint",
        "endpoint_float64_sha256": seed["endpoint_float64_sha256"],
        "lane_decimal_digits": [155, 232, 320],
        "lane_bit_minimums": [512, 768, 1024],
    }
    float_candidate = components["float_candidate_class"](
        x_float=endpoint,
        score=0.5 * float(observation.residual_norm_float) ** 2,
        residual_norm_float=float(observation.residual_norm_float),
        guard_ok=True,
        evaluation_status=observation.evaluation_status,
        origin_seed=origin_seed,
        origin_start_point_index=candidate_id,
        candidate_id=candidate_id,
        hard_feasible=True,
        hard_violation_tags=tuple(hard.failure_tags),
        validity_margin_float=(
            None if hard.min_margin is None else float(hard.min_margin)
        ),
    )
    lanes: dict[int, object | None] = {}
    for dps, bits in LANES:
        phase = f"independent_lane_{bits}"
        lane_started = time.monotonic()
        lanes[dps] = components["lane"](
            dps=dps,
            bundle=bundle,
            evaluator=evaluator,
            float_candidate=float_candidate,
            config_class=components["config_class"],
            refiner_class=components["refiner_class"],
            target_reached=components["target_reached"],
        )
        timing[phase] = _elapsed(lane_started)
        aggregate_timing[phase] += timing[phase]
    successful = [dps for dps, lane in lanes.items() if lane is not None]
    if len(successful) != len(lanes):
        return {
            "source": source,
            "status": "REFINEMENT_INCOMPLETE",
            "successful_lanes_dps": successful,
            "independent_precision_lanes": True,
            "independent_lane_start": lane_start,
            "phase_timing_seconds": timing,
            "original_dsl_exact_replay": "NOT_RUN",
            "exact_descriptor_authority": False,
        }

    lane512, lane768, lane1024 = lanes[155], lanes[232], lanes[320]
    with mp.workdps(320):
        answer_disagreement = abs(lane512.answer_hp - lane768.answer_hp)
        coordinate_disagreement = max(
            (
                abs(left - right)
                for left, right in zip(
                    lane512.x_hp,
                    lane768.x_hp,
                    strict=True,
                )
            ),
            default=mp.mpf("0"),
        )
    numeric_gate = bool(answer_disagreement <= mp.mpf("1e-100"))
    return {
        "source": source,
        "status": (
            "INDEPENDENT_REFINEMENT_READY"
            if numeric_gate
            else "NUMERIC_AGREEMENT_GATE_FAILED"
        ),
        "independent_precision_lanes": True,
        "independent_lane_start": lane_start,
        "lane_methods": {
            str(dps): getattr(lane, "method", "legacy_staged_mpmath_lm")
            for dps, lane in lanes.items()
        },
        "lane_working_decimal_digits": {
            str(dps): int(getattr(lane, "working_dps", dps) or dps)
            for dps, lane in lanes.items()
        },
        "answer_512bit_minimum": components["mp_text"](lane512.answer_hp, 155),
        "answer_768bit_minimum": components["mp_text"](lane768.answer_hp, 232),
        "answer_1024bit_minimum": components["mp_text"](lane1024.answer_hp, 320),
        "coordinates_768bit_minimum": [
            components["mp_text"](value, 232) for value in lane768.x_hp
        ],
        "coordinates_1024bit_minimum": [
            components["mp_text"](value, 320) for value in lane1024.x_hp
        ],
        "answer_512_768_disagreement": components["mp_text"](
            answer_disagreement, 120
        ),
        "coordinate_512_768_disagreement_inf": components["mp_text"](
            coordinate_disagreement, 120
        ),
        "numeric_gate_1e_100": numeric_gate,
        "phase_timing_seconds": timing,
        "original_dsl_exact_replay": "NOT_RUN",
        "target_image_completeness": "NOT_RUN",
        "exact_descriptor_authority": False,
    }


def build_bridge_result(
    case_path: Path,
    expected_case_sha256: str,
    trial_paths: list[Path],
    *,
    components: dict[str, Any] | None = None,
    owned_processor: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, object]:
    total_started = time.monotonic()
    timing = {phase: 0.0 for phase in PHASES}
    ingest_started = time.monotonic()
    payload = case_path.read_bytes()
    actual_case_sha256 = _sha256(payload)
    if actual_case_sha256 != expected_case_sha256:
        raise ValueError("case source hash mismatch")
    document = json.loads(payload)
    if document.get("task") != "solve":
        raise ValueError("refinement bridge accepts solve cases only")
    case_id = case_path.stem
    if not isinstance(document.get("id"), str) or not document["id"]:
        raise ValueError("case source lacks its internal identifier")
    names = document.get("variables", {}).get("names")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("source variable declaration is malformed")
    seeds, seed_summary = collect_seed_records(
        trial_paths,
        expected_case_id=case_id,
        expected_case_sha256=actual_case_sha256,
        expected_dimension=len(names),
    )
    timing["input_ingest"] = _elapsed(ingest_started)

    if components is None or owned_processor is None:
        component_started = time.monotonic()
        if components is None:
            components = _load_components()
        if owned_processor is None:
            owned_processor = _load_owned_processor()
        timing["component_load"] = _elapsed(component_started)

    runtime_started = time.monotonic()
    bundle = components["load_problem_bundle"](document, prefer_fast=False)
    evaluator = components["build_ir_evaluator"](bundle)
    timing["runtime_build"] = _elapsed(runtime_started)

    proposals = [
        _refine_seed(
            seed,
            candidate_id=index,
            bundle=bundle,
            evaluator=evaluator,
            components=components,
            aggregate_timing=timing,
        )
        for index, seed in enumerate(seeds)
    ]
    refinement = {
        "schema_version": "geotarget.real61-refined-proposals/v1",
        "authority": "DEVELOPMENT_PROPOSALS_ONLY",
        "truth_status": "NOT_MATERIALIZED",
        "accuracy_claims_permitted": False,
        "completeness_claims_permitted": False,
        "case_id": case_id,
        "case_sha256": actual_case_sha256,
        "input_seed_count": len(seeds),
        "seed_collection": seed_summary,
        "proposals": proposals,
        "phase_timing_seconds": dict(timing),
        "original_dsl_exact_replay": "NOT_RUN",
        "target_image_completeness": "NOT_RUN",
    }
    refinement_payload = json.dumps(
        refinement,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    pslq_started = time.monotonic()
    refinement_payload_sha256 = _sha256(refinement_payload)
    owned_pslq = _validate_owned_result(
        owned_processor(
            refinement_payload,
            source_path=f"embedded-refinement:{case_id}",
        ),
        case_id=case_id,
        case_sha256=actual_case_sha256,
        source_artifact_sha256=refinement_payload_sha256,
    )
    timing["owned_pslq"] = _elapsed(pslq_started)
    result_started = time.monotonic()
    result = {
        "schema_version": SCHEMA,
        "completed": True,
        "authority": False,
        "authority_label": "DEVELOPMENT_PROPOSAL_ONLY",
        "truth_status": "NOT_MATERIALIZED",
        "accuracy_claims_permitted": False,
        "completeness_claims_permitted": False,
        "case_id": case_id,
        "case_sha256": actual_case_sha256,
        "source_policy_seed_bindings_preserved": True,
        "seed_collection": seed_summary,
        "refinement_payload_sha256": refinement_payload_sha256,
        "refinement": refinement,
        "owned_pslq": owned_pslq,
        "component_sources": _component_sources(),
        "phase_timing_seconds": timing,
        "original_dsl_exact_replay": "NOT_RUN",
        "exact_replay_disposition": "DEFERRED_TO_CAPABILITY_LANES",
        "target_image_completeness": "NOT_RUN",
        "thread_environment": {
            name: os.environ.get(name) for name in (*THREAD_ENVIRONMENT, "PYTHONHASHSEED")
        },
    }
    timing["result_build"] = _elapsed(result_started)
    result["elapsed_before_atomic_write_seconds"] = _elapsed(total_started)
    result["peak_process_rss_bytes_before_atomic_write"] = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    )
    result["phase_timing_inventory_sha256"] = canonical_sha256(timing)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--trial", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 1:
        raise SystemExit(f"worker requires exactly one logical CPU, received {affinity}")
    wrong_threads = {
        name: os.environ.get(name)
        for name in THREAD_ENVIRONMENT
        if os.environ.get(name) != "1"
    }
    if wrong_threads:
        raise SystemExit(f"worker requires one-thread environment: {wrong_threads}")
    result = build_bridge_result(
        arguments.case,
        arguments.case_sha256,
        arguments.trial,
    )
    result["cpu_affinity"] = affinity
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
