"""Prospective toy families for exceptional-stratum D0.

Family/role/truth live only in this scorer-side module.  The candidate receives
only numerical callbacks, scales, parameters, and an unstable endpoint cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from candidate import ParameterizedProblem, canonical_source_replay


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    family: str
    role: str
    problem: ParameterizedProblem
    baseline: tuple[np.ndarray, ...]
    unstable_cluster: tuple[np.ndarray, ...]
    exact: tuple[np.ndarray, ...]
    normalize: Callable[[np.ndarray], tuple[float, ...]]


def _real_roots(coefficients: Sequence[complex], *, tolerance: float = 5.0e-8) -> list[float]:
    roots = np.roots(np.asarray(coefficients, dtype=np.complex128))
    return sorted(float(root.real) for root in roots if abs(root.imag) <= tolerance)


def polynomial_case(
    *,
    name: str,
    family: str,
    role: str,
    source_parameter: Sequence[float],
    parameter_scale: Sequence[float],
    coefficients: Callable[[np.ndarray], Sequence[complex]],
    baseline_indices: Sequence[int],
    x_factor: float = 1.0,
    equation_scale: float = 1.0,
    guard_x: Callable[[float, np.ndarray], bool] | None = None,
    unstable_extra_x: Sequence[float] = (),
    opaque: bool = False,
) -> GeneratedCase:
    p0 = np.asarray(source_parameter, dtype=float)
    pscale = np.asarray(parameter_scale, dtype=float)
    guard_underlying = guard_x or (lambda _x, _p: True)

    def fibre_solver(parameter: np.ndarray) -> tuple[np.ndarray, ...]:
        roots = np.roots(np.asarray(coefficients(parameter), dtype=np.complex128))
        return tuple(np.asarray([x_factor * root], dtype=np.complex128) for root in roots)

    def residual(point: np.ndarray, parameter: np.ndarray) -> tuple[complex]:
        x = complex(point[0]) / x_factor
        return (equation_scale * np.polyval(coefficients(parameter), x),)

    def jacobian(point: np.ndarray, parameter: np.ndarray) -> np.ndarray:
        x = complex(point[0]) / x_factor
        derivative = np.polyval(np.polyder(np.asarray(coefficients(parameter), dtype=np.complex128)), x)
        return np.asarray([[equation_scale * derivative / x_factor]], dtype=np.complex128)

    def guard(point: np.ndarray, parameter: np.ndarray) -> bool:
        return bool(guard_underlying(float(point[0]) / x_factor, parameter))

    problem = ParameterizedProblem(
        source_parameter=p0,
        parameter_scale=pscale,
        point_scale=np.asarray([abs(x_factor)], dtype=float),
        residual_scale=np.asarray([abs(equation_scale)], dtype=float),
        ball_radius=1.0,
        fibre_solver=fibre_solver,
        residual=residual,
        jacobian=jacobian,
        guard=guard,
        opaque=opaque,
    )
    source_roots = _real_roots(coefficients(p0))
    exact = tuple(
        np.asarray([x_factor * root], dtype=float)
        for root in source_roots
        if guard_underlying(root, p0)
    )
    baseline = tuple(np.array(exact[index], copy=True) for index in baseline_indices)
    unstable = tuple(
        [*baseline, *(np.asarray([x_factor * value], dtype=float) for value in unstable_extra_x)]
    )
    return GeneratedCase(
        name,
        family,
        role,
        problem,
        baseline,
        unstable,
        exact,
        lambda point: (round(float(point[0]) / x_factor, 8),),
    )


def fold_case(
    name: str = "fold_pair",
    family: str = "fold_coalescence",
    role: str = "positive",
    *,
    x_factor: float = 1.0,
    equation_scale: float = 1.0,
    reflected_parameter: bool = False,
    guard_x: Callable[[float, np.ndarray], bool] | None = None,
    baseline_indices: Sequence[int] = (0,),
) -> GeneratedCase:
    sign = -1.0 if reflected_parameter else 1.0
    p0 = [-0.0025] if reflected_parameter else [0.0025]
    return polynomial_case(
        name=name,
        family=family,
        role=role,
        source_parameter=p0,
        parameter_scale=[0.0025],
        coefficients=lambda parameter: [1.0, 0.0, -(sign * parameter[0])],
        baseline_indices=baseline_indices,
        x_factor=x_factor,
        equation_scale=equation_scale,
        guard_x=guard_x,
    )


def transcritical_case() -> GeneratedCase:
    return polynomial_case(
        name="transcritical_pair",
        family="transcritical_crossing",
        role="positive",
        source_parameter=[0.04],
        parameter_scale=[0.04],
        coefficients=lambda parameter: [1.0, -parameter[0], 0.0],
        baseline_indices=(0,),
    )


def pitchfork_case() -> GeneratedCase:
    return polynomial_case(
        name="pitchfork_triple",
        family="pitchfork_emergence",
        role="positive",
        source_parameter=[0.01],
        parameter_scale=[0.01],
        coefficients=lambda parameter: [1.0, 0.0, -parameter[0], 0.0],
        baseline_indices=(0, 1),
    )


def cusp_case(*, swapped_parameters: bool = False) -> GeneratedCase:
    if swapped_parameters:
        source = [0.0018, 0.03]
        scale = [0.0002, 0.005]

        def coefficients(parameter: np.ndarray) -> list[float]:
            b, a = parameter
            return [1.0, 0.0, -a, -b]

        name = "cusp_discriminant_swapped"
    else:
        source = [0.03, 0.0018]
        scale = [0.005, 0.0002]

        def coefficients(parameter: np.ndarray) -> list[float]:
            a, b = parameter
            return [1.0, 0.0, -a, -b]

        name = "cusp_discriminant"
    return polynomial_case(
        name=name,
        family="cusp_discriminant",
        role="positive",
        source_parameter=source,
        parameter_scale=scale,
        coefficients=coefficients,
        baseline_indices=(0, 2),
    )


def guard_boundary_case() -> GeneratedCase:
    return fold_case(
        name="guarded_fold",
        family="strict_guard_boundary",
        role="negative",
        guard_x=lambda x, _parameter: x < -1.0e-10,
        baseline_indices=(0,),
    )


def dimension_jump_case() -> GeneratedCase:
    p0 = np.asarray([1.0e-4])

    def fibre_solver(parameter: np.ndarray) -> tuple[np.ndarray, ...]:
        if abs(float(parameter[0])) <= 1.0e-14:
            return tuple(np.asarray([0.0, y]) for y in (-1.0, 0.0, 1.0))
        return (np.asarray([0.0, 0.0]),)

    def residual(point: np.ndarray, parameter: np.ndarray) -> tuple[complex, complex]:
        x, y = point
        return (x, parameter[0] * y)

    def jacobian(_point: np.ndarray, parameter: np.ndarray) -> np.ndarray:
        return np.asarray([[1.0, 0.0], [0.0, parameter[0]]])

    problem = ParameterizedProblem(
        source_parameter=p0,
        parameter_scale=np.asarray([1.0e-4]),
        point_scale=np.ones(2),
        residual_scale=np.ones(2),
        ball_radius=1.0,
        fibre_solver=fibre_solver,
        residual=residual,
        jacobian=jacobian,
        guard=lambda _point, _parameter: True,
    )
    root = np.asarray([0.0, 0.0])
    return GeneratedCase(
        "line_fibre_dimension_jump",
        "positive_dimensional_fibre",
        "near_miss",
        problem,
        (root,),
        (root,),
        (root,),
        lambda point: tuple(round(float(value), 8) for value in point),
    )


def emergent_overdetermined_case() -> GeneratedCase:
    p0 = np.asarray([1.0e-3])

    def fibre_solver(parameter: np.ndarray) -> tuple[np.ndarray, ...]:
        if abs(float(parameter[0])) <= 1.0e-14:
            return (np.asarray([-1.0]), np.asarray([1.0]))
        return (np.asarray([1.0]),)

    def residual(point: np.ndarray, parameter: np.ndarray) -> tuple[complex, complex]:
        x = point[0]
        return (x * x - 1.0, parameter[0] * (x - 1.0))

    def jacobian(point: np.ndarray, parameter: np.ndarray) -> np.ndarray:
        return np.asarray([[2.0 * point[0]], [parameter[0]]])

    problem = ParameterizedProblem(
        source_parameter=p0,
        parameter_scale=np.asarray([1.0e-3]),
        point_scale=np.ones(1),
        residual_scale=np.ones(2),
        ball_radius=1.0,
        fibre_solver=fibre_solver,
        residual=residual,
        jacobian=jacobian,
        guard=lambda _point, _parameter: True,
    )
    root = np.asarray([1.0])
    near = np.asarray([-1.0])
    return GeneratedCase(
        "overdetermined_emergent_root",
        "emergent_overdetermined",
        "near_miss",
        problem,
        (root,),
        (root, near),
        (root,),
        lambda point: (round(float(point[0]), 8),),
    )


def complex_side_near_miss_case() -> GeneratedCase:
    return polynomial_case(
        name="complex_only_source_side",
        family="real_to_complex_fold",
        role="near_miss",
        source_parameter=[-0.0025],
        parameter_scale=[0.0025],
        coefficients=lambda parameter: [1.0, 0.0, -parameter[0]],
        baseline_indices=(),
        unstable_extra_x=(0.0,),
    )


def stable_nonexceptional_case() -> GeneratedCase:
    return polynomial_case(
        name="stable_parallel_roots",
        family="stable_nonexceptional",
        role="negative",
        source_parameter=[0.0],
        parameter_scale=[0.1],
        coefficients=lambda parameter: np.poly([1.0 + parameter[0], -2.0 + parameter[0]]),
        baseline_indices=(0, 1),
    )


def opaque_case() -> GeneratedCase:
    calls = {"fibre": 0}

    def forbidden(_parameter: np.ndarray) -> tuple[np.ndarray, ...]:
        calls["fibre"] += 1
        raise AssertionError("opaque problem must fail before fibre sampling")

    problem = ParameterizedProblem(
        source_parameter=np.asarray([0.0]),
        parameter_scale=np.asarray([0.1]),
        point_scale=np.ones(1),
        residual_scale=np.ones(1),
        ball_radius=1.0,
        fibre_solver=forbidden,
        residual=lambda point, _parameter: (np.sin(point[0]),),
        jacobian=lambda point, _parameter: np.asarray([[np.cos(point[0])]]),
        guard=lambda _point, _parameter: True,
        opaque=True,
    )
    root = np.asarray([0.0])
    case = GeneratedCase(
        "opaque_transcendental",
        "opaque_no_parameter_fibre",
        "negative",
        problem,
        (root,),
        (root,),
        (root,),
        lambda point: (round(float(point[0]), 8),),
    )
    object.__setattr__(case, "_calls", calls)
    return case


def generated_suite() -> tuple[GeneratedCase, ...]:
    return (
        fold_case(),
        transcritical_case(),
        pitchfork_case(),
        cusp_case(),
        guard_boundary_case(),
        dimension_jump_case(),
        emergent_overdetermined_case(),
        complex_side_near_miss_case(),
        stable_nonexceptional_case(),
        opaque_case(),
    )


def truth_contains(case: GeneratedCase, point: np.ndarray, tolerance: float = 3.0e-6) -> bool:
    return any(
        np.linalg.norm(
            (np.asarray(point, dtype=float) - target) / case.problem.point_scale
        )
        <= tolerance
        for target in case.exact
    )


def assert_truth_safe(case: GeneratedCase) -> None:
    for point in case.exact:
        if not canonical_source_replay(case.problem, point):
            raise AssertionError(f"unsafe generated truth in {case.name}")
