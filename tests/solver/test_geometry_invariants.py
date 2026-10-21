"""Geometry invariants contracts and numerical regressions."""

import pytest
from mpmath import mp

from geosolver.errors import GeometryDomainError
from geosolver.geometry.mp.mp_bisectors import mp_angle_bisector
from geosolver.geometry.mp.mp_core_types import MPPoint
from geosolver.geometry.mp.mp_impl import mp_circumcircle, mp_incircle
from geosolver.geometry.mp.mp_triangle_centers import mp_triangle_center
from geosolver.geometry.mp.mp_triangle_checks import mp_orthic_triangle, mp_triangle_type
from geosolver.geometry.mp.mp_triangle_circles import mp_excircle, mp_nine_point_circle
from geosolver.geometry.mp.mp_triangle_metrics import mp_is_acute_triangle


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
@pytest.mark.parametrize("exponent", [-50, 0, 50])
def test_scaled_triangle_predicates_and_bisector(dps, exponent):
    with mp.workdps(dps):
        s = mp.power(10, exponent)
        a, b, c = MPPoint(0, 0), MPPoint(2 * s, 0), MPPoint(s, 2 * s)
        assert mp_is_acute_triangle(a, b, c)
        assert mp_triangle_type(a, b, c) == "acute"
        assert mp_orthic_triangle(a, b, c) is not None
        assert mp_excircle(a, b, c) is not None
        line = mp_angle_bisector(MPPoint(s, 0), a, MPPoint(0, s))
        assert abs(line.a + line.b) < 64 * mp.eps
        assert abs(line.a) > mp.mpf("0.7")


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
@pytest.mark.parametrize("n", [13, 14, 15, 16])
@pytest.mark.parametrize(
    "vertices", [((0, 0), (4, 0), (0, 3)), ((1, 2), (7, 3), (2, 6)), ((0, 0), (4, 0), (-2, 1))]
)
def test_centers_match_etc_trilinears(dps, n, vertices):
    # Independent trig reference: trilinears must first be multiplied by sides.
    with mp.workdps(dps):
        points = [MPPoint(*p) for p in vertices]
        sides, angles = [], []
        for i, a in enumerate(points):
            b, c = points[(i + 1) % 3], points[(i + 2) % 3]
            sides.append(b.distance_to(c))
            u, v = b - a, c - a
            angles.append(mp.atan2(abs(u.cross(v)), u.dot(v)))
        sign = 1 if n in (13, 15) else -1
        trig = [mp.sin(a + sign * mp.pi / 3) for a in angles]
        weights = [s / t if n in (13, 14) else s * t for s, t in zip(sides, trig, strict=True)]
        expected = [
            mp.fsum(w * getattr(p, axis) for w, p in zip(weights, points, strict=True))
            / mp.fsum(weights)
            for axis in ("x", "y")
        ]
        actual = mp_triangle_center(*points, n)
        assert all(
            abs(getattr(actual, axis) - v) < 5000 * mp.eps * max(1, abs(v))
            for axis, v in zip(("x", "y"), expected, strict=True)
        )


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
def test_fermat_stationarity_and_feuerbach_contact(dps):
    with mp.workdps(dps):
        points = (MPPoint(0, 0), MPPoint(4, 0), MPPoint(0, 3))
        f = mp_triangle_center(*points, 13)
        for axis in ("x", "y"):
            gradient = mp.fsum(
                (getattr(f, axis) - getattr(p, axis)) / f.distance_to(p) for p in points
            )
            assert abs(gradient) < 100 * mp.eps
        contact = mp_triangle_center(*points, 11)
        inc, nine = mp_incircle(*points), mp_nine_point_circle(*points)
        assert abs(contact.distance_to(inc.center) - inc.radius) < 100 * mp.eps
        assert abs(contact.distance_to(nine.center) - nine.radius) < 100 * mp.eps
        assert abs(contact.x - 1) < 100 * mp.eps and abs(contact.y - 2) < 100 * mp.eps
        circ = mp_circumcircle(*points)
        assert abs(nine.radius * 2 - circ.radius) < 100 * mp.eps


def test_symbolic_feuerbach_has_exact_coordinates():
    from geosolver.geometry.entities.base import Point
    from geosolver.geometry.operations.triangle_centers_core import TriangleCenter

    f = TriangleCenter(Point(0, 0), Point(4, 0), Point(0, 3), 11)
    assert f.x == 1 and f.y == 2


def test_singular_centers_do_not_fabricate_centroid():
    with mp.workdps(80):
        points = MPPoint(0, 0), MPPoint(2, 0), MPPoint(1, mp.sqrt(3))
        for n in (11, 14, 16):
            with pytest.raises(GeometryDomainError):
                mp_triangle_center(*points, n)


@pytest.mark.parametrize("dps", [80, 180, 500])
@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16])
def test_center_similarity_and_permutation_covariance(dps, n):
    with mp.workdps(dps):
        points = (MPPoint(0, 0), MPPoint(5, 0), MPPoint(1, 3))
        original = mp_triangle_center(*points, n)
        # Rational orthogonal rotation, scale and translation, independent of kernel formulas.
        scale = mp.mpf("1e-40")

        def transform(p):
            return MPPoint(
                scale * ((3 * p.x - 4 * p.y) / 5 + 7), scale * ((4 * p.x + 3 * p.y) / 5 - 9)
            )

        expected = transform(original)
        for ordered in (
            points,
            (points[1], points[2], points[0]),
            (points[0], points[2], points[1]),
        ):
            result = mp_triangle_center(*(transform(p) for p in ordered), n)
            assert result.distance_to(expected) <= 10000 * mp.eps * scale * max(
                1, abs(original.x), abs(original.y)
            )


@pytest.mark.parametrize("dps", [80, 180, 500])
def test_isodynamic_and_contact_concurrency_properties(dps):
    with mp.workdps(dps):
        a, b, c = MPPoint(0, 0), MPPoint(5, 0), MPPoint(1, 3)
        sides = (b.distance_to(c), c.distance_to(a), a.distance_to(b))
        for n in (15, 16):
            p = mp_triangle_center(a, b, c, n)
            products = [
                side * p.distance_to(vertex) for side, vertex in zip(sides, (a, b, c), strict=True)
            ]
            assert max(products) - min(products) <= 1000 * mp.eps * max(products)
        s = sum(sides) / 2
        for n in (7, 8):
            p = mp_triangle_center(a, b, c, n)
            for vertex, u, v in ((a, b, c), (b, c, a), (c, a, b)):
                from_u = s - (vertex.distance_to(v) if n == 7 else vertex.distance_to(u))
                t = from_u / u.distance_to(v)
                contact = MPPoint(u.x + t * (v.x - u.x), u.y + t * (v.y - u.y))
                determinant = (p.x - vertex.x) * (contact.y - vertex.y) - (p.y - vertex.y) * (
                    contact.x - vertex.x
                )
                assert abs(determinant) < 1000 * mp.eps


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
@pytest.mark.parametrize("scale_text", ["1e-50", "1", "1e50"])
def test_order_boolean_guard_handles_mp_points_and_similarity(dps, scale_text):
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.engine.standard.interpreter.guards.compile import (
        compile_guard_expr,
        guard_hard_satisfied,
    )
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )
    from geosolver.problem.ir.compiler import safe_eval_expr_hp

    with mp.workdps(dps), high_precision_mode():
        scale = mp.mpf(scale_text)
        context = _get_high_precision_context(dps)
        context.update(
            A=MPPoint(0, 0),
            P=MPPoint(scale, 0),
            B=MPPoint(2 * scale, 0),
            Q=MPPoint(3 * scale, 0),
            R=MPPoint(scale, scale),
        )
        assert safe_eval_expr_hp("Order(A,P,B)", context) is None
        for expression, expected in [
            ("Order(A,P,B)", True),
            ("Order(P1=A,P2=P,P3=B)", True),
            ("Order(A,Q,B)", False),
            ("Order(A,R,B)", False),
            ("Order(A,P,A)", False),
        ]:
            assert guard_hard_satisfied(compile_guard_expr(expression), context) is expected


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
def test_tangent_at_point_macro_preserves_incidence_and_perpendicularity(dps):
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.models import GeometryProblem

    problem = GeometryProblem(
        id="tangent-macro",
        variables=[],
        constructions=[
            {"name": "O", "expression": "Point(0,0)"},
            {"name": "P", "expression": "Point(3,4)"},
            {"name": "W", "expression": "Circle(O,5)"},
            {"name": "T", "expression": "TangentAtPoint(P,W)"},
        ],
        conditions=[],
        target="Distance(P,T)",
    )
    document = problem.engine_document()
    assert document["construction"][-1]["expr"] == "Polar(P, W)"
    ev = build_ir_evaluator(load_problem_bundle(document))
    assert ev.evaluate_float_residual([]).is_finite
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    with mp.workdps(dps), high_precision_mode():
        answer = ev.evaluate_answer_hp([], precision=dps)
        assert answer.answer_hp == 0
        from geosolver.engine.standard.interpreter.context.high_precision import (
            _get_high_precision_context,
        )

        context = _get_high_precision_context(dps)
        circle = context["Circle"](MPPoint(0, 0), mp.mpf(5))
        tangent = context["Polar"](MPPoint(3, 4), circle)
        assert abs(3 * tangent.b - 4 * tangent.a) < 32 * mp.eps


_GUARD_CASES = {
    "AcuteTriangle": (
        "AcuteTriangle(Point(0,0),Point(2,0),Point(1,2))",
        "AcuteTriangle(Point(0,0),Point(1,0),Point(0,1))",
    ),
    "RightTriangle": (
        "RightTriangle(Point(0,0),Point(1,0),Point(0,1))",
        "RightTriangle(Point(0,0),Point(2,0),Point(1,2))",
    ),
    "ObtuseTriangle": (
        "ObtuseTriangle(Point(0,0),Point(1,0),Point(2,1))",
        "ObtuseTriangle(Point(0,0),Point(2,0),Point(1,2))",
    ),
    "Order": (
        "Order(Point(0,0),Point(1,0),Point(2,0))",
        "Order(Point(0,0),Point(3,0),Point(2,0))",
    ),
    "Bound": ("Bound(1,(0,2))", "Bound(3,(0,2))"),
    "And": ("And(1>0,2>1)", "And(1>0,2<1)"),
    "Or": ("Or(1>0,2<1)", "Or(1<0,2<1)"),
    "Not": ("Not(1<0)", "Not(1>0)"),
    "ConvexPolygon": (
        "ConvexPolygon([Point(0,0),Point(2,0),Point(2,2),Point(0,2)])",
        "ConvexPolygon([Point(0,0),Point(2,0),Point(1,1),Point(2,2),Point(0,2)])",
    ),
    "SimplePolygon": (
        "SimplePolygon([Point(0,0),Point(2,0),Point(2,2),Point(0,2)])",
        "SimplePolygon([Point(0,0),Point(2,2),Point(2,0),Point(0,2)])",
    ),
}


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
@pytest.mark.parametrize("name", sorted(_GUARD_CASES))
def test_public_boolean_guards_and_aliases_have_true_and_false_cases(name, dps):
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.engine.standard.interpreter.guards.compile import (
        compile_guard_expr,
        guard_hard_satisfied,
    )
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )
    from geosolver.problem.dsl_spec import symbols_by_name
    from geosolver.problem.ir.compiler import IRCompileError

    with mp.workdps(dps), high_precision_mode():
        context = _get_high_precision_context(dps)
        for expression, expected in zip(_GUARD_CASES[name], (True, False), strict=True):
            for spelling in (name, *symbols_by_name()[name].aliases):
                text = expression.replace(name + "(", spelling + "(", 1)
                if not expected and name in {"ConvexPolygon", "SimplePolygon"}:
                    # These public Assume wrappers reject through an exception;
                    # the evaluator turns it into failed guard evidence.
                    with pytest.raises(
                        IRCompileError, match="Polygon (is not convex|has self-intersection)"
                    ):
                        guard_hard_satisfied(compile_guard_expr(text), context)
                else:
                    assert guard_hard_satisfied(compile_guard_expr(text), context) is expected


def test_boolean_fixture_inventory_matches_public_contract():
    from geosolver.problem.dsl_spec import dsl_spec

    assert set(_GUARD_CASES) == {s.name for s in dsl_spec().symbols if s.output_type == "boolean"}


@pytest.mark.parametrize("dps", [15, 80, 180, 500])
def test_ratio_macro_evaluates_length_ratio_at_each_precision(dps):
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.models import GeometryProblem

    problem = GeometryProblem(
        id="ratio-macro",
        variables=[],
        constructions=[],
        conditions=[],
        target="Ratio(Point(0,0),Point(3,4),Point(0,0),Point(2,0))",
    )
    evaluator = build_ir_evaluator(load_problem_bundle(problem.engine_document()))
    with mp.workdps(dps), high_precision_mode():
        assert evaluator.evaluate_answer_hp([], precision=dps).answer_hp == mp.mpf(5) / 2


def test_public_solver_does_not_verify_the_old_incorrect_x13_answer():
    from geosolver import GeometryProblem, solve

    problem = GeometryProblem(
        id="x13-public-regression",
        variables=[],
        constructions=[
            {"name": "A", "expression": "Point(0,0)"},
            {"name": "B", "expression": "Point(4,0)"},
            {"name": "C", "expression": "Point(0,3)"},
            {"name": "F", "expression": "TriangleCenter(A,B,C,13)"},
        ],
        conditions=[],
        target="Distance(A,FootOfPerpendicular(F,Line(A,B)))",
    )
    result = solve(problem)
    assert result.status == "solved", result
    # This point also satisfies the independent Fermat stationarity test above.
    assert float(result.answers[0].decimal) == pytest.approx(0.6957885340875542, abs=1e-14)
    diagnostics = result.diagnostics
    exact = diagnostics["pipeline_summary"]["exact_candidate_records"][0]["candidate"]
    candidate = diagnostics["candidate_records"][0]
    assert exact["candidate_key"] == candidate["candidate_key"]
    assert exact["candidate_uid"] == candidate["candidate_uid"]
    assert exact["revision"] == candidate["revision"]


@pytest.mark.parametrize("n", [11, 13, 14, 15, 16])
@pytest.mark.parametrize(
    "vertices", [((0, 0), (4, 0), (0, 3)), ((1, 2), (7, 3), (2, 6)), ((0, 0), (4, 0), (-2, 1))]
)
def test_fixed_centers_agree_with_symbolic_and_numpy_backends(n, vertices):
    import numpy as np
    from sympy import N

    from geosolver.geometry.entities.base import Point
    from geosolver.geometry.operations.triangle_centers_core import TriangleCenter

    exact = TriangleCenter(*(Point(*p) for p in vertices), n)
    numerical = TriangleCenter.fast(*(np.asarray(p, dtype=float) for p in vertices), n)
    with mp.workdps(180):
        high = mp_triangle_center(*(MPPoint(*p) for p in vertices), n)
        for i, axis in enumerate(("x", "y")):
            reference = mp.mpf(str(N(getattr(exact, axis), 170)))
            assert abs(getattr(high, axis) - reference) < mp.mpf("1e-160")
            assert float(numerical[i]) == pytest.approx(float(reference), rel=1e-11, abs=1e-12)
