"""Source-backed parity checks for oriented nonzero Cartesian measurements."""

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.search.cartesian_polynomials import (
    CartesianPolynomials,
    exact_guard_value,
)
from geosolver.problem.ir.compiler import safe_eval_expr_hp


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize(
    "template",
    [
        "Line({s}*2,{s}*-3,5).a",
        "Line({s}*2,{s}*-3,5).b",
        "Line({s}*2,{s}*-3,5).c",
        "Line(Point(2,3),Point({s}*4,-5)).a",
        "Line(Point(2,3),Point({s}*4,-5)).b",
        "Line(Point(2,3),Point({s}*4,-5)).c",
        "Dot(Line({s}*2,-3,5),Line(-4,7,3))",
        "Parallel(Line({s}*2,-3,5),Line(-4,7,3))",
        "Perpendicular(Line({s}*2,-3,5),Line(-4,7,3))",
        "Dot(Vector(Point(2,3),Point({s}*4,-5)),Point(-4,7))",
        "Collinear(Point({s}*1,2),Point(4,8),Point(-3,5))",
        "OnLine(Point({s}*1,2),Point(4,8),Point(-3,5))",
        "OnLine(Point({s}*1,2),Line(2,-3,5))",
        "Distance(Point({s}*1,2),Line(2,-3,5))",
        "Area(Point({s}*1,2),Point(4,8),Point(-3,5))",
        "Area(Point({s}*1,2),Point(4,8),Point(-3,5),Point(-7,2))",
        "PerpendicularLine(Line({s}*2,-3,5),Point(-4,7)).c",
        "ParallelLine(Point(-4,7),Line({s}*2,-3,5)).c",
        "PerpendicularBisector(Point({s}*1,2),Point(4,8)).c",
        "FootOfPerpendicular(Point({s}*1,2),Line(2,-3,5)).x",
        "Reflect(Point({s}*1,2),Line(2,-3,5)).y",
        "Reflect(Point({s}*1,2),Point(4,8)).x",
        "Intersect(Line({s}*2,-3,5),Line(-4,7,3)).x",
        "Circumcenter(Point({s}*1,2),Point(4,8),Point(-3,5)).y",
        "Radius(Circumcircle(Point({s}*1,2),Point(4,8),Point(-3,5)))",
        "Orthocenter(Point({s}*1,2),Point(4,8),Point(-3,5)).x",
        "Centroid(Point({s}*1,2),Point(4,8),Point(-3,5)).y",
    ],
)
def test_nonzero_measurements_match_original_high_precision_semantics(template, sign):
    source = template.format(s=sign)
    geometry = CartesianPolynomials({})
    exact = geometry.scalar(geometry.parse(source))
    with mp.workdps(100):
        original = safe_eval_expr_hp(source, _get_high_precision_context(100))
        proposal = mp.mpf(str(sp.N(exact, 100)))
        assert abs(original - proposal) < mp.mpf("1e-90")


@pytest.mark.parametrize(
    "source",
    [
        "AssumeEq(Dot(Line(1,0,0),Line(-1,0,0)),1)",
        "AssumeLt(Collinear(Point(1,2),Point(4,8),Point(-3,5)),0)",
        "AssumeEq(Area(Point(0,0),Point(2,0),Point(0,2)),3)",
        "AssumeEq(Distance(Point(0,0),Line(0,0,0)),0)",
        "AssumeEq((1/(x-x))*0,1)",
        "AssumeEq(sqrt(x-2)**2,0)",
        "AssumeEq((x-1)/(x-1),0)",
    ],
)
def test_geometry_and_undefined_arithmetic_guards_remain_unresolved(source):
    geometry = CartesianPolynomials({})
    assert exact_guard_value(source, geometry, {sp.Symbol("x", real=True): sp.Integer(1)}) is None


def test_scalar_alias_to_geometry_is_not_used_for_exclusion():
    geometry = CartesianPolynomials({"d": "Distance(Point(0,0),Point(1,0))"})
    assert exact_guard_value("AssumeEq(d,0)", geometry, {}) is None


def test_scalar_aliases_and_exact_arithmetic_can_prove_false_guard():
    geometry = CartesianPolynomials({"a": "x+1", "b": "sqrt(a)*2"})
    values = {sp.Symbol("x", real=True): sp.Integer(3)}
    assert exact_guard_value("AssumeLt(b,abs(-3))", geometry, values) is False
