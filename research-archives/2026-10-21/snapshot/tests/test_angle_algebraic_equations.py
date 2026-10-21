import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from geosolver.engine.standard.search.angle_equations import necessary_angle_equation
from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials
from geosolver.problem.ir.compiler import safe_eval_expr_hp


@pytest.mark.parametrize(
    "source",
    [
        "Angle(Point(1,2),Point(-3,4),Point(7,-5))",
        "Angle(Point(-1,2),Point(3,-4),Point(-7,5))",
        "Angle(Point(1,0),Point(0,0),Point(-2,-3))",
        "Angle(Line(2,-3,4),Line(-5,7,-8))",
        "Angle(Line(-2,3,-4),Line(-5,7,-8))",
        "sin(Angle(Point(1,0),Point(0,0),Point(2,3)))",
        "cos(Angle(Point(1,0),Point(0,0),Point(2,3)))",
    ],
)
def test_exact_unsigned_angle_measurement_matches_original_high_precision(source):
    geometry = CartesianPolynomials({})
    exact = geometry.scalar(geometry.parse(source))
    with mp.workdps(110):
        original = safe_eval_expr_hp(source, _get_high_precision_context(110))
        assert abs(original - mp.mpf(str(sp.N(exact, 110)))) < mp.mpf("1e-100")


@pytest.mark.parametrize("theta", [sp.pi / 6, sp.pi / 3, 2 * sp.pi / 3])
@pytest.mark.parametrize("sign", [-1, 1])
def test_signed_two_angle_relation_preserves_an_original_exact_solution(theta, sign):
    x, y = sp.symbols("x y", real=True)
    # Pick B=pi/12 and A=theta-sign*B, strictly inside the principal domain.
    a, b = theta - sign * sp.pi / 12, sp.pi / 12
    equation = sp.acos(x) + sign * sp.acos(y) - theta
    consequence = necessary_angle_equation(equation)
    assert sp.to_number_field(consequence.subs({x: sp.cos(a), y: sp.cos(b)})).as_expr() == 0


@pytest.mark.parametrize(
    "equation",
    [
        lambda x, y: sp.acos(x) * sp.acos(y) - 1,
        lambda x, y: x * sp.acos(y) - 1,
        lambda x, y: sp.acos(x) - 1,
        lambda x, y: sp.acos(x) + 2 * sp.acos(y) - sp.pi,
    ],
)
def test_unsupported_angle_relations_decline_instead_of_guessing(equation):
    x, y = sp.symbols("x y", real=True)
    with pytest.raises(ValueError):
        necessary_angle_equation(equation(x, y))


@pytest.mark.parametrize("scale,translate", [(1, 0), (7, 13), (sp.Rational(1, 100), -4)])
def test_circle_fixed_angle_retains_both_signed_height_branches(scale, translate):
    p = {
        "variables": ["u", "v"],
        "construction": [
            ("O", f"Point({translate},0)"),
            ("A", f"Point({translate}+{scale},0)"),
            ("P", f"Point({translate}+({scale})*u,({scale})*v)"),
        ],
        "constraints": ["u*u+v*v-25", "-7*(Angle(A,O,P)-pi/3)"],
        "targets": [0, 0],
        "guards": ["AssumeGt(u,0)"],
    }
    result = discover_polynomial_branches(p)
    assert result is not None
    points = sorted((sp.Rational(x), sp.Rational(y)) for x, y in result["points"])
    assert len(points) == 2
    assert all(abs(x - sp.Rational(5, 2)) < sp.Rational(1, 10**150) for x, y in points)
    assert abs(points[0][1] + 5 * sp.sqrt(3) / 2).evalf(200) < sp.Rational(1, 10**150)
    assert abs(points[1][1] - 5 * sp.sqrt(3) / 2).evalf(200) < sp.Rational(1, 10**150)
