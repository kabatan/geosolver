#!/usr/bin/env python3
"""Run one byte-preserved public endpoint through one escalation arm."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BRIDGE_PATH = ROOT / "research/experiments/EXP-REAL61-004/refinement_bridge/worker.py"
for path in (HERE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import candidate  # noqa: E402
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _endpoint_sha(endpoint: tuple[float, ...]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", value) for value in endpoint
    )
    return hashlib.sha256(payload).hexdigest()


class CountingEvaluator:
    def __init__(self, raw):
        self.raw = raw
        self.counts = {
            "float_residual": 0,
            "hp_residual": 0,
            "float_hard": 0,
            "hp_hard": 0,
            "guard": 0,
            "hp_answer": 0,
        }

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def evaluate_float_residual(self, point):
        self.counts["float_residual"] += 1
        return self.raw.evaluate_float_residual(point)

    def evaluate_hp_residual(self, point, *, precision):
        self.counts["hp_residual"] += 1
        return self.raw.evaluate_hp_residual(point, precision=precision)

    def evaluate_float_hard_feasibility(self, point):
        self.counts["float_hard"] += 1
        return self.raw.evaluate_float_hard_feasibility(point)

    def evaluate_hp_hard_feasibility(self, point, *, precision):
        self.counts["hp_hard"] += 1
        return self.raw.evaluate_hp_hard_feasibility(point, precision=precision)

    def evaluate_guard(self, point):
        self.counts["guard"] += 1
        return self.raw.evaluate_guard(point)

    def evaluate_answer_hp(self, point, *, precision):
        self.counts["hp_answer"] += 1
        return self.raw.evaluate_answer_hp(point, precision=precision)


class OpaqueAdapter:
    def __init__(self, raw, high_precision_mode):
        self.raw = raw
        self.high_precision_mode = high_precision_mode
        self.cached_key = None
        self.cached_observation = None
        self.cache_hits = 0
        self.cache_misses = 0

    @staticmethod
    def _key(point, dps):
        with mp.workdps(int(dps)):
            return int(dps), tuple(mp.mpf(value)._mpf_ for value in point)

    def residual(self, point, dps):
        key = self._key(point, dps)
        if key == self.cached_key and self.cached_observation is not None:
            observation = self.cached_observation
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            with self.high_precision_mode():
                observation = self.raw.evaluate_hp_residual(
                    list(point), precision=int(dps)
                )
        self.cached_key = None
        self.cached_observation = None
        if not observation.is_finite:
            raise ArithmeticError("nonfinite residual")
        return tuple(observation.residual_vector)

    def semantic(self, point, dps):
        self.cached_key = None
        self.cached_observation = None
        with self.high_precision_mode():
            hard = self.raw.evaluate_hp_hard_feasibility(
                list(point), precision=int(dps)
            )
            guard_ok, violations = self.raw.evaluate_guard(list(point))
            observation = self.raw.evaluate_hp_residual(
                list(point), precision=int(dps)
            )
        self.cached_key = self._key(point, dps)
        self.cached_observation = observation
        return candidate.BASE.BASE.SemanticState(
            bool(hard.hard_feasible and guard_ok and observation.is_finite),
            getattr(hard, "min_margin", None),
            f"hard={hard.hard_feasible};guard={guard_ok};violations={violations}",
        )

    def answer(self, point, dps):
        self.cached_key = None
        self.cached_observation = None
        with self.high_precision_mode():
            answer = self.raw.evaluate_answer_hp(list(point), precision=int(dps))
        if answer.answer_hp is None:
            raise ArithmeticError("answer unavailable")
        return answer.answer_hp


def _original_replay(raw, lane_points, high_precision_mode):
    if len(lane_points) != 3:
        return {"numeric_v3_ready": False, "status": "LANE_COUNT_FAILED"}
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
                    "answer": answer.answer_hp,
                }
            )
    with mp.workdps(350):
        coordinate_disagreement = max(
            (
                abs(left - right)
                for left, right in zip(
                    replay[0]["point"], replay[1]["point"], strict=True
                )
            ),
            default=mp.mpf("0"),
        )
        target_512_768 = abs(replay[0]["answer"] - replay[1]["answer"])
        target_768_1024 = abs(replay[1]["answer"] - replay[2]["answer"])
    ready = bool(
        all(
            row["finite"] and row["hard_feasible"] and row["guard_ok"]
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


def _endpoint(document, selector: str):
    if selector == "near":
        row = document["near_root"]["selected"]
    elif selector.startswith("safe:"):
        row = document["safe_endpoints"][int(selector.split(":", 1)[1])]
    elif selector.startswith("index:"):
        row = document["endpoints"][int(selector.split(":", 1)[1])]
    else:
        raise ValueError("selector must be near, safe:N, or index:N")
    if row is None:
        raise ValueError("selected endpoint is absent")
    endpoint = tuple(float(value) for value in row["endpoint"])
    digest = row.get("endpoint_float64_sha256", _endpoint_sha(endpoint))
    if _endpoint_sha(endpoint) != digest:
        raise ValueError("endpoint digest mismatch")
    return endpoint, digest, row


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "_mpf_"):
        return mp.nstr(value, 150)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--endpoints", type=Path, required=True)
    parser.add_argument("--endpoints-sha256", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--arm", choices=candidate.VARIANTS, required=True)
    parser.add_argument("--deadline-seconds", type=float, default=24.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.monotonic()
    if _sha(arguments.case) != arguments.case_sha256:
        raise SystemExit("case digest mismatch")
    if _sha(arguments.endpoints) != arguments.endpoints_sha256:
        raise SystemExit("endpoint artifact digest mismatch")
    endpoint_document = json.loads(arguments.endpoints.read_text(encoding="utf-8"))
    endpoint, endpoint_digest, endpoint_row = _endpoint(
        endpoint_document, arguments.selector
    )
    source = json.loads(arguments.case.read_text(encoding="utf-8"))
    bridge = _load("geotarget_exp006_adaptive_hp_bridge", BRIDGE_PATH)
    components = bridge._load_components()
    bundle = components["load_problem_bundle"](source, prefer_fast=False)
    raw = CountingEvaluator(components["build_ir_evaluator"](bundle))
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
        "schema_version": "geotarget.exp006-adaptive-hp-escalation/v1",
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
        result["status"] = "FLOAT64_SEMANTIC_REJECTED"
        result["numeric_v3_ready"] = False
    else:
        adapter = OpaqueAdapter(raw, high_precision_mode)
        refined = candidate.refine_endpoint(
            adapter,
            endpoint,
            variant=arguments.arm,
            deadline_seconds=arguments.deadline_seconds,
        )
        result["candidate"] = refined
        lane_points = [
            row["point"]
            for row in refined["lanes"]
            if row.get("status") == "SUCCESS" and row.get("point") is not None
        ]
        result["semantic_residual_cache"] = {
            "hits": adapter.cache_hits,
            "misses": adapter.cache_misses,
        }
    replay = _original_replay(raw, lane_points, high_precision_mode)
    result["original_numerical_replay"] = replay
    result["numeric_v3_ready"] = bool(replay["numeric_v3_ready"])
    result["status"] = replay["status"]
    result["callback_counts"] = raw.counts
    result["elapsed_seconds"] = time.monotonic() - started
    atomic_write_json(arguments.output, _jsonable(result))


if __name__ == "__main__":
    main()
