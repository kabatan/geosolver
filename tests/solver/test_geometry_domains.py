"""Geometry domains contracts and numerical regressions."""

import time

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.deadline import runtime_session


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


def boundary_evaluator(kind, *, equation="x*x", extra_guards=()):
    constructions = [
        {"name": "A", "expression": "Point(0,0)"},
        {"name": "B", "expression": "Point(0,1)"},
        {"name": "P", "expression": "Point(x,0)"},
    ]
    conditions = [{"left": equation, "operator": "=", "right": 0}]
    target = "1"
    if kind == "line":
        conditions.append(
            {"left": "Perpendicular(Line(A,P),Line(A,B))", "operator": "=", "right": 0}
        )
    elif kind == "circle":
        target = "Distance(Center(Circle(A,x)),B)"
    elif kind == "segment_keyword":
        target = "Distance(PointOnSegment(A=A,B=P,t=0),B)"
    elif kind == "acute":
        constructions = [
            {"name": "A", "expression": "Point(-x,0)"},
            {"name": "B", "expression": "Point(x,0)"},
            {"name": "C", "expression": "Point(0,sqrt(3)*x)"},
        ]
        conditions.append({"predicate": "AcuteTriangle(A,B,C)"})
    else:
        constructions = [
            {"name": "A", "expression": "Point(0,0)"},
            {"name": "B", "expression": "Point(1,0)"},
            {"name": "C", "expression": "Point(1,x)"},
            {"name": "D", "expression": "Point(0,x)"},
        ]
        name = {"convex": "ConvexPolygon", "simple": "SimplePolygon"}[kind]
        conditions.append({"predicate": f"{name}([A,B,C,D])"})
    conditions.extend({"predicate": guard} for guard in extra_guards)
    problem = GeometryProblem(
        id="artificial-boundary",
        variables=["x"],
        constructions=constructions,
        conditions=conditions,
        target=target,
    )
    return build_ir_evaluator(load_problem_bundle(problem.engine_document()))


@pytest.mark.parametrize("kind", ["line", "circle", "segment_keyword", "convex", "simple", "acute"])
def test_inline_and_shape_boundaries_never_accept_a_collapsing_solution(kind):
    with mp.workdps(600), runtime_session(time.monotonic() + 15):
        result = verify_final_candidate(
            evaluator=boundary_evaluator(kind), values=(mp.mpf("1e-60"),)
        )
    assert not result.verified
    assert "domain_boundary_unresolved" in result.hard_failure_tags


@pytest.mark.parametrize("kind", ["line", "circle", "segment_keyword", "convex", "simple", "acute"])
@pytest.mark.parametrize("value", ["1", "1e-40", "1e-100"])
def test_the_same_shapes_with_genuinely_positive_scale_remain_valid(kind, value):
    with mp.workdps(600), runtime_session(time.monotonic() + 15):
        result = verify_final_candidate(
            evaluator=boundary_evaluator(kind, equation=f"x-({value})"),
            values=(mp.mpf(value),),
        )
    assert result.verified, result.hard_failure_tags


@pytest.mark.parametrize("mode", ["nested_convex", "negated_right", "near_right"])
def test_shape_predicates_do_not_hide_boundaries_inside_logic(mode):
    constructions = [
        {"name": "A", "expression": "Point(-1,0)"},
        {"name": "B", "expression": "Point(0,x)" if mode == "nested_convex" else "Point(0,1+x)"},
        {"name": "C", "expression": "Point(1,0)"},
    ]
    if mode == "nested_convex":
        constructions.append({"name": "D", "expression": "Point(0,-1)"})
        predicate = "And(ConvexPolygon([A,B,C,D]),1>0)"
    else:
        predicate = (
            "Not(RightTriangle(A,B,C))" if mode == "negated_right" else "RightTriangle(A,B,C)"
        )
    value = "1e-200" if mode == "near_right" else "1e-60"
    problem = GeometryProblem(
        id="artificial-logical-boundary",
        variables=["x"],
        constructions=constructions,
        conditions=[
            {
                "left": f"x-({value})" if mode == "near_right" else "x*x",
                "operator": "=",
                "right": 0,
            },
            {"predicate": predicate},
        ],
        target="1",
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 10):
        result = verify_final_candidate(
            evaluator=build_ir_evaluator(load_problem_bundle(problem.engine_document())),
            values=(mp.mpf(value),),
        )
    assert not result.verified


@pytest.mark.parametrize(
    "guard",
    [
        "RightTriangle(A,B,C)",
        "Not(AcuteTriangle(A,B,C))",
        "Or(ObtuseTriangle(A,B,C),RightTriangle(A,B,C))",
        "RightTriangle(A=A,B=B,C=C)",
    ],
)
def test_exact_right_triangle_is_not_lost_in_logical_or_keyword_forms(guard):
    problem = GeometryProblem(
        id="right-control",
        variables=["x"],
        constructions=[
            {"name": "A", "expression": "Point(0,0)"},
            {"name": "B", "expression": "Point(x,0)"},
            {"name": "C", "expression": "Point(0,x)"},
        ],
        conditions=[{"left": "x-1e-100", "operator": "=", "right": 0}, {"predicate": guard}],
        target="x",
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 10):
        result = verify_final_candidate(
            evaluator=build_ir_evaluator(load_problem_bundle(problem.engine_document())),
            values=(mp.mpf("1e-100"),),
        )
    assert result.verified, result.hard_failure_tags


@pytest.mark.parametrize("scale", ["1", "1e-100"])
def test_coefficient_line_is_not_mistaken_for_two_endpoints(scale):
    problem = GeometryProblem(
        id="coefficient-line",
        variables=["x"],
        constructions=[
            {"name": "ell", "expression": "Line(x,0,-2*x)"},
            {"name": "A", "expression": "Point(0,0)"},
        ],
        conditions=[{"left": f"x-({scale})", "operator": "=", "right": 0}],
        target="Distance(A,ell)",
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 10):
        result = verify_final_candidate(
            evaluator=build_ir_evaluator(load_problem_bundle(problem.engine_document())),
            values=(mp.mpf(scale),),
        )
    assert result.verified and result.answer_hp == 2, result.hard_failure_tags


def test_collapsing_line_coefficients_remain_a_domain_rejection():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [{"name": "ell", "expr": "Line(x,0,-2*x)"}],
                "constraints": ["x*x"],
                "answer": "1",
            }
        )
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 10):
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf("1e-60"),))
    assert not result.verified


@pytest.mark.parametrize(
    "expression",
    [
        "Triangle(A,B,C)",
        "Triangle([A,B,C])",
        "Triangle(points=[A,B,C])",
        "Polygon(arg1=[A,B,C])",
        "Line(A=A,B=B)",
        "Line(A,B=B)",
    ],
)
def test_public_constructor_call_forms_work_in_both_arithmetic_contexts(expression):
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.ir.compiler import safe_eval_expr, safe_eval_expr_hp

    with mp.workdps(80):
        for context, evaluate in (
            (_get_geometry_context(), safe_eval_expr),
            (_get_high_precision_context(), safe_eval_expr_hp),
        ):
            context = dict(context)
            for name, source in {"A": "Point(0,0)", "B": "Point(1,0)", "C": "Point(0,1)"}.items():
                context[name] = evaluate(source, context)
            result = evaluate(expression, context)
            if expression.startswith("Line"):
                assert result.a == 0 and result.c == 0 and result.b != 0
            else:
                assert len(result.vertices) == 3 and result.area > 0


@pytest.mark.parametrize(
    "expression",
    ["Triangle(A,B,C)", "Triangle([A,B,C])", "Triangle(points=[A,B,C])", "Triangle(A,B,C,A)"],
)
def test_triangle_constructor_rejects_collinearity_and_wrong_vertex_count(expression):
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.ir.compiler import IRCompileError, safe_eval_expr, safe_eval_expr_hp

    with mp.workdps(80):
        for context, evaluate in (
            (_get_geometry_context(), safe_eval_expr),
            (_get_high_precision_context(), safe_eval_expr_hp),
        ):
            context = dict(context)
            for name, source in {"A": "Point(0,0)", "B": "Point(1,0)", "C": "Point(2,0)"}.items():
                context[name] = evaluate(source, context)
            with pytest.raises(IRCompileError):
                evaluate(expression, context)


@pytest.mark.parametrize("predicate", ["SimplePolygon", "ConvexPolygon"])
def test_polygon_object_and_optional_message_work_in_both_contexts(predicate):
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.ir.compiler import safe_eval_expr, safe_eval_expr_hp

    with mp.workdps(80):
        for context, evaluate in (
            (_get_geometry_context(), safe_eval_expr),
            (_get_high_precision_context(), safe_eval_expr_hp),
        ):
            value = evaluate(
                f"{predicate}(Polygon([Point(0,0),Point(1,0),Point(0,1)]), 'note')",
                context,
            )
            assert value is None or bool(value)


@pytest.mark.parametrize(
    "expression",
    [
        "AcuteTriangle(Point(0,0),Point(2,0),Point(1,2))",
        "RightTriangle(Point(0,0),Point(1,0),Point(0,1))",
        "ObtuseTriangle(Point(0,0),Point(1,0),Point(2,1))",
        "ConvexPolygon([Point(0.1,0),Point(1.1,0),Point(0.1,1)])",
    ],
)
def test_standard_geometry_guards_do_not_feed_python_floats_to_strict_mp_constructors(expression):
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.problem.ir.compiler import safe_eval_expr

    value = safe_eval_expr(expression, _get_geometry_context())
    assert value is None or bool(value)


def test_geometry_guard_conversion_does_not_launder_low_precision_points():
    from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
        HighPrecisionContaminationError,
    )
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )
    from geosolver.geometry.safety.guards import _as_mp_point

    with high_precision_mode(), pytest.raises(HighPrecisionContaminationError):
        _as_mp_point((0.1, 0.2), to_point_xy=lambda point: point)


@pytest.mark.parametrize(
    "construction,predicate",
    [
        ("Triangle([A,B,C])", None),
        ("Triangle(points=[A,B,C])", None),
        ("Line(A=A,B=B)", None),
        ("Polygon([A,B,C])", "SimplePolygon([A,B,C], 'note')"),
        ("Polygon([A,B,C])", "ConvexPolygon([A,B,C], 'note')"),
        ("Polygon([A,B,C])", "SimplePolygon(polygon=T, message='note')"),
        ("Polygon([A,B,C])", "And(ConvexPolygon(polygon=T, message='note'),1>0)"),
    ],
)
@pytest.mark.parametrize("collapsing", [False, True])
def test_shape_call_forms_preserve_final_domain_checks(construction, predicate, collapsing):
    value = "1e-60" if collapsing else "1e-100"
    conditions = [{"left": "x*x" if collapsing else f"x-({value})", "operator": "=", "right": 0}]
    if predicate is not None:
        conditions.append({"predicate": predicate})
    problem = GeometryProblem(
        id="shape-call-forms",
        variables=["x"],
        constructions=[
            {"name": "A", "expression": "Point(0,0)"},
            {"name": "B", "expression": "Point(x,0)"},
            {"name": "C", "expression": "Point(0,x)"},
            {"name": "T", "expression": construction},
        ],
        conditions=conditions,
        target="1",
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 10):
        result = verify_final_candidate(
            evaluator=build_ir_evaluator(load_problem_bundle(problem.engine_document())),
            values=(mp.mpf(value),),
        )
    assert result.verified is not collapsing, result.hard_failure_tags
    if collapsing:
        assert "domain_boundary_unresolved" in result.hard_failure_tags


def test_zero_line_distance_still_rejects_coincident_line_endpoints():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(0,0)"},
                    {"name": "P", "expr": "Point(0,x)"},
                ],
                "constraints": ["Distance(P,Line(A,B))"],
                "guards": [],
                "answer": "x",
            }
        )
    )
    with mp.workdps(180), runtime_session(None):
        assert not verify_final_candidate(evaluator=ev, values=(mp.mpf(0),)).verified


def test_unused_circle_still_excludes_zero_radius_in_original_final_domain():
    from mpmath import mp

    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.adapter import to_engine_document

    # The contact equality alone has both roots r=0 and r=1. The declared
    # Circle(B,r), even if unused by that equality, makes r=0 inadmissible.
    definitions = (
        ("P", "Point(2,0)"),
        ("Q", "Point(0,2)"),
        ("S", "Point(-2,0)"),
        ("G", "Circumcircle(P,Q,S)"),
        ("B", "Point(2-2*r,r)"),
        ("unused", "Circle(B,r)"),
    )
    problem = GeometryProblem.model_validate(
        {
            "id": "unused-positive-domain-counterexample",
            "variables": ["r"],
            "constructions": [{"name": n, "expression": e} for n, e in definitions],
            "conditions": [
                {"left": "Distance(B,Center(G))", "operator": "=", "right": "Radius(G)-r"}
            ],
            "target": "r",
        }
    )
    evaluator = build_ir_evaluator(load_problem_bundle(to_engine_document(problem)))
    assert not verify_final_candidate(evaluator=evaluator, values=(mp.mpf(0),)).verified
    assert verify_final_candidate(evaluator=evaluator, values=(mp.mpf(1),)).verified
