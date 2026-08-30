"""Regression tests from independent corpus configurations, not solver outputs."""

import json
import time
from pathlib import Path

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.deadline import runtime_session

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "benchmarks/repairs/corpus97"


def make_evaluator(dsl):
    return build_ir_evaluator(
        load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    )


def test_saved_jmo_2009_forbidden_boundary_is_not_accepted():
    dsl = json.loads((AUDIT / "known-boundary-regression.json").read_text())
    fixtures = json.loads((ROOT / "tests/fixtures/forbidden-boundary-candidates.json").read_text())
    candidate = next(
        c
        for c in fixtures
        if c["candidate_id"] == 9000000000014
    )
    with mp.workdps(1200), runtime_session(time.monotonic() + 15):
        point = tuple(mp.mpf(v) for v in candidate["x_hp"])
        assert not verify_final_candidate(evaluator=make_evaluator(dsl), values=point).verified


def test_jmo_2009_true_noncoincident_configuration_survives():
    dsl = json.loads((AUDIT / "known-boundary-regression.json").read_text())
    with mp.workdps(220), runtime_session(time.monotonic() + 15):
        point = (mp.mpf(14) / 9, 8 * mp.sqrt(2) / 9, mp.mpf(26) / 9, -16 * mp.sqrt(2) / 9)
        result = verify_final_candidate(evaluator=make_evaluator(dsl), values=point)
        assert result.verified, result.hard_failure_tags
        assert abs(result.answer_hp - mp.mpf(8) / 3) < mp.mpf("1e-100")


@pytest.mark.parametrize(
    "identifier",
    [
        "HMMT-2016-FEB-GEO-10",
        "HMMT-2018-FEB-GEO-10",
        "AIME-2021-II-14",
        "HMMT-2017-FEB-GEO-07",
        "HMMT-2013-FEB-GEO-10",
        "AIME-2019-II-11",
        "JMO-2017-PRE-04",
        "JMO-2024-PRE-03",
        "JMO-2024-PRE-06",
        "AIME-2010-I-13",
        "HMMT-2008-FEB-GEO-05",
        "AIME-2013-I-12",
    ],
)
def test_original_dsl_accepts_independent_valid_configuration(identifier):
    records = json.loads((ROOT / "tests/fixtures/independent-configurations.json").read_text())[
        "witnesses"
    ]
    witness = next(r for r in records if r["id"] == identifier)
    dsl = json.loads((ROOT / "benchmarks/dsl" / f"{identifier}.json").read_text())
    with mp.workdps(220), runtime_session(time.monotonic() + 20):
        point = tuple(
            mp.mpf(str(sp.N(sp.sympify(witness["assignments"][v]), 240))) for v in dsl["variables"]
        )
        ev = make_evaluator(dsl)
        result = verify_final_candidate(evaluator=ev, values=point)
        assert result.verified, (identifier, result.hard_failure_tags)
        confirmation = verify_final_candidate(
            evaluator=ev, values=result.values, precision_schedule=(250, 350, 500)
        )
        assert confirmation.verified, (identifier, confirmation.hard_failure_tags)


def test_confirmed_absolute_error_identifies_zero_but_not_tiny_resolved_number():
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer

    with mp.workdps(350), runtime_session(time.monotonic() + 15):
        result = identify_answer(
            answer_hp=mp.mpf("5.9e-382"),
            tier="strict",
            input_precision_dps=350,
            answer_uncertainty=mp.mpf("1e-352"),
        )
        assert result.selected_exact_value == "0"
        assert result.descriptor is not None and result.polynomial_degree == 1
        result = identify_answer(
            answer_hp=mp.mpf("1e-40"),
            tier="strict",
            input_precision_dps=350,
            answer_uncertainty=mp.mpf("1e-350"),
        )
        assert result.selected_exact_value != "0"


@pytest.mark.parametrize("precision", [40, 120, 250])
def test_native_tangent_uses_constructed_incidence_not_a_numeric_tolerance(precision):
    from geosolver.errors import NoIntersectionError
    from geosolver.geometry.mp.mp_api_common_wrappers import MP_Circumcircle
    from geosolver.geometry.mp.mp_api_geometry import MP_Tangent
    from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint
    from geosolver.geometry.mp.mp_parametric_points import mp_point_on_circle

    with mp.workdps(precision):
        vertices = [MPPoint(0, 0), MPPoint(3, 0), MPPoint(1, 2)]
        circle = MP_Circumcircle(*vertices)
        for point in (*vertices, mp_point_on_circle(circle, mp.mpf("0.123"))):
            first, second = (MP_Tangent(point, circle, branch) for branch in (True, False))
            assert (first.a, first.b, first.c) == (second.a, second.b, second.c)
        unit = MPCircle(MPPoint(0, 0), 1)
        near_inside = MPPoint(1 - mp.power(10, -precision + 10), 0)
        with pytest.raises(NoIntersectionError):
            MP_Tangent(near_inside, unit)
        point = mp_point_on_circle(unit, 0)
        point.x -= mp.power(10, -precision + 10)
        with pytest.raises(NoIntersectionError):
            MP_Tangent(point, unit)  # Mutation invalidates the incidence witness.


def test_numeric_contact_selector_has_float_hp_parity_and_rejects_unknown_side():
    from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )

    with mp.workdps(80):
        for context, index in [
            (_get_geometry_context(), 0),
            (_get_high_precision_context(80), mp.mpf(0)),
        ]:
            vertices = [context["Point"](0, 0), context["Point"](4, 0), context["Point"](0, 3)]
            named = context["IncircleContactPoint"](*vertices, "BC")
            numeric = context["IncircleContactPoint"](*vertices, index)
            assert named.x == numeric.x and named.y == numeric.y
            for invalid in [True, 3, "not-a-side"]:
                with pytest.raises(ValueError):
                    context["IncircleContactPoint"](*vertices, invalid)


@pytest.mark.parametrize("point", [1, 2, 3])
def test_logical_equality_lowering_keeps_all_disjuncts(point):
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [],
                "constraints": [],
                "guards": ["Or(x==1,And(x==2,2*x==4),x==3)"],
                "answer": "x",
            }
        )
    )
    with mp.workdps(180), runtime_session(None):
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf(point),))
        assert result.verified and result.answer_hp == point
        with high_precision_mode():
            residual = ev.evaluate_hp_residual((mp.mpf("1.5"),), precision=180)
        assert residual.residual_norm_hp > 0


def test_zero_line_distance_still_rejects_coincident_line_endpoints():
    ev = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(0,0)"},
                    {"name": "P", "expr": "Point(0,x)"},
                ],
                "constraints": ["Distance(P,Line(A,B))"],
                "guards": [],
                "answer": "x",
            }
        )
    )
    with mp.workdps(180), runtime_session(None):
        assert not verify_final_candidate(evaluator=ev, values=(mp.mpf(0),)).verified


def test_exclude_lowering_requires_an_incidence_proof():
    from geosolver.problem.construction_contracts import _lower

    items = (
        ("A", "Point(0,0)"),
        ("B", "Point(2,0)"),
        ("P", "Point(3,0)"),
        ("omega", "Circle(A,1)"),
        ("ell", "Line(A,B)"),
        ("Q", "Intersect(ell,omega,exclude=P)"),
    )
    lowered, guards, evidence = _lower(items, ())
    assert not guards and not evidence
    assert "exclude" in lowered[-1][1]


def test_quarantined_problem_is_not_counted_as_a_solver_failure(tmp_path):
    from benchmarks.research_runner import summarize_campaign

    rows = [
        {"matched": True, "status": "solved"},
        {"matched": None, "status": "no_answer_found", "truth_status": "quarantined"},
    ]
    (tmp_path / "assessment.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    summarize_campaign(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["run_count"] == 2 and summary["assessed_count"] == 1
    assert summary["unassessed_count"] == 1 and summary["match_rate"] == 1
