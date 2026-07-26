"""Run full external pipeline (Phase 0 -> Phase C)."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time

from mpmath import mp

from geosolver._internal.pipeline.box.julia_box_solver import JuliaBoxSolver
from geosolver._internal.pipeline.contracts.box_solver_port import BoxSolverPort
from geosolver._internal.pipeline.contracts.baseline_search_policy import (
    SEARCH_ATTEMPT_HYBRID_FALLBACK,
    SEARCH_ATTEMPT_PRIMARY,
    SearchAttemptConfig,
)
from geosolver._internal.pipeline.contracts.candidate_record import (
    RefinementBatchResult,
    RefinedCandidate,
    SearchBatchResult,
)
from geosolver._internal.pipeline.contracts.external_pipeline_config import (
    ExternalPipelineConfig,
    SEARCH_MODE_HYBRID_LEGACY_NOMAD,
)
from geosolver._internal.pipeline.contracts.pipeline_result import ExternalPipelineResult
from geosolver._internal.pipeline.contracts.runtime_budget import RuntimeBudget
from geosolver._internal.pipeline.completion import (
    default_rescue_completion_summary,
    merge_search_candidates_with_rescue,
    phasec_needs_completion,
)
from geosolver._internal.pipeline.discrete.integer_targets import (
    default_discrete_completion_summary,
    run_discrete_target_completion,
)
from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import EvaluationStatus
from geosolver._internal.pipeline.evaluator.ir_evaluator import build_ir_evaluator
from geosolver._internal.pipeline.problem.infer_problem_bounds import infer_problem_bounds
from geosolver._internal.pipeline.problem.load_problem_bundle import load_problem_bundle
from geosolver._internal.pipeline.refine.mpmath_refiner import MpmathRefiner
from geosolver._internal.pipeline.search.nomad_config import NomadConfig
from geosolver._internal.pipeline.search.nomad_config import (
    DEFAULT_SEED_VALUES,
    derive_seed_values,
)
from geosolver._internal.solver.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat

from .build_pipeline_summary import build_pipeline_summary
from .run_phase0_probe import (
    augment_phase0_with_exact_distance_samples,
    derive_phase0_seeds,
    run_phase0_probe,
    Phase0ProbeResult,
)
from .run_phasea_search import run_phasea_search
from .run_phaseb_box_solve import run_phaseb_box_solve
from .run_phaseb_refinement import run_phaseb_refinement
from .run_phase_rescue_search import run_phase_rescue_search
from .run_phasec_assembly import PhaseCAssemblyResult, run_phasec_assembly

# Backwards-compatible private aliases for older regression tests/importers.
_default_integer_fallback_summary = default_discrete_completion_summary
_run_integer_target_fallback = run_discrete_target_completion


def _resolve_search_seed_count(config: NomadConfig) -> int:
    configured_count = len(config.seed_values)
    if configured_count > 0:
        return configured_count
    return len(DEFAULT_SEED_VALUES)



@dataclass(frozen=True)
class _PipelineStageState:
    phase0_result: Phase0ProbeResult
    phasea_result: SearchBatchResult
    phaseb_result: RefinementBatchResult
    phasec_result: PhaseCAssemblyResult


@dataclass(frozen=True)
class _CompletedPipelineStageState:
    phase0_result: Phase0ProbeResult
    phasea_result: SearchBatchResult
    phaseb_result: RefinementBatchResult
    phasec_result: PhaseCAssemblyResult
    phase_rescue_summary: dict[str, object]
    phase_integer_fallback_summary: dict[str, object]


_ORDERED_ATTEMPT_COMPLETION_BUDGET_SHARED_RUNTIME = "shared_runtime_budget"
_ORDERED_ATTEMPT_COMPLETION_BUDGET_FRESH_AFTER_SEARCH = (
    "fresh_completion_budget_after_search"
)


@dataclass(frozen=True)
class _OrderedAttemptBudgetRelationship:
    completion_budget_mode: str

    def build_completion_runtime_budget(
        self,
        *,
        pipeline_config: ExternalPipelineConfig,
        runtime_budget: RuntimeBudget,
    ) -> RuntimeBudget:
        if self.completion_budget_mode == _ORDERED_ATTEMPT_COMPLETION_BUDGET_SHARED_RUNTIME:
            return runtime_budget
        if (
            self.completion_budget_mode
            != _ORDERED_ATTEMPT_COMPLETION_BUDGET_FRESH_AFTER_SEARCH
        ):
            raise ValueError(
                "unknown ordered-attempt completion budget mode: "
                f"{self.completion_budget_mode}"
            )
        return RuntimeBudget(
            total_budget_sec=pipeline_config.total_time_budget_sec,
            started_at_monotonic=time.monotonic(),
        )


@dataclass(frozen=True)
class _OrderedSearchAttemptDescriptor:
    attempt_id: str
    stage_label: str
    pipeline_config: ExternalPipelineConfig
    phase0_seed_base: int | None
    budget_relationship: _OrderedAttemptBudgetRelationship


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


def _resolve_primary_phase0_seed_base(*, seed: int | None) -> int | None:
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
            phase0_seed_base=_resolve_primary_phase0_seed_base(seed=seed),
            budget_relationship=_OrderedAttemptBudgetRelationship(
                completion_budget_mode=_ORDERED_ATTEMPT_COMPLETION_BUDGET_SHARED_RUNTIME
            ),
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
            phase0_seed_base=fallback_seed_base,
            budget_relationship=_OrderedAttemptBudgetRelationship(
                completion_budget_mode=(
                    _ORDERED_ATTEMPT_COMPLETION_BUDGET_FRESH_AFTER_SEARCH
                )
            ),
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
        "primary_phasec_accepted_count": len(primary_result.phasec_result.accepted_candidates),
        "primary_phaseb_best_residual": str(_best_refinement_residual(primary_result.phaseb_result)),
    }
    if selection.fallback_outcome is not None:
        fallback_config = selection.fallback_outcome.attempt.pipeline_config
        fallback_result = selection.fallback_outcome.completed_stage_state
        summary["fallback_search_mode"] = fallback_config.global_search_mode
        summary["fallback_seed_values"] = list(fallback_config.search.seed_values)
        summary["fallback_phasec_accepted_count"] = len(
            fallback_result.phasec_result.accepted_candidates
        )
        summary["fallback_phaseb_best_residual"] = str(
            _best_refinement_residual(fallback_result.phaseb_result)
        )
    return summary


def _should_select_fallback_attempt(
    *,
    primary_outcome: _OrderedSearchAttemptOutcome,
    fallback_outcome: _OrderedSearchAttemptOutcome,
) -> bool:
    primary_result = primary_outcome.completed_stage_state
    fallback_result = fallback_outcome.completed_stage_state
    if len(fallback_result.phasec_result.accepted_candidates) > len(
        primary_result.phasec_result.accepted_candidates
    ):
        return True
    if len(fallback_result.phasec_result.accepted_candidates) < len(
        primary_result.phasec_result.accepted_candidates
    ):
        return False
    fallback_best = _best_refinement_residual(fallback_result.phaseb_result)
    primary_best = _best_refinement_residual(primary_result.phaseb_result)
    if fallback_best < primary_best:
        return True
    if fallback_best > primary_best:
        return False
    return fallback_result.phasea_result.evaluation_count > primary_result.phasea_result.evaluation_count


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
    if (
        pipeline_config.global_search_mode == SEARCH_MODE_HYBRID_LEGACY_NOMAD
        and tuple(pipeline_config.search.seed_values) == tuple(fallback_seed_values)
    ):
        return None
    return replace(
        pipeline_config,
        global_search_mode=SEARCH_MODE_HYBRID_LEGACY_NOMAD,
        search=replace(
            pipeline_config.search,
            seed_values=fallback_seed_values,
        ),
    )


def _resolve_attempt_completion_runtime_budget(
    *,
    attempt: _OrderedSearchAttemptDescriptor,
    runtime_budget: RuntimeBudget,
) -> RuntimeBudget:
    return attempt.budget_relationship.build_completion_runtime_budget(
        pipeline_config=attempt.pipeline_config,
        runtime_budget=runtime_budget,
    )


def _build_phaseb_refiner(pipeline_config: ExternalPipelineConfig) -> MpmathRefiner:
    try:
        return MpmathRefiner(config=pipeline_config.refiner_config)
    except TypeError:
        # Some tests monkeypatch MpmathRefiner with a zero-arg stub.
        return MpmathRefiner()


def _run_pipeline_stage(
    *,
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    pipeline_config: ExternalPipelineConfig,
    seed_base: int | None,
    box_solver: BoxSolverPort | None,
    refiner: MpmathRefiner | None,
    runtime_budget: RuntimeBudget | None = None,
) -> _PipelineStageState:
    phase0_seed_count = _resolve_search_seed_count(pipeline_config.search)
    phase0_seeds = (
        derive_phase0_seeds(seed_base, count=phase0_seed_count)
        if seed_base is not None
        else None
    )
    phase0_result = run_phase0_probe(
        evaluator=evaluator,
        bounds=bounds,
        **({"seeds": phase0_seeds} if phase0_seeds is not None else {}),
    )
    phase0_result = augment_phase0_with_exact_distance_samples(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        phase0_result=phase0_result,
    )
    constraint_scales = getattr(phase0_result, "constraint_scales", None)
    phasea_search_config = pipeline_config.search
    if phasea_search_config.max_time_sec is None:
        # The baseline contract keeps the search config timeless so NOMAD can own
        # its own budget.  The SciPy fallback, however, is an in-process portfolio
        # and must receive an explicit wall-clock slice to avoid overrunning the
        # external pipeline's per-case budget.
        phasea_search_config = replace(
            phasea_search_config,
            max_time_sec=max(1.0, float(pipeline_config.total_time_budget_sec) * 0.55),
        )
    phasea_result = run_phasea_search(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        phase0_result=phase0_result,
        config=phasea_search_config,
        search_mode=pipeline_config.global_search_mode,
        guard_feasible_prefix_min=pipeline_config.guard_feasible_prefix_min,
        guard_feasible_prefix_multiplier=pipeline_config.guard_feasible_prefix_multiplier,
        constraint_scales=constraint_scales,
    )
    if pipeline_config.enable_box_solver:
        if box_solver is None:
            raise RuntimeError("box solver is required but unavailable")
        phaseb_result = run_phaseb_box_solve(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            search_result=phasea_result,
            pipeline_config=pipeline_config,
            box_solver=box_solver,
        )
    else:
        if refiner is None:
            raise RuntimeError("refiner is required for non-box-solver path")
        phaseb_result = run_phaseb_refinement(
            bundle=bundle,
            evaluator=evaluator,
            search_result=phasea_result,
            refiner=refiner,
        )
    phasec_result = run_phasec_assembly(
        refined_candidates=phaseb_result.candidates,
        input_precision_dps=120,
        residual_threshold=mp.mpf(pipeline_config.acceptance_residual_threshold),
        acceptance_margin_ratio=mp.mpf(pipeline_config.acceptance_margin_ratio),
    )
    return _PipelineStageState(
        phase0_result=phase0_result,
        phasea_result=phasea_result,
        phaseb_result=phaseb_result,
        phasec_result=phasec_result,
    )


def _complete_pipeline_stage(
    *,
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    stage_state: _PipelineStageState,
    pipeline_config: ExternalPipelineConfig,
    box_solver: BoxSolverPort | None,
    refiner: MpmathRefiner | None,
    runtime_budget: RuntimeBudget,
) -> _CompletedPipelineStageState:
    phasea_result = stage_state.phasea_result
    phaseb_result = stage_state.phaseb_result
    phasec_result = stage_state.phasec_result
    phase_rescue_summary = default_rescue_completion_summary(
        runtime_budget=runtime_budget,
    )
    phase_integer_fallback_summary = default_discrete_completion_summary(
        runtime_budget=runtime_budget,
        skip_reason="not_attempted",
    )
    if phasec_needs_completion(phasec_result.accepted_candidates):
        if runtime_budget.remaining_sec() >= pipeline_config.rescue_time_budget_sec:
            try:
                rescue_result = run_phase_rescue_search(
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    search_result=phasea_result,
                    pipeline_config=pipeline_config,
                    runtime_budget=runtime_budget,
                    constraint_scales=stage_state.phase0_result.constraint_scales,
                )
            except ImportError as exc:
                rescue_result = None
                phase_rescue_summary = default_rescue_completion_summary(
                    runtime_budget=runtime_budget,
                    triggered=False,
                    skip_reason=f"backend_unavailable: {exc}",
                )
            if rescue_result is not None:
                phase_rescue_summary = default_rescue_completion_summary(
                    runtime_budget=runtime_budget,
                    triggered=True,
                    box_count=len(rescue_result.boxes),
                    rescued_candidate_count=len(rescue_result.candidates),
                    best_residual=(
                        "inf"
                        if not rescue_result.candidates
                        else min(candidate.residual_norm_float for candidate in rescue_result.candidates)
                    ),
                    elapsed_sec=rescue_result.elapsed_sec,
                )
            if rescue_result is not None and rescue_result.candidates:
                phasea_result = merge_search_candidates_with_rescue(
                    search_result=phasea_result,
                    rescued_candidates=rescue_result.candidates,
                )
                if pipeline_config.enable_box_solver:
                    if box_solver is None:
                        raise RuntimeError("box solver is required but unavailable")
                    phaseb_result = run_phaseb_box_solve(
                        bundle=bundle,
                        evaluator=evaluator,
                        bounds=bounds,
                        search_result=phasea_result,
                        pipeline_config=pipeline_config,
                        box_solver=box_solver,
                        rescue_boxes=rescue_result.boxes,
                    )
                else:
                    if refiner is None:
                        raise RuntimeError("refiner is required for non-box-solver path")
                    phaseb_result = run_phaseb_refinement(
                        bundle=bundle,
                        evaluator=evaluator,
                        search_result=phasea_result,
                        refiner=refiner,
                        deadline_monotonic=time.monotonic() + runtime_budget.remaining_sec(),
                    )
                phasec_result = run_phasec_assembly(
                    refined_candidates=phaseb_result.candidates,
                    input_precision_dps=120,
                    residual_threshold=mp.mpf(pipeline_config.acceptance_residual_threshold),
                    acceptance_margin_ratio=mp.mpf(pipeline_config.acceptance_margin_ratio),
                )
    phaseb_result, phasec_result, phase_integer_fallback_summary = run_discrete_target_completion(
        bundle=bundle,
        evaluator=evaluator,
        search_result=phasea_result,
        refinement_result=phaseb_result,
        phasec_result=phasec_result,
        refiner=refiner,
        runtime_budget=runtime_budget,
        pipeline_config=pipeline_config,
    )
    return _CompletedPipelineStageState(
        phase0_result=stage_state.phase0_result,
        phasea_result=phasea_result,
        phaseb_result=phaseb_result,
        phasec_result=phasec_result,
        phase_rescue_summary=phase_rescue_summary,
        phase_integer_fallback_summary=phase_integer_fallback_summary,
    )


def _execute_ordered_search_attempt(
    *,
    attempt: _OrderedSearchAttemptDescriptor,
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    box_solver: BoxSolverPort | None,
    refiner: MpmathRefiner | None,
    runtime_budget: RuntimeBudget,
) -> _OrderedSearchAttemptOutcome:
    stage_state = _run_pipeline_stage(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        pipeline_config=attempt.pipeline_config,
        seed_base=attempt.phase0_seed_base,
        box_solver=box_solver,
        refiner=refiner,
        runtime_budget=runtime_budget,
    )
    return _OrderedSearchAttemptOutcome(
        attempt=attempt,
        completed_stage_state=_complete_pipeline_stage(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            stage_state=stage_state,
            pipeline_config=attempt.pipeline_config,
            box_solver=box_solver,
            refiner=refiner,
            runtime_budget=_resolve_attempt_completion_runtime_budget(
                attempt=attempt,
                runtime_budget=runtime_budget,
            ),
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


def _run_ordered_search_attempts(
    *,
    ordered_attempts: tuple[_OrderedSearchAttemptDescriptor, ...],
    bundle: object,
    evaluator: object,
    bounds: list[tuple[float, float]],
    box_solver: BoxSolverPort | None,
    refiner: MpmathRefiner | None,
    runtime_budget: RuntimeBudget,
) -> _OrderedSearchAttemptSelection:
    primary_attempt = ordered_attempts[0]
    primary_outcome = _execute_ordered_search_attempt(
        attempt=primary_attempt,
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        box_solver=box_solver,
        refiner=refiner,
        runtime_budget=runtime_budget,
    )
    if (
        len(primary_outcome.completed_stage_state.phasec_result.accepted_candidates) > 0
        or len(ordered_attempts) == 1
    ):
        return _select_ordered_search_attempt_outcome(primary_outcome=primary_outcome)
    fallback_attempt = ordered_attempts[1]
    fallback_outcome = _execute_ordered_search_attempt(
        attempt=fallback_attempt,
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        box_solver=box_solver,
        refiner=refiner,
        runtime_budget=runtime_budget,
    )
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
    accepted_ids = {candidate.candidate_id for candidate in accepted_candidates}
    ordered = sorted(refined_candidates, key=lambda candidate: candidate.residual_norm_hp)
    debug_entries: list[dict[str, object]] = []
    for candidate in ordered[: max(0, int(limit))]:
        debug_entries.append(
            {
                "candidate_id": int(candidate.candidate_id),
                "stage": "phaseb",
                "hard_feasible": bool(candidate.hard_feasible),
                "validity_margin": (
                    None
                    if candidate.validity_margin_hp is None
                    else str(candidate.validity_margin_hp)
                ),
                "hard_violation_tags": list(candidate.hard_violation_tags),
                "refinement_status": candidate.refinement_status,
                "rejection_tag": (
                    None if candidate.candidate_id in accepted_ids else "rejected_by_phasec"
                ),
            }
        )
    return tuple(debug_entries)


def _run_external_pipeline_without_variables(
    evaluator: object,
    *,
    pipeline_config: ExternalPipelineConfig,
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
    phasec_answer_values: tuple[str, ...] = ()
    phasec_accepted_count = 0
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
            hard_feasible=guard_ok,
            hard_violation_tags=() if guard_ok else tuple(guard_violations),
            validity_margin_hp=None,
        )
        refined_candidates = (refined,)
        phasec_result = run_phasec_assembly(
            refined_candidates=refined_candidates,
            input_precision_dps=120,
            residual_threshold=mp.mpf(pipeline_config.acceptance_residual_threshold),
            acceptance_margin_ratio=mp.mpf(pipeline_config.acceptance_margin_ratio),
        )
        exact_results = phasec_result.exact_results
        phasec_answer_values = phasec_result.answer_values
        phasec_accepted_count = len(phasec_result.accepted_candidates)
        accepted_answers = tuple(
            candidate.answer_hp
            for candidate in phasec_result.accepted_candidates
            if candidate.answer_hp is not None
        )
        if phasec_result.accepted_candidates:
            selected_answer = phasec_result.accepted_candidates[0].answer_hp
    status = "success" if selected_answer is not None else "no_solution"
    summary = {
        "phase0": {
            "total_random_points": 1,
            "finite_residual_ratio": 1.0 if float_eval.is_finite else 0.0,
            "guard_pass_ratio": 1.0 if guard_ok else 0.0,
            "best_random_residual": float_eval.residual_norm_float if float_eval.is_finite else None,
            "best_random_point": [],
            "guard_violations": list(guard_violations),
        },
        "phasea": {
            "evaluation_count": 0,
            "failure_ratio": 0.0,
            "selected_candidates": 0,
            "all_record_count": 0,
            "guard_feasible_record_count": 0,
            "guard_feasible_ledger_count": 0,
            "compact_candidate_count": 0,
        },
        "phaseb": {
            "attempted_count": 1,
            "converged_count": 1 if selected_answer is not None else 0,
            "best_residual": str(hp_eval.residual_norm_hp),
            "solver_name": "direct_evaluation",
            "hard_feasible_count": 1 if selected_answer is not None else 0,
            "attempted_box_count": 0,
        },
        "phasec": {
            "accepted_count": phasec_accepted_count,
            "answer_values": list(phasec_answer_values),
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
    # Backward-compatible summary key retained for older benchmark readers.
    summary["phase_integer_fallback"] = summary["phase_discrete_completion"]
    accepted_candidate_ids = [
        int(candidate.candidate_id)
        for candidate in phasec_result.accepted_candidates
        if int(candidate.candidate_id) >= 0
    ]
    selected_candidate_id = accepted_candidate_ids[0] if accepted_candidate_ids else None
    summary["candidate_ledger"] = []
    summary["best_candidate_id"] = selected_candidate_id
    summary["answer_source_candidate_id"] = selected_candidate_id
    summary["residual_source_candidate_id"] = selected_candidate_id
    summary["answer_extraction_candidate_ids"] = accepted_candidate_ids
    summary["answer_candidates"] = accepted_candidate_ids
    summary["answer_candidate_values"] = list(phasec_answer_values)
    return ExternalPipelineResult(
        status=status,
        selected_answer=selected_answer,
        accepted_answers=accepted_answers,
        float_candidates=(),
        refined_candidates=refined_candidates,
        exact_results=exact_results,
        summary=summary,
    )


def run_external_pipeline(
    problem_ir: object,
    *,
    prefer_fast: bool = False,
    seed: int | None = None,
    nomad_config: NomadConfig | None = None,
    refiner: MpmathRefiner | None = None,
    pipeline_config: ExternalPipelineConfig | None = None,
    box_solver: BoxSolverPort | None = None,
) -> ExternalPipelineResult:
    """Execute external pipeline and return structured contract result.

    Args:
        refiner: Compatibility/debug-only refiner used when box-solver path is disabled.
    """
    if pipeline_config is not None and nomad_config is not None:
        raise ValueError("pipeline_config and nomad_config cannot be provided together")
    active_pipeline_config = (
        pipeline_config
        if pipeline_config is not None
        else (
            ExternalPipelineConfig.sanity_tier()
            if prefer_fast
            else ExternalPipelineConfig.standard_tier()
        )
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
    )
    active_box_solver = box_solver
    if active_pipeline_config.enable_box_solver and active_box_solver is None:
        active_box_solver = JuliaBoxSolver(
            precision_dps=int(active_pipeline_config.box_precision_dps),
            time_budget_sec=float(active_pipeline_config.box_time_budget_sec),
        )
    phaseb_refiner = refiner
    if not active_pipeline_config.enable_box_solver and phaseb_refiner is None:
        phaseb_refiner = _build_phaseb_refiner(active_pipeline_config)
    bundle = load_problem_bundle(problem_ir, prefer_fast=prefer_fast)
    evaluator = build_ir_evaluator(bundle)
    if len(bundle.var_names) == 0:
        return _run_external_pipeline_without_variables(
            evaluator,
            pipeline_config=active_pipeline_config,
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
        box_solver=active_box_solver,
        refiner=phaseb_refiner,
        runtime_budget=runtime_budget,
    )
    selected_attempt = attempt_selection.selected_outcome.attempt
    completed_stage_state = attempt_selection.selected_outcome.completed_stage_state
    phase0_result = completed_stage_state.phase0_result
    phasea_result = completed_stage_state.phasea_result
    phaseb_result = completed_stage_state.phaseb_result
    phasec_result = completed_stage_state.phasec_result
    phase_rescue_summary = completed_stage_state.phase_rescue_summary
    phase_integer_fallback_summary = completed_stage_state.phase_integer_fallback_summary
    summary = build_pipeline_summary(
        phase0_result=phase0_result,
        search_result=phasea_result,
        refinement_result=phaseb_result,
        assembly_result=phasec_result,
        phase_rescue_summary=phase_rescue_summary,
        phase_integer_fallback_summary=phase_integer_fallback_summary,
        debug_candidates=_build_debug_candidates(
            refined_candidates=phaseb_result.candidates,
            accepted_candidates=phasec_result.accepted_candidates,
            limit=selected_attempt.pipeline_config.candidate_debug_limit,
        ),
    )
    summary["phasea_staged_fallback"] = _build_staged_fallback_summary(
        selection=attempt_selection,
    )
    selected_answer = None
    accepted_answers = tuple(
        candidate.answer_hp
        for candidate in phasec_result.accepted_candidates
        if candidate.answer_hp is not None
    )
    accepted_candidate_ids = tuple(
        int(candidate.candidate_id) for candidate in phasec_result.accepted_candidates
    )
    if phasec_result.accepted_candidates:
        selected_answer = phasec_result.accepted_candidates[0].answer_hp
    status = "success" if selected_answer is not None else "no_solution"
    return ExternalPipelineResult(
        status=status,
        selected_answer=selected_answer,
        accepted_answers=accepted_answers,
        float_candidates=phasea_result.candidates,
        refined_candidates=phaseb_result.candidates,
        exact_results=phasec_result.exact_results,
        summary=summary,
        accepted_candidate_ids=accepted_candidate_ids,
    )
