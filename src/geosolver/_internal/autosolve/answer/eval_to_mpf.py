"""Convert exact expressions to mpf values."""

from __future__ import annotations

from typing import Any

from mpmath import mp
from sympy import sympify
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)


def _eval_exact_to_mpf(expr: Any, precision: int = 80) -> Any:
    """Evaluate symbolic expression to mpmath value with fallback behavior."""
    if expr is None:
        return None

    target_precision = max(15, int(precision))
    mp.dps = max(mp.dps, target_precision)

    try:
        if isinstance(expr, (mp.mpf, mp.mpc)):
            return expr
    except Exception:
        pass

    try:
        symbolic = sympify(expr)
        try:
            evaluated = symbolic.evalf(target_precision)
            if isinstance(evaluated, float):
                return boundary_float_to_mpf(evaluated, origin=BoundaryOrigin.OBJECTIVE_VALUE)
            return mp.mpf(evaluated)
        except Exception:
            if isinstance(symbolic, float):
                return boundary_float_to_mpf(symbolic, origin=BoundaryOrigin.OBJECTIVE_VALUE)
            return mp.mpf(symbolic)
    except Exception:
        pass

    try:
        if isinstance(expr, float):
            return boundary_float_to_mpf(expr, origin=BoundaryOrigin.OBJECTIVE_VALUE)
        return mp.mpf(expr)
    except Exception:
        return None
