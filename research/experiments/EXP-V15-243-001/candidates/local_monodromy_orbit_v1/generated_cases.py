"""Truth-local generated germs for local-monodromy D0 only."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Sequence

import numpy as np

from candidate import LocalGermProblem, canonical_source_replay


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    family: str
    problem: LocalGermProblem
    from_source: Callable[[np.ndarray], np.ndarray]


def _make_case(
    *,
    name: str,
    family: str,
    coefficient_builder: Callable[[complex], Sequence[complex]],
    residual_local: Callable[[complex, complex], complex],
    transform: np.ndarray | None = None,
    radius: float = 0.04,
    residual_scale: float = 1.0,
    guard_local: Callable[[float, float], bool] | None = None,
    rank: int = 0,
    opaque: bool = False,
) -> GeneratedCase:
    matrix = np.asarray(np.eye(2) if transform is None else transform, dtype=float)
    inverse = np.linalg.inv(matrix)
    guard = guard_local or (lambda _u, _v: True)

    def to_source(u: complex, v: complex) -> np.ndarray:
        return matrix.astype(np.complex128) @ np.asarray([u, v], dtype=np.complex128)

    def from_source(point: np.ndarray) -> np.ndarray:
        return inverse @ np.asarray(point, dtype=float)

    def source_residual(point: np.ndarray) -> tuple[complex]:
        u, v = from_source(point)
        return (residual_scale * residual_local(complex(u), complex(v)),)

    def source_guard(point: np.ndarray) -> bool:
        u, v = from_source(point)
        return bool(guard(float(u), float(v)))

    problem = LocalGermProblem(
        singular_point=np.zeros(2, dtype=float),
        local_jacobian_rank=rank,
        projection_radius=radius,
        fibre_coefficients=coefficient_builder,
        to_source=to_source,
        source_residual=source_residual,
        source_guard=source_guard,
        opaque=opaque,
    )
    return GeneratedCase(name, family, problem, from_source)


def binomial_case(
    name: str,
    family: str,
    *,
    fibre_degree: int,
    projection_power: int,
    **kwargs: object,
) -> GeneratedCase:
    def coefficients(parameter: complex) -> list[complex]:
        return [1.0] + [0.0] * (fibre_degree - 1) + [-(parameter**projection_power)]

    def residual(u: complex, v: complex) -> complex:
        return v**fibre_degree - u**projection_power

    return _make_case(
        name=name,
        family=family,
        coefficient_builder=coefficients,
        residual_local=residual,
        **kwargs,
    )


def branch_product_case(
    name: str,
    *,
    slopes: Sequence[float],
    power: int,
    **kwargs: object,
) -> GeneratedCase:
    def roots(parameter: complex) -> list[complex]:
        return [float(slope) * parameter**power for slope in slopes]

    def coefficients(parameter: complex) -> np.ndarray:
        return np.poly(roots(parameter))

    def residual(u: complex, v: complex) -> complex:
        value = 1.0 + 0.0j
        for slope in slopes:
            value *= v - float(slope) * u**power
        return value

    return _make_case(
        name=name,
        family="real_branch_product",
        coefficient_builder=coefficients,
        residual_local=residual,
        **kwargs,
    )


def generated_suite() -> tuple[GeneratedCase, ...]:
    permutation_scale = np.asarray([[0.0, 2.0], [3.0, 0.0]])
    return (
        binomial_case("cusp_2_3", "irreducible_cusp", fibre_degree=2, projection_power=3),
        binomial_case("cusp_2_5", "irreducible_cusp", fibre_degree=2, projection_power=5, radius=0.06),
        binomial_case(
            "cusp_2_3_permuted_scaled",
            "irreducible_cusp",
            fibre_degree=2,
            projection_power=3,
            transform=permutation_scale,
            residual_scale=7.0,
        ),
        binomial_case("ramified_4_5", "higher_ramification", fibre_degree=4, projection_power=5),
        binomial_case("ramified_4_7", "higher_ramification", fibre_degree=4, projection_power=7, radius=0.07),
        binomial_case("node_2_2", "reducible_tangent", fibre_degree=2, projection_power=2),
        binomial_case("tacnode_2_4", "reducible_tangent", fibre_degree=2, projection_power=4, radius=0.08),
        binomial_case(
            "tacnode_2_4_scaled",
            "reducible_tangent",
            fibre_degree=2,
            projection_power=4,
            transform=np.asarray([[4.0, 0.0], [0.0, 0.5]]),
        ),
        branch_product_case("three_branches", slopes=(-2.0, 0.5, 3.0), power=1),
        branch_product_case("four_tangent_branches", slopes=(-3.0, -0.5, 1.0, 2.5), power=2),
        branch_product_case(
            "three_branches_permuted_scaled",
            slopes=(-1.5, 0.75, 2.0),
            power=1,
            transform=permutation_scale,
            residual_scale=11.0,
        ),
        binomial_case(
            "guard_positive_near_miss",
            "guard_boundary_near_miss",
            fibre_degree=2,
            projection_power=3,
            guard_local=lambda _u, v: v > 0.0,
        ),
    )


def exact_local_witnesses(case: GeneratedCase) -> tuple[np.ndarray, ...]:
    problem = case.problem
    coefficients = np.asarray(problem.fibre_coefficients(complex(problem.projection_radius)))
    roots = np.roots(coefficients)
    retained: list[np.ndarray] = []
    for root in roots:
        source = np.asarray(problem.to_source(complex(problem.projection_radius), complex(root)))
        if np.max(np.abs(source.imag)) > 2.0e-9:
            continue
        point = np.asarray(source.real, dtype=float)
        if canonical_source_replay(problem, point) and not any(
            np.linalg.norm(point - prior) <= 1.0e-9 for prior in retained
        ):
            retained.append(point)
    retained.sort(key=lambda point: tuple(round(float(value), 12) for value in case.from_source(point)))
    return tuple(retained)


def opaque_fallback_case() -> GeneratedCase:
    calls = {"count": 0}

    def forbidden(_parameter: complex) -> list[complex]:
        calls["count"] += 1
        raise AssertionError("opaque fibre must not be evaluated")

    case = _make_case(
        name="opaque_transcendental",
        family="opaque_fallback",
        coefficient_builder=forbidden,
        residual_local=lambda u, v: v - np.sin(u),
        rank=0,
        opaque=True,
    )
    object.__setattr__(case, "_calls", calls)  # test-only observation, never read by candidate
    return case


def regular_fallback_case() -> GeneratedCase:
    return binomial_case(
        "regular_graph",
        "regular_fallback",
        fibre_degree=1,
        projection_power=3,
        rank=1,
    )
