"""Build wide guard-feasible ledger and compact representatives."""

from __future__ import annotations

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus


def _normalized_distance(
    *,
    first: tuple[float, ...],
    second: tuple[float, ...],
    bounds: list[tuple[float, float]],
) -> float:
    total = 0.0
    for index, (low, high) in enumerate(bounds):
        width = max(high - low, 1e-12)
        diff = (first[index] - second[index]) / width
        total += diff * diff
    return total ** 0.5


def _guard_feasible_prefix_count(*, total_count: int, prefix_count: int) -> int:
    if total_count <= 0:
        return 0
    return max(1, min(int(prefix_count), int(total_count)))


def _select_guard_feasible_prefix(
    *,
    all_records: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    prefix_count: int,
) -> tuple[FloatCandidate, ...]:
    """Select a score-anchored but basin-diverse guard-feasible prefix.

    The first entry remains the best-scoring feasible candidate.  Additional
    entries are chosen by farthest-point traversal over normalized coordinates,
    so the prefix behaves like a small coverage ledger rather than a pure
    residual ranking that can collapse onto one basin.
    """

    guard_feasible = [
        candidate
        for candidate in all_records
        if (
            candidate.evaluation_status is EvaluationStatus.OK
            and candidate.guard_ok
            and candidate.hard_feasible
        )
    ]
    ordered = sorted(guard_feasible, key=lambda item: (item.score, item.candidate_id))
    keep_count = _guard_feasible_prefix_count(
        total_count=len(ordered),
        prefix_count=prefix_count,
    )
    if keep_count <= 0:
        return ()
    selected: list[FloatCandidate] = [ordered[0]]
    remaining = list(ordered[1:])
    while remaining and len(selected) < keep_count:
        best_index = 0
        best_key: tuple[float, float, int] | None = None
        for index, candidate in enumerate(remaining):
            min_distance = min(
                _normalized_distance(
                    first=candidate.x_float,
                    second=chosen.x_float,
                    bounds=bounds,
                )
                for chosen in selected
            )
            key = (min_distance, -float(candidate.score), -int(candidate.candidate_id))
            if best_key is None or key > best_key:
                best_key = key
                best_index = index
        selected.append(remaining.pop(best_index))
    return tuple(selected)


def _select_farthest_point_representatives(
    *,
    prefix: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    compact_keep_count: int,
) -> tuple[FloatCandidate, ...]:
    if not prefix or compact_keep_count <= 0:
        return ()
    representatives: list[FloatCandidate] = [prefix[0]]
    remaining = list(prefix[1:])
    while remaining and len(representatives) < int(compact_keep_count):
        best_index = 0
        best_distance = -1.0
        for index, candidate in enumerate(remaining):
            min_distance = min(
                _normalized_distance(
                    first=candidate.x_float,
                    second=selected.x_float,
                    bounds=bounds,
                )
                for selected in representatives
            )
            if min_distance > best_distance:
                best_distance = min_distance
                best_index = index
        representatives.append(remaining.pop(best_index))
    representatives.sort(key=lambda item: item.score)
    return tuple(representatives[: max(0, int(compact_keep_count))])


def build_guard_feasible_ledger(
    *,
    all_records: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    compact_keep_count: int,
    prefix_count: int,
) -> tuple[tuple[FloatCandidate, ...], tuple[FloatCandidate, ...]]:
    """Build compact representatives and wide guard-feasible ledger."""
    prefix = _select_guard_feasible_prefix(
        all_records=all_records,
        bounds=bounds,
        prefix_count=prefix_count,
    )
    representatives = _select_farthest_point_representatives(
        prefix=prefix,
        bounds=bounds,
        compact_keep_count=compact_keep_count,
    )
    return representatives, prefix
