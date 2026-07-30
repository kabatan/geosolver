"""Prospective breadth fixtures for guard-directed equation swapping.

These families are intentionally disjoint from the frozen graph/circle/cubic
carrier panel.  They exercise transcendental carriers, a curved strict guard,
and a four-dimensional non-polynomial chain.  Labels live only in this
assessor module and never enter the candidate API.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import numpy as np

from candidate import Observation


Array = np.ndarray


@dataclass(frozen=True, slots=True)
class BreadthCase:
    family: str
    role: str
    seed: int
    evaluator: Callable[[Array], Observation]
    start: Array
    scale: Array
    lower: Array
    upper: Array
    expected_gain: bool
    near_miss: str | None


def _orthogonal(dimension: int, seed: int) -> Array:
    generator = np.random.default_rng(seed)
    raw = generator.normal(size=(dimension, dimension))
    q, r = np.linalg.qr(raw)
    signs = np.where(np.diag(r) < 0.0, -1.0, 1.0)
    return q * signs[None, :]


def _near_mode(seed: int, role: str) -> str | None:
    if role != "near_miss":
        return None
    return ("singular_entry", "unproven_margin", "opaque_branch")[seed % 3]


def _box(dimension: int, unit: float) -> tuple[Array, Array, Array]:
    return (
        np.full(dimension, unit, dtype=float),
        np.full(dimension, -math.inf, dtype=float),
        np.full(dimension, math.inf, dtype=float),
    )


def _mapped_jacobian(local_jacobian: Array, frame: Array, unit: float) -> Array:
    return local_jacobian @ frame.T / unit


def transcendental_helix(seed: int, role: str) -> BreadthCase:
    """A helix carrier closed by a two-root scalar equation.

    The second smooth margin is an already-interior decoy.  It verifies that
    the candidate chooses among anonymous violated margins rather than routing
    on a fixed guard ordinal.
    """

    frame = _orthogonal(3, 31000 + seed)
    unit = 0.7 + 0.025 * (seed % 7)
    shift = np.asarray([0.05 * ((seed % 3) - 1), -0.08, 0.11])
    a = 0.56 + 0.012 * (seed % 7)
    b = 1.03 + 0.015 * (seed % 8)
    omega = 0.72 + 0.025 * (seed % 6)
    phase = -0.21 + 0.03 * (seed % 5)
    threshold = 0.08 + 0.008 * (seed % 4)
    near = _near_mode(seed, role)
    if role == "negative":
        threshold = b + 0.24

    def carrier(u: float) -> tuple[float, float]:
        return math.sin(omega * u + phase), math.cos(omega * u - phase)

    v0, w0 = carrier(-a)
    local_start = np.asarray([-a, v0, w0])
    start = shift + unit * (frame @ local_start)

    def evaluator(point: Array) -> Observation:
        u, v, w = frame.T @ ((np.asarray(point, dtype=float) - shift) / unit)
        f0 = v - math.sin(omega * u + phase)
        f1 = w - math.cos(omega * u - phase)
        if near == "singular_entry":
            f2 = (u + a) ** 2 * (u - b)
            df2 = (u + a) * (3.0 * u + a - 2.0 * b)
        else:
            f2 = (u + a) * (u - b)
            df2 = 2.0 * u + a - b
        local_j = np.asarray(
            [
                [-omega * math.cos(omega * u + phase), 1.0, 0.0],
                [omega * math.sin(omega * u - phase), 0.0, 1.0],
                [df2, 0.0, 0.0],
            ]
        )
        main_margin = u - threshold
        decoy_margin = 2.0 + 0.05 * u
        provenance = near != "unproven_margin"
        opaque_ok = near != "opaque_branch"
        return Observation(
            np.asarray([f0, f1, f2]),
            np.asarray([main_margin, decoy_margin]),
            True,
            bool(main_margin > 1.0e-11 and decoy_margin > 0.0 and opaque_ok),
            _mapped_jacobian(local_j, frame, unit),
            _mapped_jacobian(
                np.asarray([[1.0, 0.0, 0.0], [0.05, 0.0, 0.0]]),
                frame,
                unit,
            ),
            np.asarray([provenance, True]),
        )

    scale, lower, upper = _box(3, unit)
    return BreadthCase(
        "transcendental_helix",
        role,
        seed,
        evaluator,
        start,
        scale,
        lower,
        upper,
        role == "positive",
        near,
    )


def curved_guard_rational_carrier(seed: int, role: str) -> BreadthCase:
    """Two negative roots separated by the curved guard ``u^2-q^2>0``."""

    frame = _orthogonal(2, 32000 + seed)
    unit = 0.78 + 0.03 * (seed % 6)
    shift = np.asarray([0.13, -0.06 * ((seed % 3) - 1)])
    a = 0.31 + 0.009 * (seed % 7)
    b = 1.12 + 0.014 * (seed % 8)
    q = 0.72 + 0.01 * (seed % 5)
    tilt = -0.14 + 0.018 * (seed % 6)
    near = _near_mode(seed, role)
    if role == "negative":
        q = b + 0.22

    def carrier(u: float) -> float:
        return 0.34 + tilt * u + 1.0 / (1.0 + u * u)

    local_start = np.asarray([-a, carrier(-a)])
    start = shift + unit * (frame @ local_start)

    def evaluator(point: Array) -> Observation:
        u, v = frame.T @ ((np.asarray(point, dtype=float) - shift) / unit)
        f0 = v - carrier(u)
        if near == "singular_entry":
            f1 = (u + a) ** 2 * (u + b)
            df1 = (u + a) * (3.0 * u + 2.0 * b - a)
        else:
            f1 = (u + a) * (u + b)
            df1 = 2.0 * u + a + b
        carrier_derivative = tilt - 2.0 * u / (1.0 + u * u) ** 2
        local_j = np.asarray([[-carrier_derivative, 1.0], [df1, 0.0]])
        margin = u * u - q * q
        provenance = near != "unproven_margin"
        opaque_ok = near != "opaque_branch"
        return Observation(
            np.asarray([f0, f1]),
            np.asarray([margin]),
            True,
            bool(margin > 1.0e-11 and opaque_ok),
            _mapped_jacobian(local_j, frame, unit),
            _mapped_jacobian(np.asarray([[2.0 * u, 0.0]]), frame, unit),
            np.asarray([provenance]),
        )

    scale, lower, upper = _box(2, unit)
    return BreadthCase(
        "curved_guard_rational_carrier",
        role,
        seed,
        evaluator,
        start,
        scale,
        lower,
        upper,
        role == "positive",
        near,
    )


def exponential_four_chain(seed: int, role: str) -> BreadthCase:
    """A rotated four-dimensional non-polynomial triangular carrier."""

    frame = _orthogonal(4, 33000 + seed)
    unit = 0.62 + 0.028 * (seed % 8)
    shift = np.asarray([0.09, -0.12, 0.04, 0.07])
    a = 0.62 + 0.011 * (seed % 7)
    b = 0.96 + 0.013 * (seed % 9)
    kappa = 0.38 + 0.018 * (seed % 5)
    eta = 0.22 + 0.012 * (seed % 6)
    threshold = 1.04 + 0.01 * (seed % 4)
    near = _near_mode(seed, role)
    if role == "negative":
        threshold = math.exp(kappa * b) + 0.20

    def carrier(u: float) -> tuple[float, float, float]:
        v = math.exp(eta * u)
        w = math.sin(0.65 * u) + 0.18 * v
        z = 0.24 * u * w + math.cos(0.31 * u)
        return v, w, z

    v0, w0, z0 = carrier(-a)
    local_start = np.asarray([-a, v0, w0, z0])
    start = shift + unit * (frame @ local_start)

    def evaluator(point: Array) -> Observation:
        u, v, w, z = frame.T @ ((np.asarray(point, dtype=float) - shift) / unit)
        f0 = v - math.exp(eta * u)
        f1 = w - math.sin(0.65 * u) - 0.18 * v
        f2 = z - 0.24 * u * w - math.cos(0.31 * u)
        if near == "singular_entry":
            f3 = (u + a) ** 2 * (u - b)
            df3 = (u + a) * (3.0 * u + a - 2.0 * b)
        else:
            f3 = (u + a) * (u - b)
            df3 = 2.0 * u + a - b
        local_j = np.asarray(
            [
                [-eta * math.exp(eta * u), 1.0, 0.0, 0.0],
                [-0.65 * math.cos(0.65 * u), -0.18, 1.0, 0.0],
                [-0.24 * w + 0.31 * math.sin(0.31 * u), 0.0, -0.24 * u, 1.0],
                [df3, 0.0, 0.0, 0.0],
            ]
        )
        margin = math.exp(kappa * u) - threshold
        provenance = near != "unproven_margin"
        opaque_ok = near != "opaque_branch"
        local_margin_j = np.asarray(
            [[kappa * math.exp(kappa * u), 0.0, 0.0, 0.0]]
        )
        return Observation(
            np.asarray([f0, f1, f2, f3]),
            np.asarray([margin]),
            True,
            bool(margin > 1.0e-11 and opaque_ok),
            _mapped_jacobian(local_j, frame, unit),
            _mapped_jacobian(local_margin_j, frame, unit),
            np.asarray([provenance]),
        )

    scale, lower, upper = _box(4, unit)
    return BreadthCase(
        "exponential_four_chain",
        role,
        seed,
        evaluator,
        start,
        scale,
        lower,
        upper,
        role == "positive",
        near,
    )


def prospective_cases(seeds: int = 12) -> list[BreadthCase]:
    factories = (
        transcendental_helix,
        curved_guard_rational_carrier,
        exponential_four_chain,
    )
    return [
        factory(seed, role)
        for factory in factories
        for role in ("positive", "negative", "near_miss")
        for seed in range(seeds)
    ]
