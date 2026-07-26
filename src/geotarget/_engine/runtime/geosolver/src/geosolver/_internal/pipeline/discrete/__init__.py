"""Discrete structure handlers for the external solver pipeline.

The preferred names use "completion" rather than "fallback": these strategies
are general finite-branch mechanisms triggered by IR structure.
"""

from .integer_targets import (
    IntegerTargetObservation,
    default_discrete_completion_summary,
    default_integer_fallback_summary,
    run_discrete_target_completion,
    run_integer_target_fallback,
)

__all__ = [
    "IntegerTargetObservation",
    "default_discrete_completion_summary",
    "default_integer_fallback_summary",
    "run_discrete_target_completion",
    "run_integer_target_fallback",
]
