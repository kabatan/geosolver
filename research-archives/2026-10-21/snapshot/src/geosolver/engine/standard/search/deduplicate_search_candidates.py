"""Deduplicate NOMAD candidates across runs."""

from __future__ import annotations

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate

from .coordinate_distance import normalized_distance


def _is_duplicate_candidate(
    *,
    candidate: FloatCandidate,
    selected: list[FloatCandidate],
    bounds: list[tuple[float, float]],
    dedup_distance_threshold: float,
) -> bool:
    return any(
        normalized_distance(first=candidate.x_float, second=existing.x_float, bounds=bounds)
        < dedup_distance_threshold
        for existing in selected
    )


def _select_seed_diverse_prefix(
    *,
    ordered: list[FloatCandidate],
    bounds: list[tuple[float, float]],
    keep_count: int,
    dedup_distance_threshold: float,
    min_per_seed: int,
) -> list[FloatCandidate]:
    if min_per_seed <= 0:
        return []
    by_seed: dict[int, list[FloatCandidate]] = {}
    for candidate in ordered:
        by_seed.setdefault(candidate.origin_seed, []).append(candidate)
    offsets = {seed: 0 for seed in by_seed}
    selected: list[FloatCandidate] = []
    for _round in range(int(min_per_seed)):
        for seed in sorted(by_seed):
            seed_candidates = by_seed[seed]
            index = offsets[seed]
            while index < len(seed_candidates):
                candidate = seed_candidates[index]
                index += 1
                if _is_duplicate_candidate(
                    candidate=candidate,
                    selected=selected,
                    bounds=bounds,
                    dedup_distance_threshold=dedup_distance_threshold,
                ):
                    continue
                selected.append(candidate)
                break
            offsets[seed] = index
            if len(selected) >= keep_count:
                return selected
    return selected


def deduplicate_search_candidates(
    *,
    candidates: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    keep_count: int,
    dedup_distance_threshold: float,
    min_per_seed: int = 0,
) -> tuple[FloatCandidate, ...]:
    """Legacy compact-only path: score-sort then remove near-duplicate points."""
    ordered = sorted(candidates, key=lambda candidate: candidate.score)
    selected = _select_seed_diverse_prefix(
        ordered=ordered,
        bounds=bounds,
        keep_count=keep_count,
        dedup_distance_threshold=dedup_distance_threshold,
        min_per_seed=min_per_seed,
    )
    if len(selected) >= keep_count:
        return tuple(selected[:keep_count])
    selected_set = set(selected)
    for candidate in ordered:
        if candidate in selected_set:
            continue
        if _is_duplicate_candidate(
            candidate=candidate,
            selected=selected,
            bounds=bounds,
            dedup_distance_threshold=dedup_distance_threshold,
        ):
            continue
        selected.append(candidate)
        selected_set.add(candidate)
        if len(selected) >= keep_count:
            break
    return tuple(selected)
