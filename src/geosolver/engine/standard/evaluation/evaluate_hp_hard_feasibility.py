"""High-precision hard-feasibility evaluation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from geosolver.engine.standard.interpreter.context import _get_high_precision_context
from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    _collect_guard_evidence,
)
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf

from geosolver.engine.standard.contracts.hard_feasibility_snapshot import (
    HardFeasibilitySnapshot,
)
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.evaluation._hard_feasibility_core import (
    evaluate_hard_feasibility,
)


def _cast_hp_value(value: object) -> object:
    return strict_to_mpf(value, context="evaluate_hp_hard_feasibility.cast")


def evaluate_hp_hard_feasibility(
    *,
    bundle: ProblemBundle,
    values: Sequence[MPFloat],
    precision: int,
    include_margins: bool = True,
) -> HardFeasibilitySnapshot:
    """Evaluate hard-feasibility checks in high-precision execution mode."""
    guard_violations, guard_margins = _collect_guard_evidence(
        list(values),
        spec=bundle.spec,
        var_names=list(bundle.var_names),
        base_context=dict(bundle.base_context),
        include_margins=bool(include_margins),
    )
    hp_base_context = dict(bundle.base_context)
    hp_base_context.update(_get_high_precision_context(int(precision)))
    hp_bundle = replace(bundle, base_context=hp_base_context)
    return evaluate_hard_feasibility(
        bundle=hp_bundle,
        checks=hp_bundle.hard_feasibility_checks,
        values=values,
        eval_expr=safe_eval_expr_hp,
        cast_value=_cast_hp_value,
        allow_float=False,
        guard_ok=(len(guard_violations) == 0),
        guard_violations=tuple(guard_violations),
        guard_margins=guard_margins,
    )
