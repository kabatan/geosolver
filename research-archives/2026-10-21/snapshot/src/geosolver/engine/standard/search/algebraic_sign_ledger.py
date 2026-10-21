"""Necessary norm signs proved only in finite real arithmetic at exact roots."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NormSignCondition:
    constraint_index: int
    step: int
    a: object
    b: object
    radicand: object
    absolute: bool = False


def proved_norm_sign_violation(conditions, solution):
    """Return a violated necessary condition; unknown/domain failures stay.

    If a+b*r=0 with a,b finite-real and r>=0, then a*b=-b²*r<=0.
    The exact interval evaluator proves a,b individually finite-real. For sqrt,
    it also proves c>=0; for Abs(c), c must individually be finite-real.
    Positivity of the product alone is insufficient when a or b is complex.
    """
    import sympy as sp

    from geosolver.engine.standard.search.algebraic_branch_boxes import (
        exact_algebraic_interval_evaluator,
    )

    interval = exact_algebraic_interval_evaluator(sp.Rational(1, 2**640))
    for condition in conditions:
        try:
            a = interval(condition.a.subs(solution))
            b = interval(condition.b.subs(solution))
            c = interval(condition.radicand.subs(solution))
            if not condition.absolute and c[0] < 0:
                continue
            products = [first * second for first in a for second in b]
            if min(products) > 0:
                return condition
        except (ValueError, TypeError, ZeroDivisionError, NotImplementedError):
            # Unsupported, complex, nonfinite and undefined quantities do not
            # disprove the original equation. Keep the root for its verifier.
            continue
    return None
