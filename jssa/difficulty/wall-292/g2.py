"""Fixed constraint-violation hinge penalty; no changes to the frozen source."""
from __future__ import annotations

import math
from collections import Counter

from mpmath import mp

from geosolver.engine.standard.evaluation._hard_feasibility_core import (
    HardFeasibilityRuntimeState, _evaluate_single_check,
)
from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace, index_selection_trace,
)
from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
from geosolver.engine.standard.interpreter.guards.compile import guard_violation_value

EPS = 1e-6


def boolean_kinds(guard):
    kinds = []
    if guard.kind in ("raw_condition", "logical_not"):
        kinds.append(guard.kind)
    for child in guard.children:
        kinds.extend(boolean_kinds(child))
    return kinds


class DistancePenalty:
    def __init__(self, evaluator):
        self.ev = evaluator
        self.counts = Counter()
        self.boolean = [boolean_kinds(g) for g in evaluator.compiled_guards]

    def fallback(self, reason):
        self.counts[reason] += 1
        return 1.0

    def __call__(self, *, evaluator, values):
        assert evaluator is self.ev
        self.counts["calls"] += 1
        bundle = evaluator.bundle
        terms = []
        if evaluator.compiled_guards:
            with mp.workdps(max(int(mp.dps), 80)):
                try:
                    snap = numerical_snapshot(bundle.spec, bundle.var_names, list(values), bundle.base_context)
                    context = snap.for_expressions(bundle.spec.guards, partial=True)
                except TimeoutError:
                    raise
                except Exception as exc:
                    context = None
                    self.counts["guard_context:" + type(exc).__name__] += 1
                for guard, kinds in zip(evaluator.compiled_guards, self.boolean):
                    for kind in kinds:
                        self.counts["boolean:" + kind] += 1
                    try:
                        v = float(guard_violation_value(guard, context)) if context is not None else None
                        if v is None or not math.isfinite(v):
                            v = self.fallback("guard_unavailable:" + guard.kind)
                    except TimeoutError:
                        raise
                    except Exception as exc:
                        v = self.fallback("guard_exception:" + guard.kind + ":" + type(exc).__name__)
                    terms.append(v)
        checks = [c for c in bundle.hard_feasibility_checks if c.kind != "guard"]
        if checks:
            with mp.workprec(53):
                try:
                    snap = numerical_snapshot(bundle.spec, bundle.var_names, list(values),
                                              bundle.base_context, arithmetic="float")
                    with capture_selection_trace() as trace:
                        context = snap.materialize(item.name for item in bundle.spec.construction)
                    state = HardFeasibilityRuntimeState(context, index_selection_trace(trace))
                except TimeoutError:
                    raise
                except Exception as exc:
                    state = None
                    self.counts["construction:" + type(exc).__name__] += 1
                for check in checks:
                    try:
                        if state is None:
                            margin = None
                        else:
                            _, _, margin = _evaluate_single_check(
                                check=check, state=state, allow_float=True,
                                guard_ok=True, guard_violations=(), guard_margins=())
                        m = float(margin) if margin is not None else None
                        if m == math.inf:
                            v = 0.0
                        elif m is None or not math.isfinite(m):
                            v = self.fallback("margin_unavailable:" + check.kind)
                        else:
                            v = max(0.0, EPS - m)
                    except TimeoutError:
                        raise
                    except Exception as exc:
                        v = self.fallback("hard_exception:" + check.kind + ":" + type(exc).__name__)
                    terms.append(v)
        return math.hypot(*terms)
