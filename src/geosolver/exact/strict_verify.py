"""Strict verification helpers for exact-identification candidates."""

from __future__ import annotations

import re
from typing import Any

try:
    import sympy as _sympy
except Exception:
    _sympy = None

try:
    from mpmath import mp
except Exception:
    mp = None


def normalize_expression(expr: str) -> str:
    """Normalize expression text for robust parsing/evaluation."""
    s = re.sub(r"\s+", "", str(expr))
    s = s.replace("^", "**")
    s = re.sub(r"(?<=\d)(?=[A-Za-z(])", "*", s)
    s = re.sub(r"(?<=\))(?=[A-Za-z0-9(])", "*", s)
    s = s.replace("+-", "-").replace("-+", "-").replace("++", "+")
    return s


def evaluate_expression(expr: str, precision: int) -> Any | None:
    """Evaluate expression string to mpf using target precision."""
    if _sympy is None or mp is None:
        return None

    normalized = normalize_expression(expr)
    old_dps = mp.dps
    try:
        mp.dps = max(mp.dps, int(precision) * 2 + 40)
        sym_expr = _sympy.sympify(normalized)
        eval_out = sym_expr.evalf(mp.dps)
        return mp.mpf(eval_out)
    except Exception:
        return None
    finally:
        mp.dps = old_dps


def precision_tolerance(precision: int) -> Any:
    """Absolute tolerance implied by required precision digits."""
    if mp is None:
        return None
    digits = max(1, int(precision))
    return mp.power(mp.mpf(10), -digits)


def is_exact_match(expr: str, value: Any, precision: int) -> bool:
    """Return True when expression numerically matches value at required precision."""
    if mp is None:
        return False

    evaluated = evaluate_expression(expr, precision)
    if evaluated is None:
        return False

    try:
        target_input = value
        target = mp.mpf(target_input)
    except Exception:
        return False

    tol = precision_tolerance(precision)
    if tol is None:
        return False
    return abs(evaluated - target) <= tol
