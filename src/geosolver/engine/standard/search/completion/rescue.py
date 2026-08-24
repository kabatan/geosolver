"""Generic completion helpers for under-covered candidate sets.

The rescue pass is expressed here as a completion strategy: it is triggered by
Phase C coverage/stability signals, not by problem IDs or case-specific failure
signatures.
"""

from __future__ import annotations

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    SearchBatchResult,
)
from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget

_STABLE_ACCEPTED_STATUSES = ("target_reached", "box_solved", "box_enumerated")


def exact_assembly_needs_completion(accepted_candidates: tuple[RefinedCandidate, ...]) -> bool:
    """Return whether Phase C evidence is too weak to stop the pipeline."""

    if not accepted_candidates:
        return True
    return all(
        candidate.refinement_status not in _STABLE_ACCEPTED_STATUSES
        for candidate in accepted_candidates
    )


def default_rescue_completion_summary(
    *,
    runtime_budget: RuntimeBudget,
    triggered: bool = False,
    box_count: int = 0,
    rescued_candidate_count: int = 0,
    best_residual: object = "inf",
    elapsed_sec: float = 0.0,
    skip_reason: str | None = None,
) -> dict[str, object]:
    """Create a stable summary schema for rescue-style completion."""

    return {
        "strategy_id": "candidate_space_rescue",
        "completion_type": "guard_feasible_box_search",
        "triggered": bool(triggered),
        "skip_reason": skip_reason,
        "box_count": int(box_count),
        "rescued_candidate_count": int(rescued_candidate_count),
        "best_residual": best_residual,
        "elapsed_sec": float(elapsed_sec),
        "remaining_budget_sec": runtime_budget.remaining_sec(),
    }


def merge_search_candidates_with_rescue(
    *,
    search_result: SearchBatchResult,
    rescued_candidates: tuple[FloatCandidate, ...],
) -> SearchBatchResult:
    """Append rescue candidates without duplicating candidate IDs."""

    merged_candidates = list(search_result.candidates)
    seen = {candidate.candidate_id for candidate in merged_candidates}
    for rescued in rescued_candidates:
        if rescued.candidate_id in seen:
            continue
        merged_candidates.append(rescued)
        seen.add(rescued.candidate_id)
    merged_all_records = tuple(search_result.all_records) + tuple(rescued_candidates)
    return SearchBatchResult(
        candidates=tuple(merged_candidates),
        evaluation_count=search_result.evaluation_count + len(rescued_candidates),
        failure_ratio=search_result.failure_ratio,
        all_records=merged_all_records,
        guard_feasible_ledger=search_result.guard_feasible_ledger,
        search_diagnostics=search_result.search_diagnostics,
    )
