"""Leftover-only proposal scheduling at the frozen champion service seam."""

from __future__ import annotations

import math
import time
from typing import Callable, Mapping, Sequence


ProposalFactory = Callable[
    [Mapping[str, object], tuple[tuple[float, ...], ...], float],
    Sequence[Sequence[float]],
]


def _finite_points(
    endpoints: Sequence[object], dimension: int
) -> tuple[tuple[float, ...], ...]:
    points: list[tuple[float, ...]] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, Mapping) or not isinstance(endpoint.get("point"), list):
            continue
        try:
            point = tuple(float(value) for value in endpoint["point"])
        except (TypeError, ValueError, OverflowError):
            continue
        if len(point) == dimension and all(map(math.isfinite, point)):
            points.append(point)
    return tuple(points)


def baseline_waves_complete(statistics: object) -> bool:
    if not isinstance(statistics, Mapping):
        return False
    return bool(
        statistics.get("all_discovered_primaries_served") is True
        and statistics.get("primary_wave_complete") is True
        and statistics.get("alternate_wave_complete") is True
        and statistics.get("restoration_wave_complete") is True
        and statistics.get("primary_deferred_unknown_count") == 0
        and statistics.get("deadline_backlog_unexamined_count") == 0
    )


def install_leftover_only(
    champion,
    *,
    proposal_factory: ProposalFactory,
    mechanism_hash: str,
    maximum_proposals: int = 32,
    maximum_generation_seconds: float = 2.0,
    source_replay_seconds: float = 0.5,
):
    """Patch only fresh replay capture, service sequencing, and dry metadata."""

    if maximum_proposals <= 0:
        raise ValueError("maximum_proposals must be positive")
    if not 0.0 < maximum_generation_seconds <= 2.0:
        raise ValueError("maximum_generation_seconds must be in (0, 2]")
    if source_replay_seconds <= 0.0:
        raise ValueError("source_replay_seconds must be positive")

    base = champion.BASE
    original_fresh = base._fresh_replay_candidates
    original_service = base._service_candidates
    original_plan = base._plan
    protected_names = (
        "_run_hp_candidate",
        "_run_restoration_candidate",
        "_authority_descriptor",
        "_descriptor_key",
    )
    protected = {name: getattr(base, name) for name in protected_names}
    state: dict[str, object] = {}
    audit: dict[str, object] = {}

    def fresh(document, endpoints, *, hard_deadline):
        # Baseline replay is called first with its exact original endpoint
        # sequence. No side proposal exists in any capped reservoir here.
        result = original_fresh(document, endpoints, hard_deadline=hard_deadline)
        state.clear()
        state.update(
            {
                "document": document,
                # Keep only references before baseline HP service. Validation,
                # float conversion, and proposal work are deferred until after
                # the baseline completion gate.
                "endpoints": endpoints,
            }
        )
        audit.clear()
        return result

    def service(**kwargs):
        baseline_result = original_service(**kwargs)
        attempts, descriptors, statistics = baseline_result
        raw_endpoints = state.get("endpoints")
        document = state.get("document")
        endpoint_count = len(raw_endpoints) if isinstance(raw_endpoints, Sequence) else 0
        audit.update(
            {
                "baseline_fresh_replay_called_first": True,
                "baseline_endpoint_count": endpoint_count,
                "baseline_endpoints_removed": 0,
                "baseline_endpoints_reordered": False,
                "side_proposals_in_baseline_reservoir": 0,
                "side_service_started": False,
                "local_candidate_authority": False,
            }
        )
        complete = baseline_waves_complete(statistics)
        audit["baseline_waves_complete"] = complete
        audit["baseline_attempt_count_before_side"] = len(attempts)
        audit["baseline_descriptor_count_before_side"] = len(descriptors)
        if not complete:
            audit["side_skip_reason"] = "BASELINE_WAVES_INCOMPLETE"
            return baseline_result

        variables = document.get("variables") if isinstance(document, Mapping) else None
        names = variables.get("names") if isinstance(variables, Mapping) else None
        dimension = len(names) if isinstance(names, list) else 0
        starts = (
            _finite_points(raw_endpoints, dimension)
            if isinstance(raw_endpoints, Sequence)
            else ()
        )
        if not isinstance(document, Mapping) or not starts:
            audit["side_skip_reason"] = "NO_FINITE_BASELINE_TEMPLATE"
            return baseline_result
        hard_deadline = float(kwargs["hard_deadline"])
        finalize_reserve = float(base.FINALIZE_RESERVE_SECONDS)
        minimum_hp = float(base.MIN_HP_ATTEMPT_SECONDS)
        remaining = hard_deadline - time.monotonic() - finalize_reserve
        generation_budget = min(
            maximum_generation_seconds,
            remaining - source_replay_seconds - minimum_hp,
        )
        if not math.isfinite(generation_budget) or generation_budget <= 0.26:
            audit["side_skip_reason"] = "NO_LEFTOVER_GENERATION_AND_HP_SLOT"
            return baseline_result

        try:
            proposals = proposal_factory(document, starts, generation_budget)
        except Exception as error:
            audit["side_skip_reason"] = f"PROPOSAL_FACTORY_FAILED:{type(error).__name__}"
            return baseline_result
        shaped: list[dict[str, object]] = []
        seen = set(starts)
        for raw in proposals:
            if len(shaped) >= maximum_proposals:
                break
            try:
                point = tuple(float(value) for value in raw)
            except (TypeError, ValueError, OverflowError):
                continue
            if (
                len(point) != len(starts[0])
                or not all(map(math.isfinite, point))
                or point in seen
            ):
                continue
            seen.add(point)
            shaped.append({"point": list(point)})
        audit["side_proposals_generated_after_baseline"] = len(shaped)
        if not shaped:
            audit["side_skip_reason"] = "NO_FINITE_NOVEL_PROPOSAL"
            return baseline_result

        remaining = hard_deadline - time.monotonic() - finalize_reserve
        if remaining <= source_replay_seconds + minimum_hp:
            audit["side_skip_reason"] = "NO_LEFTOVER_SOURCE_REPLAY_AND_HP_SLOT"
            return baseline_result
        replay_deadline = min(
            time.monotonic() + source_replay_seconds,
            hard_deadline - finalize_reserve - minimum_hp,
        )
        try:
            side_candidates = original_fresh(
                document,
                tuple(shaped),
                hard_deadline=replay_deadline,
            )
        except Exception as error:
            audit["side_skip_reason"] = f"SIDE_SOURCE_REPLAY_FAILED:{type(error).__name__}"
            return baseline_result
        backlog = getattr(side_candidates, "deadline_backlog", ())
        audit["side_source_replay_candidate_count"] = len(side_candidates)
        audit["side_source_replay_backlog_count"] = len(backlog)
        if not side_candidates:
            audit["side_skip_reason"] = "NO_SOURCE_REPLAYED_SIDE_CANDIDATE"
            return baseline_result

        side_kwargs = dict(kwargs)
        side_kwargs["candidates"] = side_candidates
        audit["side_service_started"] = True
        try:
            side_attempts, side_descriptors, side_statistics = original_service(**side_kwargs)
        except Exception as error:
            audit["side_skip_reason"] = f"SIDE_SERVICE_FAILED:{type(error).__name__}"
            audit["side_service_started"] = False
            return baseline_result
        combined_attempts = [*attempts, *side_attempts]
        combined_descriptors = dict(descriptors)
        for key, descriptor in side_descriptors.items():
            combined_descriptors.setdefault(key, descriptor)
        combined_statistics = dict(statistics)
        combined_statistics["leftover_only_side_lane"] = {
            "baseline_waves_complete_before_side": True,
            "baseline_attempt_count": len(attempts),
            "baseline_descriptor_count": len(descriptors),
            "side_attempt_count": len(side_attempts),
            "side_descriptor_count": len(side_descriptors),
            "side_statistics": dict(side_statistics),
        }
        audit["side_attempt_count"] = len(side_attempts)
        audit["side_descriptor_count"] = len(side_descriptors)
        return combined_attempts, combined_descriptors, combined_statistics

    def plan(**kwargs):
        value = original_plan(**kwargs)
        value.update(
            {
                "exp_struct_poly_001_v2": {
                    "mode": "LEFTOVER_ONLY_AFTER_IDENTICAL_BASELINE_WAVES",
                    "mechanism_hash": mechanism_hash,
                    "baseline_fresh_replay_first": True,
                    "side_proposals_in_baseline_reservoir": 0,
                    "baseline_completion_required": True,
                    "maximum_generation_seconds": maximum_generation_seconds,
                    "maximum_proposals": maximum_proposals,
                    "source_replay_seconds": source_replay_seconds,
                    "original_finalize_and_minimum_hp_reserves_retained": True,
                    "local_candidate_authority": False,
                    "source_guard_hp_exact_descriptor_authority": "ORIGINAL_CHAMPION",
                }
            }
        )
        return value

    base._fresh_replay_candidates = fresh
    base._service_candidates = service
    base._plan = plan
    if any(getattr(base, name) is not value for name, value in protected.items()):
        raise RuntimeError("original HP or exact descriptor authority changed")
    return lambda: dict(audit)
