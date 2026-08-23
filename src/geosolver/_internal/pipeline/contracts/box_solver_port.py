"""Protocol for bounded local solver backends."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from .branch_box import BranchBox
from .candidate_record import RefinementBatchResult
from .evaluator_port import EvaluatorPort
from .problem_bundle import ProblemBundle

TaskKind = Literal["solve", "optimize"]


@runtime_checkable
class BoxSolverPort(Protocol):
    """Box-solver contract used by solve/optimize orchestration."""

    def solve_boxes(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        boxes: tuple[BranchBox, ...],
        task_kind: TaskKind,
    ) -> RefinementBatchResult:
        """Solve one batch of branch boxes."""
