"""Disposable nullspace low-height witness transport D0."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import random
from typing import Callable, Sequence


Vector = tuple[float, float]
Residual = Callable[[Vector], tuple[float, ...]]
Guard = Callable[[Vector], bool]


@dataclass(frozen=True)
class System:
    residual: Residual
    guard: Guard
    bounds: tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class RunResult:
    activated: bool
    rank_ratio: float
    free_coordinate: int | None
    accepted: tuple[Vector, ...]
    shared_baseline_signature: str
    shared_baseline_accept_count: int
    side_accept_count: int
    fallback_used: bool
    invalid_accept_count: int


def _jacobian(system: System, point: Vector) -> list[tuple[float, float]]:
    base = system.residual(point)
    columns: list[list[float]] = []
    for coordinate in range(2):
        step = 1.0e-6 * max(1.0, abs(point[coordinate]))
        shifted = list(point)
        shifted[coordinate] += step
        value = system.residual((shifted[0], shifted[1]))
        columns.append([(right - left) / step for left, right in zip(base, value, strict=True)])
    return list(zip(columns[0], columns[1], strict=True))


def _stable_nullspace(system: System, point: Vector) -> tuple[Vector | None, float]:
    jacobian = _jacobian(system, point)
    a = sum(row[0] * row[0] for row in jacobian)
    b = sum(row[0] * row[1] for row in jacobian)
    c = sum(row[1] * row[1] for row in jacobian)
    discriminant = math.sqrt(max(0.0, (a - c) ** 2 + 4.0 * b * b))
    small = max(0.0, 0.5 * (a + c - discriminant))
    large = max(0.0, 0.5 * (a + c + discriminant))
    ratio = small / large if large > 0.0 else math.inf
    if large <= 1.0e-14 or ratio > 1.0e-8:
        return None, ratio
    if abs(b) > 1.0e-18:
        vector = (b, small - a)
    elif a <= c:
        vector = (1.0, 0.0)
    else:
        vector = (0.0, 1.0)
    norm = math.hypot(*vector)
    if norm <= 1.0e-14:
        return None, ratio
    return (vector[0] / norm, vector[1] / norm), ratio


def _range_newton(
    system: System,
    initial: Vector,
    free_coordinate: int,
    free_value: float,
) -> Vector | None:
    dependent = 1 - free_coordinate
    point = [initial[0], initial[1]]
    point[free_coordinate] = free_value
    for _iteration in range(18):
        vector = (point[0], point[1])
        residual = system.residual(vector)
        if not all(math.isfinite(value) for value in residual):
            return None
        if max(abs(value) for value in residual) <= 1.0e-12:
            break
        jacobian = _jacobian(system, vector)
        column = [row[dependent] for row in jacobian]
        denominator = sum(value * value for value in column)
        if denominator <= 1.0e-18:
            return None
        step = -sum(left * right for left, right in zip(column, residual, strict=True)) / denominator
        if not math.isfinite(step):
            return None
        point[dependent] += max(-2.0, min(2.0, step))
    answer = (point[0], point[1])
    residual = system.residual(answer)
    if (
        not all(math.isfinite(value) for value in answer + residual)
        or max(abs(value) for value in residual) > 1.0e-10
        or not system.guard(answer)
    ):
        return None
    return answer


def _baseline_values(
    initial: float,
    bounds: tuple[float, float],
    rng: random.Random,
) -> list[float]:
    lower, upper = bounds
    width = upper - lower
    answer: list[float] = []
    for ordinal in range(100):
        if ordinal % 2 == 0:
            value = rng.uniform(lower, upper)
        else:
            u = min(1.0 - 1.0e-9, max(1.0e-9, rng.random()))
            value = initial + 0.15 * width * math.tan(math.pi * (u - 0.5))
            value = min(upper, max(lower, value))
        answer.append(value)
    return answer


def _low_height_values(
    initial: float, bounds: tuple[float, float]
) -> list[float]:
    lower, upper = bounds
    radius = max(0.1, 0.5 * (upper - lower))
    rationals: set[Fraction] = set()
    for denominator in range(1, 49):
        center = round(initial * denominator)
        for numerator in range(center - 2, center + 3):
            value = Fraction(numerator, denominator)
            numeric = float(value)
            if lower < numeric < upper and abs(numeric - initial) <= radius:
                rationals.add(value)
        rationals.add(Fraction(initial).limit_denominator(denominator))
    ordered = sorted(
        (
            value
            for value in rationals
            if lower < float(value) < upper and abs(float(value) - initial) <= radius
        ),
        key=lambda value: (
            value.denominator + abs(value.numerator),
            abs(float(value) - initial),
            value.denominator,
            value.numerator,
        ),
    )
    return [float(value) for value in ordered[:25]]


def _signature(points: Sequence[Vector]) -> str:
    payload = json.dumps(
        [[format(x, ".17g"), format(y, ".17g")] for x, y in points],
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run(
    system: System,
    initial: Vector,
    *,
    seed: int,
    candidate: bool,
) -> RunResult:
    nullspace, ratio = _stable_nullspace(system, initial)
    rng = random.Random(seed)
    if nullspace is None:
        free_coordinate = 0
        baseline = _baseline_values(initial[0], system.bounds[0], rng)
        shared_values = baseline[:75]
        side_values = baseline[75:]
        fallback = True
        activated = False
    else:
        free_coordinate = 0 if abs(nullspace[0]) >= abs(nullspace[1]) else 1
        baseline = _baseline_values(
            initial[free_coordinate], system.bounds[free_coordinate], rng
        )
        shared_values = baseline[:75]
        side_values = (
            _low_height_values(
                initial[free_coordinate], system.bounds[free_coordinate]
            )
            if candidate
            else baseline[75:]
        )
        fallback = False
        activated = candidate

    shared = tuple(
        point
        for value in shared_values
        if (point := _range_newton(system, initial, free_coordinate, value)) is not None
    )
    side = tuple(
        point
        for value in side_values
        if (point := _range_newton(system, initial, free_coordinate, value)) is not None
    )
    accepted = shared + side
    invalid = sum(
        max(abs(value) for value in system.residual(point)) > 1.0e-10
        or not system.guard(point)
        for point in accepted
    )
    return RunResult(
        activated=activated,
        rank_ratio=ratio,
        free_coordinate=free_coordinate,
        accepted=accepted,
        shared_baseline_signature=_signature(shared),
        shared_baseline_accept_count=len(shared),
        side_accept_count=len(side),
        fallback_used=fallback,
        invalid_accept_count=invalid,
    )


__all__ = ["RunResult", "System", "run"]
