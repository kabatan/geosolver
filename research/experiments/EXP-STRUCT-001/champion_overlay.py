"""Minimal endpoint-injection seam for the frozen Python champion.

The champion's search remains intact.  This overlay may append structurally
generated endpoint proposals immediately before the existing source replay.
The original replay, guard, hard-feasibility, HP, and exact-authority code then
retains sole admission and answer authority.
"""

from __future__ import annotations

import math
from typing import Callable, Mapping, Sequence

from block_structure import BlockTriangularPlan, extract_v15_structure


ProposalFactory = Callable[
    [Mapping[str, object], BlockTriangularPlan, tuple[tuple[float, ...], ...], float],
    Sequence[Sequence[float]],
]


def _search_points(endpoints: Sequence[object], dimension: int) -> tuple[tuple[float, ...], ...]:
    points: list[tuple[float, ...]] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, Mapping) or not isinstance(endpoint.get("point"), list):
            continue
        try:
            point = tuple(float(value) for value in endpoint["point"])
        except (TypeError, ValueError, OverflowError):
            continue
        if len(point) == dimension and all(math.isfinite(value) for value in point):
            points.append(point)
    return tuple(points)


def merge_block_proposals(
    document: Mapping[str, object],
    endpoints: Sequence[object],
    *,
    hard_deadline: float,
    proposal_factory: ProposalFactory,
    maximum_block_proposals: int = 4,
) -> tuple[tuple[object, ...], dict[str, object]]:
    """Append bounded proposals; never remove or reorder champion endpoints."""

    if maximum_block_proposals < 0:
        raise ValueError("maximum_block_proposals cannot be negative")
    structure = extract_v15_structure(document)
    plan = structure.plan
    original = tuple(endpoints)
    audit: dict[str, object] = {
        "applicable": plan.applicable,
        "reason": plan.reason,
        "block_count": len(plan.blocks),
        "maximum_block_size": plan.maximum_block_size,
        "baseline_endpoint_count": len(original),
        "baseline_endpoints_removed": 0,
        "baseline_endpoints_reordered": False,
        "block_proposals_presented_to_source_replay": 0,
        "source_replay_bypassed": False,
        "canonical_verifier_bypassed": False,
    }
    if not plan.applicable or maximum_block_proposals == 0:
        return original, audit

    starts = _search_points(original, plan.variable_count)
    if not starts:
        audit["proposal_skip_reason"] = "NO_FINITE_CHAMPION_ENDPOINT_START"
        return original, audit
    proposals = proposal_factory(document, plan, starts, hard_deadline)
    accepted_shape: list[dict[str, object]] = []
    seen = set(starts)
    for raw in proposals:
        if len(accepted_shape) >= maximum_block_proposals:
            break
        try:
            point = tuple(float(value) for value in raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            len(point) != plan.variable_count
            or not all(math.isfinite(value) for value in point)
            or point in seen
        ):
            continue
        seen.add(point)
        # Keep the exact raw endpoint wire shape consumed by the champion.
        accepted_shape.append({"point": list(point)})
    audit["block_proposals_presented_to_source_replay"] = len(accepted_shape)
    return (*original, *accepted_shape), audit


def install(
    champion,
    *,
    proposal_factory: ProposalFactory,
    mechanism_hash: str,
    maximum_block_proposals: int = 4,
):
    """Install the proposal seam on an already loaded frozen champion module.

    This function is intentionally separate from the dry worker.  A formal
    execution wrapper can install it only after pinning the champion closure
    and a concrete block solver.  The returned audit accessor is truth-free.
    """

    base = champion.BASE
    original_fresh = base._fresh_replay_candidates
    original_plan = base._plan
    last_audit: dict[str, object] = {}

    def fresh(document, endpoints, *, hard_deadline):
        merged, audit = merge_block_proposals(
            document,
            endpoints,
            hard_deadline=hard_deadline,
            proposal_factory=proposal_factory,
            maximum_block_proposals=maximum_block_proposals,
        )
        last_audit.clear()
        last_audit.update(audit)
        # This original function performs source residual/guard/hard-feasibility
        # replay.  Downstream champion HP and exact verification are untouched.
        return original_fresh(document, merged, hard_deadline=hard_deadline)

    def plan(**kwargs):
        document = kwargs.pop("_structure_document", None)
        value = original_plan(**kwargs)
        structure_summary: dict[str, object] = {"available": False}
        if isinstance(document, Mapping):
            structure = extract_v15_structure(document)
            structure_summary = {
                "available": True,
                "applicable": structure.plan.applicable,
                "reason": structure.plan.reason,
                "block_count": len(structure.plan.blocks),
                "maximum_block_size": structure.plan.maximum_block_size,
            }
        value.update(
            {
                "block_triangular_overlay": structure_summary,
                "block_triangular_mechanism_hash": mechanism_hash,
                "baseline_start_fraction": 1.0,
                "baseline_start_quota_at_least_half": True,
                "block_endpoint_authority": "PROPOSAL_ONLY_THEN_ORIGINAL_SOURCE_REPLAY",
                "original_canonical_and_exact_authority_unchanged": True,
            }
        )
        return value

    base._fresh_replay_candidates = fresh
    base._plan = plan
    return lambda: dict(last_audit)
