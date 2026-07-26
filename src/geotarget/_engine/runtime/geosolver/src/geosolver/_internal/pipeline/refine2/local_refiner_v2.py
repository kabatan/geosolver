"""QR/SVD local refiner with MpmathRefiner fallback."""

from __future__ import annotations

from dataclasses import dataclass
import time

from mpmath import mp

from geosolver._internal.pipeline.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver._internal.pipeline.contracts.evaluator_port import EvaluatorPort
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import EvaluationStatus
from geosolver._internal.pipeline.refine.deduplicate_refined_candidates import (
    deduplicate_refined_candidates,
)
from geosolver._internal.pipeline.refine.finite_difference_jacobian import (
    compute_finite_difference_jacobian,
)
from geosolver._internal.pipeline.refine.mpmath_refiner import MpmathRefiner, TARGET_REACHED
from geosolver._internal.pipeline.refine.refiner_config import RefinerConfig
from geosolver._internal.solver.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat

from .linear_solvers import compute_qr_svd_damped_step


_SOLVER_NAME = "local_refiner_v2_qr_svd"
_FALLBACK_SOLVER_NAME = "local_refiner_v2_qr_svd+mpmath_fallback"


def _convert_bounds(bundle: ProblemBundle) -> tuple[tuple[MPFloat, MPFloat], ...]:
    bounds = bundle.spec.bounds or []
    converted: list[tuple[MPFloat, MPFloat]] = []
    for index, _name in enumerate(bundle.var_names):
        if index < len(bounds) and bounds[index] is not None:
            lower, upper = bounds[index]  # type: ignore[misc]
            converted.append((mp.mpf(str(lower)), mp.mpf(str(upper))))
        else:
            converted.append((mp.mpf("-inf"), mp.mpf("inf")))
    return tuple(converted)


def _clamp_to_bounds(
    point: list[MPFloat],
    bounds: tuple[tuple[MPFloat, MPFloat], ...],
) -> list[MPFloat]:
    clamped: list[MPFloat] = []
    for index, value in enumerate(point):
        lower, upper = bounds[index]
        if mp.isfinite(lower) and value < lower:
            clamped.append(lower)
        elif mp.isfinite(upper) and value > upper:
            clamped.append(upper)
        else:
            clamped.append(mp.mpf(value))
    return clamped


@dataclass(frozen=True)
class LocalRefinerV2:
    """Damped QR/SVD Gauss-Newton refiner.

    This refiner is opt-in and falls back to MpmathRefiner for candidates it
    cannot improve to the configured acceptance threshold.
    """

    config: RefinerConfig = RefinerConfig()
    fallback_refiner: MpmathRefiner | None = None

    def _fallback(self) -> MpmathRefiner:
        return self.fallback_refiner or MpmathRefiner(config=self.config)

    def _residual_fn(
        self,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        dps: int,
    ) -> list[MPFloat] | None:
        try:
            with high_precision_mode():
                evaluated = evaluator.evaluate_hp_residual(point, precision=int(dps))
        except Exception:
            return None
        if evaluated.evaluation_status is not EvaluationStatus.OK:
            return None
        return list(evaluated.residual_vector)

    def _refine_one(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        deadline_monotonic: float | None,
    ) -> RefinedCandidate | None:
        if not candidate.x_float:
            return None
        bounds = _convert_bounds(bundle)
        point = [mp.mpf(str(value)) for value in candidate.x_float]
        best_point = list(point)
        best_norm = mp.inf
        phase_history: list[str] = []
        with high_precision_mode():
            for dps in self.config.schedule_dps:
                target = mp.mpf(self.config.target_for_dps(int(dps)))
                damping = mp.mpf(self.config.damping_initial)
                with mp.workdps(int(dps)):
                    for iteration in range(int(self.config.max_stage_iters)):
                        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                            return None
                        evaluated = evaluator.evaluate_hp_residual(point, precision=int(dps))
                        if evaluated.evaluation_status is not EvaluationStatus.OK:
                            return None
                        residual_norm = mp.mpf(evaluated.residual_norm_hp)
                        if residual_norm < best_norm:
                            best_norm = residual_norm
                            best_point = list(point)
                        phase_history.append(f"qr_svd:{dps}:iter={iteration}:residual={residual_norm}")
                        if residual_norm <= target:
                            return self._build_candidate(
                                bundle=bundle,
                                evaluator=evaluator,
                                source=candidate,
                                point=point,
                                residual_norm=residual_norm,
                                phase_history=tuple(phase_history),
                                status=TARGET_REACHED,
                                dps=int(dps),
                            )
                        jacobian = compute_finite_difference_jacobian(
                            point=point,
                            dps=int(dps),
                            residual_fn=lambda values, precision: self._residual_fn(
                                evaluator,
                                values,
                                precision,
                            ),
                        )
                        if jacobian is None:
                            return None
                        step = compute_qr_svd_damped_step(
                            jacobian=jacobian,
                            residual_vector=evaluated.residual_vector,
                            damping=damping,
                        )
                        if not step or all(abs(value) <= mp.mpf("1e-40") for value in step):
                            return None
                        trial = _clamp_to_bounds(
                            [mp.mpf(value) + step[index] for index, value in enumerate(point)],
                            bounds,
                        )
                        trial_eval = evaluator.evaluate_hp_residual(trial, precision=int(dps))
                        if (
                            trial_eval.evaluation_status is EvaluationStatus.OK
                            and trial_eval.residual_norm_hp < residual_norm
                        ):
                            point = trial
                            damping = max(mp.mpf(self.config.damping_min), damping / mp.mpf("4"))
                        else:
                            damping *= mp.mpf(self.config.damping_scale)
            if mp.isfinite(best_norm):
                return self._build_candidate(
                    bundle=bundle,
                    evaluator=evaluator,
                    source=candidate,
                    point=best_point,
                    residual_norm=best_norm,
                    phase_history=tuple(phase_history),
                    status="stalled",
                    dps=int(self.config.schedule_dps[-1]),
                )
        return None

    def _build_candidate(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        source: FloatCandidate,
        point: list[MPFloat],
        residual_norm: MPFloat,
        phase_history: tuple[str, ...],
        status: str,
        dps: int,
    ) -> RefinedCandidate:
        with high_precision_mode():
            answer_eval = evaluator.evaluate_answer_hp(point, precision=int(dps))
            hard_snapshot = evaluator.evaluate_hp_hard_feasibility(point, precision=int(dps))
        answer_hp = (
            answer_eval.answer_hp
            if answer_eval.evaluation_status is EvaluationStatus.OK
            else None
        )
        return RefinedCandidate(
            x_hp=tuple(point),
            residual_norm_hp=mp.mpf(residual_norm),
            answer_hp=answer_hp,
            refinement_status=status,
            phase_history=phase_history,
            source=source,
            candidate_id=source.candidate_id,
            hard_feasible=bool(hard_snapshot.ok),
            hard_violation_tags=tuple(hard_snapshot.violation_tags),
            validity_margin_hp=hard_snapshot.validity_margin,
        )

    def refine_candidates(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidates: tuple[FloatCandidate, ...],
        deadline_monotonic: float | None = None,
    ) -> RefinementBatchResult:
        refined: list[RefinedCandidate] = []
        fallback_candidates: list[FloatCandidate] = []
        attempted_count = 0
        for candidate in candidates:
            if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
                break
            attempted_count += 1
            candidate_result = self._refine_one(
                bundle=bundle,
                evaluator=evaluator,
                candidate=candidate,
                deadline_monotonic=deadline_monotonic,
            )
            if candidate_result is None or candidate_result.refinement_status != TARGET_REACHED:
                fallback_candidates.append(candidate)
            if candidate_result is not None:
                refined.append(candidate_result)
        fallback_result = None
        if fallback_candidates:
            fallback_result = self._fallback().refine_candidates(
                bundle=bundle,
                evaluator=evaluator,
                candidates=tuple(fallback_candidates),
                deadline_monotonic=deadline_monotonic,
            )
            refined.extend(fallback_result.candidates)
        deduped = deduplicate_refined_candidates(
            candidates=tuple(refined),
            tolerance=mp.mpf(self.config.dedup_answer_tolerance),
        )
        converged_count = sum(1 for candidate in deduped if candidate.refinement_status == TARGET_REACHED)
        solver_name = _FALLBACK_SOLVER_NAME if fallback_result is not None else _SOLVER_NAME
        return RefinementBatchResult(
            candidates=deduped,
            converged_count=converged_count,
            attempted_count=attempted_count,
            solver_name=solver_name,
            hard_feasible_count=sum(1 for candidate in deduped if candidate.hard_feasible),
            attempted_box_count=0,
        )
