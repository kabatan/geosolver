"""Phase C: assemble accepted candidates and run exact identification."""

from __future__ import annotations

from dataclasses import dataclass

from mpmath import mp

from geosolver._internal.pipeline.contracts.candidate_record import RefinedCandidate
from geosolver._internal.pipeline.contracts.pipeline_result import ExactIdentificationResult
from geosolver._internal.pipeline.exact.classify_exact_requirement import classify_exact_requirement
from geosolver._internal.pipeline.exact.identify_answer import identify_answer

ACCEPTANCE_RESIDUAL_THRESHOLD = mp.mpf("1e-15")
ACCEPTANCE_MARGIN_RATIO = mp.mpf("1e-8")
ANSWER_DEDUP_TOLERANCE = mp.mpf("1e-20")
ACCEPTED_REFINEMENT_STATUSES = (
    "direct_evaluation",
    "target_reached",
    "stalled",
    "box_solved",
    "box_enumerated",
)


@dataclass(frozen=True)
class PhaseCAssemblyResult:
    """Output of Phase C assembly."""

    accepted_candidates: tuple[RefinedCandidate, ...]
    exact_results: tuple[ExactIdentificationResult, ...]
    answer_values: tuple[str, ...]
    rejected_false_positive_count: int
    rejection_tags: tuple[str, ...]


def _candidate_rejection_tag(
    *,
    candidate: RefinedCandidate,
    residual_threshold: object,
    acceptance_margin_threshold: object,
) -> str | None:
    if candidate.answer_hp is None:
        return "answer_missing"
    if not mp.isfinite(candidate.answer_hp):
        return "answer_non_finite"
    if not mp.isfinite(candidate.residual_norm_hp):
        return "residual_non_finite"
    if candidate.residual_norm_hp >= mp.mpf(residual_threshold):
        return "residual_too_large"
    if not candidate.hard_feasible:
        return "hard_infeasible"
    if candidate.validity_margin_hp is not None and candidate.validity_margin_hp < mp.mpf(
        acceptance_margin_threshold
    ):
        return "margin_too_small"
    if candidate.refinement_status not in ACCEPTED_REFINEMENT_STATUSES:
        return f"status_not_allowed:{candidate.refinement_status}"
    return None


def _is_acceptable_candidate(
    candidate: RefinedCandidate,
    residual_threshold: object,
    acceptance_margin_threshold: object,
) -> bool:
    rejection_tag = _candidate_rejection_tag(
        candidate=candidate,
        residual_threshold=residual_threshold,
        acceptance_margin_threshold=acceptance_margin_threshold,
    )
    return rejection_tag is None


def _dedupe_accepted_candidates(
    candidates: tuple[RefinedCandidate, ...],
) -> tuple[RefinedCandidate, ...]:
    ordered = sorted(candidates, key=lambda candidate: candidate.residual_norm_hp)
    selected: list[RefinedCandidate] = []
    for candidate in ordered:
        if candidate.answer_hp is None:
            continue
        duplicate = False
        for existing in selected:
            if existing.answer_hp is None:
                continue
            if (
                abs(candidate.answer_hp - existing.answer_hp) <= ANSWER_DEDUP_TOLERANCE
                and candidate.hard_violation_tags == existing.hard_violation_tags
            ):
                duplicate = True
                break
        if not duplicate:
            selected.append(candidate)
    return tuple(selected)


def run_phasec_assembly(
    *,
    refined_candidates: tuple[RefinedCandidate, ...],
    input_precision_dps: int = 120,
    residual_threshold: object = ACCEPTANCE_RESIDUAL_THRESHOLD,
    acceptance_margin_ratio: object = ACCEPTANCE_MARGIN_RATIO,
) -> PhaseCAssemblyResult:
    """Assemble accepted answers and run exact identification for all of them."""
    acceptance_margin_threshold = mp.mpf(acceptance_margin_ratio)
    rejection_tags: list[str] = []
    accepted = tuple(
        candidate
        for candidate in refined_candidates
        if _is_acceptable_candidate(
            candidate,
            residual_threshold,
            acceptance_margin_threshold,
        )
    )
    for candidate in refined_candidates:
        rejection_tag = _candidate_rejection_tag(
            candidate=candidate,
            residual_threshold=residual_threshold,
            acceptance_margin_threshold=acceptance_margin_threshold,
        )
        if rejection_tag is not None:
            rejection_tags.append(rejection_tag)
    deduped = _dedupe_accepted_candidates(accepted)
    exact_results = tuple(
        identify_answer(
            answer_hp=candidate.answer_hp,
            tier=classify_exact_requirement(candidate),
            input_precision_dps=int(input_precision_dps),
        )
        for candidate in deduped
        if candidate.answer_hp is not None
    )
    # Build answer_values using exact identification when available,
    # falling back to full-precision numeric string.
    answer_value_set: dict[str, None] = {}
    candidates_with_hp = [c for c in deduped if c.answer_hp is not None]
    for idx, candidate in enumerate(candidates_with_hp):
        if idx < len(exact_results) and exact_results[idx].selected_exact_value is not None:
            val = exact_results[idx].selected_exact_value
        else:
            val = str(candidate.answer_hp)
        answer_value_set[val] = None
    answer_values = tuple(sorted(answer_value_set))
    return PhaseCAssemblyResult(
        accepted_candidates=deduped,
        exact_results=exact_results,
        answer_values=answer_values,
        rejected_false_positive_count=len(rejection_tags),
        rejection_tags=tuple(dict.fromkeys(rejection_tags)),
    )

