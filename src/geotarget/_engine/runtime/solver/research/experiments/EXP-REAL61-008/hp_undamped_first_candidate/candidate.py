"""Disposable undamped-first HP semismooth Newton corrective.

The only change to the frozen target-stability refiner is the step order at
each semismooth iteration: test the rank-filtered minimum-norm Newton step
before the unchanged positive-damping ladder.  Every trial still passes the
untouched semantic callback and must decrease the original scaled residual
merit.  No problem identity, geometry, truth, bound, or gauge is consumed.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-006/adaptive_hp_escalation/target_stable_candidate.py"
)
VARIANT = "UNDAMPED_MINIMUM_NORM_BEFORE_EXISTING_DAMPING_LADDER"
VARIANTS = (VARIANT,)


def _load_frozen():
    name = "geotarget_exp008_undamped_first_frozen_target_stability"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, FROZEN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(FROZEN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FROZEN = _load_frozen()
SEMISMOOTH = FROZEN.SEMISMOOTH
_ACTIVATION = {"stage_calls": 0, "undamped_trials": 0, "undamped_accepts": 0}


def _damping_schedule(current):
    """Undamped first, followed by the frozen five-value damping ladder."""

    value = mp.mpf(current)
    return (mp.mpf("0"),) + tuple(value * mp.power(100, index) for index in range(5))


def _run_stage(
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
    damping = mp.mpf("1e-6")
    damping_floor = mp.power(10, -min(240, max(30, int(dps) - 10)))
    trust_radius = mp.mpf("2")
    status = "ITERATION_LIMIT"
    final_residual = None
    final_merit = None
    ranks = []
    iterations = 0
    counters.precision_stages += 1
    _ACTIVATION["stage_calls"] += 1
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
            gate = SEMISMOOTH._stage_gate(dps, final)
            if variant == SEMISMOOTH.CORRECTIVE and int(dps) >= 180:
                gate = max(gate, mp.mpf("1e-104"))
            if final_residual <= gate:
                replay = SEMISMOOTH._residual(problem, z, dps, counters)
                final_residual = SEMISMOOTH._norm_inf(replay)
                if final_residual <= gate and SEMISMOOTH._semantic(
                    problem, z, dps, counters
                ):
                    status = "SUCCESS"
                else:
                    status = "REPLAY_GATE_FAILED"
                break

            opposing_before = counters.opposing_side_derivatives
            jacobian = SEMISMOOTH._adaptive_semismooth_jacobian(
                problem, z, residual, dps, counters
            )
            kink_active = counters.opposing_side_derivatives > opposing_before
            row_divisors, column_divisors, scaled_r, matrix, current_merit = (
                SEMISMOOTH._equilibrate(residual, jacobian)
            )
            final_merit = current_merit
            accepted = None
            accepted_damping = None

            for option, local_damping in enumerate(_damping_schedule(damping)):
                if option == 0:
                    _ACTIVATION["undamped_trials"] += 1
                else:
                    counters.damping_retries += int(option > 1)
                step, rank = SEMISMOOTH._damped_svd_step(
                    matrix,
                    scaled_r,
                    column_divisors,
                    local_damping,
                    dps,
                    counters,
                )
                ranks.append(rank)
                step_norm = SEMISMOOTH._norm_inf(step)
                if step_norm == 0:
                    continue
                if step_norm > trust_radius:
                    step = tuple(value * trust_radius / step_norm for value in step)
                alpha_schedule = (
                    ("1", "0.5", "0.25", "0.125", "0.0625")
                    if kink_active
                    else ("2", "1", "0.5", "0.25", "0.125", "0.0625")
                )
                for alpha_text in alpha_schedule:
                    alpha = mp.mpf(alpha_text)
                    trial = [z[index] + alpha * step[index] for index in range(len(z))]
                    if not all(mp.isfinite(value) for value in trial):
                        counters.rejected_trials += 1
                        continue
                    if not SEMISMOOTH._semantic(problem, trial, dps, counters):
                        counters.semantic_rejections += 1
                        continue
                    trial_residual = SEMISMOOTH._residual(problem, trial, dps, counters)
                    trial_merit = SEMISMOOTH._trial_merit(
                        trial_residual, row_divisors
                    )
                    if trial_merit < current_merit:
                        if accepted is None or trial_merit < accepted[0]:
                            accepted = (trial_merit, trial, alpha)
                            accepted_damping = local_damping
                    else:
                        counters.rejected_trials += 1
                if accepted is not None:
                    if local_damping == 0:
                        _ACTIVATION["undamped_accepts"] += 1
                    else:
                        damping = max(damping_floor, local_damping / 10)
                    break

            if accepted is None and variant == SEMISMOOTH.CORRECTIVE:
                fallback = SEMISMOOTH._cauchy_step(matrix, scaled_r, column_divisors)
                if fallback is not None:
                    counters.cauchy_fallbacks += 1
                    step_norm = SEMISMOOTH._norm_inf(fallback)
                    if step_norm > trust_radius:
                        fallback = tuple(value * trust_radius / step_norm for value in fallback)
                    for alpha_text in ("1", "0.25", "0.0625", "0.015625"):
                        alpha = mp.mpf(alpha_text)
                        trial = [z[index] + alpha * fallback[index] for index in range(len(z))]
                        if not SEMISMOOTH._semantic(problem, trial, dps, counters):
                            counters.semantic_rejections += 1
                            continue
                        trial_residual = SEMISMOOTH._residual(problem, trial, dps, counters)
                        trial_merit = SEMISMOOTH._trial_merit(
                            trial_residual, row_divisors
                        )
                        if trial_merit < current_merit:
                            accepted = (trial_merit, trial, alpha)
                            break
                        counters.rejected_trials += 1

            if accepted is None:
                status = "NO_SEMISMOOTH_DESCENT"
                break
            reduction = accepted[0] / current_merit
            z = accepted[1]
            counters.accepted_trials += 1
            if accepted[2] == 2:
                counters.alpha_two_accepts += 1
            if accepted[2] >= 1 and reduction < mp.mpf("0.2"):
                trust_radius = min(mp.mpf("32"), trust_radius * 2)
            elif accepted[2] < 1:
                trust_radius = max(mp.mpf("1e-6"), trust_radius / 2)

    return (
        status,
        z,
        SEMISMOOTH.StageRecord(
            dps=int(dps),
            status=status,
            iterations=iterations,
            residual_inf=final_residual,
            merit=final_merit,
            damping=damping,
            rank_min=min(ranks) if ranks else None,
            rank_max=max(ranks) if ranks else None,
        ),
    )


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = VARIANT,
    deadline_seconds: float = 23.0,
):
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")
    for key in _ACTIVATION:
        _ACTIVATION[key] = 0
    original = SEMISMOOTH._run_stage
    SEMISMOOTH._run_stage = _run_stage
    try:
        result = FROZEN.refine_endpoint(
            evaluator,
            values,
            variant=FROZEN.TARGET_STABLE,
            deadline_seconds=deadline_seconds,
        )
    finally:
        SEMISMOOTH._run_stage = original
    return {
        **result,
        "variant": variant,
        "undamped_first_corrective": dict(_ACTIVATION),
        "step_order": "UNDAMPED_MINIMUM_NORM_THEN_UNCHANGED_FIVE_VALUE_DAMPING_LADDER",
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
    }


__all__ = ["VARIANT", "VARIANTS", "refine_endpoint"]
