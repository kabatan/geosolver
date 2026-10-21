"""Three-valued guards and uncertainty propagation at forbidden boundaries."""

from mpmath import mp

from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.snapshots import (
    evaluation_session,
    numerical_snapshot,
)
from geosolver.engine.standard.evaluation.verification_geometry import (
    geometry_margins,
    implicit_guard_margins,
)
from geosolver.engine.standard.evaluation.verification_numerics import differentiate
from geosolver.engine.standard.evaluation.verification_sampling import precision_sample
from geosolver.engine.standard.interpreter.guards.compile import (
    guard_hard_satisfied,
    guard_margin_value,
)
from geosolver.problem.evaluation_trace import capture_calls
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.deadline import check_deadline, count_event


def _combine(values, conjunction=True):
    values = tuple(values)
    if conjunction:
        return False if False in values else (None if None in values else True)
    return True if True in values else (None if None in values else False)


class DomainVerifier:
    def __init__(self, evaluator, point, uncertainty, scales, precision, zero_sources=()):
        self.evaluator, self.point = evaluator, point
        self.uncertainty, self.scales, self.precision = uncertainty, scales, precision
        self.evidence = []
        self._snapshots = {}
        self._numerical_snapshots = {}
        self._expression_snapshots = {}
        self._margin_snapshots = {}
        self.zero_sources = zero_sources
        self._zero_signatures = None

    def variable_dependencies(self, expression):
        store = getattr(self.evaluator, "evaluation_store", None)
        return None if store is None else store.plan.variable_dependencies((expression,))

    def numerical_snapshot(self, point):
        key = (mp.prec, tuple(v._mpf_ for v in point))
        if key not in self._numerical_snapshots:
            bundle = self.evaluator.bundle
            with evaluation_session(self.evaluator):
                self._numerical_snapshots[key] = numerical_snapshot(
                    bundle.spec, bundle.var_names, point, bundle.base_context
                )
        return self._numerical_snapshots[key]

    def certified_zero(self, expression):
        from geosolver.engine.standard.evaluation.verification_identities import (
            signatures,
            zero_signature,
        )

        constructions = tuple(
            (item.name, item.expr) for item in self.evaluator.bundle.spec.construction
        )
        signature = zero_signature(expression, constructions)
        if signature == "0":
            return True
        if not self.zero_sources:
            return False
        if self._zero_signatures is None:
            context, _, _ = self.snapshot(self.point)
            self._zero_signatures = signatures(self.zero_sources, constructions, context)
        return signature is not None and signature in self._zero_signatures

    def snapshot(self, point, *, partial=False):
        key = (mp.prec, tuple(v._mpf_ for v in point))
        if key not in self._snapshots:
            bundle = self.evaluator.bundle
            with (
                evaluation_session(self.evaluator),
                capture_calls() as calls,
                capture_selection_trace() as trace,
            ):
                snapshot = self.numerical_snapshot(point)
                context = snapshot.context
                error = None
                try:
                    snapshot.materialize(item.name for item in bundle.spec.construction)
                    # Inline constructions have the same domains as named
                    # constructions. Capture equations and the answer too.
                    for expression in self.evaluator.domain_expressions:
                        safe_eval_expr_hp(expression, context)
                except TimeoutError:
                    raise
                except Exception as exc:
                    error = exc
            self._snapshots[key] = context, tuple(calls), tuple(trace), error
        context, calls, trace, error = self._snapshots[key]
        if error is not None and not partial:
            raise error
        return context, calls, trace

    def scalar(self, expression):
        def evaluate(point):
            value, _, trace, _ = self.expression_snapshot(point, expression)
            return value, trace

        evaluate.variable_dependencies = self.variable_dependencies(expression)
        return evaluate

    def expression_snapshot(self, point, expression):
        key = (mp.prec, tuple(v._mpf_ for v in point), expression)
        if key not in self._expression_snapshots:
            if isinstance(expression, str):
                context = self.numerical_snapshot(point).for_expressions((expression,))
            else:
                context, _, _ = self.snapshot(point, partial=True)
            with capture_calls() as calls, capture_selection_trace() as trace:
                if isinstance(expression, str):
                    value = safe_eval_expr_hp(expression, context)
                    implicit = {}
                else:
                    value = guard_hard_satisfied(expression, context)
                    implicit = implicit_guard_margins(expression, context)
            margins = self.geometry_margins(calls, trace)
            margins.update({f"implicit:{k}": v for k, v in implicit.items()})
            self._expression_snapshots[key] = value, tuple(calls), tuple(trace), margins
        return self._expression_snapshots[key]

    def verify_expression_domain(self, expression, label):
        def margins(point):
            return self.expression_snapshot(point, expression)[3]

        if isinstance(expression, str):
            margins.variable_dependencies = self.variable_dependencies(expression)
        return self.verify_margins(margins, label)

    def verify_margins(self, function, label):
        # The adaptive step and uncertainty calculation remain per margin. Only
        # evaluation at identical perturbations is shared across margin rows.
        samples = {}

        def sample_all(point):
            check_deadline()
            coordinates = tuple(v._mpf_ for v in point)
            if coordinates not in samples:
                with mp.workdps(self.precision):
                    low = function(point)
                    epsilon = +mp.eps
                with mp.workdps(self.precision + 30):
                    high = function(point)
                    result = {}
                    for key in low.keys() & high.keys():
                        a, b = low[key], high[key]
                        try:
                            error = (
                                4 * abs(b - a) + 32 * epsilon * abs(b)
                                if mp.isfinite(a) and mp.isfinite(b)
                                else mp.inf
                            )
                        except (TypeError, ValueError, ArithmeticError):
                            # One invalid row must not invalidate other margins.
                            continue
                        result[key] = b, (), error
                samples[coordinates] = result
                count_event("domain_margin_system_samples")
            else:
                count_event("domain_margin_sample_cache_hits")
            return samples[coordinates]

        states = []
        for key in function(self.point):
            try:
                margin, error = self.measure(
                    None,
                    label + key,
                    sampled=lambda p, k=key: sample_all(p)[k],
                    dependencies=getattr(function, "variable_dependencies", None),
                )
                states.append(True if margin > 100 * error else (False if margin <= 0 else None))
            except TimeoutError:
                raise
            except Exception:
                states.append(None)
        return _combine(states)

    def measure(self, function, label, *, sampled=None, dependencies=None):
        if dependencies is None:
            dependencies = getattr(function, "variable_dependencies", None)
        if sampled is None:

            def sampled(point):
                return precision_sample(function, point, self.precision)

        base = sampled(self.point)
        value, _, error = base
        for j, uncertainty in enumerate(self.uncertainty):
            if uncertainty == 0 or (dependencies is not None and j not in dependencies):
                continue
            derivative = differentiate(
                sampled,
                self.point,
                j,
                self.scales[j],
                self.precision,
                base,
                allow_nonsmooth=True,
            )
            if derivative is None or not mp.isfinite(uncertainty):
                error = mp.inf
                break
            error += (abs(derivative[0]) + derivative[1]) * uncertainty
        self.evidence.append({"condition": label, "value": value, "uncertainty": error})
        return value, error

    def compare(self, expression, operator, label, *, require_zero_certificate=False):
        if self.verify_expression_domain(expression, label + ":domain:") is not True:
            return None
        value, error = self.measure(self.scalar(expression), label)
        if not mp.isfinite(value) or not mp.isfinite(error):
            return None
        if (
            operator in ("==", ">=", "<=")
            and abs(value) <= 100 * error
            and self.certified_zero(expression)
        ):
            self.evidence[-1]["zero_certificate"] = True
            return True
        if operator in ("<", "<="):
            value = -value
        if operator in ("!=", "=="):
            different = True if abs(value) > 100 * error else (False if value == 0 else None)
            if different is False and require_zero_certificate:
                return None
            return different if operator == "!=" else (None if different is None else not different)
        if value == 0:
            if error > 0 and not self.certified_zero(expression):
                return None
            return operator in (">=", "<=")
        if abs(value) <= 100 * error:
            return None
        return value > 0

    def guard(self, guard):
        if guard.kind in ("logical_and", "logical_or"):
            states = []
            conjunction = guard.kind == "logical_and"
            for child in guard.children:
                state = self.guard(child)
                if state is (not conjunction):
                    return state
                states.append(state)
            return _combine(states, conjunction)
        if guard.kind == "logical_not":
            value = self.guard(guard.children[0])
            return None if value is None else not value
        if guard.kind == "triangle_class":
            if self.verify_expression_domain(guard, guard.source + ":domain:") is not True:
                return None
            operator = {"acute": ">", "obtuse": "<", "right": "=="}[guard.operator]
            states = []
            # Coordinate-unit dot products retain tiny angular differences.
            # A rounded zero is not enough to assert an exact right angle.
            for i, vertex in enumerate(guard.argument_exprs):
                a, c = (guard.argument_exprs[(i + offset) % 3] for offset in (1, 2))
                expression = (
                    f"(({a}).x-({vertex}).x)*(({c}).x-({vertex}).x)"
                    f"+(({a}).y-({vertex}).y)*(({c}).y-({vertex}).y)"
                )
                state = self.compare(
                    expression,
                    operator,
                    guard.source + f":angle:{i}",
                    require_zero_certificate=guard.operator == "right",
                )
                if state is (guard.operator != "acute"):
                    return state
                states.append(state)
            return _combine(states, guard.operator == "acute")
        if guard.kind == "compare":
            return self.compare(
                f"({guard.lhs_expr})-({guard.rhs_expr})", guard.operator, guard.source
            )
        if guard.kind in ("bound", "bound_open"):
            op = ">=" if guard.kind == "bound" else ">"
            values = []
            if guard.lower_expr is not None:
                values.append(
                    self.compare(
                        f"({guard.lhs_expr})-({guard.lower_expr})", op, guard.source + ":lower"
                    )
                )
            if guard.upper_expr is not None:
                values.append(
                    self.compare(
                        f"({guard.upper_expr})-({guard.lhs_expr})", op, guard.source + ":upper"
                    )
                )
            return _combine(values)
        value, _, _, _ = self.expression_snapshot(self.point, guard)
        if self.verify_expression_domain(guard, guard.source + ":domain:") is not True:
            return None
        if not value:
            return False
        context, _, _ = self.snapshot(self.point)
        margin = guard_margin_value(guard, context)
        if not mp.isfinite(margin):
            # Opaque boolean predicates are still checked at both precisions.
            return True
        value, error = self.measure(
            lambda p: (guard_margin_value(guard, self.snapshot(p)[0]), ()), guard.source
        )
        return True if value > 100 * error else None

    geometry_margins = staticmethod(geometry_margins)

    def snapshot_margins(self, point):
        key = (mp.prec, tuple(v._mpf_ for v in point))
        if key not in self._margin_snapshots:
            _, calls, trace = self.snapshot(point, partial=True)
            self._margin_snapshots[key] = self.geometry_margins(calls, trace)
        return self._margin_snapshots[key]

    def verify(self):
        states = [self.guard(guard) for guard in self.evaluator.compiled_guards]
        _, _, trace = self.snapshot(self.point)
        states.append(self.verify_margins(self.snapshot_margins, ""))
        return _combine(states), tuple(trace), tuple(self.evidence)

    def answer(self):
        expression = (
            self.evaluator.bundle.spec.answer_expr or self.evaluator.bundle.spec.objective_expr
        )
        return self.measure(self.scalar(expression), "answer")
