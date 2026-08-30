"""High-precision answer evaluation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from geosolver.engine.standard.interpreter.context import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    high_precision_mode,
)
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.schema import IRSpec

from .eval_to_mpf import _eval_exact_to_mpf


def _evaluate_answer_high_precision(
    spec: IRSpec,
    var_names: Sequence[str],
    solution: Sequence[object],
    precision: int = 80,
) -> Any:
    """Evaluate the IR answer without constructing unused text or context outputs."""
    hp_context = _get_high_precision_context(int(precision))

    for name, value in zip(var_names, solution, strict=False):
        hp_context[name] = value

    with high_precision_mode():
        for item in spec.construction:
            hp_context[item.name] = safe_eval_expr_hp(item.expr, hp_context)

        answer_expr = spec.answer_expr or spec.objective_expr
        if not answer_expr:
            return None

        answer_value = safe_eval_expr_hp(answer_expr, hp_context)
        hp_value = _eval_exact_to_mpf(answer_value, precision=int(precision))
    return hp_value
