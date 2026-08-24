"""Extract branch signature for a high-precision solution point."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from geosolver.engine.standard.search.branches.branch_decision import BranchDecision
from geosolver.engine.standard.search.branches.branch_signature import BranchSignature
from geosolver.engine.standard.refinement.optimization.mp.mp_residual_vector import mp_residual_vector
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


def extract_branch_signature(
    *,
    f_hp: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    point: list[MPFloat],
) -> BranchSignature:
    """Evaluate a point once and extract selector decisions as a signature.

    Args:
        f_hp: High-precision constraint function.
        targets: Constraint targets.
        point: Candidate point in high precision.

    Returns:
        BranchSignature built from the selector trace at this point.
        If no selectors are encountered, returns the default signature.
    """
    from geosolver.geometry.mp.mp_primitives_intersections import capture_selector_trace

    with capture_selector_trace() as trace:
        mp_residual_vector(f=f_hp, targets=targets, x=point)

    if not trace.entries:
        return BranchSignature()

    decisions = tuple(
        BranchDecision(
            selector_index=index,
            branch_index=int(entry.branch_index),
            kind=str(entry.kind),
        )
        for index, entry in enumerate(trace.entries)
    )
    return BranchSignature(decisions=decisions)
