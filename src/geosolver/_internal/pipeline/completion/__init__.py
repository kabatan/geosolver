"""Completion strategies run after the primary search/refinement pass."""

from .rescue import (
    default_rescue_completion_summary,
    merge_search_candidates_with_rescue,
    phasec_needs_completion,
)

__all__ = [
    "default_rescue_completion_summary",
    "merge_search_candidates_with_rescue",
    "phasec_needs_completion",
]
