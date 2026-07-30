"""Tiny operator-safe trigonometric lift and algebraic proposal lane.

This is deliberately not a source-expression compiler.  It consumes only an
already recognized, typed pair of explicit sine/cosine constructions for one
affine phase.  Numerical roots are proposals; the untouched canonical source
replay is the only authority for bounds, branches, ordinals, guards and
residuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from typing import Callable, Mapping

import numpy as np
from numpy.polynomial import Polynomial as UniPolynomial


BASELINE_QUOTA = 0.75
MAX_EQUATIONS = 4
MAX_TOTAL_DEGREE = 6
MAX_UNIVARIATE_DEGREE = 12
MAX_SHEETS = 16
ROOT_IMAGINARY_TOLERANCE = 2.0e-7
LIFTED_RESIDUAL_TOLERANCE = 2.0e-6
REPLAY_RESIDUAL_TOLERANCE = 1.0e-7

Exponent = tuple[int, int]
Polynomial = Mapping[Exponent, float]


@dataclass(frozen=True)
class PhaseSpec:
    """Exact metadata emitted by an existing typed operator frontend.

    For radians, ``phi = multiplier * theta + pi * offset``.  For turns,
    ``phi = 2*pi*(multiplier * theta + offset)``.  Rational metadata prevents
    a floating phase matcher from silently joining different constructions.
    """

    variable: str
    unit: str
    multiplier: Fraction
    offset: Fraction = Fraction(0)
    source_operator: str = "SinCos"
    phase_id: str = "phase-0"


@dataclass(frozen=True)
class TrigBlock:
    variable: str
    sine_phase: PhaseSpec | None
    cosine_phase: PhaseSpec | None
    equations: tuple[Polynomial, ...]
    lower: float
    upper: float
    lower_closed: bool = True
    upper_closed: bool = True
    semantic_kind: str = "explicit_sin_cos_pair"
    raw_angle_escape: bool = False
    required_branch: str | None = None
    required_ordinal: int | None = None


@dataclass(frozen=True)
class SourceCandidate:
    variable: str
    value: float
    cosine: float
    sine: float
    sheet: int
    phase_id: str
    required_branch: str | None
    required_ordinal: int | None
    lower_closed: bool
    upper_closed: bool


@dataclass(frozen=True)
class Proposal:
    source_value: float
    cosine: float
    sine: float
    sheet: int
    lifted_residual_inf: float
    replay_payload: Mapping[str, object]


@dataclass(frozen=True)
class ProposalResult:
    status: str
    applicable: bool
    proposals: tuple[Proposal, ...]
    transformed_degrees: tuple[int, ...]
    replay_attempts: int
    pole_checked: bool
    baseline_quota: float = BASELINE_QUOTA
    proposal_is_authority: bool = False
    canonical_replay_required: bool = True


@dataclass(frozen=True)
class DistanceOperand:
    """Squared Distance supplied by existing operator metadata."""

    squared_polynomial: Polynomial
    source_operator: str = "Distance"
    nonnegative_proved: bool = True


class UnsafeLowering(ValueError):
    pass


def _validate_polynomial(polynomial: Polynomial) -> int:
    if not isinstance(polynomial, Mapping) or not polynomial:
        raise UnsafeLowering("polynomial must contain at least one term")
    degree = 0
    nonzero = False
    for exponent, coefficient in polynomial.items():
        if (
            not isinstance(exponent, tuple)
            or len(exponent) != 2
            or any(type(power) is not int or power < 0 for power in exponent)
            or not isinstance(coefficient, (int, float))
            or isinstance(coefficient, bool)
            or not math.isfinite(float(coefficient))
        ):
            raise UnsafeLowering("invalid bivariate polynomial term")
        if float(coefficient) != 0.0:
            nonzero = True
            degree = max(degree, sum(exponent))
    if not nonzero:
        return 0
    if degree > MAX_TOTAL_DEGREE:
        raise UnsafeLowering("polynomial degree cap exceeded")
    return degree


def _combine(left: Polynomial, right: Polynomial, right_scale: float) -> dict[Exponent, float]:
    result = {exponent: float(coefficient) for exponent, coefficient in left.items()}
    for exponent, coefficient in right.items():
        result[exponent] = result.get(exponent, 0.0) + right_scale * float(coefficient)
    return {exponent: coefficient for exponent, coefficient in result.items() if coefficient != 0.0}


def sound_distance_equality_square(
    left: DistanceOperand, right: DistanceOperand | float
) -> dict[Exponent, float]:
    """Lower ``Distance == nonnegative`` without erasing a sqrt/abs branch.

    This helper accepts only typed ``Distance`` operands whose nonnegativity is
    already proved by the operator registry, or an explicit nonnegative
    literal.  Arbitrary expressions and inferred signs fail closed.
    """

    if left.source_operator != "Distance" or left.nonnegative_proved is not True:
        raise UnsafeLowering("left operand lacks proved Distance nonnegativity")
    _validate_polynomial(left.squared_polynomial)
    if isinstance(right, DistanceOperand):
        if right.source_operator != "Distance" or right.nonnegative_proved is not True:
            raise UnsafeLowering("right operand lacks proved Distance nonnegativity")
        _validate_polynomial(right.squared_polynomial)
        return _combine(left.squared_polynomial, right.squared_polynomial, -1.0)
    if (
        not isinstance(right, (int, float))
        or isinstance(right, bool)
        or not math.isfinite(float(right))
        or float(right) < 0.0
    ):
        raise UnsafeLowering("distance literal must be finite and nonnegative")
    return _combine(left.squared_polynomial, {(0, 0): float(right) ** 2}, -1.0)


def evaluate(polynomial: Polynomial, cosine: float, sine: float) -> float:
    return math.fsum(
        float(coefficient) * cosine**i * sine**j
        for (i, j), coefficient in polynomial.items()
    )


def lifted_residual_inf(block: TrigBlock, cosine: float, sine: float) -> float:
    values = [abs(evaluate(polynomial, cosine, sine)) for polynomial in block.equations]
    values.append(abs(cosine * cosine + sine * sine - 1.0))
    return max(values)


def _reject(status: str) -> ProposalResult:
    return ProposalResult(status, False, (), (), 0, False)


def _recognize(block: TrigBlock) -> str | None:
    if block.semantic_kind not in {"explicit_sin_cos_pair", "point_on_circle_angle_pair"}:
        return "OPAQUE_OR_UNRECOGNIZED_BASELINE_ONLY"
    if block.sine_phase is None or block.cosine_phase is None:
        return "INCOMPLETE_TRIG_PAIR_BASELINE_ONLY"
    if block.sine_phase != block.cosine_phase:
        return "PHASE_OR_UNIT_MISMATCH_BASELINE_ONLY"
    phase = block.sine_phase
    if phase.variable != block.variable or not phase.variable or block.raw_angle_escape:
        return "RAW_ANGLE_ESCAPE_BASELINE_ONLY"
    if not isinstance(phase.multiplier, Fraction) or not isinstance(phase.offset, Fraction):
        return "INEXACT_PHASE_METADATA_BASELINE_ONLY"
    if phase.multiplier == 0:
        return "CONSTANT_PHASE_BASELINE_ONLY"
    if phase.unit == "radians":
        if phase.source_operator != "SinCos":
            return "OPERATOR_UNIT_MISMATCH_BASELINE_ONLY"
    elif phase.unit == "turns":
        if phase.source_operator != "PointOnCircle":
            return "OPERATOR_UNIT_MISMATCH_BASELINE_ONLY"
    else:
        return "UNKNOWN_PHASE_UNIT_BASELINE_ONLY"
    if (
        not math.isfinite(float(block.lower))
        or not math.isfinite(float(block.upper))
        or not float(block.lower) < float(block.upper)
    ):
        return "NONFINITE_OR_EMPTY_SHEET_LEDGER_BASELINE_ONLY"
    phase_span_cycles = abs(float(phase.multiplier)) * (block.upper - block.lower)
    if phase.unit == "radians":
        phase_span_cycles /= 2.0 * math.pi
    if math.ceil(phase_span_cycles) + 2 > MAX_SHEETS:
        return "SHEET_CAP_BASELINE_ONLY"
    if not 1 <= len(block.equations) <= MAX_EQUATIONS:
        return "EQUATION_COUNT_BASELINE_ONLY"
    try:
        for polynomial in block.equations:
            _validate_polynomial(polynomial)
    except UnsafeLowering:
        return "POLYNOMIAL_GATE_BASELINE_ONLY"
    return None


def _stereographic_numerator(polynomial: Polynomial) -> np.ndarray | None:
    """Substitute c=(1-u^2)/(1+u^2), s=2u/(1+u^2)."""

    degree = _validate_polynomial(polynomial)
    one_minus_square = UniPolynomial([1.0, 0.0, -1.0])
    two_u = UniPolynomial([0.0, 2.0])
    one_plus_square = UniPolynomial([1.0, 0.0, 1.0])
    numerator = UniPolynomial([0.0])
    for (i, j), coefficient in polynomial.items():
        denominator_power = degree - i - j
        term = (
            float(coefficient)
            * one_minus_square**i
            * two_u**j
            * one_plus_square**denominator_power
        )
        numerator = numerator + term
    coefficients = np.asarray(numerator.coef, dtype=float)
    scale = max(float(np.max(np.abs(coefficients))), 1.0)
    coefficients[np.abs(coefficients) <= 5.0e-13 * scale] = 0.0
    nonzero = np.flatnonzero(coefficients)
    if not nonzero.size:
        return None
    coefficients = coefficients[: int(nonzero[-1]) + 1]
    if len(coefficients) - 1 > MAX_UNIVARIATE_DEGREE:
        raise UnsafeLowering("stereographic degree cap exceeded")
    return coefficients


def _lifted_points(block: TrigBlock) -> tuple[tuple[float, float], ...] | None:
    numerators: list[np.ndarray] = []
    for equation in block.equations:
        numerator = _stereographic_numerator(equation)
        if numerator is not None:
            numerators.append(numerator)
    if not numerators:
        return None
    # The smallest polynomial is a deterministic finite candidate generator;
    # every equation is still checked below.
    generator = min(numerators, key=lambda values: (len(values), tuple(values.tolist())))
    roots = np.polynomial.polynomial.polyroots(generator)
    points: list[tuple[float, float]] = []
    for root in roots:
        if abs(float(root.imag)) > ROOT_IMAGINARY_TOLERANCE * max(1.0, abs(float(root.real))):
            continue
        u = float(root.real)
        if not math.isfinite(u):
            continue
        denominator = 1.0 + u * u
        point = ((1.0 - u * u) / denominator, 2.0 * u / denominator)
        if lifted_residual_inf(block, *point) <= LIFTED_RESIDUAL_TOLERANCE:
            points.append(point)
    # u=infinity is omitted by stereographic coordinates.  Check the pole
    # explicitly; this is essential for antipodal PointOnCircle roots.
    pole = (-1.0, 0.0)
    if lifted_residual_inf(block, *pole) <= LIFTED_RESIDUAL_TOLERANCE:
        points.append(pole)
    unique: list[tuple[float, float]] = []
    for point in points:
        if not any(math.hypot(point[0] - c, point[1] - s) <= 2.0e-7 for c, s in unique):
            unique.append(point)
    return tuple(unique)


def _inverse_sheets(block: TrigBlock, cosine: float, sine: float) -> tuple[tuple[float, int], ...]:
    phase = block.sine_phase
    assert phase is not None
    principal = math.atan2(sine, cosine)
    multiplier = float(phase.multiplier)
    offset = float(phase.offset)
    if phase.unit == "radians":
        endpoints = [
            multiplier * block.lower + math.pi * offset,
            multiplier * block.upper + math.pi * offset,
        ]
        raw_low = (min(endpoints) - principal) / (2.0 * math.pi)
        raw_high = (max(endpoints) - principal) / (2.0 * math.pi)
        inverse_base = principal - math.pi * offset
        inverse_step = 2.0 * math.pi
    else:
        endpoints = [multiplier * block.lower + offset, multiplier * block.upper + offset]
        principal_turn = principal / (2.0 * math.pi)
        raw_low = min(endpoints) - principal_turn
        raw_high = max(endpoints) - principal_turn
        inverse_base = principal_turn - offset
        inverse_step = 1.0
    start = math.floor(raw_low) - 1
    stop = math.ceil(raw_high) + 2
    values: list[tuple[float, int]] = []
    scale = max(abs(block.lower), abs(block.upper), 1.0)
    for sheet in range(start, stop):
        value = float((inverse_base + inverse_step * sheet) / multiplier)
        # This is only an inclusive prefilter. Strict endpoints and all source
        # guards are deliberately left to canonical replay.
        if block.lower - 2.0e-12 * scale <= value <= block.upper + 2.0e-12 * scale:
            values.append((value, sheet))
    return tuple(values)


def propose(
    block: TrigBlock,
    canonical_replay: Callable[[SourceCandidate], Mapping[str, object]],
) -> ProposalResult:
    rejection = _recognize(block)
    if rejection is not None:
        return _reject(rejection)
    try:
        numerators = tuple(_stereographic_numerator(equation) for equation in block.equations)
        transformed_degrees = tuple(
            -1 if numerator is None else len(numerator) - 1 for numerator in numerators
        )
        points = _lifted_points(block)
    except (UnsafeLowering, ArithmeticError, ValueError, np.linalg.LinAlgError):
        return _reject("ALGEBRAIC_SIDE_SOLVER_FAILURE_BASELINE_ONLY")
    if points is None:
        return ProposalResult(
            "POSITIVE_DIMENSIONAL_BASELINE_ONLY", False, (), transformed_degrees, 0, False
        )
    if not points:
        return ProposalResult(
            "NO_LIFTED_REAL_ROOT", True, (), transformed_degrees, 0, True
        )
    attempts = 0
    accepted: list[Proposal] = []
    phase = block.sine_phase
    assert phase is not None
    for cosine, sine in points:
        for source_value, sheet in _inverse_sheets(block, cosine, sine):
            attempts += 1
            source = SourceCandidate(
                block.variable,
                source_value,
                cosine,
                sine,
                sheet,
                phase.phase_id,
                block.required_branch,
                block.required_ordinal,
                block.lower_closed,
                block.upper_closed,
            )
            try:
                replay = canonical_replay(source)
            except Exception:
                continue
            if not isinstance(replay, Mapping):
                continue
            if any(
                replay.get(field) is not True
                for field in (
                    "safe",
                    "canonical_source_replay",
                    "strict_guards_valid",
                    "branch_valid",
                    "ordinal_valid",
                )
            ):
                continue
            try:
                replay_residual = float(replay.get("residual_inf"))
            except (TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(replay_residual) or replay_residual > REPLAY_RESIDUAL_TOLERANCE:
                continue
            if any(
                abs(proposal.source_value - source_value)
                <= 2.0e-8 * max(abs(proposal.source_value), abs(source_value), 1.0)
                for proposal in accepted
            ):
                continue
            accepted.append(
                Proposal(
                    source_value,
                    cosine,
                    sine,
                    sheet,
                    lifted_residual_inf(block, cosine, sine),
                    dict(replay),
                )
            )
    return ProposalResult(
        "PROPOSALS_REPLAY_ACCEPTED" if accepted else "NO_CANONICAL_PROPOSAL",
        True,
        tuple(sorted(accepted, key=lambda proposal: proposal.source_value)),
        transformed_degrees,
        attempts,
        True,
    )


def portfolio_slots(total_slots: int) -> tuple[int, int]:
    if total_slots < 1:
        raise ValueError("total_slots must be positive")
    baseline = math.ceil(BASELINE_QUOTA * total_slots)
    return baseline, total_slots - baseline
