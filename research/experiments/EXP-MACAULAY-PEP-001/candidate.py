"""Disposable Macaulay-nullspace eigenproposal for tiny polynomial blocks.

This module is proposal-only.  It accepts no benchmark metadata and releases
no point until an externally supplied canonical replay accepts the point.
"""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Callable, Mapping, Sequence

import numpy as np
from scipy import linalg


MAX_VARIABLES = 2
MAX_EQUATION_DEGREE = 3
MAX_QUOTIENT_DIMENSION = 8
BASELINE_QUOTA = 0.75
RANK_RELATIVE_TOLERANCE = 5.0e-11
BASIS_CONDITION_LIMIT = 1.0e10
COMMUTATOR_LIMIT = 5.0e-6
REAL_TOLERANCE = 2.0e-6

Exponent = tuple[int, ...]
Polynomial = Mapping[Exponent, float]


@dataclass(frozen=True)
class PolynomialBlock:
    variable_count: int
    equations: tuple[Polynomial, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    semantic_kind: str = "literal_polynomial"
    rank_signal: str = "unknown"


@dataclass(frozen=True)
class Proposal:
    point: tuple[float, ...]
    residual_inf: float
    replay_payload: Mapping[str, object]


@dataclass(frozen=True)
class ProposalResult:
    status: str
    applicable: bool
    proposals: tuple[Proposal, ...]
    macaulay_degree: int | None
    expected_quotient_dimension: int | None
    observed_nullity: int | None
    baseline_quota: float = BASELINE_QUOTA
    proposal_is_authority: bool = False
    canonical_replay_required: bool = True


def _monomials(variable_count: int, maximum_degree: int) -> tuple[Exponent, ...]:
    values = [
        exponent
        for exponent in itertools.product(range(maximum_degree + 1), repeat=variable_count)
        if sum(exponent) <= maximum_degree
    ]
    return tuple(sorted(values, key=lambda exponent: (sum(exponent), exponent)))


def _degree(polynomial: Polynomial, variable_count: int) -> int | None:
    degrees: list[int] = []
    for exponent, coefficient in polynomial.items():
        if (
            not isinstance(exponent, tuple)
            or len(exponent) != variable_count
            or any(type(value) is not int or value < 0 for value in exponent)
            or not isinstance(coefficient, (int, float))
            or isinstance(coefficient, bool)
            or not math.isfinite(float(coefficient))
        ):
            return None
        if float(coefficient) != 0.0:
            degrees.append(sum(exponent))
    return max(degrees, default=None)


def evaluate(polynomial: Polynomial, point: Sequence[float]) -> float:
    return math.fsum(
        float(coefficient)
        * math.prod(float(value) ** power for value, power in zip(point, exponent, strict=True))
        for exponent, coefficient in polynomial.items()
    )


def residual_inf(block: PolynomialBlock, point: Sequence[float]) -> float:
    return max(abs(evaluate(polynomial, point)) for polynomial in block.equations)


def _reject(status: str) -> ProposalResult:
    return ProposalResult(status, False, (), None, None, None)


def _macaulay(
    block: PolynomialBlock, degrees: Sequence[int], macaulay_degree: int
) -> tuple[np.ndarray, tuple[Exponent, ...]]:
    monomials = _monomials(block.variable_count, macaulay_degree)
    ordinal = {monomial: index for index, monomial in enumerate(monomials)}
    rows: list[np.ndarray] = []
    for polynomial, degree in zip(block.equations, degrees, strict=True):
        for multiplier in _monomials(block.variable_count, macaulay_degree - degree):
            row = np.zeros(len(monomials), dtype=float)
            for exponent, coefficient in polynomial.items():
                shifted = tuple(a + b for a, b in zip(exponent, multiplier, strict=True))
                row[ordinal[shifted]] += float(coefficient)
            rows.append(row)
    return np.vstack(rows), monomials


def _nullspace(
    matrix: np.ndarray, expected: int
) -> tuple[np.ndarray, int, float] | None:
    _u, singular, vh = np.linalg.svd(matrix, full_matrices=True)
    scale = max(float(singular[0]) if singular.size else 0.0, 1.0)
    rank = int(np.count_nonzero(singular > RANK_RELATIVE_TOLERANCE * scale))
    nullity = matrix.shape[1] - rank
    if nullity != expected or rank < matrix.shape[0]:
        return None
    # The expected quotient dimension is the rank completion: retain exactly
    # the structurally missing right-singular directions, never an inferred
    # benchmark-dependent dimension.
    basis = vh[rank:, :].conj().T
    rank_margin = (
        float(singular[rank - 1] / scale) if rank > 0 and singular.size >= rank else 0.0
    )
    return basis, nullity, rank_margin


def _multiplication_matrices(
    nullspace: np.ndarray,
    monomials: Sequence[Exponent],
    variable_count: int,
    macaulay_degree: int,
    quotient_dimension: int,
) -> tuple[np.ndarray, ...] | None:
    ordinal = {monomial: index for index, monomial in enumerate(monomials)}
    low = [
        index for index, monomial in enumerate(monomials)
        if sum(monomial) < macaulay_degree
    ]
    if len(low) < quotient_dimension:
        return None
    # CPQR on candidate rows selects a numerically independent quotient basis.
    _q, _r, pivots = linalg.qr(nullspace[low, :].T, pivoting=True, mode="economic")
    selected = [low[int(index)] for index in pivots[:quotient_dimension]]
    basis = nullspace[selected, :]
    if np.linalg.cond(basis) > BASIS_CONDITION_LIMIT:
        return None
    inverse = np.linalg.inv(basis)
    matrices: list[np.ndarray] = []
    for variable in range(variable_count):
        shifted_rows: list[int] = []
        for index in selected:
            exponent = list(monomials[index])
            exponent[variable] += 1
            shifted = tuple(exponent)
            if shifted not in ordinal:
                return None
            shifted_rows.append(ordinal[shifted])
        matrices.append(nullspace[shifted_rows, :] @ inverse)
    for left in matrices:
        for right in matrices:
            denominator = max(np.linalg.norm(left) * np.linalg.norm(right), 1.0)
            if np.linalg.norm(left @ right - right @ left) / denominator > COMMUTATOR_LIMIT:
                return None
    return tuple(matrices)


def _eigenproposals(matrices: Sequence[np.ndarray]) -> tuple[tuple[float, ...], ...]:
    pencil = sum((index + 1.0) * matrix for index, matrix in enumerate(matrices))
    dimension = pencil.shape[0]
    left = np.arange(1, dimension + 1, dtype=float)
    right = left[::-1].copy()
    left /= np.linalg.norm(left)
    right /= np.linalg.norm(right)
    # A fixed rank-one completion splits a defective/singular local pencil.
    # Its eigenvalues are never authorities: real projections must survive the
    # untouched canonical replay below.
    completion_scale = 1.0e-12 * max(float(np.linalg.norm(pencil)), 1.0)
    completed_pencil = pencil + completion_scale * np.outer(left, right)
    _values, vectors = np.linalg.eig(completed_pencil)
    points: list[tuple[float, ...]] = []
    for column in range(vectors.shape[1]):
        vector = vectors[:, column]
        denominator = np.vdot(vector, vector)
        if abs(denominator) <= 1.0e-30:
            continue
        coordinates = [np.vdot(vector, matrix @ vector) / denominator for matrix in matrices]
        if any(abs(value.imag) > REAL_TOLERANCE * max(1.0, abs(value.real)) for value in coordinates):
            continue
        point = tuple(float(value.real) for value in coordinates)
        if all(math.isfinite(value) for value in point):
            points.append(point)
    return tuple(points)


def propose(
    block: PolynomialBlock,
    canonical_replay: Callable[[tuple[float, ...]], Mapping[str, object]],
) -> ProposalResult:
    if block.semantic_kind != "literal_polynomial":
        return _reject("OPAQUE_OR_NONPOLYNOMIAL_BASELINE_ONLY")
    if block.rank_signal not in {"stable_rank_deficient", "near_multiple"}:
        return _reject("RANK_TRIGGER_BASELINE_ONLY")
    if (
        block.variable_count < 1
        or block.variable_count > MAX_VARIABLES
        or len(block.equations) != block.variable_count
        or len(block.lower) != block.variable_count
        or len(block.upper) != block.variable_count
        or any(
            not math.isfinite(float(low))
            or not math.isfinite(float(high))
            or not float(low) < float(high)
            for low, high in zip(block.lower, block.upper, strict=True)
        )
    ):
        return _reject("STRUCTURAL_GATE_REJECTED")
    degrees = tuple(_degree(polynomial, block.variable_count) for polynomial in block.equations)
    if any(degree is None or degree < 1 or degree > MAX_EQUATION_DEGREE for degree in degrees):
        return _reject("POLYNOMIAL_DEGREE_GATE_REJECTED")
    concrete_degrees = tuple(int(degree) for degree in degrees if degree is not None)
    quotient_dimension = math.prod(concrete_degrees)
    if quotient_dimension > MAX_QUOTIENT_DIMENSION:
        return _reject("QUOTIENT_DIMENSION_GATE_REJECTED")
    macaulay_degree = sum(degree - 1 for degree in concrete_degrees) + 1
    matrix, monomials = _macaulay(block, concrete_degrees, macaulay_degree)
    completed = _nullspace(matrix, quotient_dimension)
    if completed is None:
        return ProposalResult(
            "RANK_COMPLETION_GATE_REJECTED", False, (), macaulay_degree,
            quotient_dimension, None,
        )
    nullspace, observed_nullity, _rank_margin = completed
    matrices = _multiplication_matrices(
        nullspace, monomials, block.variable_count, macaulay_degree, quotient_dimension
    )
    if matrices is None:
        return ProposalResult(
            "MULTIPLICATION_PENCIL_GATE_REJECTED", False, (), macaulay_degree,
            quotient_dimension, observed_nullity,
        )

    accepted: list[Proposal] = []
    for point in _eigenproposals(matrices):
        if any(
            value < low or value > high
            for value, low, high in zip(point, block.lower, block.upper, strict=True)
        ):
            continue
        try:
            replay = canonical_replay(point)
        except Exception:
            continue
        if not isinstance(replay, Mapping) or replay.get("safe") is not True:
            continue
        try:
            replay_residual = float(replay.get("residual_inf"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(replay_residual) or replay_residual > 1.0e-7:
            continue
        if any(
            all(abs(a - b) <= 2.0e-7 * max(abs(a), abs(b), 1.0)
                for a, b in zip(existing.point, point, strict=True))
            for existing in accepted
        ):
            continue
        accepted.append(Proposal(point, replay_residual, dict(replay)))
    return ProposalResult(
        "PROPOSALS_REPLAY_ACCEPTED" if accepted else "NO_CANONICAL_PROPOSAL",
        True,
        tuple(accepted),
        macaulay_degree,
        quotient_dimension,
        observed_nullity,
    )


def portfolio_slots(total_slots: int) -> tuple[int, int]:
    if total_slots < 1:
        raise ValueError("total_slots must be positive")
    baseline = math.ceil(BASELINE_QUOTA * total_slots)
    return baseline, total_slots - baseline
