"""Protocol for local high-precision refiner adapters."""

from __future__ import annotations

from typing import Protocol

from .candidate_record import FloatCandidate, RefinementBatchResult
from .evaluator_port import EvaluatorPort
from .problem_bundle import ProblemBundle


class LocalRefinerPort(Protocol):
    """High-precision local-refinement contract."""

    def refine_candidates(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidates: tuple[FloatCandidate, ...],
    ) -> RefinementBatchResult:
        """Refine float candidates into high-precision candidates."""

