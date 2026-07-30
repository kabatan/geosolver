"""Disposable rank-completion D0 for singular polynomial eigenproblems.

This is a proposal-only side lane.  It regularizes a structurally singular
polynomial matrix with several deterministic-random low-rank completions,
separates stable true eigenvalues from completion-created eigenvalues, and
replays every real proposal against the untouched singular polynomial matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Sequence

import numpy as np
from scipy import linalg


SCHEMA = "geotarget.exp-v15-243.singular-pep-rank-completion/v1"
BASELINE_PERIOD = 4
DEFAULT_TRIALS = 5
RANK_REL_TOL = 2.0e-10
DROP_REL_TOL = 2.0e-7
VECTOR_ORTH_TOL = 2.0e-5
CLUSTER_REL_TOL = 4.0e-6
REAL_TOL = 2.0e-7


@dataclass(frozen=True)
class PolynomialMatrixProblem:
    coefficients: tuple[np.ndarray, ...]  # low degree first
    opaque: bool = False
    real_only: bool = True


@dataclass(frozen=True)
class TrialEigenvalue:
    value: complex
    trial: int
    rank_drop_ratio: float
    left_completion_overlap: float
    right_completion_overlap: float


@dataclass(frozen=True)
class RankCompletionResult:
    activated: bool
    reason: str
    normal_rank: int
    corank: int
    proposals: tuple[float, ...]
    accepted_trials: tuple[TrialEigenvalue, ...]
    finite_completed_eigenvalues: int
    rejected_fake: int
    rejected_nonreal: int
    rejected_replay: int


@dataclass(frozen=True)
class PortfolioResult:
    proposals: tuple[float, ...]
    side: RankCompletionResult
    route_trace: tuple[str, ...]
    baseline_digest_before: str
    baseline_digest_after: str


def route_trace(starts: int = 16) -> tuple[str, ...]:
    if starts < 4 or starts % 4:
        raise ValueError("starts must be a positive multiple of four")
    return tuple("rank_completion" if index % 4 == 3 else "baseline" for index in range(starts))


def _digest(values: Sequence[float]) -> str:
    array = np.asarray(values, dtype="<f8")
    return hashlib.sha256(array.tobytes()).hexdigest()


def _validate(problem: PolynomialMatrixProblem) -> tuple[np.ndarray, ...]:
    coefficients = tuple(np.asarray(item, dtype=np.complex128) for item in problem.coefficients)
    if not coefficients:
        raise ValueError("empty polynomial matrix")
    shape = coefficients[0].shape
    if len(shape) != 2 or shape[0] != shape[1] or not 2 <= shape[0] <= 8:
        raise ValueError("only small square polynomial matrices are supported")
    if len(coefficients) > 6:
        raise ValueError("polynomial degree cap exceeded")
    for coefficient in coefficients:
        if coefficient.shape != shape:
            raise ValueError("coefficient shape changed")
        if not np.all(np.isfinite(coefficient.real)) or not np.all(np.isfinite(coefficient.imag)):
            raise ValueError("non-finite coefficient")
    while len(coefficients) > 1 and np.linalg.norm(coefficients[-1]) <= 1.0e-14:
        coefficients = coefficients[:-1]
    return coefficients


def evaluate_polynomial(coefficients: Sequence[np.ndarray], value: complex) -> np.ndarray:
    result = np.zeros_like(np.asarray(coefficients[0], dtype=np.complex128))
    for coefficient in reversed(coefficients):
        result = result * value + coefficient
    return result


def _rank(matrix: np.ndarray) -> tuple[int, np.ndarray]:
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    if singular_values.size == 0 or singular_values[0] == 0.0:
        return 0, singular_values
    threshold = RANK_REL_TOL * singular_values[0]
    return int(np.count_nonzero(singular_values > threshold)), singular_values


def estimate_normal_rank(coefficients: Sequence[np.ndarray]) -> tuple[int, bool]:
    probes = (0.0, 1.0, -1.0, 0.5 + 0.75j, -0.8 + 0.35j, 1.7 - 0.4j)
    observations = [_rank(evaluate_polynomial(coefficients, probe)) for probe in probes]
    ranks = [rank for rank, _ in observations]
    normal_rank = max(ranks)
    witnesses = [values for rank, values in observations if rank == normal_rank]
    stable = len(witnesses) >= 2
    if normal_rank > 0:
        for values in witnesses:
            pivot = values[normal_rank - 1]
            next_value = values[normal_rank] if normal_rank < values.size else 0.0
            if pivot <= 1.0e3 * max(next_value, np.finfo(float).eps * values[0]):
                stable = False
    return normal_rank, stable


def _companion_eigenvalues(coefficients: Sequence[np.ndarray]) -> tuple[complex, ...]:
    degree = len(coefficients) - 1
    size = coefficients[0].shape[0]
    if degree == 0:
        return ()
    block_size = degree * size
    left = np.zeros((block_size, block_size), dtype=np.complex128)
    right = np.zeros_like(left)
    left[:size, :] = np.hstack([-coefficients[index] for index in range(degree - 1, -1, -1)])
    right[:size, :size] = coefficients[degree]
    identity = np.eye(size, dtype=np.complex128)
    for row in range(1, degree):
        left[row * size : (row + 1) * size, (row - 1) * size : row * size] = identity
        right[row * size : (row + 1) * size, row * size : (row + 1) * size] = identity
    values = linalg.eigvals(left, right, check_finite=False)
    return tuple(complex(value) for value in values if np.isfinite(value.real) and np.isfinite(value.imag))


def _orthonormal_random(rng: np.random.Generator, size: int, columns: int) -> np.ndarray:
    raw = rng.standard_normal((size, columns)) + 1j * rng.standard_normal((size, columns))
    q, _ = np.linalg.qr(raw)
    return q[:, :columns]


def _completion(
    coefficients: Sequence[np.ndarray], *, trial: int, corank: int
) -> tuple[tuple[np.ndarray, ...], np.ndarray, np.ndarray]:
    size = coefficients[0].shape[0]
    degree = len(coefficients) - 1
    rng = np.random.default_rng(0x5EED_243 + 7919 * trial + 101 * size + degree)
    left_basis = _orthonormal_random(rng, size, corank)
    right_basis = _orthonormal_random(rng, size, corank)
    completed = [np.array(coefficient, copy=True) for coefficient in coefficients]
    if len(completed) == 1:
        completed.append(np.zeros_like(completed[0]))
    constant = rng.uniform(0.6, 1.4, size=corank)
    linear = rng.choice((-1.0, 1.0), size=corank) * rng.uniform(0.7, 1.6, size=corank)
    completed[0] += left_basis @ np.diag(constant) @ right_basis.conj().T
    completed[1] += left_basis @ np.diag(linear) @ right_basis.conj().T
    return tuple(completed), left_basis, right_basis


def _rank_drop_ratio(matrix: np.ndarray, normal_rank: int) -> float:
    values = np.linalg.svd(matrix, compute_uv=False)
    if normal_rank <= 0 or values.size < normal_rank or values[0] == 0.0:
        return math.inf
    return float(values[normal_rank - 1] / values[0])


def canonical_source_replay(
    problem: PolynomialMatrixProblem, value: float | complex, normal_rank: int | None = None
) -> bool:
    try:
        coefficients = _validate(problem)
        if normal_rank is None:
            normal_rank, stable = estimate_normal_rank(coefficients)
            if not stable:
                return False
        matrix = evaluate_polynomial(coefficients, complex(value))
        return _rank_drop_ratio(matrix, normal_rank) <= DROP_REL_TOL
    except Exception:
        return False


def ordinary_regular_proposals(problem: PolynomialMatrixProblem) -> tuple[float, ...]:
    """Tiny control: ordinary companion solve, refusing a singular polynomial."""

    if problem.opaque:
        return ()
    try:
        coefficients = _validate(problem)
        normal_rank, stable = estimate_normal_rank(coefficients)
        if not stable or normal_rank != coefficients[0].shape[0]:
            return ()
        retained: list[float] = []
        for value in _companion_eigenvalues(coefficients):
            if abs(value.imag) > REAL_TOL * max(1.0, abs(value.real)):
                continue
            real_value = float(value.real)
            if not canonical_source_replay(problem, real_value, normal_rank):
                continue
            if not any(
                abs(real_value - prior) <= CLUSTER_REL_TOL * max(1.0, abs(real_value))
                for prior in retained
            ):
                retained.append(real_value)
        return tuple(sorted(retained))
    except Exception:
        return ()


def _classify_completed_value(
    coefficients: Sequence[np.ndarray],
    completed: Sequence[np.ndarray],
    left_basis: np.ndarray,
    right_basis: np.ndarray,
    value: complex,
    *,
    normal_rank: int,
    trial: int,
) -> TrialEigenvalue | None:
    completed_matrix = evaluate_polynomial(completed, value)
    left_vectors, _, right_vectors_h = np.linalg.svd(completed_matrix)
    left_vector = left_vectors[:, -1]
    right_vector = right_vectors_h.conj().T[:, -1]
    left_overlap = float(np.linalg.norm(left_basis.conj().T @ left_vector))
    right_overlap = float(np.linalg.norm(right_basis.conj().T @ right_vector))
    drop = _rank_drop_ratio(evaluate_polynomial(coefficients, value), normal_rank)
    if drop > DROP_REL_TOL or left_overlap > VECTOR_ORTH_TOL or right_overlap > VECTOR_ORTH_TOL:
        return None
    return TrialEigenvalue(value, trial, drop, left_overlap, right_overlap)


def _deduplicate_trial(values: Sequence[TrialEigenvalue]) -> tuple[TrialEigenvalue, ...]:
    retained: list[TrialEigenvalue] = []
    for item in sorted(values, key=lambda x: (x.value.real, x.value.imag)):
        if any(abs(item.value - previous.value) <= CLUSTER_REL_TOL * max(1.0, abs(item.value)) for previous in retained):
            continue
        retained.append(item)
    return tuple(retained)


def _consensus(values: Sequence[TrialEigenvalue], minimum_trials: int) -> tuple[complex, ...]:
    clusters: list[list[TrialEigenvalue]] = []
    for item in sorted(values, key=lambda x: (x.value.real, x.value.imag, x.trial)):
        target: list[TrialEigenvalue] | None = None
        for cluster in clusters:
            center = sum(member.value for member in cluster) / len(cluster)
            if abs(item.value - center) <= CLUSTER_REL_TOL * max(1.0, abs(item.value), abs(center)):
                target = cluster
                break
        if target is None:
            clusters.append([item])
        else:
            target.append(item)
    output: list[complex] = []
    for cluster in clusters:
        if len({item.trial for item in cluster}) < minimum_trials:
            continue
        output.append(sum(item.value for item in cluster) / len(cluster))
    return tuple(output)


def discover_true_eigenvalues(
    problem: PolynomialMatrixProblem, *, trials: int = DEFAULT_TRIALS
) -> RankCompletionResult:
    if problem.opaque:
        return RankCompletionResult(False, "opaque_fallback", 0, 0, (), (), 0, 0, 0, 0)
    try:
        coefficients = _validate(problem)
        normal_rank, stable = estimate_normal_rank(coefficients)
    except Exception as error:
        return RankCompletionResult(False, f"invalid_input:{type(error).__name__}", 0, 0, (), (), 0, 0, 0, 0)
    size = coefficients[0].shape[0]
    if not stable:
        return RankCompletionResult(False, "ambiguous_normal_rank", normal_rank, size - normal_rank, (), (), 0, 0, 0, 0)
    if normal_rank == size:
        return RankCompletionResult(False, "regular_polynomial_fallback", normal_rank, 0, (), (), 0, 0, 0, 0)
    if normal_rank <= 0 or not 3 <= trials <= 9:
        return RankCompletionResult(False, "unsupported_corank_or_trials", normal_rank, size - normal_rank, (), (), 0, 0, 0, 0)

    accepted: list[TrialEigenvalue] = []
    finite_count = 0
    rejected_fake = 0
    corank = size - normal_rank
    for trial in range(trials):
        completed, left_basis, right_basis = _completion(coefficients, trial=trial, corank=corank)
        trial_values: list[TrialEigenvalue] = []
        for value in _companion_eigenvalues(completed):
            finite_count += 1
            classified = _classify_completed_value(
                coefficients,
                completed,
                left_basis,
                right_basis,
                value,
                normal_rank=normal_rank,
                trial=trial,
            )
            if classified is None:
                rejected_fake += 1
            else:
                trial_values.append(classified)
        accepted.extend(_deduplicate_trial(trial_values))

    consensus = _consensus(accepted, minimum_trials=max(2, trials - 1))
    proposals: list[float] = []
    rejected_nonreal = 0
    rejected_replay = 0
    for value in consensus:
        if problem.real_only and abs(value.imag) > REAL_TOL * max(1.0, abs(value.real)):
            rejected_nonreal += 1
            continue
        real_value = float(value.real)
        if not canonical_source_replay(problem, real_value, normal_rank):
            rejected_replay += 1
            continue
        if not any(abs(real_value - prior) <= CLUSTER_REL_TOL * max(1.0, abs(real_value)) for prior in proposals):
            proposals.append(real_value)
    proposals.sort()
    return RankCompletionResult(
        True,
        "stable_singular_polynomial_matrix",
        normal_rank,
        corank,
        tuple(proposals),
        tuple(accepted),
        finite_count,
        rejected_fake,
        rejected_nonreal,
        rejected_replay,
    )


def run_portfolio(
    problem: PolynomialMatrixProblem,
    baseline_proposals: Sequence[float],
    *,
    starts: int = 16,
    trials: int = DEFAULT_TRIALS,
) -> PortfolioResult:
    baseline = tuple(float(value) for value in baseline_proposals)
    before = _digest(baseline)
    side = discover_true_eigenvalues(problem, trials=trials)
    retained = list(baseline)
    for value in side.proposals:
        if not any(abs(value - prior) <= CLUSTER_REL_TOL * max(1.0, abs(value)) for prior in retained):
            retained.append(value)
    retained.sort()
    return PortfolioResult(tuple(retained), side, route_trace(starts), before, _digest(baseline))
