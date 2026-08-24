"""Legacy float multistart backend adapted to pipeline search contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

import numpy as np
from scipy.optimize import brentq, least_squares, minimize, minimize_scalar
from scipy.stats import qmc
from mpmath import mp

from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    _guard_violation_penalty,
)
from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    SearchBatchResult,
)
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.global_search_port import GlobalSearchPort
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.evaluation.classify_evaluation_failure import (
    EvaluationStatus,
)
from geosolver.engine.standard.problem.infer_problem_bounds import (
    _infer_parametric_variable_names,
)

from .build_guard_feasible_ledger import build_guard_feasible_ledger
from .deduplicate_search_candidates import deduplicate_search_candidates
from .nomad_config import NomadConfig

_LOCAL_FLOAT_TIME_BUDGET_SECONDS = 45.0
_PARAMETRIC_LOCAL_FLOAT_TIME_BUDGET_SECONDS = 60.0
_BOUNDED_TRF_TIME_BUDGET_SECONDS = 45.0
_N_HALTON_STARTS = 320
_LM_MAX_NFEV = 80
# Keep a small search-side closure window so that the high-precision refiner
# can polish roots returned by bounded 1-D scans.  Phase C still applies the
# strict residual gate (1e-15) to the polished candidate, so this does not
# weaken final answer acceptance.  In particular, a root found within the
# scan's float resolution must not be discarded before refinement.
_RESIDUAL_ACCEPT_FLOAT = 1e-6
_FLOAT_HARD_FEASIBILITY_MARGIN_MIN = mp.mpf("1e-6")
_HALTON_START_BURN_IN = 3
_HALTON_PREFIX_STARTS_PER_DIMENSION = 1
_EARLY_FRONT_TAIL_STARTS_PER_DIMENSION = 1
_UNDERDETERMINED_POWELL_MAXITER = 400
_BOUNDED_TRF_HALTON_STARTS = 24
_BOUNDED_TRF_MAX_NFEV = 1200
_NONFINITE_RESIDUAL_PENALTY = 1e10
_LM_FAMILY_CODE = 1
_TRF_FAMILY_CODE = 2
_ONE_D_FAMILY_CODE = 3
_SEED_CANDIDATE_MULTIPLIER = 1_000_000
_FAMILY_CANDIDATE_MULTIPLIER = 100_000
_START_POINT_MULTIPLIER = 100


class _SearchDeadlineExceeded(RuntimeError):
    """Raised when the current family exceeded its wall-clock budget."""


@dataclass(frozen=True)
class _FamilyBudget:
    """Wall-clock allocation for the LM and bounded-TRF families."""

    lm_budget_sec: float
    trf_budget_sec: float


@dataclass
class _SearchTelemetry:
    """Residual-evaluation telemetry shared across scipy search families."""

    evaluation_count: int = 0
    failure_count: int = 0
    local_start_events: list[dict[str, object]] = field(default_factory=list)

    def record_status(self, status: EvaluationStatus) -> None:
        self.evaluation_count += 1
        if status is not EvaluationStatus.OK:
            self.failure_count += 1

    def record_exception(self) -> None:
        self.evaluation_count += 1
        self.failure_count += 1

    def record_local_start_event(
        self,
        *,
        seed: int,
        start_index: int,
        start_kind: str,
        status: str,
        candidate_id: int | None = None,
    ) -> None:
        event: dict[str, object] = {
            "seed": int(seed),
            "start_index": int(start_index),
            "start_kind": str(start_kind),
            "status": str(status),
        }
        if candidate_id is not None:
            event["candidate_id"] = int(candidate_id)
        self.local_start_events.append(event)


@dataclass
class _AugmentedResidualVectorFn:
    """Callable residual vector used by scipy least-squares families."""

    bundle: ProblemBundle
    evaluator: EvaluatorPort
    n_constraints: int
    deadline_monotonic: float | None
    telemetry: _SearchTelemetry
    constraint_scales: tuple[float, ...] | None = None

    def __call__(self, raw_values: object) -> np.ndarray:
        _raise_if_deadline_exceeded(self.deadline_monotonic)
        values = np.array(raw_values, dtype=float)
        return _evaluate_augmented_residual_vector(
            bundle=self.bundle,
            evaluator=self.evaluator,
            values=values,
            n_constraints=self.n_constraints,
            telemetry=self.telemetry,
            constraint_scales=self.constraint_scales,
        )


@dataclass
class _ResidualObjectiveFn:
    """Scalar sum-of-squares objective for Powell fallback."""

    vector_fn: _AugmentedResidualVectorFn

    def __call__(self, raw_values: object) -> float:
        vector = self.vector_fn(raw_values)
        return float(np.dot(vector, vector))


def _raise_if_deadline_exceeded(deadline_monotonic: float | None) -> None:
    if deadline_monotonic is None:
        return
    if time.monotonic() > float(deadline_monotonic):
        raise _SearchDeadlineExceeded()


def _family_budget(
    *,
    config: NomadConfig,
    has_parametric_variables: bool,
) -> _FamilyBudget:
    base_local_budget = (
        _PARAMETRIC_LOCAL_FLOAT_TIME_BUDGET_SECONDS
        if has_parametric_variables
        else _LOCAL_FLOAT_TIME_BUDGET_SECONDS
    )
    total_budget = float(
        config.max_time_sec
        if config.max_time_sec is not None and float(config.max_time_sec) > 0.0
        else (base_local_budget + _BOUNDED_TRF_TIME_BUDGET_SECONDS)
    )
    total_share = base_local_budget + _BOUNDED_TRF_TIME_BUDGET_SECONDS
    local_budget = total_budget * (base_local_budget / total_share)
    trf_budget = total_budget - local_budget
    return _FamilyBudget(
        lm_budget_sec=max(0.0, local_budget),
        trf_budget_sec=max(0.0, trf_budget),
    )


def _derive_halton_seed(seed: int, family_tag: str) -> int:
    tag_value = 0
    for index, character in enumerate(family_tag):
        tag_value += (index + 1) * ord(character)
    return int(seed) * 1009 + tag_value


def _candidate_id(
    *,
    origin_seed: int,
    family_code: int,
    origin_start_point_index: int,
) -> int:
    return (
        int(origin_seed) * _SEED_CANDIDATE_MULTIPLIER
        + int(family_code) * _FAMILY_CANDIDATE_MULTIPLIER
        + int(origin_start_point_index) * _START_POINT_MULTIPLIER
    )


def _append_unique_starts(
    starts: list[np.ndarray],
    seen: set[tuple[float, ...]],
    extra_starts: list[np.ndarray],
) -> None:
    for start in extra_starts:
        key = tuple(np.round(np.array(start, dtype=float), 12))
        if key in seen:
            continue
        seen.add(key)
        starts.append(np.array(start, dtype=float))


def _append_unique_labeled_starts(
    *,
    starts: list[np.ndarray],
    labels: list[str],
    seen: set[tuple[float, ...]],
    extra_starts: list[np.ndarray],
    label: str,
) -> None:
    before_count = len(starts)
    _append_unique_starts(starts, seen, extra_starts)
    added_count = len(starts) - before_count
    labels.extend([str(label)] * added_count)


def _split_front_anchor_block(
    *,
    front_anchors: list[np.ndarray],
    front_tail: list[np.ndarray],
    n_vars: int,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    if not front_anchors or not front_tail:
        return front_anchors, [], front_tail
    early_tail_count = min(
        len(front_tail),
        max(1, _EARLY_FRONT_TAIL_STARTS_PER_DIMENSION * max(1, int(n_vars))),
    )
    early_anchor_count = max(1, len(front_anchors) - early_tail_count)
    return (
        front_anchors[:early_anchor_count],
        front_tail[:early_tail_count],
        front_anchors[early_anchor_count:],
    )


def _build_interior_anchor_starts(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
) -> list[np.ndarray]:
    n_vars = lower.size
    if n_vars == 0:
        return []
    ladder = np.array([0.2, 0.4, 0.6, 0.8], dtype=float)
    anchors: list[np.ndarray] = []
    shift_order = list(range(1, min(n_vars, ladder.size))) + [0]
    for shift in shift_order:
        unit = np.resize(np.roll(ladder, shift), n_vars)
        anchors.append(lower + unit * (upper - lower))
    midpoint = np.full(n_vars, 0.5, dtype=float)
    anchors.append(lower + midpoint * (upper - lower))
    anchors.append(lower + np.linspace(0.25, 0.75, n_vars, dtype=float) * (upper - lower))
    anchors.append(lower + np.linspace(0.75, 0.25, n_vars, dtype=float) * (upper - lower))
    return anchors


def _build_halton_starts(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    n_starts: int,
    burn_in: int,
    seed: int,
    family_tag: str,
) -> list[np.ndarray]:
    n_vars = lower.size
    if n_vars == 0 or n_starts <= 0:
        return []
    sampler = qmc.Halton(
        d=n_vars,
        scramble=True,
        seed=_derive_halton_seed(seed, family_tag),
    )
    if burn_in > 0:
        sampler.fast_forward(int(burn_in))
    samples = sampler.random(n=max(1, int(n_starts)))
    return [lower + sample * (upper - lower) for sample in samples]


def _build_local_start_sequence(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    n_starts_halton: int,
    burn_in: int,
    seed: int,
    extra_prefix_points: tuple[list[float], ...],
) -> list[np.ndarray]:
    starts, _ = _build_local_start_sequence_with_prefix_count(
        lower=lower,
        upper=upper,
        n_starts_halton=n_starts_halton,
        burn_in=burn_in,
        seed=seed,
        extra_prefix_points=extra_prefix_points,
    )
    return list(starts)


def _build_local_start_sequence_with_kinds(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    n_starts_halton: int,
    burn_in: int,
    seed: int,
    extra_prefix_points: tuple[list[float], ...],
) -> tuple[tuple[np.ndarray, ...], tuple[str, ...], int]:
    halton_starts = _build_halton_starts(
        lower=lower,
        upper=upper,
        n_starts=n_starts_halton,
        burn_in=burn_in,
        seed=seed,
        family_tag="local_halton",
    )
    anchors = _build_interior_anchor_starts(lower=lower, upper=upper)
    prefix_count = min(
        len(halton_starts),
        max(1, _HALTON_PREFIX_STARTS_PER_DIMENSION * lower.size),
    )
    front_anchors, front_tail, final_anchors, remaining_tail = _split_local_anchor_block(
        anchors=anchors,
        halton_tail=halton_starts[prefix_count:],
        prefix_count=prefix_count,
    )
    early_anchors, early_tail, late_anchors = _split_front_anchor_block(
        front_anchors=front_anchors,
        front_tail=front_tail,
        n_vars=lower.size,
    )
    starts: list[np.ndarray] = []
    labels: list[str] = []
    seen: set[tuple[float, ...]] = set()
    extra_points = [np.array(point, dtype=float) for point in extra_prefix_points]
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=extra_points,
        label="extra_prefix",
    )
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=halton_starts[:prefix_count],
        label="halton_prefix",
    )
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=early_anchors,
        label="front_anchor",
    )
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=early_tail,
        label="front_tail",
    )
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=late_anchors,
        label="front_anchor",
    )
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=final_anchors,
        label="final_anchor",
    )
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=front_tail[len(early_tail):],
        label="front_tail",
    )
    shallow_prefix_count = len(starts)
    _append_unique_labeled_starts(
        starts=starts,
        labels=labels,
        seen=seen,
        extra_starts=remaining_tail,
        label="remaining_tail",
    )
    seed_prefix_count = min(
        len(starts),
        max(shallow_prefix_count, _BOUNDED_TRF_HALTON_STARTS),
    )
    return tuple(starts), tuple(labels), seed_prefix_count


def _split_local_anchor_block(
    *,
    anchors: list[np.ndarray],
    halton_tail: list[np.ndarray],
    prefix_count: int,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    if len(anchors) <= 1 or not halton_tail:
        return anchors, [], [], halton_tail
    front_anchor_count = min(len(anchors) - 1, max(1, int(prefix_count)))
    front_tail_count = min(len(halton_tail), front_anchor_count)
    return (
        anchors[:front_anchor_count],
        halton_tail[:front_tail_count],
        anchors[front_anchor_count:],
        halton_tail[front_tail_count:],
    )


def _build_local_start_sequence_with_prefix_count(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    n_starts_halton: int,
    burn_in: int,
    seed: int,
    extra_prefix_points: tuple[list[float], ...],
) -> tuple[tuple[np.ndarray, ...], int]:
    starts, _labels, seed_prefix_count = _build_local_start_sequence_with_kinds(
        lower=lower,
        upper=upper,
        n_starts_halton=n_starts_halton,
        burn_in=burn_in,
        seed=seed,
        extra_prefix_points=extra_prefix_points,
    )
    return starts, seed_prefix_count


def _build_local_start_diagnostics(
    *,
    telemetry: _SearchTelemetry,
) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    seed_status_counts: dict[int, dict[str, int]] = {}
    for event in telemetry.local_start_events:
        status = str(event["status"])
        seed = int(event["seed"])
        status_counts[status] = status_counts.get(status, 0) + 1
        per_seed = seed_status_counts.setdefault(seed, {})
        per_seed[status] = per_seed.get(status, 0) + 1
    return {
        "local_start_events": tuple(dict(event) for event in telemetry.local_start_events),
        "local_start_status_counts": dict(status_counts),
        "local_start_status_counts_by_seed": {
            str(seed): dict(counts) for seed, counts in seed_status_counts.items()
        },
    }


def _build_local_seed_prefix_schedule(
    seed_start_sequences: tuple[tuple[int, tuple[np.ndarray, ...], int], ...],
) -> tuple[tuple[int, int, np.ndarray], ...]:
    """Schedule a shallow per-seed prefix before deeper starts."""

    scheduled_starts: list[tuple[int, int, np.ndarray]] = []
    for seed, starts, shallow_prefix_count in seed_start_sequences:
        prefix_count = min(len(starts), max(0, int(shallow_prefix_count)))
        for start_index, start in enumerate(starts[:prefix_count]):
            scheduled_starts.append((int(seed), start_index, start))
    for seed, starts, shallow_prefix_count in seed_start_sequences:
        prefix_count = min(len(starts), max(0, int(shallow_prefix_count)))
        for start_index, start in enumerate(starts[prefix_count:], start=prefix_count):
            scheduled_starts.append((int(seed), start_index, start))
    return tuple(scheduled_starts)


def _evaluate_guard_penalty(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    values: np.ndarray,
) -> float:
    try:
        penalty = _guard_violation_penalty(
            list(values),
            spec=bundle.spec,
            var_names=list(bundle.var_names),
            base_context=dict(bundle.base_context),
            compiled_guards=getattr(evaluator, "compiled_guards", None),
        )
    except Exception:
        return float(1e6)
    penalty_float = float(penalty)
    if not math.isfinite(penalty_float):
        return float(1e6)
    return penalty_float


def _evaluate_hard_feasibility_penalty(
    *,
    evaluator: EvaluatorPort,
    values: np.ndarray,
) -> float:
    try:
        snapshot = evaluator.evaluate_float_hard_feasibility(
            list(values),
            include_margins=False,
        )
    except Exception:
        return float(1e3)
    if not snapshot.hard_feasible:
        return float(1e3)
    if snapshot.min_margin is None:
        return 0.0
    safe_margin = max(snapshot.min_margin, mp.mpf("1e-30"))
    return float(_FLOAT_HARD_FEASIBILITY_MARGIN_MIN / safe_margin)


def _evaluate_augmented_residual_vector(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    values: np.ndarray,
    n_constraints: int,
    telemetry: _SearchTelemetry,
    constraint_scales: tuple[float, ...] | None = None,
) -> np.ndarray:
    try:
        result = evaluator.evaluate_float_residual(list(values))
        telemetry.record_status(result.evaluation_status)
        if result.evaluation_status is not EvaluationStatus.OK or not result.is_finite:
            return np.full(n_constraints + 2, _NONFINITE_RESIDUAL_PENALTY, dtype=float)
        vector = np.array(result.residual_vector, dtype=float)
        if vector.size != n_constraints or not np.all(np.isfinite(vector)):
            return np.full(n_constraints + 2, _NONFINITE_RESIDUAL_PENALTY, dtype=float)
    except Exception:
        telemetry.record_exception()
        return np.full(n_constraints + 2, _NONFINITE_RESIDUAL_PENALTY, dtype=float)
    if constraint_scales is not None and len(constraint_scales) == n_constraints:
        scale_arr = np.array(constraint_scales, dtype=float)
        vector = vector / scale_arr
    guard_penalty = _evaluate_guard_penalty(
        bundle=bundle,
        evaluator=evaluator,
        values=values,
    )
    hard_penalty = _evaluate_hard_feasibility_penalty(evaluator=evaluator, values=values)
    if not math.isfinite(guard_penalty) or not math.isfinite(hard_penalty):
        return np.full(n_constraints + 2, _NONFINITE_RESIDUAL_PENALTY, dtype=float)
    return np.concatenate(
        [
            vector,
            np.array([10.0 * guard_penalty, 10.0 * hard_penalty], dtype=float),
        ]
    )


def _evaluate_float_residual_norm(
    *,
    evaluator: EvaluatorPort,
    values: np.ndarray,
    telemetry: _SearchTelemetry,
) -> float | None:
    try:
        residual_eval = evaluator.evaluate_float_residual(list(values))
        telemetry.record_status(residual_eval.evaluation_status)
    except Exception:
        telemetry.record_exception()
        return None
    if residual_eval.evaluation_status is not EvaluationStatus.OK or not residual_eval.is_finite:
        return None
    residual_vector = np.array(residual_eval.residual_vector, dtype=float)
    if not np.all(np.isfinite(residual_vector)):
        return None
    return float(np.linalg.norm(residual_vector))


def _collect_local_start_record(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    config: NomadConfig,
    seed: int,
    start_index: int,
    start: np.ndarray,
    deadline_monotonic: float | None,
    telemetry: _SearchTelemetry,
    constraint_scales: tuple[float, ...] | None = None,
) -> FloatCandidate | None:
    _raise_if_deadline_exceeded(deadline_monotonic)
    n_vars = len(bounds)
    n_constraints = len(bundle.spec.constraints)
    vector_fn = _AugmentedResidualVectorFn(
        bundle=bundle,
        evaluator=evaluator,
        n_constraints=n_constraints,
        deadline_monotonic=deadline_monotonic if n_vars > n_constraints else None,
        telemetry=telemetry,
        constraint_scales=constraint_scales,
    )
    objective_fn = _ResidualObjectiveFn(vector_fn=vector_fn)
    try:
        if n_vars > n_constraints:
            result = minimize(
                objective_fn,
                start,
                method="Powell",
                options={"maxiter": _UNDERDETERMINED_POWELL_MAXITER, "ftol": 1e-16},
            )
        else:
            result = least_squares(
                vector_fn,
                start,
                method="lm",
                max_nfev=_LM_MAX_NFEV,
                ftol=1e-14,
                xtol=1e-14,
                gtol=1e-14,
            )
    except _SearchDeadlineExceeded:
        raise
    except Exception:
        return None
    return _build_candidate(
        evaluator=evaluator,
        config=config,
        bounds=bounds,
        values=np.array(result.x, dtype=float),
        origin_seed=seed,
        family_code=_LM_FAMILY_CODE,
        origin_start_point_index=start_index,
        telemetry=telemetry,
    )


def _build_candidate(
    *,
    evaluator: EvaluatorPort,
    config: NomadConfig,
    bounds: list[tuple[float, float]],
    values: np.ndarray,
    origin_seed: int,
    family_code: int,
    origin_start_point_index: int,
    telemetry: _SearchTelemetry,
) -> FloatCandidate:
    point = tuple(float(value) for value in values)
    in_bounds = all(
        float(low) <= value <= float(high)
        for value, (low, high) in zip(point, bounds)
    )
    if not in_bounds:
        candidate_id = _candidate_id(
            origin_seed=origin_seed,
            family_code=family_code,
            origin_start_point_index=origin_start_point_index,
        )
        return FloatCandidate(
            x_float=point,
            score=float(config.guard_penalty) + _NONFINITE_RESIDUAL_PENALTY,
            residual_norm_float=float("inf"),
            guard_ok=False,
            evaluation_status=EvaluationStatus.EVALUATION_FAILED,
            origin_seed=int(origin_seed),
            origin_start_point_index=int(origin_start_point_index),
            candidate_id=candidate_id,
            hard_feasible=False,
            hard_violation_tags=("out_of_bounds",),
            validity_margin_float=None,
        )
    candidate_id = _candidate_id(
        origin_seed=origin_seed,
        family_code=family_code,
        origin_start_point_index=origin_start_point_index,
    )
    try:
        float_eval = evaluator.evaluate_float_residual(point)
        telemetry.record_status(float_eval.evaluation_status)
    except Exception:
        telemetry.record_exception()
        return FloatCandidate(
            x_float=point,
            score=float(config.guard_penalty) + _NONFINITE_RESIDUAL_PENALTY,
            residual_norm_float=float("inf"),
            guard_ok=False,
            evaluation_status=EvaluationStatus.EVALUATION_FAILED,
            origin_seed=int(origin_seed),
            origin_start_point_index=int(origin_start_point_index),
            candidate_id=candidate_id,
            hard_feasible=False,
            hard_violation_tags=("eval_status:evaluation_failed",),
            validity_margin_float=None,
        )
    if float_eval.evaluation_status is not EvaluationStatus.OK or not float_eval.is_finite:
        return FloatCandidate(
            x_float=point,
            score=float(config.guard_penalty) + _NONFINITE_RESIDUAL_PENALTY,
            residual_norm_float=float("inf"),
            guard_ok=False,
            evaluation_status=float_eval.evaluation_status,
            origin_seed=int(origin_seed),
            origin_start_point_index=int(origin_start_point_index),
            candidate_id=candidate_id,
            hard_feasible=False,
            hard_violation_tags=(f"eval_status:{float_eval.evaluation_status.value}",),
            validity_margin_float=None,
        )
    hard_snapshot = evaluator.evaluate_float_hard_feasibility(
        point,
        include_margins=False,
    )
    guard_ok, _violations = evaluator.evaluate_guard(point)
    penalty = 0.0 if hard_snapshot.hard_feasible else float(config.guard_penalty)
    validity_margin_float = None
    if hard_snapshot.min_margin is not None and math.isfinite(float(hard_snapshot.min_margin)):
        validity_margin_float = float(hard_snapshot.min_margin)
    return FloatCandidate(
        x_float=point,
        score=(float(float_eval.residual_norm_float) * float(float_eval.residual_norm_float)) + penalty,
        residual_norm_float=float(float_eval.residual_norm_float),
        guard_ok=bool(guard_ok),
        evaluation_status=float_eval.evaluation_status,
        origin_seed=int(origin_seed),
        origin_start_point_index=int(origin_start_point_index),
        candidate_id=candidate_id,
        hard_feasible=bool(hard_snapshot.hard_feasible),
        hard_violation_tags=tuple(hard_snapshot.failure_tags),
        validity_margin_float=validity_margin_float,
    )


def _is_admissible_candidate(candidate: FloatCandidate) -> bool:
    if candidate.evaluation_status is not EvaluationStatus.OK:
        return False
    if candidate.residual_norm_float >= _RESIDUAL_ACCEPT_FLOAT:
        return False
    if not candidate.guard_ok or not candidate.hard_feasible:
        return False
    if candidate.validity_margin_float is None:
        return True
    return candidate.validity_margin_float >= float(_FLOAT_HARD_FEASIBILITY_MARGIN_MIN)


def _rank_bounded_trf_starts(
    *,
    evaluator: EvaluatorPort,
    starts: list[np.ndarray],
    telemetry: _SearchTelemetry,
) -> list[np.ndarray]:
    ranked: list[tuple[tuple[int, int, int, float, int], np.ndarray]] = []
    for index, start in enumerate(starts):
        residual_norm = _evaluate_float_residual_norm(
            evaluator=evaluator,
            values=start,
            telemetry=telemetry,
        )
        try:
            guard_ok, _ = evaluator.evaluate_guard(list(start))
        except Exception:
            guard_ok = False
        try:
            hard_feasible = bool(
                evaluator.evaluate_float_hard_feasibility(
                    list(start),
                    include_margins=False,
                ).hard_feasible
            )
        except Exception:
            hard_feasible = False
        priority = (
            0 if hard_feasible else 1,
            0 if guard_ok else 1,
            0 if residual_norm is not None else 1,
            float("inf") if residual_norm is None else float(residual_norm),
            index,
        )
        ranked.append((priority, start))
    ranked.sort(key=lambda item: item[0])
    return [values for _, values in ranked]


def _collect_local_family_records(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    config: NomadConfig,
    seed: int,
    deadline_monotonic: float | None,
    extra_prefix_points: tuple[list[float], ...],
    has_parametric_variables: bool,
    telemetry: _SearchTelemetry,
    constraint_scales: tuple[float, ...] | None = None,
) -> tuple[FloatCandidate, ...]:
    if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
        return ()
    lower = np.array([low for low, _high in bounds], dtype=float)
    upper = np.array([high for _low, high in bounds], dtype=float)
    burn_in = _HALTON_START_BURN_IN if has_parametric_variables else 0
    starts, _ = _build_local_start_sequence_with_prefix_count(
        lower=lower,
        upper=upper,
        n_starts_halton=_N_HALTON_STARTS,
        burn_in=burn_in,
        seed=seed,
        extra_prefix_points=extra_prefix_points,
    )
    records: list[FloatCandidate] = []
    for start_index, start in enumerate(starts):
        try:
            record = _collect_local_start_record(
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                config=config,
                seed=seed,
                start_index=start_index,
                start=start,
                deadline_monotonic=deadline_monotonic,
                telemetry=telemetry,
                constraint_scales=constraint_scales,
            )
        except _SearchDeadlineExceeded:
            break
        if record is None:
            continue
        records.append(record)
    return tuple(records)


def _collect_bounded_trf_records(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    config: NomadConfig,
    seed: int,
    deadline_monotonic: float | None,
    telemetry: _SearchTelemetry,
    constraint_scales: tuple[float, ...] | None = None,
) -> tuple[FloatCandidate, ...]:
    if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
        return ()
    n_vars = len(bounds)
    n_constraints = len(bundle.spec.constraints)
    if n_vars <= 0:
        return ()
    lower = np.array([low for low, _high in bounds], dtype=float)
    upper = np.array([high for _low, high in bounds], dtype=float)
    starts = _build_halton_starts(
        lower=lower,
        upper=upper,
        n_starts=_BOUNDED_TRF_HALTON_STARTS,
        burn_in=0,
        seed=seed,
        family_tag="bounded_trf",
    )
    ranked_starts = _rank_bounded_trf_starts(
        evaluator=evaluator,
        starts=starts,
        telemetry=telemetry,
    )
    vector_fn = _AugmentedResidualVectorFn(
        bundle=bundle,
        evaluator=evaluator,
        n_constraints=n_constraints,
        deadline_monotonic=deadline_monotonic,
        telemetry=telemetry,
        constraint_scales=constraint_scales,
    )
    records: list[FloatCandidate] = []
    for start_index, start in enumerate(ranked_starts):
        if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
            break
        try:
            result = least_squares(
                vector_fn,
                start,
                method="trf",
                bounds=(lower, upper),
                max_nfev=_BOUNDED_TRF_MAX_NFEV,
                ftol=1e-14,
                xtol=1e-14,
                gtol=1e-14,
            )
        except _SearchDeadlineExceeded:
            break
        except Exception:
            continue
        records.append(
            _build_candidate(
                evaluator=evaluator,
                config=config,
                bounds=bounds,
                values=np.array(result.x, dtype=float),
                origin_seed=seed,
                family_code=_TRF_FAMILY_CODE,
                origin_start_point_index=start_index,
                telemetry=telemetry,
            )
        )
    return tuple(records)


def _one_dimensional_grid_size(config: NomadConfig) -> int:
    """Choose a bounded deterministic scan size for one-dimensional systems."""
    eval_budget = max(32, int(config.max_bb_eval))
    return max(81, min(401, eval_budget + 1))


def _evaluate_one_dimensional_residual(
    *,
    evaluator: EvaluatorPort,
    x_value: float,
    telemetry: _SearchTelemetry,
) -> tuple[float | None, float | None]:
    """Return (first residual, residual norm) at a scalar point."""
    try:
        residual_eval = evaluator.evaluate_float_residual([float(x_value)])
        telemetry.record_status(residual_eval.evaluation_status)
    except Exception:
        telemetry.record_exception()
        return None, None
    if residual_eval.evaluation_status is not EvaluationStatus.OK or not residual_eval.is_finite:
        return None, None
    vector = np.array(residual_eval.residual_vector, dtype=float)
    if vector.size == 0 or not np.all(np.isfinite(vector)):
        return None, None
    return float(vector[0]), float(np.linalg.norm(vector))


def _safe_brentq_root(
    *,
    evaluator: EvaluatorPort,
    left: float,
    right: float,
    f_left: float,
    f_right: float,
    telemetry: _SearchTelemetry,
    deadline_monotonic: float | None,
) -> float | None:
    if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
        return None
    if not (math.isfinite(left) and math.isfinite(right) and left < right):
        return None
    if f_left == 0.0:
        return float(left)
    if f_right == 0.0:
        return float(right)
    if f_left * f_right > 0.0:
        return None

    def scalar_fn(raw: float) -> float:
        _raise_if_deadline_exceeded(deadline_monotonic)
        residual, _norm = _evaluate_one_dimensional_residual(
            evaluator=evaluator,
            x_value=float(raw),
            telemetry=telemetry,
        )
        if residual is None or not math.isfinite(residual):
            raise ValueError("non-finite residual in brentq")
        return float(residual)

    try:
        return float(brentq(scalar_fn, float(left), float(right), xtol=1e-12, rtol=1e-12, maxiter=80))
    except Exception:
        return None


def _safe_minimize_scalar_root(
    *,
    evaluator: EvaluatorPort,
    left: float,
    right: float,
    telemetry: _SearchTelemetry,
    deadline_monotonic: float | None,
) -> float | None:
    if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
        return None
    if not (math.isfinite(left) and math.isfinite(right) and left < right):
        return None

    def objective(raw: float) -> float:
        _raise_if_deadline_exceeded(deadline_monotonic)
        _residual, norm = _evaluate_one_dimensional_residual(
            evaluator=evaluator,
            x_value=float(raw),
            telemetry=telemetry,
        )
        if norm is None or not math.isfinite(norm):
            return _NONFINITE_RESIDUAL_PENALTY
        return float(norm * norm)

    try:
        result = minimize_scalar(
            objective,
            bounds=(float(left), float(right)),
            method="bounded",
            options={"xatol": 1e-11, "maxiter": 80},
        )
    except _SearchDeadlineExceeded:
        return None
    except Exception:
        return None
    if not getattr(result, "success", False):
        # scipy may report bounded-iteration warnings even at a useful minimizer; keep finite x.
        try:
            if not math.isfinite(float(result.x)):
                return None
        except Exception:
            return None
    try:
        return float(result.x)
    except Exception:
        return None


def _run_one_dimensional_search(
    *,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    config: NomadConfig,
    seed: int,
    deadline_monotonic: float | None,
    telemetry: _SearchTelemetry,
) -> tuple[tuple[float, ...], dict[str, object]]:
    """Cheap complete-ish 1D scan used before the expensive multistart family.

    It is intentionally structure-free: it uses only the residual evaluator and bounds,
    so it is a general numerical root-candidate generator rather than a case patch.
    """
    if len(bounds) != 1:
        return (), {"enabled": False, "reason": "not_one_dimensional"}
    lower, upper = bounds[0]
    lower = float(lower)
    upper = float(upper)
    if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
        return (), {"enabled": False, "reason": "invalid_bounds"}
    # Avoid evaluating exactly on open-ish guard boundaries; hard feasibility still filters later.
    width = upper - lower
    eps = max(width * 1e-10, 1e-10)
    scan_lower = lower + eps
    scan_upper = upper - eps
    if scan_lower >= scan_upper:
        scan_lower, scan_upper = lower, upper
    grid_size = _one_dimensional_grid_size(config)
    xs = np.linspace(scan_lower, scan_upper, grid_size, dtype=float)
    observations: list[tuple[float, float | None, float | None]] = []
    for x_value in xs:
        if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
            break
        residual, norm = _evaluate_one_dimensional_residual(
            evaluator=evaluator,
            x_value=float(x_value),
            telemetry=telemetry,
        )
        observations.append((float(x_value), residual, norm))
    if not observations:
        return (), {"enabled": True, "grid_size": grid_size, "observation_count": 0}

    root_values: list[float] = []
    # Exact-ish grid hits and sign-change brackets for scalar equations.
    for x_value, residual, norm in observations:
        if norm is not None and math.isfinite(norm) and norm <= 1e-7:
            root_values.append(float(x_value))
        if residual is not None and math.isfinite(residual) and abs(residual) <= 1e-8:
            root_values.append(float(x_value))
    for (left, f_left, _n_left), (right, f_right, _n_right) in zip(observations, observations[1:]):
        if f_left is None or f_right is None:
            continue
        if not (math.isfinite(f_left) and math.isfinite(f_right)):
            continue
        if f_left == 0.0 or f_right == 0.0 or f_left * f_right <= 0.0:
            root = _safe_brentq_root(
                evaluator=evaluator,
                left=left,
                right=right,
                f_left=f_left,
                f_right=f_right,
                telemetry=telemetry,
                deadline_monotonic=deadline_monotonic,
            )
            if root is not None:
                root_values.append(root)
    # Refine the best few residual-norm basins. This catches tangent/double roots.
    finite_norms = [
        (float(norm), index)
        for index, (_x, _residual, norm) in enumerate(observations)
        if norm is not None and math.isfinite(norm)
    ]
    finite_norms.sort(key=lambda item: item[0])
    minimized_intervals: set[tuple[int, int]] = set()
    for _norm, index in finite_norms[: min(10, len(finite_norms))]:
        left_index = max(0, index - 1)
        right_index = min(len(observations) - 1, index + 1)
        if left_index == right_index:
            continue
        key = (left_index, right_index)
        if key in minimized_intervals:
            continue
        minimized_intervals.add(key)
        root = _safe_minimize_scalar_root(
            evaluator=evaluator,
            left=observations[left_index][0],
            right=observations[right_index][0],
            telemetry=telemetry,
            deadline_monotonic=deadline_monotonic,
        )
        if root is not None:
            root_values.append(root)
    # Always preserve the best raw grid locations as fallbacks for downstream refinement.
    for _norm, index in finite_norms[: min(8, len(finite_norms))]:
        root_values.append(float(observations[index][0]))

    deduped: list[float] = []
    seen: set[int] = set()
    tolerance = max(width * 1e-9, 1e-9)
    for value in sorted(root_values):
        if not (lower <= value <= upper):
            continue
        bucket = int(round((value - lower) / tolerance)) if tolerance > 0 else int(round(value, 12))
        if bucket in seen:
            continue
        seen.add(bucket)
        deduped.append(float(value))
    diagnostics = {
        "enabled": True,
        "grid_size": grid_size,
        "observation_count": len(observations),
        "candidate_count": len(deduped),
        "best_grid_norm": (None if not finite_norms else finite_norms[0][0]),
    }
    return tuple((value,) for value in deduped), diagnostics


@dataclass(frozen=True)
class ScipyMultistartBackend(GlobalSearchPort):
    """Run the legacy float multistart search family under pipeline contracts."""

    config: NomadConfig
    start_points: tuple[list[float], ...]
    constraint_scales: tuple[float, ...] | None = None

    def run_search(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        bounds: list[tuple[float, float]],
        search_mode: str = "scipy_multistart",
        guard_feasible_prefix_count: int | None = None,
    ) -> SearchBatchResult:
        _ = search_mode
        has_parametric_variables = bool(_infer_parametric_variable_names(bundle))
        family_budget = _family_budget(
            config=self.config,
            has_parametric_variables=has_parametric_variables,
        )
        telemetry = _SearchTelemetry()
        seed_values = self.config.seed_values or (11,)
        local_deadline = (
            time.monotonic() + family_budget.lm_budget_sec
            if family_budget.lm_budget_sec > 0.0
            else None
        )
        all_records: list[FloatCandidate] = []
        lower = np.array([low for low, _high in bounds], dtype=float)
        upper = np.array([high for _low, high in bounds], dtype=float)
        one_d_deadline = (
            time.monotonic() + family_budget.lm_budget_sec
            if family_budget.lm_budget_sec > 0.0
            else None
        )
        if len(bounds) == 1:
            one_d_points, one_d_diagnostics = _run_one_dimensional_search(
                evaluator=evaluator,
                bounds=bounds,
                config=self.config,
                seed=int(seed_values[0]),
                deadline_monotonic=one_d_deadline,
                telemetry=telemetry,
            )
            one_d_records = tuple(
                _build_candidate(
                    evaluator=evaluator,
                    config=self.config,
                    bounds=bounds,
                    values=np.array(point, dtype=float),
                    origin_seed=int(seed_values[0]),
                    family_code=_ONE_D_FAMILY_CODE,
                    origin_start_point_index=index,
                    telemetry=telemetry,
                )
                for index, point in enumerate(one_d_points)
            )
            admissible_one_d_records = tuple(
                sorted(
                    (candidate for candidate in one_d_records if _is_admissible_candidate(candidate)),
                    key=lambda candidate: (candidate.residual_norm_float, candidate.score, candidate.candidate_id),
                )
            )
            if one_d_records and admissible_one_d_records:
                records = tuple(one_d_records)
                prefix_count = (
                    int(guard_feasible_prefix_count)
                    if guard_feasible_prefix_count is not None
                    else int(self.config.keep_after_dedup)
                )
                _compact_candidates, guard_feasible_ledger = build_guard_feasible_ledger(
                    all_records=records,
                    bounds=bounds,
                    compact_keep_count=int(self.config.keep_after_dedup),
                    prefix_count=prefix_count,
                )
                # For a certified 1D bracket/refine pass, feeding every nearby grid/minimize
                # point into mpmath is pure overhead.  Keep all admissible roots/families,
                # but do not let close non-root probes inflate Phase B.
                selected = admissible_one_d_records[: int(self.config.keep_after_dedup)]
                failure_ratio = 1.0 if telemetry.evaluation_count == 0 else (telemetry.failure_count / telemetry.evaluation_count)
                diagnostics = _build_local_start_diagnostics(telemetry=telemetry)
                diagnostics["one_dimensional_search"] = one_d_diagnostics
                print(
                    "    One-dimensional root family:"
                    f" {sum(1 for candidate in records if _is_admissible_candidate(candidate))} admissible"
                    f" ({len(records)} final states, {telemetry.evaluation_count} residual evals)"
                )
                return SearchBatchResult(
                    candidates=selected,
                    evaluation_count=telemetry.evaluation_count,
                    failure_ratio=failure_ratio,
                    all_records=records,
                    guard_feasible_ledger=guard_feasible_ledger,
                    search_diagnostics=diagnostics,
                )
            all_records.extend(one_d_records)
        burn_in = _HALTON_START_BURN_IN if has_parametric_variables else 0
        local_seed_start_sequences = tuple(
            (
                int(seed),
                starts,
                start_kinds,
                shallow_prefix_count,
            )
            for seed in seed_values
            for starts, start_kinds, shallow_prefix_count in [
                _build_local_start_sequence_with_kinds(
                    lower=lower,
                    upper=upper,
                    n_starts_halton=_N_HALTON_STARTS,
                    burn_in=burn_in,
                    seed=int(seed),
                    extra_prefix_points=self.start_points,
                )
            ]
        )
        scheduled_local_starts = _build_local_seed_prefix_schedule(
            tuple(
                (seed, starts, shallow_prefix_count)
                for seed, starts, _start_kinds, shallow_prefix_count in local_seed_start_sequences
            )
        )
        local_start_kind_by_seed = {
            seed: start_kinds
            for seed, _starts, start_kinds, _shallow_prefix_count in local_seed_start_sequences
        }
        deadline_stop_index: int | None = None
        for schedule_index, (seed, start_index, start) in enumerate(scheduled_local_starts):
            start_kind = local_start_kind_by_seed[seed][start_index]
            if local_deadline is not None and time.monotonic() > local_deadline:
                telemetry.record_local_start_event(
                    seed=seed,
                    start_index=start_index,
                    start_kind=start_kind,
                    status="deadline_before_start",
                )
                deadline_stop_index = schedule_index
                break
            try:
                record = _collect_local_start_record(
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    config=self.config,
                    seed=seed,
                    start_index=start_index,
                    start=start,
                    deadline_monotonic=local_deadline,
                    telemetry=telemetry,
                    constraint_scales=self.constraint_scales,
                )
            except _SearchDeadlineExceeded:
                telemetry.record_local_start_event(
                    seed=seed,
                    start_index=start_index,
                    start_kind=start_kind,
                    status="deadline_during_eval",
                )
                deadline_stop_index = schedule_index
                break
            if record is None:
                telemetry.record_local_start_event(
                    seed=seed,
                    start_index=start_index,
                    start_kind=start_kind,
                    status="record_failed",
                )
                continue
            telemetry.record_local_start_event(
                seed=seed,
                start_index=start_index,
                start_kind=start_kind,
                status="finished",
                candidate_id=record.candidate_id,
            )
            all_records.append(record)
        if deadline_stop_index is not None:
            for seed, start_index, _start in scheduled_local_starts[deadline_stop_index + 1 :]:
                telemetry.record_local_start_event(
                    seed=seed,
                    start_index=start_index,
                    start_kind=local_start_kind_by_seed[seed][start_index],
                    status="not_started_after_deadline",
                )
        trf_deadline = (
            time.monotonic() + family_budget.trf_budget_sec
            if family_budget.trf_budget_sec > 0.0
            else None
        )
        for seed in seed_values:
            all_records.extend(
                _collect_bounded_trf_records(
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    config=self.config,
                    seed=int(seed),
                    deadline_monotonic=trf_deadline,
                    telemetry=telemetry,
                    constraint_scales=self.constraint_scales,
                )
            )
        records = tuple(all_records)
        prefix_count = (
            int(guard_feasible_prefix_count)
            if guard_feasible_prefix_count is not None
            else int(self.config.keep_after_dedup)
        )
        compact_candidates, guard_feasible_ledger = build_guard_feasible_ledger(
            all_records=records,
            bounds=bounds,
            compact_keep_count=int(self.config.keep_after_dedup),
            prefix_count=prefix_count,
        )
        selected = compact_candidates
        if not selected:
            selected = deduplicate_search_candidates(
                candidates=records,
                bounds=bounds,
                keep_count=int(self.config.keep_after_dedup),
                dedup_distance_threshold=float(self.config.dedup_distance),
                min_per_seed=int(self.config.min_per_seed_after_dedup),
            )
        admissible_count = sum(1 for candidate in records if _is_admissible_candidate(candidate))
        failure_count = telemetry.failure_count
        evaluation_count = telemetry.evaluation_count
        failure_ratio = 1.0 if evaluation_count == 0 else (failure_count / evaluation_count)
        print(
            "    Supplemental legacy float family:"
            f" {admissible_count} admissible"
            f" ({len(records)} final states, {evaluation_count} residual evals, mode=scipy_multistart)"
        )
        return SearchBatchResult(
            candidates=selected,
            evaluation_count=evaluation_count,
            failure_ratio=failure_ratio,
            all_records=records,
            guard_feasible_ledger=guard_feasible_ledger,
            search_diagnostics=_build_local_start_diagnostics(telemetry=telemetry),
        )
