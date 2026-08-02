#!/usr/bin/env python3
"""One frozen source-only local-algorithm trial."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Mapping

import numpy as np


PROCESS_STARTED = time.monotonic()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AD_PATH = HERE.parents[1] / "EXP-REAL61-006/analytic_jacobian/candidate.py"
for path in (HERE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from policy import materialize_policy, packet_record  # noqa: E402
from replay import replay_endpoint  # noqa: E402
from runtime import BudgetExceeded, build_source_case  # noqa: E402
from scaling import case_for_start  # noqa: E402
from scaling import frozen_configuration as scaling_configuration  # noqa: E402
from research.infrastructure.memory_safety.safe_subprocess import atomic_write_json  # noqa: E402


def _load_ad():
    name = "geotarget_exp008_forward_ad"
    specification = importlib.util.spec_from_file_location(name, AD_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(AD_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


AD = _load_ad()
ARMS = (AD.ANALYTIC_CPQR, AD.ANALYTIC_LSMR)
SCHEMA = "geotarget.exp-real61-008.source-only-trial/v1"
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class LaneQuota:
    def __init__(self, case: object, budget: object, cap: int) -> None:
        self.evaluate_owner = case.evaluate
        self.progressive_owner = case.progressive_residual
        self.budget = budget
        self.begin = int(budget.callbacks)
        self.cap = int(cap)

    @property
    def used(self) -> int:
        return int(self.budget.callbacks) - self.begin

    def _check(self) -> None:
        if self.used >= self.cap:
            raise BudgetExceeded("per_start_callback_cap")

    def evaluate(self, point: np.ndarray):
        self._check()
        return self.evaluate_owner(np.asarray(point, dtype=float))

    def progressive(self, point: np.ndarray) -> np.ndarray:
        self._check()
        return self.progressive_owner(np.asarray(point, dtype=float))


def _targets(validations: list[Mapping[str, object]]) -> list[str]:
    values: list[tuple[float, str]] = []
    for item in validations:
        raw = item.get("diagnostic_target")
        if item.get("safe") is not True or raw is None:
            continue
        try:
            numeric = float(str(raw))
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(numeric):
            values.append((numeric, str(raw)))
    clusters: list[tuple[float, str]] = []
    for numeric, text in sorted(values):
        if not any(
            math.isclose(numeric, known, rel_tol=1.0e-8, abs_tol=1.0e-8)
            for known, _ in clusters
        ):
            clusters.append((numeric, text))
    return [text for _, text in clusters]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--starts", type=int, required=True)
    parser.add_argument("--callbacks-per-start", type=int, required=True)
    parser.add_argument("--aggregate-callback-cap", type=int)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    affinity = sorted(os.sched_getaffinity(0))
    thread_environment = {name: os.environ.get(name) for name in THREAD_VARIABLES}
    if len(affinity) != 1:
        raise SystemExit("one logical CPU is required")
    if any(value != "1" for value in thread_environment.values()):
        raise SystemExit(f"one-thread environment required: {thread_environment}")
    maximum_cap = arguments.starts * arguments.callbacks_per_start
    callback_cap = (
        maximum_cap
        if arguments.aggregate_callback_cap is None
        else min(maximum_cap, int(arguments.aggregate_callback_cap))
    )
    if (
        arguments.seconds <= 0.0
        or arguments.seconds > 180.0
        or arguments.starts < 1
        or arguments.callbacks_per_start < 2
        or callback_cap < 1
    ):
        raise SystemExit("invalid trial budget")

    source_payload = arguments.case.read_bytes()
    source_sha256 = _sha256(source_payload)
    if source_sha256 != arguments.case_sha256:
        raise SystemExit("source SHA-256 mismatch")
    document = json.loads(source_payload)
    if document.get("task") != "solve":
        raise SystemExit("solve cases only")
    program = AD.compile_program(document)
    hard_deadline = PROCESS_STARTED + arguments.seconds
    replay_reserve = max(0.15, min(1.0, 0.05 * arguments.seconds))
    solve_deadline = max(PROCESS_STARTED, hard_deadline - replay_reserve)
    base_case, budget, evaluator = build_source_case(
        document, callback_cap=callback_cap, deadline=solve_deadline
    )
    policy = materialize_policy(
        document,
        source_sha256=source_sha256,
        starts=arguments.starts,
        seed=arguments.seed,
    )

    endpoints: list[tuple[int, np.ndarray]] = []
    statuses: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    lane_callbacks: list[int] = []
    for lane, start in enumerate(policy.points):
        if time.monotonic() >= solve_deadline or budget.callbacks >= callback_cap:
            statuses["global_stop_before_lane"] += 1
            break
        lane_cap = min(arguments.callbacks_per_start, callback_cap - budget.callbacks)
        local_case = case_for_start(base_case, start)
        quota = LaneQuota(local_case, budget, lane_cap)
        local_case = replace(
            local_case,
            evaluate=quota.evaluate,
            progressive_residual=quota.progressive,
        )
        outcome = AD.solve_local(
            local_case,
            program,
            AD.CONFIGURATIONS[arguments.arm],
            start,
            max_callbacks=lane_cap,
            deadline_monotonic=solve_deadline,
        )
        lane_callbacks.append(quota.used)
        statuses[outcome.status] += 1
        counters.update({str(key): int(value) for key, value in outcome.counters.items()})
        endpoint = np.asarray(outcome.endpoint, dtype=float)
        if endpoint.shape == (base_case.dimension,) and np.all(np.isfinite(endpoint)):
            endpoints.append((lane, endpoint))

    validations: list[Mapping[str, object]] = []
    validation_lanes: list[int] = []
    for lane, endpoint in endpoints:
        if time.monotonic() >= hard_deadline - 0.02:
            break
        validations.append(replay_endpoint(evaluator, endpoint, precision=80))
        validation_lanes.append(lane)
    safe_lanes = [
        lane
        for lane, validation in zip(validation_lanes, validations, strict=True)
        if validation.get("safe") is True
    ]
    targets = _targets(validations)
    elapsed = time.monotonic() - PROCESS_STARTED
    source_unchanged = arguments.case.read_bytes() == source_payload
    result = {
        "schema_version": SCHEMA,
        "completed": True,
        "arm": arguments.arm,
        "source_sha256": source_sha256,
        "source_bytes_unchanged": source_unchanged,
        "source_evaluator_compiled_from_original_document": True,
        "source_semantics_modified": False,
        "explicit_source_bounds_only": True,
        "gauge_or_symmetry_reduction": False,
        "candidate_received_case_id_family_truth_or_target_count": False,
        "seed": arguments.seed,
        "cpu_affinity": affinity,
        "thread_environment": thread_environment,
        "policy_packet": packet_record(policy),
        "scaling": scaling_configuration(),
        "budget": {
            "seconds": arguments.seconds,
            "starts": arguments.starts,
            "callbacks_per_start": arguments.callbacks_per_start,
            "maximum_callback_cap": maximum_cap,
            "aggregate_callback_cap": callback_cap,
            "endpoint_replay_reserve_seconds": replay_reserve,
        },
        "work": {
            "callbacks": int(budget.callbacks),
            "finite_callbacks": int(budget.finite),
            "invalid_callbacks": int(budget.invalid),
            "guard_failed_callbacks": int(budget.guard_failed),
            "best_residual_inf": (
                float(budget.best_norm) if math.isfinite(budget.best_norm) else None
            ),
            "lanes_started": len(lane_callbacks),
            "lane_callbacks_min": min(lane_callbacks, default=0),
            "lane_callbacks_max": max(lane_callbacks, default=0),
        },
        "activation": {
            "status_counts": dict(sorted(statuses.items())),
            "counter_sums": dict(sorted(counters.items())),
        },
        "endpoints": [
            {"lane": lane, "point": endpoint.tolist()} for lane, endpoint in endpoints
        ],
        "endpoints_validated": len(validations),
        "safe_endpoint_count": len(safe_lanes),
        "diagnostic_distinct_target_count": len(targets),
        "diagnostic_targets": targets,
        "diagnostic_targets_are_exact_or_complete": False,
        "truth_used": False,
        "completeness_claim": False,
        "elapsed_wall_seconds": elapsed,
    }
    if not source_unchanged:
        raise RuntimeError("source document changed during the trial")
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
