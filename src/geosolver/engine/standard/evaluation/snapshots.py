"""Lazy numerical constructions, shared only at identical coordinates and precision.

The cache belongs to one evaluator/solve, not to the process.  It never rounds a
cache key and never merges candidates.  Captured calls and selector decisions
are replayed with cached values, so reuse cannot hide a branch or domain check.
"""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from weakref import WeakMethod

from mpmath import mp

from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace,
    replay_selection_trace,
    selection_evaluation_identity,
    use_selection_symbol,
)
from geosolver.engine.standard.interpreter.context.high_precision import (
    _get_high_precision_context,
    _HPCallableWithTrace,
)
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.ensure_no_float import ValidatedHPContext
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.errors import GeometryDomainError
from geosolver.geometry.mp.mp_aux_entities import MPVector
from geosolver.geometry.mp.mp_core_types import MPPoint
from geosolver.problem.evaluation_trace import capture_calls, replay_calls
from geosolver.problem.ir.compiler import extract_names, safe_eval_expr_hp
from geosolver.problem.logical_equalities import evaluation_sources
from geosolver.runtime.deadline import check_deadline, count_event

_active_store = ContextVar("numerical_evaluation_store", default=None)


class ConstructionPlan:
    """One immutable dependency plan; construction order remains the DSL order."""

    def __init__(self, spec, var_names, base_context):
        self.items = tuple(spec.construction)
        self.sources = {item.name: item.expr for item in self.items}
        self.var_names = tuple(var_names)
        self.base_context = dict(base_context)
        self.logical_plans = tuple(spec.logical_plans)
        self.dependencies = {item.name: frozenset(extract_names(item.expr)) for item in self.items}
        variable_dependent = set(self.var_names)
        constant_names = set()
        for item in self.items:
            if self.dependencies[item.name] & variable_dependent:
                variable_dependent.add(item.name)
            else:
                constant_names.add(item.name)
        self.constant_names = frozenset(constant_names)
        self.variable_dependent = frozenset(variable_dependent)
        self._required = {}
        self._variable_dependencies = {}
        self.expression_names = {}

    def required(self, expressions):
        key = tuple(expressions)
        if key not in self._required:
            names = set()
            for expression in key:
                for source in evaluation_sources(expression, self.logical_plans):
                    names.update(extract_names(source))
            for item in reversed(self.items):
                if item.name in names:
                    names.update(self.dependencies[item.name])
            self._required[key] = tuple(item.name for item in self.items if item.name in names)
        return self._required[key]

    def variable_dependencies(self, expressions):
        """Return conservative coordinate dependencies, including construction leaves."""
        key = tuple(expressions)
        if key not in self._variable_dependencies:
            names = set()
            for expression in key:
                for source in evaluation_sources(expression, self.logical_plans):
                    names.update(extract_names(source))
            for name in self.required(key):
                names.update(self.dependencies[name])
            self._variable_dependencies[key] = frozenset(
                index for index, name in enumerate(self.var_names) if name in names
            )
        return self._variable_dependencies[key]

    def accepts(self, spec, var_names, base_context):
        return (
            tuple(var_names) == self.var_names
            and all(plan in self.logical_plans for plan in spec.logical_plans)
            and all(self.sources.get(item.name) == item.expr for item in spec.construction)
            and self.base_context.keys() == base_context.keys()
            and all(self.base_context[name] is value for name, value in base_context.items())
        )


class EvaluationSnapshot:
    def __init__(self, plan, values, store, *, arithmetic="hp"):
        self.plan, self.store = plan, store
        self.precision_bits = mp.prec
        self.constant_cache = store.constant_bucket(arithmetic, self.precision_bits)
        self.context = store.base_context.fork()
        # Contexts can outlive LRU eviction (e.g. a verifier's base point). They
        # must not retain an evicted snapshot and its store via a bound method.
        self.context.scalar_evaluator = WeakMethod(self.evaluate)
        if values is not None:
            self.context.update(zip(plan.var_names, values, strict=True))
        if plan.logical_plans:
            from .logical_vectors import LogicalVector, SmoothLogicalVector

            for logical in plan.logical_plans:
                vector = LogicalVector(logical, self.context)
                self.context.setdefault(logical.context_name, {})[logical.identity] = vector
                self.context.setdefault(logical.smooth_context_name, {})[logical.identity] = (
                    SmoothLogicalVector(vector, store.logical_zero_sources)
                )
        self.completed = {}
        self.errors = {}
        self.evidence = {}
        self.memo = {}

    def materialize(self, names, *, partial=False):
        """Return a context and replay evidence for exactly the requested slice."""
        check_deadline()
        if self.precision_bits != mp.prec:
            raise RuntimeError("evaluation snapshot used at a different precision")
        names = tuple(names)
        for name in names:
            if name not in self.completed and name in self.constant_cache:
                value, evidence = self.constant_cache[name]
                self.context[name] = self.completed[name] = value
                self.evidence[name] = evidence
                count_event("constant_construction_cache_hits")
            if name not in self.completed and name not in self.errors:
                check_deadline()
                with capture_calls() as calls, capture_selection_trace() as trace:
                    try:
                        with use_selection_symbol(name):
                            value = safe_eval_expr_hp(self.plan.sources[name], self.context)
                        if value is None:
                            raise GeometryDomainError(f"construction {name} returned no object")
                        self.context[name] = self.completed[name] = value
                    except TimeoutError:
                        raise
                    except Exception as error:
                        self.errors[name] = error
                        self.context[name] = None
                self.evidence[name] = tuple(calls), tuple(trace)
                if name in self.plan.constant_names and name in self.completed:
                    self.constant_cache[name] = self.completed[name], self.evidence[name]
                self.store.construction_evaluations += 1
                count_event("numerical_construction_evaluations")
            calls, trace = self.evidence[name]
            replay_calls(calls)
            replay_selection_trace(trace)
            if name in self.errors and not partial:
                # Re-raising a cached exception must not grow its traceback
                # on every repeated infeasible evaluation.
                raise self.errors[name].with_traceback(None)
        return self.context

    def for_expressions(self, expressions, *, partial=False):
        return self.materialize(self.plan.required(expressions), partial=partial)

    def evaluate(self, expression, *, constants_only=False):
        """Share scalar leaves, with exact input and evidence identity.

        Logical vectors and unrecognised mutable dependencies deliberately use
        the uncached path. Geometry points are keyed by coordinates, not id().
        """
        check_deadline()
        if self.precision_bits != mp.prec:
            raise RuntimeError("expression snapshot used at a different precision")
        names = self.plan.expression_names.get(expression)
        if names is None:
            names = tuple(extract_names(expression))
            self.plan.expression_names[expression] = names
        constant = not self.plan.variable_dependent.intersection(names)
        if constants_only and not constant:
            return safe_eval_expr_hp(expression, self.context)
        tokens = []
        for name in (*names, "mpf"):
            value = self.context.get(name)
            token = _scalar_dependency_token(value)
            if token is None:
                return safe_eval_expr_hp(expression, self.context)
            tokens.append(token)
        cache = self.constant_cache if constant else self.memo
        key = ("scalar", expression, selection_evaluation_identity(), tuple(tokens))
        if key in cache:
            value, calls, trace = cache[key]
            count_event("constant_scalar_cache_hits" if constant else "scalar_leaf_cache_hits")
        else:
            with capture_calls() as calls, capture_selection_trace() as trace:
                value = safe_eval_expr_hp(expression, self.context)
            calls, trace = tuple(calls), tuple(trace)
            # A small bound also protects against mutated external contexts.
            if type(value) in (mp.mpf, int, bool) and len(cache) < 512:
                cache[key] = value, calls, trace
            count_event("scalar_leaf_evaluations")
        replay_calls(calls)
        replay_selection_trace(trace)
        return value


def _scalar_dependency_token(value):
    if type(value) is mp.mpf:
        return ("mpf", value._mpf_)
    if type(value) in (int, bool, str):
        return (type(value), value)
    if type(value) in (MPPoint, MPVector) and type(value.x) is mp.mpf and type(value.y) is mp.mpf:
        return (type(value), value.x._mpf_, value.y._mpf_)
    if type(value) is _HPCallableWithTrace or value is mp.pi:
        return ("binding", value)
    return None


def evaluate_scalar_expression(expression, context, *, constants_only=False):
    if type(context) is ValidatedHPContext and context.scalar_evaluator is not None:
        evaluate = context.scalar_evaluator()
        if evaluate is not None:
            return evaluate(expression, constants_only=constants_only)
    return safe_eval_expr_hp(expression, context)


class EvaluationStore:
    """Bounded solve-local cache; expression slices share the parent plan."""

    def __init__(self, bundle=None, *, spec=None, var_names=(), base_context=None, capacity=256):
        if bundle is not None:
            spec, var_names, base_context = bundle.spec, bundle.var_names, bundle.base_context
        self.plan = ConstructionPlan(spec, var_names, base_context or {})
        context = dict(self.plan.base_context)
        context.update(_get_high_precision_context(mp.dps))
        self.base_context = ValidatedHPContext(context)
        self.capacity = capacity
        self.snapshots = OrderedDict()
        self.constant_snapshots = OrderedDict()
        self.logical_zero_sources = {}
        self.construction_evaluations = 0
        self.snapshot_hits = 0

    def constant_bucket(self, arithmetic, precision_bits):
        key = arithmetic, precision_bits
        if key not in self.constant_snapshots:
            self.constant_snapshots[key] = {}
        self.constant_snapshots.move_to_end(key)
        if len(self.constant_snapshots) > min(32, max(1, self.capacity)):
            self.constant_snapshots.popitem(last=False)
        return self.constant_snapshots[key]

    def get(self, values, *, arithmetic="hp"):
        check_deadline()
        key = (arithmetic, mp.prec, tuple(value._mpf_ for value in values))
        if key in self.snapshots:
            self.snapshot_hits += 1
            count_event("evaluation_snapshot_hits")
            self.snapshots.move_to_end(key)
            return self.snapshots[key]
        snapshot = EvaluationSnapshot(self.plan, values, self, arithmetic=arithmetic)
        self.snapshots[key] = snapshot
        if len(self.snapshots) > self.capacity:
            self.snapshots.popitem(last=False)
        return snapshot

    def fixed_snapshot(self):
        """No variable values: only genuinely constant constructions can evaluate."""
        return EvaluationSnapshot(self.plan, None, self)


@contextmanager
def evaluation_session(evaluator):
    store = getattr(evaluator, "evaluation_store", None)
    if store is None or store is _active_store.get():
        yield
        return
    token = _active_store.set(store)
    try:
        yield
    finally:
        _active_store.reset(token)


def uses_evaluation_store(parameter="evaluator"):
    def decorate(function):
        parameter_index = tuple(signature(function).parameters).index(parameter)

        @wraps(function)
        def scoped(*args, **kwargs):
            evaluator = kwargs.get(parameter)
            if evaluator is None and parameter_index < len(args):
                evaluator = args[parameter_index]
            with evaluation_session(evaluator):
                return function(*args, **kwargs)

        return scoped

    return decorate


def numerical_snapshot(spec, var_names, values, base_context, *, arithmetic="hp"):
    converted = []
    for value in values:
        if isinstance(value, float):
            converted.append(boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE))
        else:
            converted.append(strict_to_mpf(value, context="evaluation_snapshot.coordinate"))
    store = _active_store.get()
    if store is None or not store.plan.accepts(spec, var_names, base_context):
        store = EvaluationStore(spec=spec, var_names=var_names, base_context=base_context)
    return store.get(converted, arithmetic=arithmetic)
