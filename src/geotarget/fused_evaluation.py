"""Bit-identical callback fusion for the frozen champion evaluation budget.

The frozen search budget evaluates one V15 point through residual, guard,
hard-feasibility, guard-penalty and guard-vector paths.  The latter four paths
construct the same geometry context repeatedly.  This product adapter builds
that context once while preserving the original field values, exception
policy, counter updates and exact-authority boundary.

This module never selects by problem identity or corpus membership.  It first
attests the frozen method it is replacing and fails closed if that execution
contract changes.
"""

from __future__ import annotations

import hashlib
import inspect
import math
import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np
from mpmath import mp

FUSION_SCHEMA_VERSION = "geotarget.fused-evaluation-budget/v1"
REFERENCE_CALL_SHA256 = (
    "6d96f00d46c51d2b6921534b1aa958150c1c098353e9f4e5603a10c52eaaa533"
)
REFERENCE_SOURCE_SUFFIX = (
    "solver/research/experiments/EXP-REAL61-007/"
    "provisional_numerical_architecture/source_only_runtime.py"
)
_MARKER = "__geotarget_fused_evaluation_schema__"
_ORIGINAL = "__geotarget_original_evaluation_call__"
_INSTALL_LOCK = threading.Lock()


def _source_sha256(function: Any) -> str:
    try:
        source = inspect.getsource(function).encode("utf-8")
    except (OSError, TypeError) as error:
        raise RuntimeError("frozen EvaluationBudget.__call__ source is unavailable") from error
    return hashlib.sha256(source).hexdigest()


def _attest_budget_class(budget_class: type[Any]) -> Any:
    if budget_class.__name__ != "EvaluationBudget":
        raise RuntimeError("unexpected frozen evaluation budget class")
    owner = sys.modules.get(budget_class.__module__)
    opaque_evaluation = getattr(owner, "OpaqueEvaluation", None)
    if owner is None or opaque_evaluation is None:
        raise RuntimeError("frozen OpaqueEvaluation authority is unavailable")
    original = budget_class.__call__
    if _source_sha256(original) != REFERENCE_CALL_SHA256:
        raise RuntimeError("frozen EvaluationBudget.__call__ hash mismatch")
    source_file = inspect.getsourcefile(original)
    if source_file is None or not Path(source_file).as_posix().endswith(
        REFERENCE_SOURCE_SUFFIX
    ):
        raise RuntimeError("frozen EvaluationBudget source path mismatch")
    return opaque_evaluation


def _fused_call_factory(opaque_evaluation: Any):
    # Imports remain lazy because the product wrapper is imported before the
    # isolated frozen geosolver tree is placed on sys.path.
    from geosolver._internal.autosolve.answer.precision_schedule import (
        MIN_PRECISION,
    )
    from geosolver._internal.autosolve.execution.interpreter_helpers import (
        _build_guard_context,
    )
    from geosolver._internal.autosolve.guards.compile import (
        guard_hard_satisfied,
        guard_margin_value,
        guard_violation_value,
    )
    from geosolver._internal.pipeline.evaluator._hard_feasibility_core import (
        evaluate_hard_feasibility,
    )
    from geosolver.ir.compiler import safe_eval_expr

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
                guard_margins: list[Any | None] = []
                guard_penalty_mpf = mp.mpf("0")
                guard_vector_values: list[float] = []
                guard_vector_failed = False
                for index, guard in enumerate(evaluator.compiled_guards):
                    try:
                        guard_satisfied = guard_hard_satisfied(guard, context)
                        if not guard_satisfied:
                            violations.append(f"guard[{index}] returned False")
                            guard_margins.append(None)
                        else:
                            guard_margins.append(guard_margin_value(guard, context))
                    except Exception as error:
                        violations.append(f"guard[{index}] raised: {error}")
                        guard_margins.append(None)
                    try:
                        value = guard_violation_value(guard, context)
                        if mp.isfinite(value):
                            guard_penalty_mpf += value
                            guard_vector_values.append(float(value))
                        else:
                            guard_penalty_mpf += mp.mpf("1")
                            guard_vector_values.append(1.0)
                    except Exception:
                        guard_penalty_mpf += mp.mpf("1")
                        guard_vector_failed = True
                        guard_vector_values.append(1.0)

            guard_ok = len(violations) == 0
            guard_penalty = float(guard_penalty_mpf)
            guard_vector = (
                np.ones(len(evaluator.compiled_guards), dtype=float)
                if guard_vector_failed
                else np.asarray(guard_vector_values, dtype=float)
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
                guard_margins=tuple(guard_margins),
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

    fused.__name__ = "fused_evaluation_budget_call"
    fused.__qualname__ = "EvaluationBudget.fused_evaluation_budget_call"
    return fused


def install_fused_evaluation(budget: Any) -> dict[str, Any]:
    """Install the process-wide fusion once and return auditable metadata."""

    budget_class = type(budget)
    with _INSTALL_LOCK:
        installed_schema = getattr(budget_class, _MARKER, None)
        if installed_schema is not None:
            if installed_schema != FUSION_SCHEMA_VERSION:
                raise RuntimeError("a different EvaluationBudget fusion is installed")
        else:
            opaque_evaluation = _attest_budget_class(budget_class)
            original = budget_class.__call__
            setattr(budget_class, _ORIGINAL, original)
            budget_class.__call__ = _fused_call_factory(opaque_evaluation)
            setattr(budget_class, _MARKER, FUSION_SCHEMA_VERSION)
    return {
        "schema_version": FUSION_SCHEMA_VERSION,
        "enabled": True,
        "reference_call_sha256": REFERENCE_CALL_SHA256,
        "case_specific_routing": False,
        "problem_identity_read": False,
        "guard_contexts_per_callback": 1,
        "exact_authority_modified": False,
    }
