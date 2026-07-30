"""Generated D0 families for the disposable noise-aware SQP polish."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


Array = np.ndarray
ResidualFactory = Callable[[], Callable[[Array], Array]]


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    family: str
    residual_factory: ResidualFactory
    start: Array
    exact_roots: tuple[Array, ...]
    variable_scale: Array
    smooth: bool = True


class AlternatingNoise:
    """Deterministic bounded measurement noise with reproducible repeats."""

    def __init__(self, base: Callable[[Array], Array], noise: Array) -> None:
        self.base = base
        self.noise = np.asarray(noise, dtype=float)
        self.calls = 0

    def __call__(self, x: Array) -> Array:
        # solve_attempt uses 10 probe calls followed by six charged trials for
        # two variables.  The paired FD signs leave a small, measurable
        # derivative discrepancy without turning it into a trusted direction.
        phase = self.calls % 16
        pattern = (1.0, -1.0, 1.0, 0.75, -1.0, -0.75, 1.0, 0.75, -1.0, -0.75)
        sign = pattern[phase] if phase < len(pattern) else 0.0
        self.calls += 1
        return np.asarray(self.base(x), dtype=float) + sign * self.noise


def rotation(angle: float) -> Array:
    cosine, sine = np.cos(angle), np.sin(angle)
    return np.array([[cosine, -sine], [sine, cosine]], dtype=float)


def positive_cases() -> list[GeneratedCase]:
    cases: list[GeneratedCase] = []
    for index in range(8):
        row = np.array([1.0, 1.7 + 0.1 * index, 0.8 + 0.05 * index])

        def factory(row: Array = row) -> Callable[[Array], Array]:
            return lambda x: row * np.array([x[0], 2.0 * x[0], x[1] ** 2 - 1.0])

        cases.append(GeneratedCase(
            f"redundant_quadratic_{index}",
            "redundant_constraints",
            factory,
            np.array([2.0 + 0.2 * index, 0.0]),
            (np.array([0.0, -1.0]), np.array([0.0, 1.0])),
            np.ones(2),
        ))

    for index in range(8):
        transform = rotation(0.13 + 0.17 * index)

        def factory(transform: Array = transform) -> Callable[[Array], Array]:
            def residual(x: Array) -> Array:
                u = transform.T @ x
                return np.array([u[0], 1.4 * u[0], u[1] ** 2 - 1.0])
            return residual

        roots = (
            transform @ np.array([0.0, -1.0]),
            transform @ np.array([0.0, 1.0]),
        )
        cases.append(GeneratedCase(
            f"rotated_plateau_{index}",
            "rotated_rank_plateau",
            factory,
            transform @ np.array([2.0 + 0.15 * index, 0.0]),
            roots,
            np.ones(2),
        ))

    for index in range(8):
        delta = 1e-3 * (index + 1)
        plateau = -0.5 * delta
        discriminant = np.sqrt(delta * delta + 4.0)
        roots = (
            np.array([0.0, (-delta - discriminant) / 2.0]),
            np.array([0.0, (-delta + discriminant) / 2.0]),
        )

        def factory(delta: float = delta) -> Callable[[Array], Array]:
            return lambda x: np.array([x[0], 1.8 * x[0], x[1] ** 2 + delta * x[1] - 1.0])

        cases.append(GeneratedCase(
            f"near_rank_plateau_{index}",
            "near_rank_deficient",
            factory,
            np.array([1.5 + 0.1 * index, plateau]),
            roots,
            np.ones(2),
        ))

    for index in range(8):
        amplitude = 1e-12 * (index + 1)

        def factory(amplitude: float = amplitude) -> Callable[[Array], Array]:
            def base(x: Array) -> Array:
                return np.array([x[0], 2.0 * x[0], x[1] ** 2 - 1.0])
            return AlternatingNoise(base, amplitude * np.array([1.0, -0.5, 0.75]))

        cases.append(GeneratedCase(
            f"fd_noise_floor_{index}",
            "fd_noise_floor",
            factory,
            np.array([1.7 + 0.1 * index, 0.0]),
            (np.array([0.0, -1.0]), np.array([0.0, 1.0])),
            np.ones(2),
        ))
    return cases


def negative_cases() -> list[GeneratedCase]:
    cases: list[GeneratedCase] = []
    for index in range(8):
        matrix = rotation(0.09 * index) @ np.diag([1.0, 1.5 + 0.1 * index])
        root = np.array([0.25, -0.6])

        def factory(matrix: Array = matrix, root: Array = root) -> Callable[[Array], Array]:
            return lambda x: matrix @ (x - root)

        cases.append(GeneratedCase(
            f"full_rank_linear_{index}",
            "full_rank_control",
            factory,
            np.array([2.0 + index, -1.5]),
            (root,),
            np.ones(2),
        ))

    for index in range(6):
        offset = 1.0 + 0.1 * index

        def factory(offset: float = offset) -> Callable[[Array], Array]:
            return lambda x: np.array([x[0] - offset, x[0] + offset])

        cases.append(GeneratedCase(
            f"inconsistent_{index}",
            "inconsistent_negative",
            factory,
            np.array([3.0 + index]),
            (),
            np.ones(1),
        ))

    for index in range(4):
        def factory() -> Callable[[Array], Array]:
            return lambda x: np.array([x[0], 2.0 * x[0], abs(x[1]) + 1.0])

        cases.append(GeneratedCase(
            f"opaque_branch_{index}",
            "opaque_negative",
            factory,
            np.array([2.0 + index, 0.0]),
            (),
            np.ones(2),
            smooth=False,
        ))

    for index in range(4):
        def factory() -> Callable[[Array], Array]:
            def residual(x: Array) -> Array:
                if x[1] > 5e-5:
                    return np.array([x[0], 1.0])
                return np.array([x[0], 2.0 * x[0], abs(x[1]) + 1.0])
            return residual

        cases.append(GeneratedCase(
            f"opaque_shape_change_{index}",
            "opaque_shape_negative",
            factory,
            np.array([2.0 + index, 0.0]),
            (),
            np.ones(2),
            smooth=False,
        ))
    return cases
