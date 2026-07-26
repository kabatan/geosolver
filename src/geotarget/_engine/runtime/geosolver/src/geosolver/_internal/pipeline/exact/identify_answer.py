"""Exact-identification workflow for one high-precision answer value."""

from __future__ import annotations

from dataclasses import dataclass

from mpmath import mp

from geosolver._internal.pipeline.contracts.pipeline_result import ExactIdentificationResult
from geosolver._internal.solver.exact.polynomial_search import find_minimal_polynomial
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat

from .classify_exact_requirement import RELAXED_TIER, STANDARD_TIER, STRICT_TIER
from .verify_identified_answer import verify_identified_answer


@dataclass(frozen=True)
class ExactTierConfig:
    """Search parameters for each exact tier."""

    max_degree: int
    max_coeff: int
    max_steps: int


TIER_CONFIGS = {
    STRICT_TIER: ExactTierConfig(max_degree=8, max_coeff=10**8, max_steps=20000),
    STANDARD_TIER: ExactTierConfig(max_degree=6, max_coeff=10**7, max_steps=15000),
    RELAXED_TIER: ExactTierConfig(max_degree=4, max_coeff=10**6, max_steps=10000),
}


def _linear_exact_value(coefficients: list[int]) -> str | None:
    if len(coefficients) != 2:
        return None
    leading = int(coefficients[0])
    constant = int(coefficients[1])
    if leading == 0:
        return None
    try:
        from sympy import Rational
    except Exception:
        return None
    return str(Rational(-constant, leading))


def _polynomial_exact_value(
    coefficients: list[int], numeric_value: MPFloat
) -> str | None:
    """Resolve a minimal polynomial to a symbolic expression via sympy.

    For a polynomial of degree >= 2, compute all real roots symbolically
    and pick the one closest to *numeric_value*.
    """
    try:
        import sympy as sp
    except Exception:
        return None
    x = sp.Symbol("x")
    poly_expr = sum(int(c) * x ** (len(coefficients) - 1 - i) for i, c in enumerate(coefficients))
    try:
        roots = sp.real_roots(poly_expr, x)
    except Exception:
        return None
    if not roots:
        return None
    best_root = None
    best_dist = None
    for root in roots:
        try:
            approx = mp.mpf(str(sp.N(root, 40)))
            dist = abs(approx - numeric_value)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_root = root
        except Exception:
            continue
    if best_root is None:
        return None
    simplified = sp.nsimplify(best_root)
    return str(simplified)


def _sympy_fallback(value: MPFloat, precision_dps: int) -> tuple[str | None, MPFloat | None]:
    try:
        import sympy as sp
    except Exception:
        return None, None
    expr = sp.nsimplify(str(value))
    # Reject trivial decimal-to-fraction conversions (denominator is a power of 10).
    if expr.is_Rational and expr.q > 10**6:
        from sympy import factorint
        factors = factorint(int(expr.q))
        if set(factors.keys()) <= {2, 5}:
            return None, None
    approx = mp.mpf(sp.N(expr, int(precision_dps) + 20))
    residual = abs(approx - value)
    tolerance = mp.power(mp.mpf("10"), -(max(int(precision_dps) - 20, 1)))
    if residual <= tolerance:
        return str(expr), residual
    return None, residual


def identify_answer(
    *,
    answer_hp: MPFloat,
    tier: str,
    input_precision_dps: int,
) -> ExactIdentificationResult:
    """Identify exact representation using PSLQ-first strategy."""
    config = TIER_CONFIGS.get(tier, TIER_CONFIGS[RELAXED_TIER])
    coefficients = find_minimal_polynomial(
        answer_hp,
        precision=int(input_precision_dps),
        max_degree=int(config.max_degree),
        max_coeff=int(config.max_coeff),
        max_steps=int(config.max_steps),
        verbose=False,
    )
    if coefficients is not None:
        verified, residual = verify_identified_answer(
            coefficients=coefficients,
            numeric_value=answer_hp,
            precision_dps=int(input_precision_dps),
        )
        degree = len(coefficients) - 1
        if verified:
            linear_exact = _linear_exact_value(coefficients)
            if linear_exact is not None:
                selected_exact = linear_exact
                method = "pslq-linear"
            else:
                poly_exact = _polynomial_exact_value(list(coefficients), answer_hp)
                if poly_exact is not None:
                    selected_exact = poly_exact
                    method = "pslq-symbolic"
                else:
                    selected_exact = f"poly({coefficients})"
                    method = "pslq"
            return ExactIdentificationResult(
                exact_status="identified",
                identification_method=method,
                input_precision_dps=int(input_precision_dps),
                minimal_polynomial=tuple(int(c) for c in coefficients),
                polynomial_degree=degree,
                selected_exact_value=selected_exact,
                verification_residual=residual,
                numeric_fallback_value=None,
            )
        return ExactIdentificationResult(
            exact_status="verification_failed",
            identification_method="pslq",
            input_precision_dps=int(input_precision_dps),
            minimal_polynomial=tuple(int(c) for c in coefficients),
            polynomial_degree=degree,
            selected_exact_value=None,
            verification_residual=residual,
            numeric_fallback_value=answer_hp,
        )
    sympy_exact, sympy_residual = _sympy_fallback(answer_hp, int(input_precision_dps))
    if sympy_exact is not None:
        return ExactIdentificationResult(
            exact_status="identified",
            identification_method="sympy",
            input_precision_dps=int(input_precision_dps),
            minimal_polynomial=None,
            polynomial_degree=None,
            selected_exact_value=sympy_exact,
            verification_residual=sympy_residual,
            numeric_fallback_value=None,
        )
    return ExactIdentificationResult(
        exact_status="not_identified",
        identification_method="none",
        input_precision_dps=int(input_precision_dps),
        minimal_polynomial=None,
        polynomial_degree=None,
        selected_exact_value=None,
        verification_residual=sympy_residual,
        numeric_fallback_value=answer_hp,
    )

