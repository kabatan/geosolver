"""Integer target handling as a general discrete-constraint strategy.

This module keeps finite enumeration logic out of orchestration.  The trigger is
not a benchmark case or a failure signature; it is the presence of explicit
integer-valued constraints compiled from the problem bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import time

from mpmath import mp

from geosolver._internal.pipeline.contracts.candidate_record import (
    FloatCandidate,
    RefinementBatchResult,
    RefinedCandidate,
    SearchBatchResult,
)
from geosolver._internal.pipeline.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver._internal.pipeline.contracts.runtime_budget import RuntimeBudget
from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import EvaluationStatus
from geosolver._internal.pipeline.problem.infer_problem_bounds import infer_problem_bounds
from geosolver._internal.pipeline.refine.mpmath_refiner import (
    MpmathRefiner,
    build_integer_constraint_specs,
    evaluate_integer_constraint_values,
)
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


DISCRETE_TARGET_STRATEGY_ID = "discrete.integer_target_enumeration"


@dataclass(frozen=True)
class IntegerTargetObservation:
    """Observed integer-target values paired with a refinement start.

    Instances are derived from guard-feasible candidates, not from problem IDs or
    expected answers.
    """

    source_candidate: FloatCandidate
    target_values: tuple[MPFloat, ...]
    start_point: tuple[MPFloat, ...] | None = None


def default_discrete_completion_summary(
    *,
    runtime_budget: RuntimeBudget,
    skip_reason: str,
    tuple_cap: int = 0,
    elapsed_sec: float = 0.0,
) -> dict[str, object]:
    return {
        "strategy_id": DISCRETE_TARGET_STRATEGY_ID,
        "completion_type": "discrete_target_enumeration",
        "triggered": False,
        "skip_reason": skip_reason,
        "constraint_count": 0,
        "target_intervals": [],
        "tuple_cap": int(tuple_cap),
        "tuple_count": 0,
        "attempted_tuple_count": 0,
        "completed_enumeration": False,
        "best_residual": "inf",
        "accepted_count": 0,
        "solved_tuples": [],
        "elapsed_sec": float(elapsed_sec),
        "remaining_budget_sec": runtime_budget.remaining_sec(),
    }


def _build_integer_target_observations(
    *,
    bundle: object,
    observation_candidates: tuple[FloatCandidate, ...],
    dps: int,
) -> tuple[object, tuple[IntegerTargetObservation, ...]]:
    specs = build_integer_constraint_specs(bundle=bundle)
    observations: list[IntegerTargetObservation] = []
    for candidate in observation_candidates:
        point = [
            boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
            for value in candidate.x_float
        ]
        values = evaluate_integer_constraint_values(
            bundle=bundle,
            point=point,
            specs=specs,
            dps=int(dps),
        )
        if values is None or len(values) != len(specs):
            continue
        observations.append(
            IntegerTargetObservation(
                source_candidate=candidate,
                target_values=tuple(values),
            )
        )
    return specs, tuple(observations)


def _integer_observation_candidates(
    *,
    search_result: SearchBatchResult,
) -> tuple[FloatCandidate, ...]:
    observation_candidates: list[FloatCandidate] = []
    seen_candidate_ids: set[int] = set()
    for candidate in tuple(search_result.candidates) + tuple(search_result.guard_feasible_ledger):
        candidate_id = int(candidate.candidate_id)
        if candidate_id in seen_candidate_ids:
            continue
        if (
            candidate.evaluation_status is not EvaluationStatus.OK
            or not candidate.guard_ok
            or not candidate.hard_feasible
        ):
            continue
        seen_candidate_ids.add(candidate_id)
        observation_candidates.append(candidate)
    return tuple(observation_candidates)


def _derive_integer_target_intervals(
    *,
    observations: tuple[IntegerTargetObservation, ...],
) -> tuple[tuple[int, int], ...]:
    if not observations:
        return ()
    value_count = len(observations[0].target_values)
    intervals: list[tuple[int, int]] = []
    for index in range(value_count):
        axis_values = [observation.target_values[index] for observation in observations]
        lower = int(mp.floor(min(axis_values)))
        upper = int(mp.ceil(max(axis_values)))
        intervals.append((lower, upper))
    return tuple(intervals)


def _integer_tuple_product(intervals: tuple[tuple[int, int], ...]) -> int:
    product_size = 1
    for lower, upper in intervals:
        product_size *= max(0, int(upper) - int(lower) + 1)
    return int(product_size)


def _nearest_integer_target_source(
    *,
    target_tuple: tuple[MPFloat, ...],
    observations: tuple[IntegerTargetObservation, ...],
) -> IntegerTargetObservation:
    best_observation = observations[0]
    best_candidate = best_observation.source_candidate
    best_distance = mp.inf
    best_score = float(best_candidate.score)
    best_id = int(best_candidate.candidate_id)
    for observation in observations:
        candidate = observation.source_candidate
        distance = mp.fsum(
            abs(value - target)
            for value, target in zip(
                observation.target_values,
                target_tuple,
                strict=True,
            )
        )
        candidate_score = float(candidate.score)
        candidate_id = int(candidate.candidate_id)
        if (
            distance < best_distance
            or (
                distance == best_distance
                and (candidate_score, candidate_id) < (best_score, best_id)
            )
        ):
            best_observation = observation
            best_candidate = candidate
            best_distance = distance
            best_score = candidate_score
            best_id = candidate_id
    return best_observation


def _fallback_axis_bounds(
    observation_candidates: tuple[FloatCandidate, ...],
    axis_index: int,
) -> tuple[MPFloat, MPFloat] | None:
    axis_values = [
        boundary_float_to_mpf(
            candidate.x_float[axis_index],
            origin=BoundaryOrigin.INITIAL_POINT,
        )
        for candidate in observation_candidates
        if axis_index < len(candidate.x_float)
    ]
    if not axis_values:
        return None
    return min(axis_values), max(axis_values)


def _resolved_projection_bounds(
    *,
    bundle: object,
    observation_candidates: tuple[FloatCandidate, ...],
) -> tuple[tuple[MPFloat, MPFloat], ...]:
    raw_bounds = infer_problem_bounds(bundle)
    resolved: list[tuple[MPFloat, MPFloat]] = []
    for axis_index, (lower, upper) in enumerate(raw_bounds):
        fallback = _fallback_axis_bounds(observation_candidates, axis_index)
        resolved_lower = (
            boundary_float_to_mpf(lower, origin=BoundaryOrigin.LEGACY_BOUND)
            if lower is not None
            else (fallback[0] if fallback is not None else mp.mpf("0"))
        )
        resolved_upper = (
            boundary_float_to_mpf(upper, origin=BoundaryOrigin.LEGACY_BOUND)
            if upper is not None
            else (fallback[1] if fallback is not None else resolved_lower)
        )
        if resolved_lower > resolved_upper:
            resolved_lower, resolved_upper = resolved_upper, resolved_lower
        resolved.append((resolved_lower, resolved_upper))
    return tuple(resolved)


def _projection_sample_limit(
    *,
    bounds: tuple[tuple[MPFloat, MPFloat], ...],
    tuple_cap: int,
) -> int:
    if not bounds:
        return 0
    return max(1, min(int(tuple_cap), 1 + (2 ** min(len(bounds), 4))))


def _bound_projection_samples(
    *,
    bounds: tuple[tuple[MPFloat, MPFloat], ...],
    point_cap: int,
) -> tuple[tuple[MPFloat, ...], ...]:
    if point_cap <= 0 or not bounds:
        return ()
    midpoint = tuple(
        (lower + upper) / mp.mpf("2")
        for lower, upper in bounds
    )
    samples: list[tuple[MPFloat, ...]] = [midpoint]
    for corner in product(*(((lower, upper) for lower, upper in bounds))):
        samples.append(tuple(mp.mpf(value) for value in corner))
        if len(samples) >= int(point_cap):
            break
    unique_samples: list[tuple[MPFloat, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for sample in samples:
        key = tuple(str(value) for value in sample)
        if key in seen:
            continue
        seen.add(key)
        unique_samples.append(sample)
    return tuple(unique_samples)


def _nearest_projection_source_candidate(
    *,
    point: tuple[MPFloat, ...],
    observation_candidates: tuple[FloatCandidate, ...],
) -> FloatCandidate:
    best_candidate = observation_candidates[0]
    best_distance = mp.inf
    best_score = float(best_candidate.score)
    best_id = int(best_candidate.candidate_id)
    for candidate in observation_candidates:
        candidate_point = [
            boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
            for value in candidate.x_float
        ]
        distance = mp.fsum(
            abs(value - target)
            for value, target in zip(candidate_point, point, strict=True)
        )
        candidate_score = float(candidate.score)
        candidate_id = int(candidate.candidate_id)
        if (
            distance < best_distance
            or (
                distance == best_distance
                and (candidate_score, candidate_id) < (best_score, best_id)
            )
        ):
            best_candidate = candidate
            best_distance = distance
            best_score = candidate_score
            best_id = candidate_id
    return best_candidate


def _observation_expands_intervals(
    *,
    observation: IntegerTargetObservation,
    intervals: tuple[tuple[int, int], ...],
) -> bool:
    if not intervals:
        return True
    return any(
        value < lower or value > upper
        for value, (lower, upper) in zip(
            observation.target_values,
            intervals,
            strict=True,
        )
    )


def _augment_integer_target_observations(
    *,
    bundle: object,
    evaluator: object,
    observation_candidates: tuple[FloatCandidate, ...],
    observations: tuple[IntegerTargetObservation, ...],
    refiner: MpmathRefiner,
    dps: int,
    tuple_cap: int,
) -> tuple[IntegerTargetObservation, ...]:
    if (
        not observation_candidates
        or not observations
        or tuple_cap <= 0
        or not hasattr(refiner, "project_point_to_noninteger_constraint_manifold")
    ):
        return observations
    intervals = _derive_integer_target_intervals(observations=observations)
    try:
        bounds = _resolved_projection_bounds(
            bundle=bundle,
            observation_candidates=observation_candidates,
        )
    except AttributeError:
        return observations
    sample_points = _bound_projection_samples(
        bounds=bounds,
        point_cap=_projection_sample_limit(
            bounds=bounds,
            tuple_cap=tuple_cap,
        ),
    )
    augmented = tuple(observations)
    for sample_point in sample_points:
        projected = refiner.project_point_to_noninteger_constraint_manifold(
            bundle=bundle,
            evaluator=evaluator,
            start_point=sample_point,
            dps=int(dps),
        )
        if projected is None:
            continue
        observation = IntegerTargetObservation(
            source_candidate=_nearest_projection_source_candidate(
                point=projected.point,
                observation_candidates=observation_candidates,
            ),
            target_values=tuple(projected.integer_values),
            start_point=tuple(projected.point),
        )
        if not _observation_expands_intervals(
            observation=observation,
            intervals=intervals,
        ):
            continue
        candidate_observations = augmented + (observation,)
        candidate_intervals = _derive_integer_target_intervals(
            observations=candidate_observations,
        )
        if _integer_tuple_product(candidate_intervals) > int(tuple_cap):
            continue
        augmented = candidate_observations
        intervals = candidate_intervals
    return augmented


def _best_refined_starts_by_source_id(
    refined_candidates: tuple[RefinedCandidate, ...],
) -> dict[int, tuple[MPFloat, ...]]:
    best: dict[int, tuple[MPFloat, tuple[MPFloat, ...]]] = {}
    for candidate in refined_candidates:
        source = candidate.source
        if source is None:
            continue
        source_id = int(source.candidate_id)
        existing = best.get(source_id)
        if existing is None or candidate.residual_norm_hp < existing[0]:
            best[source_id] = (
                candidate.residual_norm_hp,
                tuple(candidate.x_hp),
            )
    return {source_id: point for source_id, (_, point) in best.items()}


def _merge_refinement_results(
    *,
    refinement_result: RefinementBatchResult,
    fallback_candidates: tuple[RefinedCandidate, ...],
) -> RefinementBatchResult:
    merged_candidates = tuple(refinement_result.candidates) + tuple(fallback_candidates)
    return RefinementBatchResult(
        candidates=merged_candidates,
        converged_count=sum(
            1
            for candidate in merged_candidates
            if candidate.refinement_status == "target_reached"
        ),
        attempted_count=refinement_result.attempted_count + len(fallback_candidates),
        solver_name=refinement_result.solver_name,
        hard_feasible_count=sum(1 for candidate in merged_candidates if candidate.hard_feasible),
        attempted_box_count=refinement_result.attempted_box_count,
    )


def run_discrete_target_completion(
    *,
    bundle: object,
    evaluator: object,
    search_result: SearchBatchResult,
    refinement_result: RefinementBatchResult,
    phasec_result: object,
    refiner: MpmathRefiner | None,
    runtime_budget: RuntimeBudget,
    pipeline_config: ExternalPipelineConfig,
) -> tuple[RefinementBatchResult, object, dict[str, object]]:
    # Lazily import to avoid making the orchestration package depend on itself
    # while still sharing Phase C acceptance policy.
    from geosolver._internal.pipeline.orchestration.run_phasec_assembly import run_phasec_assembly

    if phasec_result.accepted_candidates:
        return (
            refinement_result,
            phasec_result,
            default_discrete_completion_summary(
                runtime_budget=runtime_budget,
                skip_reason="phasec_already_accepted",
            ),
        )
    if refiner is None:
        return (
            refinement_result,
            phasec_result,
            default_discrete_completion_summary(
                runtime_budget=runtime_budget,
                skip_reason="box_solver_path",
            ),
        )
    if runtime_budget.remaining_sec() <= 0.0:
        return (
            refinement_result,
            phasec_result,
            default_discrete_completion_summary(
                runtime_budget=runtime_budget,
                skip_reason="runtime_exhausted",
            ),
        )
    fallback_started_at = time.monotonic()
    dps = int(max(refiner.config.schedule_dps))
    observation_candidates = _integer_observation_candidates(search_result=search_result)
    specs, observations = _build_integer_target_observations(
        bundle=bundle,
        observation_candidates=observation_candidates,
        dps=dps,
    )
    if not specs:
        return (
            refinement_result,
            phasec_result,
            default_discrete_completion_summary(
                runtime_budget=runtime_budget,
                skip_reason="integer_constraint_count_lt_1",
                elapsed_sec=time.monotonic() - fallback_started_at,
            ),
        )
    if not observations:
        return (
            refinement_result,
            phasec_result,
            default_discrete_completion_summary(
                runtime_budget=runtime_budget,
                skip_reason="no_guard_feasible_integer_observations",
                elapsed_sec=time.monotonic() - fallback_started_at,
            ),
        )
    tuple_cap = int(pipeline_config.discrete_target_completion_max_tuples)
    observations = _augment_integer_target_observations(
        bundle=bundle,
        evaluator=evaluator,
        observation_candidates=observation_candidates,
        observations=observations,
        refiner=refiner,
        dps=dps,
        tuple_cap=tuple_cap,
    )
    intervals = _derive_integer_target_intervals(observations=observations)
    tuple_count = _integer_tuple_product(intervals)
    if tuple_count <= 0 or tuple_count > tuple_cap:
        summary = default_discrete_completion_summary(
            runtime_budget=runtime_budget,
            skip_reason="tuple_product_exceeds_cap",
            tuple_cap=tuple_cap,
            elapsed_sec=time.monotonic() - fallback_started_at,
        )
        summary["constraint_count"] = len(specs)
        summary["target_intervals"] = [list(interval) for interval in intervals]
        summary["tuple_count"] = tuple_count
        return refinement_result, phasec_result, summary
    refined_starts_by_source_id = _best_refined_starts_by_source_id(refinement_result.candidates)
    fallback_candidates: list[RefinedCandidate] = []
    fallback_candidate_targets: dict[int, tuple[int, ...]] = {}
    attempted_tuple_count = 0
    completed_enumeration = True
    best_residual = mp.inf
    for raw_tuple in product(
        *(
            range(int(lower), int(upper) + 1)
            for lower, upper in intervals
        )
    ):
        if runtime_budget.remaining_sec() <= 0.0:
            completed_enumeration = False
            break
        attempted_tuple_count += 1
        target_tuple = tuple(mp.mpf(value) for value in raw_tuple)
        source_observation = _nearest_integer_target_source(
            target_tuple=target_tuple,
            observations=observations,
        )
        source_candidate = source_observation.source_candidate
        start_point = source_observation.start_point
        if start_point is None:
            start_point = refined_starts_by_source_id.get(int(source_candidate.candidate_id))
        refined_candidate = refiner.refine_candidate_with_integer_targets(
            bundle=bundle,
            evaluator=evaluator,
            candidate=source_candidate,
            target_integers=target_tuple,
            start_point=start_point,
        )
        if refined_candidate is None:
            continue
        fallback_candidates.append(refined_candidate)
        fallback_candidate_targets[int(refined_candidate.candidate_id)] = tuple(int(value) for value in raw_tuple)
        if refined_candidate.residual_norm_hp < best_residual:
            best_residual = refined_candidate.residual_norm_hp
    elapsed_sec = time.monotonic() - fallback_started_at
    merged_refinement = refinement_result
    merged_phasec = phasec_result
    if fallback_candidates:
        merged_refinement = _merge_refinement_results(
            refinement_result=refinement_result,
            fallback_candidates=tuple(fallback_candidates),
        )
        merged_phasec = run_phasec_assembly(
            refined_candidates=merged_refinement.candidates,
            input_precision_dps=120,
            residual_threshold=mp.mpf(pipeline_config.acceptance_residual_threshold),
            acceptance_margin_ratio=mp.mpf(pipeline_config.acceptance_margin_ratio),
        )
    solved_tuples = [
        list(fallback_candidate_targets[int(candidate.candidate_id)])
        for candidate in merged_phasec.accepted_candidates
        if int(candidate.candidate_id) in fallback_candidate_targets
    ]
    return (
        merged_refinement,
        merged_phasec,
        {
            "strategy_id": DISCRETE_TARGET_STRATEGY_ID,
            "completion_type": "discrete_target_enumeration",
            "triggered": True,
            "skip_reason": None,
            "constraint_count": len(specs),
            "target_intervals": [list(interval) for interval in intervals],
            "tuple_cap": tuple_cap,
            "tuple_count": tuple_count,
            "attempted_tuple_count": attempted_tuple_count,
            "completed_enumeration": completed_enumeration,
            "best_residual": "inf" if not mp.isfinite(best_residual) else str(best_residual),
            "accepted_count": len(merged_phasec.accepted_candidates),
            "solved_tuples": solved_tuples,
            "elapsed_sec": elapsed_sec,
            "remaining_budget_sec": runtime_budget.remaining_sec(),
        },
    )



# Compatibility aliases retained for older orchestration summaries/tests.
default_integer_fallback_summary = default_discrete_completion_summary
run_integer_target_fallback = run_discrete_target_completion
