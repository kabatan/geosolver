"""Generated positive, negative, and near-miss D0 cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    family: str
    residual: Callable[[Array], Array]
    jacobian: Callable[[Array], Array]
    start: Array
    exact_roots: tuple[Array, ...]
    smooth: bool = True
    guards: tuple[Callable[[Array], bool], ...] = ()


def rotation(angle: float) -> Array:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s], [s, c]], dtype=float)


def positive_cases() -> list[GeneratedCase]:
    cases: list[GeneratedCase] = []
    for index in range(8):
        start_value = 14.0 + 3.0 * index

        def residual(x: Array) -> Array:
            return np.array([x[0] ** 4 - 1.0])

        def jacobian(x: Array) -> Array:
            return np.array([[4.0 * x[0] ** 3]])

        cases.append(GeneratedCase(
            f"polynomial_growth_{index}", "polynomial_growth", residual, jacobian,
            np.array([start_value]), (np.array([-1.0]), np.array([1.0])),
        ))

    for index in range(8):
        Q = rotation(0.17 + 0.19 * index)
        start = Q @ np.array([14.0 + 2.0 * index, -(7.0 + index)])

        def residual(x: Array, Q: Array = Q) -> Array:
            u = Q.T @ x
            return Q @ (u**4 - 1.0)

        def jacobian(x: Array, Q: Array = Q) -> Array:
            u = Q.T @ x
            return Q @ np.diag(4.0 * u**3) @ Q.T

        roots = tuple(Q @ np.array([a, b]) for a in (-1.0, 1.0) for b in (-1.0, 1.0))
        cases.append(GeneratedCase(
            f"rotated_quartic_{index}", "rotated_quartic", residual, jacobian,
            start, roots,
        ))

    for index in range(8):
        Q = rotation(0.11 + 0.16 * index)
        root_u = np.array([0.4, -0.3])
        target = np.sinh(root_u)
        start = Q @ np.array([6.0 + 0.35 * index, -(4.8 + 0.25 * index)])

        def residual(x: Array, Q: Array = Q, target: Array = target) -> Array:
            return Q @ (np.sinh(Q.T @ x) - target)

        def jacobian(x: Array, Q: Array = Q) -> Array:
            return Q @ np.diag(np.cosh(Q.T @ x)) @ Q.T

        cases.append(GeneratedCase(
            f"rotated_sinh_{index}", "rotated_sinh", residual, jacobian,
            start, (Q @ root_u,),
        ))
    return cases


def negative_cases() -> list[GeneratedCase]:
    cases: list[GeneratedCase] = []
    for index in range(6):
        Q = rotation(0.2 + 0.2 * index)
        root = Q @ np.array([0.25, -0.75])

        def residual(x: Array, Q: Array = Q, root: Array = root) -> Array:
            return Q.T @ (x - root)

        def jacobian(x: Array, Q: Array = Q) -> Array:
            del x
            return Q.T

        cases.append(GeneratedCase(
            f"linear_control_{index}", "linear_control", residual, jacobian,
            Q @ np.array([3.0 + index, -2.0]), (root,),
        ))
    return cases


def near_miss_cases() -> list[GeneratedCase]:
    cases: list[GeneratedCase] = []
    for index in range(6):
        offset = 1.0 + 0.1 * index

        def residual(x: Array, offset: float = offset) -> Array:
            return np.array([x[0] - offset, x[0] + offset])

        def jacobian(x: Array) -> Array:
            del x
            return np.array([[1.0], [1.0]])

        cases.append(GeneratedCase(
            f"inconsistent_{index}", "inconsistent_near_miss", residual, jacobian,
            np.array([3.0 + index]), (),
        ))

    def branch_residual(x: Array) -> Array:
        return np.array([abs(x[0]) + 1.0])

    def branch_jacobian(x: Array) -> Array:
        return np.array([[1.0 if x[0] >= 0.0 else -1.0]])

    cases.append(GeneratedCase(
        "opaque_branch_near_miss", "unsupported_branch", branch_residual, branch_jacobian,
        np.array([2.0]), (), smooth=False,
    ))
    return cases

