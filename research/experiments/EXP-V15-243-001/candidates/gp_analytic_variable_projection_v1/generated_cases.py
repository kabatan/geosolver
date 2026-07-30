"""Generated separable nonlinear LS operators; metadata stays outside candidate."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np

from candidate import OperatorState, SeparableProblem


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    family: str
    role: str
    problem: SeparableProblem
    start: np.ndarray


Basis = Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]


def _build_case(
    name: str,
    family: str,
    role: str,
    basis: Basis,
    *,
    target_x: float,
    target_linear: np.ndarray,
    start_x: float,
    t: np.ndarray,
    affine_certified: bool = True,
    opaque: bool = False,
    inconsistent: float = 0.0,
) -> GeneratedCase:
    target_matrix, _ = basis(t, np.asarray([target_x]))
    rhs = target_matrix @ target_linear
    if inconsistent:
        rhs = rhs + inconsistent * np.linspace(-1.0, 1.0, rhs.size) ** 3

    def operator(nonlinear: np.ndarray) -> OperatorState:
        matrix, derivative = basis(t, nonlinear)
        return OperatorState(
            matrix=matrix,
            matrix_derivative=derivative[:, :, None],
            rhs=rhs,
            rhs_derivative=np.zeros((rhs.size, 1)),
            outer_residual=np.empty(0),
            outer_jacobian=np.empty((0, 1)),
        )

    def full_residual(point: np.ndarray) -> np.ndarray:
        nonlinear = point[:1]
        linear = point[1:]
        state = operator(nonlinear)
        return state.matrix @ linear - state.rhs

    def full_jacobian(point: np.ndarray) -> np.ndarray:
        nonlinear = point[:1]
        linear = point[1:]
        state = operator(nonlinear)
        nonlinear_column = state.matrix_derivative[:, :, 0] @ linear - state.rhs_derivative[:, 0]
        return np.column_stack((nonlinear_column, state.matrix))

    problem = SeparableProblem(
        nonlinear_dimension=1,
        linear_dimension=target_linear.size,
        operator=operator,
        full_residual=full_residual,
        full_jacobian=full_jacobian,
        guard=lambda point: bool(np.all(np.isfinite(point)) and abs(point[0]) < 3.0),
        affine_certified=affine_certified,
        opaque=opaque,
    )
    start = np.concatenate(([start_x], np.zeros_like(target_linear)))
    return GeneratedCase(name, family, role, problem, start)


def exponential_basis(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    exponential = np.exp(t * x[0])
    return np.column_stack((np.ones_like(t), exponential)), np.column_stack((np.zeros_like(t), t * exponential))


def trigonometric_basis(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cosine = np.cos(t * x[0])
    sine = np.sin(t * x[0])
    return np.column_stack((cosine, sine)), np.column_stack((-t * sine, t * cosine))


def rational_basis(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    denominator = 1.0 + t * x[0]
    inverse = 1.0 / denominator
    return np.column_stack((np.ones_like(t), inverse)), np.column_stack((np.zeros_like(t), -t / denominator**2))


def rank_deficient_basis(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    column = np.exp(t * x[0])
    derivative = t * column
    return np.column_stack((column, column)), np.column_stack((derivative, derivative))


def ill_conditioned_basis(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    column = np.exp(t * x[0])
    other = column + 1.0e-11 * t
    derivative = t * column
    return np.column_stack((column, other)), np.column_stack((derivative, derivative))


def two_rate_case(name: str, target: np.ndarray, start: np.ndarray) -> GeneratedCase:
    t = np.linspace(-1.0, 1.2, 10)
    target_linear = np.asarray([1.2, -0.8])

    def state(nonlinear: np.ndarray) -> OperatorState:
        first = np.exp(t * nonlinear[0])
        second = np.exp(t * nonlinear[1])
        matrix = np.column_stack((first, second))
        derivative = np.zeros((t.size, 2, 2))
        derivative[:, 0, 0] = t * first
        derivative[:, 1, 1] = t * second
        target_matrix = np.column_stack((np.exp(t * target[0]), np.exp(t * target[1])))
        rhs = target_matrix @ target_linear
        return OperatorState(matrix, derivative, rhs, np.zeros((t.size, 2)), np.empty(0), np.empty((0, 2)))

    def residual(point: np.ndarray) -> np.ndarray:
        operator_state = state(point[:2])
        return operator_state.matrix @ point[2:] - operator_state.rhs

    def jacobian(point: np.ndarray) -> np.ndarray:
        operator_state = state(point[:2])
        nonlinear_columns = np.column_stack(
            tuple(operator_state.matrix_derivative[:, :, axis] @ point[2:] for axis in range(2))
        )
        return np.column_stack((nonlinear_columns, operator_state.matrix))

    problem = SeparableProblem(
        2,
        2,
        state,
        residual,
        jacobian,
        lambda point: bool(np.all(np.isfinite(point)) and np.max(np.abs(point[:2])) < 3.0),
    )
    return GeneratedCase(name, "rotated_two_rate", "positive", problem, np.concatenate((start, np.zeros(2))))


def rotate_nonlinear_coordinates(case: GeneratedCase, rotation: np.ndarray) -> GeneratedCase:
    """Return z-coordinates with physical nonlinear x = rotation @ z."""

    rotation = np.asarray(rotation, dtype=float)
    inverse = rotation.T
    original = case.problem

    def operator(z: np.ndarray) -> OperatorState:
        source = original.operator(rotation @ z)
        derivative = np.einsum("mpj,jk->mpk", source.matrix_derivative, rotation)
        rhs_derivative = source.rhs_derivative @ rotation
        outer_jacobian = source.outer_jacobian @ rotation
        return OperatorState(source.matrix, derivative, source.rhs, rhs_derivative, source.outer_residual, outer_jacobian)

    def to_source(point: np.ndarray) -> np.ndarray:
        return np.concatenate((rotation @ point[:2], point[2:]))

    problem = SeparableProblem(
        2,
        original.linear_dimension,
        operator,
        lambda point: original.full_residual(to_source(point)),
        lambda point: original.full_jacobian(to_source(point)) @ np.block(
            [[rotation, np.zeros((2, original.linear_dimension))],
             [np.zeros((original.linear_dimension, 2)), np.eye(original.linear_dimension)]]
        ),
        lambda point: original.guard(to_source(point)),
    )
    return GeneratedCase(
        case.name + "_rotated",
        case.family,
        case.role,
        problem,
        np.concatenate((inverse @ case.start[:2], case.start[2:])),
    )


def generated_suite() -> tuple[GeneratedCase, ...]:
    t = np.linspace(-1.0, 1.4, 9)
    cases: list[GeneratedCase] = []
    for index, (target, start) in enumerate(((-0.7, 0.9), (0.25, -1.1), (0.8, -0.8), (1.15, -0.5))):
        cases.append(_build_case(f"exp_{index}", "exponential_amplitude", "positive", exponential_basis, target_x=target, target_linear=np.asarray([0.6, 1.8]), start_x=start, t=t))
    for index, (target, start) in enumerate(((0.55, -0.7), (0.9, -0.4), (1.2, 0.1), (-0.8, 0.65))):
        cases.append(_build_case(f"trig_{index}", "trigonometric_amplitude", "positive", trigonometric_basis, target_x=target, target_linear=np.asarray([1.4, -0.75]), start_x=start, t=t))
    positive_t = np.linspace(0.0, 1.0, 9)
    for index, (target, start) in enumerate(((0.4, 1.5), (0.75, -0.4), (1.1, 0.1), (1.35, 0.3))):
        cases.append(_build_case(f"rational_{index}", "rational_amplitude", "positive", rational_basis, target_x=target, target_linear=np.asarray([0.3, 2.0]), start_x=start, t=positive_t))
    cases.extend(
        (
            two_rate_case("two_rate_0", np.asarray([-0.65, 0.75]), np.asarray([0.3, -0.5])),
            two_rate_case("two_rate_1", np.asarray([-0.9, 0.45]), np.asarray([0.1, -0.2])),
        )
    )
    cases.extend(
        (
            _build_case("inconsistent", "inconsistent_negative", "negative", exponential_basis, target_x=0.5, target_linear=np.asarray([0.7, 1.1]), start_x=-0.5, t=t, inconsistent=0.03),
            _build_case("rank_deficient", "rank_near_miss", "near_miss", rank_deficient_basis, target_x=0.4, target_linear=np.asarray([0.8, 0.2]), start_x=-0.3, t=t),
            _build_case("ill_conditioned", "rank_near_miss", "near_miss", ill_conditioned_basis, target_x=0.4, target_linear=np.asarray([0.8, 0.2]), start_x=-0.3, t=t),
            _build_case("nonaffine_marker", "nonaffine_fallback", "negative", exponential_basis, target_x=0.4, target_linear=np.asarray([0.8, 0.2]), start_x=-0.3, t=t, affine_certified=False),
            _build_case("opaque", "opaque_fallback", "negative", exponential_basis, target_x=0.4, target_linear=np.asarray([0.8, 0.2]), start_x=-0.3, t=t, opaque=True),
        )
    )
    return tuple(cases)
