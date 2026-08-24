"""Cluster solutions into families by answer value."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.families.solution_family import SolutionFamily


def cluster_solutions_into_families(
    *,
    solutions: list[list[MPFloat]],
    residuals: list[MPFloat],
    answer_values: Sequence[MPFloat] | None = None,
    answer_fn: Callable[[list[MPFloat]], MPFloat] | None = None,
    branch_signatures: Sequence[str] | None = None,
    cluster_tolerance: MPFloat | None = None,
) -> list[SolutionFamily]:
    """Cluster solutions into families by answer value.

    Args:
        solutions: List of solution points.
        residuals: Corresponding residual norms.
        answer_values: Optional precomputed answer values.
        answer_fn: Function to extract answer value from a solution.
            If None, uses the first variable.
        branch_signatures: Optional branch signature key per solution.
        cluster_tolerance: Maximum distance for same-family answer values.

    Returns:
        List of SolutionFamily instances, sorted by best residual.
    """
    if not solutions:
        return []

    if cluster_tolerance is None:
        cluster_tolerance = mp.mpf("1e-6")

    families: list[SolutionFamily] = []
    for i, solution in enumerate(solutions):
        if answer_values is not None and i < len(answer_values):
            answer = answer_values[i]
        elif answer_fn is not None:
            answer = answer_fn(solution)
        else:
            answer = solution[0]
        residual = residuals[i] if i < len(residuals) else mp.mpf("inf")
        branch_signature = (
            branch_signatures[i]
            if branch_signatures is not None and i < len(branch_signatures)
            else None
        )

        matched = False
        for family in families:
            same_branch = family.branch_signature == branch_signature
            if abs(answer - family.answer_cluster) <= cluster_tolerance:
                if family.branch_signature is not None or branch_signature is not None:
                    if not same_branch:
                        continue
                family.members.append(solution)
                if residual < family.best_residual:
                    family.best_residual = residual
                    family.representative = list(solution)
                matched = True
                break

        if not matched:
            families.append(SolutionFamily(
                family_id=len(families),
                answer_cluster=answer,
                members=[solution],
                best_residual=residual,
                representative=list(solution),
                branch_signature=branch_signature,
            ))

    families.sort(key=lambda f: f.best_residual)
    return families
