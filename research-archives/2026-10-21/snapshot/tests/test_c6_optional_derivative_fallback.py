"""An optional derivative compiler must not disable a solvable original system."""

from contextlib import nullcontext

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import analytic_jacobian as analytic
from geosolver.engine.standard.refinement import mpmath_refiner as refiner
from geosolver.runtime import symbolic
from geosolver.runtime.deadline import runtime_session


def evaluator(aliases=0):
    construction = []
    source = "x+y"
    if aliases:
        construction = [{"name": "a0", "expr": "x"}] + [
            {"name": f"a{i}", "expr": f"a{i - 1}"} for i in range(1, aliases)
        ]
        source = f"a{aliases - 1}+y"
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "construction": construction,
                "constraints": [source, "x-y"],
                "v": [3, 1],
                "answer": "x*y",
            }
        )
    )


def assert_original_system_closes(ev):
    with mp.workdps(150), high_precision_mode():
        result = refiner._run_findroot_closure(
            evaluator=ev,
            start_point=[mp.mpf("1.99"), mp.mpf("1.01")],
            bounds=((None, None),) * 2,
            dps=120,
            target_residual=mp.mpf("1e-90"),
            max_steps=10,
        )
        assert result is not None
        assert max(
            abs(value - wanted) for value, wanted in zip(result[0], (2, 1), strict=True)
        ) < mp.mpf("1e-90")
        checked = ev.evaluate_hp_residual(result[0], precision=120)
        assert len(checked.residual_vector) == 2
        assert max(map(abs, checked.residual_vector)) < mp.mpf("1e-90")


@pytest.mark.parametrize("worker", [False, True])
def test_valid_alias_chain_exceeding_optional_recursion_capacity_keeps_numerical_closure(worker):
    # The numerical construction evaluator visits aliases iteratively in DSL
    # order; the optional symbolic geometry compiler recursively expands them.
    analytic._plan.cache_clear()
    ev = evaluator(aliases=600)
    with runtime_session(None) if worker else nullcontext():
        assert analytic.derivative_plan(ev.bundle) is None
        assert_original_system_closes(ev)
    analytic._plan.cache_clear()


@pytest.mark.parametrize(
    "error", [ValueError, TypeError, ArithmeticError, KeyError, RecursionError]
)
def test_optional_compile_error_keeps_original_closure_and_caches_unsupported(monkeypatch, error):
    analytic._plan.cache_clear()
    calls = []

    def failed(*args, **kwargs):
        calls.append((args, kwargs))
        raise error("independent optional compiler rejection")

    monkeypatch.setattr(symbolic, "request", failed)
    ev = evaluator()
    assert_original_system_closes(ev)
    assert len(calls) == 1
    assert analytic.derivative_plan(ev.bundle) is None
    assert len(calls) == 1
    analytic._plan.cache_clear()


def test_solve_deadline_from_optional_plan_still_propagates(monkeypatch):
    analytic._plan.cache_clear()

    def expired(*args, **kwargs):
        raise TimeoutError("independent global deadline")

    monkeypatch.setattr(symbolic, "request", expired)
    with pytest.raises(TimeoutError, match="global deadline"):
        assert_original_system_closes(evaluator())
    analytic._plan.cache_clear()
