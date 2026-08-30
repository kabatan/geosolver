"""Phase B orchestration for high-precision refinement."""

from __future__ import annotations

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner


def run_refinement(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    search_result: SearchBatchResult,
    refiner: MpmathRefiner,
    deadline_monotonic: float | None = None,
) -> RefinementBatchResult:
    """Run phase B refinement for selected float candidates."""
    return refiner.refine_candidates(
        bundle=bundle,
        evaluator=evaluator,
        candidates=search_result.candidates,
        deadline_monotonic=deadline_monotonic,
    )


def refine_added_candidates(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    candidates: tuple[FloatCandidate, ...],
    refiner: MpmathRefiner,
    deadline_monotonic: float | None = None,
) -> RefinementBatchResult:
    """Refine only candidates introduced by a completion strategy."""

    return refiner.refine_candidates(
        bundle=bundle,
        evaluator=evaluator,
        candidates=candidates,
        deadline_monotonic=deadline_monotonic,
    )


def merge_refinement_results(
    first: RefinementBatchResult,
    second: RefinementBatchResult,
) -> RefinementBatchResult:
    """Combine independent refinement batches without changing candidate order."""

    return RefinementBatchResult(
        candidates=tuple(first.candidates) + tuple(second.candidates),
        converged_count=int(first.converged_count) + int(second.converged_count),
        attempted_count=int(first.attempted_count) + int(second.attempted_count),
        solver_name=first.solver_name,
        hard_feasible_count=(int(first.hard_feasible_count) + int(second.hard_feasible_count)),
    )
