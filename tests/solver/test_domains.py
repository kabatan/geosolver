"""Domains contracts and numerical regressions."""

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.errors import IRCompileError


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


@pytest.mark.parametrize("t", ["-1", "2"])
def test_segment_rejects_extrapolation_in_both_contexts(t):
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.ir.compiler import safe_eval_expr

    expression = f"PointOnSegment(Point(0,0),Point(1,0),{t})"
    with pytest.raises(IRCompileError):
        safe_eval_expr(expression, _get_geometry_context())
    with pytest.raises(IRCompileError):
        safe_eval_expr_hp(expression, _get_high_precision_context(80))


@pytest.mark.parametrize("t", ["-2", "2", "0.4"])
def test_extension_migration_preserves_coordinates(t):
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )

    with mp.workdps(120):
        ctx = _get_high_precision_context(120)
        ctx["A"] = safe_eval_expr_hp("Point(2,3)", ctx)
        ctx["B"] = safe_eval_expr_hp("Point(5,7)", ctx)
        ctx["L"] = safe_eval_expr_hp("Line(A,B)", ctx)
        p = safe_eval_expr_hp(
            f"PointOnLine(L,-L.b*(A.x+({t})*(B.x-A.x))+L.a*(A.y+({t})*(B.y-A.y)))", ctx
        )
        assert abs(p.x - (2 + mp.mpf(t) * 3)) < mp.mpf("1e-110")
        assert abs(p.y - (3 + mp.mpf(t) * 4)) < mp.mpf("1e-110")


@pytest.mark.parametrize("constraint", ["x", "x**2"])
def test_forbidden_zero_boundary_is_not_a_solution(constraint):
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator([constraint], guards=["x>0"]), values=(mp.mpf("1e-40"),)
        )
    assert not result.verified


def test_tiny_positive_solution_is_not_a_boundary():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(["x-1e-40"], guards=["x>0"]), values=(mp.mpf("1e-40"),)
        )
    assert result.verified


def test_periodic_circle_parameter_is_not_a_hard_unit_interval():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(
                ["x-2"],
                construction=[{"name": "P", "expr": "PointOnCircle(Circle(Point(0,0),1),x)"}],
                answer="x",
            ),
            values=(mp.mpf(2),),
        )
    assert result.verified and result.answer_hp == 2


def test_gauge_freedom_and_redundant_equations_are_allowed():
    with mp.workdps(180):
        result = verify_final_candidate(
            evaluator=evaluator(
                ["x-y-1", "2*(x-y-1)"], variables=("x", "y"), guards=["y>0"], answer="x-y"
            ),
            values=(mp.mpf(3), mp.mpf(2)),
        )
    assert result.verified and result.answer_hp == 1
