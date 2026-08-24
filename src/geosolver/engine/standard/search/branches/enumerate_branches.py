"""Enumerate all possible branch signature combinations."""

from __future__ import annotations

import itertools

from geosolver.engine.standard.search.branches.branch_decision import BranchDecision
from geosolver.engine.standard.search.branches.branch_signature import BranchSignature


def enumerate_branch_signatures(
    *,
    selector_count: int,
    selector_kinds: list[str] | None = None,
    branches_per_selector: int | list[int] = 2,
) -> list[BranchSignature]:
    """Enumerate all branch signature combinations.

    Args:
        selector_count: Number of selectors in the problem.
        selector_kinds: Kind label for each selector.
        branches_per_selector: Number of branches per selector (uniform int
            or per-selector list).

    Returns:
        List of all possible BranchSignature combinations.
    """
    if selector_count <= 0:
        return [BranchSignature()]

    if selector_kinds is None:
        selector_kinds = [""] * selector_count

    if isinstance(branches_per_selector, int):
        per_selector = [branches_per_selector] * selector_count
    else:
        per_selector = list(branches_per_selector)
        while len(per_selector) < selector_count:
            per_selector.append(2)

    ranges = [range(per_selector[i]) for i in range(selector_count)]
    signatures: list[BranchSignature] = []
    for combo in itertools.product(*ranges):
        decisions = tuple(
            BranchDecision(
                selector_index=i,
                branch_index=combo[i],
                kind=selector_kinds[i] if i < len(selector_kinds) else "",
            )
            for i in range(selector_count)
        )
        signatures.append(BranchSignature(decisions=decisions))
    return signatures
