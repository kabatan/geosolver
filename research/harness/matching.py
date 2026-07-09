"""Match reported answers to distinct Gold target values without hidden epsilons."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    AnswerLevel,
    CaseInput,
    DomainKind,
    GoldTarget,
    MatchMode,
    ReportedAnswer,
    RunInput,
)


@dataclass(frozen=True, slots=True)
class RunEvaluation:
    """Safety and recall facts for one case/seed/budget run.

    Branch and boundary counts are diagnostic subsets of ``false_answer_count``;
    they must not be added to the level-specific counts a second time.
    """

    run_id: str
    case_id: str
    family_id: str
    seed: int
    budget_seconds: int
    strata: tuple[str, ...]
    domain_kind: DomainKind
    exact_eligible: bool
    gold_target_ids: frozenset[str]
    covered_validated_targets: frozenset[str]
    covered_exact_targets: frozenset[str]
    duplicate_validated_witnesses: int
    duplicate_exact_witnesses: int
    false_exact_count: int
    false_validated_count: int
    false_branch_count: int
    false_boundary_count: int
    false_guard_count: int
    ambiguous_target_count: int
    false_complete_count: int
    full_validated: bool
    full_exact: bool

    @property
    def false_answer_count(self) -> int:
        return self.false_exact_count + self.false_validated_count

    @property
    def safety_violation_count(self) -> int:
        """Disjoint release-blocking count (answers plus complete claims)."""

        return self.false_answer_count + self.false_complete_count


def _numerically_matches(case: CaseInput, answer: ReportedAnswer, target: GoldTarget) -> bool:
    if case.matching.mode is MatchMode.CERTIFIED_INTERVAL:
        return answer.interval.certified and answer.interval.overlaps(target.interval)

    tolerance = case.matching.tolerance
    assert tolerance is not None  # guaranteed by the strict parser
    # A broad interval must not pass merely because its midpoint is nearby.
    return (
        abs(answer.interval.midpoint - target.interval.midpoint) <= tolerance
        and answer.interval.width <= tolerance * 2
    )


def _branch_matches(answer: ReportedAnswer, target: GoldTarget) -> bool:
    return target.allowed_branches is None or answer.branch in target.allowed_branches


def evaluate_run(case: CaseInput, run: RunInput) -> RunEvaluation:
    """Evaluate one run against one case's distinct target-value truth.

    Matching uses only the case-declared certified-interval or tolerance rule.
    A second configuration for an already covered target is a duplicate witness,
    not another Gold target and not a false output.
    """

    if run.case_id != case.case_id:
        raise ValueError(
            f"run {run.run_id!r} references case {run.case_id!r}, expected {case.case_id!r}"
        )

    covered_validated: set[str] = set()
    covered_exact: set[str] = set()
    duplicate_validated = 0
    duplicate_exact = 0
    false_exact = 0
    false_validated = 0
    false_branch = 0
    false_boundary = 0
    false_guard = 0
    ambiguous_target = 0

    for answer in run.answers:
        numeric_candidates = [
            target for target in case.gold_targets if _numerically_matches(case, answer, target)
        ]
        candidates = [
            target for target in numeric_candidates if _branch_matches(answer, target)
        ]
        branch_wrong = bool(numeric_candidates) and not candidates
        ambiguous = len(candidates) > 1

        assurance_valid = (
            answer.configuration_validated
            and answer.guard_valid
            and answer.boundary_valid
            and (
                answer.level is AnswerLevel.VALIDATED
                or answer.target_identity_certified
            )
        )
        valid = len(candidates) == 1 and assurance_valid

        if not valid:
            if answer.level is AnswerLevel.EXACT:
                false_exact += 1
            else:
                false_validated += 1
            false_branch += int(branch_wrong)
            false_boundary += int(not answer.boundary_valid)
            false_guard += int(not answer.guard_valid)
            ambiguous_target += int(ambiguous)
            continue

        target_id = candidates[0].target_id
        if target_id in covered_validated:
            duplicate_validated += 1
        covered_validated.add(target_id)

        if answer.level is AnswerLevel.EXACT:
            if target_id in covered_exact:
                duplicate_exact += 1
            covered_exact.add(target_id)

    gold_ids = frozenset(target.target_id for target in case.gold_targets)
    false_answers = false_exact + false_validated
    full_validated = covered_validated == gold_ids and false_answers == 0
    full_exact = (
        case.exact_eligible and covered_exact == gold_ids and false_answers == 0
    )
    false_complete = int(
        run.claims_complete and (not run.coverage_certificate or not full_validated)
    )

    return RunEvaluation(
        run_id=run.run_id,
        case_id=case.case_id,
        family_id=case.family_id,
        seed=run.seed,
        budget_seconds=run.budget_seconds,
        strata=case.strata,
        domain_kind=case.domain_kind,
        exact_eligible=case.exact_eligible,
        gold_target_ids=gold_ids,
        covered_validated_targets=frozenset(covered_validated),
        covered_exact_targets=frozenset(covered_exact),
        duplicate_validated_witnesses=duplicate_validated,
        duplicate_exact_witnesses=duplicate_exact,
        false_exact_count=false_exact,
        false_validated_count=false_validated,
        false_branch_count=false_branch,
        false_boundary_count=false_boundary,
        false_guard_count=false_guard,
        ambiguous_target_count=ambiguous_target,
        false_complete_count=false_complete,
        full_validated=full_validated,
        full_exact=full_exact,
    )
