"""Branch decision dataclass."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchDecision:
    """A single branch decision at a selector point.

    Args:
        selector_index: Index of the selector in the problem.
        branch_index: Which branch was chosen (0, 1, ...).
        kind: Type of selector (e.g., "near", "far", "exclude").
    """

    selector_index: int
    branch_index: int
    kind: str = ""
