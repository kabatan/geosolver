#!/usr/bin/env python3
"""Run one endpoint through target-stability HP and actual target authority."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
COMMON_WORKER_PATH = HERE / "worker.py"
BRIDGE_PATH = ROOT / "research/experiments/EXP-REAL61-004/refinement_bridge/worker.py"
AUTHORITY_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-004/target_only_numerical_authority_v3/adapter.py"
)
for path in (HERE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import target_stable_candidate as candidate  # noqa: E402
from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    atomic_write_json,
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


COMMON = _load("geotarget_exp006_target_stable_common_worker", COMMON_WORKER_PATH)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _numeric_text(value, dps: int) -> str:
    with mp.workdps(int(dps)):
        return mp.nstr(
            mp.mpf(value),
            n=max(120, int(dps) - 8),
            strip_zeros=False,
        )


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "_mpf_"):
        return mp.nstr(value, 340, strip_zeros=False)
    return value


def _original_replay(raw, lane_points, high_precision_mode):
    if len(lane_points) != 3:
        return {
            "numeric_v3_ready": False,
            "status": "LANE_COUNT_FAILED",
            "lanes": [],
        }
    replay = []
    for bits, dps, raw_point in zip(
        (512, 768, 1024), (180, 252, 340), lane_points, strict=True
    ):
        with mp.workdps(dps), high_precision_mode():
            point = [mp.mpf(value) for value in raw_point]
            observation = raw.evaluate_hp_residual(point, precision=dps)
            hard = raw.evaluate_hp_hard_feasibility(point, precision=dps)
            guard_ok, violations = raw.evaluate_guard(point)
            answer = raw.evaluate_answer_hp(point, precision=dps)
            replay.append(
                {
                    "bits": bits,
                    "dps": dps,
                    "point": point,
                    "residual_inf": (
                        mp.mpf(observation.residual_norm_hp)
                        if observation.is_finite
                        else mp.inf
                    ),
                    "finite": bool(observation.is_finite),
                    "hard_feasible": bool(hard.hard_feasible),
                    "guard_ok": bool(guard_ok),
                    "guard_violations": list(violations),
                    "answer": (
                        None
                        if answer.answer_hp is None
                        else _numeric_text(answer.answer_hp, dps)
                    ),
                }
            )
    with mp.workdps(370):
        coordinate_disagreement = max(
            (
                abs(mp.mpf(left) - mp.mpf(right))
                for left, right in zip(
                    replay[0]["point"], replay[1]["point"], strict=True
                )
            ),
            default=mp.mpf("0"),
        )
        target_512_768 = abs(
            mp.mpf(replay[0]["answer"]) - mp.mpf(replay[1]["answer"])
        )
        target_768_1024 = abs(
            mp.mpf(replay[1]["answer"]) - mp.mpf(replay[2]["answer"])
        )
    ready = bool(
        all(
            row["finite"]
            and row["hard_feasible"]
            and row["guard_ok"]
            and row["answer"] is not None
            for row in replay
        )
        and all(row["residual_inf"] <= mp.mpf("1e-100") for row in replay[:2])
        and coordinate_disagreement <= mp.mpf("1e-100")
        and target_512_768 <= mp.mpf("1e-100")
        and target_768_1024 <= mp.mpf("1e-100")
    )
    return {
        "numeric_v3_ready": ready,
        "status": "NUMERIC_V3_READY" if ready else "NUMERIC_V3_GATE_FAILED",
        "configuration_512_768_disagreement_inf": coordinate_disagreement,
        "target_512_768_disagreement": target_512_768,
        "target_768_1024_disagreement": target_768_1024,
        "lanes": replay,
    }


def _target_authority(source, replay):
    if not replay.get("numeric_v3_ready"):
        return {
            "status": "NUMERIC_V3_GATE_FAILED",
            "target_relation_confirmed": False,
        }
    authority = _load(
        "geotarget_exp006_target_stable_authority",
        AUTHORITY_PATH,
    )
    lanes = replay["lanes"]
    try:
        evidence = authority._owned_target_relation(
            lanes[1]["answer"],
            lanes[2]["answer"],
            target_512=lanes[0]["answer"],
            source=source,
        )
    except authority.NumericalAuthorityError as error:
        return {
            "status": error.failure_class,
            "detail": str(error),
            "target_relation_confirmed": False,
        }
    return {
        **evidence,
        "target_relation_confirmed": bool(
            evidence.get("status") == "TARGET_RELATION_CONFIRMED"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--endpoints", type=Path, required=True)
    parser.add_argument("--endpoints-sha256", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--arm", choices=candidate.VARIANTS, required=True)
    parser.add_argument("--deadline-seconds", type=float, default=23.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.monotonic()
    if _sha(arguments.case) != arguments.case_sha256:
        raise SystemExit("case digest mismatch")
    if _sha(arguments.endpoints) != arguments.endpoints_sha256:
        raise SystemExit("endpoint artifact digest mismatch")

    endpoint_document = json.loads(arguments.endpoints.read_text(encoding="utf-8"))
    endpoint, endpoint_digest, endpoint_row = COMMON._endpoint(
        endpoint_document, arguments.selector
    )
    source = json.loads(arguments.case.read_text(encoding="utf-8"))
    bridge = _load("geotarget_exp006_target_stable_bridge", BRIDGE_PATH)
    components = bridge._load_components()
    bundle = components["load_problem_bundle"](source, prefer_fast=False)
    raw = COMMON.CountingEvaluator(components["build_ir_evaluator"](bundle))
    from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    observation = raw.evaluate_float_residual(endpoint)
    hard = raw.evaluate_float_hard_feasibility(endpoint)
    guard_ok, violations = raw.evaluate_guard(endpoint)
    float_valid = bool(
        observation.evaluation_status is components["evaluation_status"].OK
        and hard.hard_feasible
        and guard_ok
        and math.isfinite(float(observation.residual_norm_float))
    )
    result = {
        "schema_version": "geotarget.exp006-target-stable-authority/v1",
        "case_id": arguments.case.stem,
        "source_sha256": arguments.case_sha256,
        "endpoint_selector": arguments.selector,
        "endpoint_float64_sha256": endpoint_digest,
        "endpoint_role": endpoint_row.get("role"),
        "arm": arguments.arm,
        "float64_replay": {
            "semantic_valid": float_valid,
            "residual_inf": (
                float(observation.residual_norm_float)
                if math.isfinite(float(observation.residual_norm_float))
                else None
            ),
            "hard_feasible": bool(hard.hard_feasible),
            "guard_ok": bool(guard_ok),
            "guard_violations": list(violations),
        },
        "truth_read": False,
        "known_target_count_read": False,
        "source_mutated": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
    }
    lane_points = []
    if not float_valid:
        refined = {
            "status": "FLOAT64_SEMANTIC_REJECTED",
            "numeric_v3_ready": False,
            "lanes": [],
        }
    else:
        adapter = COMMON.OpaqueAdapter(raw, high_precision_mode)
        refined = candidate.refine_endpoint(
            adapter,
            endpoint,
            variant=arguments.arm,
            deadline_seconds=arguments.deadline_seconds,
        )
        lane_points = [
            row["point"]
            for row in refined.get("lanes", [])
            if row.get("point") is not None
            and row.get("status") in {"SUCCESS", "TARGET_STABILITY_REACHED"}
        ]
        result["semantic_residual_cache"] = {
            "hits": adapter.cache_hits,
            "misses": adapter.cache_misses,
        }
    result["candidate"] = refined
    replay = _original_replay(raw, lane_points, high_precision_mode)
    authority = _target_authority(source, replay)
    result["original_numerical_replay"] = replay
    result["target_authority"] = authority
    result["numeric_v3_ready"] = bool(replay["numeric_v3_ready"])
    result["target_relation_confirmed"] = bool(
        authority.get("target_relation_confirmed")
    )
    result["status"] = (
        "TARGET_AUTHORITY_READY"
        if result["target_relation_confirmed"]
        else authority.get("status", replay["status"])
    )
    result["callback_counts"] = raw.counts
    result["elapsed_seconds"] = time.monotonic() - started
    atomic_write_json(arguments.output, _jsonable(result))


if __name__ == "__main__":
    main()
