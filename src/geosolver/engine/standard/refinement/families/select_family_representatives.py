"""Select representative solutions from families."""

from __future__ import annotations

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.refinement.families.solution_family import SolutionFamily


def select_family_representatives(
    families: list[SolutionFamily],
    max_solutions: int,
) -> list[list[MPFloat]]:
    """Select one representative per family, up to max_solutions.

    Families are already sorted by best_residual. Takes the best
    representative from each family.

    Args:
        families: Sorted list of SolutionFamily.
        max_solutions: Maximum number of solutions to return.

    Returns:
        List of representative solution points.
    """
    result: list[list[MPFloat]] = []
    for family in families[:max_solutions]:
        if family.representative is not None:
            result.append(family.representative)
    return result
