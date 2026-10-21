from __future__ import annotations

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.search.build_guard_feasible_ledger import (
    build_guard_feasible_ledger,
)
from geosolver.engine.standard.search.coordinate_distance import normalized_distance


def _candidate(index: int, *, x: tuple[float, float] | None = None) -> FloatCandidate:
    point = x if x is not None else ((index * 0.37) % 1.0, (index * 0.61) % 1.0)
    return FloatCandidate(
        x_float=point,
        score=float(index % 5),
        residual_norm_float=float(index % 5),
        guard_ok=True,
        evaluation_status=EvaluationStatus.OK,
        origin_seed=index % 3,
        origin_start_point_index=index,
        candidate_id=index,
        hard_feasible=True,
        origin_backend="fixture",
        origin_evaluation_index=index,
    )


def _reference_prefix(
    records: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    count: int,
) -> tuple[FloatCandidate, ...]:
    ordered = sorted(records, key=lambda item: (item.score, item.candidate_id))
    selected = [ordered[0]]
    remaining = list(ordered[1:])
    while remaining and len(selected) < count:
        keys = [
            (
                min(
                    normalized_distance(
                        first=candidate.x_float,
                        second=chosen.x_float,
                        bounds=bounds,
                    )
                    for chosen in selected
                ),
                -candidate.score,
                -candidate.candidate_id,
            )
            for candidate in remaining
        ]
        index = max(range(len(keys)), key=keys.__getitem__)
        selected.append(remaining.pop(index))
    return tuple(selected)


def test_incremental_farthest_ledger_preserves_reference_order() -> None:
    records = tuple(_candidate(index) for index in range(25))
    bounds = [(0.0, 1.0), (0.0, 1.0)]

    _compact, ledger = build_guard_feasible_ledger(
        all_records=records,
        bounds=bounds,
        compact_keep_count=7,
        prefix_count=18,
    )

    assert ledger == _reference_prefix(records, bounds, 18)
