"""Post-answer-only adaptive slack policy for frozen numerical-v15.

The frozen worker has no descriptor-authority seam inside numerical discovery.
Consequently this overlay leaves discovery, reservoir replay, primary tranche
selection, and every scheduling decision through the first authority result
unchanged.  Anonymous diversity is consulted only after an authority pass.
If no authority passes, candidate servicing follows frozen v15 exactly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from pathlib import Path
import time
from typing import Any


POLICY_ID = "post_answer_adaptive_slack_v2"
MAX_SLACK_HP_SECONDS = 6.0


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
    """Order anonymous endpoints only after canonical authority has passed."""

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
    # Raw differences followed by unit-range normalization are invariant under
    # every invertible affine transform of the provisional target.
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


def _slack_capacity(
    remaining_seconds: float,
    candidate_count: int,
    minimum_seconds: float,
) -> int:
    """Fit a breadth tranche after all frozen scheduled work has completed."""

    if candidate_count <= 0 or remaining_seconds < minimum_seconds:
        return 0
    if remaining_seconds < MAX_SLACK_HP_SECONDS:
        return 1
    extra = math.floor(
        (remaining_seconds - MAX_SLACK_HP_SECONDS) / minimum_seconds
    )
    return min(candidate_count, 1 + max(0, extra))


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
    """Run frozen service until authority, then use genuinely leftover slack.

    The code before ``record_authority`` returns true mirrors frozen v15's
    `_service_candidates`: the same clock reads, tranche, order, paths, and
    timeout floats are used.  Adaptation is monotone: it appends deferred
    reservoir work only after all frozen waves finish; it never reserves time
    or reorders frozen work.
    """

    indexed = tuple(enumerate(candidates))
    all_primaries = tuple(
        (ordinal, candidate)
        for ordinal, candidate in indexed
        if candidate.cluster_rank == 0
    )
    retained_alternates = tuple(
        (ordinal, candidate)
        for ordinal, candidate in indexed
        if candidate.cluster_rank == 1
    )
    initial_remaining = max(
        0.0,
        hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS,
    )
    primary_tranche_capacity = base._primary_tranche_capacity(
        initial_remaining, len(all_primaries)
    )
    selected_primaries, deferred_primaries = base._select_primary_tranche(
        all_primaries, primary_tranche_capacity
    )

    attempts: list[dict[str, object]] = []
    descriptors: dict[str, dict[str, object]] = {}
    successful_cluster_ordinals: set[int] = set()
    primary_authority_clusters: set[int] = set()
    failed_primary_by_cluster: dict[int, tuple[int, Any, Path]] = {}
    authoritative_candidates: list[Any] = []
    attempted_ordinals: set[int] = set()
    first_authority_attempt_ordinal: int | None = None
    primary_attempted = 0
    alternate_attempted = 0
    restoration_attempted = 0
    primary_wave_complete = False
    alternate_wave_complete = False
    restoration_wave_complete = False
    eligible_alternate_count = 0
    eligible_restoration_count = 0
    slack_hp_attempted = 0
    slack_restoration_attempted = 0

    def record_authority(candidate: Any, attempt: Mapping[str, object]) -> bool:
        nonlocal first_authority_attempt_ordinal
        descriptor = attempt.get("descriptor")
        if attempt.get("authority_pass") is not True or not isinstance(
            descriptor, Mapping
        ):
            return False
        descriptors.setdefault(base._descriptor_key(descriptor), dict(descriptor))
        successful_cluster_ordinals.add(candidate.cluster_ordinal)
        authoritative_candidates.append(candidate)
        if first_authority_attempt_ordinal is None:
            first_authority_attempt_ordinal = len(attempts) - 1
        return True

    def adaptive_rank(
        pending: Sequence[tuple[int, Any]],
    ) -> tuple[tuple[int, Any], ...]:
        # Crucial reopen-gate invariant: this function is never called before
        # the first authority pass, so no pre-answer ordering work is changed.
        if first_authority_attempt_ordinal is None:
            return tuple(pending)
        return _rank_by_verified_diversity(
            base, pending, authoritative_candidates
        )

    def statistics() -> dict[str, object]:
        return {
            "policy": POLICY_ID,
            "pre_confirmation_schedule": "BITWISE_FROZEN_V15",
            "pre_confirmation_reserve_seconds": 0.0,
            "search_schedule_changed": False,
            "reservoir_replay_changed": False,
            "adaptive_activated": first_authority_attempt_ordinal is not None,
            "first_authority_attempt_ordinal": first_authority_attempt_ordinal,
            "attempts_after_first_authority": (
                0
                if first_authority_attempt_ordinal is None
                else len(attempts) - first_authority_attempt_ordinal - 1
            ),
            "primary_total": len(all_primaries),
            "primary_tranche_capacity": primary_tranche_capacity,
            "primary_selected_count": len(selected_primaries),
            "primary_deferred_unknown_count": len(deferred_primaries),
            "unselected_primary_disposition": "DEFERRED_UNKNOWN_NOT_DISCARDED",
            "primary_attempted": primary_attempted,
            "primary_wave_complete": primary_wave_complete,
            "all_discovered_primaries_served": bool(
                primary_wave_complete and not deferred_primaries
            ),
            "eligible_alternate_count": eligible_alternate_count,
            "alternate_attempted": alternate_attempted,
            "alternate_wave_complete": alternate_wave_complete,
            "same_cluster_alternates_skipped_after_authority": sum(
                candidate.cluster_ordinal in primary_authority_clusters
                for _ordinal, candidate in retained_alternates
            ),
            "eligible_restoration_count": eligible_restoration_count,
            "restoration_attempted": restoration_attempted,
            "restoration_wave_complete": restoration_wave_complete,
            "slack_hp_attempted": slack_hp_attempted,
            "slack_restoration_attempted": slack_restoration_attempted,
            "minimum_reserved_seconds_per_unserved_wave_candidate": (
                base.MIN_HP_ATTEMPT_SECONDS
            ),
            "maximum_primary_or_alternate_seconds": base.MAX_HP_ATTEMPT_SECONDS,
            "maximum_restoration_seconds": base.MAX_RESTORATION_ATTEMPT_SECONDS,
            "maximum_slack_hp_seconds": MAX_SLACK_HP_SECONDS,
            "cross_cluster_candidate_suppression": False,
            "truth_case_family_known_target_count_read": False,
        }

    # Frozen wave 1.  Even after confirmation this consumes the exact frozen
    # tuple order.  Adaptation may use only wall slack after every frozen wave.
    primary_pending = list(selected_primaries)
    while primary_pending:
        ordinal, candidate = primary_pending.pop(0)
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
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
        attempted_ordinals.add(ordinal)
        primary_attempted += 1
        if record_authority(candidate, attempt):
            primary_authority_clusters.add(candidate.cluster_ordinal)
            continue
        failed_primary_by_cluster[candidate.cluster_ordinal] = (
            ordinal,
            candidate,
            hp_output,
        )
    primary_wave_complete = not primary_pending
    if not primary_wave_complete:
        return attempts, descriptors, statistics()

    # Frozen wave 2 eligibility and order are retained.
    eligible_alternates = tuple(
        (ordinal, candidate)
        for ordinal, candidate in retained_alternates
        if candidate.cluster_ordinal in failed_primary_by_cluster
        and not base._same_cluster_authority_exists(
            candidate, successful_cluster_ordinals
        )
    )
    eligible_alternate_count = len(eligible_alternates)
    alternate_pending = list(eligible_alternates)
    while alternate_pending:
        ordinal, candidate = alternate_pending.pop(0)
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(alternate_pending) + 1,
            base.MAX_HP_ATTEMPT_SECONDS,
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
        attempted_ordinals.add(ordinal)
        alternate_attempted += 1
        if record_authority(candidate, attempt):
            failed_primary_by_cluster.pop(candidate.cluster_ordinal, None)
    alternate_wave_complete = not alternate_pending
    if not alternate_wave_complete:
        return attempts, descriptors, statistics()

    # Frozen wave 3 candidate set and original ordinal order are retained.
    restorables = tuple(
        failed_primary_by_cluster[cluster_ordinal]
        for cluster_ordinal in sorted(
            failed_primary_by_cluster,
            key=lambda item: failed_primary_by_cluster[item][0],
        )
    )
    eligible_restoration_count = len(restorables)
    restoration_pending = list(restorables)
    while restoration_pending:
        position = 0
        ordinal, candidate, failed_hp_output = restoration_pending.pop(position)
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(restoration_pending) + 1,
            base.MAX_RESTORATION_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
            restoration_pending.insert(
                position, (ordinal, candidate, failed_hp_output)
            )
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
        if record_authority(candidate, rescue):
            failed_primary_by_cluster.pop(candidate.cluster_ordinal, None)
    restoration_wave_complete = not restoration_pending
    if not restoration_wave_complete or first_authority_attempt_ordinal is None:
        return attempts, descriptors, statistics()

    # Only now, after every frozen wave completed and authority has passed, may
    # genuinely unused wall time admit deferred replay-reservoir endpoints.
    remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
    unattempted = tuple(
        item for item in indexed if item[0] not in attempted_ordinals
    )
    ranked_unattempted = adaptive_rank(unattempted)
    slack_capacity = _slack_capacity(
        remaining, len(ranked_unattempted), base.MIN_HP_ATTEMPT_SECONDS
    )
    slack_pending = list(ranked_unattempted[:slack_capacity])
    slack_failures: list[tuple[int, Any, Path]] = []
    while slack_pending:
        slack_pending[:] = adaptive_rank(slack_pending)
        ordinal, candidate = slack_pending.pop(0)
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(slack_pending) + 1,
            MAX_SLACK_HP_SECONDS,
        )
        if attempt_seconds == 0.0:
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
        attempted_ordinals.add(ordinal)
        slack_hp_attempted += 1
        if not record_authority(candidate, attempt):
            slack_failures.append((ordinal, candidate, hp_output))

    # Fast failed slack attempts may themselves leave restoration slack.  This
    # uses only their existing failed authority artifacts and the frozen rescue.
    while slack_failures:
        ranked = adaptive_rank(
            tuple(
                (ordinal, candidate)
                for ordinal, candidate, _path in slack_failures
            )
        )
        next_ordinal = ranked[0][0]
        position = next(
            index
            for index, (ordinal, _candidate, _path) in enumerate(slack_failures)
            if ordinal == next_ordinal
        )
        ordinal, candidate, failed_hp_output = slack_failures.pop(position)
        remaining = hard_deadline - time.monotonic() - base.FINALIZE_RESERVE_SECONDS
        attempt_seconds = base._wave_attempt_seconds(
            remaining,
            len(slack_failures) + 1,
            base.MAX_RESTORATION_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
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
        slack_restoration_attempted += 1
        record_authority(candidate, rescue)

    return attempts, descriptors, statistics()


def patch_plan(
    original_plan: Any,
    *,
    overlay_worker_sha256: str,
    mechanism_sha256: str,
) -> Any:
    """Add audit provenance without altering any frozen schedule field."""

    def wrapped(**kwargs: object) -> dict[str, object]:
        plan = dict(original_plan(**kwargs))
        plan.update(
            {
                "schema_version": "geotarget.exp-multitarget-001-plan-v2/v1",
                "tail_policy": POLICY_ID,
                "overlay_worker_sha256": overlay_worker_sha256,
                "tail_mechanism_sha256": mechanism_sha256,
                "pre_confirmation_schedule": "BITWISE_FROZEN_V15",
                "pre_confirmation_reserve_seconds": 0.0,
                "search_schedule_changed": False,
                "reservoir_replay_changed": False,
                "adaptive_activation": "FIRST_CANONICAL_AUTHORITY_PASS",
                "post_confirmation_extra_work": "REMAINING_WALL_SLACK_ONLY",
                "canonical_source_replay_changed": False,
                "exact_authority_changed": False,
            }
        )
        return plan

    return wrapped
