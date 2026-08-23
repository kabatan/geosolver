"""Phase B orchestration for high-precision refinement."""

from __future__ import annotations

from geosolver._internal.pipeline.contracts.candidate_record import (
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver._internal.pipeline.contracts.evaluator_port import EvaluatorPort
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.refine.mpmath_refiner import MpmathRefiner


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

