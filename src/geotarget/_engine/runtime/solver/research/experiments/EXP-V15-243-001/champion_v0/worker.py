#!/usr/bin/env python3
"""v15 candidate with cheap semantic admission and delayed target evaluation.

The frozen v15 worker spends its one-second endpoint-selection window running
an 80-digit target evaluation for every source-safe endpoint.  That work is
both unnecessary before HP refinement and capable of discarding every
endpoint when target construction is expensive or temporarily unsupported.

This research wrapper keeps the frozen search and HP authorities, but changes
only the search-to-HP seam:

* replay Float64 residual, guards, and hard feasibility;
* admit source-semantic endpoints through the reviewed 1e-3 near-root band;
* do not evaluate or cluster by a provisional target before HP;
* select the finite HP tranche by residual quality and configuration maximin;
* retain exact target identity as an HP/final-authority decision only.

No case identity, family, truth, known target count, or inferred bound is
available to the policy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE_WORKER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
)
SEARCH_WORKER = HERE / "search_worker.py"
HP_BRIDGE = HERE / "hp_bridge.py"
ENDPOINT_RESERVOIR = (
    HERE.parent / "candidates/endpoint_reservoir/candidate.py"
)
SAFE_RESIDUAL_MAX = 1.0e-8
NEAR_RESIDUAL_MAX = 1.0e-3
SELECTION_RESERVE_SECONDS = 3.0
FINALIZE_RESERVE_SECONDS = 3.0

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_base():
    name = "geotarget_exp_v15_243_champion_v0_base"
    specification = importlib.util.spec_from_file_location(name, BASE_WORKER)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_base()


def _load_endpoint_reservoir():
    name = "geotarget_exp_v15_243_champion_v0_endpoint_reservoir"
    specification = importlib.util.spec_from_file_location(
        name, ENDPOINT_RESERVOIR
    )
    if specification is None or specification.loader is None:
        raise ImportError(ENDPOINT_RESERVOIR)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


RESERVOIR = _load_endpoint_reservoir()


@dataclass(frozen=True)
class ReplayCandidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None = None
    cluster_ordinal: int = 0
    cluster_rank: int = 0
    discovery_ordinal: int = 0
    admission_role: str = "RAW_SAFE"
    record_id: str = ""
    bucket_id: str = ""
    bucket_kind: str = ""
    aging_wave: int = 0
    semantic_verified: bool = True


class CandidateReservoir(tuple):
    """Verified candidates plus an explicit, unclaimed deadline backlog."""

    def __new__(
        cls,
        verified: Sequence[ReplayCandidate],
        deadline_backlog: Sequence[ReplayCandidate] = (),
    ):
        instance = super().__new__(cls, tuple(verified))
        instance.deadline_backlog = tuple(deadline_backlog)
        return instance


def _fresh_replay_candidates(
    document: dict[str, object],
    endpoints: Sequence[object],
    *,
    hard_deadline: float,
) -> tuple[ReplayCandidate, ...]:
    """Admit semantic near roots and preserve any unexamined backlog."""

    runtime = BASE._load_module(
        "geotarget_exp_v15_243_champion_v0_precision_runtime",
        BASE.PRECISION_RUNTIME,
    )
    _case, _budget, evaluator = runtime.build_source_case(
        document,
        callback_cap=max(1, len(endpoints)),
        deadline=max(time.monotonic() + 0.01, hard_deadline),
    )
    scan = RESERVOIR.cheap_scan_endpoints(
        evaluator,
        endpoints,
        hard_deadline=hard_deadline,
    )
    reservoir_plan = RESERVOIR.build_plan(scan.observations)
    scheduled = RESERVOIR.scheduled_endpoints(reservoir_plan)

    # Each unknown-target discovery remains an independent HP primary.  This
    # prevents authority from one provisional configuration from suppressing
    # another before exact descriptors exist.  Equal Float64 endpoint bytes
    # are retained as separate discoveries and naturally fall late in the
    # configuration-maximin aging order.
    converted = tuple(
        ReplayCandidate(
            endpoint=row.endpoint,
            endpoint_sha256=row.endpoint_sha256,
            residual_inf=row.residual_inf,
            provisional_target=None,
            cluster_ordinal=cluster_ordinal,
            cluster_rank=0,
            discovery_ordinal=int(row.record_id.split(":", 1)[0]),
            admission_role=row.admission_role,
            record_id=row.record_id,
            bucket_id=row.bucket_id,
            bucket_kind=row.bucket_kind,
            aging_wave=row.aging_wave,
            semantic_verified=(
                row.admission_role != RESERVOIR.DEADLINE_BACKLOG_ROLE
            ),
        )
        for cluster_ordinal, row in enumerate(scheduled)
    )
    verified = tuple(
        candidate for candidate in converted if candidate.semantic_verified
    )
    backlog = tuple(
        candidate for candidate in converted if not candidate.semantic_verified
    )
    return CandidateReservoir(verified, backlog)


def _select_primary_tranche(
    primaries: Sequence[tuple[int, ReplayCandidate]],
    capacity: int,
) -> tuple[
    tuple[tuple[int, ReplayCandidate], ...],
    tuple[tuple[int, ReplayCandidate], ...],
]:
    """Preserve the reservoir's residual-plus-maximin aging order."""

    if capacity < 0:
        raise ValueError("primary tranche capacity cannot be negative")
    ordered = tuple(primaries)
    return ordered[:capacity], ordered[capacity:]


def _finite_semantic_observation(evaluator, endpoint: Sequence[float]):
    observation = evaluator.evaluate_float_residual(endpoint)
    guard_ok, violations = evaluator.evaluate_guard(endpoint)
    hard = evaluator.evaluate_float_hard_feasibility(endpoint)
    residual = float(observation.residual_norm_float)
    finite = bool(
        getattr(observation, "is_finite", False)
        and math.isfinite(residual)
    )
    return {
        "finite": finite,
        "guard_ok": bool(guard_ok),
        "guard_violations": tuple(violations),
        "hard_feasible": bool(hard.hard_feasible),
        "residual_inf": residual if math.isfinite(residual) else None,
    }


_ORIGINAL_SERVICE_CANDIDATES = BASE._service_candidates


def _service_candidates(
    *,
    source: Path,
    source_sha256: str,
    candidates: Sequence[ReplayCandidate],
    cpu: int,
    output: Path,
    hard_deadline: float,
):
    """Service reservoir batches until the real wall budget is exhausted.

    The frozen worker chooses one finite primary tranche once.  If an HP child
    returns early, the rest of the reservoir remains unreachable.  This
    wrapper preserves the frozen per-batch HP/restoration policy but repeatedly
    admits the next reservoir prefix whenever actual elapsed time leaves room.
    Deadline-unexamined rows are cheaply source-replayed before they can enter
    any HP batch.
    """

    queue = list(candidates)
    deadline_backlog = list(
        getattr(candidates, "deadline_backlog", ())
    )
    queue.extend(deadline_backlog)
    discovered_count = len(queue)
    initial_verified_count = len(candidates)
    backlog_verified_count = 0
    backlog_rejected_count = 0
    batch_statistics: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []
    descriptors: dict[str, dict[str, object]] = {}
    batch_ordinal = 0
    replay_evaluator = None

    def verify_front_backlog() -> bool:
        nonlocal replay_evaluator
        nonlocal backlog_verified_count
        nonlocal backlog_rejected_count

        if not queue or queue[0].semantic_verified:
            return True
        if (
            time.monotonic()
            >= hard_deadline - BASE.FINALIZE_RESERVE_SECONDS
        ):
            return False
        if replay_evaluator is None:
            _payload, document = BASE._source_contract(source, source_sha256)
            runtime = BASE._load_module(
                "geotarget_exp_v15_243_champion_v0_service_precision_runtime",
                BASE.PRECISION_RUNTIME,
            )
            _case, _budget, replay_evaluator = runtime.build_source_case(
                document,
                callback_cap=max(1, len(deadline_backlog)),
                deadline=hard_deadline - BASE.FINALIZE_RESERVE_SECONDS,
            )
        candidate = queue[0]
        try:
            replay = _finite_semantic_observation(
                replay_evaluator, candidate.endpoint
            )
        except Exception:
            replay = {}
        residual = replay.get("residual_inf")
        if (
            replay.get("finite") is True
            and replay.get("guard_ok") is True
            and replay.get("hard_feasible") is True
            and isinstance(residual, float)
            and residual <= NEAR_RESIDUAL_MAX
        ):
            queue[0] = replace(
                candidate,
                residual_inf=residual,
                admission_role=(
                    RESERVOIR.TARGET_UNAVAILABLE_RAW_SAFE_ROLE
                    if residual <= SAFE_RESIDUAL_MAX
                    else RESERVOIR.TARGET_UNAVAILABLE_NEAR_ROOT_ROLE
                ),
                semantic_verified=True,
            )
            backlog_verified_count += 1
            return True
        queue.pop(0)
        backlog_rejected_count += 1
        return True

    while queue:
        if not verify_front_backlog():
            break
        if not queue:
            break
        remaining = (
            hard_deadline
            - time.monotonic()
            - BASE.FINALIZE_RESERVE_SECONDS
        )
        capacity = BASE._primary_tranche_capacity(
            remaining,
            sum(candidate.semantic_verified for candidate in queue),
        )
        if capacity < 1:
            break

        verified_prefix = 0
        for candidate in queue:
            if not candidate.semantic_verified:
                break
            verified_prefix += 1
        capacity = min(capacity, verified_prefix)
        if capacity < 1:
            continue
        batch = tuple(queue[:capacity])
        batch_attempts, batch_descriptors, statistics = (
            _ORIGINAL_SERVICE_CANDIDATES(
                source=source,
                source_sha256=source_sha256,
                candidates=batch,
                cpu=cpu,
                output=output / f"reservoir-batch-{batch_ordinal:03d}",
                hard_deadline=hard_deadline,
            )
        )
        attempts.extend(batch_attempts)
        for key, descriptor in batch_descriptors.items():
            descriptors.setdefault(key, descriptor)
        batch_statistics.append(dict(statistics))

        primary_attempted = int(statistics.get("primary_attempted", 0))
        primary_complete = bool(statistics.get("primary_wave_complete"))
        consumed = len(batch) if primary_complete else primary_attempted
        if consumed < 1:
            break
        del queue[:consumed]
        batch_ordinal += 1
        if not primary_complete:
            break

    deferred_ids = tuple(candidate.record_id for candidate in queue)
    aggregate = {
        "policy": (
            "target-free reservoir batches; each batch preserves frozen "
            "HP/restoration policy; actual early returns promote the next "
            "breadth-first aging prefix"
        ),
        "reservoir_batch_count": len(batch_statistics),
        "reservoir_batches": batch_statistics,
        "primary_total": discovered_count,
        "primary_tranche_capacity": (
            int(batch_statistics[0].get("primary_tranche_capacity", 0))
            if batch_statistics
            else 0
        ),
        "primary_selected_count": sum(
            int(row.get("primary_selected_count", 0))
            for row in batch_statistics
        ),
        "primary_deferred_unknown_count": len(queue),
        "unselected_primary_disposition": (
            "EXPLICIT_DEFERRED_UNKNOWN_AFTER_REAL_WALL_BUDGET"
        ),
        "deferred_record_ids": deferred_ids,
        "primary_attempted": sum(
            int(row.get("primary_attempted", 0))
            for row in batch_statistics
        ),
        "primary_wave_complete": not queue,
        "all_discovered_primaries_served": not queue,
        "all_discovered_records_resolved": not queue,
        "eligible_alternate_count": sum(
            int(row.get("eligible_alternate_count", 0))
            for row in batch_statistics
        ),
        "alternate_attempted": sum(
            int(row.get("alternate_attempted", 0))
            for row in batch_statistics
        ),
        "alternate_wave_complete": all(
            bool(row.get("alternate_wave_complete"))
            for row in batch_statistics
        ),
        "same_cluster_alternates_skipped_after_authority": sum(
            int(
                row.get(
                    "same_cluster_alternates_skipped_after_authority", 0
                )
            )
            for row in batch_statistics
        ),
        "eligible_restoration_count": sum(
            int(row.get("eligible_restoration_count", 0))
            for row in batch_statistics
        ),
        "restoration_attempted": sum(
            int(row.get("restoration_attempted", 0))
            for row in batch_statistics
        ),
        "restoration_wave_complete": all(
            bool(row.get("restoration_wave_complete"))
            for row in batch_statistics
        ),
        "initial_verified_near_root_count": initial_verified_count,
        "deadline_backlog_initial_count": len(deadline_backlog),
        "deadline_backlog_verified_count": backlog_verified_count,
        "deadline_backlog_rejected_count": backlog_rejected_count,
        "deadline_backlog_unexamined_count": sum(
            not candidate.semantic_verified for candidate in queue
        ),
        "minimum_reserved_seconds_per_unserved_wave_candidate": (
            BASE.MIN_HP_ATTEMPT_SECONDS
        ),
        "maximum_primary_or_alternate_seconds": (
            BASE.MAX_HP_ATTEMPT_SECONDS
        ),
        "maximum_restoration_seconds": (
            BASE.MAX_RESTORATION_ATTEMPT_SECONDS
        ),
        "cross_cluster_candidate_suppression": False,
    }
    return attempts, descriptors, aggregate


def _normalized_target_distance(
    left: ReplayCandidate, right: ReplayCandidate
) -> float:
    if left.provisional_target is None or right.provisional_target is None:
        return 0.0
    scale = max(
        abs(left.provisional_target),
        abs(right.provisional_target),
        1.0,
    )
    return abs(left.provisional_target - right.provisional_target) / scale


def _near_configuration_duplicate(
    candidate: ReplayCandidate, accepted: ReplayCandidate
) -> bool:
    machine_epsilon = math.ulp(1.0)
    uncertainty = math.sqrt(max(candidate.residual_inf, machine_epsilon))
    uncertainty += math.sqrt(max(accepted.residual_inf, machine_epsilon))
    return BASE._configuration_distance(candidate, accepted) <= uncertainty


_ORIGINAL_PLAN = BASE._plan


def _plan(**kwargs):
    plan = _ORIGINAL_PLAN(**kwargs)
    plan.update(
        {
            "schema_version": "geotarget.exp-v15-243-champion-v0-plan/v1",
            "integrated_worker_sha256": BASE._sha256(Path(__file__).read_bytes()),
            "base_worker_sha256": BASE._sha256(BASE_WORKER.read_bytes()),
            "selection_reserve_seconds": SELECTION_RESERVE_SECONDS,
            "candidate_selection": (
                "cheap original-evaluator residual/guard/hard replay through "
                "the reviewed 1e-3 near-root band; delayed target evaluation; "
                "explicit soft reservoir with residual champion, configuration "
                "maximin, breadth-first aging, deadline backlog replay, and "
                "deferred/unknown reporting at the real wall limit"
            ),
            "endpoint_reservoir_policy_sha256": RESERVOIR.policy_sha256(),
            "endpoint_reservoir_path": str(ENDPOINT_RESERVOIR),
            "pre_hp_target_evaluation": False,
            "pre_hp_target_deduplication": False,
            "safe_residual_max": SAFE_RESIDUAL_MAX,
            "near_residual_max": NEAR_RESIDUAL_MAX,
            "unknown_target_cross_configuration_suppression": False,
        }
    )
    return plan


BASE.ReplayCandidate = ReplayCandidate
BASE._fresh_replay_candidates = _fresh_replay_candidates
BASE._select_primary_tranche = _select_primary_tranche
BASE._service_candidates = _service_candidates
BASE._normalized_target_distance = _normalized_target_distance
BASE._near_configuration_duplicate = _near_configuration_duplicate
BASE._plan = _plan
BASE.SELECTION_RESERVE_SECONDS = SELECTION_RESERVE_SECONDS
BASE.FINALIZE_RESERVE_SECONDS = FINALIZE_RESERVE_SECONDS
BASE.SEARCH_WORKER = SEARCH_WORKER
BASE.HP_BRIDGE = HP_BRIDGE


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
