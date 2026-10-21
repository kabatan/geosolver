"""Numeric geometry contracts and numerical regressions."""

import math

import pytest
from mpmath import mp
from sympy import Basic

from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.geometry.mp.mp_core_types import MPLine, MPPoint
from geosolver.geometry.mp.mp_line_relations import mp_angle_between_lines, mp_angle_between_vectors
from geosolver.geometry.mp.signed_tangency import signed_tangency
from geosolver.problem.dsl_spec import dsl_spec
from geosolver.problem.ir.compiler import safe_eval_expr_hp

_TRIANGLE_CENTERS = [
    "Centroid",
    "Circumcenter",
    "Circumcircle",
    "Excenter",
    "Excircle",
    "FermatPoint",
    "FeuerbachPoint",
    "GergonnePoint",
    "Incenter",
    "Incircle",
    "IsodynamicPoint",
    "Mittenpunkt",
    "NagelPoint",
    "NinePointCenter",
    "NinePointCircle",
    "Orthocenter",
    "SpiekerCenter",
    "SymmedianPoint",
]


_CALLS = {
    **{name: f"{name}(A,B,C)" for name in _TRIANGLE_CENTERS},
    "Angle": "Angle(A,B,C)",
    "AngleBisector": "AngleBisector(A,B,C)",
    "Arc": "Arc(omega,U,V)",
    "AreConcyclic": "AreConcyclic(A,B,C,D)",
    "Area": "Area(A,B,C)",
    "Center": "Center(omega)",
    "Circle": "Circle(O,2)",
    "CircleThroughPoint": "CircleThroughPoint(O,P)",
    "CircleThroughThreePoints": "CircleThroughThreePoints(A,B,C)",
    "Circumference": "Circumference(omega)",
    "ClosestPoint": "ClosestPoint(P,line)",
    "Collinear": "Collinear(A,B,C)",
    "ContactPoint": "ContactPoint(omega,line)",
    "Degrees": "Degrees(pi/3)",
    "Distance": "Distance(A,B)",
    "Dot": "Dot(Vector(A,B),Vector(A,C))",
    "FootOfPerpendicular": "FootOfPerpendicular(P,line)",
    "IncircleContactPoint": "IncircleContactPoint(A,B,C)",
    "InscribedPolygon": "InscribedPolygon(omega,0.17,0.28)",
    "InscribedPolygonVertices": "InscribedPolygonVertices(omega,0.17,0.28)",
    "Intersect": "Intersect(line,omega,n=1)",
    "IntersectCircles": "IntersectCircles(omega,other)",
    "IntersectLineCircle": "IntersectLineCircle(line,omega)",
    "IntersectLines": "IntersectLines(line,Line(A,C))",
    "IsInteger": "IsInteger(2.3)",
    "IsPrime": "IsPrime(11)",
    "IsTangent": "IsTangent(line,omega)",
    "Length": "Length(Segment(A,B))",
    "Line": "Line(A,B)",
    "Midpoint": "Midpoint(A,B)",
    "OnCircle": "OnCircle(P,omega)",
    "OnLine": "OnLine(P,line)",
    "OnSegment": "OnSegment(P,A,B)",
    "Parallel": "Parallel(line,Line(A,C))",
    "ParallelLine": "ParallelLine(line,P)",
    "ParallelismMeasure": "ParallelismMeasure(line,Line(A,C))",
    "Perimeter": "Perimeter(A,B,C)",
    "Perpendicular": "Perpendicular(line,Line(A,C))",
    "PerpendicularBisector": "PerpendicularBisector(A,B)",
    "PerpendicularLine": "PerpendicularLine(line,P)",
    "Point": "Point(1.2,3.4)",
    "PointOnArc": "PointOnArc(Arc(omega,U,V),0.31)",
    "PointOnCircle": "PointOnCircle(omega,0.31)",
    "PointOnLine": "PointOnLine(line,0.31)",
    "PointOnSegment": "PointOnSegment(A,B,0.31)",
    "Polar": "Polar(P,omega)",
    "Pole": "Pole(Line(Point(0,1),Point(1,1)),omega)",
    "Polygon": "Polygon([A,B,C])",
    "PowerOfPoint": "PowerOfPoint(P,omega)",
    "RadicalAxis": "RadicalAxis(omega,other)",
    "Radius": "Radius(omega)",
    "Ray": "Ray(A,B)",
    "Reflect": "Reflect(P,line)",
    "RegularPolygon": "RegularPolygon(A,B,7)",
    "Rotate": "Rotate(P,pi/7,center=O)",
    "Segment": "Segment(A,B)",
    "Slope": "Slope(A,C)",
    "Tangent": "Tangent(P,omega)",
    "TangentLine": "TangentLine(P,omega)",
    "Triangle": "Triangle(A,B,C)",
    "TriangleCenter": "TriangleCenter(A,B,C,6)",
    "Vector": "Vector(A,B)",
    **{
        name: f"{name}(0.3)"
        for name in ("abs", "acos", "asin", "atan", "cos", "sin", "sqrt", "tan")
    },
    "atan2": "atan2(1,2)",
    "max": "max(1,2)",
    "min": "min(1,2)",
}


def _context():
    ctx = _get_high_precision_context(mp.dps)
    for name, expression in (
        ("A", "Point(0,0)"),
        ("B", "Point(5,0)"),
        ("C", "Point(1,3)"),
        ("D", "Point(-1,2)"),
        ("O", "Point(0,0)"),
        ("P", "Point(3,1)"),
        ("U", "Point(2,0)"),
        ("V", "Point(0,2)"),
        ("line", "Line(A,B)"),
        ("omega", "Circle(O,2)"),
        ("other", "Circle(Point(3,0),2)"),
    ):
        ctx[name] = safe_eval_expr_hp(expression, ctx)
    return ctx


def _numeric_leaves(value):
    assert not isinstance(value, float | Basic), repr(value)
    if isinstance(value, mp.mpf):
        assert mp.isfinite(value)
        return [value]
    if isinstance(value, list | tuple):
        return [x for item in value for x in _numeric_leaves(item)]
    if isinstance(value, int | bool):
        return [value]
    result = []
    for attr in (
        "x",
        "y",
        "a",
        "b",
        "c",
        "p1",
        "p2",
        "start",
        "through",
        "end",
        "center",
        "radius",
        "vertices",
        "circle",
    ):
        if hasattr(value, attr):
            result.extend(_numeric_leaves(getattr(value, attr)))
    assert result, type(value)
    return result


def test_numeric_fixtures_cover_all_public_non_boolean_functions_and_aliases():
    expected = {
        s.name
        for s in dsl_spec().symbols
        if s.symbol_kind == "function" and s.output_type != "boolean"
    }
    assert set(_CALLS) == expected


@pytest.mark.parametrize("name,expression", sorted(_CALLS.items()))
def test_all_numerical_kernels_are_numeric_at_float_and_hp_precision(name, expression):
    from geosolver.problem.dsl_spec import symbols_by_name

    results = []
    for bits in (53, 269, 601, 1664):
        with mp.workprec(bits), high_precision_mode():
            ctx = _context()
            original = _numeric_leaves(safe_eval_expr_hp(expression, ctx))
            results.append(original)
            for alias in symbols_by_name()[name].aliases:
                aliased = expression.replace(name + "(", alias + "(", 1)
                assert _numeric_leaves(safe_eval_expr_hp(aliased, ctx)) == original
    with mp.workdps(120):
        scale = max(abs(v) for v in results[-1])
        for low, high in zip(results[0], results[-1], strict=True):
            assert abs(low - high) <= scale * mp.mpf("1e-13")


@pytest.mark.parametrize("precision", [80, 180, 500])
def test_angles_preserve_nearly_parallel_and_perpendicular_directions(precision):
    with mp.workdps(precision + 400):
        delta = mp.mpf("1e-300")
        a, b = MPPoint(1, 1), MPPoint(1, 1 + delta)
        expected = mp.atan(delta / (2 + delta))
        la, lb = MPLine(1, 1, 0), MPLine(1, 1 + delta, 0)
        line_expected = mp.atan2(abs(la.a * lb.b - la.b * lb.a), abs(la.a * lb.a + la.b * lb.b))
    with mp.workdps(precision):
        before = mp.prec
        assert mp.almosteq(mp_angle_between_vectors(a, b), expected)
        assert mp.almosteq(mp_angle_between_lines(la, lb), line_expected)
        assert mp_angle_between_vectors(MPPoint(1, 0), MPPoint(-1, 0)) == mp.pi
        assert mp_angle_between_lines(MPLine(1, 0, 0), MPLine(0, 1, 0)) == mp.pi / 2
        assert mp.prec == before
        assert mp_angle_between_vectors(a, b) > 0


def test_line_angle_does_not_raise_working_precision(monkeypatch):
    with mp.workdps(180):
        a, b = MPLine(1, 2, 0), MPLine(3, 4, 0)
        original = mp.atan2
        seen = []

        def recorded(y, x):
            seen.append(mp.dps)
            return original(y, x)

        monkeypatch.setattr(mp, "atan2", recorded)
        assert math.isfinite(float(mp_angle_between_lines(a, b)))
        assert seen == [180]


@pytest.mark.parametrize("line_height", ["2", "-2", "0", "1", "3"])
def test_signed_line_tangency_preserves_absolute_public_residual(line_height):
    with mp.workdps(180):
        ctx = _context()
        line = MPLine(0, 1, -mp.mpf(line_height))
        assert abs(signed_tangency(line, ctx["omega"])) == ctx["IsTangent"](line, ctx["omega"])


@pytest.mark.parametrize("scale", ["1e-100", "1e-3", "1e100"])
@pytest.mark.parametrize(
    "name", ["Circumcircle", "CircleThroughThreePoints", "Incenter", "Mittenpunkt"]
)
def test_numeric_triangle_constructors_do_not_use_an_absolute_size_floor(name, scale):
    with mp.workprec(53):
        ctx = _context()
        s = mp.mpf(scale)
        points = [MPPoint(ctx[n].x * s, ctx[n].y * s) for n in ("A", "B", "C")]
        result = ctx[name](*points)
        assert _numeric_leaves(result)


def test_regular_polygon_accepts_distinct_microscopic_vertices():
    with mp.workprec(53):
        ctx = _get_high_precision_context(15)
        polygon = ctx["RegularPolygon"](MPPoint(0, 0), MPPoint(mp.mpf("1e-100"), 0), 4)
        assert len(polygon) == 4 and polygon.perimeter > 0
