"""Classify exact-identification search tier for accepted candidates."""

from __future__ import annotations

from mpmath import mp

from geosolver._internal.pipeline.contracts.candidate_record import RefinedCandidate

STRICT_TIER = "strict"
STANDARD_TIER = "standard"
RELAXED_TIER = "relaxed"

STRICT_THRESHOLD = mp.mpf("1e-70")
STANDARD_THRESHOLD = mp.mpf("1e-55")


def classify_exact_requirement(candidate: RefinedCandidate) -> str:
    """Classify only the exact-search tier (not execute/no-execute decision)."""
    residual = candidate.residual_norm_hp
    if residual <= STRICT_THRESHOLD:
        return STRICT_TIER
    if residual <= STANDARD_THRESHOLD:
        return STANDARD_TIER
    return RELAXED_TIER

