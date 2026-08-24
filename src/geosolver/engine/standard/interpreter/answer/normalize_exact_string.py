"""Normalize exact answer strings while preserving symbolic meaning."""

from __future__ import annotations

from typing import Any

from sympy import sympify


def _normalize_exact_string(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return text

    try:
        expr = sympify(text)
        expr = expr.simplify()
    except Exception:
        return text

    try:
        if getattr(expr, "is_Integer", False):
            return str(int(expr))
        if getattr(expr, "is_Rational", False):
            numerator = int(expr.p)
            denominator = int(expr.q)
            if denominator == 1:
                return str(numerator)
            return f"{numerator}/{denominator}"
        if getattr(expr, "is_Float", False):
            number = float(expr)
            nearest = round(number)
            if abs(number - nearest) < 1e-12:
                return str(int(nearest))
    except Exception:
        pass

    try:
        normalized = str(expr)
        return normalized.strip() if normalized else text
    except Exception:
        return text