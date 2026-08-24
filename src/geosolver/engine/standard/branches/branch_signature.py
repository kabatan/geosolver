"""Branch signature for identifying solution branches."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.branches.branch_decision import BranchDecision


@dataclass(frozen=True)
class BranchSignature:
    """Identifies a unique combination of branch decisions.

    Args:
        decisions: Ordered tuple of branch decisions.
    """

    decisions: tuple[BranchDecision, ...] = ()

    def signature_key(self) -> str:
        """Return a string key for hashing/comparison."""
        parts = [
            f"{d.selector_index}:{d.branch_index}"
            for d in self.decisions
        ]
        return "|".join(parts) if parts else "default"
