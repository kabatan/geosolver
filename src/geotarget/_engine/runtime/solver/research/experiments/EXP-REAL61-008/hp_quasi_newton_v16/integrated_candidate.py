"""Lane-local HP direct-Broyden integration for the numerical-v3 finalist.

This disposable adapter changes only how a Jacobian is reused inside the
existing high-precision endpoint refiner.  Each independently initialized
512/768 prefix lane builds one dense semismooth finite-difference Jacobian,
then applies direct good-Broyden updates after accepted steps.  A fresh dense
Jacobian is permitted only after an identity-free numerical event.  The
original variables, residuals, semantic callbacks, guards, branches, bounds,
coordinates, 512/768 agreement gate, original-DSL replay, and target-only
768/1024 PSLQ authority are inherited unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Callable, Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
CONTROL_PATH = HERE.parent / "hp_precision_schedule_v11/candidate.py"
KERNEL_PATH = HERE / "candidate.py"


def _load(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CONTROL = _load("geotarget_exp008_hp_qn_v16_control", CONTROL_PATH)
KERNEL = _load("geotarget_exp008_hp_qn_v16_kernel", KERNEL_PATH)
FROZEN = CONTROL.FROZEN
ADAPTIVE = CONTROL.ADAPTIVE
SEMISMOOTH = CONTROL.SEMISMOOTH

VARIANT = CONTROL.VARIANT
VARIANTS = (VARIANT,)
EVENT_REFRESHED = "EVENT_REFRESHED_DIRECT_GOOD_BROYDEN"
SHAMANSKII_M4 = "SHAMANSKII_M4_DIRECT_GOOD_BROYDEN"
CONFIGURATIONS = (EVENT_REFRESHED, SHAMANSKII_M4)
CONFIGURATION = EVENT_REFRESHED
STRICT_STAGE_COUNT = 4


@dataclass
class _ModelState:
    phase: str
    jacobian: list[list[object]] | None = None
    pending_refresh: str | None = None
    dense_initializations: int = 0
    event_refreshes: int = 0
    refresh_reasons: dict[str, int] = field(default_factory=dict)
    good_broyden_updates: int = 0
    unusable_broyden_updates: int = 0
    accepted_steps: int = 0
    accepted_updates_since_refresh: int = 0
    consecutive_poor_ratios: int = 0
    last_rank: int | None = None
    factorization_calls: int = 0
    semantic_kink_models: int = 0
    damping: object = field(default_factory=lambda: mp.mpf("1e-6"))
    trust_radius: object = field(default_factory=lambda: mp.mpf("2"))

    def summary(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "dense_initializations": self.dense_initializations,
            "event_refreshes": self.event_refreshes,
            "dense_jacobian_builds": self.dense_initializations
            + self.event_refreshes,
            "refresh_reasons": dict(sorted(self.refresh_reasons.items())),
            "good_broyden_updates": self.good_broyden_updates,
            "unusable_broyden_updates": self.unusable_broyden_updates,
            "accepted_steps": self.accepted_steps,
            "accepted_updates_since_refresh": self.accepted_updates_since_refresh,
            "factorization_calls": self.factorization_calls,
            "semantic_kink_models": self.semantic_kink_models,
            "pending_refresh_at_exit": self.pending_refresh,
        }


_ACTIVE_STATE: _ModelState | None = None
_PHASE_SUMMARIES: list[dict[str, object]] = []


def _policy():
    if CONFIGURATION == EVENT_REFRESHED:
        return KERNEL.RefreshPolicy(maximum_updates_without_refresh=None)
    if CONFIGURATION == SHAMANSKII_M4:
        return KERNEL.RefreshPolicy(maximum_updates_without_refresh=4)
    raise ValueError(f"unknown HP quasi-Newton configuration: {CONFIGURATION}")


def _note_refresh(state: _ModelState, reason: str) -> None:
    state.pending_refresh = reason
    state.refresh_reasons[reason] = state.refresh_reasons.get(reason, 0) + 1


def _dense_prefix(problem, z, residual, dps, counters, _stencil_extra):
    opposing_before = counters.opposing_side_derivatives
    one_sided_before = counters.semantic_one_sided_columns
    jacobian = SEMISMOOTH._adaptive_semismooth_jacobian(
        problem, z, residual, dps, counters
    )
    kink = bool(
        counters.opposing_side_derivatives > opposing_before
        or counters.semantic_one_sided_columns > one_sided_before
    )
    return jacobian, kink


def _dense_strict(problem, z, residual, dps, counters, stencil_extra):
    return FROZEN._fine_semismooth_jacobian(
        problem,
        z,
        residual,
        dps,
        counters,
        stencil_extra=stencil_extra,
    )


def _factor_step_options(
    matrix,
    scaled_residual,
    column_divisors,
    *,
    damping,
    dps: int,
    counters,
):
    """Factor once, then form the frozen undamped+damping step ladder."""

    counters.svd_factorizations += 1
    try:
        left, singular_values, right = mp.svd(
            mp.matrix(matrix), full_matrices=False
        )
    except Exception as error:
        raise SEMISMOOTH._Failure("SVD_FAILED") from error
    if not singular_values:
        raise SEMISMOOTH._Failure("RANK_ZERO")
    largest = max(abs(value) for value in singular_values)
    cutoff = largest * mp.power(10, -min(100, max(24, int(dps) // 2)))
    retained = [
        index
        for index, singular in enumerate(singular_values)
        if abs(singular) > cutoff
    ]
    if not retained:
        raise SEMISMOOTH._Failure("RANK_ZERO")
    if len(retained) < min(len(matrix), len(matrix[0])):
        counters.rank_deficient_steps += 1
    projections = {
        index: -mp.fsum(
            left[row, index] * scaled_residual[row]
            for row in range(len(matrix))
        )
        for index in retained
    }
    damping_values = (mp.mpf("0"),) + tuple(
        mp.mpf(damping) * mp.power(100, index) for index in range(5)
    )
    options = []
    for local_damping in damping_values:
        scaled_step = [mp.mpf("0") for _ in range(len(matrix[0]))]
        for index in retained:
            singular = singular_values[index]
            coefficient = (
                projections[index] / singular
                if local_damping == 0
                else singular
                * projections[index]
                / (singular * singular + local_damping)
            )
            for column in range(len(scaled_step)):
                scaled_step[column] += right[index, column] * coefficient
        step = tuple(
            scaled_step[column] / column_divisors[column]
            for column in range(len(scaled_step))
        )
        if all(mp.isfinite(value) for value in step):
            options.append((step, len(retained), local_damping))
    if not options:
        raise SEMISMOOTH._Failure("NONFINITE_STEP")
    return options


def _run_model_stage(
    problem,
    z,
    *,
    dps: int,
    gate,
    counters,
    deadline: float,
    max_iterations: int,
    dense_builder: Callable,
    stencil_extra: int,
    fine_equilibration: bool,
):
    global _ACTIVE_STATE
    state = _ACTIVE_STATE
    if state is None:
        raise RuntimeError("lane-local Broyden state is not installed")
    status = "ITERATION_LIMIT"
    final_residual = None
    final_merit = None
    ranks: list[int] = []
    iterations = 0
    damping_floor = mp.power(10, -min(240, max(30, int(dps) - 10)))
    counters.precision_stages += 1

    with mp.workdps(int(dps)):
        for iterations in range(1, max_iterations + 1):
            if time.monotonic() >= deadline:
                status = "DEADLINE_REACHED"
                break
            if not SEMISMOOTH._semantic(problem, z, dps, counters):
                status = "SEMANTIC_REJECTED"
                break
            residual = SEMISMOOTH._residual(problem, z, dps, counters)
            final_residual = SEMISMOOTH._norm_inf(residual)
            if final_residual <= gate:
                replay = SEMISMOOTH._residual(problem, z, dps, counters)
                final_residual = SEMISMOOTH._norm_inf(replay)
                status = (
                    "SUCCESS"
                    if final_residual <= gate
                    and SEMISMOOTH._semantic(problem, z, dps, counters)
                    else "REPLAY_GATE_FAILED"
                )
                break

            if state.jacobian is None or state.pending_refresh is not None:
                was_initial = state.jacobian is None
                jacobian, kink_active = dense_builder(
                    problem,
                    z,
                    residual,
                    dps,
                    counters,
                    stencil_extra,
                )
                state.jacobian = [list(row) for row in jacobian]
                if was_initial:
                    state.dense_initializations += 1
                else:
                    state.event_refreshes += 1
                if kink_active:
                    state.semantic_kink_models += 1
                state.pending_refresh = None
                state.accepted_updates_since_refresh = 0
                state.consecutive_poor_ratios = 0
                state.last_rank = None

            jacobian = state.jacobian
            if jacobian is None:
                raise RuntimeError("dense builder returned no Jacobian")
            if fine_equilibration:
                row_divisors, column_divisors, scaled_r, matrix, current_merit = (
                    FROZEN._fine_equilibrate(residual, jacobian, dps)
                )
            else:
                row_divisors, column_divisors, scaled_r, matrix, current_merit = (
                    SEMISMOOTH._equilibrate(residual, jacobian)
                )
            final_merit = current_merit

            try:
                options = _factor_step_options(
                    matrix,
                    scaled_r,
                    column_divisors,
                    damping=state.damping,
                    dps=dps,
                    counters=counters,
                )
                state.factorization_calls += 1
            except SEMISMOOTH._Failure:
                if state.accepted_updates_since_refresh > 0:
                    reason = KERNEL.refresh_reason(
                        KERNEL.RefreshObservation(linear_solve_failed=True),
                        _policy(),
                    )
                    _note_refresh(state, str(reason))
                    continue
                raise

            current_rank = options[0][1]
            rank_changed = state.last_rank is not None and current_rank != state.last_rank
            ranks.append(current_rank)
            accepted = None
            semantic_branch_changed = False
            for option_index, (step, rank, local_damping) in enumerate(options):
                if option_index > 1:
                    counters.damping_retries += 1
                step_norm = SEMISMOOTH._norm_inf(step)
                if step_norm == 0:
                    continue
                if step_norm > state.trust_radius:
                    factor = state.trust_radius / step_norm
                    step = tuple(factor * value for value in step)
                alpha_schedule = ("2", "1", "0.5", "0.25", "0.125", "0.0625")
                best = None
                for alpha_text in alpha_schedule:
                    alpha = mp.mpf(alpha_text)
                    trial = [
                        z[index] + alpha * step[index]
                        for index in range(len(z))
                    ]
                    if not all(mp.isfinite(value) for value in trial):
                        counters.rejected_trials += 1
                        continue
                    if not SEMISMOOTH._semantic(problem, trial, dps, counters):
                        counters.semantic_rejections += 1
                        if alpha <= 1:
                            semantic_branch_changed = True
                        continue
                    trial_residual = SEMISMOOTH._residual(
                        problem, trial, dps, counters
                    )
                    trial_merit = SEMISMOOTH._trial_merit(
                        trial_residual, row_divisors
                    )
                    if trial_merit < current_merit and (
                        best is None or trial_merit < best[0]
                    ):
                        best = (
                            trial_merit,
                            trial,
                            trial_residual,
                            alpha,
                            local_damping,
                        )
                    else:
                        counters.rejected_trials += 1
                if best is not None:
                    accepted = best
                    break

            if accepted is None and state.accepted_updates_since_refresh > 0:
                reason = KERNEL.refresh_reason(
                    KERNEL.RefreshObservation(accepted_step=False), _policy()
                )
                _note_refresh(state, str(reason))
                continue

            if accepted is None:
                fallback = SEMISMOOTH._cauchy_step(
                    matrix, scaled_r, column_divisors
                )
                if fallback is not None:
                    counters.cauchy_fallbacks += 1
                    step_norm = SEMISMOOTH._norm_inf(fallback)
                    if step_norm > state.trust_radius:
                        fallback = tuple(
                            value * state.trust_radius / step_norm for value in fallback
                        )
                    for alpha_text in ("1", "0.25", "0.0625", "0.015625"):
                        alpha = mp.mpf(alpha_text)
                        trial = [z[index] + alpha * fallback[index] for index in range(len(z))]
                        if not SEMISMOOTH._semantic(problem, trial, dps, counters):
                            counters.semantic_rejections += 1
                            semantic_branch_changed = True
                            continue
                        trial_residual = SEMISMOOTH._residual(
                            problem, trial, dps, counters
                        )
                        trial_merit = SEMISMOOTH._trial_merit(
                            trial_residual, row_divisors
                        )
                        if trial_merit < current_merit:
                            accepted = (
                                trial_merit,
                                trial,
                                trial_residual,
                                alpha,
                                state.damping,
                            )
                            break
                        counters.rejected_trials += 1

            if accepted is None:
                status = "NO_SEMISMOOTH_DESCENT"
                break

            old_z = list(z)
            step_taken = [
                accepted[1][index] - old_z[index] for index in range(len(z))
            ]
            residual_change = [
                accepted[2][row] - residual[row] for row in range(len(residual))
            ]
            predicted_residual = [
                residual[row]
                + mp.fsum(
                    jacobian[row][column] * step_taken[column]
                    for column in range(len(step_taken))
                )
                for row in range(len(residual))
            ]
            predicted_merit = SEMISMOOTH._trial_merit(
                predicted_residual, row_divisors
            )
            predicted_reduction = current_merit - predicted_merit
            actual_reduction = current_merit - accepted[0]
            ratio = (
                actual_reduction / predicted_reduction
                if predicted_reduction > 0
                else mp.mpf("0")
            )

            update = KERNEL.good_broyden_update(
                jacobian, step_taken, residual_change
            )
            if update.usable:
                state.jacobian = [list(row) for row in update.matrix]
                state.good_broyden_updates += 1
            else:
                state.unusable_broyden_updates += 1

            poor = ratio < mp.mpf(_policy().poor_ratio_threshold)
            state.consecutive_poor_ratios = (
                state.consecutive_poor_ratios + 1 if poor else 0
            )
            state.accepted_updates_since_refresh += 1
            state.accepted_steps += 1
            refresh = KERNEL.refresh_reason(
                KERNEL.RefreshObservation(
                    linear_solve_failed=not update.usable,
                    rank_changed=rank_changed,
                    semantic_branch_changed=semantic_branch_changed,
                    accepted_step=True,
                    actual_to_predicted_ratio=ratio,
                    normalized_secant_defect=update.normalized_secant_defect,
                    consecutive_poor_ratios=state.consecutive_poor_ratios,
                    accepted_updates_since_refresh=state.accepted_updates_since_refresh,
                ),
                _policy(),
            )
            if refresh is not None:
                _note_refresh(state, refresh)

            z = accepted[1]
            counters.accepted_trials += 1
            if accepted[3] == 2:
                counters.alpha_two_accepts += 1
            if accepted[4] != 0:
                state.damping = max(damping_floor, accepted[4] / 10)
            reduction = accepted[0] / current_merit
            if accepted[3] >= 1 and reduction < mp.mpf("0.2"):
                state.trust_radius = min(mp.mpf("32"), state.trust_radius * 2)
            elif accepted[3] < 1:
                state.trust_radius = max(mp.mpf("1e-6"), state.trust_radius / 2)
            state.last_rank = current_rank

    return (
        status,
        z,
        SEMISMOOTH.StageRecord(
            dps=int(dps),
            status=status,
            iterations=iterations,
            residual_inf=final_residual,
            merit=final_merit,
            damping=state.damping,
            rank_min=min(ranks) if ranks else None,
            rank_max=max(ranks) if ranks else None,
        ),
    )


def _prefix_stage(
    problem,
    z,
    *,
    dps: int,
    final: bool,
    variant: str,
    counters,
    deadline: float,
    max_iterations: int,
):
    gate = SEMISMOOTH._stage_gate(dps, final)
    if variant == SEMISMOOTH.CORRECTIVE and int(dps) >= 180:
        gate = max(gate, mp.mpf("1e-104"))
    return _run_model_stage(
        problem,
        z,
        dps=dps,
        gate=gate,
        counters=counters,
        deadline=deadline,
        max_iterations=max_iterations,
        dense_builder=_dense_prefix,
        stencil_extra=0,
        fine_equilibration=False,
    )


def _strict_stage(
    problem,
    z,
    *,
    dps,
    gate,
    mode,
    stencil_extra,
    counters,
    deadline,
):
    del mode
    return _run_model_stage(
        problem,
        z,
        dps=int(dps),
        gate=mp.mpf(gate),
        counters=counters,
        deadline=deadline,
        max_iterations=64,
        dense_builder=_dense_strict,
        stencil_extra=int(stencil_extra),
        fine_equilibration=True,
    )


def _two_prefix_lanes(problem, deadline, counters):
    global _ACTIVE_STATE
    escalation_counters = ADAPTIVE.EscalationCounters()
    lanes = []
    events = []
    for lane in SEMISMOOTH.LANES[:2]:
        if time.monotonic() >= deadline:
            break
        _ACTIVE_STATE = _ModelState(phase=f"independent-prefix-{int(lane[0])}")
        record, lane_events = ADAPTIVE._refine_lane(
            problem,
            lane,
            ADAPTIVE.ADAPTIVE_ESCALATION,
            deadline,
            counters,
            escalation_counters,
        )
        _PHASE_SUMMARIES.append(_ACTIVE_STATE.summary())
        lanes.append(record)
        events.append({"bits": int(lane[0]), "events": lane_events})
        if record.status != "SUCCESS":
            break

    coordinate_disagreement = None
    target_512_768 = None
    if len(lanes) == 2 and all(row.status == "SUCCESS" for row in lanes):
        with mp.workdps(350):
            coordinate_disagreement = max(
                (
                    abs(left - right)
                    for left, right in zip(
                        lanes[0].point, lanes[1].point, strict=True
                    )
                ),
                default=mp.mpf("0"),
            )
            target_512_768 = abs(lanes[0].answer - lanes[1].answer)
    ready = bool(
        len(lanes) == 2
        and all(row.status == "SUCCESS" for row in lanes)
        and coordinate_disagreement is not None
        and coordinate_disagreement <= SEMISMOOTH.AGREEMENT_GATE
        and target_512_768 is not None
        and target_512_768 <= SEMISMOOTH.AGREEMENT_GATE
    )
    return {
        "status": "NUMERIC_512_768_PREFIX_READY" if ready else "PREFIX_FAILED",
        "numeric_512_768_prefix_ready": ready,
        "lanes": lanes,
        "configuration_512_768_disagreement_inf": coordinate_disagreement,
        "target_512_768_disagreement": target_512_768,
        "escalation_counters": asdict(escalation_counters),
        "escalation_events": events,
    }


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = VARIANT,
    deadline_seconds: float = 23.0,
):
    global _ACTIVE_STATE
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    if CONFIGURATION not in CONFIGURATIONS:
        raise ValueError(f"unknown configuration: {CONFIGURATION}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")
    if STRICT_STAGE_COUNT not in (4, 6):
        raise ValueError("STRICT_STAGE_COUNT must be 4 or 6")

    _PHASE_SUMMARIES.clear()
    started = time.monotonic()
    deadline = started + max(0.03, float(deadline_seconds))
    problem = FROZEN._problem(evaluator, values)
    prefix_counters = SEMISMOOTH.Counters()
    strict_counters = SEMISMOOTH.Counters()
    stability_counters = FROZEN.StabilityCounters()
    lanes = []

    original_run_stage = SEMISMOOTH._run_stage
    original_strict_stage = FROZEN._strict_stage
    original_strict_stages = FROZEN.STRICT_STAGES
    original_minimum = FROZEN.MIN_STRICT_STAGES
    SEMISMOOTH._run_stage = _prefix_stage
    FROZEN._strict_stage = _strict_stage
    FROZEN.STRICT_STAGES = original_strict_stages[:STRICT_STAGE_COUNT]
    FROZEN.MIN_STRICT_STAGES = STRICT_STAGE_COUNT
    try:
        prefix = _two_prefix_lanes(problem, deadline, prefix_counters)
        prefix_lanes = prefix["lanes"]
        if prefix["numeric_512_768_prefix_ready"] is True:
            _ACTIVE_STATE = _ModelState(phase="common-anchor-strict-polish")
            polished = FROZEN._postpolish_lane(
                problem,
                asdict(prefix_lanes[0]),
                deadline,
                strict_counters,
                stability_counters,
            )
            _PHASE_SUMMARIES.append(_ACTIVE_STATE.summary())
            if polished["status"] == "TARGET_STABILITY_REACHED":
                for bits, nominal_dps, _ in SEMISMOOTH.LANES:
                    lanes.append(
                        {
                            **polished,
                            "bits": bits,
                            "nominal_dps": nominal_dps,
                            "common_anchor_after_independent_512_768_prefix": True,
                        }
                    )
    finally:
        SEMISMOOTH._run_stage = original_run_stage
        FROZEN._strict_stage = original_strict_stage
        FROZEN.STRICT_STAGES = original_strict_stages
        FROZEN.MIN_STRICT_STAGES = original_minimum
        _ACTIVE_STATE = None

    ready = bool(
        len(lanes) == 3
        and all(row["status"] == "TARGET_STABILITY_REACHED" for row in lanes)
    )
    phase_summaries = [dict(row) for row in _PHASE_SUMMARIES]
    return {
        "variant": variant,
        "status": "TARGET_STABILITY_READY" if ready else "TARGET_STABILITY_FAILED",
        "target_stability_ready": ready,
        "numeric_v3_ready": ready,
        "lanes": FROZEN._jsonable(lanes),
        "adaptive_prefix": {
            "status": prefix["status"],
            "numeric_512_768_prefix_ready": prefix[
                "numeric_512_768_prefix_ready"
            ],
            "lanes": FROZEN._jsonable([asdict(row) for row in prefix["lanes"]]),
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix["configuration_512_768_disagreement_inf"]
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix["target_512_768_disagreement"]
            ),
            "escalation_counters": prefix["escalation_counters"],
            "escalation_events": FROZEN._jsonable(prefix["escalation_events"]),
        },
        "independent_prefix_lane_count": len(prefix["lanes"]),
        "independent_prefix_bits": [row.bits for row in prefix["lanes"]],
        "common_anchor_after_independent_prefix": bool(
            prefix["numeric_512_768_prefix_ready"]
        ),
        "stability_counters": {
            **asdict(stability_counters),
            "independent_prefix_bits": [row.bits for row in prefix["lanes"]],
            "configuration_512_768_disagreement_inf": FROZEN._jsonable(
                prefix["configuration_512_768_disagreement_inf"]
            ),
            "target_512_768_disagreement": FROZEN._jsonable(
                prefix["target_512_768_disagreement"]
            ),
            "strict_stage_count": STRICT_STAGE_COUNT,
            "hp_quasi_newton_configuration": CONFIGURATION,
            "hp_quasi_newton_phases": phase_summaries,
        },
        "semismooth_counters": {
            "prefix": asdict(prefix_counters),
            "strict": asdict(strict_counters),
        },
        "strict_stage_count": STRICT_STAGE_COUNT,
        "hp_quasi_newton": {
            "configuration": CONFIGURATION,
            "policy": asdict(_policy()),
            "phases": phase_summaries,
            "mechanism": KERNEL.mechanism_manifest(),
            "checkpointable": False,
            "resume_token": None,
        },
        "elapsed_seconds": time.monotonic() - started,
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
        "source_or_problem_modified": False,
        "coordinate_reparameterization": False,
    }


__all__ = [
    "CONFIGURATION",
    "CONFIGURATIONS",
    "EVENT_REFRESHED",
    "SHAMANSKII_M4",
    "STRICT_STAGE_COUNT",
    "VARIANT",
    "VARIANTS",
    "refine_endpoint",
]
