"""Source-bounds-only opaque runtime and full-support proposal policy.

This module deliberately does not import or call ``infer_problem_bounds``.
Missing source bounds remain infinite.  The proposal distribution uses only a
fixed, case-independent Cauchy/dyadic schedule on such axes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
import sys
import time
from typing import Callable

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GEOSOLVER_SOURCE = ROOT.parent / "geosolver/src"
if str(GEOSOLVER_SOURCE) not in sys.path:
    sys.path.insert(0, str(GEOSOLVER_SOURCE))

from geosolver._internal.autosolve.execution.interpreter_helpers import (  # noqa: E402
    _assign_variables,
    _build_guard_context,
    _evaluate_target,
    _guard_violation_penalty,
    _to_float,
)
from geosolver._internal.autosolve.guards.compile import (  # noqa: E402
    guard_violation_value,
)
from geosolver._internal.pipeline.evaluator.ir_evaluator import (  # noqa: E402
    build_ir_evaluator,
)
from geosolver._internal.pipeline.problem.load_problem_bundle import (  # noqa: E402
    load_problem_bundle,
)
from geosolver.ir.compiler import safe_eval_expr  # noqa: E402


PROPOSAL_POLICY = "SOURCE_ONLY_FULL_SUPPORT_CAUCHY_DYADIC"
IID_INSURANCE_FRACTION = 0.25


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class OpaqueEvaluation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool
    violation: float
    violation_vector: np.ndarray


@dataclass(frozen=True)
class SourceOnlyCase:
    dimension: int
    residual_dimension: int
    lower: np.ndarray
    upper: np.ndarray
    # These neutral values are used only by the public near-root trace.  Each
    # local solve replaces them from that solve's start magnitude.
    origin: np.ndarray
    scales: np.ndarray
    evaluate: Callable[[np.ndarray], OpaqueEvaluation]
    progressive_residual: Callable[[np.ndarray], np.ndarray]


def source_bounds(document: dict[str, object], dimension: int):
    raw = document.get("bounds")
    if raw is None:
        return np.full(dimension, -math.inf), np.full(dimension, math.inf)
    if not isinstance(raw, list) or len(raw) != dimension:
        raise ValueError("source bounds do not match variables.names")
    lower = np.asarray([float(pair[0]) for pair in raw], dtype=float)
    upper = np.asarray([float(pair[1]) for pair in raw], dtype=float)
    if (
        not np.all(np.isfinite(lower))
        or not np.all(np.isfinite(upper))
        or not np.all(lower < upper)
    ):
        raise ValueError("source bounds must be finite and ordered")
    return lower, upper


class EvaluationBudget:
    def __init__(self, evaluator, residual_dimension: int, cap: int, deadline: float):
        self.evaluator = evaluator
        self.residual_dimension = int(residual_dimension)
        self.cap = int(cap)
        self.deadline = float(deadline)
        self.callbacks = 0
        self.finite = 0
        self.invalid = 0
        self.guard_failed = 0
        self.best_norm = math.inf

    def _charge(self):
        if self.callbacks >= self.cap:
            raise BudgetExceeded("callback_cap")
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("deadline")
        self.callbacks += 1

    def __call__(self, point: np.ndarray) -> OpaqueEvaluation:
        self._charge()
        values = np.asarray(point, dtype=float)
        try:
            observation = self.evaluator.evaluate_float_residual(values.tolist())
            guard_ok, _violations = self.evaluator.evaluate_guard(values.tolist())
            hard = self.evaluator.evaluate_float_hard_feasibility(values.tolist())
            residual = np.asarray(observation.residual_vector, dtype=float)
            finite = bool(
                observation.is_finite
                and residual.shape == (self.residual_dimension,)
                and np.all(np.isfinite(residual))
            )
            semantics = bool(guard_ok and hard.hard_feasible)
            guard_penalty = float(
                _guard_violation_penalty(
                    values.tolist(),
                    spec=self.evaluator.bundle.spec,
                    var_names=list(self.evaluator.bundle.var_names),
                    base_context=dict(self.evaluator.bundle.base_context),
                    compiled_guards=self.evaluator.compiled_guards,
                )
            )
            try:
                context = _build_guard_context(
                    self.evaluator.bundle.spec,
                    list(self.evaluator.bundle.var_names),
                    values.tolist(),
                    dict(self.evaluator.bundle.base_context),
                )
                guard_vector = np.asarray(
                    [
                        float(guard_violation_value(guard, context))
                        for guard in self.evaluator.compiled_guards
                    ],
                    dtype=float,
                )
                guard_vector = np.where(np.isfinite(guard_vector), guard_vector, 1.0)
            except Exception:
                guard_vector = np.ones(len(self.evaluator.compiled_guards), dtype=float)
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
        return OpaqueEvaluation(
            residual=residual,
            finite=finite,
            semantics_valid=semantics,
            violation=max(0.0, float(violation)),
            violation_vector=np.maximum(0.0, violation_vector),
        )

    def progressive_residual(self, point: np.ndarray) -> np.ndarray:
        self._charge()
        values = np.asarray(point, dtype=float)
        bundle = self.evaluator.bundle
        context = dict(bundle.base_context)
        _assign_variables(context, list(bundle.var_names), values.tolist())
        for item in bundle.spec.construction:
            try:
                context[item.name] = safe_eval_expr(item.expr, context)
            except Exception:
                continue
        residuals: list[float] = []
        available = 0
        for index, expression in enumerate(bundle.spec.constraints):
            try:
                lhs = _to_float(safe_eval_expr(expression, context))
                rhs = _evaluate_target(bundle.targets[index], context)
                value = float(lhs - rhs)
                if not math.isfinite(value):
                    raise ValueError("nonfinite progressive residual")
                residuals.append(value)
                available += 1
            except Exception:
                residuals.append(1.0e3)
        vector = np.asarray(residuals, dtype=float)
        if available:
            self.finite += 1
            values = np.abs(vector[np.abs(vector) < 1.0e3])
            if values.size:
                self.best_norm = min(self.best_norm, float(np.max(values)))
        else:
            self.invalid += 1
        return vector


def build_opaque_case(document: dict[str, object], *, callback_cap: int, deadline: float):
    bundle = load_problem_bundle(document, prefer_fast=False)
    evaluator = build_ir_evaluator(bundle)
    dimension = len(bundle.var_names)
    residual_dimension = len(bundle.targets)
    lower, upper = source_bounds(document, dimension)
    budget = EvaluationBudget(evaluator, residual_dimension, callback_cap, deadline)
    # Missing bounds stay exactly unbounded.  Neutral trace normalization does
    # not constrain or transform the evaluator's variable domain.
    origin = np.zeros(dimension, dtype=float)
    scales = np.ones(dimension, dtype=float)
    bounded = np.isfinite(lower) & np.isfinite(upper)
    origin[bounded] = lower[bounded] / 2.0 + upper[bounded] / 2.0
    scales[bounded] = upper[bounded] / 2.0 - lower[bounded] / 2.0
    case = SourceOnlyCase(
        dimension=dimension,
        residual_dimension=residual_dimension,
        lower=lower,
        upper=upper,
        origin=origin,
        scales=scales,
        evaluate=budget,
        progressive_residual=budget.progressive_residual,
    )
    return case, budget, evaluator


def readonly_case(case: SourceOnlyCase) -> SourceOnlyCase:
    values = {}
    for name in ("lower", "upper", "origin", "scales"):
        array = np.asarray(getattr(case, name), dtype=float).copy()
        array.flags.writeable = False
        values[name] = array
    return replace(case, **values)


def _noninsurance_exponent(ordinal: int) -> int:
    magnitude = ordinal // 2 + 1
    return magnitude if ordinal % 2 == 0 else -magnitude


def proposals(case: SourceOnlyCase, _compatibility_label: str, count: int, seed: int):
    """Return source-only starts; the historical proposal label is ignored."""

    if count < 1:
        return []
    if case.dimension == 0:
        return [np.empty(0)]
    rng = np.random.default_rng(int(seed))
    bounded = np.isfinite(case.lower) & np.isfinite(case.upper)
    lower_only = np.isfinite(case.lower) & ~np.isfinite(case.upper)
    upper_only = ~np.isfinite(case.lower) & np.isfinite(case.upper)
    unbounded = ~np.isfinite(case.lower) & ~np.isfinite(case.upper)
    points = []
    shell_ordinal = 0
    for index in range(int(count)):
        insurance = index % 4 == 0
        exponent = 0 if insurance else _noninsurance_exponent(shell_ordinal)
        shell_ordinal += int(not insurance)
        scale = math.ldexp(1.0, exponent)
        for _attempt in range(32):
            draw = rng.standard_cauchy(case.dimension) * scale
            point = draw.copy()
            if np.any(bounded):
                point[bounded] = rng.uniform(case.lower[bounded], case.upper[bounded])
            if np.any(lower_only):
                point[lower_only] = case.lower[lower_only] + np.abs(draw[lower_only])
            if np.any(upper_only):
                point[upper_only] = case.upper[upper_only] - np.abs(draw[upper_only])
            if np.all(np.isfinite(point)):
                break
        else:
            raise ArithmeticError("failed to draw a finite full-support proposal")
        # No inferred envelope and no clipping exists on unbounded axes.
        assert np.all(np.isfinite(point[unbounded]))
        points.append(point)
    return points


__all__ = [
    "BudgetExceeded",
    "IID_INSURANCE_FRACTION",
    "PROPOSAL_POLICY",
    "SourceOnlyCase",
    "build_opaque_case",
    "proposals",
    "readonly_case",
    "source_bounds",
]
