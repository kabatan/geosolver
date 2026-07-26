"""Adaptive-precision semismooth pseudo-transient endpoint corrector.

This is a disposable algorithm experiment.  Its only problem-facing seam is an
opaque numerical residual/semantic/answer evaluator plus one finite Float64
endpoint.  It does not inspect geometry primitives, case identity, family,
truth, a known target count, or source bounds, and it never changes the source
residual system.

The mechanism is deliberately complementary to the existing common-anchor
RRQR refiner.  The latter uses a comparatively wide high-order stencil and can
cross an absolute-value kink even when an endpoint is already within 1e-16 of
a root.  Here the stencil width follows working precision (roughly
``10**(-dps/2)``), a one-sided generalized derivative is selected only when
the two sides visibly oppose, and a damped SVD step is globalized as a
pseudo-transient continuation step.  All three authority lanes repeat the
same 70/110/180-dps prefix from the identical Float64 endpoint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-004/hp_independent_rrqr_refiner_v3/candidate.py"
)


def _load_base():
    name = "geotarget_exp005_nearroot_semismooth_base"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    specification = importlib.util.spec_from_file_location(name, BASE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load {BASE_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_base()

REFERENCE = "ADAPTIVE_SEMISMOOTH_PTC_REFERENCE"
CORRECTIVE = "ADAPTIVE_SEMISMOOTH_PTC_CAUCHY_CORRECTIVE"
VARIANTS = (REFERENCE, CORRECTIVE)
FINAL_GATE = mp.mpf("1e-112")
AGREEMENT_GATE = mp.mpf("1e-100")
LANES = (
    (512, 155, (70, 110, 180)),
    (768, 232, (70, 110, 180, 252)),
    (1024, 320, (70, 110, 180, 340)),
)


@dataclass
class Counters:
    semantic_calls: int = 0
    residual_calls: int = 0
    jacobians: int = 0
    stencil_columns: int = 0
    central_derivatives: int = 0
    opposing_side_derivatives: int = 0
    semantic_one_sided_columns: int = 0
    svd_factorizations: int = 0
    rank_deficient_steps: int = 0
    damping_retries: int = 0
    accepted_trials: int = 0
    rejected_trials: int = 0
    semantic_rejections: int = 0
    alpha_two_accepts: int = 0
    cauchy_fallbacks: int = 0
    precision_stages: int = 0


@dataclass
class StageRecord:
    dps: int
    status: str
    iterations: int
    residual_inf: object | None
    merit: object | None
    damping: object | None
    rank_min: int | None
    rank_max: int | None


@dataclass
class LaneRecord:
    bits: int
    nominal_dps: int
    status: str
    point: tuple[object, ...] | None
    answer: object | None
    residual_inf: object | None
    stages: list[StageRecord] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class _Failure(RuntimeError):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


def _external(problem, z: Sequence[object]) -> tuple[object, ...]:
    return tuple(
        mp.mpf(problem.origin_text[index])
        + mp.mpf(problem.scale_text[index]) * mp.mpf(z[index])
        for index in range(len(z))
    )


def _semantic(problem, z: Sequence[object], dps: int, counters: Counters) -> bool:
    counters.semantic_calls += 1
    state = problem.evaluator.semantic(_external(problem, z), int(dps))
    if not bool(state.admissible):
        return False
    if state.strict_margin is not None:
        margin = mp.mpf(state.strict_margin)
        buffer = mp.power(10, -min(70, max(24, int(dps) // 3)))
        if not mp.isfinite(margin) or margin <= buffer:
            return False
    return True


def _residual(problem, z: Sequence[object], dps: int, counters: Counters):
    counters.residual_calls += 1
    values = tuple(
        mp.mpf(value)
        for value in problem.evaluator.residual(_external(problem, z), int(dps))
    )
    if not values or not all(mp.isfinite(value) for value in values):
        raise _Failure("NONFINITE_RESIDUAL")
    return values


def _norm_inf(values: Sequence[object]) -> object:
    return max((abs(value) for value in values), default=mp.mpf("0"))


def _stage_gate(dps: int, final: bool) -> object:
    # Every lane shares a fully converged 180-dps anchor.  Without this, an
    # underdetermined manifold can let the 768/1024 lanes move after the 512
    # lane stops, creating a configuration disagreement despite identical
    # targets and tiny residuals.
    if final or int(dps) >= 180:
        return FINAL_GATE
    return mp.power(10, -min(72, max(28, int(dps) // 2)))


def _adaptive_semismooth_jacobian(
    problem,
    z: Sequence[object],
    residual: Sequence[object],
    dps: int,
    counters: Counters,
) -> list[list[object]]:
    """Build a branch-local generalized Jacobian from an opaque evaluator.

    At 70 dps the normal stencil is about 1e-30 in normalized coordinates,
    far below the 1e-3..1e-16 endpoint residuals of interest yet comfortably
    above roundoff.  Thus smooth-side derivatives are measured without
    straddling a nearby kink.  If the endpoint is so close that both sides do
    straddle it, opposing slopes are detected numerically and the outward side
    (the side with the larger residual displacement) supplies an admissible
    Clarke derivative.
    """

    rows = len(residual)
    columns = len(z)
    matrix = [[mp.mpf("0") for _ in range(columns)] for _ in range(rows)]
    exponent = min(120, max(24, (int(dps) - 10) // 2))
    counters.jacobians += 1
    for column in range(columns):
        counters.stencil_columns += 1
        h = mp.power(10, -exponent) * max(mp.mpf("1"), abs(z[column]))
        plus = list(z)
        minus = list(z)
        plus[column] += h
        minus[column] -= h
        plus_ok = _semantic(problem, plus, dps, counters)
        minus_ok = _semantic(problem, minus, dps, counters)
        plus_residual = _residual(problem, plus, dps, counters) if plus_ok else None
        minus_residual = _residual(problem, minus, dps, counters) if minus_ok else None
        if plus_residual is not None and minus_residual is not None:
            for row in range(rows):
                forward = (plus_residual[row] - residual[row]) / h
                backward = (residual[row] - minus_residual[row]) / h
                central = (plus_residual[row] - minus_residual[row]) / (2 * h)
                scale = max(abs(forward), abs(backward), mp.mpf("1e-300"))
                if forward * backward < 0 and abs(central) <= mp.mpf("0.35") * scale:
                    plus_change = abs(plus_residual[row] - residual[row])
                    minus_change = abs(minus_residual[row] - residual[row])
                    matrix[row][column] = (
                        forward if plus_change >= minus_change else backward
                    )
                    counters.opposing_side_derivatives += 1
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
            raise _Failure("SEMANTIC_STENCIL_BLOCKED")
    if not all(mp.isfinite(value) for row in matrix for value in row):
        raise _Failure("NONFINITE_JACOBIAN")
    return matrix


def _equilibrate(residual, jacobian):
    row_divisors = []
    for value, row in zip(residual, jacobian, strict=True):
        sensitivity = mp.sqrt(mp.fsum(entry * entry for entry in row))
        divisor = max(abs(value), sensitivity, mp.mpf("1e-300"))
        row_divisors.append(divisor)
    scaled_r = [
        residual[row] / row_divisors[row] for row in range(len(residual))
    ]
    scaled_j = [
        [entry / row_divisors[row] for entry in jacobian[row]]
        for row in range(len(jacobian))
    ]
    column_divisors = []
    for column in range(len(jacobian[0])):
        norm = mp.sqrt(
            mp.fsum(scaled_j[row][column] ** 2 for row in range(len(scaled_j)))
        )
        column_divisors.append(max(norm, mp.mpf("1e-40")))
    matrix = [
        [
            scaled_j[row][column] / column_divisors[column]
            for column in range(len(column_divisors))
        ]
        for row in range(len(scaled_j))
    ]
    merit = mp.mpf("0.5") * mp.fsum(value * value for value in scaled_r)
    return row_divisors, column_divisors, scaled_r, matrix, merit


def _damped_svd_step(matrix, scaled_r, column_divisors, damping, dps, counters):
    counters.svd_factorizations += 1
    try:
        left, singular_values, right = mp.svd(mp.matrix(matrix), full_matrices=False)
    except Exception as error:
        raise _Failure("SVD_FAILED") from error
    if not singular_values:
        raise _Failure("RANK_ZERO")
    largest = max(abs(value) for value in singular_values)
    cutoff = largest * mp.power(10, -min(100, max(24, int(dps) // 2)))
    retained = [
        index
        for index, singular in enumerate(singular_values)
        if abs(singular) > cutoff
    ]
    if not retained:
        raise _Failure("RANK_ZERO")
    if len(retained) < min(len(matrix), len(matrix[0])):
        counters.rank_deficient_steps += 1
    scaled_step = [mp.mpf("0") for _ in range(len(matrix[0]))]
    for index in retained:
        singular = singular_values[index]
        projection = -mp.fsum(
            left[row, index] * scaled_r[row] for row in range(len(matrix))
        )
        # Pseudo-transient/Tikhonov filter.  As damping tends to zero this is
        # the minimum-norm semismooth Newton step.
        coefficient = (
            singular * projection / (singular * singular + damping)
        )
        for column in range(len(scaled_step)):
            scaled_step[column] += right[index, column] * coefficient
    step = tuple(
        scaled_step[column] / column_divisors[column]
        for column in range(len(scaled_step))
    )
    if not all(mp.isfinite(value) for value in step):
        raise _Failure("NONFINITE_STEP")
    return step, len(retained)


def _cauchy_step(matrix, scaled_r, column_divisors):
    gradient = [
        mp.fsum(matrix[row][column] * scaled_r[row] for row in range(len(matrix)))
        for column in range(len(matrix[0]))
    ]
    norm = max((abs(value) for value in gradient), default=mp.mpf("0"))
    if norm == 0:
        return None
    return tuple(
        -(gradient[column] / norm) / column_divisors[column]
        for column in range(len(gradient))
    )


def _trial_merit(residual, row_divisors):
    return mp.mpf("0.5") * mp.fsum(
        (residual[row] / row_divisors[row]) ** 2
        for row in range(len(residual))
    )


def _run_stage(
    problem,
    z: list[object],
    *,
    dps: int,
    final: bool,
    variant: str,
    counters: Counters,
    deadline: float,
    max_iterations: int,
):
    damping = mp.mpf("1e-6")
    damping_floor = mp.power(10, -min(240, max(30, int(dps) - 10)))
    trust_radius = mp.mpf("2")
    status = "ITERATION_LIMIT"
    final_residual = None
    final_merit = None
    ranks: list[int] = []
    iterations = 0
    counters.precision_stages += 1
    with mp.workdps(int(dps)):
        for iterations in range(1, max_iterations + 1):
            if time.monotonic() >= deadline:
                status = "DEADLINE_REACHED"
                break
            if not _semantic(problem, z, dps, counters):
                status = "SEMANTIC_REJECTED"
                break
            residual = _residual(problem, z, dps, counters)
            final_residual = _norm_inf(residual)
            gate = _stage_gate(dps, final)
            if variant == CORRECTIVE and int(dps) >= 180:
                # Corrective-wave termination is tied to the public 1e-100
                # replay contract with a four-decade buffer.  The reference
                # configuration's inherited 1e-112 gate was diagnostic, not
                # an authority requirement; rejecting an independently
                # replayable 1e-108 endpoint is an implementation-level false
                # negative rather than useful extra safety.
                gate = max(gate, mp.mpf("1e-104"))
            if final_residual <= gate:
                # Fresh untouched replay at the same precision guards against
                # cache or model-only success.
                replay = _residual(problem, z, dps, counters)
                final_residual = _norm_inf(replay)
                if final_residual <= gate and _semantic(problem, z, dps, counters):
                    status = "SUCCESS"
                else:
                    status = "REPLAY_GATE_FAILED"
                break
            opposing_before = counters.opposing_side_derivatives
            jacobian = _adaptive_semismooth_jacobian(
                problem, z, residual, dps, counters
            )
            kink_active = counters.opposing_side_derivatives > opposing_before
            row_divisors, column_divisors, scaled_r, matrix, current_merit = (
                _equilibrate(residual, jacobian)
            )
            final_merit = current_merit
            accepted = None
            local_damping = damping
            # Multiple pseudo-time steps use one Jacobian.  This is cheaper
            # than abandoning a useful endpoint after a single failed Newton
            # model and remains a general local globalization rule.
            for retry in range(5):
                if retry:
                    counters.damping_retries += 1
                step, rank = _damped_svd_step(
                    matrix,
                    scaled_r,
                    column_divisors,
                    local_damping,
                    dps,
                    counters,
                )
                ranks.append(rank)
                step_norm = _norm_inf(step)
                if step_norm == 0:
                    local_damping *= 100
                    continue
                if step_norm > trust_radius:
                    factor = trust_radius / step_norm
                    step = tuple(factor * value for value in step)
                # Extrapolating by alpha=2 is valuable for a smooth even-
                # multiplicity row, but it merely crosses and oscillates on
                # an active absolute-value kink.  The numerical opposing-side
                # test, not a primitive or case label, controls this choice.
                alpha_schedule = (
                    ("1", "0.5", "0.25", "0.125", "0.0625")
                    if kink_active
                    else ("2", "1", "0.5", "0.25", "0.125", "0.0625")
                )
                for alpha_text in alpha_schedule:
                    alpha = mp.mpf(alpha_text)
                    trial = [
                        z[index] + alpha * step[index]
                        for index in range(len(z))
                    ]
                    if not all(mp.isfinite(value) for value in trial):
                        counters.rejected_trials += 1
                        continue
                    if not _semantic(problem, trial, dps, counters):
                        counters.semantic_rejections += 1
                        continue
                    trial_residual = _residual(problem, trial, dps, counters)
                    trial_merit = _trial_merit(trial_residual, row_divisors)
                    if trial_merit < current_merit:
                        if accepted is None or trial_merit < accepted[0]:
                            accepted = (trial_merit, trial, alpha)
                    else:
                        counters.rejected_trials += 1
                if accepted is not None:
                    # A fixed 1e-30 floor destroys the Newton limit for a
                    # multiple/flat root once its smallest useful singular
                    # value falls below 1e-15.  Tie the floor to working
                    # precision so pseudo-time can continue to infinity.
                    damping = max(damping_floor, local_damping / 10)
                    break
                local_damping *= 100

            if accepted is None and variant == CORRECTIVE:
                fallback = _cauchy_step(matrix, scaled_r, column_divisors)
                if fallback is not None:
                    counters.cauchy_fallbacks += 1
                    step_norm = _norm_inf(fallback)
                    if step_norm > trust_radius:
                        factor = trust_radius / step_norm
                        fallback = tuple(factor * value for value in fallback)
                    for alpha_text in ("1", "0.25", "0.0625", "0.015625"):
                        alpha = mp.mpf(alpha_text)
                        trial = [
                            z[index] + alpha * fallback[index]
                            for index in range(len(z))
                        ]
                        if not _semantic(problem, trial, dps, counters):
                            counters.semantic_rejections += 1
                            continue
                        trial_residual = _residual(problem, trial, dps, counters)
                        trial_merit = _trial_merit(trial_residual, row_divisors)
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
        StageRecord(
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


def _refine_lane(problem, lane, variant, deadline, counters):
    bits, nominal_dps, stages = lane
    started = time.monotonic()
    with mp.workdps(stages[0]):
        z = [
            (mp.mpf(problem.start_text[index]) - mp.mpf(problem.origin_text[index]))
            / mp.mpf(problem.scale_text[index])
            for index in range(len(problem.start_text))
        ]
    records: list[StageRecord] = []
    status = "REFINEMENT_INCOMPLETE"
    residual_inf = None
    try:
        for index, dps in enumerate(stages):
            status, z, record = _run_stage(
                problem,
                z,
                dps=dps,
                final=index == len(stages) - 1,
                variant=variant,
                counters=counters,
                deadline=deadline,
                max_iterations=128,
            )
            records.append(record)
            residual_inf = record.residual_inf
            if status != "SUCCESS":
                break
        if status == "SUCCESS":
            with mp.workdps(stages[-1]):
                point = _external(problem, z)
                answer = mp.mpf(problem.evaluator.answer(point, stages[-1]))
            return LaneRecord(
                bits,
                nominal_dps,
                status,
                point,
                answer,
                residual_inf,
                records,
                time.monotonic() - started,
            )
    except _Failure as error:
        status = error.status
    except Exception:
        status = "CALLBACK_OR_NUMERIC_EXCEPTION"
    return LaneRecord(
        bits,
        nominal_dps,
        status,
        None,
        None,
        residual_inf,
        records,
        time.monotonic() - started,
    )


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "_mpf_"):
        return mp.nstr(value, 150)
    return value


def refine_endpoint(
    evaluator,
    endpoint: Sequence[float],
    *,
    variant: str = REFERENCE,
    deadline_seconds: float = 24.0,
) -> dict[str, object]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be finite and nonempty")
    problem = BASE.Problem(
        evaluator,
        BASE.canonical_float64_endpoint(values),
        tuple("0" for _ in values),
        tuple(repr(max(1.0, abs(value))) for value in values),
    )
    deadline = time.monotonic() + max(0.03, float(deadline_seconds))
    counters = Counters()
    lanes: list[LaneRecord] = []
    for lane in LANES:
        if time.monotonic() >= deadline:
            break
        record = _refine_lane(problem, lane, variant, deadline, counters)
        lanes.append(record)
        if record.status != "SUCCESS":
            break

    coordinate_disagreement = None
    target_512_768 = None
    target_768_1024 = None
    if len(lanes) >= 2 and all(row.status == "SUCCESS" for row in lanes[:2]):
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
    if len(lanes) == 3 and all(row.status == "SUCCESS" for row in lanes[1:]):
        with mp.workdps(350):
            target_768_1024 = abs(lanes[1].answer - lanes[2].answer)
    ready = bool(
        len(lanes) == 3
        and all(row.status == "SUCCESS" for row in lanes)
        and coordinate_disagreement is not None
        and coordinate_disagreement <= AGREEMENT_GATE
        and target_512_768 is not None
        and target_512_768 <= AGREEMENT_GATE
        and target_768_1024 is not None
        and target_768_1024 <= AGREEMENT_GATE
    )
    return {
        "variant": variant,
        "status": "NUMERIC_V3_READY" if ready else "HIGH_PRECISION_REFINEMENT_FAILED",
        "numeric_v3_ready": ready,
        "lanes": [
            {
                **asdict(row),
                "point": row.point,
                "answer": row.answer,
            }
            for row in lanes
        ],
        "configuration_512_768_disagreement_inf": coordinate_disagreement,
        "target_512_768_disagreement": target_512_768,
        "target_768_1024_disagreement": target_768_1024,
        "independent_lane_initialization": len(lanes) == 3,
        "mechanism_counters": asdict(counters),
        "case_identity_read": False,
        "family_read": False,
        "truth_read": False,
        "known_target_count_read": False,
        "coordinate_fixing_or_gauge": False,
        "hard_bounds_added": False,
        "source_residual_changed": False,
    }


def result_to_jsonable(result: dict[str, object]) -> dict[str, object]:
    return _jsonable(result)


__all__ = [
    "BASE",
    "CORRECTIVE",
    "REFERENCE",
    "VARIANTS",
    "refine_endpoint",
    "result_to_jsonable",
]
