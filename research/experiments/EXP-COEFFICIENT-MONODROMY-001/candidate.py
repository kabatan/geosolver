"""Small, source-safe coefficient-parameter monodromy proposal route."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from typing import Sequence

import numpy as np


POLICY_ID = "small_exact_polynomial_coefficient_monodromy_d0"
BASELINE_FLOOR = 0.75
MAX_DEGREE = 8
MAX_COEFFICIENT_BITS = 96
UNKNOWN_STATUS = "UNKNOWN"


@dataclass(frozen=True)
class PolynomialSource:
    coefficients_high_to_low: tuple[Fraction, ...]
    square_free_certificate: bool
    lower_bound: Fraction | None = None
    upper_bound: Fraction | None = None

    @property
    def degree(self) -> int:
        return len(self.coefficients_high_to_low) - 1


@dataclass
class WorkBudget:
    cap: int
    used: int = 0

    def charge(self, amount: int = 1) -> bool:
        if amount < 0:
            raise ValueError("work charge cannot be negative")
        if self.used + amount > self.cap:
            return False
        self.used += amount
        return True


@dataclass(frozen=True)
class MonodromyResult:
    proposals: tuple[complex, ...]
    loops_attempted: int
    loops_completed: int
    tracker_failures: int
    charged_work: int
    eligible: bool
    reason: str
    status: str = UNKNOWN_STATUS


def split_work(total_work: int) -> tuple[int, int]:
    if total_work <= 0:
        raise ValueError("total_work must be positive")
    baseline = math.ceil(BASELINE_FLOOR * total_work)
    return baseline, total_work - baseline


def eligible(source: PolynomialSource) -> tuple[bool, str]:
    coefficients = source.coefficients_high_to_low
    if not source.square_free_certificate:
        return False, "SQUARE_FREE_CERTIFICATE_MISSING"
    if source.degree < 2 or source.degree > MAX_DEGREE:
        return False, "DEGREE_OUT_OF_RANGE"
    if not coefficients or coefficients[0] == 0:
        return False, "LEADING_COEFFICIENT_ZERO"
    if any(
        max(abs(value.numerator).bit_length(), value.denominator.bit_length())
        > MAX_COEFFICIENT_BITS
        for value in coefficients
    ):
        return False, "COEFFICIENT_CAP_EXCEEDED"
    if (
        source.lower_bound is not None
        and source.upper_bound is not None
        and source.lower_bound >= source.upper_bound
    ):
        return False, "INVALID_SOURCE_BOUNDS"
    return True, "ELIGIBLE"


def _coefficients(source: PolynomialSource) -> np.ndarray:
    return np.asarray(
        [complex(float(value)) for value in source.coefficients_high_to_low],
        dtype=np.complex128,
    )


def _newton_at_parameter(
    coefficients: np.ndarray,
    start: complex,
    parameter: complex,
    budget: WorkBudget,
) -> complex | None:
    derivative = np.polyder(coefficients)
    value = complex(start)
    for _ in range(12):
        if not budget.charge(2):
            return None
        residual = complex(np.polyval(coefficients, value) - parameter)
        slope = complex(np.polyval(derivative, value))
        if not all(
            math.isfinite(component)
            for component in (residual.real, residual.imag, slope.real, slope.imag)
        ):
            return None
        if abs(residual) <= 2.0e-11:
            return value
        if abs(slope) <= 1.0e-13:
            return None
        step = residual / slope
        value -= step
        if abs(step) <= 2.0e-12 and abs(residual) <= 1.0e-8:
            return value
    return value if abs(np.polyval(coefficients, value) - parameter) <= 1.0e-8 else None


def _segment(left: complex, right: complex, steps: int) -> tuple[complex, ...]:
    return tuple(left + (right - left) * index / steps for index in range(1, steps + 1))


def _lollipop_path(
    critical_value: complex, other_values: Sequence[complex]
) -> tuple[complex, ...] | None:
    distance_to_base = abs(critical_value)
    if not math.isfinite(distance_to_base) or distance_to_base <= 1.0e-7:
        return None
    separations = [
        abs(critical_value - other)
        for other in other_values
        if abs(critical_value - other) > 1.0e-8
    ]
    separation = min(separations, default=distance_to_base)
    radius = 0.18 * min(distance_to_base, separation)
    if not math.isfinite(radius) or radius <= 1.0e-8:
        return None
    tangent = 1j * critical_value / distance_to_base
    circle_start = critical_value + radius * tangent
    phase = math.atan2(tangent.imag, tangent.real)
    outward = _segment(0.0j, circle_start, 12)
    circle = tuple(
        critical_value
        + radius * complex(
            math.cos(phase + 2.0 * math.pi * index / 48),
            math.sin(phase + 2.0 * math.pi * index / 48),
        )
        for index in range(1, 49)
    )
    inward = _segment(circle_start, 0.0j, 12)
    return (*outward, *circle, *inward)


def _track_loop(
    coefficients: np.ndarray,
    start: complex,
    path: Sequence[complex],
    budget: WorkBudget,
) -> complex | None:
    value = complex(start)
    for parameter in path:
        corrected = _newton_at_parameter(coefficients, value, parameter, budget)
        if corrected is None:
            return None
        value = corrected
    corrected = _newton_at_parameter(coefficients, value, 0.0j, budget)
    if corrected is None or abs(np.polyval(coefficients, corrected)) > 1.0e-7:
        return None
    return corrected


def discover(
    source: PolynomialSource,
    *,
    accepted_start: complex,
    side_work_cap: int,
) -> MonodromyResult:
    applicability, reason = eligible(source)
    if not applicability:
        return MonodromyResult((), 0, 0, 0, 0, False, reason)
    if side_work_cap <= 0:
        return MonodromyResult((), 0, 0, 0, 0, True, "NO_SIDE_WORK")

    coefficients = _coefficients(source)
    if abs(np.polyval(coefficients, accepted_start)) > 1.0e-8:
        return MonodromyResult((), 0, 0, 0, 0, True, "START_REPLAY_FAILED")
    derivative_roots = np.roots(np.polyder(coefficients))
    critical_values = tuple(
        complex(np.polyval(coefficients, value)) for value in derivative_roots
    )
    paths = tuple(
        path
        for index, critical in enumerate(critical_values)
        if (
            path := _lollipop_path(
                critical,
                (*critical_values[:index], *critical_values[index + 1 :]),
            )
        )
        is not None
    )
    budget = WorkBudget(side_work_cap)
    queue = [complex(accepted_start)]
    proposals = [complex(accepted_start)]
    attempted = 0
    completed = 0
    failures = 0
    cursor = 0
    while cursor < len(queue) and budget.used < budget.cap:
        anchor = queue[cursor]
        cursor += 1
        for path in paths:
            attempted += 1
            endpoint = _track_loop(coefficients, anchor, path, budget)
            if endpoint is None:
                failures += 1
                if budget.used >= budget.cap:
                    break
                continue
            completed += 1
            if any(abs(endpoint - prior) <= 1.0e-7 for prior in proposals):
                continue
            proposals.append(endpoint)
            queue.append(endpoint)
        if budget.used >= budget.cap:
            break
    return MonodromyResult(
        proposals=tuple(proposals),
        loops_attempted=attempted,
        loops_completed=completed,
        tracker_failures=failures,
        charged_work=budget.used,
        eligible=True,
        reason="PROPOSALS_ONLY",
    )
