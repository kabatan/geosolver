"""Minimal counterexamples from the final audit (not performance benchmarks)."""

import pytest
from mpmath import mp

from geosolver import GeometryProblem, solve
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.exact.descriptors import assemble_exact_answers
from geosolver.problem.ir.compiler import safe_eval_expr, safe_eval_expr_hp


def test_inner_tangent_public_answer():
    problem = GeometryProblem(
        id="inner-tangent",
        variables=[],
        conditions=[],
        constructions=[
            {"name": "P", "expression": "Intersect(Circle(Point(0,0),1),Circle(Point(1,0),2))"}
        ],
        target="Distance(P,Point(1,0))",
    )
    result = solve(problem)
    assert result.answers[0].minimal_polynomial == ["1", "-2"]


@pytest.mark.parametrize("offset", ["1e100", "1e1000"])
def test_constant_contradiction_never_publishes_an_answer(offset):
    result = solve(
        GeometryProblem(
            id="contradiction",
            variables=[],
            constructions=[],
            conditions=[{"left": offset, "operator": "=", "right": offset + "+1"}],
            target="42",
        )
    )
    assert not result.answers


def test_exact_root_is_not_nsimplified_to_a_nearby_rational():
    with mp.workdps(150):
        value = mp.findroot(lambda x: x**8 - 10**7 * x + 1, mp.mpf("1e-7"))
        result = identify_answer(answer_hp=value, tier="strict", input_precision_dps=120)
        assert result.exact_status == "identified"
        assert result.selected_exact_value != "1/10000000"


def test_close_exact_roots_remain_distinct():
    answers, warnings = assemble_exact_answers(["1-sqrt(2)/10**130", "1+sqrt(2)/10**130"])
    assert not warnings
    assert len(answers) == 2
    assert {answer.value.real_root_index for answer in answers} == {0, 1}


@pytest.mark.parametrize(
    "expression",
    [
        "Intersect(Line(Point(-4,-1),Point(2,1)),Circle(Point(-1,0),2),1).x",
        "Slope(Point(0,0),Point(1,1))",
        "Slope(first=Point(0,0),second=Point(1,1))",
        "Dot(Line(Point(0,0),Point(1,1)),Line(Point(0,1),Point(1,2)))",
        "Perimeter(RegularPolygon(Point(0,0),Point(1,0),4))",
        "PointOnArc(Arc(Circle(Point(0,0),1),Point(1,0),Point(0,-1)),0.5).x",
        "PointOnArc(Arc(Circle(Point(0,0),1),Point(1,0),Point(0,-1),including=Point(-1,0)),0.5).x",
    ],
)
def test_audited_dsl_calls_agree(expression):
    with mp.workdps(80):
        standard = safe_eval_expr(expression, _get_geometry_context())
        high = safe_eval_expr_hp(expression, _get_high_precision_context(80))
        assert float(standard) == pytest.approx(float(high), abs=1e-13)


def test_small_algebraic_scale_is_exactly_reconstructed():
    with mp.workdps(150):
        result = identify_answer(
            answer_hp=mp.sqrt(2) / 10**10, tier="strict", input_precision_dps=120
        )
        assert result.exact_status == "identified"


def test_tangent_boundary_is_not_rejected_by_derivative():
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.ir.schema import IRConstruction, IRSpec, IRVariableSpec

    spec = IRSpec(
        task="solve",
        variables=IRVariableSpec(names=["x"]),
        bounds=[(0, 2)],
        construction=[
            IRConstruction("Q", "Intersect(Line(Point(-1,0),Point(1,0)),Circle(Point(0,x),1),n=1)")
        ],
        constraints=["x"],
        v=[1],
        answer_expr="Q.x",
    )
    result = verify_final_candidate(
        evaluator=build_ir_evaluator(load_problem_bundle(spec)), values=(mp.mpf(1),)
    )
    assert result.verified


def test_common_offset_cannot_hide_variable_contradiction():
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.ir.schema import IRSpec, IRVariableSpec

    spec = IRSpec(
        task="solve",
        variables=IRVariableSpec(names=["x"]),
        constraints=["1e1000+x"],
        v=["1e1000+x+1"],
        answer_expr="x",
    )
    result = verify_final_candidate(
        evaluator=build_ir_evaluator(load_problem_bundle(spec)), values=(mp.mpf(1),)
    )
    assert not result.verified


@pytest.mark.parametrize("scale", ["1", "1e-100", "1e100"])
def test_hp_circle_domain_is_invariant_under_scaling(scale):
    from geosolver.errors import NoIntersectionError

    with mp.workdps(120):
        hp = _get_high_precision_context(120)
        s = mp.mpf(scale)
        circle1 = hp["Circle"](hp["Point"](0, 0), s)
        circle2 = hp["Circle"](hp["Point"](3 * s, 0), s)
        with pytest.raises(NoIntersectionError):
            hp["Intersect"](circle1, circle2)
