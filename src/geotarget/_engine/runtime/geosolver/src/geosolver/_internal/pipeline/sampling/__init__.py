"""Sampling strategies used before global search.

This package keeps structure-aware start generation out of orchestration code.
Strategies must be driven by geometry/IR structure only; they must not inspect
problem identifiers, benchmark names, or expected answers.
"""

from .manifold import (
    DistanceCircleSampler,
    ManifoldSampleResult,
    ManifoldSampleStrategy,
    augment_with_manifold_samples,
)

__all__ = [
    "DistanceCircleSampler",
    "ManifoldSampleResult",
    "ManifoldSampleStrategy",
    "augment_with_manifold_samples",
]
