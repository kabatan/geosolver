"""Phase B orchestration for high-precision refinement."""

from __future__ import annotations

from geosolver.engine.standard.contracts.candidate_record import (
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

