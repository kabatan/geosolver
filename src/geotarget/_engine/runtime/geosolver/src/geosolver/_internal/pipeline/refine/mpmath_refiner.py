"""mpmath-based staged local refiner (compatibility/debugging only)."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
import time
from functools import partial

from mpmath import mp

from geosolver._internal.autosolve.execution.interpreter_hp_helpers import to_mpf_value
from geosolver._internal.autosolve.execution.interpreter_modes import (
    _build_solution_context_high_precision,
)
from geosolver._internal.pipeline.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver._internal.pipeline.contracts.evaluator_port import EvaluatorPort
from geosolver._internal.pipeline.contracts.local_refiner_port import LocalRefinerPort
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import EvaluationStatus
from geosolver._internal.autosolve.compile.infer_bounds import infer_bound_expansion_locks
from geosolver._internal.pipeline.problem.infer_problem_bounds import infer_problem_bounds
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver._internal.solver.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver.ir.compiler import safe_eval_expr_hp

from .deduplicate_refined_candidates import deduplicate_refined_candidates
from .finite_difference_jacobian import compute_finite_difference_jacobian
from .levenberg_marquardt_step import compute_levenberg_marquardt_step
from .line_search import _point_within_bounds, run_line_search
from .refiner_config import RefinerConfig

NON_FINITE_INITIAL = "non_finite_initial"
BRANCH_INSTABILITY = "branch_instability"
LINE_SEARCH_FAILED = "line_search_failed"
STALLED = "stalled"
TARGET_REACHED = "target_reached"
MAX_ITERS = "max_iters"
INTEGER_CLOSURE_PHASE = "integer_closure"


def _vector_norm(values: list[MPFloat]) -> MPFloat:
    return mp.sqrt(mp.fsum(value * value for value in values))


@dataclass(frozen=True)
class IntegerConstraintSpec:
    """Top-level zero-target ``IsInteger`` constraint metadata."""

    constraint_index: int
    inner_expression: str


@dataclass(frozen=True)
class IntegerConstraintClosure:
    """Linearized target for one top-level ``IsInteger`` constraint."""

    constraint_index: int
    inner_expression: str
    target_integer: MPFloat


@dataclass(frozen=True)
class ProjectedIntegerObservation:
    """Projected non-integer-manifold sample with integer observations."""

    point: tuple[MPFloat, ...]
    integer_values: tuple[MPFloat, ...]


def _closure_start_threshold(config: RefinerConfig, dps: int) -> MPFloat:
    return max(
        mp.mpf(config.stage_tolerance),
        mp.mpf(config.promotion_threshold_for_dps(dps)),
    )


def _evaluate_hard_feasibility(
    evaluator: EvaluatorPort,
    point: list[MPFloat],
    precision: int,
) -> object:
    with high_precision_mode():
        return evaluator.evaluate_hp_hard_feasibility(
            point,
            precision=int(precision),
        )


def _is_zero_target(target: object) -> bool:
    """Return whether the target is numerically zero."""

    if isinstance(target, str):
        return target.strip() == "0"
    try:
        return mp.mpf(target) == mp.mpf("0")
    except Exception:
        return False


def _extract_isinteger_inner_expression(constraint_expression: str) -> str | None:
    """Extract the inner expression from an ``IsInteger(inner)`` constraint."""

    try:
        parsed = ast.parse(constraint_expression, mode="eval")
    except SyntaxError:
        return None
    call = parsed.body
    if not isinstance(call, ast.Call):
        return None
    if call.keywords or len(call.args) != 1:
        return None
    if not isinstance(call.func, ast.Name) or call.func.id != "IsInteger":
        return None
    return ast.unparse(call.args[0])


def _integer_closure_candidate_id(base_candidate_id: int) -> int:
    """Derive a stable negative id for closure-derived candidates."""

    return -abs(int(base_candidate_id)) - 1


def _integer_target_tuple_candidate_id(
    base_candidate_id: int,
    target_integers: tuple[MPFloat, ...],
) -> int:
    """Derive a stable negative id for one explicit integer-target tuple."""

    encoded = abs(int(base_candidate_id)) + 1
    for target in target_integers:
        integer_value = int(mp.nint(target))
        sign_bit = 1 if integer_value < 0 else 0
        magnitude = abs(integer_value)
        encoded = encoded * 1_000_003 + magnitude * 2 + sign_bit
    return -encoded


def _build_hp_context(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    dps: int,
) -> dict[str, object]:
    """Build the high-precision evaluation context for one point."""

    return _build_solution_context_high_precision(
        bundle.spec,
        list(bundle.var_names),
        list(point),
        dict(bundle.base_context),
        int(dps),
    )


def build_integer_constraint_specs(
    *,
    bundle: ProblemBundle,
) -> tuple[IntegerConstraintSpec, ...]:
    """Return all top-level zero-target ``IsInteger`` constraints."""

    specs: list[IntegerConstraintSpec] = []
    for index, constraint_expression in enumerate(bundle.spec.constraints):
        if index >= len(bundle.targets) or not _is_zero_target(bundle.targets[index]):
            continue
        inner_expression = _extract_isinteger_inner_expression(constraint_expression)
        if inner_expression is None:
            continue
        specs.append(
            IntegerConstraintSpec(
                constraint_index=index,
                inner_expression=inner_expression,
            )
        )
    return tuple(specs)


def evaluate_integer_constraint_values(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    specs: tuple[IntegerConstraintSpec, ...],
    dps: int,
) -> tuple[MPFloat, ...] | None:
    """Evaluate top-level integer-constraint inner expressions at one point."""

    if not specs:
        return ()
    if len(point) != len(bundle.var_names):
        return None
    try:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                context = _build_hp_context(bundle=bundle, point=point, dps=int(dps))
                values: list[MPFloat] = []
                for spec in specs:
                    raw_value = safe_eval_expr_hp(spec.inner_expression, context)
                    values.append(
                        mp.mpf(
                            to_mpf_value(
                                raw_value,
                                precision=int(dps),
                                context=f"integer_constraint_value:{spec.constraint_index}",
                            )
                        )
                    )
        return tuple(values)
    except Exception:
        return None


def build_integer_constraint_closures_from_targets(
    *,
    specs: tuple[IntegerConstraintSpec, ...],
    target_integers: tuple[MPFloat, ...],
) -> tuple[IntegerConstraintClosure, ...]:
    """Build explicit closure targets for top-level integer constraints."""

    if len(specs) != len(target_integers):
        raise ValueError("integer target count must match integer constraint count")
    closures: list[IntegerConstraintClosure] = []
    for spec, target in zip(specs, target_integers, strict=True):
        closures.append(
            IntegerConstraintClosure(
                constraint_index=spec.constraint_index,
                inner_expression=spec.inner_expression,
                target_integer=mp.mpf(mp.nint(target)),
            )
        )
    return tuple(closures)


def _build_integer_constraint_closures(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    dps: int,
) -> tuple[IntegerConstraintClosure, ...]:
    """Build nearest-integer closure targets for top-level IsInteger constraints."""

    specs = build_integer_constraint_specs(bundle=bundle)
    values = evaluate_integer_constraint_values(
        bundle=bundle,
        point=point,
        specs=specs,
        dps=int(dps),
    )
    if values is None:
        return ()
    return build_integer_constraint_closures_from_targets(
        specs=specs,
        target_integers=values,
    )


def _evaluate_integer_closure_residuals(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    closures: tuple[IntegerConstraintClosure, ...],
    dps: int,
) -> dict[int, MPFloat] | None:
    """Evaluate linearized residuals for IsInteger closures."""

    if not closures:
        return {}
    try:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                context = _build_hp_context(bundle=bundle, point=point, dps=int(dps))
                overrides: dict[int, MPFloat] = {}
                for closure in closures:
                    raw_value = safe_eval_expr_hp(closure.inner_expression, context)
                    inner_value = mp.mpf(
                        to_mpf_value(
                            raw_value,
                            precision=int(dps),
                            context=f"integer_closure_residual:{closure.constraint_index}",
                        )
                    )
                    overrides[closure.constraint_index] = inner_value - closure.target_integer
        return overrides
    except Exception:
        return None


def _residual_vector_without_integer_constraints(
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    point: list[MPFloat],
    dps: int,
    *,
    integer_constraint_indices: tuple[int, ...],
) -> list[MPFloat] | None:
    """Evaluate residuals with top-level integer constraints removed."""

    with mp.workdps(int(dps)):
        with high_precision_mode():
            hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
    if hp_eval.evaluation_status is not EvaluationStatus.OK:
        return None
    skipped = set(int(index) for index in integer_constraint_indices)
    residuals = [
        mp.mpf(value)
        for index, value in enumerate(hp_eval.residual_vector)
        if index not in skipped
    ]
    if not residuals:
        return None
    return residuals


def _normalize_findroot_point(root: object) -> list[MPFloat] | None:
    if isinstance(root, mp.matrix):
        values = [mp.mpf(root[index]) for index in range(len(root))]
        return values
    if isinstance(root, (list, tuple)):
        return [mp.mpf(value) for value in root]
    try:
        return [mp.mpf(root)]
    except (TypeError, ValueError):
        return None


def _convert_problem_bounds(
    bundle: ProblemBundle,
) -> tuple[tuple[MPFloat | None, MPFloat | None], ...]:
    bounds = infer_problem_bounds(bundle)
    locks = infer_bound_expansion_locks(
        bundle.spec,
        bundle.var_names,
        bundle.base_context,
    )
    return tuple(
        (
            (
                boundary_float_to_mpf(lower, origin=BoundaryOrigin.LEGACY_BOUND)
                if lower_locked
                else None
            ),
            (
                boundary_float_to_mpf(upper, origin=BoundaryOrigin.LEGACY_BOUND)
                if upper_locked
                else None
            ),
        )
        for (lower, upper), (lower_locked, upper_locked) in zip(bounds, locks, strict=True)
    )


def _run_findroot_closure(
    *,
    evaluator: EvaluatorPort,
    start_point: list[MPFloat],
    bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
    dps: int,
    target_residual: MPFloat,
    max_steps: int,
) -> tuple[list[MPFloat], MPFloat] | None:
    if len(start_point) == 0:
        return None

    if len(start_point) == 1:
        def scalar_residual(arg: MPFloat) -> MPFloat:
            point = [mp.mpf(arg)]
            with mp.workdps(int(dps)):
                with high_precision_mode():
                    hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
            if hp_eval.evaluation_status is not EvaluationStatus.OK:
                raise ValueError(f"findroot residual status={hp_eval.evaluation_status.value}")
            return mp.mpf(hp_eval.residual_vector[0])

        try:
            with mp.workdps(int(dps)):
                root = mp.findroot(
                    scalar_residual,
                    mp.mpf(start_point[0]),
                    solver="secant",
                    tol=mp.mpf(target_residual),
                    maxsteps=int(max_steps),
                )
        except (ValueError, ZeroDivisionError):
            return None
        with mp.workdps(int(dps)):
            normalized = [mp.mpf(root)]
    else:
        def residuals(*args: MPFloat) -> tuple[MPFloat, ...]:
            point = [mp.mpf(value) for value in args]
            with mp.workdps(int(dps)):
                with high_precision_mode():
                    hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
            if hp_eval.evaluation_status is not EvaluationStatus.OK:
                raise ValueError(f"findroot residual status={hp_eval.evaluation_status.value}")
            return tuple(mp.mpf(value) for value in hp_eval.residual_vector)

        try:
            with mp.workdps(int(dps)):
                root = mp.findroot(
                    residuals,
                    tuple(start_point),
                    solver="mnewton",
                    tol=mp.mpf(target_residual),
                    maxsteps=int(max_steps),
                )
        except (ValueError, ZeroDivisionError):
            return None

        with mp.workdps(int(dps)):
            normalized = _normalize_findroot_point(root)
    if normalized is None or len(normalized) != len(start_point):
        return None
    if not _point_within_bounds(normalized, bounds):
        return None
    with mp.workdps(int(dps)):
        with high_precision_mode():
            hp_eval = evaluator.evaluate_hp_residual(normalized, precision=int(dps))
    if hp_eval.evaluation_status is not EvaluationStatus.OK:
        return None
    return normalized, _vector_norm([mp.mpf(value) for value in hp_eval.residual_vector])


@dataclass(frozen=True)
class MpmathRefiner(LocalRefinerPort):
    """Compatibility/debug-only local refiner using staged LM at high precision."""

    config: RefinerConfig = RefinerConfig()

    def refine_candidates(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidates: tuple[FloatCandidate, ...],
        deadline_monotonic: float | None = None,
    ) -> RefinementBatchResult:
        bounds = _convert_problem_bounds(bundle)
        refined_list: list[RefinedCandidate] = []
        attempted_count = 0
        for candidate in candidates:
            if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
                break
            attempted_count += 1
            refined_list.extend(
                self._refine_single_candidate(
                    bundle=bundle,
                    evaluator=evaluator,
                    candidate=candidate,
                    bounds=bounds,
                )
            )
        refined = tuple(refined_list)
        deduped = deduplicate_refined_candidates(
            candidates=refined,
            tolerance=mp.mpf(self.config.dedup_answer_tolerance),
        )
        converged_count = sum(
            1 for candidate in deduped if candidate.refinement_status == TARGET_REACHED
        )
        return RefinementBatchResult(
            candidates=deduped,
            converged_count=converged_count,
            attempted_count=attempted_count,
            solver_name="mpmath_refiner",
            hard_feasible_count=sum(1 for candidate in deduped if candidate.hard_feasible),
            attempted_box_count=0,
        )

    def refine_candidate_with_integer_targets(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        target_integers: tuple[MPFloat, ...],
        start_point: tuple[MPFloat, ...] | None = None,
    ) -> RefinedCandidate | None:
        """Run the explicit integer-closure path for one audited target tuple."""

        specs = build_integer_constraint_specs(bundle=bundle)
        if not specs or len(specs) != len(target_integers):
            return None
        bounds = _convert_problem_bounds(bundle)
        if start_point is None:
            current = [
                boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
                for value in candidate.x_float
            ]
        else:
            current = [mp.mpf(value) for value in start_point]
        closures = build_integer_constraint_closures_from_targets(
            specs=specs,
            target_integers=target_integers,
        )
        closure_status, closure_point, closure_answer_dps, closure_history = self._run_integer_closure_path(
            bundle=bundle,
            evaluator=evaluator,
            start_point=current,
            bounds=bounds,
            preserve_hard_feasibility=bool(candidate.hard_feasible),
            integer_closures=closures,
        )
        closure_point, closure_history, closure_status, closure_answer_dps = self._apply_post_lm_closure_polish(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            point=closure_point,
            phase_history=closure_history,
            stage_status=closure_status,
            answer_dps=closure_answer_dps,
        )
        return self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=closure_point,
            phase_history=closure_history,
            stage_status=closure_status,
            candidate_id=_integer_target_tuple_candidate_id(
                int(candidate.candidate_id),
                tuple(mp.mpf(target) for target in target_integers),
            ),
            answer_dps=closure_answer_dps,
        )

    def project_point_to_noninteger_constraint_manifold(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        start_point: tuple[MPFloat, ...],
        dps: int,
    ) -> ProjectedIntegerObservation | None:
        """Project a deterministic sample toward the non-integer manifold."""

        specs = build_integer_constraint_specs(bundle=bundle)
        if not specs:
            return None
        integer_constraint_indices = tuple(
            int(spec.constraint_index)
            for spec in specs
        )
        residual_fn = partial(
            _residual_vector_without_integer_constraints,
            bundle,
            evaluator,
            integer_constraint_indices=integer_constraint_indices,
        )
        bounds = _convert_problem_bounds(bundle)
        current = [mp.mpf(value) for value in start_point]
        stage_status, projected_point, projected_norm = self._run_stage(
            bundle=bundle,
            evaluator=evaluator,
            start_point=current,
            bounds=bounds,
            dps=int(dps),
            target_residual=mp.mpf(self.config.target_for_dps(int(dps))),
            preserve_hard_feasibility=False,
            residual_fn=residual_fn,
        )
        _ = stage_status
        projection_threshold = _closure_start_threshold(self.config, int(dps))
        if projected_norm > projection_threshold:
            return None
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            projected_point,
            int(dps),
        )
        if not hard_snapshot.hard_feasible:
            return None
        integer_values = evaluate_integer_constraint_values(
            bundle=bundle,
            point=projected_point,
            specs=specs,
            dps=int(dps),
        )
        if integer_values is None or len(integer_values) != len(specs):
            return None
        return ProjectedIntegerObservation(
            point=tuple(projected_point),
            integer_values=tuple(integer_values),
        )

    def _residual_vector_for_stage(
        self,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        dps: int,
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
    ) -> list[MPFloat] | None:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        residuals = [mp.mpf(value) for value in hp_eval.residual_vector]
        if not integer_closures:
            return residuals
        overrides = _evaluate_integer_closure_residuals(
            bundle=bundle,
            point=point,
            closures=integer_closures,
            dps=int(dps),
        )
        if overrides is None:
            return None
        for closure in integer_closures:
            residuals[closure.constraint_index] = mp.mpf(overrides[closure.constraint_index])
        return residuals

    def _evaluate_answer(
        self,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        dps: int,
    ) -> MPFloat | None:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                answer_eval = evaluator.evaluate_answer_hp(point, precision=int(dps))
        if answer_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        return answer_eval.answer_hp

    def _run_stage(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        start_point: list[MPFloat],
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        dps: int,
        target_residual: MPFloat,
        preserve_hard_feasibility: bool,
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
        residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None] | None = None,
    ) -> tuple[str, list[MPFloat], MPFloat]:
        if residual_fn is None:
            residual_fn = partial(
                self._residual_vector_for_stage,
                bundle,
                evaluator,
                integer_closures=integer_closures,
            )
        current = [mp.mpf(value) for value in start_point]
        current_vec = residual_fn(current, int(dps))
        if current_vec is None:
            return NON_FINITE_INITIAL, current, mp.inf
        current_norm = _vector_norm(current_vec)
        best = [mp.mpf(value) for value in current]
        best_norm = current_norm
        damping = mp.mpf(self.config.damping_initial)
        damping_min = mp.mpf(self.config.damping_min)
        damping_scale = mp.mpf(self.config.damping_scale)
        stage_tolerance = mp.mpf(self.config.stage_tolerance)
        stalled_count = 0
        line_failures = 0
        status = MAX_ITERS
        trial_filter = None
        if preserve_hard_feasibility:
            trial_filter = lambda trial, trial_dps: _evaluate_hard_feasibility(
                evaluator,
                trial,
                trial_dps,
            ).hard_feasible
        for _ in range(int(self.config.max_stage_iters)):
            if best_norm <= target_residual:
                status = TARGET_REACHED
                break
            jacobian = compute_finite_difference_jacobian(
                point=current,
                dps=int(dps),
                residual_fn=residual_fn,
            )
            if jacobian is None:
                status = BRANCH_INSTABILITY
                break
            step = compute_levenberg_marquardt_step(
                jacobian=jacobian,
                residual_vector=current_vec,
                damping=damping,
            )
            trial, trial_vec, improved = run_line_search(
                point=current,
                current_norm=current_norm,
                step=step,
                dps=int(dps),
                max_steps=int(self.config.line_search_max_steps),
                residual_fn=residual_fn,
                bounds=bounds,
                trial_filter=trial_filter,
            )
            if (
                not improved
                and preserve_hard_feasibility
                and integer_closures
            ):
                trial, trial_vec, improved = run_line_search(
                    point=current,
                    current_norm=current_norm,
                    step=step,
                    dps=int(dps),
                    max_steps=int(self.config.line_search_max_steps),
                    residual_fn=residual_fn,
                    bounds=bounds,
                    trial_filter=None,
                )
            if improved and trial_vec is not None:
                trial_norm = _vector_norm(trial_vec)
                improvement = (current_norm - trial_norm) / max(
                    abs(current_norm),
                    mp.mpf("1e-30"),
                )
                current = [mp.mpf(value) for value in trial]
                current_vec = [mp.mpf(value) for value in trial_vec]
                current_norm = trial_norm
                if trial_norm < best_norm:
                    best = [mp.mpf(value) for value in current]
                    best_norm = trial_norm
                damping = max(damping_min, damping / damping_scale)
                line_failures = 0
                if improvement < stage_tolerance:
                    stalled_count += 1
                else:
                    stalled_count = 0
                if stalled_count >= int(self.config.stall_limit):
                    status = STALLED
                    break
            else:
                damping *= damping_scale
                line_failures += 1
                if line_failures >= int(self.config.line_search_failure_limit):
                    status = LINE_SEARCH_FAILED
                    break
        if status == MAX_ITERS and best_norm <= target_residual:
            status = TARGET_REACHED
        return status, best, best_norm

    def _build_refined_candidate(
        self,
        *,
        bundle: ProblemBundle,
        candidate: FloatCandidate,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        phase_history: tuple[str, ...],
        stage_status: str,
        candidate_id: int,
        answer_dps: int,
    ) -> RefinedCandidate:
        final_vector = self._residual_vector_for_stage(
            bundle=bundle,
            evaluator=evaluator,
            point=point,
            dps=int(answer_dps),
        )
        if final_vector is None:
            final_norm = mp.inf
        else:
            final_norm = _vector_norm(final_vector)
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            point,
            int(answer_dps),
        )
        answer = self._evaluate_answer(
            evaluator=evaluator,
            point=point,
            dps=int(answer_dps),
        )
        return RefinedCandidate(
            x_hp=tuple(point),
            residual_norm_hp=final_norm,
            answer_hp=answer,
            refinement_status=stage_status,
            phase_history=phase_history,
            source=candidate,
            candidate_id=int(candidate_id),
            hard_feasible=hard_snapshot.hard_feasible,
            hard_violation_tags=tuple(hard_snapshot.failure_tags),
            validity_margin_hp=hard_snapshot.min_margin,
        )


    def _direct_accept_candidate(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        point: list[MPFloat],
    ) -> RefinedCandidate | None:
        """Accept already-good high precision candidates without finite-difference LM.

        Phase C already defines a residual/hard-feasibility gate for accepted
        answers.  When Phase A has produced a point that passes the same gate at
        high precision, running a full staged finite-difference LM pass only
        burns time and can even destabilize near singular but already acceptable
        isolated candidates.  This shortcut is intentionally problem-agnostic:
        it depends only on the residual norm and hard feasibility, not on a case
        id or benchmark-specific failure mode.
        """
        raw_threshold = self.config.direct_accept_residual
        if raw_threshold is None:
            return None
        try:
            threshold = mp.mpf(raw_threshold)
        except Exception:
            return None
        if threshold <= mp.mpf("0"):
            return None
        scheduled_dps = max((int(stage) for stage in self.config.schedule_dps), default=120)
        direct_dps = max(int(self.config.direct_accept_dps), scheduled_dps)
        final_vector = self._residual_vector_for_stage(
            bundle=bundle,
            evaluator=evaluator,
            point=point,
            dps=direct_dps,
        )
        if final_vector is None:
            return None
        final_norm = _vector_norm(final_vector)
        if not mp.isfinite(final_norm) or final_norm >= threshold:
            return None
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            point,
            direct_dps,
        )
        if not hard_snapshot.hard_feasible:
            return None
        return self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=point,
            phase_history=(f"direct:{direct_dps}:{final_norm}",),
            stage_status="direct_evaluation",
            candidate_id=int(candidate.candidate_id),
            answer_dps=direct_dps,
        )

    def _apply_post_lm_closure_polish(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        point: list[MPFloat],
        phase_history: tuple[str, ...],
        stage_status: str,
        answer_dps: int,
    ) -> tuple[list[MPFloat], tuple[str, ...], str, int]:
        current = [mp.mpf(value) for value in point]
        history = list(phase_history)
        final_dps = int(max(self.config.schedule_dps))
        final_vector = self._residual_vector_for_stage(
            bundle=bundle,
            evaluator=evaluator,
            point=current,
            dps=final_dps,
        )
        if final_vector is None:
            return current, tuple(history), stage_status, answer_dps
        final_norm = _vector_norm(final_vector)
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            current,
            final_dps,
        )
        closure_threshold = _closure_start_threshold(self.config, final_dps)
        if (
            not hard_snapshot.hard_feasible
            or len(final_vector) < len(current)
            or final_norm > closure_threshold
        ):
            return current, tuple(history), stage_status, answer_dps
        closure_stages = tuple(
            int(stage)
            for stage in self.config.closure_schedule_dps
            if int(stage) >= final_dps
        )
        for closure_dps in closure_stages:
            closed = _run_findroot_closure(
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=closure_dps,
                target_residual=mp.mpf(self.config.target_for_dps(closure_dps)),
                max_steps=int(self.config.max_stage_iters),
            )
            if closed is None:
                continue
            closed_point, closed_norm = closed
            closed_hard_snapshot = _evaluate_hard_feasibility(
                evaluator,
                closed_point,
                closure_dps,
            )
            if not closed_hard_snapshot.hard_feasible or closed_norm >= final_norm:
                continue
            current = closed_point
            final_vector = self._residual_vector_for_stage(
                bundle=bundle,
                evaluator=evaluator,
                point=current,
                dps=closure_dps,
            )
            final_norm = closed_norm
            answer_dps = closure_dps
            stage_status = TARGET_REACHED
            history.append(f"{closure_dps}:findroot:{closed_norm}")
        return current, tuple(history), stage_status, answer_dps

    def _run_integer_closure_path(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        start_point: list[MPFloat],
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        preserve_hard_feasibility: bool,
        integer_closures: tuple[IntegerConstraintClosure, ...],
    ) -> tuple[str, list[MPFloat], int, tuple[str, ...]]:
        current = [mp.mpf(value) for value in start_point]
        history: list[str] = []
        target_summary = ",".join(
            f"{closure.constraint_index}:{closure.target_integer}"
            for closure in integer_closures
        )
        history.append(f"{INTEGER_CLOSURE_PHASE}:targets:{target_summary}")
        stage_status = MAX_ITERS
        answer_dps = int(max(self.config.schedule_dps))
        for dps in self.config.schedule_dps:
            target = mp.mpf(self.config.target_for_dps(int(dps)))
            promotion_threshold = mp.mpf(self.config.promotion_threshold_for_dps(int(dps)))
            stage_status, current, stage_norm = self._run_stage(
                bundle=bundle,
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=int(dps),
                target_residual=target,
                preserve_hard_feasibility=preserve_hard_feasibility,
                integer_closures=integer_closures,
            )
            answer_dps = int(dps)
            history.append(f"{INTEGER_CLOSURE_PHASE}:{dps}:{stage_status}:{stage_norm}")
            if stage_norm <= target:
                continue
            if stage_norm <= promotion_threshold:
                history.append(f"{INTEGER_CLOSURE_PHASE}:{dps}:promote:{stage_norm}")
                continue
            if stage_status != TARGET_REACHED:
                break
        return stage_status, current, answer_dps, tuple(history)

    def _refine_single_candidate(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
    ) -> tuple[RefinedCandidate, ...]:
        current = [
            boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
            for value in candidate.x_float
        ]
        direct_candidate = self._direct_accept_candidate(
            bundle=bundle,
            evaluator=evaluator,
            candidate=candidate,
            point=current,
        )
        if direct_candidate is not None:
            return (direct_candidate,)
        history: list[str] = []
        stage_status = MAX_ITERS
        for dps in self.config.schedule_dps:
            target = mp.mpf(self.config.target_for_dps(int(dps)))
            promotion_threshold = mp.mpf(self.config.promotion_threshold_for_dps(int(dps)))
            stage_status, current, stage_norm = self._run_stage(
                bundle=bundle,
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=int(dps),
                target_residual=target,
                preserve_hard_feasibility=bool(candidate.hard_feasible),
            )
            history.append(f"{dps}:{stage_status}:{stage_norm}")
            if stage_norm <= target:
                continue
            if stage_norm <= promotion_threshold:
                history.append(f"{dps}:promote:{stage_norm}")
                continue
            if stage_status != TARGET_REACHED:
                break
        final_dps = int(max(self.config.schedule_dps))
        answer_dps = final_dps
        current, phase_history, stage_status, answer_dps = self._apply_post_lm_closure_polish(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            point=current,
            phase_history=tuple(history),
            stage_status=stage_status,
            answer_dps=answer_dps,
        )
        primary_candidate = self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=current,
            phase_history=phase_history,
            stage_status=stage_status,
            candidate_id=int(candidate.candidate_id),
            answer_dps=answer_dps,
        )
        results: list[RefinedCandidate] = [primary_candidate]
        if stage_status == TARGET_REACHED:
            return tuple(results)
        closures = _build_integer_constraint_closures(
            bundle=bundle,
            point=current,
            dps=final_dps,
        )
        if not closures:
            return tuple(results)
        closure_status, closure_point, closure_answer_dps, closure_history = self._run_integer_closure_path(
            bundle=bundle,
            evaluator=evaluator,
            start_point=current,
            bounds=bounds,
            preserve_hard_feasibility=primary_candidate.hard_feasible,
            integer_closures=closures,
        )
        closure_candidate = self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=closure_point,
            phase_history=tuple(history) + closure_history,
            stage_status=closure_status,
            candidate_id=_integer_closure_candidate_id(int(candidate.candidate_id)),
            answer_dps=closure_answer_dps,
        )
        if closure_candidate.residual_norm_hp < primary_candidate.residual_norm_hp:
            results.append(closure_candidate)
        return tuple(results)

