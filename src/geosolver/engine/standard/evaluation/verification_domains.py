"""Three-valued guards and uncertainty propagation at forbidden boundaries."""

from dataclasses import replace
from functools import lru_cache

from mpmath import mp

from geosolver.engine.standard.evaluation.high_precision_expressions import (
    build_solution_context_high_precision,
)
from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.verification_numerics import differentiate
from geosolver.engine.standard.evaluation.verification_sampling import precision_sample
from geosolver.engine.standard.interpreter.guards.compile import (
    guard_hard_satisfied,
    guard_margin_value,
)
from geosolver.problem.evaluation_trace import capture_calls, evaluation_scope
from geosolver.problem.ir.compiler import extract_names, safe_eval_expr_hp


@lru_cache(maxsize=1)
def _triangle_functions():
    from geosolver.problem.dsl_spec import dsl_spec

    return frozenset(
        name
        for symbol in dsl_spec().symbols
        if symbol.category == "centers" or "three points are non-collinear" in symbol.domain
        for name in (symbol.name, *symbol.aliases)
    )


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
        self.zero_sources = zero_sources
        self._zero_signatures = None

    def certified_zero(self, expression):
        if not self.zero_sources:
            return False
        from geosolver.engine.standard.evaluation.verification_identities import (
            signatures,
            zero_signature,
        )

        constructions = tuple(
            (item.name, item.expr) for item in self.evaluator.bundle.spec.construction
        )
        if self._zero_signatures is None:
            context, _, _ = self.snapshot(self.point)
            self._zero_signatures = signatures(self.zero_sources, constructions, context)
        signature = zero_signature(expression, constructions)
        return signature is not None and signature in self._zero_signatures

    def snapshot(self, point, *, partial=False):
        key = (mp.prec, tuple(v._mpf_ for v in point))
        if key not in self._snapshots:
            bundle = self.evaluator.bundle
            with capture_calls() as calls, capture_selection_trace() as trace:
                from geosolver.engine.standard.interpreter.context.high_precision import (
                    _get_high_precision_context,
                )

                context = dict(bundle.base_context)
                context.update(_get_high_precision_context(mp.dps))
                context.update(zip(bundle.var_names, point, strict=True))
                error = None
                for item in bundle.spec.construction:
                    try:
                        with evaluation_scope(item.name):
                            context[item.name] = safe_eval_expr_hp(item.expr, context)
                    except Exception as exc:
                        error = exc
                        break
            self._snapshots[key] = context, tuple(calls), tuple(trace), error
        context, calls, trace, error = self._snapshots[key]
        if error is not None and not partial:
            raise error
        return context, calls, trace

    def scalar(self, expression):
        bundle = self.evaluator.bundle
        names = set(extract_names(expression))
        needed = []
        for item in reversed(bundle.spec.construction):
            if item.name in names:
                needed.append(item)
                names.update(extract_names(item.expr))
        spec = replace(bundle.spec, construction=list(reversed(needed)))

        def evaluate(point):
            with capture_selection_trace() as trace:
                context = build_solution_context_high_precision(
                    spec, list(bundle.var_names), list(point), bundle.base_context, mp.dps
                )
                value = safe_eval_expr_hp(expression, context)
            return value, tuple(trace)

        return evaluate

    def measure(self, function, label):
        def sampled(point):
            return precision_sample(function, point, self.precision)

        base = sampled(self.point)
        value, _, error = base
        for j, uncertainty in enumerate(self.uncertainty):
            if uncertainty == 0:
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

    def compare(self, expression, operator, label):
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
            return different if operator == "!=" else (None if different is None else not different)
        if value == 0:
            return operator in (">=", "<=")
        if abs(value) <= 100 * error:
            return None
        return value > 0

    def guard(self, guard):
        if guard.kind in ("logical_and", "logical_or"):
            return _combine(
                (self.guard(child) for child in guard.children), guard.kind == "logical_and"
            )
        if guard.kind == "logical_not":
            value = self.guard(guard.children[0])
            return None if value is None else not value
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
        context, _, _ = self.snapshot(self.point)
        if not guard_hard_satisfied(guard, context):
            return False
        margin = guard_margin_value(guard, context)
        if not mp.isfinite(margin):
            # Opaque boolean predicates are still checked at both precisions.
            return True
        value, error = self.measure(
            lambda p: (guard_margin_value(guard, self.snapshot(p)[0]), ()), guard.source
        )
        return True if value > 100 * error else None

    @staticmethod
    def geometry_margins(calls, trace):
        margins = {}
        for index, (site, name, args, _kwargs, result) in enumerate(calls):
            key = f"{site}:{index}:{name}"
            if hasattr(result, "radius"):
                margins[key + ":positive_radius"] = result.radius
            if name in {"Line", "Segment", "Ray", "PointOnSegment"} and len(args) >= 2:
                a, b = args[:2]
                if hasattr(a, "x") and hasattr(b, "x"):
                    margins[key + ":distinct"] = mp.hypot(a.x - b.x, a.y - b.y)
            if (
                name in _triangle_functions()
                and len(args) >= 3
                and all(hasattr(p, "x") for p in args[:3])
            ):
                a, b, c = args[:3]
                margins[key + ":noncollinear"] = abs(
                    (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
                )
        for index, entry in enumerate(trace):
            if entry.margin is not None and mp.isfinite(entry.margin):
                margins[f"{entry.call_site_id}:{index}:selector"] = entry.margin
        return margins

    def verify(self):
        states = [self.guard(guard) for guard in self.evaluator.compiled_guards]
        _, calls, trace = self.snapshot(self.point)
        margins = self.geometry_margins(calls, trace)
        for key in margins:

            def value(point, key=key):
                _, other_calls, other_trace = self.snapshot(point, partial=True)
                # Branch jumps increase uncertainty here, never a residual denominator.
                return self.geometry_margins(other_calls, other_trace)[key], ()

            try:
                margin, error = self.measure(value, key)
                states.append(True if margin > 100 * error else (False if margin <= 0 else None))
            except Exception:
                states.append(None)
        return _combine(states), tuple(trace), tuple(self.evidence)

    def answer(self):
        expression = (
            self.evaluator.bundle.spec.answer_expr or self.evaluator.bundle.spec.objective_expr
        )
        return self.measure(self.scalar(expression), "answer")
