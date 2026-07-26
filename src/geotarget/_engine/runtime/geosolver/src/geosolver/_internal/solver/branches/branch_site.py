"""Data class describing a selector site in the constraint function."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchSite:
    """A single selector site discovered in the constraint IR / callable."""

    selector_index: int
    kind: str = ""
    branches: int = 2
