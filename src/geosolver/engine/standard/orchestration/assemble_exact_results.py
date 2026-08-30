"""Finite Phase C: verified candidate revisions and completed exact descriptors."""

import time
from dataclasses import asdict, dataclass, replace

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.exact_assembly.classify_exact_requirement import (
    classify_exact_requirement,
)
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.runtime.deadline import timed_phase, uses_deadline

ACCEPTED_REFINEMENT_STATUSES = (
    "direct_evaluation",
    "target_reached",
    "stalled",
    # Optimizer termination is not a mathematical verdict. These records still
    # undergo the same independent verification, confirmation and exactification.
    "max_iters",
    "deadline_reached",
    "line_search_failed",
)


@dataclass(frozen=True)
class ExactCandidateRecord:
    candidate: RefinedCandidate
    exact_result: ExactIdentificationResult

    @property
    def exact_identified(self):
        return (
            self.exact_result.selected_exact_value is not None
            and self.exact_result.descriptor is not None
        )


@dataclass(frozen=True)
class ExactAssemblyResult:
    numeric_feasible_candidates: tuple[RefinedCandidate, ...]
    accepted_candidates: tuple[RefinedCandidate, ...]
    exact_results: tuple[ExactIdentificationResult, ...]
    candidate_records: tuple[ExactCandidateRecord, ...]
    answer_values: tuple[str, ...]
    rejected_false_positive_count: int
    rejection_tags: tuple[str, ...]
    verification_records: tuple[dict[str, object], ...] = ()

    def updated_candidates(self, original):
        latest = {
            candidate.candidate_id: candidate for candidate in self.numeric_feasible_candidates
        }
        return tuple(latest.get(candidate.candidate_id, candidate) for candidate in original)


def _candidate_rejection_tag(*, candidate):
    if any(not mp.isfinite(value) for value in candidate.x_hp):
        return "coordinate_non_finite"
    if candidate.refinement_status == "deadline_reached":
        # An interrupted refinement may only have coordinates. Recompute every
        # numerical quantity in final verification; never publish draft values.
        return None
    if candidate.answer_hp is None:
        return "answer_missing"
    if not mp.isfinite(candidate.answer_hp):
        return "answer_non_finite"
    if not mp.isfinite(candidate.residual_norm_hp):
        return "residual_non_finite"
    if candidate.refinement_status not in ACCEPTED_REFINEMENT_STATUSES:
        return f"status_not_allowed:{candidate.refinement_status}"
    return None


def _revise(candidate, verification):
    # Never round the newly computed value through the ambient mp.dps.
    return replace(
        candidate,
        x_hp=verification.values,
        answer_hp=verification.answer_hp,
        revision=candidate.revision + 1,
        coordinate_precision_dps=verification.precision_dps,
        answer_precision_dps=verification.precision_dps,
        coordinate_uncertainty=verification.coordinate_uncertainty,
        answer_uncertainty=verification.answer_uncertainty,
        branch_trace=verification.branch_trace,
        verification_history=(*candidate.verification_history, asdict(verification)),
        residual_norm_hp=verification.residual_norm,
        hard_feasible=True,
        hard_violation_tags=(),
        validity_margin_hp=verification.min_margin,
    )


@timed_phase("exact_assembly")
@uses_deadline
def assemble_exact_results(
    *, refined_candidates, evaluator, input_precision_dps=120, deadline_monotonic=None
):
    rejection_tags, numeric, records, verifications = [], [], [], []
    # Complete each candidate atomically before the deadline; previously completed
    # descriptors survive a later candidate's symbolic timeout.
    for original in sorted(refined_candidates, key=lambda c: c.residual_norm_hp):
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            rejection_tags.append("deadline_before_verification")
            break
        tag = _candidate_rejection_tag(candidate=original)
        if tag:
            rejection_tags.append(tag)
            verifications.append(
                {"candidate_id": original.candidate_id, "status": tag, "verified": False}
            )
            continue
        cache_key = (
            original.candidate_uid,
            original.candidate_id,
            original.revision,
            tuple(v._mpf_ for v in original.x_hp),
            None if original.answer_hp is None else original.answer_hp._mpf_,
            original.coordinate_precision_dps,
            original.answer_precision_dps,
            classify_exact_requirement(original),
            int(input_precision_dps),
        )
        cache = evaluator.exact_candidate_cache
        if cache_key in cache:
            record = cache[cache_key]
            numeric.append(record.candidate)
            records.append(record)
            verifications.extend(
                {"candidate_id": original.candidate_id, **item}
                for item in record.candidate.verification_history
            )
            continue
        try:
            verification = verify_final_candidate(evaluator=evaluator, values=original.x_hp)
        except TimeoutError:
            rejection_tags.append("deadline_during_verification")
            break
        verifications.append({"candidate_id": original.candidate_id, **asdict(verification)})
        if not verification.verified:
            rejection_tags.extend((verification.status, *verification.hard_failure_tags))
            continue
        candidate = _revise(original, verification)
        numeric.append(candidate)
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            rejection_tags.append("deadline_before_exactification")
            break
        try:
            from geosolver.problem.ir.compiler import extract_names

            source = evaluator.bundle.spec.answer_expr
            closed = source and set(extract_names(source)) <= {
                "sqrt",
                "sin",
                "cos",
                "tan",
                "pi",
                "abs",
                "Abs",
            }
            if not closed:
                p = candidate.coordinate_precision_dps
                schedule = tuple(d for d in (250, 350, 500) if d > p)
                if len(schedule) == 1:
                    schedule = (p, schedule[0])
                if len(schedule) >= 2:
                    confirmation = verify_final_candidate(
                        evaluator=evaluator, values=candidate.x_hp, precision_schedule=schedule
                    )
                    verifications.append(
                        {"candidate_id": original.candidate_id, **asdict(confirmation)}
                    )
                    if not confirmation.verified:
                        rejection_tags.append("independent_confirmation_unresolved")
                        continue
                    candidate = _revise(candidate, confirmation)
                    numeric[-1] = candidate
            result = identify_answer(
                answer_hp=candidate.answer_hp,
                tier=classify_exact_requirement(candidate),
                input_precision_dps=candidate.answer_precision_dps,
                answer_uncertainty=candidate.answer_uncertainty,
                closed_source=source if closed else None,
            )
            record = ExactCandidateRecord(candidate, result)
            records.append(record)
            cache[cache_key] = record
        except TimeoutError:
            rejection_tags.append("deadline_during_exactification")
            break
        except (ValueError, ArithmeticError) as error:
            rejection_tags.append(f"exactification_unresolved:{type(error).__name__}")
    accepted = tuple(record for record in records if record.exact_identified)
    failures = len(records) - len(accepted)
    if failures:
        rejection_tags.append("exactification_failed")
    return ExactAssemblyResult(
        tuple(numeric),
        tuple(r.candidate for r in accepted),
        tuple(r.exact_result for r in records),
        tuple(records),
        tuple(r.exact_result.selected_exact_value for r in accepted),
        len(refined_candidates) - len(numeric) + failures,
        tuple(dict.fromkeys(rejection_tags)),
        tuple(verifications),
    )
