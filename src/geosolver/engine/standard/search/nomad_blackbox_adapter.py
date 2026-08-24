"""NOMAD blackbox callback adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus

from .nomad_config import NomadConfig

NON_FINITE_SCORE_PENALTY = 1e30
_NOMAD_CANDIDATE_NAMESPACE = 9_000_000_000_000
_SEED_CANDIDATE_MULTIPLIER = 100_000_000
_START_POINT_CANDIDATE_MULTIPLIER = 1_000_000


def _candidate_id(
    *,
    origin_seed: int,
    origin_start_point_index: int,
    evaluation_count: int,
) -> int:
    return (
        _NOMAD_CANDIDATE_NAMESPACE
        + int(origin_seed) * _SEED_CANDIDATE_MULTIPLIER
        + int(origin_start_point_index) * _START_POINT_CANDIDATE_MULTIPLIER
        + int(evaluation_count)
    )


class NomadPointLike(Protocol):
    """Minimal PyNomad point protocol used by the adapter."""

    def size(self) -> int:
        """Return point dimension."""

    def get_coord(self, index: int) -> float:
        """Return coordinate value."""

    def setBBO(self, payload: bytes) -> None:
        """Set objective payload."""


@dataclass
class NomadBlackboxAdapter:
    """Adapter from evaluator API to PyNomad callback contract."""

    evaluator: EvaluatorPort
    config: NomadConfig
    origin_seed: int
    origin_start_point_index: int
    constraint_scales: tuple[float, ...] | None = None
    records: list[FloatCandidate] = field(default_factory=list)
    evaluation_count: int = 0
    failure_count: int = 0

    def __call__(self, point: NomadPointLike) -> int:
        coords = [float(point.get_coord(index)) for index in range(point.size())]
        self.evaluation_count += 1
        candidate_id = _candidate_id(
            origin_seed=self.origin_seed,
            origin_start_point_index=self.origin_start_point_index,
            evaluation_count=self.evaluation_count,
        )
        float_eval = self.evaluator.evaluate_float_residual(coords)
        if float_eval.evaluation_status is not EvaluationStatus.OK:
            self.failure_count += 1
            self.records.append(
                FloatCandidate(
                    x_float=tuple(coords),
                    score=self.config.guard_penalty + NON_FINITE_SCORE_PENALTY,
                    residual_norm_float=float("inf"),
                    guard_ok=False,
                    evaluation_status=float_eval.evaluation_status,
                    origin_seed=self.origin_seed,
                    origin_start_point_index=self.origin_start_point_index,
                    candidate_id=candidate_id,
                    hard_feasible=False,
                    hard_violation_tags=(f"eval_status:{float_eval.evaluation_status.value}",),
                    validity_margin_float=None,
                )
            )
            return 0
        hard_snapshot = self.evaluator.evaluate_float_hard_feasibility(
            coords,
            include_margins=False,
        )
        guard_ok, _violations = self.evaluator.evaluate_guard(coords)
        penalty = 0.0 if hard_snapshot.hard_feasible else self.config.guard_penalty
        if self.constraint_scales is not None:
            scaled = [
                r / s
                for r, s in zip(float_eval.residual_vector, self.constraint_scales)
            ]
            scaled_norm_sq = sum(r * r for r in scaled)
        else:
            scaled_norm_sq = float_eval.residual_norm_float * float_eval.residual_norm_float
        score = scaled_norm_sq + penalty
        point.setBBO(str(score).encode("utf-8"))
        validity_margin_float = None
        if hard_snapshot.min_margin is not None and mp.isfinite(hard_snapshot.min_margin):
            validity_margin_float = float(hard_snapshot.min_margin)
        self.records.append(
            FloatCandidate(
                x_float=tuple(coords),
                score=score,
                residual_norm_float=float_eval.residual_norm_float,
                guard_ok=guard_ok,
                evaluation_status=float_eval.evaluation_status,
                origin_seed=self.origin_seed,
                origin_start_point_index=self.origin_start_point_index,
                candidate_id=candidate_id,
                hard_feasible=hard_snapshot.hard_feasible,
                hard_violation_tags=tuple(hard_snapshot.failure_tags),
                validity_margin_float=validity_margin_float,
            )
        )
        return 1

