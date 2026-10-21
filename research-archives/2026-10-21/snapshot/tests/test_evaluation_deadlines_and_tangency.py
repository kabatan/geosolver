"""Small synthetic regressions for inner deadlines and zero-test conditioning."""

from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.verification_numerics import differentiate
from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.nomad_blackbox_adapter import NomadBlackboxAdapter
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.deadline import deadline_scope, runtime_session


def test_deadline_after_dsl_call_is_not_converted_to_a_domain_failure(monkeypatch):
    clock = [0]
    monkeypatch.setattr("geosolver.runtime.deadline.time.monotonic", lambda: clock[0])

    def late():
        clock[0] = 2
        return 1

    with deadline_scope(1), pytest.raises(TimeoutError):
        safe_eval_expr_hp("Late()", {"Late": late})


def test_nomad_does_not_evaluate_more_stages_or_publish_after_its_deadline(monkeypatch):
    clock = [0]
    monkeypatch.setattr("geosolver.runtime.deadline.time.monotonic", lambda: clock[0])

    def late(_values):
        clock[0] = 2
        return SimpleNamespace(evaluation_status=EvaluationStatus.OK)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("an expired callback continued")

    ev = SimpleNamespace(
        evaluate_float_residual=late,
        evaluate_float_hard_feasibility=forbidden,
        evaluate_guard=forbidden,
    )
    point = SimpleNamespace(size=lambda: 1, get_coord=lambda _i: 0, setBBO=forbidden)
    adapter = NomadBlackboxAdapter(
        evaluator=ev,
        config=NomadConfig(max_bb_eval=10),
        origin_seed=0,
        origin_start_point_index=0,
        deadline_monotonic=1,
    )
    assert adapter(point) == 0
    assert not adapter.records


def test_large_regular_polygon_checks_deadline_inside_the_loop(monkeypatch):
    hp = _get_high_precision_context(80)
    a, b = hp["Point"](0, 0), hp["Point"](1, 0)
    clock = [0]

    def ticks():
        clock[0] += 1
        return clock[0]

    monkeypatch.setattr("geosolver.runtime.deadline.time.monotonic", ticks)
    with deadline_scope(5), pytest.raises(TimeoutError):
        hp["RegularPolygon"](a, b, 100000)
    assert clock[0] <= 6


def test_tangency_difference_resolves_without_repeated_cusp_shrinking():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "L", "expr": "Line(Point(-1,x),Point(1,x))"},
                    {"name": "W", "expr": "Circle(Point(0,0),1)"},
                ],
                "constraints": ["IsTangent(L,W)"],
                "answer": "x",
            }
        )
    )
    with runtime_session(None), mp.workdps(180), high_precision_mode():
        equation = ev.verification_equations[0]
        assert "_SignedTangency" in equation.source
        samples = [0]

        def sampled(point):
            samples[0] += 1
            return equation.sample(point, 180)

        derivative = differentiate(sampled, (mp.mpf(1),), 0, mp.mpf(1), 180)
        assert derivative is not None and abs(derivative[0] - 1) <= derivative[1]
        assert samples[0] == 5  # base + two central differences, each at two precisions


def test_nonzero_tangency_equations_are_never_signed():
    from geosolver.engine.standard.evaluation.verification_numerics import _smooth_zero_equation

    for expression in ("IsTangent(L,W)-1", "IsTangent(L,W)+1", "1/IsTangent(L,W)"):
        assert "_SignedTangency" not in _smooth_zero_equation(expression)


def test_hp_contract_inspects_signature_only_at_decoration(monkeypatch):
    from geosolver.engine.standard.precision.type_guards import hp_contract as module

    @module.hp_contract(input_names=("value",))
    def identity(value):
        return value

    def forbidden(*_args):
        raise AssertionError("signature inspection in numerical loop")

    monkeypatch.setattr(module, "signature", forbidden)
    with high_precision_mode():
        for _ in range(10):
            assert identity(mp.mpf(1)) == 1
        with pytest.raises(TypeError):
            identity(1.0)
