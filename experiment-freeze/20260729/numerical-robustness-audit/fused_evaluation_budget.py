"""Audit-only fused EvaluationBudget preserving frozen field semantics."""

from __future__ import annotations

import math
import sys
from typing import Any

import numpy as np
from mpmath import mp

from geosolver._internal.autosolve.execution.interpreter_helpers import _build_guard_context
from geosolver._internal.autosolve.answer.precision_schedule import MIN_PRECISION
from geosolver._internal.autosolve.guards.compile import (
    guard_hard_satisfied,
    guard_violation_value,
)
from geosolver._internal.pipeline.evaluator._hard_feasibility_core import (
    evaluate_hard_feasibility,
)
from geosolver.ir.compiler import safe_eval_expr


def install(budget: Any) -> None:
    budget_class = type(budget)
    owner = sys.modules[budget_class.__module__]
    opaque_evaluation = owner.OpaqueEvaluation

    def fused(self: Any, point: np.ndarray):
        self._charge()
        values = np.asarray(point, dtype=float)
        try:
            evaluator = self.evaluator
            raw_values = values.tolist()
            observation = evaluator.evaluate_float_residual(raw_values)
            residual = np.asarray(observation.residual_vector, dtype=float)
            finite = bool(
                observation.is_finite
                and residual.shape == (self.residual_dimension,)
                and np.all(np.isfinite(residual))
            )

            target_dps = max(int(mp.dps), MIN_PRECISION, 80)
            with mp.workdps(target_dps):
                context = _build_guard_context(
                    evaluator.bundle.spec,
                    list(evaluator.bundle.var_names),
                    raw_values,
                    dict(evaluator.bundle.base_context),
                )
                violations: list[str] = []
                penalty = mp.mpf("0")
                vector_values: list[float] = []
                vector_failed = False
                for index, guard in enumerate(evaluator.compiled_guards):
                    try:
                        if not guard_hard_satisfied(guard, context):
                            violations.append(f"guard[{index}] returned False")
                    except Exception as error:
                        violations.append(f"guard[{index}] raised: {error}")
                    try:
                        value = guard_violation_value(guard, context)
                        if mp.isfinite(value):
                            penalty += value
                            vector_values.append(float(value))
                        else:
                            penalty += mp.mpf("1")
                            vector_values.append(1.0)
                    except Exception:
                        penalty += mp.mpf("1")
                        vector_failed = True
                        vector_values.append(1.0)

            guard_ok = len(violations) == 0
            guard_penalty = float(penalty)
            guard_vector = (
                np.ones(len(evaluator.compiled_guards), dtype=float)
                if vector_failed
                else np.asarray(vector_values, dtype=float)
            )
            hard = evaluate_hard_feasibility(
                bundle=evaluator.bundle,
                checks=evaluator.bundle.hard_feasibility_checks,
                values=raw_values,
                eval_expr=safe_eval_expr,
                cast_value=float,
                allow_float=True,
                guard_ok=guard_ok,
                guard_violations=tuple(violations),
            )
            semantics = bool(guard_ok and hard.hard_feasible)
            hard_penalty = 0.0
            if not hard.hard_feasible:
                margin = getattr(hard, "min_margin", None)
                hard_penalty = (
                    max(0.0, -float(margin))
                    if margin is not None and math.isfinite(float(margin))
                    else 1.0
                )
            violation_vector = np.concatenate(
                (guard_vector, np.asarray([hard_penalty], dtype=float))
            )
            violation = guard_penalty + hard_penalty
        except Exception:
            residual = np.full(self.residual_dimension, math.inf)
            finite = False
            semantics = False
            violation = 1.0
            violation_vector = np.ones(1, dtype=float)
        if finite:
            self.finite += 1
            self.best_norm = min(
                self.best_norm, float(np.linalg.norm(residual, ord=np.inf))
            )
        else:
            self.invalid += 1
        if finite and not semantics:
            self.guard_failed += 1
        return opaque_evaluation(
            residual=residual,
            finite=finite,
            semantics_valid=semantics,
            violation=max(0.0, float(violation)),
            violation_vector=np.maximum(0.0, violation_vector),
        )

    budget_class.__call__ = fused
