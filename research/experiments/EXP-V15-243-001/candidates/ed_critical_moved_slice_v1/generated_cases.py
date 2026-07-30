"""Prospective generated systems for ED-critical / moved-slice D0."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from candidate import Observation, Problem


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    role: str
    seed: int
    problem: Problem
    starts: list[np.ndarray]


def _build(
    family: str,
    role: str,
    seed: int,
    residual_jacobian,
    dimension: int,
    valid_predicate,
    ed_capable: bool = True,
) -> GeneratedCase:
    rng = np.random.default_rng(70_000 + 97 * seed + len(family))
    center = np.zeros(dimension)
    widths = np.ones(dimension) * 1.45
    if family == "scaled_space_curve":
        widths = np.array([1e-2, 2.0, 2e2])
    chart = np.diag(widths)
    lower, upper = -widths, widths

    def observe(point: np.ndarray) -> Observation:
        residual, jacobian = residual_jacobian(point / widths)
        jacobian = jacobian @ np.diag(1.0 / widths)
        if role == "negative":
            residual = np.concatenate([residual, np.array([0.2])])
            jacobian = np.vstack([jacobian, np.zeros((1, dimension))])
        return Observation(residual, jacobian, True)

    def in_bounds(point: np.ndarray) -> bool:
        z = point / widths
        return bool(np.all(np.abs(z) < 0.999999))

    def replay(point: np.ndarray) -> bool:
        residual, _ = residual_jacobian(point / widths)
        numeric = np.linalg.norm(residual, ord=np.inf) <= 2e-8
        if role == "positive":
            return bool(numeric and in_bounds(point) and valid_predicate(point / widths))
        return False

    starts = []
    for ordinal in range(4):
        z = np.zeros(dimension)
        z[0] = rng.uniform(-0.88, -0.45)
        if dimension > 1:
            z[1] = rng.uniform(-0.72, -0.12)
        if dimension > 2:
            z[2:] = rng.uniform(-0.35, 0.35, size=dimension - 2)
        z += rng.normal(scale=0.015, size=dimension)
        starts.append(widths * np.clip(z, -0.92, 0.92))

    return GeneratedCase(
        family,
        role,
        seed,
        Problem(center, chart, lower, upper, observe, replay, in_bounds, ed_capable),
        starts,
    )


def make_case(family: str, role: str, seed: int) -> GeneratedCase:
    if family == "curved_circle":
        def residual_jacobian(z):
            return np.array([z[0] ** 2 + z[1] ** 2 - 0.64]), np.array([[2 * z[0], 2 * z[1]]])

        return _build(family, role, seed, residual_jacobian, 2, lambda z: z[0] > 0.55)

    if family == "disconnected_ovals":
        def residual_jacobian(z):
            left = (z[0] + 0.52) ** 2 + 1.4 * z[1] ** 2 - 0.10
            right = (z[0] - 0.52) ** 2 + 1.4 * z[1] ** 2 - 0.10
            dl = np.array([2 * (z[0] + 0.52), 2.8 * z[1]])
            dr = np.array([2 * (z[0] - 0.52), 2.8 * z[1]])
            return np.array([left * right]), np.array([right * dl + left * dr])

        return _build(family, role, seed, residual_jacobian, 2, lambda z: z[0] > 0.25)

    if family == "scaled_space_curve":
        def residual_jacobian(z):
            residual = np.array([z[0] ** 2 + z[1] ** 2 - 0.49, z[2] - 0.3 * z[0] * z[1]])
            jac = np.array([[2 * z[0], 2 * z[1], 0.0], [-0.3 * z[1], -0.3 * z[0], 1.0]])
            return residual, jac

        return _build(family, role, seed, residual_jacobian, 3, lambda z: z[0] > 0.42 and z[1] > -0.2)

    if family == "nonpolynomial_sheet":
        def residual_jacobian(z):
            residual = np.array([np.sin(1.3 * z[0]) + 0.45 * z[1]])
            jac = np.array([[1.3 * np.cos(1.3 * z[0]), 0.45]])
            return residual, jac

        return _build(family, role, seed, residual_jacobian, 2, lambda z: z[0] > 0.35)

    raise ValueError(family)


def make_isolated_counter(seed: int) -> GeneratedCase:
    def residual_jacobian(z):
        return np.array([z[0] ** 2 + 0.25]), np.array([[2 * z[0]]])

    return _build("isolated_fullrank", "negative", seed, residual_jacobian, 1, lambda z: False)


def make_opaque_counter(seed: int) -> GeneratedCase:
    def residual_jacobian(z):
        return np.array([np.sin(z[0])]), np.array([[np.cos(z[0])]])

    return _build("opaque_fallback", "negative", seed, residual_jacobian, 1, lambda z: False, ed_capable=False)


def transformed_case(case: GeneratedCase, coordinate_map: np.ndarray, row_map: np.ndarray) -> GeneratedCase:
    original = case.problem
    t = np.asarray(coordinate_map, dtype=float)
    t_inv = np.linalg.inv(t)
    rmap = np.asarray(row_map, dtype=float)
    center = t @ original.center
    chart = t @ original.chart
    corners = []
    for bits in np.ndindex(*(2,) * original.center.size):
        corner = np.where(np.asarray(bits), original.upper, original.lower)
        corners.append(t @ corner)
    corners = np.asarray(corners)
    lower, upper = corners.min(axis=0), corners.max(axis=0)

    def observe(point: np.ndarray) -> Observation:
        obs = original.observe(t_inv @ point)
        return Observation(rmap @ obs.residual, rmap @ obs.jacobian @ t_inv, obs.semantic_valid)

    def replay(point: np.ndarray) -> bool:
        return original.replay(t_inv @ point)

    def in_bounds(point: np.ndarray) -> bool:
        return original.in_bounds(t_inv @ point)

    return GeneratedCase(
        case.family,
        case.role,
        case.seed,
        Problem(center, chart, lower, upper, observe, replay, in_bounds, original.ed_capable),
        [t @ point for point in case.starts],
    )
