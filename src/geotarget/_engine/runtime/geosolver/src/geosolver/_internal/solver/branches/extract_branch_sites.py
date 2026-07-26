"""Extract selector sites from a constraint function by probing."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from mpmath import mp

from geosolver._internal.solver.branches.branch_site import BranchSite
from geosolver._internal.solver.branches.extract_branch_signature import (
    extract_branch_signature,
)
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


def extract_branch_sites(
    *,
    f_hp: Callable[[list[MPFloat]], Sequence[MPFloat]],
    targets: list[MPFloat],
    probe_points: list[list[MPFloat]],
) -> list[BranchSite]:
    """Discover selector sites by probing the constraint function.

    Evaluates ``f_hp`` at each probe point and records which selectors fire.
    Returns a list of unique ``BranchSite`` objects.
    """
    max_selectors = 0
    kind_map: dict[int, str] = {}

    for point in probe_points:
        try:
            sig = extract_branch_signature(
                f_hp=f_hp,
                targets=targets,
                point=point,
            )
            for decision in sig.decisions:
                idx = decision.selector_index
                if idx >= max_selectors:
                    max_selectors = idx + 1
                if idx not in kind_map and decision.kind:
                    kind_map[idx] = decision.kind
        except Exception:
            continue

    sites: list[BranchSite] = []
    for i in range(max_selectors):
        sites.append(BranchSite(
            selector_index=i,
            kind=kind_map.get(i, ""),
            branches=2,
        ))
    return sites
