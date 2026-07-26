"""Public PSLQ entrypoint backed by shared polynomial-search implementation."""

from .polynomial_search import find_minimal_polynomial


def find_polynomial_pslq(
    value: object,
    max_degree: int = 4,
    max_coeff: int = 8,
) -> list[int] | None:
    """Find an integer relation for ``[1, x, x^2, ...]``."""
    return find_minimal_polynomial(
        value,
        precision=50,
        max_degree=max_degree,
        max_coeff=max_coeff,
        max_steps=10000,
        verbose=False,
    )
