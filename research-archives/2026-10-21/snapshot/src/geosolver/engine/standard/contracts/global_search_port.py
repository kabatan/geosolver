"""Protocol for global-search backend adapters."""

from __future__ import annotations

from typing import Protocol

from .candidate_record import SearchBatchResult
from .evaluator_port import EvaluatorPort
from .problem_bundle import ProblemBundle


class GlobalSearchPort(Protocol):
    """Global-search contract."""

    def run_search(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        bounds: list[tuple[float, float]],
        search_mode: str = "disco_mads",
        guard_feasible_prefix_count: int | None = None,
    ) -> SearchBatchResult:
        """Run global search and return float candidates."""
