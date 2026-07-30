"""Generated positive, negative, and near-miss systems for the D0 portal."""

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


def _signed_permutation(rng: np.random.Generator, n: int) -> np.ndarray:
    p = np.eye(n)[rng.permutation(n)]
    signs = rng.choice(np.array([-1.0, 1.0]), size=n)
    return np.diag(signs) @ p


def make_case(family: str, role: str, seed: int) -> GeneratedCase:
    rng = np.random.default_rng(10_000 + seed)
    n = {"sparse_chain": 5, "dense_coupled": 4, "strict_bound_scale": 3}[family]
    frame = _signed_permutation(rng, n)
    center = rng.uniform(-0.15, 0.15, size=n)
    widths = rng.uniform(1.4, 2.2, size=n)
    if family == "strict_bound_scale":
        widths *= np.array([1e-3, 1.0, 1e3])
    lower = center - widths / 2.0
    upper = center + widths / 2.0
    scale = widths / 2.0
    root_q = rng.uniform(0.12, 0.88, size=n)
    if family == "strict_bound_scale":
        root_q[0] = 0.015 + 0.002 * (seed % 4)
    root = lower + widths * root_q

    if family == "sparse_chain":
        coupling = np.eye(n)
        coupling[np.arange(1, n), np.arange(n - 1)] = -0.28
        steep = np.linspace(4.0, 8.0, n)
    elif family == "dense_coupled":
        raw = rng.normal(size=(n, n))
        coupling, _ = np.linalg.qr(raw)
        coupling = np.diag(np.linspace(0.35, 2.5, n)) @ coupling
        steep = np.linspace(3.0, 10.0, n)
    else:
        coupling = np.array([[1.0, 0.12, 0.0], [0.15, 1.0, -0.2], [0.0, 0.1, 1.0]])
        steep = np.array([18.0, 6.0, 3.0])

    def canonical(point: np.ndarray) -> np.ndarray:
        return frame @ ((point - center) / scale)

    root_y = canonical(root)

    def base_residual_jacobian(point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        y = canonical(point)
        delta = y - root_y
        t = np.tanh(steep * delta)
        residual = coupling @ t
        diagonal = steep * (1.0 - t * t)
        jac = coupling @ np.diag(diagonal) @ frame @ np.diag(1.0 / scale)
        return residual, jac

    def observe(point: np.ndarray) -> Observation:
        residual, jac = base_residual_jacobian(point)
        if role == "negative":
            residual = np.concatenate([residual, np.array([0.35])])
            jac = np.vstack([jac, np.zeros((1, n))])
        return Observation(residual, jac, semantic_valid=True)

    def replay(point: np.ndarray) -> bool:
        residual, _ = base_residual_jacobian(point)
        numeric = np.linalg.norm(residual, ord=np.inf) <= 1e-8
        if role == "negative":
            return False
        if role == "near_miss":
            return bool(numeric and point[0] > upper[0] + 1.0)
        return bool(numeric and np.all(point > lower) and np.all(point < upper))

    starts: list[np.ndarray] = []
    for ordinal in range(4):
        q = rng.uniform(0.08, 0.92, size=n)
        if ordinal == 3:
            q = np.where(root_q < 0.5, 0.90, 0.10)
            q += rng.normal(scale=0.012, size=n)
            q = np.clip(q, 0.04, 0.96)
        starts.append(lower + widths * q)

    return GeneratedCase(family, role, seed, Problem(lower, upper, scale, observe, replay), starts)


def transformed_case(
    case: GeneratedCase,
    coordinate_permutation: np.ndarray,
    residual_permutation: np.ndarray,
    residual_scale: np.ndarray,
) -> GeneratedCase:
    """Representation-only transform used by the metamorphic D0."""
    original = case.problem
    p = np.asarray(coordinate_permutation, dtype=float)
    rp = np.asarray(residual_permutation, dtype=float)
    rs = np.asarray(residual_scale, dtype=float)
    lower = p @ original.lower
    upper = p @ original.upper
    swap = lower > upper
    lower[swap], upper[swap] = upper[swap].copy(), lower[swap].copy()
    scale = np.abs(p) @ original.scale

    def to_original(point: np.ndarray) -> np.ndarray:
        return p.T @ point

    def observe(point: np.ndarray) -> Observation:
        obs = original.observe(to_original(point))
        residual = rs * (rp @ obs.residual)
        jac = np.diag(rs) @ rp @ obs.jacobian @ p.T
        return Observation(residual, jac, obs.semantic_valid)

    def replay(point: np.ndarray) -> bool:
        return original.replay(to_original(point))

    starts = [p @ x for x in case.starts]
    return GeneratedCase(
        case.family,
        case.role,
        case.seed,
        Problem(lower, upper, scale, observe, replay),
        starts,
    )
