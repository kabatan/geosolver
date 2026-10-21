"""Lazy shared equality leaves at one coordinate and one arithmetic precision."""

from mpmath import mp

from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace,
    replay_selection_trace,
)
from geosolver.problem.evaluation_trace import capture_calls, evaluation_scope, replay_calls
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.deadline import check_deadline, count_event


class LogicalVector:
    def __init__(self, plan, context):
        self.plan, self.context = plan, context
        self.precision_bits = mp.prec
        self.leaves = {}
        self.scores = {}
        self.choice = None
        self.choice_evidence = (), ()

    def leaf(self, source):
        if source not in self.leaves:
            value = error = None
            with capture_calls() as calls, capture_selection_trace() as trace:
                try:
                    with evaluation_scope(f"logical:{self.plan.identity}"):
                        value = safe_eval_expr_hp(source, self.context)
                except TimeoutError:
                    raise
                except Exception as caught:
                    error = caught
            self.leaves[source] = value, error, tuple(calls), tuple(trace)
            count_event("logical_leaf_evaluations")
        value, error, calls, trace = self.leaves[source]
        replay_calls(calls)
        replay_selection_trace(trace)
        if error is not None:
            raise error.with_traceback(None)
        return value

    def score(self, index):
        if index not in self.scores:
            self.scores[index] = max(abs(self.leaf(source)) for source in self.plan.clauses[index])
        return self.scores[index]

    def select(self):
        if self.choice is None:
            with capture_calls() as calls, capture_selection_trace() as trace:
                # Keep the old comparison/short-circuit order, including NaNs
                # and first-branch ties, but compute each leaf/score only once.
                chosen = len(self.plan.clauses) - 1
                for i in range(chosen):
                    if all(
                        self.score(i) <= self.score(j) for j in range(i + 1, len(self.plan.clauses))
                    ):
                        chosen = i
                        break
            self.choice, self.choice_evidence = chosen, (tuple(calls), tuple(trace))
        return self.choice

    def selected_source(self, column):
        clause = self.plan.clauses[self.select()]
        return clause[column] if column < len(clause) else "0"

    def component(self, column, *, zero_sources=None):
        check_deadline()
        if mp.prec != self.precision_bits:
            raise RuntimeError("logical vector used at a different precision")
        column = int(column)
        if not 0 <= column < self.plan.width:
            raise IndexError("logical residual component out of range")
        source = self.selected_source(column)
        calls, trace = self.choice_evidence
        replay_calls(calls)
        replay_selection_trace(trace)
        if zero_sources is not None and source != "0":
            source = zero_sources[source]
        return self.leaf(source)

    def __getitem__(self, column):
        return self.component(column)


class SmoothLogicalVector:
    """Smooth only the selected zero test; selection scores remain unchanged."""

    def __init__(self, original, zero_sources):
        self.original = original
        self.zero_sources = zero_sources

    def __getitem__(self, column):
        return self.original.component(column, zero_sources=self.zero_sources)

    def selected_source(self, column):
        return self.original.selected_source(column)
