"""Float construction and residual evaluation for the search phase."""

from __future__ import annotations

import math
from typing import Any

from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
from geosolver.problem.evaluation_trace import evaluation_scope
from geosolver.problem.ir.compiler import safe_eval_expr
from geosolver.problem.ir.schema import IRSpec


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        try:
            return float(str(_eval_exact_to_mpf(value, 50)))
        except Exception:
            return math.nan


def compute_residual_vector(
    values: list[float],
    *,
    spec: IRSpec,
    var_names: list[str],
    targets: list[Any],
    base_context: dict[str, Any],
) -> list[float]:
    context = dict(base_context)
    for name, value in zip(var_names, values, strict=True):
        context[name] = value
    try:
        for item in spec.construction:
            with evaluation_scope(item.name):
                context[item.name] = safe_eval_expr(item.expr, context)
    except Exception:
        return [math.nan for _ in spec.constraints]

    residuals: list[float] = []
    for index, constraint_expr in enumerate(spec.constraints):
        try:
            lhs = _to_float(safe_eval_expr(constraint_expr, context))
            target = targets[index]
            rhs = _to_float(safe_eval_expr(target, context) if isinstance(target, str) else target)
            residuals.append(lhs - rhs)
        except Exception:
            residuals.append(math.nan)
    return residuals


def residual_norm(residuals: list[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in residuals))
