"""Bounded polynomial reconstruction and real-root verification helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mpmath import mp, mpf

from geosolver.exact.polynomial_search_helpers import (
    scale_candidates_for_value,
    to_mpf_sanitized,
    verify_polynomial,
)
from geosolver.runtime.logging import emit_legacy_log as _emit_log


def _normalize_integer_polynomial(coefficients: Sequence[int]) -> list[int] | None:
    """Return a primitive, positive-leading polynomial in descending order.

    PSLQ can return a relation multiplied by an arbitrary integer, with
    leading zero coefficients, or (in a numerical breakdown) an all-zero
    vector.  Normalising those cases here gives the factor/verification code
    one unambiguous representation.  Trailing zero coefficients are retained:
    ``x`` and ``x**2`` are different polynomials and both are valid relations
    at the exact value zero.
    """
    try:
        values = [int(coefficient) for coefficient in coefficients]
    except (TypeError, ValueError, OverflowError):
        return None

    while values and values[0] == 0:
        values.pop(0)
    if len(values) < 2 or not any(values):
        return None

    from functools import reduce
    from math import gcd

    divisor = reduce(gcd, (abs(value) for value in values if value), 0)
    if divisor == 0:
        return None
    if divisor > 1:
        values = [value // divisor for value in values]
    if values[0] < 0:
        values = [-value for value in values]
    return values


def _irreducible_factors(coefficients: Sequence[int]) -> list[list[int]] | None:
    """Factor an integer relation and return its distinct primitive factors.

    A relation found from an approximate value is not necessarily a minimal
    polynomial.  In particular, PSLQ may return ``(x-a)^2`` or a product of
    unrelated factors.  SymPy's exact factorisation removes content and
    multiplicities; callers then select the factor whose real root is
    numerically compatible with the input.
    """
    normalized = _normalize_integer_polynomial(coefficients)
    if normalized is None:
        return None
    try:
        import sympy as sp

        symbol = sp.Symbol("x")
        polynomial = sp.Poly.from_list(normalized, gens=symbol, domain=sp.ZZ)
        _content, factors = sp.factor_list(polynomial.as_expr())
    except Exception:
        # Exact factorisation is an acceptance prerequisite.  Returning None
        # here fails closed instead of allowing a repeated relation through
        # the residual check when SymPy is unavailable or cannot factor it.
        return None

    result: list[list[int]] = []
    for factor, _multiplicity in factors:
        try:
            factor_poly = sp.Poly(factor, symbol, domain=sp.ZZ)
            if factor_poly.degree() < 1:
                continue
            factor_coefficients = _normalize_integer_polynomial(
                [int(value) for value in factor_poly.all_coeffs()]
            )
        except Exception:
            continue
        if factor_coefficients is not None:
            result.append(factor_coefficients)
    return result or None


def nearest_real_root_distance(coefficients: Sequence[int], value: Any) -> Any:
    """Return the distance from ``value`` to the nearest real root.

    This is deliberately a root-distance check rather than a polynomial
    residual check.  For a repeated factor, the latter scales as the square
    (or a higher power) of the numeric error and can therefore manufacture
    apparent precision.
    """
    normalized = _normalize_integer_polynomial(coefficients)
    if normalized is None:
        return mp.inf
    try:
        import sympy as sp

        symbol = sp.Symbol("x")
        polynomial = sp.Poly.from_list(normalized, gens=symbol, domain=sp.ZZ)
        roots = sp.real_roots(polynomial.as_expr(), symbol)
    except Exception:
        return mp.inf
    if not roots:
        return mp.inf

    try:
        numeric_value = to_mpf_sanitized(value)
        root_precision = max(80, int(mp.dps) + 20)
        with mp.workdps(root_precision):
            return min(
                abs(mp.mpf(str(sp.N(root, root_precision))) - numeric_value) for root in roots
            )
    except Exception:
        return mp.inf


def canonicalize_polynomial(
    coefficients: Sequence[int],
    numeric_value: Any | None = None,
    *,
    precision_dps: int | None = None,
) -> list[int] | None:
    """Return the distinct minimal-polynomial factor compatible with a value.

    The result is always primitive, positive-leading, and square-free.  When
    a reducible relation has several factors, the factor whose real root is
    closest to ``numeric_value`` is selected.  Ties at the available working
    precision are rejected because the numeric value does not identify one
    exact branch uniquely.
    """
    factors = _irreducible_factors(coefficients)
    if not factors:
        return None
    if numeric_value is None:
        return factors[0] if len(factors) == 1 else None
    if len(factors) == 1:
        return factors[0]

    precision = int(precision_dps) if precision_dps is not None else int(mp.dps)
    with mp.workdps(precision + 40):
        scored = [(nearest_real_root_distance(factor, numeric_value), factor) for factor in factors]
    scored = [entry for entry in scored if mp.isfinite(entry[0])]
    if not scored:
        return None
    scored.sort(key=lambda entry: entry[0])
    best_distance, best_factor = scored[0]
    if len(scored) > 1:
        second_distance = scored[1][0]
        tie_tolerance = mp.power(mp.mpf("10"), -max(20, precision - 20))
        if abs(second_distance - best_distance) <= tie_tolerance:
            return None
    return best_factor


def _verify_polynomial(coeffs: list[int], r: Any, precision: float) -> bool:
    canonical = canonicalize_polynomial(coeffs, r)
    if canonical is None:
        return False
    return verify_polynomial(canonical, r, precision)


def _find_minimal_polynomial_current_precision(
    r: float | Any,
    precision: int = 15,
    max_degree: int = 8,
    verbose: bool = False,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
) -> list[int] | None:
    """Predict minimal polynomial coefficients from a numerical approximation."""
    r = to_mpf_sanitized(r)

    for degree in range(1, max_degree + 1):
        coeffs = _find_polynomial_pslq(
            r,
            degree,
            precision,
            max_coeff=max_coeff,
            max_steps=max_steps,
            verbose=verbose,
        )
        canonical = None if coeffs is None else canonicalize_polynomial(coeffs, r)
        if canonical is not None and _verify_polynomial(canonical, r, precision):
            if verbose:
                _emit_log(f"  次数{degree}の最小因子を発見: {canonical}")
            return canonical

        for s in scale_candidates_for_value(r):
            try:
                y = r / s
            except Exception:
                continue
            coeffs_y = _find_polynomial_pslq(
                y,
                degree,
                precision,
                max_coeff=max_coeff,
                max_steps=max_steps,
                verbose=verbose,
            )
            if coeffs_y is None:
                continue

            import sympy as sp

            # Scales are powers of ten; reconstruct them exactly, including
            # negative exponents, before clearing coefficient denominators.
            exponent = int(mp.nint(mp.log10(s)))
            scale_exact = sp.Rational(10) ** exponent
            scaled = [sp.Integer(a) * scale_exact**idx for idx, a in enumerate(coeffs_y)]
            denominator = sp.ilcm(*[int(a.q) for a in scaled])
            coeffs_x = [int(a * denominator) for a in scaled]

            if not coeffs_x:
                continue

            from functools import reduce
            from math import gcd

            g = reduce(gcd, [abs(c) for c in coeffs_x if c != 0], 0)
            if g and g > 1:
                coeffs_x = [c // g for c in coeffs_x]
            if coeffs_x and coeffs_x[0] < 0:
                coeffs_x = [-c for c in coeffs_x]

            canonical_x = canonicalize_polynomial(coeffs_x, r)
            if canonical_x is not None and _verify_polynomial(canonical_x, r, precision):
                if verbose:
                    _emit_log(f"  次数{degree}の最小因子を発見(スケール{s}): {canonical_x}")
                return canonical_x

    return None


def find_minimal_polynomial(
    r: float | Any,
    precision: int = 15,
    max_degree: int = 8,
    verbose: bool = False,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
) -> list[int] | None:
    """Predict a minimal polynomial without leaking mpmath precision."""
    with mp.workdps(max(mp.dps, int(precision) + 40, 80)):
        return _find_minimal_polynomial_current_precision(
            r,
            precision,
            max_degree,
            verbose,
            max_coeff=max_coeff,
            max_steps=max_steps,
        )


def _find_polynomial_pslq_current_precision(
    r: Any,
    degree: int,
    precision: int,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
    verbose: bool = False,
) -> list[int] | None:
    """Find polynomial coefficients with PSLQ."""
    from mpmath import pslq

    powers = [r**i for i in range(degree + 1)]

    try:
        if precision > 100:
            tol = mpf(10) ** -(precision // 2)
        else:
            tol = mpf(10) ** -(precision * 3 // 10)
        relation = pslq(
            powers,
            tol=tol,
            maxcoeff=int(max_coeff),
            maxsteps=int(max_steps),
        )

        if relation is None:
            return None

        coeffs = [int(c) for c in reversed(relation)]
        if coeffs[0] < 0:
            coeffs = [-c for c in coeffs]
        if all(c == 0 for c in coeffs):
            return None

        from functools import reduce
        from math import gcd

        g = reduce(gcd, [abs(c) for c in coeffs if c != 0])
        if g > 1:
            coeffs = [c // g for c in coeffs]

        return coeffs
    except Exception as e:
        if verbose:
            _emit_log(f"  PSLQ failed for degree {degree}: {e}")
        return None


def _find_polynomial_pslq(
    r: Any,
    degree: int,
    precision: int,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
    verbose: bool = False,
) -> list[int] | None:
    with mp.workdps(max(mp.dps, int(precision) + 30, 60)):
        return _find_polynomial_pslq_current_precision(
            r,
            degree,
            precision,
            max_coeff=max_coeff,
            max_steps=max_steps,
            verbose=verbose,
        )
