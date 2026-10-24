"""Frozen STRICT polynomial discovery, with the bound exposed unchanged."""
from frozen_polynomial_search import find_minimal_polynomial


def identify(value, digits, max_coeff=10**8):
    return find_minimal_polynomial(value, precision=digits, max_degree=8,
                                   max_coeff=max_coeff, max_steps=20000, verbose=False)
