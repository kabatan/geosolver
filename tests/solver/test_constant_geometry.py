"""Constant geometry contracts and numerical regressions."""

from types import SimpleNamespace

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.exact_assembly.constant_geometry import (
    constant_geometry_expression,
    geometry_hint,
)
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.engine.standard.interpreter.context.high_precision import _get_high_precision_context
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.symbolic import OptionalSymbolicTimeout


@pytest.mark.parametrize("denominator", [7, 9, 11])
@pytest.mark.parametrize("normalize", [False, True])
def test_zero_variable_chord_bisector_hint_declines_descriptor_and_uses_existing_reconstruction(
    denominator, normalize
):
    # Sum of unit vectors at angles0 and theta points along theta/2.
    # The unexpanded acos hint is exact but not currently a supported descriptor;
    # the independently checked original angle is an existing affine-pi family.
    source = f"Angle(Point(1,0),Point(0,0),Point(1+cos(pi/{denominator}),sin(pi/{denominator})))"
    if normalize:
        source = f"({source})*({2 * denominator})/pi"
    hint = constant_geometry_expression({"source": source, "constructions": []})
    assert hint is not None
    with pytest.raises(sp.polys.polyerrors.NotAlgebraic):
        sp.minimal_polynomial(sp.sympify(hint))
    with mp.workdps(300):
        original = safe_eval_expr_hp(source, _get_high_precision_context(250))
        expected = mp.mpf(1) if normalize else mp.pi / (2 * denominator)
        assert abs(original - expected) < mp.mpf("1e-240")
        result = identify_answer(
            answer_hp=original,
            tier="standard",
            input_precision_dps=250,
            answer_uncertainty=mp.mpf("1e-230"),
            geometry_hint=hint,
            prefer_affine_pi=True,
        )
        assert result.exact_status == "identified"
        assert result.descriptor is not None
        assert result.identification_method != "verified_constant_geometry"
        assert (
            sp.simplify(
                sp.sympify(result.selected_exact_value)
                - (1 if normalize else sp.pi / (2 * denominator))
            )
            == 0
        )


@pytest.mark.parametrize(
    "error",
    [
        sp.polys.polyerrors.NotAlgebraic,
        sp.polys.polyerrors.CoercionFailed,
        sp.polys.polyerrors.PolynomialError,
    ],
)
def test_optional_polynomial_descriptor_errors_fall_back_without_weakening_confirmation(
    monkeypatch, error
):
    import geosolver.exact.descriptors as descriptors

    original = descriptors.describe_exact
    calls = []

    def unsupported_once(expression, *args, **kwargs):
        calls.append(expression)
        if len(calls) == 1:
            raise error("unsupported optional proposal")
        return original(expression, *args, **kwargs)

    monkeypatch.setattr(descriptors, "describe_exact", unsupported_once)
    with mp.workdps(200):
        result = identify_answer(
            answer_hp=mp.mpf(7) / 3,
            tier="standard",
            input_precision_dps=180,
            answer_uncertainty=mp.mpf("1e-170"),
            geometry_hint="7/3",
        )
    assert result.exact_status == "identified"
    assert result.identification_method == "pslq-linear"
    assert result.selected_exact_value == "7/3"
    assert len(calls) == 2


def test_global_deadline_is_not_caught_as_optional_hint_failure(monkeypatch):
    import geosolver.exact.descriptors as descriptors

    def timeout(*args, **kwargs):
        raise TimeoutError("global solve deadline")

    monkeypatch.setattr(descriptors, "describe_exact", timeout)
    with mp.workdps(200), pytest.raises(TimeoutError, match="global solve"):
        identify_answer(
            answer_hp=mp.mpf(7) / 3,
            tier="standard",
            input_precision_dps=180,
            answer_uncertainty=mp.mpf("1e-170"),
            geometry_hint="7/3",
        )


@pytest.mark.parametrize("scale", ["1/1000", "1", "1000"])
@pytest.mark.parametrize("rename", [False, True])
def test_translated_rotated_constant_geometry(scale, rename):
    p, q, r = ("alpha", "beta", "gamma") if rename else ("A", "B", "C")
    expression = constant_geometry_expression(
        {
            "source": f"Area({p},{q},{r})+Area(Circle({p},{scale}))",
            "constructions": [
                (p, "Point(7,-3)"),
                (q, f"Point(7-4*({scale}),-3+3*({scale}))"),
                (r, f"Point(7-3*({scale}),-3-4*({scale}))"),
            ],
        }
    )
    assert (
        sp.simplify(sp.sympify(expression) - (sp.Rational(25, 2) + sp.pi) * sp.Rational(scale) ** 2)
        == 0
    )


@pytest.mark.parametrize("source", ["x+1", "sqrt(-1)", "1/0", "Angle(A,B,C)"])
def test_unsupported_or_nonconstant_has_no_hint(source):
    assert constant_geometry_expression({"source": source, "constructions": []}) is None


def test_decimal_tokens_remain_exact():
    source = "Distance(Point(0,0),Point(0.123456789012345678901234567890123456789,0))"
    assert sp.sympify(
        constant_geometry_expression({"source": source, "constructions": []})
    ) == sp.Rational("0.123456789012345678901234567890123456789")


@pytest.mark.parametrize(
    "hint,expected_method", [("7/3", "verified_constant_geometry"), ("8/3", "pslq-linear")]
)
def test_hint_requires_original_confirmed_error_interval(hint, expected_method):
    with mp.workdps(200):
        result = identify_answer(
            answer_hp=mp.mpf(7) / 3,
            tier="standard",
            input_precision_dps=180,
            answer_uncertainty=mp.mpf("1e-170"),
            geometry_hint=hint,
        )
        assert result.identification_method == expected_method
        assert result.selected_exact_value == "7/3"
        assert result.descriptor is not None


def test_optional_timeout_falls_back_and_is_cached(monkeypatch):
    import geosolver.runtime.symbolic as symbolic

    def timeout(*args, **kwargs):
        raise OptionalSymbolicTimeout("optional")

    monkeypatch.setattr(symbolic, "request", timeout)
    evaluator = SimpleNamespace(
        bundle=SimpleNamespace(
            var_names=(),
            analysis_plan=SimpleNamespace(),
            spec=SimpleNamespace(answer_expr="1", construction=()),
        )
    )
    assert geometry_hint(evaluator) is None
    monkeypatch.setattr(symbolic, "request", lambda *args, **kwargs: pytest.fail("retry"))
    assert geometry_hint(evaluator) is None


def test_global_timeout_is_not_swallowed(monkeypatch):
    import geosolver.runtime.symbolic as symbolic

    def timeout(*args, **kwargs):
        raise TimeoutError("global deadline")

    monkeypatch.setattr(symbolic, "request", timeout)
    evaluator = SimpleNamespace(
        bundle=SimpleNamespace(
            var_names=(),
            analysis_plan=SimpleNamespace(),
            spec=SimpleNamespace(answer_expr="1", construction=()),
        )
    )
    with pytest.raises(TimeoutError, match="global"):
        geometry_hint(evaluator)


def test_variable_problems_do_not_request_constant_hint(monkeypatch):
    import geosolver.runtime.symbolic as symbolic

    monkeypatch.setattr(symbolic, "request", lambda *args, **kwargs: pytest.fail("variable target"))
    assert geometry_hint(SimpleNamespace(bundle=SimpleNamespace(var_names=("x",)))) is None
