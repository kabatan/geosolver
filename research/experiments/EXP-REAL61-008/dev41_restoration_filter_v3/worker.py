#!/usr/bin/env python3
"""One truth-blind restoration-filter/control trial on untouched source JSON."""

from __future__ import annotations

import argparse
import hashlib
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
SOURCE_ONLY = HERE.parent / "source_only"
for path in (HERE, SOURCE_ONLY, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapter import (  # noqa: E402
    ARMS,
    BINDING_RECORD,
    build_literal_prefix,
    compile_program,
    configuration_manifest,
    run_local_arm,
)
from policy import materialize_policy, packet_record  # noqa: E402
from replay import replay_endpoint  # noqa: E402
from runtime import build_source_case  # noqa: E402
from research.infrastructure.memory_safety.safe_subprocess import atomic_write_json  # noqa: E402


SCHEMA = "geotarget.exp-real61-008.dev41-restoration-filter-trial-v3/v1"
SOURCE_ONLY_POLICY_DIGEST = (
    "fbf70a530960ffdbcc59f87ede65644ff5eb968dc9e67eb75b47f67384dcd609"
)
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _targets(validations: list[Mapping[str, object]]) -> list[str]:
    values: list[tuple[float, str]] = []
    for validation in validations:
        raw = validation.get("diagnostic_target")
        if validation.get("safe") is not True or raw is None:
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
            math.isclose(numeric, old, rel_tol=1.0e-8, abs_tol=1.0e-8)
            for old, _text in clusters
        ):
            clusters.append((numeric, text))
    return [text for _numeric, text in clusters]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--starts", type=int, required=True)
    parser.add_argument("--callbacks-per-start", type=int, required=True)
    parser.add_argument("--aggregate-callback-cap", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    affinity = sorted(os.sched_getaffinity(0))
    thread_environment = {name: os.environ.get(name) for name in THREAD_VARIABLES}
    if len(affinity) != 1:
        raise SystemExit("one pinned logical CPU is required")
    if any(value != "1" for value in thread_environment.values()):
        raise SystemExit(f"one-thread environment required: {thread_environment}")
    maximum_cap = arguments.starts * arguments.callbacks_per_start
    callback_cap = min(maximum_cap, int(arguments.aggregate_callback_cap))
    if (
        arguments.seconds <= 0.0
        or arguments.seconds > 180.0
        or arguments.starts < 1
        or arguments.callbacks_per_start < 2
        or callback_cap < 1
    ):
        raise SystemExit("invalid trial budget")

    source_payload = arguments.case.read_bytes()
    source_sha256 = hashlib.sha256(source_payload).hexdigest()
    if source_sha256 != arguments.case_sha256:
        raise SystemExit("source digest mismatch")
    document = json.loads(source_payload)
    if document.get("task") != "solve":
        raise SystemExit("solve cases only")

    hard_deadline = PROCESS_STARTED + arguments.seconds
    replay_reserve = max(0.15, min(1.0, 0.05 * arguments.seconds))
    solve_deadline = max(PROCESS_STARTED, hard_deadline - replay_reserve)
    base_case, budget, evaluator = build_source_case(
        document, callback_cap=callback_cap, deadline=solve_deadline
    )
    base_policy = materialize_policy(
        document,
        source_sha256=source_sha256,
        starts=arguments.starts,
        seed=arguments.seed,
    )
    if base_policy.policy_digest != SOURCE_ONLY_POLICY_DIGEST:
        raise RuntimeError("source-only policy digest changed")
    literal_prefix = build_literal_prefix(document, base_case, base_policy)

    if base_case.dimension == 0:
        endpoint = np.empty(0, dtype=float)
        base_case.evaluate(endpoint)
        endpoints = ((0, endpoint),)
        statuses = {"dimension_zero_direct_replay": 1}
        counters = {"unique_configuration_evaluated": 1}
        lane_callbacks = (int(budget.callbacks),)
    else:
        program = compile_program(arguments.arm, document)
        outcome = run_local_arm(
            arguments.arm,
            base_case=base_case,
            budget=budget,
            program=program,
            literal_prefix=literal_prefix,
            callback_cap=callback_cap,
            callbacks_per_start=arguments.callbacks_per_start,
            deadline_monotonic=solve_deadline,
        )
        endpoints = outcome.endpoints
        statuses = outcome.statuses
        counters = outcome.counters
        lane_callbacks = outcome.lane_callbacks

    validations: list[Mapping[str, object]] = []
    validated_endpoints: list[tuple[int, np.ndarray]] = []
    for lane, endpoint in endpoints:
        if time.monotonic() >= hard_deadline - 0.02:
            break
        validations.append(replay_endpoint(evaluator, endpoint, precision=80))
        validated_endpoints.append((lane, np.asarray(endpoint, dtype=float).copy()))
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
        "all_source_variables_and_equations_retained": True,
        "explicit_source_bounds_only": True,
        "added_or_inferred_search_bounds": False,
        "gauge_or_symmetry_reduction": False,
        "candidate_received_case_id_family_truth_or_target_count": False,
        "truth_used": False,
        "completeness_claim": False,
        "seed": arguments.seed,
        "cpu_affinity": affinity,
        "thread_environment": thread_environment,
        "binding_record": BINDING_RECORD,
        "configuration": configuration_manifest(),
        "base_policy_packet": packet_record(base_policy),
        "literal_prefix": {
            "sha256": literal_prefix.sha256,
            "sources": list(literal_prefix.sources),
            "scale_exponents": list(literal_prefix.scale_exponents),
            "activation": literal_prefix.activation,
        },
        "budget": {
            "seconds": arguments.seconds,
            "starts": arguments.starts,
            "callbacks_per_start": arguments.callbacks_per_start,
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
            {"lane": lane, "point": endpoint.tolist()}
            for lane, endpoint in validated_endpoints
        ],
        "endpoints_validated": len(validations),
        "safe_endpoint_count": sum(
            validation.get("safe") is True for validation in validations
        ),
        "diagnostic_distinct_target_count": len(targets),
        "diagnostic_targets": targets,
        "diagnostic_targets_are_exact_or_complete": False,
        "elapsed_wall_seconds": elapsed,
    }
    if not source_unchanged:
        raise RuntimeError("source bytes changed during restoration-filter trial")
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
