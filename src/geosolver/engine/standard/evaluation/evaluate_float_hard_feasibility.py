"""Float-path hard-feasibility evaluation."""

from __future__ import annotations

from collections.abc import Sequence

from mpmath import mp

from geosolver.engine.standard.contracts.hard_feasibility_snapshot import (
    HardFeasibilitySnapshot,
)
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.evaluation._hard_feasibility_core import (
    HardFeasibilityRuntimeState,
    evaluate_hard_feasibility,
)
from geosolver.engine.standard.evaluation.guard_penalty import (
    collect_guard_evidence,
)
from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace,
    index_selection_trace,
)
from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
from geosolver.problem.ir.compiler import safe_eval_expr_hp


def _cast_float_value(value: object) -> object:
    return float(value)


def evaluate_float_hard_feasibility(
    *,
    bundle: ProblemBundle,
    values: Sequence[float],
    include_margins: bool = True,
    compiled_guards=None,
    guard_evidence=None,
) -> HardFeasibilitySnapshot:
    """Evaluate hard-feasibility checks in float execution mode."""
    guard_violations, guard_margins = (
        guard_evidence
        if guard_evidence is not None
        else collect_guard_evidence(
            list(values),
            spec=bundle.spec,
            var_names=list(bundle.var_names),
            base_context=dict(bundle.base_context),
            include_margins=bool(include_margins),
            compiled_guards=compiled_guards,
        )
    )
    with mp.workprec(53):
        try:
            snapshot = numerical_snapshot(
                bundle.spec, bundle.var_names, values, bundle.base_context, arithmetic="float"
            )
            with capture_selection_trace() as trace:
                context = snapshot.materialize(item.name for item in bundle.spec.construction)
        except TimeoutError:
            raise
        except Exception as error:
            return HardFeasibilitySnapshot(False, (f"construction_error:{error}",), None)
        return evaluate_hard_feasibility(
            bundle=bundle,
            checks=bundle.hard_feasibility_checks,
            values=values,
            eval_expr=safe_eval_expr_hp,
            cast_value=_cast_float_value,
            allow_float=True,
            guard_ok=(len(guard_violations) == 0),
            guard_violations=tuple(guard_violations),
            guard_margins=guard_margins,
            state=HardFeasibilityRuntimeState(context, index_selection_trace(trace)),
        )
