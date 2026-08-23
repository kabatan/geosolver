"""Problem-structure-driven pipeline strategies.

This facade collects reusable strategies that are allowed to inspect geometric
IR structure, but not problem IDs, benchmark names, known answers, or historical
failure signatures.
"""

from geosolver._internal.pipeline.completion import (
    default_rescue_completion_summary,
    merge_search_candidates_with_rescue,
    phasec_needs_completion,
)
from geosolver._internal.pipeline.discrete import (
    IntegerTargetObservation,
    default_discrete_completion_summary,
    run_discrete_target_completion,
)
from geosolver._internal.pipeline.sampling import (
    DistanceCircleSampler,
    ManifoldSampleResult,
    ManifoldSampleStrategy,
    augment_with_manifold_samples,
)

__all__ = [
    "DistanceCircleSampler",
    "IntegerTargetObservation",
    "ManifoldSampleResult",
    "ManifoldSampleStrategy",
    "augment_with_manifold_samples",
    "default_discrete_completion_summary",
    "default_rescue_completion_summary",
    "merge_search_candidates_with_rescue",
    "phasec_needs_completion",
    "run_discrete_target_completion",
]
