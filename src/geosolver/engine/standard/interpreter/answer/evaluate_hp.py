"""High-precision answer evaluation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Sequence

from geosolver.engine.standard.interpreter.context import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    high_precision_mode,
)
from geosolver.ir.compiler import safe_eval_expr_hp
from geosolver.ir.schema import IRSpec

from .eval_to_mpf import _eval_exact_to_mpf


def _evaluate_answer_high_precision(
    spec_or_fn: IRSpec | Callable[[Sequence[object]], object],
    var_names_or_solution: Sequence[str] | Sequence[object],
    solution: Sequence[object] | None = None,
    precision: int = 80,
) -> tuple[Any, str | None, dict[str, Any]] | Any:
    """Evaluate answer expression in high precision with legacy return contract.

    Returns:
        (hp_value, hp_string, hp_context)
    """
    if callable(spec_or_fn) and solution is None:
        with high_precision_mode():
            return _eval_exact_to_mpf(spec_or_fn(var_names_or_solution), precision=int(precision))

    if solution is None:
        raise TypeError("solution is required for IRSpec-based high-precision evaluation")

    spec = spec_or_fn
    var_names = var_names_or_solution

    hp_context = _get_high_precision_context(int(precision))

    for name, value in zip(var_names, solution):
        hp_context[name] = value

    with high_precision_mode():
        for item in spec.construction:
            hp_context[item.name] = safe_eval_expr_hp(item.expr, hp_context)

        answer_expr = spec.answer_expr or spec.objective_expr
        if not answer_expr:
            return None, None, hp_context

        answer_value = safe_eval_expr_hp(answer_expr, hp_context)
        hp_value = _eval_exact_to_mpf(answer_value, precision=int(precision))
    return hp_value, str(hp_value), hp_context
