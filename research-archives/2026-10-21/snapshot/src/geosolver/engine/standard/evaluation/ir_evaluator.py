"""Unified evaluator object for external pipeline phases."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.evaluation.guard_penalty import collect_guard_violations
from geosolver.engine.standard.interpreter.guards.compile import GuardIR
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.problem.compile_problem_guards import compile_problem_guards
from geosolver.runtime.deadline import counted

from .evaluate_answer_hp import HPAnswerEvaluation, evaluate_answer_hp
from .evaluate_float_hard_feasibility import evaluate_float_hard_feasibility
from .evaluate_float_residual import FloatResidualEvaluation, evaluate_float_residual
from .evaluate_hp_hard_feasibility import evaluate_hp_hard_feasibility
from .evaluate_hp_residual import HPResidualEvaluation, evaluate_hp_residual
from .snapshots import EvaluationStore, uses_evaluation_store


@dataclass(frozen=True)
class IREvaluator:
    """Evaluator API for residual, answer, and guard checks."""

    bundle: ProblemBundle
    compiled_guards: tuple[GuardIR, ...]
    shared_store: EvaluationStore | None = None

    @cached_property
    def evaluation_store(self):
        return self.shared_store if self.shared_store is not None else EvaluationStore(self.bundle)

    @cached_property
    def verification_equations(self):
        from geosolver.engine.standard.evaluation.verification_numerics import prepare_equations

        return prepare_equations(self)

    @cached_property
    def domain_expressions(self):
        """Original equations and the answer, not alternative logical branches."""
        spec = self.bundle.spec
        logical = frozenset(source for plan in spec.logical_plans for source in plan.components)
        return tuple(
            dict.fromkeys(
                [
                    *(source for source in spec.constraints if source not in logical),
                    *(value for value in self.bundle.targets if isinstance(value, str)),
                    *(source for source in (spec.answer_expr, spec.objective_expr) if source),
                ]
            )
        )

    @cached_property
    def exact_candidate_cache(self):
        return {}

    @cached_property
    def final_verification_cache(self):
        return OrderedDict()

    @cached_property
    def verified_coordinate_cache(self):
        """Completed successful verification at exact coordinates and precision."""
        return OrderedDict()

    @cached_property
    def exact_value_registry(self):
        return {}

    @cached_property
    def probe_cache(self):
        return {}

    @cached_property
    def active_verification_columns(self):
        return tuple(
            j
            for j, name in enumerate(self.bundle.var_names)
            if any(e.constant is None and name in e.names for e in self.verification_equations)
        )

    @counted
    @uses_evaluation_store("self")
    def evaluate_float_residual(self, values: Sequence[float]) -> FloatResidualEvaluation:
        return evaluate_float_residual(bundle=self.bundle, values=list(values))

    @counted
    @uses_evaluation_store("self")
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

    @counted
    @uses_evaluation_store("self")
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

    @counted
    @uses_evaluation_store("self")
    def evaluate_guard(self, values: Sequence[object]) -> tuple[bool, tuple[str, ...]]:
        violations = collect_guard_violations(
            list(values),
            spec=self.bundle.spec,
            var_names=list(self.bundle.var_names),
            base_context=dict(self.bundle.base_context),
            compiled_guards=self.compiled_guards,
        )
        return (len(violations) == 0), tuple(violations)

    @counted
    @uses_evaluation_store("self")
    def evaluate_float_hard_feasibility(
        self,
        values: Sequence[float],
        *,
        include_margins: bool = True,
        guard_evidence=None,
    ):
        return evaluate_float_hard_feasibility(
            bundle=self.bundle,
            values=list(values),
            include_margins=bool(include_margins),
            compiled_guards=self.compiled_guards,
            guard_evidence=guard_evidence,
        )

    @counted
    @uses_evaluation_store("self")
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
            compiled_guards=self.compiled_guards,
        )


def build_ir_evaluator(bundle: ProblemBundle, *, evaluation_store=None) -> IREvaluator:
    """Build evaluator with precompiled guards."""
    return IREvaluator(
        bundle=bundle,
        compiled_guards=compile_problem_guards(bundle),
        shared_store=evaluation_store,
    )
