"""Multi-output sampling at identical perturbations, with evidence per equation.

Only one linearization owns this small cache. Arithmetic comparisons and each
row's adaptive difference decisions remain the scalar verifier's decisions.
"""

from mpmath import mp

from geosolver.engine.standard.evaluation.high_precision_expressions import to_mpf_value
from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.deadline import check_deadline, count_event


def sample_equations(equations, point, precision):
    """Batch a correction trial while retaining the scalar adapter contract."""
    from .verification_numerics import Equation

    if not equations or not all(isinstance(e, Equation) for e in equations):
        return tuple(e.sample(point, precision) for e in equations)
    system = VerificationSystem(equations)
    indices = tuple(range(len(equations)))
    return tuple(system.sample(i, point, precision, indices) for i in indices)


class VerificationSystem:
    def __init__(self, equations):
        self.equations = equations
        self.samples = {}

    def _evaluate(self, point, indices, precision):
        check_deadline()
        first = self.equations[indices[0]].evaluator
        bundle = first.bundle
        results = {}
        with mp.workdps(precision), evaluation_session(first):
            snapshot = numerical_snapshot(bundle.spec, bundle.var_names, point, bundle.base_context)
            count_event("verification_system_evaluations")
            for i in indices:
                check_deadline()
                equation = self.equations[i]
                with capture_selection_trace() as trace:
                    try:
                        context = snapshot.for_expressions((equation.source,))
                        value = to_mpf_value(
                            safe_eval_expr_hp(equation.source, context),
                            precision=precision,
                            context=f"verification_equation:{i}",
                        ) - mp.mpf(0)
                    except (TimeoutError, HighPrecisionContaminationError):
                        raise
                    except Exception:
                        value = mp.nan
                results[i] = value, tuple(trace)
                count_event("verification_equation_evaluations")
        return results

    def sample(self, index, point, precision, indices):
        from geosolver.engine.standard.evaluation.verification_numerics import same_branches

        coordinates = tuple(v._mpf_ for v in point)
        key = (coordinates, precision)
        known = self.samples.setdefault(key, {})
        missing = tuple(i for i in indices if i not in known)
        if missing:
            low = self._evaluate(point, missing, precision)
            high = self._evaluate(point, missing, precision + 30)
            with mp.workdps(precision):
                epsilon = +mp.eps
            with mp.workdps(precision + 30):
                for i in missing:
                    a, trace = low[i]
                    b, other = high[i]
                    error = (
                        4 * abs(b - a) + 32 * epsilon * abs(b)
                        if mp.isfinite(a) and mp.isfinite(b) and same_branches(trace, other)
                        else mp.inf
                    )
                    known[i] = b, other, error
        return known[index]
