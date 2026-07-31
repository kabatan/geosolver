"""Throwaway D0: exact global derivative-energy start transport.

The source residuals are exact QQ polynomials in standardized coordinates.
Their Gaussian derivative second moment defines a source-only metric.  The
metric transports only one quarter of baseline directions and preserves each
standardized radius; guards may reject any transported point and recover the
untouched baseline point.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable, Sequence

import numpy as np
import sympy as sp


class CapabilityError(ValueError):
    """The deliberately narrow polynomial source route is inapplicable."""


def gaussian_monomial_moment(powers: Sequence[int]) -> int:
    """Exact E[prod X_i**powers_i] for independent standard Gaussians."""

    result = 1
    for power in powers:
        if not isinstance(power, int) or power < 0:
            raise CapabilityError("Gaussian monomial powers must be nonnegative")
        if power % 2:
            return 0
        result *= math.prod(range(1, power, 2))
    return result


def gaussian_expectation(polynomial: sp.Poly) -> sp.Rational:
    result = sp.Rational(0)
    for monomial, coefficient in polynomial.terms():
        result += sp.Rational(coefficient) * gaussian_monomial_moment(monomial)
    return sp.Rational(result)


def _qq_poly(expression: sp.Expr | sp.Poly, variables: Sequence[sp.Symbol]) -> sp.Poly:
    if isinstance(expression, sp.Poly):
        expression = expression.as_expr()
    try:
        return sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError) as error:
        raise CapabilityError("residual is not an exact QQ polynomial") from error


@dataclass(frozen=True)
class DerivativeEnergyCertificate:
    variables: tuple[sp.Symbol, ...]
    residuals: tuple[sp.Poly, ...]
    row_second_moments: tuple[sp.Rational, ...]
    matrix: sp.ImmutableMatrix

    def verify(self) -> bool:
        try:
            rebuilt = derivative_energy_certificate(
                [item.as_expr() for item in self.residuals], self.variables
            )
        except CapabilityError:
            return False
        return bool(
            rebuilt.row_second_moments == self.row_second_moments
            and rebuilt.matrix == self.matrix
        )


def derivative_energy_certificate(
    residuals: Iterable[sp.Expr | sp.Poly], variables: Sequence[sp.Symbol]
) -> DerivativeEnergyCertificate:
    variables = tuple(variables)
    if not variables:
        raise CapabilityError("empty source variable vector")
    polynomials = tuple(_qq_poly(item, variables) for item in residuals)
    if not polynomials:
        raise CapabilityError("empty source residual vector")
    matrix = sp.zeros(len(variables), len(variables))
    row_moments: list[sp.Rational] = []
    active_rows = 0
    for polynomial in polynomials:
        second_moment = gaussian_expectation(
            _qq_poly(polynomial.as_expr() ** 2, variables)
        )
        row_moments.append(second_moment)
        if second_moment <= 0:
            continue
        active_rows += 1
        gradient = tuple(
            _qq_poly(sp.diff(polynomial.as_expr(), variable), variables)
            for variable in variables
        )
        for row in range(len(variables)):
            for column in range(row, len(variables)):
                entry = gaussian_expectation(
                    _qq_poly(
                        gradient[row].as_expr() * gradient[column].as_expr(),
                        variables,
                    )
                ) / second_moment
                matrix[row, column] += entry
                if row != column:
                    matrix[column, row] += entry
    if active_rows == 0 or matrix.trace() <= 0:
        raise CapabilityError("source derivative energy is zero")
    certificate = DerivativeEnergyCertificate(
        variables=variables,
        residuals=polynomials,
        row_second_moments=tuple(row_moments),
        matrix=sp.ImmutableMatrix(matrix),
    )
    if certificate.matrix != certificate.matrix.T:
        raise CapabilityError("internal derivative matrix is not symmetric")
    return certificate


def try_derivative_energy_certificate(
    residuals: Iterable[sp.Expr | sp.Poly], variables: Sequence[sp.Symbol]
) -> DerivativeEnergyCertificate | None:
    try:
        return derivative_energy_certificate(residuals, variables)
    except CapabilityError:
        return None


def standardized_residuals(
    residuals: Iterable[sp.Expr | sp.Poly],
    variables: Sequence[sp.Symbol],
    bounds: Sequence[tuple[sp.Rational, sp.Rational]],
) -> tuple[tuple[sp.Symbol, ...], tuple[sp.Poly, ...]]:
    variables = tuple(variables)
    if len(variables) != len(bounds):
        raise CapabilityError("bounds dimension mismatch")
    standardized = tuple(sp.Symbol(f"__energy_z_{index}") for index in range(len(variables)))
    substitutions: dict[sp.Symbol, sp.Expr] = {}
    for variable, z, pair in zip(variables, standardized, bounds, strict=True):
        lower, upper = map(sp.Rational, pair)
        if not lower < upper:
            raise CapabilityError("source bound is not a finite interval")
        center = (lower + upper) / 2
        scale = (upper - lower) / 2
        substitutions[variable] = center + scale * z
    result = tuple(
        _qq_poly(_qq_poly(item, variables).as_expr().subs(substitutions), standardized)
        for item in residuals
    )
    return standardized, result


def inverse_sqrt_transport(matrix: sp.MatrixBase) -> np.ndarray:
    numeric = np.asarray(matrix.tolist(), dtype=np.float64)
    if numeric.ndim != 2 or numeric.shape[0] != numeric.shape[1] or not np.all(np.isfinite(numeric)):
        raise CapabilityError("energy matrix is not finite square")
    ridge = float(np.trace(numeric) / numeric.shape[0])
    if not ridge > 0:
        raise CapabilityError("formula-fixed ridge is nonpositive")
    eigenvalues, eigenvectors = np.linalg.eigh(numeric)
    shifted = eigenvalues + ridge
    if np.any(shifted <= 0) or not np.all(np.isfinite(shifted)):
        raise CapabilityError("regularized energy matrix is not positive definite")
    return (eigenvectors * (1.0 / np.sqrt(shifted))) @ eigenvectors.T


def transport_direction(direction: Sequence[float], matrix: sp.MatrixBase) -> np.ndarray:
    baseline = np.asarray(direction, dtype=np.float64)
    if baseline.ndim != 1 or baseline.shape[0] != matrix.rows or not np.all(np.isfinite(baseline)):
        raise CapabilityError("baseline direction is malformed")
    radius = float(np.linalg.norm(baseline))
    if radius == 0:
        return baseline.copy()
    proposal = inverse_sqrt_transport(matrix) @ baseline
    proposal_radius = float(np.linalg.norm(proposal))
    if not proposal_radius > 0 or not math.isfinite(proposal_radius):
        raise CapabilityError("transport collapsed the baseline direction")
    return proposal * (radius / proposal_radius)


def transport_start_or_baseline(
    baseline: Sequence[float],
    center: Sequence[float],
    scales: Sequence[float],
    matrix: sp.MatrixBase,
    accept: Callable[[np.ndarray], bool],
) -> tuple[np.ndarray, bool]:
    baseline_array = np.asarray(baseline, dtype=np.float64)
    center_array = np.asarray(center, dtype=np.float64)
    scale_array = np.asarray(scales, dtype=np.float64)
    if (
        baseline_array.shape != center_array.shape
        or baseline_array.shape != scale_array.shape
        or np.any(scale_array <= 0)
        or not np.all(np.isfinite(scale_array))
    ):
        raise CapabilityError("source standardization is malformed")
    standardized = (baseline_array - center_array) / scale_array
    candidate = center_array + scale_array * transport_direction(standardized, matrix)
    try:
        accepted = bool(accept(candidate))
    except Exception:
        accepted = False
    if not accepted or not np.all(np.isfinite(candidate)):
        return baseline_array.copy(), False
    return candidate, True


def fixed_quarter_portfolio(
    baseline_starts: Sequence[Sequence[float]],
    transport: Callable[[Sequence[float]], tuple[np.ndarray, bool]],
) -> tuple[list[np.ndarray], int, int]:
    """Interleave exactly three untouched starts then one side-route start."""

    result: list[np.ndarray] = []
    transported = 0
    fallbacks = 0
    for index, baseline in enumerate(baseline_starts):
        baseline_array = np.asarray(baseline, dtype=np.float64)
        if index % 4 != 3:
            result.append(baseline_array.copy())
            continue
        candidate, accepted = transport(baseline)
        result.append(candidate)
        if accepted:
            transported += 1
        else:
            fallbacks += 1
    return result, transported, fallbacks


def directional_energy(direction: Sequence[float], matrix: sp.MatrixBase) -> float:
    vector = np.asarray(direction, dtype=np.float64)
    radius_squared = float(vector @ vector)
    if radius_squared == 0:
        return 0.0
    numeric = np.asarray(matrix.tolist(), dtype=np.float64)
    return float(vector @ numeric @ vector / radius_squared)
