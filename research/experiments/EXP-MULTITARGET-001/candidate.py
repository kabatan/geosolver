"""Truth-blind post-answer tail policy for the frozen numerical-v15 worker.

This module deliberately owns scheduling only.  Discovery, original-source
replay, high-precision refinement, exact identification, and canonical
authority remain functions supplied by the hash-bound frozen worker.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from pathlib import Path
import time
from typing import Any


POLICY_ID = "post_answer_diverse_tail_v1"
MINIMUM_POST_SEARCH_RESERVE_SECONDS = 28.0
RESERVOIR_REPLAY_SECONDS = 3.0
DIVERSITY_TAIL_RESERVE_SECONDS = 6.0
MAX_ALTERNATE_SECONDS = 6.0
SCHEDULING_SLACK_SECONDS = 0.25


def _unit_range(values: Mapping[int, float]) -> dict[int, float]:
    if not values:
        return {}
    finite = tuple(value for value in values.values() if math.isfinite(value))
    if len(finite) != len(values):
        return {key: 0.0 for key in values}
    low = min(finite)
    high = max(finite)
    if high <= low:
        return {key: 0.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def _rank_by_verified_diversity(
    base: Any,
    pending: Sequence[tuple[int, Any]],
    authoritative: Sequence[Any],
) -> tuple[tuple[int, Any], ...]:
    """Softly prioritize distance from already verified candidates.

    The exact descriptor is used only to establish that a candidate has passed
    authority.  Distances use the corresponding source-replayed provisional
    target and configuration; no Gold target or known answer count is present.
    """

    ordered = tuple(pending)
    if len(ordered) < 2 or not authoritative:
        return ordered

    residual_order = sorted(
        ordered,
        key=lambda item: (item[1].residual_inf, item[1].endpoint_sha256),
    )
    denominator = max(1, len(residual_order) - 1)
    residual_quality = {
        ordinal: 1.0 - rank / denominator
        for rank, (ordinal, _candidate) in enumerate(residual_order)
    }
    target_novelty = {
        ordinal: min(
            abs(candidate.provisional_target - accepted.provisional_target)
            for accepted in authoritative
        )
        for ordinal, candidate in ordered
    }
    configuration_novelty = {
        ordinal: min(
            base._configuration_distance(candidate, accepted)
            for accepted in authoritative
        )
        for ordinal, candidate in ordered
    }
    target_score = _unit_range(target_novelty)
    configuration_score = _unit_range(configuration_novelty)

    def priority(item: tuple[int, Any]) -> tuple[object, ...]:
        ordinal, candidate = item
        # Once one descriptor is known, novelty leads.  Residual quality stays
        # in the score so a numerically unusable endpoint cannot win on distance
        # alone.  This changes order only, never admission or authority.
        score = (
            0.50 * target_score[ordinal]
            + 0.25 * configuration_score[ordinal]
            + 0.25 * residual_quality[ordinal]
        )
        return (
            -score,
            -target_score[ordinal],
            -configuration_score[ordinal],
            -residual_quality[ordinal],
            candidate.residual_inf,
            candidate.endpoint_sha256,
        )

    return tuple(sorted(ordered, key=priority))


def _tranche_capacity(
    remaining_seconds: float,
    candidate_count: int,
    maximum_seconds: float,
    minimum_seconds: float,
) -> int:
    """Return a finite wall-feasible breadth tranche."""

    if candidate_count < 0:
        raise ValueError("candidate count cannot be negative")
    if maximum_seconds < minimum_seconds or minimum_seconds <= 0.0:
        raise ValueError("invalid attempt limits")
    if (
        candidate_count == 0
        or remaining_seconds < minimum_seconds + SCHEDULING_SLACK_SECONDS
    ):
        return 0
    if remaining_seconds < maximum_seconds:
        return 1
    extra = math.floor((remaining_seconds - maximum_seconds) / minimum_seconds)
    return min(candidate_count, 1 + max(0, extra))


def _select_tranche(
    base: Any,
    candidates: Sequence[tuple[int, Any]],
    capacity: int,
) -> tuple[tuple[tuple[int, Any], ...], tuple[tuple[int, Any], ...]]:
    # Reuse the frozen residual/target/configuration selector.  It is a soft
    # scheduling heuristic and has no target-identity authority.
    return base._select_primary_tranche(candidates, capacity)


def service_candidates(
    base: Any,
    *,
    source: Path,
    source_sha256: str,
    candidates: Sequence[Any],
    cpu: int,
    output: Path,
    hard_deadline: float,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]], dict[str, object]]:
    """Serve primaries, same-cluster alternates, then restoration.

    A successful authority never terminates this function.  Exact descriptors
    deduplicate only at the final frozen descriptor key, while every admitted
    same-target/configuration candidate remains eligible for service.
    """

    indexed = tuple(enumerate(candidates))
    all_primaries = tuple(
        item for item in indexed if item[1].cluster_rank == 0
    )
    all_alternates = tuple(
        item for item in indexed if item[1].cluster_rank == 1
    )
    initial_remaining = max(
        0.0,
        hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS,
    )
    diversity_reserve = min(
        DIVERSITY_TAIL_RESERVE_SECONDS,
        max(
            0.0,
            initial_remaining
            - base.MIN_HP_ATTEMPT_SECONDS
            - SCHEDULING_SLACK_SECONDS,
        ),
    )
    primary_budget = max(0.0, initial_remaining - diversity_reserve)
    primary_capacity = base._primary_tranche_capacity(
        primary_budget, len(all_primaries)
    )
    primaries, deferred_primaries = _select_tranche(
        base, all_primaries, primary_capacity
    )

    attempts: list[dict[str, object]] = []
    descriptors: dict[str, dict[str, object]] = {}
    authoritative_candidates: list[Any] = []
    failed_primary_by_cluster: dict[int, tuple[int, Any, Path]] = {}
    primary_attempted = 0
    alternate_attempted = 0
    restoration_attempted = 0
    authority_attempt_ordinals: list[int] = []
    first_authority_attempt_ordinal: int | None = None

    def record_authority(candidate: Any, attempt: Mapping[str, object]) -> bool:
        nonlocal first_authority_attempt_ordinal
        descriptor = attempt.get("descriptor")
        if attempt.get("authority_pass") is not True or not isinstance(
            descriptor, Mapping
        ):
            return False
        descriptors.setdefault(base._descriptor_key(descriptor), dict(descriptor))
        authoritative_candidates.append(candidate)
        authority_attempt_ordinals.append(len(attempts) - 1)
        if first_authority_attempt_ordinal is None:
            first_authority_attempt_ordinal = len(attempts) - 1
        return True

    primary_phase_deadline = min(
        hard_deadline - base.FINALIZE_RESERVE_SECONDS,
        time.monotonic() + primary_budget,
    )
    primary_pending = list(primaries)
    while primary_pending:
        primary_pending[:] = _rank_by_verified_diversity(
            base, primary_pending, authoritative_candidates
        )
        ordinal, candidate = primary_pending.pop(0)
        remaining = primary_phase_deadline - time.monotonic()
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(primary_pending) + 1,
            base.MAX_HP_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
            primary_pending.insert(0, (ordinal, candidate))
            break
        hp_output = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        attempt = base._run_hp_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=hp_output,
            timeout_seconds=attempt_seconds,
        )
        attempts.append(attempt)
        primary_attempted += 1
        if not record_authority(candidate, attempt):
            failed_primary_by_cluster[candidate.cluster_ordinal] = (
                ordinal,
                candidate,
                hp_output,
            )
    primary_wave_complete = not primary_pending

    tail_remaining = max(
        0.0,
        hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS,
    )
    restoration_reserve = (
        min(
            base.MIN_HP_ATTEMPT_SECONDS,
            max(
                0.0,
                tail_remaining
                - base.MIN_HP_ATTEMPT_SECONDS
                - SCHEDULING_SLACK_SECONDS,
            ),
        )
        if failed_primary_by_cluster
        else 0.0
    )
    alternate_budget = max(0.0, tail_remaining - restoration_reserve)
    alternate_capacity = _tranche_capacity(
        alternate_budget,
        len(all_alternates),
        MAX_ALTERNATE_SECONDS,
        base.MIN_HP_ATTEMPT_SECONDS,
    )
    alternates, deferred_alternates = _select_tranche(
        base, all_alternates, alternate_capacity
    )
    alternate_pending = list(alternates)
    alternate_phase_deadline = min(
        hard_deadline - base.FINALIZE_RESERVE_SECONDS,
        time.monotonic() + alternate_budget,
    )
    while alternate_pending:
        alternate_pending[:] = _rank_by_verified_diversity(
            base, alternate_pending, authoritative_candidates
        )
        ordinal, candidate = alternate_pending.pop(0)
        remaining = alternate_phase_deadline - time.monotonic()
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(alternate_pending) + 1,
            MAX_ALTERNATE_SECONDS,
        )
        if attempt_seconds == 0.0:
            alternate_pending.insert(0, (ordinal, candidate))
            break
        hp_output = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        attempt = base._run_hp_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=hp_output,
            timeout_seconds=attempt_seconds,
        )
        attempts.append(attempt)
        alternate_attempted += 1
        record_authority(candidate, attempt)
    alternate_wave_complete = not alternate_pending

    # Restoration remains failure-triggered, but success from another endpoint
    # in the same provisional cluster does not suppress it.  Provisional
    # clustering is not exact target identity.
    restoration_pending = list(failed_primary_by_cluster.values())
    while restoration_pending:
        ranked = _rank_by_verified_diversity(
            base,
            tuple((ordinal, candidate) for ordinal, candidate, _path in restoration_pending),
            authoritative_candidates,
        )
        next_ordinal = ranked[0][0]
        position = next(
            index
            for index, (ordinal, _candidate, _path) in enumerate(restoration_pending)
            if ordinal == next_ordinal
        )
        ordinal, candidate, failed_hp_output = restoration_pending.pop(position)
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(restoration_pending) + 1,
            base.MAX_RESTORATION_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
            restoration_pending.insert(position, (ordinal, candidate, failed_hp_output))
            break
        rescue = base._run_restoration_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            failed_authority_artifact=failed_hp_output / "authority.json",
            output=output
            / "restoration"
            / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}",
            timeout_seconds=attempt_seconds,
        )
        attempts.append(rescue)
        restoration_attempted += 1
        record_authority(candidate, rescue)

    statistics: dict[str, object] = {
        "policy": POLICY_ID,
        "post_search_reserve_seconds": MINIMUM_POST_SEARCH_RESERVE_SECONDS,
        "reservoir_replay_seconds": RESERVOIR_REPLAY_SECONDS,
        "diversity_tail_reserve_seconds": diversity_reserve,
        "restoration_reserve_seconds": restoration_reserve,
        "primary_total": len(all_primaries),
        "primary_tranche_capacity": primary_capacity,
        "primary_selected_count": len(primaries),
        "primary_deferred_unknown_count": len(deferred_primaries),
        "primary_attempted": primary_attempted,
        "primary_wave_complete": primary_wave_complete,
        "alternate_total": len(all_alternates),
        "alternate_selected_count": len(alternates),
        "alternate_deferred_unknown_count": len(deferred_alternates),
        "alternate_attempted": alternate_attempted,
        "alternate_wave_complete": alternate_wave_complete,
        "same_cluster_alternates_skipped_after_authority": 0,
        "same_target_candidate_suppression": False,
        "cross_cluster_candidate_suppression": False,
        "restoration_attempted": restoration_attempted,
        "restoration_wave_complete": not restoration_pending,
        "first_authority_attempt_ordinal": first_authority_attempt_ordinal,
        "attempts_after_first_authority": (
            0
            if first_authority_attempt_ordinal is None
            else len(attempts) - first_authority_attempt_ordinal - 1
        ),
        "authority_attempt_ordinals": authority_attempt_ordinals,
        "distinct_exact_descriptor_count": len(descriptors),
        "unselected_candidate_disposition": "DEFERRED_UNKNOWN_NOT_DISCARDED",
        "truth_case_family_known_target_count_read": False,
    }
    return attempts, descriptors, statistics


def patch_plan(
    base: Any,
    original_plan: Any,
    *,
    minimum_tail_seconds: float,
    overlay_worker_sha256: str,
    mechanism_sha256: str,
) -> Any:
    """Decorate the frozen dry plan without changing its source contract."""

    def wrapped(**kwargs: object) -> dict[str, object]:
        plan = dict(original_plan(**kwargs))
        plan.update(
            {
                "schema_version": "geotarget.exp-multitarget-001-plan/v1",
                "tail_policy": POLICY_ID,
                "overlay_worker_sha256": overlay_worker_sha256,
                "tail_mechanism_sha256": mechanism_sha256,
                "minimum_post_search_reserve_seconds": minimum_tail_seconds,
                "reservoir_replay_seconds": RESERVOIR_REPLAY_SECONDS,
                "same_target_candidate_suppression": False,
                "post_first_descriptor_search_continues": True,
                "tail_priority": (
                    "verified-descriptor-associated provisional target and "
                    "configuration diversity, with residual quality"
                ),
                "canonical_source_replay_changed": False,
                "exact_authority_changed": False,
            }
        )
        return plan

    return wrapped
