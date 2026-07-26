"""LLL fallback polynomial discovery."""

from .polynomial_search import find_minimal_polynomial


def find_polynomial_lll(value: object, max_degree: int = 4) -> list[int] | None:
    """Find polynomial relation using the shared search backend."""
    return find_minimal_polynomial(
        value,
        precision=50,
        max_degree=max_degree,
        max_coeff=10**6,
        max_steps=10000,
        verbose=False,
    )
