"""Build structured summary for external pipeline diagnostics."""

from __future__ import annotations

from dataclasses import asdict

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
    candidate_record,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus

from .assemble_exact_results import ExactAssemblyResult
from .run_initial_probe import InitialProbeResult


def _best_residual_text(result: RefinementBatchResult) -> str:
    best = mp.inf
    for candidate in result.candidates:
        if candidate.residual_norm_hp < best:
            best = candidate.residual_norm_hp
    if not mp.isfinite(best):
        return "inf"
    return str(best)


def _candidate_id(candidate: FloatCandidate | RefinedCandidate | None) -> int | None:
    if candidate is None or int(candidate.candidate_id) == -1:
        return None
    return int(candidate.candidate_id)


def _best_refined_candidate(
    refinement_result: RefinementBatchResult,
) -> RefinedCandidate | None:
    if not refinement_result.candidates:
        return None
    return min(refinement_result.candidates, key=lambda candidate: candidate.residual_norm_hp)


def _selected_refined_candidate(
    *,
    refinement_result: RefinementBatchResult,
    assembly_result: ExactAssemblyResult,
) -> RefinedCandidate | None:
    if assembly_result.accepted_candidates:
        return assembly_result.accepted_candidates[0]
    return _best_refined_candidate(refinement_result)


def _build_candidate_ledger(search_result: SearchBatchResult) -> list[dict[str, object]]:
    ledger: list[dict[str, object]] = []
    for index, candidate in enumerate(search_result.guard_feasible_ledger):
        entry: dict[str, object] = {
            "rank": index + 1,
            "ledger_rank": index + 1,
            "values": list(candidate.x_float),
            "score": float(candidate.score),
            "residual_norm": float(candidate.residual_norm_float),
            "guard_ok": bool(candidate.guard_ok),
            "hard_feasible": candidate.hard_feasible,
            "origin_seed": int(candidate.origin_seed),
            "origin_start_point_index": int(candidate.origin_start_point_index),
            "candidate_uid": candidate.candidate_uid,
            "origin_phase": candidate.origin_phase,
            "origin_backend": candidate.origin_backend,
            "hard_violation_tags": list(candidate.hard_violation_tags),
        }
        candidate_id = _candidate_id(candidate)
        if candidate_id is not None:
            entry["candidate_id"] = candidate_id
        if candidate.origin_box_index is not None:
            entry["origin_box_index"] = int(candidate.origin_box_index)
        if candidate.validity_margin_float is not None:
            entry["validity_margin"] = float(candidate.validity_margin_float)
        ledger.append(entry)
    return ledger


def _candidate_ids(candidates: tuple[RefinedCandidate, ...]) -> list[int]:
    ids: list[int] = []
    for candidate in candidates:
        candidate_id = _candidate_id(candidate)
        if candidate_id is not None:
            ids.append(candidate_id)
    return ids


def build_pipeline_summary(
    *,
    initial_probe_result: InitialProbeResult,
    search_result: SearchBatchResult,
    refinement_result: RefinementBatchResult,
    assembly_result: ExactAssemblyResult,
    rescue_search_summary: dict[str, object] | None = None,
    integer_fallback_summary: dict[str, object] | None = None,
    debug_candidates: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    """Build phase-level summary object."""
    rescue_summary = (
        dict(rescue_search_summary)
        if isinstance(rescue_search_summary, dict)
        else {
            "triggered": False,
            "box_count": 0,
            "rescued_candidate_count": 0,
            "best_residual": "inf",
            "elapsed_sec": 0.0,
            "remaining_budget_sec": None,
        }
    )
    integer_summary = (
        dict(integer_fallback_summary)
        if isinstance(integer_fallback_summary, dict)
        else {
            "triggered": False,
            "skip_reason": "not_attempted",
            "constraint_count": 0,
            "tuple_count": 0,
            "attempted_tuple_count": 0,
            "completed_enumeration": False,
            "best_residual": "inf",
            "accepted_count": 0,
            "solved_tuples": [],
            "elapsed_sec": 0.0,
            "remaining_budget_sec": None,
        }
    )
    search_summary: dict[str, object] = {
        "evaluation_count": search_result.evaluation_count,
        "failure_ratio": search_result.failure_ratio,
        "selected_candidates": len(search_result.candidates),
        "all_record_count": len(search_result.all_records),
        "guard_feasible_record_count": sum(
            1
            for candidate in search_result.all_records
            if (
                candidate.evaluation_status is EvaluationStatus.OK
                and candidate.guard_ok
                and candidate.hard_feasible
            )
        ),
        "guard_feasible_ledger_count": len(search_result.guard_feasible_ledger),
        "compact_candidate_count": len(search_result.candidates),
    }
    if search_result.search_diagnostics:
        search_summary.update(dict(search_result.search_diagnostics))
    local_start_events = search_summary.get("local_start_events")
    if isinstance(local_start_events, tuple | list):
        search_summary["local_start_events"] = list(local_start_events)
    selected_candidate = _selected_refined_candidate(
        refinement_result=refinement_result,
        assembly_result=assembly_result,
    )
    best_candidate_id = _candidate_id(selected_candidate)
    accepted_candidate_ids = _candidate_ids(assembly_result.accepted_candidates)
    summary = {
        "exact_candidate_records": [
            {
                "candidate": candidate_record(record.candidate),
                "exact_result": asdict(record.exact_result),
            }
            for record in assembly_result.candidate_records
        ],
        "verification_records": list(assembly_result.verification_records),
        "initial_probe": dict(initial_probe_result.metrics),
        "search": search_summary,
        "refinement": {
            "attempted_count": refinement_result.attempted_count,
            "converged_count": refinement_result.converged_count,
            "best_residual": _best_residual_text(refinement_result),
            "solver_name": refinement_result.solver_name,
            "hard_feasible_count": refinement_result.hard_feasible_count,
        },
        "exact_assembly": {
            "numeric_feasible_count": len(assembly_result.numeric_feasible_candidates),
            "accepted_count": len(assembly_result.accepted_candidates),
            "answer_values": list(assembly_result.answer_values),
            "rejected_false_positive_count": assembly_result.rejected_false_positive_count,
            "rejection_tags": list(assembly_result.rejection_tags),
        },
        "phase_rescue": rescue_summary,
        "phase_discrete_completion": integer_summary,
        "debug_candidates": list(debug_candidates),
        "candidate_ledger": _build_candidate_ledger(search_result),
        "best_candidate_id": best_candidate_id,
        "answer_source_candidate_id": best_candidate_id,
        "residual_source_candidate_id": best_candidate_id,
        "answer_extraction_candidate_ids": accepted_candidate_ids,
        "answer_candidates": accepted_candidate_ids,
        "answer_candidate_values": list(assembly_result.answer_values),
    }
    return summary
