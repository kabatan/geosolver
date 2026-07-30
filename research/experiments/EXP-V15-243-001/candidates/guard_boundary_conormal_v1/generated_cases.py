"""Prospective generated controls for guard-boundary conormal sampling."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from candidate import Observation, Problem


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    role: str
    seed: int
    problem: Problem
    starts: list[np.ndarray]
    truth: frozenset[int]

    def descriptor(self, point: np.ndarray) -> int:
        return 1 if float(point[0]) > 0.0 else -1


def _equation(family: str, point: np.ndarray) -> tuple[float, np.ndarray]:
    x, y = map(float, point)
    if family == "twin_circles":
        center, radius = 1.4, 0.65
        right = (x - center) ** 2 + y * y - radius * radius
        left = (x + center) ** 2 + y * y - radius * radius
        grad_right = np.array([2.0 * (x - center), 2.0 * y])
        grad_left = np.array([2.0 * (x + center), 2.0 * y])
        return right * left, left * grad_right + right * grad_left
    if family == "cassini_ovals":
        a, level = 1.25, 0.9**4
        left = (x - a) ** 2 + y * y
        right = (x + a) ** 2 + y * y
        grad_left = np.array([2.0 * (x - a), 2.0 * y])
        grad_right = np.array([2.0 * (x + a), 2.0 * y])
        return left * right - level, right * grad_left + left * grad_right
    if family == "clipped_hyperbola":
        return x * y - 1.0, np.array([y, x])
    raise KeyError(family)


def _starts(family: str, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    if family == "twin_circles":
        angles = np.array([2.45, 2.7, -2.55, 2.25]) + rng.normal(0.0, 0.015, 4)
        return [
            np.array([1.4 + 0.65 * math.cos(angle), 0.65 * math.sin(angle)])
            for angle in angles
        ]
    if family == "cassini_ovals":
        return [
            np.array([1.0, value]) + rng.normal(0.0, 0.012, 2)
            for value in (0.10, 0.22, -0.16, 0.31)
        ]
    if family == "clipped_hyperbola":
        xs = np.array([1.05, 1.2, 1.45, 1.7]) + rng.normal(0.0, 0.015, 4)
        return [np.array([value, 1.0 / value]) for value in xs]
    raise KeyError(family)


def make_case(family: str, role: str, seed: int) -> GeneratedCase:
    lower = np.full(2, -4.0)
    upper = np.full(2, 4.0)

    def in_bounds(point: np.ndarray) -> bool:
        point = np.asarray(point, dtype=float)
        return bool(
            point.shape == (2,)
            and np.all(np.isfinite(point))
            and np.all(point >= lower)
            and np.all(point <= upper)
        )

    def guard(point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x, y = map(float, point)
        if role == "semantic_near_miss":
            return np.array([x]), np.array([[1.0, 0.0]])
        radius_squared = {
            "twin_circles": 1.5**2,
            "cassini_ovals": 1.35**2,
            "clipped_hyperbola": 2.2**2,
        }[family]
        return (
            np.array([radius_squared - x * x - y * y]),
            np.array([[-2.0 * x, -2.0 * y]]),
        )

    def observe(point: np.ndarray) -> Observation:
        value, gradient = _equation(family, np.asarray(point, dtype=float))
        residual = np.array([value])
        jacobian = gradient.reshape(1, 2)
        if role == "inconsistent_negative":
            residual = np.array([value, 0.25])
            jacobian = np.vstack([gradient, np.zeros(2)])
        margins, gradients = guard(point)
        return Observation(residual, jacobian, margins, gradients)

    def replay(point: np.ndarray) -> bool:
        if not in_bounds(point):
            return False
        value, _ = _equation(family, np.asarray(point, dtype=float))
        margins, _ = guard(point)
        return bool(
            role != "inconsistent_negative"
            and abs(value) <= 2e-7
            and np.all(margins > 1e-7)
        )

    problem = Problem(
        center=np.zeros(2),
        chart=np.diag([2.0, 2.0]),
        lower=lower,
        upper=upper,
        observe=observe,
        replay=replay,
        in_bounds=in_bounds,
    )
    truth = (
        frozenset((-1, 1))
        if role == "positive"
        else frozenset((1,))
        if role == "semantic_near_miss"
        else frozenset()
    )
    return GeneratedCase(family, role, seed, problem, _starts(family, seed), truth)


def generated_suite(seeds: range = range(8)) -> list[GeneratedCase]:
    return [
        make_case(family, role, seed)
        for family in ("twin_circles", "cassini_ovals", "clipped_hyperbola")
        for role in ("positive", "inconsistent_negative", "semantic_near_miss")
        for seed in seeds
    ]
