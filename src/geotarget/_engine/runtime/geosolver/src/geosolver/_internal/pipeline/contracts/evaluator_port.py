"""Protocol for evaluator operations used by pipeline stages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from geosolver._internal.pipeline.contracts.hard_feasibility_snapshot import (
    HardFeasibilitySnapshot,
)
from geosolver._internal.pipeline.evaluator.evaluate_answer_hp import HPAnswerEvaluation
from geosolver._internal.pipeline.evaluator.evaluate_float_residual import FloatResidualEvaluation
from geosolver._internal.pipeline.evaluator.evaluate_hp_residual import HPResidualEvaluation
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat


class EvaluatorPort(Protocol):
    """Evaluator contract consumed by search/refine/exact layers."""

    def evaluate_float_residual(self, values: Sequence[float]) -> FloatResidualEvaluation:
        """Evaluate residual in float precision."""

    def evaluate_hp_residual(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
    ) -> HPResidualEvaluation:
        """Evaluate residual in high precision."""

    def evaluate_answer_hp(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
    ) -> HPAnswerEvaluation:
        """Evaluate answer expression in high precision."""

    def evaluate_guard(self, values: Sequence[object]) -> tuple[bool, tuple[str, ...]]:
        """Evaluate hard guards for a candidate."""

    def evaluate_float_hard_feasibility(
        self,
        values: Sequence[float],
    ) -> HardFeasibilitySnapshot:
        """Evaluate hard-feasibility checks in float mode."""

    def evaluate_hp_hard_feasibility(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
    ) -> HardFeasibilitySnapshot:
        """Evaluate hard-feasibility checks in high-precision mode."""

