"""NOMAD blackbox callback adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.search_point import evaluate_search_point
from geosolver.runtime.deadline import deadline_scope, expired

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
    namespace: int = _NOMAD_CANDIDATE_NAMESPACE,
) -> int:
    return (
        int(namespace)
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
    candidate_namespace: int = _NOMAD_CANDIDATE_NAMESPACE
    origin_phase: str = "search"
    origin_backend: str = "nomad"
    origin_attempt: int | None = None
    origin_box_index: int | None = None
    records: list[FloatCandidate] = field(default_factory=list)
    evaluation_count: int = 0
    failure_count: int = 0
    deadline_reached: bool = False
    deadline_monotonic: float | None = None

    def __call__(self, point: NomadPointLike) -> int:
        with deadline_scope(self.deadline_monotonic):
            try:
                return self._evaluate(point)
            except TimeoutError:
                self.deadline_reached = True
                return 0

    def _evaluate(self, point: NomadPointLike) -> int:
        if expired(self.deadline_monotonic):
            self.deadline_reached = True
            return 0
        coords = [float(point.get_coord(index)) for index in range(point.size())]
        self.evaluation_count += 1
        candidate_id = _candidate_id(
            origin_seed=self.origin_seed,
            origin_start_point_index=self.origin_start_point_index,
            evaluation_count=self.evaluation_count,
            namespace=self.candidate_namespace,
        )
        float_eval = self.evaluator.evaluate_float_residual(coords)
        if expired(self.deadline_monotonic):
            self.deadline_reached = True
            return 0
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
                    origin_phase=self.origin_phase,
                    origin_backend=self.origin_backend,
                    origin_attempt=self.origin_attempt,
                    origin_box_index=self.origin_box_index,
                    origin_evaluation_index=self.evaluation_count,
                )
            )
            return 0
        evaluation = evaluate_search_point(
            evaluator=self.evaluator, values=coords, residual=float_eval
        )
        hard_snapshot, guard_ok = evaluation.hard, evaluation.guard_ok
        if expired(self.deadline_monotonic):
            self.deadline_reached = True
            return 0
        penalty = 0.0 if hard_snapshot.hard_feasible else self.config.guard_penalty
        if self.constraint_scales is not None:
            scaled = [
                residual / scale
                for residual, scale in zip(
                    float_eval.residual_vector,
                    self.constraint_scales,
                    strict=False,
                )
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
                origin_phase=self.origin_phase,
                origin_backend=self.origin_backend,
                origin_attempt=self.origin_attempt,
                origin_box_index=self.origin_box_index,
                origin_evaluation_index=self.evaluation_count,
            )
        )
        return 1
