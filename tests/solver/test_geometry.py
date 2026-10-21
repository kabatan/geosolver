"""Geometry contracts and numerical regressions."""

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
from geosolver.engine.standard.interpreter.context.high_precision import (
    _get_high_precision_context,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.errors import (
    AmbiguousResultError,
    InfiniteSolutionsError,
    InvalidCircleError,
    NoIntersectionError,
)
from geosolver.geometry import (
    AreConcyclic,
    AssumeAcute,
    Circle,
    Intersect,
    IntersectCircles,
    IntersectLineCircle,
    IsInteger,
    IsPrime,
    Line,
    Point,
    Tangent,
)
from geosolver.geometry.mp.mp_api import MP_Area, MP_Point, MP_PolygonArea
from geosolver.geometry.mp.mp_api_geometry import MP_Polar
from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint
from geosolver.geometry.runtime import BackendType, use_runtime
from geosolver.geometry.safety import AssumptionError
from geosolver.problem.ir.compiler import safe_eval_expr, safe_eval_expr_hp
from geosolver.runtime.deadline import runtime_session


def evaluator(constraints, *, construction=(), guards=(), answer="x"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": list(construction),
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


def test_nonzero_unsigned_area_equation_keeps_its_public_meaning():
    construction = [
        {"name": "A", "expr": "Point(0,0)"},
        {"name": "B", "expr": "Point(1,0)"},
        {"name": "C", "expr": "Point(0,x)"},
    ]
    with mp.workdps(180), runtime_session(None):
        ev = evaluator(["Area(A,B,C)-1"], construction=construction, answer="Area(A,B,C)")
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf(-2),))
        assert result.verified and result.answer_hp == 1


@pytest.mark.parametrize("scale", ["1e-200", "1", "1e200"])
def test_zero_area_equation_uses_signed_residual_without_changing_its_zero_set(scale):
    construction = [
        {"name": "A", "expr": "Point(0,0)"},
        {"name": "B", "expr": "Point(1,0)"},
        {"name": "C", "expr": "Point(0,x)"},
    ]
    with mp.workdps(180), runtime_session(None):
        ev = evaluator([f"{scale}*Area(A,B,C)"], construction=construction, answer="7")
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf("1e-100"),))
        assert result.verified
        # A finite-difference update need not land on bitwise zero. The
        # strengthened roundoff floor must cover its remaining coordinate error.
        assert abs(result.values[0]) <= result.coordinate_uncertainty[0]
        forbidden = evaluator([f"{scale}*Area(A,B,C)"], construction=construction, guards=["x>0"])
        assert not verify_final_candidate(evaluator=forbidden, values=(mp.mpf("1e-100"),)).verified
        bad = evaluator([f"{scale}*Area(A,B,C)", "x-1"], construction=construction)
        assert not verify_final_candidate(evaluator=bad, values=(mp.mpf(1),)).verified


@pytest.mark.parametrize("precision", [80, 180])
@pytest.mark.parametrize("name,function", [("IsInteger", IsInteger), ("IsPrime", IsPrime)])
def test_registered_mp_number_constraints_match_pipeline_without_symbolic_fallback(
    precision, name, function
):
    with mp.workdps(precision), high_precision_mode():
        hp = _get_high_precision_context(precision)
        values = [mp.mpf(v) for v in ("-3", "0", "2", "9", "1009", "3.5")]
        values.append(mp.mpf(3) + mp.mpf("1e-40"))
        for value in values:
            expected = hp[name](value)
            direct = function.mp(value)
            with use_runtime(backend=BackendType.MPMATH, precision=precision):
                dispatched = function(value)
            assert isinstance(direct, mp.mpf) and isinstance(dispatched, mp.mpf)
            assert direct == dispatched == expected
        assert IsPrime.mp(mp.mpf(1009)) == 0
        assert IsPrime.mp(mp.mpf(9)) > 0
        assert IsPrime.mp(mp.mpf(3) + mp.mpf("1e-40")) > 0
        assert IsInteger.mp(mp.mpf("3.5")) > 0


def test_public_polygon_area_and_acute_guards_keep_the_active_implementations():
    with mp.workdps(120), high_precision_mode():
        a, b, c = MP_Point(0, 0), MP_Point(4, 0), MP_Point(2, 3)
        assert MP_Area(a, b, c) == MP_PolygonArea(a, b, c) == 6
        AssumeAcute(a, b, c)
        with pytest.raises(AssumptionError):
            AssumeAcute(a, b, MP_Point(2, 0))


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


def test_mp_polar_at_circle_point_is_the_tangent_line() -> None:
    with mp.workdps(80):
        center = MPPoint(mp.mpf("1.5"), mp.mpf("-2"))
        circle = MPCircle(center, mp.mpf("5"))
        point = MPPoint(center.x + mp.mpf("3"), center.y + mp.mpf("4"))

        line = MP_Polar(point, circle)

        # The polar of a point on the circle is its tangent: it contains the
        # point, stays one radius from the center, and has the radial normal.
        assert abs(line.a * point.x + line.b * point.y + line.c) < mp.mpf("1e-70")
        assert abs(abs(line.c + line.a * center.x + line.b * center.y) - circle.radius) < mp.mpf(
            "1e-70"
        )
        assert abs(line.a * (point.y - center.y) - line.b * (point.x - center.x)) < mp.mpf("1e-70")


def test_float_and_hp_selector_evidence_identifies_the_physical_branch():
    from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.evaluation_trace import evaluation_scope
    from geosolver.problem.ir.compiler import safe_eval_expr

    source = "Intersect(Circle(Point(0,0),1),Line(Point(-2,0),Point(2,0)),near=Point(2,0))"
    traces = []
    for evaluate, context in (
        (safe_eval_expr, _get_geometry_context()),
        (safe_eval_expr_hp, _get_high_precision_context(120)),
    ):
        with mp.workdps(120), capture_selection_trace() as trace:
            for name in ("P", "Q"):
                with evaluation_scope(name):
                    evaluate(source, context)
        traces.append(trace)
    for trace in traces:
        assert len(trace) == 2 and trace[0].call_site_id != trace[1].call_site_id
        assert trace[0].candidate_count == 2 and trace[0].selected_index == 1
        assert trace[0].margin > 0
    assert tuple(tuple(mp.mpf(str(v)) for v in p) for p in traces[0][0].candidates) == (
        traces[1][0].candidates
    )


def _cross_at_contact(point, center, line) -> object:
    # The contact point is the foot from the center to the normalized tangent.
    signed = line.a * center.x + line.b * center.y + line.c
    tx = center.x - signed * line.a
    ty = center.y - signed * line.b
    return (point.x - center.x) * (ty - center.y) - (point.y - center.y) * (tx - center.x)


@pytest.mark.parametrize("radius", [0, -1])
def test_circles_require_positive_radius_in_both_contexts(radius: int) -> None:
    with pytest.raises(InvalidCircleError):
        Circle(Point(0, 0), radius)
    with pytest.raises(InvalidCircleError):
        MPCircle(MPPoint(0, 0), radius)


def test_specialized_intersections_return_zero_one_or_two_distinct_points() -> None:
    circle = Circle(Point(0, 0), 1)

    assert IntersectLineCircle(Line(Point(-1, 2), Point(1, 2)), circle) == []
    tangent = IntersectLineCircle(Line(Point(-1, 1), Point(1, 1)), circle)
    secant = IntersectLineCircle(Line(Point(-2, 0), Point(2, 0)), circle)

    assert len(tangent) == 1
    assert len(secant) == 2
    assert [(point.x, point.y) for point in secant] == [(-1, 0), (1, 0)]


def test_generic_intersection_rejects_missing_ambiguous_and_infinite_results() -> None:
    circle = Circle(Point(0, 0), 1)
    with pytest.raises(NoIntersectionError):
        Intersect(Line(Point(-1, 2), Point(1, 2)), circle)
    with pytest.raises(AmbiguousResultError):
        Intersect(Line(Point(-2, 0), Point(2, 0)), circle)
    with pytest.raises(InfiniteSolutionsError):
        IntersectCircles(circle, Circle(Point(0, 0), 1))


def test_near_and_far_selector_ties_are_ambiguous() -> None:
    circle = Circle(Point(0, 0), 1)
    line = Line(Point(-2, 0), Point(2, 0))
    with pytest.raises(AmbiguousResultError):
        Intersect(line, circle, near=Point(0, 0))
    with pytest.raises(AmbiguousResultError):
        Intersect(line, circle, far=Point(0, 0))


def test_tangent_branch_orientation_matches_standard_and_high_precision() -> None:
    point = Point(2, 0)
    center = Point(0, 0)
    circle = Circle(center, 1)
    assert _cross_at_contact(point, center, Tangent(point, circle, True)) > 0
    assert _cross_at_contact(point, center, Tangent(point, circle, False)) < 0

    hp = _get_high_precision_context(80)
    hp_point = hp["Point"](2, 0)
    hp_center = hp["Point"](0, 0)
    hp_circle = hp["Circle"](hp_center, 1)
    assert _cross_at_contact(hp_point, hp_center, hp["Tangent"](hp_point, hp_circle, True)) > 0
    assert _cross_at_contact(hp_point, hp_center, hp["Tangent"](hp_point, hp_circle, False)) < 0


def test_tangent_on_circle_is_unique_and_inside_has_no_solution() -> None:
    circle = Circle(Point(0, 0), 1)
    first = Tangent(Point(1, 0), circle, True)
    second = Tangent(Point(1, 0), circle, False)
    assert first == second
    with pytest.raises(NoIntersectionError):
        Tangent(Point(0, 0), circle)


def test_are_concyclic_is_a_zero_residual_not_a_boolean() -> None:
    points = (Point(1, 0), Point(0, 1), Point(-1, 0), Point(0, -1))
    assert AreConcyclic(*points) == 0
    assert AreConcyclic(*points[:3], Point(0, -2)) != 0

    hp = _get_high_precision_context(80)
    hp_points = tuple(hp["Point"](point.x, point.y) for point in points)
    result = hp["AreConcyclic"](*hp_points)
    assert isinstance(result, mp.mpf)
    assert result == 0


def test_public_float_and_hp_contexts_have_callable_parity_without_mp_leakage() -> None:
    standard = _get_geometry_context()
    high_precision = _get_high_precision_context(80)
    standard_callables = {name for name, value in standard.items() if callable(value)}

    assert standard_callables <= {name for name, value in high_precision.items() if callable(value)}
    assert not any(name.startswith("MP_") for name in high_precision)


def test_tiny_but_distinct_lines_are_not_rejected_by_an_absolute_epsilon() -> None:
    standard = Line(Point(0, 0), Point(mp.mpf("1e-100"), 0))
    assert standard is not None
    hp = _get_high_precision_context(180)
    assert hp["Line"](hp["Point"](0, 0), hp["Point"](mp.mpf("1e-100"), 0)) is not None
