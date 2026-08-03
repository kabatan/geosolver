from __future__ import annotations

from research.homotopy_baseline.compiler import (
    UnsupportedFormulation,
    admission_report,
    compile_problem,
)


def _problem(**overrides):
    problem = {
        "task": "solve",
        "id": "unit",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x**2", "value": 2}],
        "guards": ["AssumeGt(x, 0)"],
        "answer": "x",
        "post_process": "",
    }
    problem.update(overrides)
    return problem


def test_rational_sqrt_and_sign_guard_are_polynomialized():
    compilation = compile_problem(_problem())
    assert compilation.variables == ("x", "__hc_target")
    assert len(compilation.equations) == len(compilation.variables)
    assert compilation.inequalities[0].relation == ">"


def test_inverse_denominator_is_saturated_and_guarded():
    compilation = compile_problem(_problem(constraints=[{"def": "1/x", "value": 2}], answer="x"))
    assert any(name.startswith("__hc_inv_") for name in compilation.variables)
    assert any(item.relation == "!=" for item in compilation.inequalities)


def test_circle_line_intersection_uses_algebraic_discriminant_and_branch():
    problem = {
        "task": "solve",
        "id": "circle-line",
        "variables": {"names": ["r"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "C", "expr": "Circle(O, r)"},
            {"name": "A", "expr": "Point(-2, 0)"},
            {"name": "B", "expr": "Point(2, 0)"},
            {"name": "line", "expr": "Line(A, B)"},
            {"name": "P", "expr": "Intersect(line, C, n=1)"},
        ],
        "constraints": [{"def": "r", "value": 1}],
        "guards": ["AssumeGt(r, 0)"],
        "answer": "P.x",
        "post_process": "",
    }
    compilation = compile_problem(problem)
    assert compilation.admission.branch_count == 2
    assert any(name.startswith("__hc_sqrt_") for name in compilation.variables)


def test_core_rejects_angle_and_dynamic_trig_fail_closed():
    angle = _problem(variables={"names": []}, constraints=[], guards=[], answer="cos(pi/3)")
    report = admission_report(angle, mode="core")
    assert not report.supported
    assert "unsupported_call:cos" in report.reasons
    dynamic = _problem(answer="cos(x)")
    assert "unsupported_dynamic_trigonometry" in admission_report(dynamic, mode="extended").reasons


def test_extended_phase_only_lowers_to_unit_circle():
    problem = {
        "task": "solve",
        "id": "phase",
        "variables": {"names": ["t"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "C", "expr": "Circle(O, 1)"},
            {"name": "P", "expr": "PointOnCircle(C, t)"},
        ],
        "constraints": [{"def": "P.x", "value": 0}],
        "guards": [],
        "answer": "P.y",
        "post_process": "",
    }
    compilation = compile_problem(problem, mode="extended")
    assert "t" not in compilation.variables
    assert any(name.startswith("__hc_phase_cos_t") for name in compilation.variables)
    assert len(compilation.equations) == len(compilation.variables)


def test_fail_closed_for_overdetermined_source():
    problem = _problem(
        variables={"names": ["x"]},
        constraints=[{"def": "x", "value": 1}, {"def": "x", "value": 1}],
    )
    try:
        compile_problem(problem)
    except UnsupportedFormulation as error:
        assert "source_non_square" in str(error)
    else:
        raise AssertionError("overdetermined input was admitted")
