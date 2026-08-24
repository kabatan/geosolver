"""Unified evaluator object for external pipeline phases."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from geosolver.engine.standard.interpreter.execution.interpreter_helpers import _collect_guard_violations
from geosolver.engine.standard.interpreter.guards.compile import GuardIR
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat

from geosolver.engine.standard.problem.compile_problem_guards import compile_problem_guards
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle

from .evaluate_float_hard_feasibility import evaluate_float_hard_feasibility
from .evaluate_hp_hard_feasibility import evaluate_hp_hard_feasibility
from .evaluate_answer_hp import HPAnswerEvaluation, evaluate_answer_hp
from .evaluate_float_residual import FloatResidualEvaluation, evaluate_float_residual
from .evaluate_hp_residual import HPResidualEvaluation, evaluate_hp_residual


@dataclass(frozen=True)
class IREvaluator:
    """Evaluator API for residual, answer, and guard checks."""

    bundle: ProblemBundle
    compiled_guards: tuple[GuardIR, ...]

    def evaluate_float_residual(self, values: Sequence[float]) -> FloatResidualEvaluation:
        return evaluate_float_residual(bundle=self.bundle, values=list(values))

    def evaluate_hp_residual(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
    ) -> HPResidualEvaluation:
        return evaluate_hp_residual(
            bundle=self.bundle,
            values=values,
            precision=int(precision),
        )

    def evaluate_answer_hp(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
    ) -> HPAnswerEvaluation:
        return evaluate_answer_hp(
            bundle=self.bundle,
            values=values,
            precision=int(precision),
        )

    def evaluate_guard(self, values: Sequence[object]) -> tuple[bool, tuple[str, ...]]:
        violations = _collect_guard_violations(
            list(values),
            spec=self.bundle.spec,
            var_names=list(self.bundle.var_names),
            base_context=dict(self.bundle.base_context),
            compiled_guards=self.compiled_guards,
        )
        return (len(violations) == 0), tuple(violations)

    def evaluate_float_hard_feasibility(
        self,
        values: Sequence[float],
        *,
        include_margins: bool = True,
    ):
        return evaluate_float_hard_feasibility(
            bundle=self.bundle,
            values=list(values),
            include_margins=bool(include_margins),
        )

    def evaluate_hp_hard_feasibility(
        self,
        values: Sequence[MPFloat],
        *,
        precision: int,
        include_margins: bool = True,
    ):
        return evaluate_hp_hard_feasibility(
            bundle=self.bundle,
            values=list(values),
            precision=int(precision),
            include_margins=bool(include_margins),
        )


def build_ir_evaluator(bundle: ProblemBundle) -> IREvaluator:
    """Build evaluator with precompiled guards."""
    return IREvaluator(
        bundle=bundle,
        compiled_guards=compile_problem_guards(bundle),
    )

