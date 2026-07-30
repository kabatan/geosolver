from __future__ import annotations

import json

import static_source_census as census


def _source(*, construction, constraints, guards, answer="0"):
    return {
        "variables": {"names": ["t"]},
        "construction": construction,
        "constraints": constraints,
        "guards": guards,
        "answer": answer,
    }


def test_formulation_extractor_does_not_deserialize_sibling_values():
    formulation = {"variables": {"names": []}, "answer": "0"}
    row = b'{"truth":not_deserialized,"formulation":' + json.dumps(formulation).encode() + b"}"
    assert json.loads(census.formulation_bytes(row)) == formulation


def test_exact_pair_bound_and_positive_distance_literal_activate():
    document = _source(
        construction=[{"name": "P", "expr": "Point(cos(t), sin(t))"}],
        constraints=[{"def": "Distance(P, Point(0, 0))", "value": "3/2"}],
        guards=["Bound(t, (-pi, pi), inclusive=False)"],
    )
    result = census.analyze_formulation(document)
    assert result["explicit_pair"] is True
    assert result["finite_sheet_trig"] is True
    assert result["d0_compatible_trig"] is True
    assert result["safe_distance_square"] is True
    assert result["any_distance_constraint"] is True
    assert result["safe_distance_literal_constraints"] == 1


def test_point_on_circle_is_typed_but_raw_parameter_escape_fails_d0_gate():
    document = _source(
        construction=[{"name": "P", "expr": "PointOnCircle(C, t)"}],
        constraints=[{"def": "t", "value": "1"}],
        guards=["Bound(t, (0, 1), inclusive=False)"],
    )
    result = census.analyze_formulation(document)
    assert result["point_on_circle"] is True
    assert result["raw_phase_escape"] is True
    assert result["d0_compatible_trig"] is False


def test_mixed_radian_and_turn_units_fail_closed():
    document = _source(
        construction=[
            {"name": "P", "expr": "Point(cos(t), sin(t))"},
            {"name": "Q", "expr": "PointOnCircle(C, t)"},
        ],
        constraints=[],
        guards=["Bound(t, (0, 1))"],
    )
    result = census.analyze_formulation(document)
    assert result["mixed_units"] is True
    assert result["d0_compatible_trig"] is False


def test_distance_to_distance_is_safe_but_unknown_sign_expression_is_not():
    safe = _source(
        construction=[],
        constraints=[
            {"def": "Distance(A, B)", "value": "Distance(C, D)"},
            {"def": "Distance(A, C)", "value": "-1"},
        ],
        guards=[],
    )
    result = census.analyze_formulation(safe)
    assert result["safe_distance_distance_constraints"] == 1
    assert result["safe_distance_literal_constraints"] == 0
    assert result["safe_distance_square"] is True
    assert result["any_distance_constraint"] is True


def test_nonlinear_phase_and_missing_bound_do_not_activate_d0():
    document = _source(
        construction=[{"name": "P", "expr": "Point(cos(t*t), sin(t*t))"}],
        constraints=[],
        guards=[],
    )
    result = census.analyze_formulation(document)
    assert result["malformed_phase"] is True
    assert result["d0_compatible_trig"] is False
