"""Independent safety review: original real branches imply every reduction."""

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from geosolver.engine.standard.search.angle_equations import necessary_angle_equation
from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.errors import IRCompileError


@pytest.mark.parametrize(
    "a,b",
    [
        (0, 0),
        (0, sp.pi),
        (sp.pi, 0),
        (sp.pi, sp.pi),
        (sp.pi / 6, 2 * sp.pi / 3),
        (3 * sp.pi / 4, sp.pi / 4),
    ],
)
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("scale", [1, -7, sp.sqrt(2)])
def test_all_principal_angle_endpoints_and_coefficient_scaling_are_preserved(a, b, sign, scale):
    x, y = sp.symbols("x y", real=True)
    consequence = necessary_angle_equation(
        scale * (sp.acos(x) + sign * sp.acos(y) - (a + sign * b))
    )
    value = consequence.subs({x: sp.cos(a), y: sp.cos(b)})
    assert sp.simplify(value) == 0


@pytest.mark.parametrize(
    "source",
    [
        "Angle(Point(1,0),Point(0,0),Point(7,0))",
        "Angle(Point(1,0),Point(0,0),Point(-7,0))",
        "Angle(Line(1,0,0),Line(-13,0,8))",
        "Angle(Line(1,0,0),Line(0,-13,8))",
        "sin(Angle(Point(1,0),Point(0,0),Point(-7,0)))",
        "cos(Angle(Point(1,0),Point(0,0),Point(-7,0)))",
    ],
)
def test_angle_and_trig_boundary_parity_with_original_api(source):
    geometry = CartesianPolynomials({})
    exact = geometry.scalar(geometry.parse(source))
    with mp.workdps(110):
        original = safe_eval_expr_hp(source, _get_high_precision_context(110))
        assert abs(original - mp.mpf(str(sp.N(exact, 110)))) < mp.mpf("1e-100")


@pytest.mark.parametrize(
    "theta,expected",
    [
        ("0", [(1, 0)]),
        ("pi", [(-1, 0)]),
        ("pi/3", [(sp.Rational(1, 2), -sp.sqrt(3) / 2), (sp.Rational(1, 2), sp.sqrt(3) / 2)]),
        ("2*pi/3", [(-sp.Rational(1, 2), -sp.sqrt(3) / 2), (-sp.Rational(1, 2), sp.sqrt(3) / 2)]),
    ],
)
def test_norm_ledger_keeps_every_original_circle_branch_without_coordinate_guard(theta, expected):
    payload = {
        "variables": ["u", "v"],
        "construction": [("O", "Point(0,0)"), ("A", "Point(1,0)"), ("P", "Point(u,v)")],
        "constraints": ["u*u+v*v-1", f"Angle(A,O,P)-({theta})"],
        "targets": [0, 0],
    }
    result = discover_polynomial_branches(payload)
    assert result is not None
    points = sorted((sp.Rational(x), sp.Rational(y)) for x, y in result["points"])
    assert len(points) == len(expected)
    for actual, wanted in zip(points, sorted(expected), strict=True):
        assert all(
            abs(a - b).evalf(200) < sp.Rational(1, 10**150)
            for a, b in zip(actual, wanted, strict=True)
        )
    # At non-right angles, the opposite dot sign is proven extraneous.
    if theta in ("pi/3", "2*pi/3"):
        assert result["proved_norm_sign_exclusions"] == 2


@pytest.mark.parametrize("theta", ["-pi/3", "5*pi/3", "7*pi/3"])
def test_impossible_original_angles_remain_unresolved_instead_of_claiming_equivalence(theta):
    # Applying cosine may admit these false branches. Original verification must
    # still run; polynomial candidates alone never certify the original angle.
    payload = {
        "variables": ["u", "v"],
        "construction": [("O", "Point(0,0)"), ("A", "Point(1,0)"), ("P", "Point(u,v)")],
        "constraints": ["u*u+v*v-1", f"Angle(A,O,P)-({theta})"],
        "targets": [0, 0],
    }
    result = discover_polynomial_branches(payload)
    assert result is not None and len(result["points"]) == 2
    with mp.workdps(110):
        for u, v in result["points"]:
            source = f"Angle(Point(1,0),Point(0,0),Point({u},{v}))-({theta})"
            original = safe_eval_expr_hp(source, _get_high_precision_context(110))
            assert abs(original) > 1


def test_zero_ray_construction_is_undefined_and_cannot_become_complete_candidate_set():
    payload = {
        "variables": ["x"],
        "construction": [("O", "Point(0,0)"), ("A", "Point(1,0)"), ("P", "Point(x,0)")],
        "constraints": ["x", "Angle(A,O,P)"],
        "targets": [0],
    }
    result = discover_polynomial_branches(payload)
    # A necessary relaxation may either decline or retain the undefined proposal;
    # it may not silently erase domain uncertainty using a guessed angle sign.
    assert result is None or result["points"]
    with pytest.raises(IRCompileError, match="undefined"):
        safe_eval_expr_hp(
            "Angle(Point(1,0),Point(0,0),Point(0,0))", _get_high_precision_context(110)
        )
