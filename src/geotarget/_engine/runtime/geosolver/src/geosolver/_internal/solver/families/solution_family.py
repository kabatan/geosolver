"""Solution family dataclass for grouping related solutions."""

from __future__ import annotations

from dataclasses import dataclass, field

from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


@dataclass
class SolutionFamily:
    """A group of solutions that belong to the same family.

    Members share similar answer values (clustering) and/or
    branch signatures.

    Args:
        family_id: Unique family identifier.
        answer_cluster: Representative answer value for this family.
        members: Solution points in this family.
        best_residual: Best constraint residual among members.
        representative: Best solution in this family.
        branch_signature: Optional branch signature key.
    """

    family_id: int
    answer_cluster: MPFloat
    members: list[list[MPFloat]] = field(default_factory=list)
    best_residual: MPFloat = field(default_factory=lambda: __import__("mpmath").mp.mpf("inf"))
    representative: list[MPFloat] | None = None
    branch_signature: str | None = None
