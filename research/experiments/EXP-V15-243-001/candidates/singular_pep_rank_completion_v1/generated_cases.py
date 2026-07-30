"""Small truth-local singular polynomial matrix generators for D0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from candidate import PolynomialMatrixProblem


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    family: str
    role: str
    problem: PolynomialMatrixProblem
    expected_real: tuple[float, ...]


def _trim(coefficients: Sequence[np.ndarray]) -> tuple[np.ndarray, ...]:
    output = [np.asarray(item, dtype=np.complex128) for item in coefficients]
    while len(output) > 1 and np.linalg.norm(output[-1]) <= 1.0e-14:
        output.pop()
    return tuple(output)


def _multiply(left: Sequence[np.ndarray], right: Sequence[np.ndarray]) -> tuple[np.ndarray, ...]:
    size = left[0].shape[0]
    output = [np.zeros((size, size), dtype=np.complex128) for _ in range(len(left) + len(right) - 1)]
    for i, left_coefficient in enumerate(left):
        for j, right_coefficient in enumerate(right):
            output[i + j] += left_coefficient @ right_coefficient
    return _trim(output)


def _orthogonal(seed: int, size: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.standard_normal((size, size)))
    return q


def singular_diagonal_case(
    name: str,
    family: str,
    role: str,
    roots: Sequence[complex],
    *,
    polynomial_shear: bool = False,
    scale: float = 1.0,
    seed: int = 0,
) -> GeneratedCase:
    polynomial = np.polynomial.polynomial.polyfromroots(roots)
    degree = len(polynomial) - 1
    diagonal = []
    for index in range(degree + 1):
        matrix = np.zeros((3, 3), dtype=np.complex128)
        matrix[0, 0] = polynomial[index]
        if index == 0:
            matrix[1, 1] = 1.0
        diagonal.append(matrix)
    left = _orthogonal(1000 + seed, 3)
    right = _orthogonal(2000 + seed, 3)
    coefficients = tuple(scale * left @ matrix @ right for matrix in diagonal)
    if polynomial_shear:
        identity = np.eye(3, dtype=np.complex128)
        left_linear = np.zeros((3, 3), dtype=np.complex128)
        right_linear = np.zeros((3, 3), dtype=np.complex128)
        left_linear[0, 1] = 0.4
        right_linear[1, 2] = -0.65
        coefficients = _multiply((identity, left_linear), coefficients)
        coefficients = _multiply(coefficients, (identity, right_linear))
    expected = tuple(sorted(float(root.real) for root in roots if abs(root.imag) <= 1.0e-12))
    return GeneratedCase(name, family, role, PolynomialMatrixProblem(_trim(coefficients)), expected)


def regular_near_miss() -> GeneratedCase:
    coefficients = (
        np.diag([-0.5, 1.0, 0.25]).astype(np.complex128),
        np.diag([1.0, 0.0, 0.0]).astype(np.complex128),
    )
    return GeneratedCase(
        "regular_near_miss",
        "regular_fallback",
        "near_miss",
        PolynomialMatrixProblem(coefficients),
        (0.5,),
    )


def opaque_case() -> GeneratedCase:
    coefficients = (np.zeros((3, 3), dtype=np.complex128),)
    return GeneratedCase(
        "opaque_nonpolynomial",
        "opaque_fallback",
        "negative",
        PolynomialMatrixProblem(coefficients, opaque=True),
        (),
    )


def generated_suite() -> tuple[GeneratedCase, ...]:
    return (
        singular_diagonal_case("pencil_a", "singular_pencil", "positive", (-1.7,), seed=1),
        singular_diagonal_case("pencil_b", "singular_pencil", "positive", (0.35,), seed=2, scale=7.0),
        singular_diagonal_case("pencil_c", "singular_pencil", "positive", (2.1,), seed=3),
        singular_diagonal_case("quadratic_a", "singular_quadratic", "positive", (-1.2, 0.8), seed=4),
        singular_diagonal_case("quadratic_b", "singular_quadratic", "positive", (-0.25, 1.55), seed=5, scale=0.2),
        singular_diagonal_case(
            "coupled_shear_a",
            "polynomially_coupled",
            "positive",
            (-1.0, 0.6),
            seed=6,
            polynomial_shear=True,
        ),
        singular_diagonal_case(
            "coupled_shear_b",
            "polynomially_coupled",
            "positive",
            (-0.8, 0.2, 1.4),
            seed=7,
            polynomial_shear=True,
        ),
        singular_diagonal_case(
            "close_roots",
            "near_coalescing",
            "near_miss",
            (0.5, 0.5006),
            seed=8,
            polynomial_shear=True,
        ),
        singular_diagonal_case("complex_only", "fake_or_nonreal", "negative", (1j, -1j), seed=9),
        singular_diagonal_case("constant_singular", "fake_or_nonreal", "negative", (), seed=10),
        regular_near_miss(),
        opaque_case(),
    )
