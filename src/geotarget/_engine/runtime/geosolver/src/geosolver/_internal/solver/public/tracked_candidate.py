"""Tracked candidate with stable identity for candidate-ID alignment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import itertools

_CANDIDATE_ID_COUNTER = itertools.count(1)


_VALID_SOURCES = frozenset({
    "seed",
    "optimized",
    "deduped",
    "ordered",
    "selected",
    "answer",
    "feasible",
    "solution",
    "best_pre_selector",
    "best_post_selector",
    "reported_solution",
})


@dataclass(frozen=True)
class TrackedCandidate:
    """A candidate with a stable ``candidate_id`` that follows it through the
    entire pipeline – from generation through ledger, selector, answer
    extraction, and final residual evaluation.

    ``source`` must be one of the fixed strings in ``_VALID_SOURCES``.
    """

    candidate_id: int
    values: list[Any]
    source: str

    def __post_init__(self) -> None:
        if self.source not in _VALID_SOURCES:
            raise ValueError(
                f"TrackedCandidate source must be one of {sorted(_VALID_SOURCES)}, "
                f"got {self.source!r}"
            )


def make_tracked(values: list[Any], *, source: str) -> TrackedCandidate:
    """Create a new ``TrackedCandidate`` with a globally unique ID."""
    return TrackedCandidate(
        candidate_id=next(_CANDIDATE_ID_COUNTER),
        values=list(values),
        source=source,
    )


def tracked_from_pool(
    pool: list[list[Any]],
    *,
    source: str,
) -> list[TrackedCandidate]:
    """Wrap a pool of raw value-lists into ``TrackedCandidate`` objects."""
    return [make_tracked(values, source=source) for values in pool]


def tracked_values(candidates: list[TrackedCandidate]) -> list[list[Any]]:
    """Extract the raw value-lists from a list of tracked candidates."""
    return [list(tc.values) for tc in candidates]


def with_source(candidate: TrackedCandidate, *, source: str) -> TrackedCandidate:
    """Return a copy with the same candidate_id/values and a different source."""
    return TrackedCandidate(
        candidate_id=candidate.candidate_id,
        values=list(candidate.values),
        source=source,
    )
