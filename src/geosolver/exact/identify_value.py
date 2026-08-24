"""Identify exact form for a single numeric value."""

from .algebraic_compat import identify
from .pslq import find_polynomial_pslq
from .strict_verify import is_exact_match
from .minimal_polynomial import compute_minimal_polynomial


def identify_value(value: object, max_degree: int = 4, precision: int = 50) -> dict[str, object]:
    """Return exact-identification metadata for one value."""
    polynomial = find_polynomial_pslq(value, max_degree=max_degree)
    minimal = compute_minimal_polynomial(value)
    exact = identify(value, precision=precision, max_degree=max_degree)
    verified = is_exact_match(exact, value, precision) if exact and not exact.startswith("≈") else False
    return {
        "value": str(value),
        "pslq": polynomial,
        "minimal_polynomial": minimal,
        "exact": exact,
        "verified": verified,
    }
