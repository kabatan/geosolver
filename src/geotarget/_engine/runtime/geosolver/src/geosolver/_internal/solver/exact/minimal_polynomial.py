"""Minimal polynomial computation helpers."""

from sympy import Symbol, minimal_polynomial, sympify


def compute_minimal_polynomial(value: object, symbol: str = "x") -> str | None:
    """Compute symbolic minimal polynomial expression string."""
    x = Symbol(symbol)
    try:
        polynomial = minimal_polynomial(sympify(value), x)
    except Exception:
        return None
    return str(polynomial)
