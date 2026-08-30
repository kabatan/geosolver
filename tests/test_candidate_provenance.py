from __future__ import annotations

from dataclasses import replace

import pytest

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    assert_candidate_id_consistency,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus


def _candidate(index: int, *, x: tuple[float, float]) -> FloatCandidate:
    return FloatCandidate(
        x_float=x,
        score=0.0,
        residual_norm_float=0.0,
        guard_ok=True,
        evaluation_status=EvaluationStatus.OK,
        origin_seed=0,
        origin_start_point_index=index,
        candidate_id=index,
        hard_feasible=True,
        origin_backend="fixture",
        origin_evaluation_index=index,
    )


def test_candidate_identity_collision_is_not_silently_merged() -> None:
    first = _candidate(7, x=(0.1, 0.2))
    second = replace(first, x_float=(0.8, 0.9), origin_phase="rescue")

    with pytest.raises(RuntimeError, match="candidate ID collision"):
        assert_candidate_id_consistency((first, second))


def test_candidate_uid_contains_full_provenance() -> None:
    candidate = replace(
        _candidate(3, x=(0.2, 0.4)),
        origin_phase="rescue",
        origin_backend="nomad",
        origin_attempt=2,
        origin_box_index=4,
        origin_evaluation_index=11,
    )

    assert candidate.candidate_uid == "rescue/nomad/2/4/0/3/11"
