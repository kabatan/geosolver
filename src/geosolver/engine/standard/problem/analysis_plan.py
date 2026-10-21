"""Solve-local static analysis. Point-dependent scales and branches never live here."""

from functools import cached_property

from mpmath import mp

from geosolver.problem.domain_bounds import search_bounds
from geosolver.problem.ir.compiler import extract_names


class ProblemAnalysisPlan:
    def __init__(self, bundle):
        self.bundle = bundle
        self._precision_bounds = {}
        self._mathematical_bounds = {}

    @cached_property
    def bounds(self):
        return tuple(search_bounds(self.bundle.spec))

    def bounds_at_precision(self, precision):
        if precision not in self._precision_bounds:
            with mp.workdps(precision):
                self._precision_bounds[precision] = tuple(
                    tuple(mp.mpf(str(value)) for value in pair) for pair in self.bounds
                )
        return self._precision_bounds[precision]

    @cached_property
    def integer_specs(self):
        from geosolver.engine.standard.refinement.mpmath_refiner import _build_integer_specs

        return _build_integer_specs(bundle=self.bundle)

    def mathematical_bounds_at_precision(self, precision):
        if precision not in self._mathematical_bounds:
            from geosolver.engine.standard.refinement.mpmath_refiner import _convert_bounds_uncached

            self._mathematical_bounds[precision] = _convert_bounds_uncached(self.bundle, precision)
        return self._mathematical_bounds[precision]

    @cached_property
    def answer_closed(self):
        source = self.bundle.spec.answer_expr
        return bool(source) and set(extract_names(source)) <= {
            "sqrt",
            "sin",
            "cos",
            "tan",
            "pi",
            "abs",
            "Abs",
        }

    @cached_property
    def answer_uses_pi(self):
        """A discovery-order hint, never an assertion about the exact answer."""
        spec = self.bundle.spec
        names = set(extract_names(spec.answer_expr or spec.objective_expr or "0"))
        for item in reversed(spec.construction):
            if item.name in names:
                names.update(extract_names(item.expr))
        return bool(names & {"pi", "Angle"})

    @cached_property
    def residual_variable_dependencies(self):
        """Conservative transitive variable dependencies for each residual row."""
        from geosolver.problem.logical_equalities import evaluation_sources

        spec = self.bundle.spec
        indices = {name: index for index, name in enumerate(self.bundle.var_names)}
        dependencies = {name: frozenset((index,)) for name, index in indices.items()}

        def referenced(source):
            return frozenset().union(
                *(dependencies.get(name, ()) for name in extract_names(source))
            )

        for item in spec.construction:
            dependencies[item.name] = referenced(item.expr)
        targets = spec.v or [0] * len(spec.constraints)
        return tuple(
            frozenset().union(
                *(
                    referenced(source)
                    for source in evaluation_sources(expression, spec.logical_plans)
                ),
                referenced(str(target)),
            )
            for expression, target in zip(spec.constraints, targets, strict=True)
        )
