"""Disposable independent precision-ramped RRQR/SVD numerical refiner.

This is deliberately a small algorithm experiment, not a production seam.
It knows only opaque numerical callbacks and never consumes truth, case names,
families, known target counts, or exact-coordinate machinery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import math
import time
from typing import Protocol, Sequence

from mpmath import mp


FINAL_ABSOLUTE_GATE = mp.mpf("1e-108")
AGREEMENT_GATE = mp.mpf("1e-100")


@dataclass(frozen=True)
class LaneSpec:
    bits: int
    nominal_dps: int
    stage_dps: tuple[int, ...]


LANES = (
    LaneSpec(512, 155, (70, 110, 180)),
    LaneSpec(768, 232, (70, 140, 252)),
    LaneSpec(1024, 320, (70, 160, 340)),
)


@dataclass(frozen=True)
class SemanticState:
    admissible: bool
    strict_margin: object | None = None
    reason: str = ""


class NumericEvaluator(Protocol):
    def residual(self, point: Sequence[object], dps: int) -> Sequence[object]: ...

    def semantic(self, point: Sequence[object], dps: int) -> SemanticState: ...

    def answer(self, point: Sequence[object], dps: int) -> object: ...


@dataclass(frozen=True)
class Problem:
    evaluator: NumericEvaluator
    start_text: tuple[str, ...]
    origin_text: tuple[str, ...]
    scale_text: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.start_text:
            raise ValueError("at least one free coordinate is required")
        if not (
            len(self.start_text) == len(self.origin_text) == len(self.scale_text)
        ):
            raise ValueError("start/origin/scale dimensions differ")
        with mp.workdps(80):
            if any(mp.mpf(value) <= 0 for value in self.scale_text):
                raise ValueError("canonical coordinate scales must be positive")


@dataclass
class Counters:
    residual_calls: int = 0
    complex_residual_calls: int = 0
    semantic_calls: int = 0
    answer_calls: int = 0
    analytic_jacobians: int = 0
    complex_step_jacobians: int = 0
    five_point_jacobians: int = 0
    one_sided_columns: int = 0
    verification_jacobians: int = 0
    rrqr_steps: int = 0
    svd_steps: int = 0
    rank_deficient_steps: int = 0
    row_equilibrations: int = 0
    accepted_trials: int = 0
    rejected_trials: int = 0
    semantic_rejections: int = 0
    alpha_two_accepts: int = 0


@dataclass(frozen=True)
class StageReport:
    dps: int
    status: str
    iterations: int
    residual_calls: int
    final_absolute_residual: object | None
    final_backward_error: object | None
    derivative_backends: tuple[str, ...]
    linear_solvers: tuple[str, ...]


@dataclass(frozen=True)
class LaneResult:
    bits: int
    nominal_dps: int
    status: str
    point: tuple[object, ...] | None
    answer: object | None
    absolute_residual: object | None
    backward_error: object | None
    stages: tuple[StageReport, ...]
    counters: dict[str, int]
    start_text: tuple[str, ...]
    elapsed_seconds: float


@dataclass(frozen=True)
class TripletResult:
    status: str
    lanes: tuple[LaneResult, ...]
    configuration_512_768_disagreement_inf: object | None
    target_512_768_disagreement: object | None
    target_768_1024_disagreement: object | None
    independent_lane_initialization: bool


class _Failure(RuntimeError):
    def __init__(self, status: str, detail: str = "") -> None:
        super().__init__(detail or status)
        self.status = status


def canonical_float64_endpoint(endpoint: Sequence[float]) -> tuple[str, ...]:
    """Return the exact, deterministic input seam used by all three lanes."""

    values = tuple(float(value) for value in endpoint)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("endpoint must be a nonempty finite Float64 vector")
    return tuple(repr(value) for value in values)


def endpoint_sha256(start_text: Sequence[str]) -> str:
    payload = "\0".join(start_text).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def problem_from_float64_endpoint(
    evaluator: NumericEvaluator,
    endpoint: Sequence[float],
    *,
    origin: Sequence[float] | None = None,
    scales: Sequence[float] | None = None,
) -> Problem:
    start = canonical_float64_endpoint(endpoint)
    if origin is None:
        origin_text = tuple("0.0" for _ in start)
    else:
        origin_text = canonical_float64_endpoint(origin)
    if scales is None:
        scale_text = tuple(repr(max(1.0, abs(float(value)))) for value in endpoint)
    else:
        scale_text = canonical_float64_endpoint(scales)
    return Problem(evaluator, start, origin_text, scale_text)


def _finite_real(value: object, label: str) -> object:
    try:
        result = mp.mpf(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise _Failure("NONFINITE_NUMERIC", label) from error
    if not mp.isfinite(result):
        raise _Failure("NONFINITE_NUMERIC", label)
    return result


def _external_point(problem: Problem, z: Sequence[object]) -> tuple[object, ...]:
    point = tuple(
        mp.mpf(problem.origin_text[index])
        + mp.mpf(problem.scale_text[index]) * mp.mpf(z[index])
        for index in range(len(z))
    )
    if not all(mp.isfinite(value) for value in point):
        raise _Failure("NONFINITE_POINT")
    return point


def _external_complex_point(problem: Problem, z: Sequence[object]) -> tuple[object, ...]:
    point = tuple(
        mp.mpf(problem.origin_text[index])
        + mp.mpf(problem.scale_text[index]) * mp.mpc(z[index])
        for index in range(len(z))
    )
    if not all(mp.isfinite(value.real) and mp.isfinite(value.imag) for value in point):
        raise _Failure("NONFINITE_COMPLEX_POINT")
    return point


def _strict_buffer(dps: int) -> object:
    return mp.power(10, -min(70, max(24, dps // 3)))


def _semantic(problem: Problem, z: Sequence[object], dps: int, counters: Counters) -> bool:
    counters.semantic_calls += 1
    try:
        state = problem.evaluator.semantic(_external_point(problem, z), dps)
    except Exception as error:
        raise _Failure("SEMANTIC_CALLBACK_FAILED", type(error).__name__) from error
    if not bool(state.admissible):
        return False
    if state.strict_margin is not None:
        margin = _finite_real(state.strict_margin, "strict margin")
        if margin <= _strict_buffer(dps):
            return False
    return True


def _residual(problem: Problem, z: Sequence[object], dps: int, counters: Counters) -> tuple[object, ...]:
    counters.residual_calls += 1
    try:
        raw = problem.evaluator.residual(_external_point(problem, z), dps)
        values = tuple(mp.mpf(value) for value in raw)
    except Exception as error:
        raise _Failure("RESIDUAL_CALLBACK_FAILED", type(error).__name__) from error
    if not values or not all(mp.isfinite(value) for value in values):
        raise _Failure("NONFINITE_RESIDUAL")
    return values


def _complex_residual(
    problem: Problem, z: Sequence[object], dps: int, counters: Counters
) -> tuple[object, ...]:
    callback = getattr(problem.evaluator, "complex_residual", None)
    if callback is None or not bool(getattr(problem.evaluator, "complex_safe", False)):
        raise _Failure("COMPLEX_STEP_UNAVAILABLE")
    counters.residual_calls += 1
    counters.complex_residual_calls += 1
    try:
        raw = callback(_external_complex_point(problem, z), dps)
        values = tuple(mp.mpc(value) for value in raw)
    except Exception as error:
        raise _Failure("COMPLEX_RESIDUAL_FAILED", type(error).__name__) from error
    if not values or not all(
        mp.isfinite(value.real) and mp.isfinite(value.imag) for value in values
    ):
        raise _Failure("NONFINITE_COMPLEX_RESIDUAL")
    return values


def _norm_inf(values: Sequence[object]) -> object:
    return max((abs(value) for value in values), default=mp.mpf("0"))


def _analytic_jacobian(
    problem: Problem, z: Sequence[object], residual: Sequence[object], dps: int, counters: Counters
) -> list[list[object]] | None:
    callback = getattr(problem.evaluator, "jacobian", None)
    if callback is None:
        return None
    try:
        raw = callback(_external_point(problem, z), dps)
        rows = [list(row) for row in raw]
    except (AttributeError, NotImplementedError):
        return None
    except Exception as error:
        raise _Failure("ANALYTIC_JACOBIAN_FAILED", type(error).__name__) from error
    if len(rows) != len(residual) or any(len(row) != len(z) for row in rows):
        raise _Failure("JACOBIAN_DIMENSION_MISMATCH")
    result = [
        [
            _finite_real(rows[row][column], "analytic Jacobian")
            * mp.mpf(problem.scale_text[column])
            for column in range(len(z))
        ]
        for row in range(len(residual))
    ]
    counters.analytic_jacobians += 1
    return result


def _complex_step_jacobian(
    problem: Problem,
    z: Sequence[object],
    residual: Sequence[object],
    dps: int,
    counters: Counters,
    *,
    verification: bool,
) -> list[list[object]] | None:
    if not bool(getattr(problem.evaluator, "complex_safe", False)) or not hasattr(
        problem.evaluator, "complex_residual"
    ):
        return None
    exponent = min(100, max(28, (dps - 20) // 2))
    if verification:
        exponent += 7
    step = mp.power(10, -exponent)
    matrix = [[mp.mpf("0") for _ in z] for _ in residual]
    for column in range(len(z)):
        trial = [mp.mpc(value) for value in z]
        trial[column] += mp.j * step
        values = _complex_residual(problem, trial, dps, counters)
        if len(values) != len(residual):
            raise _Failure("RESIDUAL_DIMENSION_CHANGED")
        for row in range(len(residual)):
            matrix[row][column] = values[row].imag / step
    if not all(mp.isfinite(value) for row in matrix for value in row):
        raise _Failure("NONFINITE_JACOBIAN")
    counters.complex_step_jacobians += 1
    return matrix


def _real_stencil_jacobian(
    problem: Problem,
    z: Sequence[object],
    residual: Sequence[object],
    dps: int,
    counters: Counters,
    *,
    verification: bool,
) -> list[list[object]]:
    # A fourth-order stencil balances truncation O(h^4) and subtraction O(eps/h).
    exponent = max(10, (dps - 18) // 5)
    if verification:
        exponent += 3
    matrix = [[mp.mpf("0") for _ in z] for _ in residual]
    for column in range(len(z)):
        step = mp.power(10, -exponent) * max(mp.mpf("1"), abs(z[column]))
        offsets: dict[int, tuple[list[object], bool, tuple[object, ...] | None]] = {}
        for multiplier in (-2, -1, 1, 2):
            trial = list(z)
            trial[column] += multiplier * step
            admissible = _semantic(problem, trial, dps, counters)
            # Semantic adapters may compute the branch residual.  Evaluating
            # the matching stencil immediately lets a one-shot adapter reuse
            # exactly that value; no point or precision can reuse it later.
            value = _residual(problem, trial, dps, counters) if admissible else None
            offsets[multiplier] = (trial, admissible, value)
        if all(offsets[index][1] for index in (-2, -1, 1, 2)):
            values = {index: offsets[index][2] for index in (-2, -1, 1, 2)}
            for row in range(len(residual)):
                matrix[row][column] = (
                    values[-2][row]
                    - 8 * values[-1][row]
                    + 8 * values[1][row]
                    - values[2][row]
                ) / (12 * step)
        elif offsets[1][1] and offsets[2][1]:
            plus = offsets[1][2]
            plus2 = offsets[2][2]
            for row in range(len(residual)):
                matrix[row][column] = (
                    -3 * residual[row] + 4 * plus[row] - plus2[row]
                ) / (2 * step)
            counters.one_sided_columns += 1
        elif offsets[-1][1] and offsets[-2][1]:
            minus = offsets[-1][2]
            minus2 = offsets[-2][2]
            for row in range(len(residual)):
                matrix[row][column] = (
                    3 * residual[row] - 4 * minus[row] + minus2[row]
                ) / (2 * step)
            counters.one_sided_columns += 1
        else:
            raise _Failure("SEMANTIC_STENCIL_BLOCKED")
    if not all(mp.isfinite(value) for row in matrix for value in row):
        raise _Failure("NONFINITE_JACOBIAN")
    counters.five_point_jacobians += 1
    return matrix


def _jacobian(
    problem: Problem,
    z: Sequence[object],
    residual: Sequence[object],
    dps: int,
    counters: Counters,
    *,
    verification: bool = False,
) -> tuple[list[list[object]], str]:
    analytic = _analytic_jacobian(problem, z, residual, dps, counters)
    if analytic is not None:
        backend = "analytic"
        matrix = analytic
    else:
        complex_matrix = _complex_step_jacobian(
            problem,
            z,
            residual,
            dps,
            counters,
            verification=verification,
        )
        if complex_matrix is not None:
            backend = "complex_step"
            matrix = complex_matrix
        else:
            backend = "five_point_real"
            matrix = _real_stencil_jacobian(
                problem,
                z,
                residual,
                dps,
                counters,
                verification=verification,
            )
    if verification:
        counters.verification_jacobians += 1
    return matrix, backend


def _row_divisors(
    residual: Sequence[object], jacobian: Sequence[Sequence[object]], counters: Counters
) -> tuple[object, ...]:
    divisors = []
    nonzero = []
    for value, row in zip(residual, jacobian, strict=True):
        sensitivity = mp.sqrt(mp.fsum(abs(entry) ** 2 for entry in row))
        divisor = max(abs(value), sensitivity)
        divisors.append(divisor)
        if divisor > 0:
            nonzero.append(divisor)
    if nonzero and max(nonzero) / min(nonzero) > mp.mpf("1e6"):
        counters.row_equilibrations += 1
    return tuple(divisors)


def _backward_error(residual: Sequence[object], divisors: Sequence[object]) -> object:
    ratios = []
    for value, divisor in zip(residual, divisors, strict=True):
        if value == 0:
            ratios.append(mp.mpf("0"))
        elif divisor == 0:
            ratios.append(mp.inf)
        else:
            ratios.append(abs(value) / divisor)
    return max(ratios, default=mp.inf)


def _scaled_system(
    residual: Sequence[object],
    jacobian: Sequence[Sequence[object]],
    divisors: Sequence[object],
) -> tuple[list[list[object]], list[object], list[object]]:
    active = [index for index, divisor in enumerate(divisors) if divisor > 0]
    if not active:
        raise _Failure("ZERO_LOCAL_MODEL")
    rows = [
        [jacobian[index][column] / divisors[index] for column in range(len(jacobian[0]))]
        for index in active
    ]
    rhs = [-residual[index] / divisors[index] for index in active]
    column_scales = []
    for column in range(len(jacobian[0])):
        norm = mp.sqrt(mp.fsum(abs(row[column]) ** 2 for row in rows))
        column_scales.append(norm if norm > 0 else mp.mpf("1"))
    scaled = [
        [row[column] / column_scales[column] for column in range(len(row))]
        for row in rows
    ]
    return scaled, rhs, column_scales


def _rrqr_full_column_step(
    matrix: Sequence[Sequence[object]], rhs: Sequence[object], dps: int
) -> tuple[list[object] | None, int]:
    rows = len(matrix)
    columns = len(matrix[0])
    if rows < columns:
        return None, min(rows, columns)
    work = [[mp.mpf(matrix[row][column]) for row in range(rows)] for column in range(columns)]
    permutation = list(range(columns))
    upper = [[mp.mpf("0") for _ in range(columns)] for _ in range(columns)]
    q_columns: list[list[object]] = []
    rhs_projection: list[object] = []
    largest_diagonal = mp.mpf("0")
    rank = 0
    cutoff_factor = mp.power(10, -min(80, max(20, dps // 3)))
    for pivot_index in range(columns):
        pivot = max(
            range(pivot_index, columns),
            key=lambda index: mp.fsum(abs(value) ** 2 for value in work[index]),
        )
        if pivot != pivot_index:
            work[pivot_index], work[pivot] = work[pivot], work[pivot_index]
            permutation[pivot_index], permutation[pivot] = (
                permutation[pivot],
                permutation[pivot_index],
            )
            for previous in range(pivot_index):
                upper[previous][pivot_index], upper[previous][pivot] = (
                    upper[previous][pivot],
                    upper[previous][pivot_index],
                )
        diagonal = mp.sqrt(mp.fsum(abs(value) ** 2 for value in work[pivot_index]))
        largest_diagonal = max(largest_diagonal, diagonal)
        if diagonal == 0 or diagonal <= largest_diagonal * cutoff_factor:
            break
        q = [value / diagonal for value in work[pivot_index]]
        upper[pivot_index][pivot_index] = diagonal
        q_columns.append(q)
        rhs_projection.append(mp.fsum(q[row] * rhs[row] for row in range(rows)))
        rank += 1
        for column in range(pivot_index + 1, columns):
            coefficient = mp.fsum(q[row] * work[column][row] for row in range(rows))
            work[column] = [
                work[column][row] - coefficient * q[row] for row in range(rows)
            ]
            # A second MGS pass materially improves the rank decision.
            correction = mp.fsum(q[row] * work[column][row] for row in range(rows))
            work[column] = [
                work[column][row] - correction * q[row] for row in range(rows)
            ]
            upper[pivot_index][column] = coefficient + correction
    if rank != columns:
        return None, rank
    permuted_solution = [mp.mpf("0") for _ in range(columns)]
    for row in reversed(range(columns)):
        tail = mp.fsum(
            upper[row][column] * permuted_solution[column]
            for column in range(row + 1, columns)
        )
        permuted_solution[row] = (rhs_projection[row] - tail) / upper[row][row]
    solution = [mp.mpf("0") for _ in range(columns)]
    for pivot_index, original_index in enumerate(permutation):
        solution[original_index] = permuted_solution[pivot_index]
    return solution, rank


def _svd_step(
    matrix: Sequence[Sequence[object]], rhs: Sequence[object], dps: int
) -> tuple[list[object] | None, int]:
    rows = len(matrix)
    columns = len(matrix[0])
    dense = mp.matrix(matrix)
    try:
        left, singular_values, right = mp.svd(dense, full_matrices=False)
    except Exception as error:
        raise _Failure("SVD_FAILED", type(error).__name__) from error
    if not singular_values:
        return None, 0
    largest = max(abs(value) for value in singular_values)
    cutoff = largest * mp.power(10, -min(110, max(30, dps // 2)))
    retained = [
        index for index, singular in enumerate(singular_values) if abs(singular) > cutoff
    ]
    if not retained:
        return None, 0
    solution = [mp.mpf("0") for _ in range(columns)]
    for index in retained:
        projection = mp.fsum(left[row, index] * rhs[row] for row in range(rows))
        coefficient = projection / singular_values[index]
        for column in range(columns):
            solution[column] += right[index, column] * coefficient
    return solution, len(retained)


def _linear_step(
    residual: Sequence[object],
    jacobian: Sequence[Sequence[object]],
    divisors: Sequence[object],
    dps: int,
    counters: Counters,
) -> tuple[tuple[object, ...], str, int, int]:
    matrix, rhs, column_scales = _scaled_system(residual, jacobian, divisors)
    target_rank = min(len(matrix), len(matrix[0]))
    scaled_step, rank = _rrqr_full_column_step(matrix, rhs, dps)
    if scaled_step is not None:
        solver = "rrqr"
        counters.rrqr_steps += 1
    else:
        scaled_step, rank = _svd_step(matrix, rhs, dps)
        solver = "filtered_svd"
        counters.svd_steps += 1
    if scaled_step is None or rank == 0:
        raise _Failure("RANK_ZERO_OR_STATIONARY_NONROOT")
    if rank < target_rank or len(matrix) < len(matrix[0]):
        counters.rank_deficient_steps += 1
    step = tuple(
        scaled_step[column] / column_scales[column]
        for column in range(len(column_scales))
    )
    if not all(mp.isfinite(value) for value in step):
        raise _Failure("NONFINITE_STEP")
    return step, solver, rank, target_rank


def _stage_gate(dps: int, *, final: bool) -> object:
    if final:
        return FINAL_ABSOLUTE_GATE
    return mp.power(10, -min(72, max(28, dps // 2)))


def _run_stage(
    problem: Problem,
    z: list[object],
    *,
    dps: int,
    final: bool,
    counters: Counters,
    deadline: float,
    max_iterations: int,
) -> tuple[str, list[object], StageReport, object | None, object | None]:
    calls_before = counters.residual_calls
    derivative_backends: set[str] = set()
    linear_solvers: set[str] = set()
    absolute = None
    backward = None
    trust_radius = mp.mpf("4")
    status = "ITERATION_LIMIT"
    iterations = 0
    with mp.workdps(dps):
        for iterations in range(1, max_iterations + 1):
            if time.monotonic() >= deadline:
                status = "DEADLINE_REACHED"
                break
            if not _semantic(problem, z, dps, counters):
                status = "SEMANTIC_REJECTED"
                break
            residual = _residual(problem, z, dps, counters)
            absolute = _norm_inf(residual)
            jacobian, backend = _jacobian(problem, z, residual, dps, counters)
            derivative_backends.add(backend)
            divisors = _row_divisors(residual, jacobian, counters)
            backward = _backward_error(residual, divisors)
            gate = _stage_gate(dps, final=final)
            if absolute <= gate and backward <= gate:
                if final:
                    verify_residual = _residual(problem, z, dps, counters)
                    verify_jacobian, verify_backend = _jacobian(
                        problem,
                        z,
                        verify_residual,
                        dps,
                        counters,
                        verification=True,
                    )
                    derivative_backends.add(verify_backend)
                    verify_divisors = _row_divisors(
                        verify_residual, verify_jacobian, counters
                    )
                    absolute = _norm_inf(verify_residual)
                    backward = _backward_error(verify_residual, verify_divisors)
                    if absolute > FINAL_ABSOLUTE_GATE or backward > AGREEMENT_GATE:
                        status = "VERIFICATION_GATE_FAILED"
                        break
                    if not _semantic(problem, z, dps, counters):
                        status = "SEMANTIC_REJECTED"
                        break
                status = "SUCCESS"
                break
            try:
                step, solver, _rank, _target_rank = _linear_step(
                    residual, jacobian, divisors, dps, counters
                )
            except _Failure as error:
                status = error.status
                break
            linear_solvers.add(solver)
            step_norm = _norm_inf(step)
            if step_norm == 0:
                status = "ZERO_STEP_NONROOT"
                break
            if step_norm > trust_radius:
                factor = trust_radius / step_norm
                step = tuple(factor * value for value in step)
            current_merit = backward
            best: tuple[object, list[object], tuple[object, ...], object] | None = None
            for alpha_text in ("2", "1", "0.5", "0.25", "0.125", "0.0625", "0.03125"):
                if time.monotonic() >= deadline:
                    status = "DEADLINE_REACHED"
                    break
                alpha = mp.mpf(alpha_text)
                trial = [z[index] + alpha * step[index] for index in range(len(z))]
                if not all(mp.isfinite(value) for value in trial):
                    counters.rejected_trials += 1
                    continue
                if not _semantic(problem, trial, dps, counters):
                    counters.semantic_rejections += 1
                    continue
                trial_residual = _residual(problem, trial, dps, counters)
                trial_merit = _backward_error(trial_residual, divisors)
                if trial_merit < current_merit and (
                    best is None or trial_merit < best[0]
                ):
                    best = (trial_merit, trial, trial_residual, alpha)
                else:
                    counters.rejected_trials += 1
            if status == "DEADLINE_REACHED":
                break
            if best is None:
                status = "NO_SAFE_DESCENT"
                break
            reduction = best[0] / current_merit if current_merit > 0 else mp.mpf("0")
            z = best[1]
            counters.accepted_trials += 1
            if best[3] == 2:
                counters.alpha_two_accepts += 1
            if best[3] >= 1 and reduction < mp.mpf("0.25"):
                trust_radius = min(mp.mpf("32"), 2 * trust_radius)
            elif best[3] < 1:
                trust_radius = max(mp.mpf("0.125"), trust_radius / 2)
        report = StageReport(
            dps=dps,
            status=status,
            iterations=iterations,
            residual_calls=counters.residual_calls - calls_before,
            final_absolute_residual=absolute,
            final_backward_error=backward,
            derivative_backends=tuple(sorted(derivative_backends)),
            linear_solvers=tuple(sorted(linear_solvers)),
        )
    return status, z, report, absolute, backward


def refine_lane(
    problem: Problem,
    spec: LaneSpec,
    *,
    deadline_seconds: float = 8.0,
    max_iterations_per_stage: int = 56,
    stage_override: Sequence[int] | None = None,
) -> LaneResult:
    """Refine one lane from a fresh parse of the canonical Float64 endpoint."""

    started = time.monotonic()
    deadline = started + max(0.01, float(deadline_seconds))
    counters = Counters()
    stages = tuple(int(value) for value in (stage_override or spec.stage_dps))
    if not stages:
        raise ValueError("at least one precision stage is required")
    with mp.workdps(stages[0]):
        start = tuple(_finite_real(value, "start") for value in problem.start_text)
        origin = tuple(_finite_real(value, "origin") for value in problem.origin_text)
        scales = tuple(_finite_real(value, "scale") for value in problem.scale_text)
        z = [(start[index] - origin[index]) / scales[index] for index in range(len(start))]
    reports = []
    status = "REFINEMENT_INCOMPLETE"
    absolute = None
    backward = None
    try:
        for index, dps in enumerate(stages):
            status, z, report, absolute, backward = _run_stage(
                problem,
                z,
                dps=dps,
                final=index == len(stages) - 1,
                counters=counters,
                deadline=deadline,
                max_iterations=max_iterations_per_stage,
            )
            reports.append(report)
            if status != "SUCCESS":
                break
        if status == "SUCCESS":
            final_dps = stages[-1]
            with mp.workdps(final_dps):
                if not _semantic(problem, z, final_dps, counters):
                    status = "SEMANTIC_REJECTED"
                else:
                    answer = _finite_real(
                        problem.evaluator.answer(_external_point(problem, z), final_dps),
                        "answer",
                    )
                    counters.answer_calls += 1
                    point = _external_point(problem, z)
                    return LaneResult(
                        bits=spec.bits,
                        nominal_dps=spec.nominal_dps,
                        status="SUCCESS",
                        point=point,
                        answer=answer,
                        absolute_residual=absolute,
                        backward_error=backward,
                        stages=tuple(reports),
                        counters=asdict(counters),
                        start_text=problem.start_text,
                        elapsed_seconds=time.monotonic() - started,
                    )
    except _Failure as error:
        status = error.status
    return LaneResult(
        bits=spec.bits,
        nominal_dps=spec.nominal_dps,
        status=status,
        point=None,
        answer=None,
        absolute_residual=absolute,
        backward_error=backward,
        stages=tuple(reports),
        counters=asdict(counters),
        start_text=problem.start_text,
        elapsed_seconds=time.monotonic() - started,
    )


def refine_triplet(
    problem: Problem,
    *,
    deadline_seconds: float = 24.0,
    max_iterations_per_stage: int = 56,
) -> TripletResult:
    """Run three independently initialized lanes and apply v3 numeric gates."""

    deadline = time.monotonic() + max(0.03, float(deadline_seconds))
    lanes = []
    for spec in LANES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        lane = refine_lane(
            problem,
            spec,
            deadline_seconds=remaining,
            max_iterations_per_stage=max_iterations_per_stage,
        )
        lanes.append(lane)
        if lane.status != "SUCCESS":
            break
    independent = bool(
        len(lanes) == len(LANES)
        and len({lane.start_text for lane in lanes}) == 1
    )
    coordinate_disagreement = None
    target_512_768 = None
    target_768_1024 = None
    if len(lanes) >= 2 and all(lane.status == "SUCCESS" for lane in lanes[:2]):
        with mp.workdps(350):
            coordinate_disagreement = max(
                (
                    abs(left - right)
                    for left, right in zip(lanes[0].point, lanes[1].point, strict=True)
                ),
                default=mp.mpf("0"),
            )
            target_512_768 = abs(lanes[0].answer - lanes[1].answer)
    if len(lanes) == 3 and all(lane.status == "SUCCESS" for lane in lanes[1:]):
        with mp.workdps(350):
            target_768_1024 = abs(lanes[1].answer - lanes[2].answer)
    ready = bool(
        len(lanes) == 3
        and all(lane.status == "SUCCESS" for lane in lanes)
        and independent
        and coordinate_disagreement is not None
        and coordinate_disagreement <= AGREEMENT_GATE
        and target_512_768 is not None
        and target_512_768 <= AGREEMENT_GATE
        and target_768_1024 is not None
        and target_768_1024 <= AGREEMENT_GATE
        and all(
            lane.absolute_residual is not None
            and lane.absolute_residual <= AGREEMENT_GATE
            for lane in lanes[:2]
        )
    )
    return TripletResult(
        status="NUMERIC_V3_READY" if ready else "HIGH_PRECISION_REFINEMENT_FAILED",
        lanes=tuple(lanes),
        configuration_512_768_disagreement_inf=coordinate_disagreement,
        target_512_768_disagreement=target_512_768,
        target_768_1024_disagreement=target_768_1024,
        independent_lane_initialization=independent,
    )


def result_to_jsonable(result: LaneResult | TripletResult) -> dict[str, object]:
    """Serialize numerical evidence without manufacturing authority fields."""

    def convert(value: object) -> object:
        if isinstance(value, dict):
            return {str(key): convert(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [convert(item) for item in value]
        if hasattr(value, "_mpf_"):
            return mp.nstr(value, 140)
        return value

    return convert(asdict(result))


__all__ = [
    "AGREEMENT_GATE",
    "FINAL_ABSOLUTE_GATE",
    "LANES",
    "LaneResult",
    "LaneSpec",
    "NumericEvaluator",
    "Problem",
    "SemanticState",
    "TripletResult",
    "canonical_float64_endpoint",
    "endpoint_sha256",
    "problem_from_float64_endpoint",
    "refine_lane",
    "refine_triplet",
    "result_to_jsonable",
]
