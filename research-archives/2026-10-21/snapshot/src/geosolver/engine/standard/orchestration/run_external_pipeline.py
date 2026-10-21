"""Run full external pipeline (Phase 0 -> Phase C)."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from mpmath import mp

from geosolver.engine.standard.contracts.baseline_search_policy import (
    SEARCH_ATTEMPT_HYBRID_FALLBACK,
    SEARCH_ATTEMPT_PRIMARY,
    SearchAttemptConfig,
)
from geosolver.engine.standard.contracts.candidate_record import (
    CandidateKey,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
    candidate_record,
)
from geosolver.engine.standard.contracts.external_pipeline_config import (
    SEARCH_MODE_HYBRID_LEGACY_NOMAD,
    ExternalPipelineConfig,
)
from geosolver.engine.standard.contracts.pipeline_result import ExternalPipelineResult
from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.engine.standard.search.completion import (
    default_rescue_completion_summary,
    exact_assembly_needs_completion,
    merge_search_candidates_with_rescue,
)
from geosolver.engine.standard.search.discrete.integer_targets import (
    default_discrete_completion_summary,
    run_discrete_target_completion,
)
from geosolver.engine.standard.search.nomad_config import (
    DEFAULT_SEED_VALUES,
    NomadConfig,
    derive_seed_values,
)

from .assemble_exact_results import ExactAssemblyResult, assemble_exact_results
from .build_pipeline_summary import build_pipeline_summary
from .run_initial_probe import (
    InitialProbeResult,
    augment_initial_probe_with_exact_distance_samples,
    derive_initial_probe_seeds,
    run_initial_probe,
)
from .run_refinement import (
    merge_refinement_results,
    refine_added_candidates,
    run_refinement,
)
from .run_rescue_search import run_rescue_search
from .run_search import run_search


def _resolve_search_seed_count(config: NomadConfig) -> int:
    configured_count = len(config.seed_values)
    if configured_count > 0:
        return configured_count
    return len(DEFAULT_SEED_VALUES)


@dataclass(frozen=True)
class _PipelineStageState:
    initial_probe_result: InitialProbeResult
    search_result: SearchBatchResult
    refinement_result: RefinementBatchResult
    exact_assembly_result: ExactAssemblyResult


@dataclass(frozen=True)
class _CompletedPipelineStageState:
    initial_probe_result: InitialProbeResult
    search_result: SearchBatchResult
    refinement_result: RefinementBatchResult
    exact_assembly_result: ExactAssemblyResult
    rescue_search_summary: dict[str, object]
    integer_fallback_summary: dict[str, object]


@dataclass(frozen=True)
class _OrderedSearchAttemptDescriptor:
    attempt_id: str
    stage_label: str
    pipeline_config: ExternalPipelineConfig
    initial_probe_seed_base: int | None


@dataclass(frozen=True)
class _OrderedSearchAttemptOutcome:
    attempt: _OrderedSearchAttemptDescriptor
    completed_stage_state: _CompletedPipelineStageState


@dataclass(frozen=True)
class _OrderedSearchAttemptSelection:
    primary_outcome: _OrderedSearchAttemptOutcome
    selected_outcome: _OrderedSearchAttemptOutcome
    fallback_outcome: _OrderedSearchAttemptOutcome | None = None

    @property
    def fallback_triggered(self) -> bool:
        return self.fallback_outcome is not None


def _best_refinement_residual(
    refinement_result: RefinementBatchResult,
) -> MPFloat:
    best = mp.inf
    for candidate in refinement_result.candidates:
        if candidate.residual_norm_hp < best:
            best = candidate.residual_norm_hp
    return best


def _resolve_primary_initial_probe_seed_base(*, seed: int | None) -> int | None:
    if seed is not None:
        return int(seed)
    return None


def _resolve_fallback_seed_base(
    *,
    seed: int | None,
    pipeline_config: ExternalPipelineConfig,
) -> int | None:
    if seed is not None:
        return int(seed)
    if pipeline_config.search.seed_values:
        return int(pipeline_config.search.seed_values[0])
    return None


def _build_attempt_pipeline_config(
    *,
    pipeline_config: ExternalPipelineConfig,
    attempt: SearchAttemptConfig,
) -> ExternalPipelineConfig:
    return replace(
        pipeline_config,
        global_search_mode=attempt.search_mode,
        search=replace(
            pipeline_config.search,
            seed_values=attempt.seed_values,
        ),
    )


def _resolve_baseline_search_attempt(
    *,
    pipeline_config: ExternalPipelineConfig,
    attempt_id: str,
) -> SearchAttemptConfig | None:
    baseline_search_policy = pipeline_config.baseline_search_policy
    if baseline_search_policy is None:
        return None
    for attempt in baseline_search_policy.ordered_attempts:
        if attempt.attempt_id == attempt_id:
            return attempt
    return None


def _resolve_baseline_search_attempt_config(
    *,
    pipeline_config: ExternalPipelineConfig,
    attempt_id: str,
) -> ExternalPipelineConfig | None:
    attempt = _resolve_baseline_search_attempt(
        pipeline_config=pipeline_config,
        attempt_id=attempt_id,
    )
    if attempt is None:
        return None
    return _build_attempt_pipeline_config(
        pipeline_config=pipeline_config,
        attempt=attempt,
    )


def _resolve_ordered_search_attempts(
    *,
    pipeline_config: ExternalPipelineConfig,
    seed: int | None,
) -> tuple[_OrderedSearchAttemptDescriptor, ...]:
    primary_pipeline_config = _resolve_baseline_search_attempt_config(
        pipeline_config=pipeline_config,
        attempt_id=SEARCH_ATTEMPT_PRIMARY,
    )
    if primary_pipeline_config is None:
        primary_pipeline_config = pipeline_config
    resolved_attempts = [
        _OrderedSearchAttemptDescriptor(
            attempt_id=SEARCH_ATTEMPT_PRIMARY,
            stage_label="primary",
            pipeline_config=primary_pipeline_config,
            initial_probe_seed_base=_resolve_primary_initial_probe_seed_base(seed=seed),
        )
    ]
    fallback_seed_base = _resolve_fallback_seed_base(
        seed=seed,
        pipeline_config=pipeline_config,
    )
    fallback_pipeline_config = _build_hybrid_stage_fallback_config(
        pipeline_config=pipeline_config,
        seed_base=fallback_seed_base,
    )
    if fallback_pipeline_config is None:
        return tuple(resolved_attempts)
    resolved_attempts.append(
        _OrderedSearchAttemptDescriptor(
            attempt_id=SEARCH_ATTEMPT_HYBRID_FALLBACK,
            stage_label="fallback",
            pipeline_config=fallback_pipeline_config,
            initial_probe_seed_base=fallback_seed_base,
        )
    )
    return tuple(resolved_attempts)


def _build_staged_fallback_summary(
    *,
    selection: _OrderedSearchAttemptSelection,
) -> dict[str, object]:
    primary_config = selection.primary_outcome.attempt.pipeline_config
    primary_result = selection.primary_outcome.completed_stage_state
    summary = {
        "triggered": selection.fallback_triggered,
        "selected_stage": selection.selected_outcome.attempt.stage_label,
        "primary_search_mode": primary_config.global_search_mode,
        "primary_seed_values": list(primary_config.search.seed_values),
        "primary_exact_assembly_accepted_count": len(
            primary_result.exact_assembly_result.accepted_candidates
        ),
        "primary_refinement_best_residual": str(
            _best_refinement_residual(primary_result.refinement_result)
        ),
    }
    if selection.fallback_outcome is not None:
        fallback_config = selection.fallback_outcome.attempt.pipeline_config
        fallback_result = selection.fallback_outcome.completed_stage_state
        summary["fallback_search_mode"] = fallback_config.global_search_mode
        summary["fallback_seed_values"] = list(fallback_config.search.seed_values)
        summary["fallback_exact_assembly_accepted_count"] = len(
            fallback_result.exact_assembly_result.accepted_candidates
        )
        summary["fallback_refinement_best_residual"] = str(
            _best_refinement_residual(fallback_result.refinement_result)
        )
    return summary


def _should_select_fallback_attempt(
    *,
    primary_outcome: _OrderedSearchAttemptOutcome,
    fallback_outcome: _OrderedSearchAttemptOutcome,
) -> bool:
    primary_result = primary_outcome.completed_stage_state
    fallback_result = fallback_outcome.completed_stage_state
    if len(fallback_result.exact_assembly_result.accepted_candidates) > len(
        primary_result.exact_assembly_result.accepted_candidates
    ):
        return True
    if len(fallback_result.exact_assembly_result.accepted_candidates) < len(
        primary_result.exact_assembly_result.accepted_candidates
    ):
        return False
    fallback_best = _best_refinement_residual(fallback_result.refinement_result)
    primary_best = _best_refinement_residual(primary_result.refinement_result)
    if fallback_best < primary_best:
        return True
    if fallback_best > primary_best:
        return False
    return (
        fallback_result.search_result.evaluation_count
        > primary_result.search_result.evaluation_count
    )


def _build_hybrid_stage_fallback_config(
    *,
    pipeline_config: ExternalPipelineConfig,
    seed_base: int | None,
) -> ExternalPipelineConfig | None:
    policy_fallback_config = _resolve_baseline_search_attempt_config(
        pipeline_config=pipeline_config,
        attempt_id=SEARCH_ATTEMPT_HYBRID_FALLBACK,
    )
    if policy_fallback_config is not None:
        if (
            pipeline_config.global_search_mode == policy_fallback_config.global_search_mode
            and tuple(pipeline_config.search.seed_values)
            == tuple(policy_fallback_config.search.seed_values)
        ):
            return None
        return policy_fallback_config
    if seed_base is None:
        return None
    fallback_seed_count = max(
        len(DEFAULT_SEED_VALUES),
        _resolve_search_seed_count(pipeline_config.search),
    )
    fallback_seed_values = derive_seed_values(seed_base, count=fallback_seed_count)
    if pipeline_config.global_search_mode == SEARCH_MODE_HYBRID_LEGACY_NOMAD and tuple(
        pipeline_config.search.seed_values
    ) == tuple(fallback_seed_values):
        return None
    return replace(
        pipeline_config,
        global_search_mode=SEARCH_MODE_HYBRID_LEGACY_NOMAD,
        search=replace(
            pipeline_config.search,
            seed_values=fallback_seed_values,
        ),
    )


def _build_refinement_refiner(pipeline_config: ExternalPipelineConfig) -> MpmathRefiner:
    return MpmathRefiner(config=pipeline_config.refiner_config)


def _run_pipeline_stage(
    *,
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    pipeline_config: ExternalPipelineConfig,
    seed_base: int | None,
    refiner: MpmathRefiner,
    runtime_budget: RuntimeBudget,
    allow_algebraic: bool = True,
) -> _PipelineStageState:
    initial_probe_seed_count = _resolve_search_seed_count(pipeline_config.search)
    initial_probe_seeds = (
        derive_initial_probe_seeds(seed_base, count=initial_probe_seed_count)
        if seed_base is not None
        else None
    )
    from geosolver.engine.standard.search.algebraic_branches import search_algebraic_branches

    algebraic_search = (
        search_algebraic_branches(bundle=bundle, evaluator=evaluator) if allow_algebraic else None
    )
    if algebraic_search is None:
        initial_probe_result = run_initial_probe(
            evaluator=evaluator,
            bounds=bounds,
            **({"seeds": initial_probe_seeds} if initial_probe_seeds is not None else {}),
        )
        initial_probe_result = augment_initial_probe_with_exact_distance_samples(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            initial_probe_result=initial_probe_result,
        )
    else:
        initial_probe_result = InitialProbeResult(
            candidates=algebraic_search.candidates,
            metrics={"algebraic_branch_discovery": True},
        )
    constraint_scales = getattr(initial_probe_result, "constraint_scales", None)
    search_search_config = pipeline_config.search
    remaining_before_search = runtime_budget.remaining_sec()
    if search_search_config.max_time_sec is None:
        # The baseline contract keeps the search config timeless so NOMAD can own
        # its own budget.  The SciPy fallback, however, is an in-process portfolio
        # and must receive an explicit wall-clock slice to avoid overrunning the
        # external pipeline's per-case budget.
        search_search_config = replace(
            search_search_config,
            max_time_sec=max(0.0, remaining_before_search * 0.55),
        )
    else:
        search_search_config = replace(
            search_search_config,
            max_time_sec=min(
                float(search_search_config.max_time_sec),
                remaining_before_search,
            ),
        )
    search_result = algebraic_search or run_search(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        initial_probe_result=initial_probe_result,
        config=search_search_config,
        search_mode=pipeline_config.global_search_mode,
        guard_feasible_prefix_min=pipeline_config.guard_feasible_prefix_min,
        guard_feasible_prefix_multiplier=pipeline_config.guard_feasible_prefix_multiplier,
        constraint_scales=constraint_scales,
        allow_integer_shortcuts=allow_algebraic,
    )
    refinement_result = run_refinement(
        bundle=bundle,
        evaluator=evaluator,
        search_result=search_result,
        refiner=refiner,
        deadline_monotonic=pipeline_config.refinement_deadline(runtime_budget),
    )
    exact_assembly_result = assemble_exact_results(
        refined_candidates=refinement_result.candidates,
        evaluator=evaluator,
        input_precision_dps=120,
        deadline_monotonic=float(runtime_budget.deadline_monotonic),
    )
    return _PipelineStageState(
        initial_probe_result=initial_probe_result,
        search_result=search_result,
        refinement_result=refinement_result,
        exact_assembly_result=exact_assembly_result,
    )


def _complete_pipeline_stage(
    *,
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    stage_state: _PipelineStageState,
    pipeline_config: ExternalPipelineConfig,
    refiner: MpmathRefiner,
    runtime_budget: RuntimeBudget,
) -> _CompletedPipelineStageState:
    search_result = stage_state.search_result
    refinement_result = stage_state.refinement_result
    exact_assembly_result = stage_state.exact_assembly_result
    rescue_search_summary = default_rescue_completion_summary(
        runtime_budget=runtime_budget,
    )
    integer_fallback_summary = default_discrete_completion_summary(
        runtime_budget=runtime_budget,
        skip_reason="not_attempted",
    )
    if (
        exact_assembly_needs_completion(exact_assembly_result.accepted_candidates)
        and runtime_budget.remaining_sec() >= pipeline_config.rescue_time_budget_sec
    ):
        try:
            rescue_result = run_rescue_search(
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                search_result=search_result,
                pipeline_config=pipeline_config,
                runtime_budget=runtime_budget,
                constraint_scales=stage_state.initial_probe_result.constraint_scales,
            )
        except ImportError as exc:
            rescue_result = None
            rescue_search_summary = default_rescue_completion_summary(
                runtime_budget=runtime_budget,
                triggered=False,
                skip_reason=f"backend_unavailable: {exc}",
            )
        if rescue_result is not None:
            rescue_search_summary = default_rescue_completion_summary(
                runtime_budget=runtime_budget,
                triggered=True,
                box_count=len(rescue_result.boxes),
                rescued_candidate_count=len(rescue_result.candidates),
                best_residual=(
                    "inf"
                    if not rescue_result.candidates
                    else min(
                        candidate.residual_norm_float for candidate in rescue_result.candidates
                    )
                ),
                elapsed_sec=rescue_result.elapsed_sec,
            )
            rescue_search_summary["box_runs"] = list(rescue_result.box_runs)
            rescue_search_summary["executed_box_count"] = len(rescue_result.box_runs)
        if rescue_result is not None and rescue_result.candidates:
            rescued_refinement = refine_added_candidates(
                bundle=bundle,
                evaluator=evaluator,
                candidates=rescue_result.candidates,
                refiner=refiner,
                deadline_monotonic=pipeline_config.refinement_deadline(runtime_budget),
            )
            search_result = merge_search_candidates_with_rescue(
                search_result=search_result,
                rescued_candidates=rescue_result.candidates,
            )
            refinement_result = merge_refinement_results(
                refinement_result,
                rescued_refinement,
            )
            exact_assembly_result = assemble_exact_results(
                refined_candidates=refinement_result.candidates,
                evaluator=evaluator,
                input_precision_dps=120,
                deadline_monotonic=float(runtime_budget.deadline_monotonic),
            )
    refinement_result, exact_assembly_result, integer_fallback_summary = (
        run_discrete_target_completion(
            bundle=bundle,
            evaluator=evaluator,
            search_result=search_result,
            refinement_result=refinement_result,
            exact_assembly_result=exact_assembly_result,
            refiner=refiner,
            runtime_budget=runtime_budget,
            pipeline_config=pipeline_config,
        )
    )
    return _CompletedPipelineStageState(
        initial_probe_result=stage_state.initial_probe_result,
        search_result=search_result,
        refinement_result=refinement_result,
        exact_assembly_result=exact_assembly_result,
        rescue_search_summary=rescue_search_summary,
        integer_fallback_summary=integer_fallback_summary,
    )


def _execute_ordered_search_attempt(
    *,
    attempt: _OrderedSearchAttemptDescriptor,
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    refiner: MpmathRefiner,
    runtime_budget: RuntimeBudget,
) -> _OrderedSearchAttemptOutcome:
    from geosolver.engine.standard.contracts.candidate_record import candidate_attempt

    with candidate_attempt(0 if attempt.attempt_id == "primary" else 1):
        stage_state = _run_pipeline_stage(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            pipeline_config=attempt.pipeline_config,
            seed_base=attempt.initial_probe_seed_base,
            refiner=refiner,
            runtime_budget=runtime_budget,
            allow_algebraic=attempt.attempt_id == SEARCH_ATTEMPT_PRIMARY,
        )
        if (
            attempt.attempt_id == SEARCH_ATTEMPT_PRIMARY
            and _algebraic_provenance_incomplete(stage_state)
            and runtime_budget.remaining_sec() > 0
        ):
            # An optional enumeration replaces neither the ordinary primary
            # search nor its policy. If any proposed branch remains unresolved,
            # run that same primary seed/backend before considering hybrid search.
            with candidate_attempt(2):
                numeric_stage = _run_pipeline_stage(
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    pipeline_config=attempt.pipeline_config,
                    seed_base=attempt.initial_probe_seed_base,
                    refiner=refiner,
                    runtime_budget=runtime_budget,
                    allow_algebraic=False,
                )
                completed_numeric = _complete_pipeline_stage(
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    stage_state=numeric_stage,
                    pipeline_config=attempt.pipeline_config,
                    refiner=refiner,
                    runtime_budget=runtime_budget,
                )
            completed_optional = _CompletedPipelineStageState(
                initial_probe_result=stage_state.initial_probe_result,
                search_result=stage_state.search_result,
                refinement_result=stage_state.refinement_result,
                exact_assembly_result=stage_state.exact_assembly_result,
                rescue_search_summary={},
                integer_fallback_summary={},
            )
            optional = _OrderedSearchAttemptOutcome(attempt, completed_optional)
            numeric = _OrderedSearchAttemptOutcome(attempt, completed_numeric)
            combined = _union_partially_verified_algebraic_attempts(optional, numeric)
            completed = combined.selected_outcome.completed_stage_state
            search = replace(
                completed.search_result,
                search_diagnostics={
                    **completed.search_result.search_diagnostics,
                    "finite_enumeration_numeric_primary_completion": {
                        "search_mode": attempt.pipeline_config.global_search_mode,
                        "seed_values": list(attempt.pipeline_config.search.seed_values),
                        "accepted_count": len(
                            completed_numeric.exact_assembly_result.accepted_candidates
                        ),
                    },
                },
            )
            return replace(
                combined.selected_outcome,
                completed_stage_state=replace(completed, search_result=search),
            )
        return _OrderedSearchAttemptOutcome(
            attempt=attempt,
            completed_stage_state=_complete_pipeline_stage(
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                stage_state=stage_state,
                pipeline_config=attempt.pipeline_config,
                refiner=refiner,
                runtime_budget=runtime_budget,
            ),
        )


def _select_ordered_search_attempt_outcome(
    *,
    primary_outcome: _OrderedSearchAttemptOutcome,
    fallback_outcome: _OrderedSearchAttemptOutcome | None = None,
) -> _OrderedSearchAttemptSelection:
    if fallback_outcome is None:
        return _OrderedSearchAttemptSelection(
            primary_outcome=primary_outcome,
            selected_outcome=primary_outcome,
        )
    selected_outcome = (
        fallback_outcome
        if _should_select_fallback_attempt(
            primary_outcome=primary_outcome,
            fallback_outcome=fallback_outcome,
        )
        else primary_outcome
    )
    return _OrderedSearchAttemptSelection(
        primary_outcome=primary_outcome,
        selected_outcome=selected_outcome,
        fallback_outcome=fallback_outcome,
    )


def _algebraic_provenance_incomplete(stage):
    from geosolver.engine.standard.search.algebraic_branch_boxes import accepted_within_origin_box

    if stage.search_result.search_diagnostics.get("finite_enumeration_numeric_primary_completion"):
        return False
    # Float rejection is not a mathematical nonexistence certificate. Retain
    # every finitely enumerated square root in the completion obligation.
    records = (
        *stage.search_result.candidates,
        *(
            candidate
            for candidate in stage.search_result.all_records
            if getattr(candidate, "origin_backend", None) == "integer_square_difference"
        ),
    )
    proposals = {
        candidate.candidate_key: candidate
        for candidate in records
        if getattr(candidate, "origin_backend", None)
        in {"exact_polynomial", "integer_square_difference", "integer_segment_displacements"}
    }
    if not proposals:
        return False
    verified_origins = {
        candidate.source.candidate_key
        for candidate in stage.exact_assembly_result.accepted_candidates
        if candidate.source is not None
        and candidate.source.candidate_key in proposals
        and accepted_within_origin_box(candidate, proposals[candidate.source.candidate_key])
    }
    return not proposals.keys() <= verified_origins


def _union_partially_verified_algebraic_attempts(primary_outcome, fallback_outcome):
    """Preserve every independently verified record from both attempts.

    This merge is restricted to completion of a partially verified finite
    enumeration. No candidate is admitted by branch or answer counts. The
    original record identities, revisions, and verification receipts survive.
    """
    first = primary_outcome.completed_stage_state
    second = fallback_outcome.completed_stage_state
    a, b = first.search_result, second.search_result
    search = SearchBatchResult(
        candidates=(*a.candidates, *b.candidates),
        evaluation_count=a.evaluation_count + b.evaluation_count,
        failure_ratio=(a.failed_evaluations + b.failed_evaluations)
        / max(1, a.evaluation_count + b.evaluation_count),
        evaluation_failure_count=a.failed_evaluations + b.failed_evaluations,
        all_records=(*a.all_records, *b.all_records),
        guard_feasible_ledger=(*a.guard_feasible_ledger, *b.guard_feasible_ledger),
        search_diagnostics={
            **a.search_diagnostics,
            "partial_algebraic_numeric_completion": b.search_diagnostics,
        },
    )
    a, b = first.exact_assembly_result, second.exact_assembly_result
    assembly = ExactAssemblyResult(
        numeric_feasible_candidates=(
            *a.numeric_feasible_candidates,
            *b.numeric_feasible_candidates,
        ),
        accepted_candidates=(*a.accepted_candidates, *b.accepted_candidates),
        exact_results=(*a.exact_results, *b.exact_results),
        candidate_records=(*a.candidate_records, *b.candidate_records),
        answer_values=(*a.answer_values, *b.answer_values),
        rejected_false_positive_count=a.rejected_false_positive_count
        + b.rejected_false_positive_count,
        rejection_tags=tuple(dict.fromkeys((*a.rejection_tags, *b.rejection_tags))),
        verification_records=(*a.verification_records, *b.verification_records),
    )
    combined = replace(
        second,
        search_result=search,
        refinement_result=merge_refinement_results(
            first.refinement_result, second.refinement_result
        ),
        exact_assembly_result=assembly,
    )
    return _OrderedSearchAttemptSelection(
        primary_outcome=primary_outcome,
        fallback_outcome=fallback_outcome,
        selected_outcome=replace(fallback_outcome, completed_stage_state=combined),
    )


def _run_ordered_search_attempts(
    *,
    ordered_attempts: tuple[_OrderedSearchAttemptDescriptor, ...],
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    refiner: MpmathRefiner,
    runtime_budget: RuntimeBudget,
) -> _OrderedSearchAttemptSelection:
    primary_attempt = ordered_attempts[0]
    primary_outcome = _execute_ordered_search_attempt(
        attempt=primary_attempt,
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        refiner=refiner,
        runtime_budget=runtime_budget,
    )
    primary_has_answers = bool(
        primary_outcome.completed_stage_state.exact_assembly_result.accepted_candidates
    )
    incomplete_polynomial = _algebraic_provenance_incomplete(primary_outcome.completed_stage_state)
    numeric_completion = primary_outcome.completed_stage_state.search_result.search_diagnostics.get(
        "finite_enumeration_numeric_primary_completion"
    )
    # The ordinary primary attempt controls escalation even if the optional
    # prepass already found an answer. Preserve those records in either outcome.
    numeric_primary_has_answers = (
        bool(numeric_completion["accepted_count"])
        if numeric_completion is not None
        else primary_has_answers
    )
    if (
        (numeric_primary_has_answers and not incomplete_polynomial)
        or len(ordered_attempts) == 1
        or runtime_budget.remaining_sec() <= 0
    ):
        return _select_ordered_search_attempt_outcome(primary_outcome=primary_outcome)
    fallback_attempt = ordered_attempts[1]
    fallback_outcome = _execute_ordered_search_attempt(
        attempt=fallback_attempt,
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        refiner=refiner,
        runtime_budget=runtime_budget,
    )
    if primary_has_answers and (incomplete_polynomial or numeric_completion is not None):
        return _union_partially_verified_algebraic_attempts(primary_outcome, fallback_outcome)
    return _select_ordered_search_attempt_outcome(
        primary_outcome=primary_outcome,
        fallback_outcome=fallback_outcome,
    )


def _build_debug_candidates(
    *,
    refined_candidates: tuple[RefinedCandidate, ...],
    accepted_candidates: tuple[RefinedCandidate, ...],
    limit: int,
) -> tuple[dict[str, object], ...]:
    accepted_ids = {candidate.candidate_key for candidate in accepted_candidates}
    ordered = sorted(refined_candidates, key=lambda candidate: candidate.residual_norm_hp)
    debug_entries: list[dict[str, object]] = []
    for candidate in ordered[: max(0, int(limit))]:
        debug_entries.append(
            {
                "candidate_id": int(candidate.candidate_id),
                "candidate_uid": candidate.candidate_uid,
                "stage": "refinement",
                "hard_feasible": bool(candidate.hard_feasible),
                "validity_margin": (
                    None
                    if candidate.validity_margin_hp is None
                    else str(candidate.validity_margin_hp)
                ),
                "hard_violation_tags": list(candidate.hard_violation_tags),
                "refinement_status": candidate.refinement_status,
                "rejection_tag": (
                    None
                    if candidate.candidate_key in accepted_ids
                    else "rejected_by_exact_assembly"
                ),
            }
        )
    return tuple(debug_entries)


def _run_external_pipeline_without_variables(
    evaluator: object,
    *,
    runtime_budget: RuntimeBudget,
) -> ExternalPipelineResult:
    float_eval = evaluator.evaluate_float_residual([])
    guard_ok, guard_violations = evaluator.evaluate_guard([])
    with high_precision_mode():
        hp_eval = evaluator.evaluate_hp_residual([], precision=120)
        answer_eval = evaluator.evaluate_answer_hp([], precision=120)
    refined_candidates: tuple[RefinedCandidate, ...] = ()
    exact_results = ()
    selected_answer = None
    accepted_answers: tuple[MPFloat, ...] = ()
    exact_assembly_answer_values: tuple[str, ...] = ()
    exact_assembly_accepted_count = 0
    # Keep the result object available for the no-solution branch below.  In
    # the old code it was only assigned after a successful direct evaluation,
    # so a valid zero-variable problem whose guards failed raised
    # ``UnboundLocalError`` while assembling the summary.
    exact_assembly_result = ExactAssemblyResult(
        numeric_feasible_candidates=(),
        accepted_candidates=(),
        exact_results=(),
        candidate_records=(),
        answer_values=(),
        rejected_false_positive_count=0,
        rejection_tags=(),
    )
    if (
        guard_ok
        and hp_eval.evaluation_status is EvaluationStatus.OK
        and answer_eval.evaluation_status is EvaluationStatus.OK
        and answer_eval.answer_hp is not None
    ):
        refined = RefinedCandidate(
            x_hp=(),
            residual_norm_hp=hp_eval.residual_norm_hp,
            answer_hp=answer_eval.answer_hp,
            refinement_status="direct_evaluation",
            phase_history=("direct:120:target_reached",),
            source=None,
            candidate_id=1,
            origin_key=CandidateKey("direct", "constant", 0, None, -1, 0, 0),
            hard_feasible=None,
            hard_violation_tags=() if guard_ok else tuple(guard_violations),
            validity_margin_hp=None,
        )
        refined_candidates = (refined,)
        exact_assembly_result = assemble_exact_results(
            refined_candidates=refined_candidates,
            evaluator=evaluator,
            input_precision_dps=120,
            deadline_monotonic=float(runtime_budget.deadline_monotonic),
        )
        exact_results = exact_assembly_result.exact_results
        exact_assembly_answer_values = exact_assembly_result.answer_values
        exact_assembly_accepted_count = len(exact_assembly_result.accepted_candidates)
        accepted_answers = tuple(
            candidate.answer_hp
            for candidate in exact_assembly_result.accepted_candidates
            if candidate.answer_hp is not None
        )
        if exact_assembly_result.accepted_candidates:
            selected_answer = exact_assembly_result.accepted_candidates[0].answer_hp
    status = "success" if selected_answer is not None else "no_solution"
    summary = {
        "initial_probe": {
            "total_random_points": 1,
            "finite_residual_ratio": 1.0 if float_eval.is_finite else 0.0,
            "guard_pass_ratio": 1.0 if guard_ok else 0.0,
            "best_random_residual": float_eval.residual_norm_float
            if float_eval.is_finite
            else None,
            "best_random_point": [],
            "guard_violations": list(guard_violations),
        },
        "search": {
            "evaluation_count": 0,
            "failure_ratio": 0.0,
            "selected_candidates": 0,
            "all_record_count": 0,
            "guard_feasible_record_count": 0,
            "guard_feasible_ledger_count": 0,
            "compact_candidate_count": 0,
        },
        "refinement": {
            "attempted_count": 1,
            "converged_count": 1 if selected_answer is not None else 0,
            "best_residual": str(hp_eval.residual_norm_hp),
            "solver_name": "direct_evaluation",
            "hard_feasible_count": 1 if selected_answer is not None else 0,
        },
        "exact_assembly": {
            "numeric_feasible_count": len(exact_assembly_result.numeric_feasible_candidates),
            "accepted_count": exact_assembly_accepted_count,
            "answer_values": list(exact_assembly_answer_values),
            "rejected_false_positive_count": 0,
            "rejection_tags": [],
        },
        "phase_rescue": default_rescue_completion_summary(
            runtime_budget=runtime_budget,
        ),
        "phase_discrete_completion": default_discrete_completion_summary(
            runtime_budget=runtime_budget,
            skip_reason="no_variables",
        ),
        "debug_candidates": [],
    }
    from dataclasses import asdict

    summary["pipeline_backend"] = "direct_evaluation"
    summary["verification_records"] = list(exact_assembly_result.verification_records)
    summary["exact_candidate_records"] = [
        {
            "candidate": candidate_record(record.candidate),
            "exact_result": asdict(record.exact_result),
        }
        for record in exact_assembly_result.candidate_records
    ]
    summary["exact_assembly"]["rejection_tags"] = list(exact_assembly_result.rejection_tags)
    summary["exact_assembly"]["rejected_false_positive_count"] = (
        exact_assembly_result.rejected_false_positive_count
    )
    accepted_candidate_ids = [
        int(candidate.candidate_id)
        for candidate in exact_assembly_result.accepted_candidates
        if int(candidate.candidate_id) >= 0
    ]
    selected_candidate_id = accepted_candidate_ids[0] if accepted_candidate_ids else None
    summary["candidate_ledger"] = []
    summary["best_candidate_id"] = selected_candidate_id
    summary["answer_source_candidate_id"] = selected_candidate_id
    summary["residual_source_candidate_id"] = selected_candidate_id
    summary["answer_extraction_candidate_ids"] = accepted_candidate_ids
    summary["answer_candidates"] = accepted_candidate_ids
    summary["answer_candidate_values"] = list(exact_assembly_answer_values)
    return ExternalPipelineResult(
        status=status,
        selected_answer=selected_answer,
        accepted_answers=accepted_answers,
        float_candidates=(),
        refined_candidates=exact_assembly_result.updated_candidates(refined_candidates),
        exact_results=exact_results,
        summary=summary,
        accepted_candidate_ids=tuple(accepted_candidate_ids),
        accepted_candidate_uids=tuple(
            c.candidate_uid for c in exact_assembly_result.accepted_candidates
        ),
        accepted_candidate_revisions=tuple(
            (c.candidate_uid, c.revision) for c in exact_assembly_result.accepted_candidates
        ),
    )


def run_external_pipeline(
    problem_ir: object,
    *,
    seed: int | None = None,
    nomad_config: NomadConfig | None = None,
    refiner: MpmathRefiner | None = None,
    pipeline_config: ExternalPipelineConfig | None = None,
    deadline_monotonic: float | None = None,
) -> ExternalPipelineResult:
    """Run every phase under the same deadline, including direct internal calls."""
    from geosolver.runtime.deadline import uses_deadline

    if deadline_monotonic is None:
        config = pipeline_config or ExternalPipelineConfig.standard_tier()
        deadline_monotonic = time.monotonic() + config.total_time_budget_sec
    return uses_deadline(_run_external_pipeline)(
        problem_ir,
        seed=seed,
        nomad_config=nomad_config,
        refiner=refiner,
        pipeline_config=pipeline_config,
        deadline_monotonic=deadline_monotonic,
    )


def _run_external_pipeline(
    problem_ir: object,
    *,
    seed: int | None = None,
    nomad_config: NomadConfig | None = None,
    refiner: MpmathRefiner | None = None,
    pipeline_config: ExternalPipelineConfig | None = None,
    deadline_monotonic: float | None = None,
) -> ExternalPipelineResult:
    """Execute external pipeline and return structured contract result.

    Args:
        refiner: Active local refiner, injectable for regression tests.
    """
    if pipeline_config is not None and nomad_config is not None:
        raise ValueError("pipeline_config and nomad_config cannot be provided together")
    active_pipeline_config = (
        pipeline_config if pipeline_config is not None else ExternalPipelineConfig.standard_tier()
    )
    if nomad_config is not None:
        active_pipeline_config = replace(active_pipeline_config, search=nomad_config)
    if pipeline_config is None and seed is not None:
        search_seed_count = _resolve_search_seed_count(active_pipeline_config.search)
        active_pipeline_config = replace(
            active_pipeline_config,
            search=replace(
                active_pipeline_config.search,
                seed_values=derive_seed_values(seed, count=search_seed_count),
            ),
        )
    runtime_budget = RuntimeBudget(
        total_budget_sec=active_pipeline_config.total_time_budget_sec,
        started_at_monotonic=time.monotonic(),
        deadline_monotonic=deadline_monotonic,
    )
    refinement_refiner = refiner
    if refinement_refiner is None:
        refinement_refiner = _build_refinement_refiner(active_pipeline_config)
    bundle = load_problem_bundle(problem_ir)
    evaluator = build_ir_evaluator(bundle)
    if len(bundle.var_names) == 0:
        return _run_external_pipeline_without_variables(
            evaluator,
            runtime_budget=runtime_budget,
        )
    bounds = infer_problem_bounds(bundle)
    ordered_attempts = _resolve_ordered_search_attempts(
        pipeline_config=active_pipeline_config,
        seed=seed,
    )
    attempt_selection = _run_ordered_search_attempts(
        ordered_attempts=ordered_attempts,
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        refiner=refinement_refiner,
        runtime_budget=runtime_budget,
    )
    selected_attempt = attempt_selection.selected_outcome.attempt
    completed_stage_state = attempt_selection.selected_outcome.completed_stage_state
    initial_probe_result = completed_stage_state.initial_probe_result
    search_result = completed_stage_state.search_result
    refinement_result = completed_stage_state.refinement_result
    exact_assembly_result = completed_stage_state.exact_assembly_result
    rescue_search_summary = completed_stage_state.rescue_search_summary
    integer_fallback_summary = completed_stage_state.integer_fallback_summary
    summary = build_pipeline_summary(
        initial_probe_result=initial_probe_result,
        search_result=search_result,
        refinement_result=refinement_result,
        assembly_result=exact_assembly_result,
        rescue_search_summary=rescue_search_summary,
        integer_fallback_summary=integer_fallback_summary,
        debug_candidates=_build_debug_candidates(
            refined_candidates=refinement_result.candidates,
            accepted_candidates=exact_assembly_result.accepted_candidates,
            limit=selected_attempt.pipeline_config.candidate_debug_limit,
        ),
    )
    summary["search_staged_fallback"] = _build_staged_fallback_summary(
        selection=attempt_selection,
    )
    summary["pipeline_backend"] = selected_attempt.pipeline_config.global_search_mode
    selected_answer = None
    accepted_answers = tuple(
        candidate.answer_hp
        for candidate in exact_assembly_result.accepted_candidates
        if candidate.answer_hp is not None
    )
    accepted_candidate_ids = tuple(
        int(candidate.candidate_id) for candidate in exact_assembly_result.accepted_candidates
    )
    if exact_assembly_result.accepted_candidates:
        selected_answer = exact_assembly_result.accepted_candidates[0].answer_hp
    status = "success" if selected_answer is not None else "no_solution"
    return ExternalPipelineResult(
        status=status,
        selected_answer=selected_answer,
        accepted_answers=accepted_answers,
        float_candidates=search_result.candidates,
        refined_candidates=exact_assembly_result.updated_candidates(refinement_result.candidates),
        exact_results=exact_assembly_result.exact_results,
        summary=summary,
        accepted_candidate_ids=accepted_candidate_ids,
        accepted_candidate_uids=tuple(
            c.candidate_uid for c in exact_assembly_result.accepted_candidates
        ),
        accepted_candidate_revisions=tuple(
            (c.candidate_uid, c.revision) for c in exact_assembly_result.accepted_candidates
        ),
    )
