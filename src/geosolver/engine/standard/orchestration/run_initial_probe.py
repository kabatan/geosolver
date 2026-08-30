"""Phase 0 random probe for start-point generation."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.problem.load_problem_bundle import ProblemBundle
from geosolver.engine.standard.search.nomad_config import (
    GUARD_PENALTY_DEFAULT,
    derive_seed_values,
)
from geosolver.engine.standard.search.sampling import augment_with_manifold_samples
from geosolver.runtime.deadline import timed_phase, uses_deadline

PHASE0_SEEDS = (0, 1, 2, 3, 4)
PHASE0_POINTS_PER_SEED_DEFAULT = 50


def derive_initial_probe_seeds(
    external_seed: int,
    *,
    count: int = len(PHASE0_SEEDS),
) -> tuple[int, ...]:
    """Derive phase-0 probe seeds from an authoritative external seed."""
    return derive_seed_values(external_seed, count=count)


@dataclass(frozen=True)
class InitialProbeResult:
    """Phase 0 probe output."""

    candidates: tuple[FloatCandidate, ...]
    metrics: dict[str, object]
    constraint_scales: tuple[float, ...] | None = None


def augment_initial_probe_with_exact_distance_samples(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    initial_probe_result: InitialProbeResult,
) -> InitialProbeResult:
    """Add structure-aware samples while preserving Phase 0 constraint scales."""

    candidates, metrics = augment_with_manifold_samples(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        candidates=initial_probe_result.candidates,
        metrics=dict(initial_probe_result.metrics),
    )
    return InitialProbeResult(
        candidates=candidates,
        metrics=metrics,
        constraint_scales=initial_probe_result.constraint_scales,
    )


_CONSTRAINT_SCALE_MIN = 1e-12
_CONSTRAINT_SCALE_RATIO_THRESHOLD = 10.0


def _compute_constraint_scales(
    per_constraint_abs: list[list[float]],
) -> tuple[float, ...] | None:
    """Compute per-constraint scale factors from sampled absolute residuals.

    Returns None if constraints are already well-balanced (max/min ratio < threshold).
    Uses geometric mean as floor to avoid amplifying naturally-small constraints.
    """
    if not per_constraint_abs:
        return None
    raw_medians: list[float] = []
    for vals in per_constraint_abs:
        if not vals:
            raw_medians.append(0.0)
            continue
        vals_sorted = sorted(vals)
        raw_medians.append(vals_sorted[len(vals_sorted) // 2])
    positive = [m for m in raw_medians if m > _CONSTRAINT_SCALE_MIN]
    if len(positive) < 2:
        return None
    max_pos = max(positive)
    min_pos = min(positive)
    if max_pos / min_pos < _CONSTRAINT_SCALE_RATIO_THRESHOLD:
        return None
    geo_mean = math.exp(sum(math.log(m) for m in positive) / len(positive))
    scales = tuple(max(m, geo_mean) for m in raw_medians)
    return scales


@timed_phase("initial_probe")
@uses_deadline
def run_initial_probe(
    *,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    points_per_seed: int = PHASE0_POINTS_PER_SEED_DEFAULT,
    seeds: tuple[int, ...] = PHASE0_SEEDS,
) -> InitialProbeResult:
    """Generate random probe points and keep finite candidates."""
    total_points = 0
    finite_points = 0
    guard_pass_points = 0
    records: list[FloatCandidate] = []
    best_point: tuple[float, ...] | None = None
    best_residual = float("inf")
    per_constraint_abs: list[list[float]] = []
    residual_vectors = []
    for seed in seeds:
        rng = random.Random(int(seed))
        for point_index in range(int(points_per_seed)):
            from geosolver.runtime.deadline import expired

            if expired():
                break
            point = [rng.uniform(low, high) for low, high in bounds]
            total_points += 1
            float_eval = evaluator.evaluate_float_residual(point)
            if float_eval.evaluation_status is not EvaluationStatus.OK:
                continue
            finite_points += 1
            if float_eval.residual_vector:
                if not per_constraint_abs:
                    per_constraint_abs = [[] for _ in range(len(float_eval.residual_vector))]
                for i, r in enumerate(float_eval.residual_vector):
                    if math.isfinite(r):
                        per_constraint_abs[i].append(abs(r))
            guard_ok, _violations = evaluator.evaluate_guard(point)
            if guard_ok:
                guard_pass_points += 1
            residual = float_eval.residual_norm_float
            if residual < best_residual:
                best_residual = residual
                best_point = tuple(point)
            score = (residual * residual) + (0.0 if guard_ok else GUARD_PENALTY_DEFAULT)
            records.append(
                FloatCandidate(
                    x_float=tuple(point),
                    score=score,
                    residual_norm_float=residual,
                    guard_ok=guard_ok,
                    evaluation_status=float_eval.evaluation_status,
                    origin_seed=int(seed),
                    origin_start_point_index=int(point_index),
                    candidate_id=int(total_points),
                    hard_feasible=bool(guard_ok),
                    hard_violation_tags=() if guard_ok else ("guard_failed",),
                    validity_margin_float=None,
                )
            )
            residual_vectors.append(tuple(float_eval.residual_vector))
    constraint_scales = _compute_constraint_scales(per_constraint_abs)
    from dataclasses import replace

    from geosolver.engine.standard.evaluation.scaled_score import scaled_score

    records = [
        replace(
            record,
            score=scaled_score(residuals, constraint_scales)
            + (0.0 if record.guard_ok else GUARD_PENALTY_DEFAULT),
        )
        for record, residuals in zip(records, residual_vectors, strict=True)
    ]
    metrics = {
        "total_random_points": total_points,
        "finite_residual_ratio": 0.0 if total_points == 0 else (finite_points / total_points),
        "guard_pass_ratio": 0.0 if total_points == 0 else (guard_pass_points / total_points),
        "best_random_residual": None if best_point is None else best_residual,
        "best_random_point": best_point,
        "constraint_scales": constraint_scales,
    }
    return InitialProbeResult(
        candidates=tuple(records),
        metrics=metrics,
        constraint_scales=constraint_scales,
    )
