"""One-pass target-first high-precision continuation corrective.

This disposable experiment keeps the frozen undamped-first semismooth
corrector as its initial local mechanism, but does not throw away a
semantically valid lane merely because its first precision stage exhausted
the iteration budget.  One such lane is continued through increasing
precision.  The expensive spectrum-derived Newton trial loop is
deadline-aware and accepts the first original-residual descent instead of
enumerating every damping/alpha pair.  A common high-precision anchor is then
rounded independently and briefly corrected at 512 and 768 bits; the 1024-bit
lane is a fresh target/original-residual replay from that anchor.

Only opaque residual, semantic, and answer callbacks are used.  Source
equations, variables, guards, branches, and bounds are untouched; no problem
identity, family, truth, known target count, geometry rewrite, gauge, or
inferred bound is available to this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
UNDAMPED_PATH = HERE.parent / "hp_undamped_first_candidate/candidate.py"

# Keep the old public arm spelling as an accepted alias because the tiny
# source-only authority adapter passes that frozen arm name.  The result
# records the corrective's actual mechanism name.
FROZEN_ARM_ALIAS = "UNDAMPED_MINIMUM_NORM_BEFORE_EXISTING_DAMPING_LADDER"
VARIANT = "TARGET_FIRST_SHARED_HP_CONTINUATION_ACCEPTED_FIRST"
VARIANTS = (VARIANT, FROZEN_ARM_ALIAS)

SHARED_STAGES = (
    (110, "1e-62", 0),
    (180, "1e-116", 0),
    (240, "1e-146", 0),
    (300, "1e-181", 0),
    (360, "1e-221", 30),
)
SHARED_RESIDUAL_GATE = mp.mpf("1e-112")
SHARED_TARGET_GATE = mp.mpf("1e-112")
# The independent lane handoff uses the frozen public original-DSL gate.  An
# earlier disposable draft added an unrequested 1e-108 margin and thereby
# withheld lanes whose untouched residual already passed 1e-100.  Stronger
# shared target-stability diagnostics remain advisory; the frozen independent
# replay is the authority for the actual public contract.
LANE_GATE = mp.mpf("1e-100")


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


UNDAMPED = _load("geotarget_exp008_target_first_undamped", UNDAMPED_PATH)
TARGET_STABLE = UNDAMPED.FROZEN
SEMISMOOTH = UNDAMPED.SEMISMOOTH


@dataclass
class CorrectiveCounters:
    shared_prefix_stages: int = 0
    shared_spectral_stages: int = 0
    shared_progress_escalations: int = 0
    spectral_options_considered: int = 0
    spectral_alpha_trials: int = 0
    spectral_first_descent_accepts: int = 0
    spectral_deadline_stops: int = 0
    independent_lane_corrections: int = 0
    fresh_1024_replays: int = 0


def _numeric_text(value: object, dps: int) -> str:
    with mp.workdps(int(dps)):
        return mp.nstr(
            mp.mpf(value),
            n=max(80, min(340, int(dps) - 8)),
            strip_zeros=False,
        )


def _point_text(point: Sequence[object], dps: int) -> list[str]:
    return [_numeric_text(value, dps) for value in point]


def _observe(problem, z, dps: int, counters):
    with mp.workdps(int(dps)):
        if not SEMISMOOTH._semantic(problem, z, dps, counters):
            return None, None, False
        residual = SEMISMOOTH._norm_inf(
            SEMISMOOTH._residual(problem, z, dps, counters)
        )
        answer = mp.mpf(
            problem.evaluator.answer(SEMISMOOTH._external(problem, z), dps)
        )
        return residual, answer, bool(mp.isfinite(residual) and mp.isfinite(answer))


def _accepted_first_spectral_stage(
    problem,
    z,
    *,
    dps: int,
    gate: object,
    stencil_extra: int,
    counters,
    corrective: CorrectiveCounters,
    deadline: float,
    max_iterations: int,
):
    """Spectrum-filtered Newton with prompt deadline and first-descent exit."""

    gate = mp.mpf(gate)
    status = "ITERATION_LIMIT"
    final_residual = None
    final_merit = None
    ranks: list[int] = []
    iterations = 0
    counters.precision_stages += 1
    with mp.workdps(int(dps)):
        for iterations in range(1, int(max_iterations) + 1):
            if time.monotonic() >= deadline:
                corrective.spectral_deadline_stops += 1
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
                status = "SUCCESS" if final_residual <= gate else "REPLAY_GATE_FAILED"
                break

            jacobian, kink_active = TARGET_STABLE._fine_semismooth_jacobian(
                problem,
                z,
                residual,
                dps,
                counters,
                stencil_extra=int(stencil_extra),
            )
            row_divisors, column_divisors, scaled_r, matrix, current_merit = (
                TARGET_STABLE._fine_equilibrate(residual, jacobian, dps)
            )
            final_merit = current_merit
            step_options = TARGET_STABLE._filtered_newton_steps(
                matrix, scaled_r, column_divisors, dps, counters
            )
            schedule = (
                ("1", "0.5", "0.25", "0.125", "0.0625", "0.015625")
                if kink_active
                else (
                    "2",
                    "1",
                    "0.5",
                    "0.25",
                    "0.125",
                    "0.0625",
                    "0.015625",
                    "0.00390625",
                )
            )
            accepted = None
            deadline_hit = False
            for option_index, (step, rank, damping) in enumerate(step_options):
                if time.monotonic() >= deadline:
                    deadline_hit = True
                    break
                corrective.spectral_options_considered += 1
                if option_index:
                    counters.damping_retries += 1
                ranks.append(rank)
                step_norm = SEMISMOOTH._norm_inf(step)
                if step_norm == 0:
                    continue
                if step_norm > 2:
                    step = tuple(value * 2 / step_norm for value in step)
                for alpha_text in schedule:
                    if time.monotonic() >= deadline:
                        deadline_hit = True
                        break
                    corrective.spectral_alpha_trials += 1
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
                        # The first accepted original-merit descent terminates
                        # both loops.  No remaining spectral option is charged.
                        accepted = (trial_merit, trial, alpha, damping)
                        corrective.spectral_first_descent_accepts += 1
                        break
                    counters.rejected_trials += 1
                if accepted is not None or deadline_hit:
                    break

            if deadline_hit and accepted is None:
                corrective.spectral_deadline_stops += 1
                status = "DEADLINE_REACHED"
                break
            if accepted is None:
                status = "NO_SEMISMOOTH_DESCENT"
                break
            z = accepted[1]
            counters.accepted_trials += 1
            if accepted[2] == 2:
                counters.alpha_two_accepts += 1

    return (
        status,
        z,
        SEMISMOOTH.StageRecord(
            dps=int(dps),
            status=status,
            iterations=iterations,
            residual_inf=final_residual,
            merit=final_merit,
            damping=mp.mpf("0"),
            rank_min=min(ranks) if ranks else None,
            rank_max=max(ranks) if ranks else None,
        ),
    )


def _independent_lane(
    problem,
    anchor_text: Sequence[str],
    *,
    bits: int,
    dps: int,
    correct: bool,
    counters,
    corrective: CorrectiveCounters,
    deadline: float,
):
    with mp.workdps(int(dps)):
        external = [mp.mpf(value) for value in anchor_text]
        z = TARGET_STABLE._normalized(problem, external, dps)

    records = []
    if correct:
        corrective.independent_lane_corrections += 1
        status, z, record = _accepted_first_spectral_stage(
            problem,
            z,
            dps=dps,
            gate=LANE_GATE,
            stencil_extra=0,
            counters=counters,
            corrective=corrective,
            deadline=deadline,
            max_iterations=6,
        )
        records.append(asdict(record))
    else:
        corrective.fresh_1024_replays += 1
        residual, _answer, semantic = _observe(problem, z, dps, counters)
        status = (
            "SUCCESS"
            if semantic and residual is not None and residual <= mp.mpf("1e-100")
            else "FRESH_1024_REPLAY_FAILED"
        )

    residual, answer, semantic = _observe(problem, z, dps, counters)
    if not semantic or residual is None or answer is None:
        return {
            "bits": bits,
            "nominal_dps": dps,
            "status": "SEMANTIC_REJECTED",
            "point": None,
            "answer": None,
            "residual_inf": None,
            "stages": records,
        }
    # The external tuple is constructed under this lane's own precision and
    # serialized immediately, making the 512 and 768 starts independent
    # roundings of the shared anchor.
    with mp.workdps(int(dps)):
        point = SEMISMOOTH._external(problem, z)
        point_text = _point_text(point, dps)
    return {
        "bits": bits,
        "nominal_dps": dps,
        "status": "TARGET_STABILITY_REACHED" if status == "SUCCESS" else status,
        "point": point_text,
        "answer": _numeric_text(answer, dps),
        "residual_inf": _numeric_text(residual, dps),
        "stages": records,
    }


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = VARIANT,
    deadline_seconds: float = 23.0,
) -> dict[str, object]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")

    started = time.monotonic()
    deadline = started + max(0.03, float(deadline_seconds))
    # Keep a small deterministic portion for two short independent
    # corrections.  The surrounding worker performs the fresh original-DSL
    # replay and owned PSLQ after this function returns.
    reserve = min(3.0, max(1.2, float(deadline_seconds) * 0.14))
    shared_deadline = max(started + 0.02, deadline - reserve)
    problem = TARGET_STABLE._problem(evaluator, values)
    counters = SEMISMOOTH.Counters()
    corrective = CorrectiveCounters()
    records: list[dict[str, object]] = []
    target_observations: list[dict[str, object]] = []
    status = "SHARED_CONTINUATION_FAILED"
    initial_residual = None

    with mp.workdps(70):
        z = TARGET_STABLE._normalized(problem, values, 70)
    best_z = list(z)
    best_residual, previous_answer, semantic = _observe(problem, z, 70, counters)
    if not semantic or best_residual is None:
        status = "FLOAT64_SEMANTIC_REJECTED"
    else:
        initial_residual = best_residual
        try:
            corrective.shared_prefix_stages += 1
            prefix_status, z, prefix_record = UNDAMPED._run_stage(
                problem,
                z,
                dps=70,
                final=False,
                variant=SEMISMOOTH.CORRECTIVE,
                counters=counters,
                deadline=shared_deadline,
                max_iterations=128,
            )
            after_residual, after_answer, after_semantic = _observe(
                problem, z, 70, counters
            )
            records.append(
                {
                    **asdict(prefix_record),
                    "mode": "FROZEN_UNDAMPED_FIRST_PREFIX",
                    "initial_residual_inf": initial_residual,
                    "after_residual_inf": after_residual,
                }
            )
            if after_semantic and after_residual is not None:
                if after_residual < best_residual:
                    best_z = list(z)
                    best_residual = after_residual
                previous_answer = after_answer
                if prefix_status != "SUCCESS" and after_residual < initial_residual:
                    corrective.shared_progress_escalations += 1
            z = list(best_z)

            for dps, gate_text, stencil_extra in SHARED_STAGES:
                if time.monotonic() >= shared_deadline:
                    status = "SHARED_DEADLINE_REACHED"
                    break
                before_residual, before_answer, before_semantic = _observe(
                    problem, z, dps, counters
                )
                if not before_semantic or before_residual is None:
                    status = "SEMANTIC_REJECTED"
                    break
                corrective.shared_spectral_stages += 1
                stage_status, trial_z, stage_record = _accepted_first_spectral_stage(
                    problem,
                    z,
                    dps=dps,
                    gate=mp.mpf(gate_text),
                    stencil_extra=stencil_extra,
                    counters=counters,
                    corrective=corrective,
                    deadline=shared_deadline,
                    max_iterations=48,
                )
                after_residual, after_answer, after_semantic = _observe(
                    problem, trial_z, dps, counters
                )
                target_delta = None
                if previous_answer is not None and after_answer is not None:
                    with mp.workdps(int(dps) + 20):
                        target_delta = abs(mp.mpf(after_answer) - mp.mpf(previous_answer))
                records.append(
                    {
                        **asdict(stage_record),
                        "mode": "ACCEPTED_FIRST_SPECTRAL_CONTINUATION",
                        "requested_gate": gate_text,
                        "stencil_extra_digits": stencil_extra,
                        "before_residual_inf": before_residual,
                        "after_residual_inf": after_residual,
                        "target_delta_from_previous_stage": target_delta,
                    }
                )
                target_observations.append(
                    {
                        "dps": dps,
                        "residual_inf": after_residual,
                        "answer": after_answer,
                        "target_delta": target_delta,
                    }
                )
                if after_semantic and after_residual is not None:
                    if after_residual <= best_residual:
                        best_z = list(trial_z)
                        best_residual = after_residual
                    z = list(best_z)
                    previous_answer = after_answer
                else:
                    status = "SEMANTIC_REJECTED"
                    break

                target_stable = bool(
                    dps >= 240
                    and best_residual <= SHARED_RESIDUAL_GATE
                    and target_delta is not None
                    and target_delta <= SHARED_TARGET_GATE
                )
                if target_stable:
                    status = "SHARED_TARGET_STABLE"
                    break
                if stage_status in {"DEADLINE_REACHED", "SEMANTIC_REJECTED"}:
                    status = stage_status
                    break
                if stage_status != "SUCCESS" and after_residual < before_residual:
                    corrective.shared_progress_escalations += 1
                    continue
                # Precision escalation is still allowed after a numerical
                # plateau when the current point is already within the public
                # residual gate; higher precision may stabilize the target.
                if stage_status != "SUCCESS" and after_residual > mp.mpf("1e-100"):
                    status = stage_status
                    break
            else:
                status = "SHARED_STAGE_LIMIT"
        except SEMISMOOTH._Failure as error:
            status = error.status
        except Exception:
            status = "CALLBACK_OR_NUMERIC_EXCEPTION"

    lanes = []
    # Independent replay remains useful if the shared continuation reached
    # the public residual contract even when its deliberately stronger target
    # stability diagnostic did not fire.  The untouched worker is final.
    if best_residual is not None and best_residual <= mp.mpf("1e-100"):
        with mp.workdps(360):
            anchor_external = SEMISMOOTH._external(problem, best_z)
            anchor_text = _point_text(anchor_external, 360)
        for bits, dps, correct in ((512, 180, True), (768, 252, True), (1024, 340, False)):
            if time.monotonic() >= deadline and bits != 1024:
                break
            lane = _independent_lane(
                problem,
                anchor_text,
                bits=bits,
                dps=dps,
                correct=correct,
                counters=counters,
                corrective=corrective,
                deadline=deadline,
            )
            lanes.append(lane)
            if lane["status"] != "TARGET_STABILITY_REACHED":
                break

    ready = bool(
        len(lanes) == 3
        and all(row.get("status") == "TARGET_STABILITY_REACHED" for row in lanes)
    )
    return {
        "variant": VARIANT,
        "status": "TARGET_STABILITY_READY" if ready else status,
        "target_stability_ready": ready,
        "numeric_v3_ready": ready,
        "lanes": lanes,
        "independent_prefix_lane_count": 1,
        "common_anchor_after_independent_prefix": False,
        "shared_progressed_lane_continuation": True,
        "shared_stage_records": records,
        "target_observations": target_observations,
        "lane_statuses": [
            {
                "bits": row.get("bits"),
                "status": row.get("status"),
                "residual_inf": row.get("residual_inf"),
            }
            for row in lanes
        ],
        "initial_residual_inf": (
            None if initial_residual is None else _numeric_text(initial_residual, 340)
        ),
        "best_residual_inf": (
            None if best_residual is None else _numeric_text(best_residual, 340)
        ),
        "corrective_counters": asdict(corrective),
        "semismooth_counters": asdict(counters),
        "elapsed_seconds": time.monotonic() - started,
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
    }


__all__ = ["FROZEN_ARM_ALIAS", "VARIANT", "VARIANTS", "refine_endpoint"]
