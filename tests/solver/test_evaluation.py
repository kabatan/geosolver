"""Evaluation contracts and numerical regressions."""

from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.float_expressions import residual_norm
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


@pytest.mark.parametrize("scale", [1e300, 1e-300])
def test_residual_norm_avoids_intermediate_overflow_and_underflow(scale):
    assert residual_norm([3 * scale, 4 * scale]) == pytest.approx(5 * scale, abs=0)


def test_residual_norm_retains_ordinary_search_rounding_and_rescues_subnormals():
    assert residual_norm([0.1, 0.2, 0.3]) == 0.37416573867739417
    assert residual_norm([3e-162, 4e-162]) == pytest.approx(5e-162, abs=0)


def test_scaled_score_handles_extreme_finite_residuals_without_exception():
    import math

    from geosolver.engine.standard.evaluation.scaled_score import scaled_score

    assert scaled_score([3e300, 4e300], [1e300, 1e300]) == 25
    assert math.isinf(scaled_score([1e300]))


def test_scaled_score_preserves_exactly_representable_sum_for_search_ordering():
    from geosolver.engine.standard.evaluation.scaled_score import scaled_score

    # hypot(1, 1)**2 is 2.0000000000000004 and changes ordinary score ties.
    assert scaled_score([1.0, 1.0]) == 2.0


def evaluator(constraints, *, construction=(), guards=(), variables=("x",), answer="7"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "id": "second-audit",
                "task": "solve",
                "variables": {"names": list(variables)},
                "construction": list(construction),
                "constraints": [{"def": text, "value": 0} for text in constraints],
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


def test_redundant_geometric_identity_keeps_roundoff_scale():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(
                ["x*x-2", "Distance(A,D)-p*Distance(A,B)"],
                variables=("x", "p"),
                construction=[
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(x,1)"},
                    {"name": "D", "expr": "PointOnSegment(A,B,p)"},
                ],
                guards=["x>0", "p>0", "p<1"],
                answer="x*x",
            ),
            values=(mp.sqrt(2), mp.mpf("0.1234567")),
        )
    assert result.verified and abs(result.answer_hp - 2) < mp.mpf("1e-100")


def test_large_cancelled_terms_do_not_hide_a_nonlinear_contradiction():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(["(1e200+x)-(1e200+x+1+x*x)"]), values=(mp.mpf(0),)
        )
    assert not result.verified


def test_noisy_redundant_row_does_not_erase_reliable_rank():
    from geosolver.engine.standard.evaluation.verification_numerics import correction

    with mp.workdps(500):
        change, uncertainty = correction(
            [mp.mpf("1e-350"), mp.mpf(-1)],
            [[mp.mpf("1e-300")], [mp.mpf(1)]],
            [[mp.mpf("1e-299")], [mp.mpf("1e-450")]],
            [mp.mpf(1)],
            500,
        )
    assert change == (mp.mpf(1),) and mp.isfinite(uncertainty[0])


@pytest.mark.parametrize(
    "selector, line, condition",
    [
        ("near=P", "Line(Point(-2,0),Point(2,0))", "Q.x+2"),
        ("n=1", "Line(Point(0,0),Point(x,1))", "Q.y+2"),
    ],
)
def test_branch_crossing_cannot_normalize_an_order_one_residual(selector, line, condition):
    constructions = [
        {"name": "C", "expr": "Circle(Point(0,0),1)"},
        {"name": "L", "expr": line},
        {"name": "P", "expr": "Point(x,0)"},
        {"name": "Q", "expr": f"Intersect(C,L,{selector})"},
    ]
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator([condition], construction=constructions), values=(mp.mpf("1e-60"),)
        )
    assert not result.verified
