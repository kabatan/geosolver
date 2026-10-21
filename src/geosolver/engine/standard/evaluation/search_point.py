"""A search point keeps binary64 residuals and the existing HP guard precision."""

from dataclasses import dataclass

from .guard_penalty import collect_guard_evidence, guard_violation_penalty
from .snapshots import uses_evaluation_store


@dataclass(frozen=True)
class SearchPointEvaluation:
    residual: object
    hard: object
    guard_ok: bool
    guard_violations: tuple
    guard_penalty: float | None = None


@uses_evaluation_store()
def evaluate_search_point(*, evaluator, values, residual=None, smooth_penalty=False):
    residual = evaluator.evaluate_float_residual(values) if residual is None else residual
    if not hasattr(evaluator, "compiled_guards"):
        hard = evaluator.evaluate_float_hard_feasibility(values, include_margins=False)
        guard_ok, violations = evaluator.evaluate_guard(values)
        return SearchPointEvaluation(residual, hard, guard_ok, violations)
    bundle = evaluator.bundle
    args = dict(
        spec=bundle.spec,
        var_names=list(bundle.var_names),
        base_context=bundle.base_context,
        compiled_guards=evaluator.compiled_guards,
    )
    evidence = collect_guard_evidence(list(values), include_margins=False, **args)
    hard = evaluator.evaluate_float_hard_feasibility(
        values,
        include_margins=False,
        guard_evidence=evidence,
    )
    penalty = guard_violation_penalty(list(values), **args) if smooth_penalty else None
    return SearchPointEvaluation(residual, hard, not evidence[0], tuple(evidence[0]), penalty)
