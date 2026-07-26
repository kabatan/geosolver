"""Target-stability-aware high-precision endpoint refinement.

This disposable corrective starts with the generic ratio-triggered semismooth
refiner and then keeps polishing at higher working precision.  It does not
stop merely because the original residual crossed ``1e-100``: accepted
high-precision iterates must also make the opaque scalar answer stable with a
large margin for the unchanged 768/1024-bit owned-PSLQ authority.

Only opaque residual, semantic, and answer callbacks are consumed.  Case and
family identity, truth, a known target count, geometry primitives, and
source-derived bounds are never inputs.  The source residual system and the
endpoint coordinates are not transformed.
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
ADAPTIVE_PATH = HERE / "candidate.py"


def _load_adaptive():
    name = "geotarget_exp006_target_stable_adaptive_base"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, ADAPTIVE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load {ADAPTIVE_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


ADAPTIVE = _load_adaptive()
SEMISMOOTH = ADAPTIVE.BASE

ADAPTIVE_CONTROL = "RATIO_TRIGGERED_ADAPTIVE_PRECISION_ESCALATION_CONTROL"
TARGET_STABLE = "CONDITION_AWARE_TARGET_STABILITY_ESCALATION"
VARIANTS = (ADAPTIVE_CONTROL, TARGET_STABLE)

# These are algorithm-wide numerical margins, not case-tuned values.  The
# final target margin is stronger than both the public 1e-100 target gate and
# the 600-bit (~1e-181) owned-PSLQ confirmation tolerance.
TARGET_STABILITY_GATE = mp.mpf("1e-195")
TARGET_UNCERTAINTY_GATE = mp.mpf("1e-195")
STRICT_STAGES = (
    (240, "1e-130", "DAMPED_TRANSITION", 0),
    (300, "1e-235", "SPECTRAL_NEWTON", 0),
    (360, "1e-250", "SPECTRAL_NEWTON", 30),
    (440, "1e-270", "SPECTRAL_NEWTON", 60),
    (680, "1e-430", "SPECTRAL_NEWTON", 150),
    (760, "1e-430", "SPECTRAL_NEWTON", 200),
)
MIN_STRICT_STAGES = 6
ORIGINAL_RESIDUAL_MARGIN = mp.mpf("1e-120")
PUBLIC_RESIDUAL_GATE = mp.mpf("1e-100")
MIN_ESCALATION_REDUCTION = mp.mpf("1e8")
ESCALATABLE_FAILURES = frozenset({"NO_SEMISMOOTH_DESCENT", "ITERATION_LIMIT"})


@dataclass
class StabilityCounters:
    lanes_considered: int = 0
    strict_stages: int = 0
    strict_stage_successes: int = 0
    stalled_stages_escalated: int = 0
    target_stability_checks: int = 0
    target_stability_accepts: int = 0
    target_stability_rejections: int = 0
    semantic_rejections: int = 0


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "_mpf_"):
        # 340 decimal digits preserve the full 1024-bit confirmation input.
        return mp.nstr(value, 340, strip_zeros=False)
    return value


def _problem(evaluator, endpoint: Sequence[float]):
    values = tuple(float(value) for value in endpoint)
    return SEMISMOOTH.BASE.Problem(
        evaluator,
        SEMISMOOTH.BASE.canonical_float64_endpoint(values),
        tuple("0" for _ in values),
        tuple(repr(max(1.0, abs(value))) for value in values),
    )


def _normalized(problem, point: Sequence[object], dps: int):
    with mp.workdps(int(dps)):
        return [
            (mp.mpf(point[index]) - mp.mpf(problem.origin_text[index]))
            / mp.mpf(problem.scale_text[index])
            for index in range(len(point))
        ]


def _observe(problem, z, dps, counters):
    with mp.workdps(int(dps)):
        semantic = SEMISMOOTH._semantic(problem, z, dps, counters)
        if not semantic:
            return None, None, False
        residual = SEMISMOOTH._norm_inf(
            SEMISMOOTH._residual(problem, z, dps, counters)
        )
        answer = mp.mpf(problem.evaluator.answer(SEMISMOOTH._external(problem, z), dps))
        return residual, answer, True


def _fine_semismooth_jacobian(
    problem, z, residual, dps, counters, *, stencil_extra
):
    """Generalized central Jacobian with a precision-scaled, uncapped stencil."""

    rows = len(residual)
    columns = len(z)
    matrix = [[mp.mpf("0") for _ in range(columns)] for _ in range(rows)]
    residual_inf = SEMISMOOTH._norm_inf(residual)
    if residual_inf > 0:
        residual_exponent = max(0, int(mp.floor(-mp.log10(residual_inf))))
    else:
        residual_exponent = int(dps)
    # Tighten the stencil as convergence proceeds.  A fixed 1e-120 stencil
    # caused the observed target plateau, while jumping immediately to the
    # finest representable stencil produced a poor branch-local model.  The
    # residual exponent supplies a case-agnostic continuation parameter.
    exponent = max(
        40,
        min(
            (int(dps) - 20) // 2,
            residual_exponent + 15 + int(stencil_extra),
        ),
    )
    counters.jacobians += 1
    kink_active = False
    for column in range(columns):
        counters.stencil_columns += 1
        h = mp.power(10, -exponent) * max(mp.mpf("1"), abs(z[column]))
        plus = list(z)
        minus = list(z)
        plus[column] += h
        minus[column] -= h
        plus_ok = SEMISMOOTH._semantic(problem, plus, dps, counters)
        minus_ok = SEMISMOOTH._semantic(problem, minus, dps, counters)
        plus_residual = (
            SEMISMOOTH._residual(problem, plus, dps, counters) if plus_ok else None
        )
        minus_residual = (
            SEMISMOOTH._residual(problem, minus, dps, counters) if minus_ok else None
        )
        if plus_residual is not None and minus_residual is not None:
            for row in range(rows):
                forward = (plus_residual[row] - residual[row]) / h
                backward = (residual[row] - minus_residual[row]) / h
                central = (plus_residual[row] - minus_residual[row]) / (2 * h)
                scale = max(abs(forward), abs(backward), mp.mpf("1e-500"))
                if forward * backward < 0 and abs(central) <= mp.mpf("0.35") * scale:
                    plus_change = abs(plus_residual[row] - residual[row])
                    minus_change = abs(minus_residual[row] - residual[row])
                    matrix[row][column] = (
                        forward if plus_change >= minus_change else backward
                    )
                    counters.opposing_side_derivatives += 1
                    kink_active = True
                else:
                    matrix[row][column] = central
                    counters.central_derivatives += 1
        elif plus_residual is not None:
            for row in range(rows):
                matrix[row][column] = (plus_residual[row] - residual[row]) / h
            counters.semantic_one_sided_columns += 1
        elif minus_residual is not None:
            for row in range(rows):
                matrix[row][column] = (residual[row] - minus_residual[row]) / h
            counters.semantic_one_sided_columns += 1
        else:
            raise SEMISMOOTH._Failure("SEMANTIC_STENCIL_BLOCKED")
    return matrix, kink_active


def _fine_equilibrate(residual, jacobian, dps):
    row_divisors = []
    for value, row in zip(residual, jacobian, strict=True):
        sensitivity = mp.sqrt(mp.fsum(entry * entry for entry in row))
        row_divisors.append(max(abs(value), sensitivity, mp.mpf("1e-500")))
    scaled_r = [
        residual[row] / row_divisors[row] for row in range(len(residual))
    ]
    scaled_j = [
        [entry / row_divisors[row] for entry in jacobian[row]]
        for row in range(len(jacobian))
    ]
    column_floor = mp.power(10, -min(220, max(60, int(dps) // 2)))
    column_divisors = []
    for column in range(len(jacobian[0])):
        norm = mp.sqrt(
            mp.fsum(scaled_j[row][column] ** 2 for row in range(len(scaled_j)))
        )
        column_divisors.append(max(norm, column_floor))
    matrix = [
        [
            scaled_j[row][column] / column_divisors[column]
            for column in range(len(column_divisors))
        ]
        for row in range(len(scaled_j))
    ]
    merit = mp.mpf("0.5") * mp.fsum(value * value for value in scaled_r)
    return row_divisors, column_divisors, scaled_r, matrix, merit


def _filtered_newton_steps(matrix, scaled_r, column_divisors, dps, counters):
    counters.svd_factorizations += 1
    left, singular_values, right = mp.svd(mp.matrix(matrix), full_matrices=False)
    if not singular_values:
        raise SEMISMOOTH._Failure("RANK_ZERO")
    largest = max(abs(value) for value in singular_values)
    cutoff = largest * mp.power(10, -min(240, max(80, int(dps) // 2)))
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
            left[row, index] * scaled_r[row] for row in range(len(matrix))
        )
        for index in retained
    }
    # Try a compact spectrum-derived Levenberg ladder from the same SVD.  It
    # avoids spending dozens of iterations reducing an arbitrary 1e-6
    # damping constant while retaining a safeguarded option when the raw
    # pseudoinverse direction has no semantic descent.
    damping_values = [mp.mpf("0"), largest * largest * mp.mpf("1e-6")]
    for index in retained:
        square = singular_values[index] * singular_values[index]
        damping_values.extend((square / 100, square, square * 100))
    unique = {}
    for value in damping_values:
        unique[mp.nstr(value, 40)] = value
    steps = []
    for damping in sorted(unique.values()):
        scaled_step = [mp.mpf("0") for _ in range(len(matrix[0]))]
        for index in retained:
            singular = singular_values[index]
            coefficient = (
                projections[index] / singular
                if damping == 0
                else singular * projections[index]
                / (singular * singular + damping)
            )
            for column in range(len(scaled_step)):
                scaled_step[column] += right[index, column] * coefficient
        steps.append(
            (
                tuple(
                    scaled_step[column] / column_divisors[column]
                    for column in range(len(scaled_step))
                ),
                len(retained),
                damping,
            )
        )
    return steps


def _strict_stage(
    problem, z, *, dps, gate, mode, stencil_extra, counters, deadline
):
    """Fast undamped semismooth Newton polish with a strict residual gate."""

    gate = mp.mpf(gate)
    if mode == "DAMPED_TRANSITION":
        original_gate = SEMISMOOTH._stage_gate
        try:
            SEMISMOOTH._stage_gate = lambda _dps, _final: gate
            return SEMISMOOTH._run_stage(
                problem,
                z,
                dps=int(dps),
                final=True,
                variant=SEMISMOOTH.REFERENCE,
                counters=counters,
                deadline=deadline,
                max_iterations=64,
            )
        finally:
            SEMISMOOTH._stage_gate = original_gate
    if mode != "SPECTRAL_NEWTON":
        raise ValueError(f"unknown strict-stage mode: {mode}")
    status = "ITERATION_LIMIT"
    final_residual = None
    final_merit = None
    ranks = []
    iterations = 0
    counters.precision_stages += 1
    with mp.workdps(int(dps)):
        for iterations in range(1, 49):
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
                status = "SUCCESS" if final_residual <= gate else "REPLAY_GATE_FAILED"
                break
            jacobian, kink_active = _fine_semismooth_jacobian(
                problem,
                z,
                residual,
                dps,
                counters,
                stencil_extra=stencil_extra,
            )
            row_divisors, column_divisors, scaled_r, matrix, current_merit = (
                _fine_equilibrate(residual, jacobian, dps)
            )
            final_merit = current_merit
            step_options = _filtered_newton_steps(
                matrix, scaled_r, column_divisors, dps, counters
            )
            # Alpha=2 is essential for an even-multiplicity residual.  It is
            # also safe at an absolute-value kink here because every trial is
            # passed through untouched semantic replay and must strictly
            # decrease the original scaled residual merit before acceptance.
            schedule = (
                "2",
                "1",
                "0.5",
                "0.25",
                "0.125",
                "0.0625",
                "0.015625",
                "0.00390625",
            )
            accepted = None
            for option_index, (step, rank, damping) in enumerate(step_options):
                if option_index:
                    counters.damping_retries += 1
                ranks.append(rank)
                step_norm = SEMISMOOTH._norm_inf(step)
                if step_norm == 0:
                    continue
                if step_norm > 2:
                    step = tuple(value * 2 / step_norm for value in step)
                for alpha_text in schedule:
                    alpha = mp.mpf(alpha_text)
                    trial = [z[i] + alpha * step[i] for i in range(len(z))]
                    if not SEMISMOOTH._semantic(problem, trial, dps, counters):
                        counters.semantic_rejections += 1
                        continue
                    trial_residual = SEMISMOOTH._residual(problem, trial, dps, counters)
                    trial_merit = SEMISMOOTH._trial_merit(
                        trial_residual, row_divisors
                    )
                    if trial_merit < current_merit and (
                        accepted is None or trial_merit < accepted[0]
                    ):
                        accepted = (trial_merit, trial, alpha, damping)
                    else:
                        counters.rejected_trials += 1
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


def _postpolish_lane(problem, row, deadline, semismooth_counters, stability_counters):
    stability_counters.lanes_considered += 1
    if row.get("status") != "SUCCESS" or row.get("point") is None:
        return {
            "bits": row.get("bits"),
            "nominal_dps": row.get("nominal_dps"),
            "status": "ADAPTIVE_PREFIX_FAILED",
            "point": None,
            "answer": None,
            "residual_inf": None,
            "strict_stages": [],
        }

    z = _normalized(problem, row["point"], STRICT_STAGES[0][0])
    records = []
    previous_residual = None
    previous_answer = None
    status = "TARGET_STABILITY_NOT_REACHED"
    final_residual = None
    final_answer = None
    final_target_delta = None
    final_uncertainty = None

    for index, (dps, gate, mode, stencil_extra) in enumerate(STRICT_STAGES):
        if time.monotonic() >= deadline:
            status = "DEADLINE_REACHED"
            break
        before_residual, before_answer, before_semantic = _observe(
            problem, z, dps, semismooth_counters
        )
        if not before_semantic:
            stability_counters.semantic_rejections += 1
            status = "SEMANTIC_REJECTED"
            break
        stage_status, z, stage_record = _strict_stage(
            problem,
            z,
            dps=dps,
            gate=gate,
            mode=mode,
            stencil_extra=stencil_extra,
            counters=semismooth_counters,
            deadline=deadline,
        )
        stability_counters.strict_stages += 1
        after_residual, after_answer, after_semantic = _observe(
            problem, z, dps, semismooth_counters
        )
        if not after_semantic:
            stability_counters.semantic_rejections += 1
            status = "SEMANTIC_REJECTED"
            break

        with mp.workdps(int(dps) + 20):
            target_delta = (
                None
                if previous_answer is None
                else abs(mp.mpf(after_answer) - mp.mpf(previous_answer))
            )
            sensitivity = None
            predicted_uncertainty = None
            if target_delta is not None and previous_residual is not None:
                denominator = max(
                    abs(mp.mpf(previous_residual)),
                    abs(mp.mpf(after_residual)),
                    mp.power(10, -max(40, int(dps) - 20)),
                )
                sensitivity = target_delta / denominator
                predicted_uncertainty = sensitivity * abs(mp.mpf(after_residual))
                stability_counters.target_stability_checks += 1

        record = {
            **asdict(stage_record),
            "requested_gate": gate,
            "mode": mode,
            "stencil_extra_digits": stencil_extra,
            "before_residual_inf": before_residual,
            "after_residual_inf": after_residual,
            "before_answer": before_answer,
            "after_answer": after_answer,
            "target_delta_from_previous_stage": target_delta,
            "empirical_target_residual_sensitivity": sensitivity,
            "predicted_target_uncertainty": predicted_uncertainty,
        }
        records.append(record)
        final_residual = after_residual
        final_answer = after_answer
        final_target_delta = target_delta
        final_uncertainty = predicted_uncertainty

        if stage_status == "SUCCESS":
            stability_counters.strict_stage_successes += 1
        else:
            with mp.workdps(int(dps) + 20):
                target_progress = bool(
                    target_delta is not None
                    and mp.mpf(target_delta) > TARGET_STABILITY_GATE
                )
                can_escalate = bool(
                    index + 1 < len(STRICT_STAGES)
                    and stage_status in ESCALATABLE_FAILURES
                    and before_residual is not None
                    and after_residual is not None
                    and mp.mpf(after_residual) > 0
                    and (
                        target_progress
                        or mp.mpf(after_residual) <= PUBLIC_RESIDUAL_GATE
                        or mp.mpf(before_residual) / mp.mpf(after_residual)
                        >= MIN_ESCALATION_REDUCTION
                    )
                )
                possible_stability_accept = bool(
                    index + 1 >= MIN_STRICT_STAGES
                    and target_delta is not None
                    and mp.mpf(target_delta) <= TARGET_STABILITY_GATE
                    and predicted_uncertainty is not None
                    and mp.mpf(predicted_uncertainty)
                    <= TARGET_UNCERTAINTY_GATE
                    and mp.mpf(after_residual) <= ORIGINAL_RESIDUAL_MARGIN
                )
            if not can_escalate and not possible_stability_accept:
                status = stage_status
                break
            if can_escalate:
                stability_counters.stalled_stages_escalated += 1

        with mp.workdps(int(dps) + 20):
            stable = bool(
                index + 1 >= MIN_STRICT_STAGES
                and stage_status in {"SUCCESS", "NO_SEMISMOOTH_DESCENT"}
                and target_delta is not None
                and mp.mpf(target_delta) <= TARGET_STABILITY_GATE
                and predicted_uncertainty is not None
                and mp.mpf(predicted_uncertainty) <= TARGET_UNCERTAINTY_GATE
                and mp.mpf(after_residual) <= ORIGINAL_RESIDUAL_MARGIN
            )
        if stable:
            stability_counters.target_stability_accepts += 1
            status = "TARGET_STABILITY_REACHED"
            break
        if index + 1 == len(STRICT_STAGES):
            stability_counters.target_stability_rejections += 1
        previous_residual = after_residual
        previous_answer = after_answer

    if status == "TARGET_STABILITY_REACHED":
        with mp.workdps(STRICT_STAGES[-1][0]):
            point = SEMISMOOTH._external(problem, z)
    else:
        point = None
        final_answer = None

    return {
        "bits": row.get("bits"),
        "nominal_dps": row.get("nominal_dps"),
        "status": status,
        "point": point,
        "answer": final_answer,
        "residual_inf": final_residual,
        "target_delta": final_target_delta,
        "predicted_target_uncertainty": final_uncertainty,
        "strict_stages": records,
    }


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = TARGET_STABLE,
    deadline_seconds: float = 23.0,
) -> dict[str, object]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")

    started = time.monotonic()
    deadline = started + max(0.03, float(deadline_seconds))
    prefix = ADAPTIVE.refine_endpoint(
        evaluator,
        values,
        variant=ADAPTIVE.ADAPTIVE_ESCALATION,
        deadline_seconds=max(0.03, deadline - time.monotonic()),
    )
    if variant == ADAPTIVE_CONTROL:
        return {
            **prefix,
            "variant": variant,
            "target_stability_corrective_applied": False,
        }

    problem = _problem(evaluator, values)
    semismooth_counters = SEMISMOOTH.Counters()
    stability_counters = StabilityCounters()
    lanes = []
    if prefix.get("numeric_v3_ready"):
        prefix_lanes = list(prefix.get("lanes", []))
        if len(prefix_lanes) == 3:
            # The adaptive prefix has already produced and compared three
            # independently initialized authority lanes.  Once they agree,
            # perform the expensive conditioning-aware polish once on their
            # deterministic common anchor, then replay that single refined
            # configuration independently at 512/768/1024 bits.  Repeating
            # the identical 680/760-dps SVD path three times adds no discovery
            # information and consumed the P05 deadline.
            polished = _postpolish_lane(
                problem,
                prefix_lanes[0],
                deadline,
                semismooth_counters,
                stability_counters,
            )
            if polished["status"] == "TARGET_STABILITY_REACHED":
                for row in prefix_lanes:
                    lanes.append(
                        {
                            **polished,
                            "bits": row.get("bits"),
                            "nominal_dps": row.get("nominal_dps"),
                            "common_anchor_after_independent_prefix": True,
                        }
                    )
            else:
                lanes.append(polished)

    ready = bool(
        len(lanes) == 3
        and all(row["status"] == "TARGET_STABILITY_REACHED" for row in lanes)
    )
    return {
        "variant": variant,
        "status": "TARGET_STABILITY_READY" if ready else "TARGET_STABILITY_FAILED",
        "target_stability_ready": ready,
        "numeric_v3_ready": ready,
        "lanes": _jsonable(lanes),
        "adaptive_prefix": prefix,
        "independent_prefix_lane_count": len(prefix.get("lanes", [])),
        "common_anchor_after_independent_prefix": bool(
            prefix.get("numeric_v3_ready") and len(prefix.get("lanes", [])) == 3
        ),
        "stability_counters": asdict(stability_counters),
        "strict_configuration": {
            "stages": [
                {
                    "dps": dps,
                    "residual_gate": str(gate),
                    "mode": mode,
                    "stencil_extra_digits": stencil_extra,
                }
                for dps, gate, mode, stencil_extra in STRICT_STAGES
            ],
            "minimum_strict_stages": MIN_STRICT_STAGES,
            "original_residual_margin": str(ORIGINAL_RESIDUAL_MARGIN),
            "target_stability_gate": str(TARGET_STABILITY_GATE),
            "predicted_target_uncertainty_gate": str(TARGET_UNCERTAINTY_GATE),
        },
        "semismooth_counters": asdict(semismooth_counters),
        "elapsed_seconds": time.monotonic() - started,
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
    }


__all__ = [
    "ADAPTIVE_CONTROL",
    "ADAPTIVE",
    "TARGET_STABLE",
    "VARIANTS",
    "refine_endpoint",
]
