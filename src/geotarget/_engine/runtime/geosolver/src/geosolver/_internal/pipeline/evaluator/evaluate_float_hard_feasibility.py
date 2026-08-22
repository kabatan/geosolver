"""Float-path hard-feasibility evaluation."""

from __future__ import annotations

from collections.abc import Sequence

from geosolver._internal.autosolve.execution.interpreter_helpers import (
    _collect_guard_evidence,
)
from geosolver.ir.compiler import safe_eval_expr

from geosolver._internal.pipeline.contracts.hard_feasibility_snapshot import (
    HardFeasibilitySnapshot,
)
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.evaluator._hard_feasibility_core import (
    evaluate_hard_feasibility,
)


def _cast_float_value(value: object) -> object:
    return float(value)


def evaluate_float_hard_feasibility(
    *,
    bundle: ProblemBundle,
    values: Sequence[float],
    include_margins: bool = True,
) -> HardFeasibilitySnapshot:
    """Evaluate hard-feasibility checks in float execution mode."""
    guard_violations, guard_margins = _collect_guard_evidence(
        list(values),
        spec=bundle.spec,
        var_names=list(bundle.var_names),
        base_context=dict(bundle.base_context),
        include_margins=bool(include_margins),
    )
    return evaluate_hard_feasibility(
        bundle=bundle,
        checks=bundle.hard_feasibility_checks,
        values=values,
        eval_expr=safe_eval_expr,
        cast_value=_cast_float_value,
        allow_float=True,
        guard_ok=(len(guard_violations) == 0),
        guard_violations=tuple(guard_violations),
        guard_margins=guard_margins,
    )
