"""Deterministic repository-owned PSLQ and algebraic-number verification.

Only arbitrary-precision arithmetic and exact polynomial utilities are
borrowed from dependencies.  In particular, neither mpmath nor SymPy's PSLQ
implementation is called.  The integer-relation iteration is the
Ferguson--Bailey--Arno fixed-point algorithm implemented below.

The public entry point deliberately requires two independently supplied
numeric lanes.  A 768-bit lane proposes a relation and a 1024-bit lane reruns
the integer-relation search and verifies the same irreducible factor.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from functools import reduce
from math import gcd, isqrt
from typing import Sequence

from mpmath import mp


MIN_PROPOSAL_BITS = 768
MIN_CONFIRMATION_BITS = 1024
MAX_DEGREE = 8
MIN_COEFFICIENT_BITS = 31
MAX_COEFFICIENT_BITS = 63


class RecognitionError(ValueError):
    """The recognition request violates the exact-lane contract."""


@dataclass(frozen=True)
class PSLQBudget:
    precision_bits: int
    tolerance_bits: int
    max_degree: int
    max_steps: int
    coefficient_cap_bits: int
    coefficient_cap: int


@dataclass(frozen=True)
class PSLQIteration:
    relation_low_to_high: tuple[int, ...] | None
    iterations: int
    termination: str
    best_fixed_error_bits: int | None
    norm_lower_bound: int | None
    coefficient_cap: int


def coefficient_cap_for(
    *, precision_bits: int, degree: int, max_steps: int
) -> tuple[int, int]:
    """Derive a bounded coefficient cap from precision and work.

    The precision term reserves 128 bits for verification and apportions the
    rest across the relation dimension.  The iteration term prevents a short
    run from accepting coefficients whose search space it could not have
    explored meaningfully.  Both are clamped to the signed 64-bit range used
    by the exact-descriptor interface.  The minimum still covers legacy
    coefficients above ``1e8`` without introducing a fixture-specific cap.
    """

    if precision_bits < 128:
        raise RecognitionError("precision_bits must be at least 128")
    if not 1 <= degree <= MAX_DEGREE:
        raise RecognitionError(f"degree must be in 1..{MAX_DEGREE}")
    if max_steps < 1:
        raise RecognitionError("max_steps must be positive")
    precision_bound = max(
        MIN_COEFFICIENT_BITS,
        (precision_bits - 128) // (degree + 1),
    )
    iteration_bound = max(
        MIN_COEFFICIENT_BITS,
        int(math.log2(max_steps)) + 20,
    )
    cap_bits = min(MAX_COEFFICIENT_BITS, precision_bound, iteration_bound)
    return cap_bits, 1 << cap_bits


def make_budget(
    *,
    precision_bits: int,
    degree: int,
    max_steps: int,
    tolerance_bits: int | None = None,
) -> PSLQBudget:
    if tolerance_bits is None:
        tolerance_bits = min(600, 3 * precision_bits // 4)
    if tolerance_bits < 128 or tolerance_bits >= precision_bits:
        raise RecognitionError("tolerance_bits must be in [128, precision_bits)")
    cap_bits, cap = coefficient_cap_for(
        precision_bits=precision_bits,
        degree=degree,
        max_steps=max_steps,
    )
    return PSLQBudget(
        precision_bits=precision_bits,
        tolerance_bits=tolerance_bits,
        max_degree=degree,
        max_steps=max_steps,
        coefficient_cap_bits=cap_bits,
        coefficient_cap=cap,
    )


def _round_fixed(value: int, precision: int) -> int:
    return ((value + (1 << (precision - 1))) >> precision) << precision


def _sqrt_fixed(value: int, precision: int) -> int:
    if value < 0:
        raise ArithmeticError("negative fixed-point square root")
    return isqrt(value << precision)


def _primitive_relation_low_to_high(values: Sequence[int]) -> tuple[int, ...] | None:
    relation = [int(value) for value in values]
    while len(relation) > 1 and relation[-1] == 0:
        relation.pop()
    if len(relation) < 2 or not any(relation):
        return None
    common = reduce(gcd, (abs(value) for value in relation if value), 0)
    if common > 1:
        relation = [value // common for value in relation]
    if relation[-1] < 0:
        relation = [-value for value in relation]
    return tuple(relation)


def _fixed_error_bits(error: int, precision: int) -> int | None:
    if error <= 0:
        return None
    return precision - (error.bit_length() - 1)


def pslq_fixed(
    values: Sequence[object],
    *,
    budget: PSLQBudget,
) -> PSLQIteration:
    """Run one fixed-point Ferguson--Bailey--Arno PSLQ search.

    ``values`` are converted once at the declared precision plus 64 guard
    bits.  Matrices ``A`` and ``B`` remain exact fixed-point integers, so this
    routine has no dependency on another PSLQ implementation.
    """

    n = len(values)
    if n < 2:
        raise RecognitionError("PSLQ needs at least two values")
    if n != budget.max_degree + 1:
        raise RecognitionError("budget degree does not match vector length")
    precision = budget.precision_bits + 64
    scale = 1 << precision
    with mp.workprec(precision + 32):
        fixed = [int(mp.nint(mp.mpf(value) * scale)) for value in values]
    if any(value == 0 for value in fixed):
        raise RecognitionError("PSLQ input vector contains zero")
    tolerance = 1 << (precision - budget.tolerance_bits)
    gamma = _sqrt_fixed((4 << precision) // 3, precision)

    # The implementation uses zero-based storage but follows the published
    # 1-based PSLQ steps.  Matrix entries are fixed-point integers.
    identity = 1 << precision
    a = [[identity if row == column else 0 for column in range(n)] for row in range(n)]
    b = [[identity if row == column else 0 for column in range(n)] for row in range(n)]
    h = [[0 for _column in range(n)] for _row in range(n)]

    s = [0] * n
    for k in range(n):
        squared = sum((fixed[j] * fixed[j]) >> precision for j in range(k, n))
        s[k] = _sqrt_fixed(squared, precision)
    norm = s[0]
    if norm == 0:
        raise RecognitionError("zero PSLQ input norm")
    y = [(value << precision) // norm for value in fixed]
    s = [(value << precision) // norm for value in s]

    for i in range(n):
        if i < n - 1:
            h[i][i] = (s[i + 1] << precision) // s[i] if s[i] else 0
        for j in range(i):
            denominator = s[j] * s[j + 1]
            h[i][j] = ((-y[i] * y[j]) << precision) // denominator if denominator else 0

    def reduce_row(i: int, j: int) -> bool:
        if h[j][j] == 0:
            return False
        multiplier = _round_fixed((h[i][j] << precision) // h[j][j], precision)
        y[j] += (multiplier * y[i]) >> precision
        for k in range(j + 1):
            h[i][k] -= (multiplier * h[j][k]) >> precision
        for k in range(n):
            a[i][k] -= (multiplier * a[j][k]) >> precision
            b[k][j] += (multiplier * b[k][i]) >> precision
        return True

    for i in range(1, n):
        for j in range(i - 1, -1, -1):
            reduce_row(i, j)

    best_error: int | None = None
    norm_lower_bound: int | None = None
    for iteration in range(1, budget.max_steps + 1):
        weighted = []
        gamma_power = identity
        for i in range(n - 1):
            gamma_power = (gamma_power * gamma) >> precision
            weighted.append(gamma_power * abs(h[i][i]))
        pivot = max(range(n - 1), key=weighted.__getitem__)

        y[pivot], y[pivot + 1] = y[pivot + 1], y[pivot]
        h[pivot], h[pivot + 1] = h[pivot + 1], h[pivot]
        a[pivot], a[pivot + 1] = a[pivot + 1], a[pivot]
        for row in range(n):
            b[row][pivot], b[row][pivot + 1] = b[row][pivot + 1], b[row][pivot]

        if pivot <= n - 3:
            rotation_norm = _sqrt_fixed(
                (h[pivot][pivot] ** 2 + h[pivot][pivot + 1] ** 2) >> precision,
                precision,
            )
            if rotation_norm == 0:
                return PSLQIteration(
                    None,
                    iteration,
                    "PRECISION_EXHAUSTED",
                    _fixed_error_bits(best_error or 0, precision),
                    norm_lower_bound,
                    budget.coefficient_cap,
                )
            cosine = (h[pivot][pivot] << precision) // rotation_norm
            sine = (h[pivot][pivot + 1] << precision) // rotation_norm
            for row in range(pivot, n):
                left, right = h[row][pivot], h[row][pivot + 1]
                h[row][pivot] = (cosine * left + sine * right) >> precision
                h[row][pivot + 1] = (-sine * left + cosine * right) >> precision

        for i in range(pivot + 1, n):
            for j in range(min(i - 1, pivot + 1), -1, -1):
                if not reduce_row(i, j):
                    break

        best_error = min(abs(value) for value in y)
        for column, error in enumerate(y):
            if abs(error) >= tolerance:
                continue
            raw = [
                _round_fixed(b[row][column], precision) >> precision for row in range(n)
            ]
            relation = _primitive_relation_low_to_high(raw)
            if relation is None:
                continue
            if max(abs(value) for value in relation) <= budget.coefficient_cap:
                return PSLQIteration(
                    relation,
                    iteration,
                    "RELATION_FOUND",
                    _fixed_error_bits(abs(error), precision),
                    norm_lower_bound,
                    budget.coefficient_cap,
                )

        largest_h = max(abs(value) for row in h for value in row)
        if largest_h:
            norm_lower_bound = ((1 << (2 * precision)) // largest_h) >> precision
            norm_lower_bound //= 100
            if norm_lower_bound >= budget.coefficient_cap:
                return PSLQIteration(
                    None,
                    iteration,
                    "COEFFICIENT_BOUND_EXHAUSTED",
                    _fixed_error_bits(best_error, precision),
                    norm_lower_bound,
                    budget.coefficient_cap,
                )

    return PSLQIteration(
        None,
        budget.max_steps,
        "ITERATION_BUDGET_EXHAUSTED",
        _fixed_error_bits(best_error or 0, precision),
        norm_lower_bound,
        budget.coefficient_cap,
    )


def _polynomial_residual(
    coefficients_high_to_low: Sequence[int], value: object, *, precision_bits: int
) -> tuple[object, object]:
    with mp.workprec(precision_bits + 64):
        numeric = mp.mpf(value)
        total = mp.mpf("0")
        scale = mp.mpf("0")
        magnitude = abs(numeric)
        for coefficient in coefficients_high_to_low:
            total = total * numeric + coefficient
            scale = scale * magnitude + abs(coefficient)
        return abs(total), abs(total) / max(mp.mpf("1"), scale)


def _mp_text(value: object, *, precision_bits: int) -> str:
    digits = max(50, math.ceil(precision_bits * math.log10(2)) + 8)
    with mp.workprec(precision_bits + 64):
        return mp.nstr(value, n=digits, strip_zeros=False)


def _rational_text(value: object) -> str:
    numerator, denominator = int(value.p), int(value.q)
    return str(numerator) if denominator == 1 else f"{numerator}/{denominator}"


def _factor_and_isolate(
    relation_low_to_high: Sequence[int],
    value: object,
    *,
    precision_bits: int,
    residual_bits: int,
) -> dict[str, object] | None:
    """Select the unique exact irreducible factor near ``value``."""

    import sympy as sp

    x = sp.Symbol("x")
    raw_high = list(reversed(relation_low_to_high))
    raw = sp.Poly.from_list(raw_high, gens=x, domain=sp.ZZ)
    raw_absolute, raw_relative = _polynomial_residual(
        raw_high,
        value,
        precision_bits=precision_bits,
    )
    content, factors = sp.factor_list(raw)
    raw_square_free = all(exponent == 1 for _factor, exponent in factors)
    threshold = mp.power(2, -residual_bits)
    matches: list[tuple[object, int, object, object]] = []
    for factor, exponent in factors:
        coefficients = [int(coefficient) for coefficient in factor.all_coeffs()]
        absolute, relative = _polynomial_residual(
            coefficients,
            value,
            precision_bits=precision_bits,
        )
        if relative <= threshold:
            matches.append((factor, exponent, absolute, relative))
    if len(matches) != 1:
        return None

    factor, exponent, absolute, relative = matches[0]
    if not factor.is_sqf or not factor.is_irreducible:
        return None
    isolation_bits = min(512, max(256, residual_bits - 64))
    intervals = factor.intervals(eps=sp.Rational(1, 1 << isolation_bits))
    with mp.workprec(precision_bits + 64):
        numeric = mp.mpf(value)
        selected: list[tuple[object, object, int]] = []
        slack = mp.power(2, -residual_bits) * max(mp.mpf("1"), abs(numeric))
        for root_index, ((left, right), multiplicity) in enumerate(intervals):
            left_mp = mp.mpf(int(left.p)) / int(left.q)
            right_mp = mp.mpf(int(right.p)) / int(right.q)
            if left_mp - slack <= numeric <= right_mp + slack:
                selected.append((root_index, left, right, int(multiplicity)))
    if len(selected) != 1:
        return None
    root_index, left, right, multiplicity = selected[0]
    if multiplicity != 1:
        return None
    coefficients = tuple(int(coefficient) for coefficient in factor.all_coeffs())
    return {
        "raw_relation_high_to_low": raw_high,
        "raw_relation_content": int(content),
        "raw_relation_square_free": raw_square_free,
        "raw_relation_absolute_residual": _mp_text(
            raw_absolute, precision_bits=precision_bits
        ),
        "raw_relation_normalized_residual": _mp_text(
            raw_relative, precision_bits=precision_bits
        ),
        "selected_factor_exponent_in_relation": int(exponent),
        "minimal_polynomial_high_to_low": list(coefficients),
        "minimal_polynomial_primitive": int(sp.gcd_list(coefficients)) == 1,
        "minimal_polynomial_square_free": bool(factor.is_sqf),
        "minimal_polynomial_irreducible_over_Q": bool(factor.is_irreducible),
        "absolute_residual": _mp_text(absolute, precision_bits=precision_bits),
        "normalized_residual": _mp_text(relative, precision_bits=precision_bits),
        "isolating_interval": {
            "left": _rational_text(left),
            "right": _rational_text(right),
            "multiplicity": multiplicity,
            "real_root_index": root_index,
            "width_bits_at_least": isolation_bits,
        },
    }


def _search_value(
    value: object,
    *,
    precision_bits: int,
    tolerance_bits: int,
    max_degree: int,
    max_steps: int,
) -> tuple[PSLQIteration | None, PSLQBudget | None]:
    with mp.workprec(precision_bits + 64):
        numeric = mp.mpf(value)
        zero_threshold = mp.power(2, -tolerance_bits)
        if abs(numeric) <= zero_threshold:
            budget = make_budget(
                precision_bits=precision_bits,
                degree=1,
                max_steps=max_steps,
                tolerance_bits=tolerance_bits,
            )
            return (
                PSLQIteration(
                    (0, 1),
                    0,
                    "ZERO_RELATION",
                    None,
                    None,
                    budget.coefficient_cap,
                ),
                budget,
            )
        powers = [mp.mpf("1")]
        for _degree in range(max_degree):
            powers.append(powers[-1] * numeric)
        for degree in range(1, max_degree + 1):
            budget = make_budget(
                precision_bits=precision_bits,
                degree=degree,
                max_steps=max_steps,
                tolerance_bits=tolerance_bits,
            )
            result = pslq_fixed(powers[: degree + 1], budget=budget)
            if result.relation_low_to_high is not None:
                return result, budget
    return None, None


def _lane_digest(text: str, bits: int) -> str:
    payload = json.dumps(
        {"bits": bits, "numeric_text": text},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def recognize_algebraic(
    proposal_text: str,
    confirmation_text: str,
    *,
    proposal_bits: int = MIN_PROPOSAL_BITS,
    confirmation_bits: int = MIN_CONFIRMATION_BITS,
    max_degree: int = MAX_DEGREE,
    max_steps: int = 20_000,
    relation_tolerance_bits: int | None = None,
) -> dict[str, object]:
    """Propose at >=768 bits and independently rerun/verify at >=1024 bits."""

    if proposal_bits < MIN_PROPOSAL_BITS:
        raise RecognitionError(
            f"proposal lane must be at least {MIN_PROPOSAL_BITS} bits"
        )
    if confirmation_bits < MIN_CONFIRMATION_BITS:
        raise RecognitionError(
            f"confirmation lane must be at least {MIN_CONFIRMATION_BITS} bits"
        )
    if not 1 <= max_degree <= MAX_DEGREE:
        raise RecognitionError(f"max_degree must be in 1..{MAX_DEGREE}")
    if relation_tolerance_bits is None:
        # Preserve the reusable recognizer's historical default.  A caller
        # whose numerical-success contract has an explicit error gate can
        # supply one common tolerance for both independent lanes.
        proposal_tolerance_bits = min(448, proposal_bits - 256)
        confirmation_tolerance_bits = min(600, confirmation_bits - 256)
    else:
        if (
            not isinstance(relation_tolerance_bits, int)
            or isinstance(relation_tolerance_bits, bool)
            or relation_tolerance_bits < 128
            or relation_tolerance_bits >= min(proposal_bits, confirmation_bits)
        ):
            raise RecognitionError(
                "relation_tolerance_bits must be an integer in the shared lane range"
            )
        proposal_tolerance_bits = relation_tolerance_bits
        confirmation_tolerance_bits = relation_tolerance_bits
    proposal, proposal_budget = _search_value(
        proposal_text,
        precision_bits=proposal_bits,
        tolerance_bits=proposal_tolerance_bits,
        max_degree=max_degree,
        max_steps=max_steps,
    )
    confirmation, confirmation_budget = _search_value(
        confirmation_text,
        precision_bits=confirmation_bits,
        tolerance_bits=confirmation_tolerance_bits,
        max_degree=max_degree,
        max_steps=max_steps,
    )
    base = {
        "schema_version": "geotarget.owned-pslq-recognition/v1",
        "proposal_input_sha256": _lane_digest(proposal_text, proposal_bits),
        "confirmation_input_sha256": _lane_digest(confirmation_text, confirmation_bits),
        "proposal_bits": proposal_bits,
        "confirmation_bits": confirmation_bits,
        "max_degree": max_degree,
        "max_steps_per_degree": max_steps,
        "proposal": None if proposal is None else asdict(proposal),
        "confirmation": None if confirmation is None else asdict(confirmation),
        "proposal_budget": None if proposal_budget is None else asdict(proposal_budget),
        "confirmation_budget": (
            None if confirmation_budget is None else asdict(confirmation_budget)
        ),
        "owned_integer_relation_iteration": True,
        "dependency_pslq_called": False,
    }
    if proposal is None or confirmation is None:
        return {**base, "status": "NO_RELATION", "descriptor": None}
    if (
        proposal.relation_low_to_high is None
        or confirmation.relation_low_to_high is None
    ):
        return {**base, "status": "NO_RELATION", "descriptor": None}
    proposal_factor = _factor_and_isolate(
        proposal.relation_low_to_high,
        proposal_text,
        precision_bits=proposal_bits,
        residual_bits=proposal_tolerance_bits,
    )
    confirmation_factor = _factor_and_isolate(
        confirmation.relation_low_to_high,
        confirmation_text,
        precision_bits=confirmation_bits,
        residual_bits=confirmation_tolerance_bits,
    )
    if proposal_factor is None or confirmation_factor is None:
        return {**base, "status": "EXACT_FACTOR_UNVERIFIED", "descriptor": None}
    if (
        proposal_factor["minimal_polynomial_high_to_low"]
        != confirmation_factor["minimal_polynomial_high_to_low"]
        or proposal_factor["isolating_interval"]["real_root_index"]
        != confirmation_factor["isolating_interval"]["real_root_index"]
    ):
        return {
            **base,
            "status": "INDEPENDENT_LANE_DISAGREEMENT",
            "proposal_factor": proposal_factor,
            "confirmation_factor": confirmation_factor,
            "descriptor": None,
        }
    return {
        **base,
        "status": "ALGEBRAIC_RELATION_VERIFIED",
        "proposal_factor": proposal_factor,
        "confirmation_factor": confirmation_factor,
        "descriptor": {
            "minimal_polynomial_high_to_low": confirmation_factor[
                "minimal_polynomial_high_to_low"
            ],
            "isolating_interval": confirmation_factor["isolating_interval"],
        },
    }
