"""Backward-compatible exports for search strategies."""

from .halton_search_strategy import (
    HaltonSearchStrategy,
    SearchStrategy,
    _first_primes,
    _halton_value,
    _radical_inverse,
)
from .scale_adaptive_search_strategy import ScaleAdaptiveSearchStrategy

__all__ = [
    "SearchStrategy",
    "HaltonSearchStrategy",
    "ScaleAdaptiveSearchStrategy",
    "_first_primes",
    "_radical_inverse",
    "_halton_value",
]
