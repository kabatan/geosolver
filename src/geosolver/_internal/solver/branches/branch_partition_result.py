"""Container for branch-partitioned seed pools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from geosolver._internal.solver.branches.branch_signature import BranchSignature
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


@dataclass
class BranchPartitionResult:
    """Holds per-branch seed pools and associated diagnostics."""

    pools: dict[str, list[list[MPFloat]]] = field(default_factory=dict)
    signatures: list[BranchSignature] = field(default_factory=list)

    @property
    def pool_count(self) -> int:
        return len(self.pools)

    @property
    def total_seeds(self) -> int:
        return sum(len(seeds) for seeds in self.pools.values())
