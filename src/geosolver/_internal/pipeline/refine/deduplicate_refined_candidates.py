"""Deduplicate refined high-precision candidates."""

from __future__ import annotations

from mpmath import mp

from geosolver._internal.pipeline.contracts.candidate_record import RefinedCandidate
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def deduplicate_refined_candidates(
    *,
    candidates: tuple[RefinedCandidate, ...],
    tolerance: MPFloat,
) -> tuple[RefinedCandidate, ...]:
    """Keep the best candidate for each near-equal answer value."""
    ordered = sorted(candidates, key=lambda candidate: candidate.residual_norm_hp)
    selected: list[RefinedCandidate] = []
    for candidate in ordered:
        if candidate.answer_hp is None:
            selected.append(candidate)
            continue
        duplicate = False
        for existing in selected:
            if existing.answer_hp is None:
                continue
            if abs(candidate.answer_hp - existing.answer_hp) <= tolerance:
                duplicate = True
                break
        if not duplicate:
            selected.append(candidate)
    return tuple(selected)

