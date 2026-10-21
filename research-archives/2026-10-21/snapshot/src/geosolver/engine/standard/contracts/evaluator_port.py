"""Protocol for evaluator operations used by pipeline stages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from geosolver.engine.standard.contracts.hard_feasibility_snapshot import (
    HardFeasibilitySnapshot,
)
from geosolver.engine.standard.evaluation.evaluate_answer_hp import HPAnswerEvaluation
from geosolver.engine.standard.evaluation.evaluate_float_residual import FloatResidualEvaluation
from geosolver.engine.standard.evaluation.evaluate_hp_residual import HPResidualEvaluation
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


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
        *,
        include_margins: bool = True,
    ) -> HardFeasibilitySnapshot:
        """Evaluate hard-feasibility checks in float mode."""

    def evaluate_hp_hard_feasibility(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
        include_margins: bool = True,
    ) -> HardFeasibilitySnapshot:
        """Evaluate hard-feasibility checks in high-precision mode."""
