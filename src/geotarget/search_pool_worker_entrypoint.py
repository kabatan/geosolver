"""Persistent, pinned worker for independent champion search starts.

The frozen proposal generator, evaluator, optimizer program, callback quota,
deadline and endpoint replay are reused unchanged.  This product-owned process
only keeps those immutable objects warm while claiming global start ordinals
from a shared FIFO and atomically journaling each completed start.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import struct
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

PACKAGE_SOURCE = Path(__file__).resolve().parents[1]
if str(PACKAGE_SOURCE) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SOURCE))

from geotarget.callback_snapshot import compile_callback_snapshot  # noqa: E402
from geotarget.compiled_evaluator import (  # noqa: E402
    CompiledResidualEvaluator,
    compile_residual_plan,
    precompute_constant_constructions,
)
from geotarget.fused_evaluation import (  # noqa: E402
    install_compiled_callback_snapshot,
    install_fused_evaluation,
)

SEARCH_ARM = "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm"


def _load(path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(
        "geotarget_optimized_frozen_search_pool", path
    )
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _point_digest(points: tuple[Any, ...]) -> str:
    digest = hashlib.sha256(b"geotarget.optimized-search-shard/v1\0")
    for point in points:
        values = tuple(float(value) for value in point)
        digest.update(struct.pack("<Q", len(values)))
        digest.update(struct.pack(f"<{len(values)}d", *values))
    return digest.hexdigest()


def _activate_compiled_evaluator(
    reference_evaluator: Any,
    budget: Any,
    *,
    source_sha256: str,
) -> tuple[Any, dict[str, Any]]:
    """Select the qualified kernel or preserve exact reference identity.

    Unsupported programs must not receive a partial wrapper: even a
    semantics-preserving-looking facade changes callback cost and therefore
    how much of the fixed champion work prefix fits inside its wall budget.
    """

    fused_metadata = install_fused_evaluation(budget)
    metadata: dict[str, Any] = {
        "schema_version": "geotarget.compiled-residual-plan/v1",
        "enabled": False,
        "case_specific_routing": False,
        "fused_evaluation": fused_metadata,
    }
    compilation = compile_residual_plan(
        reference_evaluator,
        source_sha256=source_sha256,
    )
    if compilation.plan is None:
        return reference_evaluator, {
            **metadata,
            "fallback_reason": compilation.fallback_reason,
            "qualification_mode": "shadow_opt_in",
            "whole_problem_reference_identity": True,
            "whole_problem_reference_semantics_fused": True,
            "constant_constructions": [],
        }
    constant_result = precompute_constant_constructions(reference_evaluator)
    evaluator = CompiledResidualEvaluator(reference_evaluator, compilation.plan)
    callback_snapshot = compile_callback_snapshot(evaluator)
    evaluator.compiled_callback_snapshot = callback_snapshot
    budget.evaluator = evaluator
    snapshot_dispatch = (
        install_compiled_callback_snapshot(budget, callback_snapshot)
        if callback_snapshot is not None
        else None
    )
    return evaluator, {
        **compilation.plan.metadata(),
        "enabled": True,
        "qualification_mode": "shadow_opt_in",
        "case_specific_routing": False,
        "fused_evaluation": fused_metadata,
        "constant_constructions": list(constant_result.precomputed_names),
        "constant_dependency_sha256": constant_result.dependency_sha256,
        "compiled_callback_snapshot": (
            {**callback_snapshot.metadata(), "dispatch": snapshot_dispatch}
            if callback_snapshot is not None
            else {
                "enabled": False,
                "fallback_scope": "whole_callback",
                "case_specific_routing": False,
            }
        ),
    }


def _claim(queue_path: Path, ordinal_end: int, worker_id: int) -> int | None:
    with queue_path.open("r+", encoding="ascii") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        state = json.loads(stream.read())
        leased = {str(key): int(value) for key, value in state.get("leased", {}).items()}
        worker_key = str(worker_id)
        existing = leased.get(worker_key)
        if existing is not None:
            return existing
        retries = sorted({int(value) for value in state.get("retry", ())})
        if retries:
            ordinal = retries.pop(0)
        else:
            ordinal = int(state["next"])
            if ordinal >= ordinal_end:
                return None
            state["next"] = ordinal + 1
        leased[worker_key] = ordinal
        state["retry"] = retries
        state["leased"] = leased
        stream.seek(0)
        stream.truncate()
        stream.write(json.dumps(state, separators=(",", ":")))
        stream.flush()
        os.fsync(stream.fileno())
        return ordinal


def _release(queue_path: Path, worker_id: int, ordinal: int) -> None:
    with queue_path.open("r+", encoding="ascii") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        state = json.loads(stream.read())
        leased = {str(key): int(value) for key, value in state.get("leased", {}).items()}
        worker_key = str(worker_id)
        if leased.get(worker_key) != ordinal:
            raise RuntimeError("search work lease changed before commit")
        leased.pop(worker_key)
        state["leased"] = leased
        stream.seek(0)
        stream.truncate()
        stream.write(json.dumps(state, separators=(",", ":")))
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _replay_action(artifact: dict[str, Any]) -> str:
    shard = artifact.get("optimized_shard")
    stable = isinstance(shard, dict) and shard.get("stable_ordinal_replay") is True
    has_raw = "_unvalidated_endpoint_points" in artifact
    if stable and not has_raw:
        return "keep"
    if has_raw and not stable:
        return "replay"
    return "invalid"


def _lane_finished_before_deadline(*, finished_at: float, deadline: float) -> bool:
    """Whether a parallel lane is eligible for ordinal-prefix commitment."""

    return finished_at < deadline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--process-started", type=float, required=True)
    parser.add_argument("--total-starts", type=int, required=True)
    parser.add_argument("--ordinal-start", type=int, required=True)
    parser.add_argument("--ordinal-end", type=int, required=True)
    parser.add_argument("--callbacks-per-start", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-id", type=int, required=True)
    parser.add_argument("--worker-count", type=int, required=True)
    parser.add_argument("--coordinator", action="store_true")
    parser.add_argument("--compiled-evaluator", action="store_true")
    arguments = parser.parse_args()
    if not (
        0 <= arguments.ordinal_start < arguments.ordinal_end <= arguments.total_starts
        and 0.0 < arguments.seconds <= 146.0
        and 0.0 < arguments.process_started <= time.monotonic()
        and arguments.callbacks_per_start == 600
        and 0 <= arguments.worker_id < arguments.worker_count
        and arguments.worker_count >= 1
    ):
        raise SystemExit("invalid optimized persistent search worker")

    search = _load(arguments.worker.resolve())
    base = search.BASE
    affinity = sorted(os.sched_getaffinity(0))
    thread_environment = {name: os.environ.get(name) for name in base.THREAD_VARIABLES}
    if len(affinity) != 1 or any(value != "1" for value in thread_environment.values()):
        raise SystemExit("one pinned CPU and one-thread environment are required")

    source_payload = arguments.source.read_bytes()
    if hashlib.sha256(source_payload).hexdigest() != arguments.source_sha256:
        raise SystemExit("source digest mismatch")
    document = json.loads(source_payload)
    hard_deadline = arguments.process_started + arguments.seconds
    replay_reserve = max(0.15, min(1.0, 0.05 * arguments.seconds))
    solve_deadline = max(arguments.process_started, hard_deadline - replay_reserve)
    total_callback_cap = (
        arguments.ordinal_end - arguments.ordinal_start
    ) * arguments.callbacks_per_start
    base_case, budget, evaluator = base.build_source_case(
        document,
        callback_cap=total_callback_cap,
        deadline=solve_deadline,
    )
    compiled_evaluator_metadata: dict[str, Any] = {
        "schema_version": "geotarget.compiled-residual-plan/v1",
        "enabled": False,
        "case_specific_routing": False,
    }
    if arguments.compiled_evaluator:
        evaluator, compiled_evaluator_metadata = _activate_compiled_evaluator(
            evaluator,
            budget,
            source_sha256=arguments.source_sha256,
        )
    policy = base.materialize_policy(
        document,
        source_sha256=arguments.source_sha256,
        starts=arguments.total_starts,
        seed=arguments.seed,
    )
    if policy.policy_digest != base.SOURCE_ONLY_POLICY_DIGEST:
        raise RuntimeError("source-only policy digest changed")
    prefix = base.build_literal_prefix(document, base_case, policy)
    program = (
        None
        if base_case.dimension == 0
        else base.compile_program(
            SEARCH_ARM,
            document,
        )
    )
    arguments.output.mkdir(parents=True, exist_ok=True)
    while time.monotonic() < solve_deadline:
        ordinal = _claim(arguments.queue, arguments.ordinal_end, arguments.worker_id)
        if ordinal is None:
            break
        if not arguments.ordinal_start <= ordinal < arguments.ordinal_end:
            raise RuntimeError("shared queue produced an out-of-range ordinal")
        before = {
            name: int(getattr(budget, name))
            for name in ("callbacks", "finite", "invalid", "guard_failed")
        }
        if base_case.dimension == 0:
            if ordinal != arguments.ordinal_start:
                break
            endpoint = base.np.empty(0, dtype=float)
            base_case.evaluate(endpoint)
            endpoints = ((0, endpoint),)
            statuses = {"dimension_zero_direct_replay": 1}
            counters = {"unique_configuration_evaluated": 1}
            lane_callbacks = (int(budget.callbacks) - before["callbacks"],)
        else:
            one = replace(
                prefix,
                points=(prefix.points[ordinal],),
                sources=(prefix.sources[ordinal],),
                scale_exponents=(prefix.scale_exponents[ordinal],),
            )
            outcome = base.run_local_arm(
                SEARCH_ARM,
                base_case=base_case,
                budget=budget,
                program=program,
                literal_prefix=one,
                callback_cap=total_callback_cap,
                callbacks_per_start=arguments.callbacks_per_start,
                deadline_monotonic=solve_deadline,
            )
            if not outcome.lane_callbacks:
                break
            # A serial frozen prefix never commits a lane whose optimizer is
            # still running when the common search deadline closes.  A
            # parallel worker can otherwise give a later ordinal a different
            # effective history.  Leave this ordinal uncommitted so the
            # global reducer closes the accepted prefix at this exact gap.
            if not _lane_finished_before_deadline(
                finished_at=time.monotonic(), deadline=solve_deadline
            ):
                break
            endpoints = outcome.endpoints
            statuses = outcome.statuses
            counters = outcome.counters
            lane_callbacks = outcome.lane_callbacks

        raw_endpoint_points = [
            base.np.asarray(endpoint, dtype=float).tolist() for _lane, endpoint in endpoints
        ]
        work = {
            name: int(getattr(budget, attribute)) - before[attribute]
            for name, attribute in (
                ("callbacks", "callbacks"),
                ("finite_callbacks", "finite"),
                ("invalid_callbacks", "invalid"),
                ("guard_failed_callbacks", "guard_failed"),
            )
        }
        work.update(
            {
                "best_residual_inf": (
                    float(budget.best_norm) if math.isfinite(budget.best_norm) else None
                ),
                "lanes_started": 1,
                "lane_callbacks_min": min(lane_callbacks),
                "lane_callbacks_max": max(lane_callbacks),
            }
        )
        source_unchanged = arguments.source.read_bytes() == source_payload
        result = {
            "schema_version": base.SCHEMA,
            "completed": True,
            "arm": SEARCH_ARM,
            "source_sha256": arguments.source_sha256,
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
            "binding_record": base.BINDING_RECORD,
            "configuration": base.configuration_manifest(),
            "compiled_evaluator": compiled_evaluator_metadata,
            "base_policy_packet": base.packet_record(policy),
            "literal_prefix": {
                "sha256": prefix.sha256,
                "full_prefix_sha256": prefix.sha256,
                "sources": [prefix.sources[ordinal]],
                "scale_exponents": [prefix.scale_exponents[ordinal]],
                "selected_proposal_points_sha256": _point_digest((prefix.points[ordinal],)),
            },
            "budget": {
                "seconds": arguments.seconds,
                "starts": arguments.total_starts,
                "callbacks_per_start": arguments.callbacks_per_start,
                "aggregate_callback_cap": arguments.callbacks_per_start,
                "endpoint_replay_reserve_seconds": replay_reserve,
            },
            "work": work,
            "activation": {
                "status_counts": dict(sorted(statuses.items())),
                "counter_sums": dict(sorted(counters.items())),
            },
            "endpoints": [],
            "endpoints_validated": 0,
            "safe_endpoint_count": 0,
            "diagnostic_distinct_target_count": 0,
            "diagnostic_targets": [],
            "diagnostic_targets_are_exact_or_complete": False,
            "elapsed_wall_seconds": time.monotonic() - arguments.process_started,
            "completed_start_ordinals": [ordinal],
            "optimized_shard": {
                "schema_version": "geotarget.optimized-search-shard/v1",
                "ordinal_start": ordinal,
                "ordinal_end": ordinal + 1,
                "total_prefix_starts": arguments.total_starts,
                "callbacks_per_start": arguments.callbacks_per_start,
                "prefix_materialized_before_slice": True,
                "persistent_worker": True,
            },
            "_unvalidated_endpoint_points": raw_endpoint_points,
        }
        if not source_unchanged:
            raise RuntimeError("source bytes changed during optimized search")
        _atomic_json(arguments.output / f"{ordinal:06d}-{ordinal + 1:06d}.json", result)
        _release(arguments.queue, arguments.worker_id, ordinal)

    done = arguments.output / f"worker-{arguments.worker_id:03d}.done"
    done.write_text("done\n", encoding="ascii")
    if not arguments.coordinator:
        return
    while time.monotonic() < hard_deadline - 0.02:
        if all(
            (arguments.output / f"worker-{worker_id:03d}.done").is_file()
            for worker_id in range(arguments.worker_count)
        ):
            break
        time.sleep(0.002)
    for ordinal in range(arguments.ordinal_start, arguments.ordinal_end):
        path = arguments.output / f"{ordinal:06d}-{ordinal + 1:06d}.json"
        if not path.is_file():
            break
        artifact = json.loads(path.read_text(encoding="utf-8"))
        replay_action = _replay_action(artifact)
        if replay_action == "keep":
            continue
        if replay_action == "invalid":
            break
        raw_points = artifact.pop("_unvalidated_endpoint_points", ())
        validations: list[dict[str, Any]] = []
        validated_endpoints: list[dict[str, Any]] = []
        for point in raw_points:
            if time.monotonic() >= hard_deadline - 0.02:
                break
            validations.append(base.replay_endpoint(evaluator, point, precision=80))
            validated_endpoints.append({"lane": ordinal, "point": point})
        artifact["endpoints"] = validated_endpoints
        artifact["endpoints_validated"] = len(validations)
        artifact["safe_endpoint_count"] = sum(
            validation.get("safe") is True for validation in validations
        )
        targets = base._targets(validations)
        artifact["diagnostic_distinct_target_count"] = len(targets)
        artifact["diagnostic_targets"] = targets
        artifact["optimized_shard"]["stable_ordinal_replay"] = True
        _atomic_json(path, artifact)


if __name__ == "__main__":
    main()
