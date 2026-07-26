"""Polynomial search helpers used by algebraic compatibility layer."""

from __future__ import annotations

from typing import Any, List, Optional, Union

from mpmath import mp, mpf

from geosolver._internal.observability.logging import emit_legacy_log as _emit_log
from geosolver._internal.solver.exact.polynomial_search_helpers import (
    scale_candidates_for_value,
    simple_lll,
    to_mpf_sanitized,
    verify_polynomial,
)


def _to_mpf_sanitized(val: Any) -> Any:
    return to_mpf_sanitized(val)


def _scale_candidates_for_value(val: Any) -> List[Any]:
    return scale_candidates_for_value(val)


def _simple_lll(basis: Any, delta: float = 0.75) -> Any:
    return simple_lll(basis, delta)


def _verify_polynomial(coeffs: List[int], r: Any, precision: float) -> bool:
    return verify_polynomial(coeffs, r, precision)


def find_minimal_polynomial(
    r: Union[float, Any],
    precision: int = 15,
    max_degree: int = 8,
    verbose: bool = False,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
) -> Optional[List[int]]:
    """Predict minimal polynomial coefficients from a numerical approximation."""
    mp.dps = max(precision + 40, 80)
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
        if coeffs is not None and _verify_polynomial(coeffs, r, precision):
            if verbose:
                _emit_log(f"  次数{degree}の多項式を発見: {coeffs}")
            return coeffs

        for s in _scale_candidates_for_value(r):
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

            coeffs_x: List[int] = []
            for idx, a in enumerate(coeffs_y):
                p = degree - idx
                try:
                    scale_pow = int(mp.nint(s ** (degree - p)))
                except Exception:
                    coeffs_x = []
                    break
                coeffs_x.append(int(a) * int(scale_pow))

            if not coeffs_x:
                continue

            from functools import reduce
            from math import gcd

            g = reduce(gcd, [abs(c) for c in coeffs_x if c != 0], 0)
            if g and g > 1:
                coeffs_x = [c // g for c in coeffs_x]
            if coeffs_x and coeffs_x[0] < 0:
                coeffs_x = [-c for c in coeffs_x]

            if _verify_polynomial(coeffs_x, r, precision):
                if verbose:
                    _emit_log(f"  次数{degree}の多項式を発見(スケール{s}): {coeffs_x}")
                return coeffs_x

    return None


def _find_polynomial_pslq(
    r: Any,
    degree: int,
    precision: int,
    *,
    max_coeff: int = 10**15,
    max_steps: int = 10000,
    verbose: bool = False,
) -> Optional[List[int]]:
    """Find polynomial coefficients with PSLQ."""
    try:
        from mpmath import pslq
    except ImportError:
        return _find_polynomial_lll(r, degree, precision, verbose)

    mp.dps = max(precision + 30, 60)
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


def _find_polynomial_lll(
    r: Any,
    degree: int,
    precision: int,
    verbose: bool = False,
) -> Optional[List[int]]:
    """Find polynomial coefficients with LLL fallback."""
    try:
        import numpy as np
    except ImportError:
        return None

    scale = 10 ** (precision // 2)
    n = degree + 1
    basis = np.zeros((n + 1, n + 1), dtype=np.float64)

    for i in range(n):
        basis[i, i] = 1

    r_float = float(r)
    for i in range(n):
        basis[n, i] = int(scale * (r_float**i))
    basis[n, n] = scale

    try:
        reduced = _simple_lll(basis)
        for row in reduced:
            coeffs = [int(round(row[i])) for i in range(n)]
            if any(c != 0 for c in coeffs):
                coeffs = list(reversed(coeffs))
                if coeffs[0] < 0:
                    coeffs = [-c for c in coeffs]
                if _verify_polynomial(coeffs, r, precision * 0.5):
                    return coeffs
    except Exception as e:
        if verbose:
            _emit_log(f"  LLL failed: {e}")

    return None
