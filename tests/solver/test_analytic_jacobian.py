"""Analytic jacobian contracts and numerical regressions."""

import json

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import analytic_jacobian as analytic
from geosolver.engine.standard.refinement import mpmath_refiner as refiner
from geosolver.runtime import symbolic


@pytest.fixture(autouse=True)
def hp_mode():
    with high_precision_mode():
        yield


@pytest.mark.parametrize("names,scale,reverse", [(("x", "y"), 1, False), (("rho", "tau"), 7, True)])
@pytest.mark.parametrize("dps", [80, 120, 500])
def test_generated_cartesian_derivatives_preserve_precision(names, scale, reverse, dps):
    x, y = names
    rows = [f"{scale}*Distance(P, Q)", f"{x}+2*{y}"]
    targets = ["5", "0"]
    if reverse:
        rows.reverse()
        targets.reverse()
    plan = analytic.compile_jacobian(
        (names, (("P", f"Point({x}, {y})"), ("Q", "Point(0, 0)")), rows, targets)
    )
    assert plan is not None
    with mp.workdps(dps):
        xval, yval = mp.mpf(3), mp.mpf(4)
        matrix = analytic.evaluate_jacobian(plan, [xval, yval], dps)
        expected = [[scale * xval / 5, scale * yval / 5], [mp.mpf(1), mp.mpf(2)]]
        if reverse:
            expected.reverse()
        assert all(hasattr(value, "_mpf_") for row in matrix for value in row)
        assert max(
            abs(value - want)
            for row, target in zip(matrix, expected, strict=False)
            for value, want in zip(row, target, strict=False)
        ) < mp.power(10, -dps + 4)
        # This derivative changes below binary64 precision and must retain it.
        delta = mp.power(10, -dps // 2)
        shifted = analytic.evaluate_jacobian(plan, [xval + delta, yval], dps)
        index = 1 if reverse else 0
        assert shifted[index][0] != matrix[index][0]


def test_segment_zero_row_only_on_open_valid_segment():
    plan = analytic.compile_jacobian(
        (
            ("s", "z"),
            (("A", "Point(0, 0)"), ("B", "Point(10, 0)"), ("P", "Point(s, 0)")),
            ("3*OnSegment(P,A,B)", "s+z"),
            ("0", "2"),
        )
    )
    assert plan is not None
    with mp.workdps(120):
        assert analytic.evaluate_jacobian(plan, [mp.mpf(3), mp.mpf(2)], 120)[0] == [0, 0]
        for endpoint in (-1, 0, 10, 11):
            assert analytic.evaluate_jacobian(plan, [mp.mpf(endpoint), mp.mpf(2)], 120) is None
    noncollinear = analytic.compile_jacobian(
        (("s", "z"), (), ("OnSegment(Point(s,z),Point(0,0),Point(10,0))",), ("0",))
    )
    assert noncollinear is None


@pytest.mark.parametrize(
    "source,target",
    [
        ("Integer(x)", "0"),
        ("Distance(Point(x,y),Point(0,0))", "0"),
        ("sin(x)+y", "1"),
    ],
)
def test_unsupported_or_transformed_residual_keeps_finite_differences(source, target):
    assert analytic.compile_jacobian((("x", "y"), (), (source,), (target,))) is None


def test_distance_cusp_falls_back():
    plan = analytic.compile_jacobian((("x", "y"), (), ("Distance(Point(x,y),Point(0,0))",), ("1",)))
    assert analytic.evaluate_jacobian(plan, [mp.mpf(0), mp.mpf(0)], 120) is None


def test_only_optional_symbolic_timeout_is_swallowed(monkeypatch):
    analytic._plan.cache_clear()

    def optional(*args, **kwargs):
        assert kwargs == {"timeout_seconds": 1.5}
        raise symbolic.OptionalSymbolicTimeout

    monkeypatch.setattr(symbolic, "request", optional)
    assert analytic._plan((("x", "y"), (), ("x+y",), ("0",))) is None

    def deadline(*args, **kwargs):
        raise TimeoutError("global deadline")

    monkeypatch.setattr(symbolic, "request", deadline)
    with pytest.raises(TimeoutError, match="global deadline"):
        analytic._plan((("x", "y"), (), ("x-y",), ("0",)))
    analytic._plan.cache_clear()


def test_closure_uses_analytic_and_checks_original_system(monkeypatch):
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "constraints": ["x*x+y*y-25", "x+y-7"],
                "answer": "x-y",
            }
        )
    )
    calls = []
    original = refiner.evaluate_jacobian

    def counted(*args):
        calls.append(args[2])
        return original(*args)

    monkeypatch.setattr(refiner, "evaluate_jacobian", counted)
    with mp.workdps(180):
        result = refiner._run_findroot_closure(
            evaluator=ev,
            start_point=[mp.mpf("3.99"), mp.mpf("3.01")],
            bounds=((None, None), (None, None)),
            dps=120,
            target_residual=mp.mpf("1e-90"),
            solver_tolerance=mp.mpf("1e-180"),
            max_steps=20,
        )
        assert result is not None
        assert calls and set(calls) == {120}
        assert result[1] < mp.mpf("1e-90")
        assert abs(result[0][0] - 4) < mp.mpf("1e-90")


def test_absolute_derivative_uses_current_branch_and_rejects_cusp():
    plan = analytic.compile_jacobian(
        (("x", "y"), (("unused", "Circle(Point(0,0), 1)"),), ("abs(x)+y",), ("2",))
    )
    assert plan is not None
    for x, expected in ((-3, -1), (3, 1)):
        assert analytic.evaluate_jacobian(plan, [mp.mpf(x), mp.mpf(1)], 120) == [[expected, 1]]
    assert analytic.evaluate_jacobian(plan, [mp.mpf(0), mp.mpf(1)], 120) is None


def test_rank_chart_uses_exact_derivative_and_certifies_every_original_row(monkeypatch):
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y", "z"]},
                "constraints": ["x*x+y*y-25", "x+y-z", "2*(x+y-z)"],
                "answer": "x-y",
            }
        )
    )
    calls = []
    original = refiner.evaluate_jacobian

    def counted(*args):
        calls.append(args[2])
        return original(*args)

    monkeypatch.setattr(refiner, "evaluate_jacobian", counted)
    with mp.workdps(180):
        result = refiner._run_findroot_closure(
            evaluator=ev,
            start_point=[mp.mpf("3.99"), mp.mpf("3.01"), mp.mpf(7)],
            bounds=((None, None),) * 3,
            dps=120,
            target_residual=mp.mpf("1e-80"),
            max_steps=20,
        )
        assert result is not None
        assert calls
        checked = ev.evaluate_hp_residual(result[0], precision=120)
        assert len(checked.residual_vector) == 3
        assert max(abs(value) for value in checked.residual_vector) < mp.mpf("1e-80")


def test_derivative_evaluation_propagates_global_deadline(monkeypatch):
    plan = analytic.compile_jacobian((("x", "y"), (), ("x+y",), ("0",)))

    def expired():
        raise TimeoutError("expired derivative")

    monkeypatch.setattr(analytic, "check_deadline", expired)
    with pytest.raises(TimeoutError, match="expired derivative"):
        analytic.evaluate_jacobian(plan, [mp.mpf(1), mp.mpf(2)], 120)


@pytest.mark.parametrize(
    "names,wrapper", [(("x", "y"), "IsTangent(l,c)"), (("alpha", "beta"), "7*IsTangent(l,c)/3")]
)
def test_line_circle_tangency_derivative_matches_actual_smoothed_residual(names, wrapper):
    x, y = names
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": list(names)},
                "construction": [
                    {"name": "P", "expr": f"Point({x}, 0)"},
                    {"name": "Q", "expr": f"Point(0, {y})"},
                    {"name": "l", "expr": "Line(P,Q)"},
                    {"name": "c", "expr": "Circle(Point(0,0),2)"},
                ],
                "constraints": [wrapper, "Distance(P,Q)"],
                "v": [0, 7],
                "answer": x,
            }
        )
    )
    payload = (
        ev.bundle.var_names,
        tuple((item.name, item.expr) for item in ev.bundle.spec.construction),
        tuple(ev.bundle.spec.constraints),
        tuple(str(target) for target in ev.bundle.targets),
    )
    plan = analytic.compile_jacobian(json.loads(json.dumps(payload)))
    assert plan is not None and plan["requires_smoothing"]
    with mp.workdps(120):
        point = [mp.mpf(3), mp.mpf(4)]
        computed = analytic.evaluate_jacobian(plan, point, 120)
        step = mp.mpf("1e-40")
        for column in range(2):
            a, b = point.copy(), point.copy()
            a[column] += step
            b[column] -= step
            plus = refiner.MpmathRefiner()._residual_vector_for_stage(
                ev.bundle, ev, a, 120, smooth_zero_constraints=True
            )
            minus = refiner.MpmathRefiner()._residual_vector_for_stage(
                ev.bundle, ev, b, 120, smooth_zero_constraints=True
            )
            assert all(
                abs(computed[row][column] - (plus[row] - minus[row]) / (2 * step)) < mp.mpf("1e-70")
                for row in range(2)
            )
        assert analytic.evaluate_jacobian(plan, [mp.mpf(0), mp.mpf(0)], 120) is None


def test_segment_uses_original_long_decimal_endpoint():
    endpoint = "1." + "0" * 99 + "1"
    source = f"OnSegment(Point(x,0),Point(0,0),Point({endpoint},0))"
    plan = analytic.compile_jacobian((("x", "y"), (), (source, "x+y"), ("0", "2")))
    with mp.workdps(180):
        assert analytic.evaluate_jacobian(plan, [mp.mpf(1), mp.mpf(1)], 180)[0] == [0, 0]


@pytest.mark.parametrize("scale", ["1e-300", "1", "1e300"])
def test_inline_long_decimal_geometry_and_extreme_units_match_native_residual(scale):
    offset = "1." + "0" * 99 + "1"
    source = f"IsTangent(Line(Point(x,0),Point(0,y)),Circle(Point({offset}*{scale},0),2*{scale}))"
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "constraints": [source, "x+y"],
                "v": [0, f"7*{scale}"],
                "answer": "x",
            }
        )
    )
    payload = (
        ev.bundle.var_names,
        (),
        tuple(ev.bundle.spec.constraints),
        tuple(str(target) for target in ev.bundle.targets),
    )
    plan = analytic.compile_jacobian(json.loads(json.dumps(payload)))
    assert plan is not None
    with mp.workdps(240):
        unit = mp.mpf(scale)
        point = [3 * unit, 4 * unit]
        computed = analytic.evaluate_jacobian(plan, point, 240)
        assert computed is not None
        h = unit * mp.mpf("1e-75")
        for column in range(2):
            a, b = point.copy(), point.copy()
            a[column] += h
            b[column] -= h
            plus = refiner.MpmathRefiner()._residual_vector_for_stage(
                ev.bundle, ev, a, 240, smooth_zero_constraints=True
            )
            minus = refiner.MpmathRefiner()._residual_vector_for_stage(
                ev.bundle, ev, b, 240, smooth_zero_constraints=True
            )
            difference = (plus[0] - minus[0]) / (2 * h)
            assert abs(computed[0][column] - difference) / unit < mp.mpf("1e-140")
