from __future__ import annotations

import pytest
from mpmath import mp
from sympy import pi

from geosolver import GeometryProblem, SolveOptions, solve
from geosolver.engine.standard.refinement.finite_difference_jacobian import (
    compute_finite_difference_jacobian,
)
from geosolver.geometry import Angle, Degrees, Point
from geosolver.geometry.mp.mp_core_types import MPPoint
from geosolver.geometry.mp.mp_triangle_metrics import mp_angle


def _fixed_angle_problem(
    *,
    point_b: tuple[int, int],
    target: str,
    condition: tuple[str, str, int] | None = None,
) -> GeometryProblem:
    conditions = []
    if condition is not None:
        left, operator, right = condition
        conditions.append({"left": left, "operator": operator, "right": right})
    return GeometryProblem(
        id="angle-regression",
        variables=[],
        constructions=[
            {"name": "A", "expression": "Point(1, 0)"},
            {"name": "B", "expression": f"Point({point_b[0]}, {point_b[1]})"},
            {"name": "C", "expression": "Point(0, 1)"},
        ],
        conditions=conditions,
        target=target,
    )


def test_degrees_is_a_public_scalar_function() -> None:
    assert Degrees(pi / 2).simplify() == 90


def test_degrees_can_be_used_inside_a_constraint() -> None:
    problem = _fixed_angle_problem(
        point_b=(0, 0),
        target="Degrees(Angle(A, B, C))",
        condition=("Degrees(Angle(A, B, C))", "=", 90),
    )

    result = solve(problem, SolveOptions(cores=1))

    assert result.status == "solved"
    assert result.answers[0].minimal_polynomial == ["1", "-90"]


def test_symbolic_angle_rejects_a_zero_length_ray() -> None:
    with pytest.raises(ValueError, match="undefined"):
        Angle(Point(0, 0), Point(0, 0), Point(1, 0))


def test_high_precision_angle_rejects_a_zero_length_ray() -> None:
    with pytest.raises(ValueError, match="undefined"):
        mp_angle(MPPoint(0, 0), MPPoint(0, 0), MPPoint(1, 0))


def test_high_precision_angle_keeps_scale_invariance_for_small_nonzero_rays() -> None:
    tiny = mp.mpf("1e-20")
    value = mp_angle(MPPoint(tiny, 0), MPPoint(0, 0), MPPoint(0, tiny))

    assert abs(value - mp.pi / 2) < mp.mpf("1e-40")


def test_degenerate_angle_is_not_certified_by_the_solver() -> None:
    problem = _fixed_angle_problem(
        point_b=(1, 0),
        target="Angle(A, B, C)",
        condition=("Angle(A, B, C)", "=", 0),
    )
    # A=(1,0), B=(1,0): the first ray is undefined.

    result = solve(problem, SolveOptions(cores=1))

    assert result.status == "no_answer_found"


def test_angle_cusp_can_use_a_directional_finite_difference() -> None:
    residual = lambda point, _dps: [abs(point[0])]

    centered = compute_finite_difference_jacobian(
        point=[mp.mpf("0")], dps=30, residual_fn=residual
    )
    cusp_aware = compute_finite_difference_jacobian(
        point=[mp.mpf("0")],
        dps=30,
        residual_fn=residual,
        one_sided_at_cusp=True,
    )

    assert centered is not None and centered[0][0] == 0
    assert cusp_aware is not None and abs(cusp_aware[0][0]) > mp.mpf("0.5")
