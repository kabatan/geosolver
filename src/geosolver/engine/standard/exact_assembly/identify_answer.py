"""Exact-identification workflow for one high-precision answer value."""

from __future__ import annotations

from dataclasses import dataclass

from mpmath import mp

from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.exact.affine_pi_search import identify_affine_pi
from geosolver.exact.polynomial_search import (
    canonicalize_polynomial,
    find_minimal_polynomial,
)

from .classify_exact_requirement import RELAXED_TIER, STANDARD_TIER, STRICT_TIER
from .verify_identified_answer import verify_identified_answer


@dataclass(frozen=True)
class ExactTierConfig:
    """Search parameters for each exact tier."""

    max_degree: int
    max_coeff: int
    max_steps: int
    max_affine_pi_total_degree: int


TIER_CONFIGS = {
    STRICT_TIER: ExactTierConfig(
        max_degree=8,
        max_coeff=10**8,
        max_steps=20000,
        max_affine_pi_total_degree=4,
    ),
    STANDARD_TIER: ExactTierConfig(
        max_degree=6,
        max_coeff=10**7,
        max_steps=15000,
        max_affine_pi_total_degree=3,
    ),
    RELAXED_TIER: ExactTierConfig(
        max_degree=4,
        max_coeff=10**6,
        max_steps=10000,
        max_affine_pi_total_degree=1,
    ),
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
    coefficients: list[int], numeric_value: MPFloat, precision_dps: int = 120
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
            with mp.workdps(int(precision_dps) + 40):
                approx = mp.mpf(str(sp.N(root, int(precision_dps) + 40)))
                dist = abs(approx - numeric_value)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_root = root
        except Exception:
            continue
    if best_root is None:
        return None
    # CRootOf is already exact. nsimplify can replace it by a nearby rational.
    with mp.workdps(int(precision_dps) + 40):
        tolerance = max(1, abs(numeric_value)) * mp.power(10, -max(1, int(precision_dps) - 20))
        if best_dist > tolerance:
            return None
        compatible = [
            root
            for root in roots
            if abs(mp.mpf(str(sp.N(root, int(precision_dps) + 40))) - numeric_value) <= tolerance
        ]
        if len(compatible) != 1:
            return None
    return str(best_root)


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


def _is_symbolic_zero(value: str | None) -> bool:
    if value is None:
        return False
    try:
        import sympy as sp

        return bool(sp.sympify(value) == 0)
    except Exception:
        return str(value).strip() in {"0", "0.0"}


def _numeric_value_is_exact_zero(value: MPFloat, precision_dps: int) -> bool:
    try:
        with mp.workdps(max(int(precision_dps) + 20, int(mp.dps))):
            return bool(mp.mpf(value) == 0)
    except Exception:
        return False


def _identify_affine_pi_result(
    *,
    answer_hp: MPFloat,
    config: ExactTierConfig,
    input_precision_dps: int,
    rational_only: bool = False,
) -> ExactIdentificationResult | None:
    candidate = identify_affine_pi(
        numeric_value=answer_hp,
        precision_dps=int(input_precision_dps),
        max_total_degree=1 if rational_only else int(config.max_affine_pi_total_degree),
        max_coeff=int(config.max_coeff),
        max_steps=int(config.max_steps),
    )
    if candidate is None:
        return None
    return ExactIdentificationResult(
        exact_status="identified",
        identification_method=candidate.method,
        input_precision_dps=int(input_precision_dps),
        # A nonconstant A*pi+B is transcendental, so it has no minimal
        # polynomial over the rationals.  The bivariate search relation is an
        # internal reconstruction certificate, not this contract field.
        minimal_polynomial=None,
        polynomial_degree=None,
        selected_exact_value=candidate.exact_value,
        verification_residual=candidate.verification_residual,
        numeric_fallback_value=None,
    )


def _identify_answer_proposal(
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
        # Keep the contract defensive even when a third-party/legacy search
        # backend supplies a reducible or repeated relation.  Exact results
        # must carry a primitive square-free minimal factor, never a relation
        # whose multiplicity artificially reduces the residual.
        canonical = canonicalize_polynomial(
            coefficients, answer_hp, precision_dps=int(input_precision_dps)
        )
        if canonical is None:
            affine_pi_result = _identify_affine_pi_result(
                answer_hp=answer_hp,
                config=config,
                input_precision_dps=int(input_precision_dps),
            )
            if affine_pi_result is not None:
                return affine_pi_result
            return ExactIdentificationResult(
                exact_status="verification_failed",
                identification_method="pslq-noncanonical",
                input_precision_dps=int(input_precision_dps),
                minimal_polynomial=tuple(int(c) for c in coefficients),
                polynomial_degree=len(coefficients) - 1,
                selected_exact_value=None,
                verification_residual=mp.inf,
                numeric_fallback_value=answer_hp,
            )
        coefficients = canonical
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
                poly_exact = _polynomial_exact_value(
                    list(coefficients), answer_hp, int(input_precision_dps)
                )
                if poly_exact is not None:
                    selected_exact = poly_exact
                    method = "pslq-symbolic"
                else:
                    return ExactIdentificationResult(
                        exact_status="verification_failed",
                        identification_method="pslq-ambiguous-root",
                        input_precision_dps=int(input_precision_dps),
                        minimal_polynomial=tuple(coefficients),
                        polynomial_degree=degree,
                        selected_exact_value=None,
                        verification_residual=residual,
                        numeric_fallback_value=answer_hp,
                    )
            # A zero-root polynomial can have a tiny nonzero numerical value
            # as its approximate root (for example x**7 at 1e-122).  The
            # polynomial residual alone is therefore not proof that the exact
            # answer is zero.  Keep the numeric value unresolved unless the
            # evaluator itself returned exact zero.
            if _is_symbolic_zero(selected_exact) and not _numeric_value_is_exact_zero(
                answer_hp,
                int(input_precision_dps),
            ):
                return ExactIdentificationResult(
                    exact_status="verification_failed",
                    identification_method=f"{method}-zero_rejected",
                    input_precision_dps=int(input_precision_dps),
                    minimal_polynomial=tuple(int(c) for c in coefficients),
                    polynomial_degree=degree,
                    selected_exact_value=None,
                    verification_residual=residual,
                    numeric_fallback_value=answer_hp,
                )
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
        affine_pi_result = _identify_affine_pi_result(
            answer_hp=answer_hp,
            config=config,
            input_precision_dps=int(input_precision_dps),
        )
        if affine_pi_result is not None:
            return affine_pi_result
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
    affine_pi_result = _identify_affine_pi_result(
        answer_hp=answer_hp,
        config=config,
        input_precision_dps=int(input_precision_dps),
    )
    if affine_pi_result is not None:
        return affine_pi_result
    sympy_exact, sympy_residual = _sympy_fallback(answer_hp, int(input_precision_dps))
    if sympy_exact is not None:
        if _is_symbolic_zero(sympy_exact) and not _numeric_value_is_exact_zero(
            answer_hp,
            int(input_precision_dps),
        ):
            return ExactIdentificationResult(
                exact_status="not_identified",
                identification_method="sympy-zero-rejected",
                input_precision_dps=int(input_precision_dps),
                minimal_polynomial=None,
                polynomial_degree=None,
                selected_exact_value=None,
                verification_residual=sympy_residual,
                numeric_fallback_value=answer_hp,
            )
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


def identify_answer(
    *,
    answer_hp,
    tier,
    input_precision_dps,
    answer_uncertainty=None,
    closed_source=None,
    reusable_results=(),
    prefer_affine_pi=False,
    geometry_hint=None,
):
    """Bounded discovery followed by root-distance validation and a descriptor."""
    from geosolver.runtime.symbolic import request
    from geosolver.runtime.symbolic_operations import decode_identification, encode_identification

    payload = {
        "value": tuple(map(int, answer_hp._mpf_)),
        "tier": tier,
        "precision": input_precision_dps,
        "uncertainty": None
        if answer_uncertainty is None
        else tuple(map(int, answer_uncertainty._mpf_)),
        "closed_source": closed_source,
        "prefer_affine_pi": bool(prefer_affine_pi),
        "geometry_hint": geometry_hint,
        "reusable_results": [encode_identification(result) for result in reusable_results],
    }
    result = decode_identification(request("identify", payload))
    if result.identification_method == "verified_descriptor_reuse":
        from geosolver.runtime.deadline import count_event

        count_event("exact_descriptor_reuses")
    return result
