"""Exact proposals must agree with independent numerical geometry evidence."""

from types import SimpleNamespace

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.exact_assembly.constant_geometry import (
    constant_geometry_expression,
    geometry_hint,
)
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.runtime.symbolic import OptionalSymbolicTimeout


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
