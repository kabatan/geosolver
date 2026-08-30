"""Positive and negative witnesses for the seven natural-problem regressions."""

from pathlib import Path

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.verification_numerics import differentiate
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.deadline import runtime_session


def evaluator(constraints, *, construction=(), guards=(), answer="x"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": list(construction),
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


@pytest.mark.parametrize("precision", [180, 350, 500])
def test_stationary_smooth_derivative_has_finite_absolute_error(precision):
    with mp.workdps(precision):
        result = differentiate(
            lambda p: (1 + p[0] ** 2 + p[0] ** 3, ()), (mp.mpf(0),), 0, mp.mpf(1), precision
        )
        assert result is not None
        value, error = result
        assert abs(value) <= error and error < mp.mpf("1e-30")


def test_cusp_is_not_misidentified_as_a_stationary_smooth_point():
    with mp.workdps(350):
        result = differentiate(lambda p: (abs(p[0]), ()), (mp.mpf("1e-250"),), 0, mp.mpf(1), 350)
        assert result is None or abs(result[0] - 1) <= result[1]


def test_positive_nonsmooth_margin_uses_bounded_one_sided_variation():
    from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier

    with mp.workdps(350):
        domain = DomainVerifier(None, (mp.mpf(0),), (mp.mpf("1e-100"),), (mp.mpf(1),), 350)
        value, error = domain.measure(lambda p: (1 - abs(p[0]), ()), "piecewise margin")
        assert value > 100 * error and error >= mp.mpf("1e-100")


def test_discontinuous_margin_cannot_use_the_nonsmooth_slope_bound():
    with mp.workdps(350):
        result = differentiate(
            lambda p: (mp.mpf(1) if p[0] >= 0 else mp.mpf(2), ()),
            (mp.mpf(0),),
            0,
            mp.mpf(1),
            350,
            allow_nonsmooth=True,
        )
        assert result is None


def test_nonzero_unsigned_area_equation_keeps_its_public_meaning():
    construction = [
        {"name": "A", "expr": "Point(0,0)"},
        {"name": "B", "expr": "Point(1,0)"},
        {"name": "C", "expr": "Point(0,x)"},
    ]
    with mp.workdps(180), runtime_session(None):
        ev = evaluator(["Area(A,B,C)-1"], construction=construction, answer="Area(A,B,C)")
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf(-2),))
        assert result.verified and result.answer_hp == 1


def test_verification_keeps_high_precision_input_and_rejects_a_wrong_circle():
    construction = [
        {"name": "O", "expr": "Point(0,0)"},
        {"name": "P", "expr": "Point(cos(x),sin(x))"},
        {"name": "omega", "expr": "Circle(O,1)"},
    ]
    with mp.workdps(180), runtime_session(None):
        point = (mp.sqrt(2),)
        ev = evaluator(["x*x-2", "OnCircle(P,omega)"], construction=construction)
        original = abs(point[0] - mp.sqrt(2))
        result = verify_final_candidate(evaluator=ev, values=point)
        assert result.verified and abs(result.values[0] - mp.sqrt(2)) <= original + mp.mpf("1e-175")
        bad = evaluator(["x*x-2", "OnCircle(P,omega)-0.01"], construction=construction)
        assert not verify_final_candidate(evaluator=bad, values=point).verified


@pytest.mark.parametrize("scale", ["1e-200", "1", "1e200"])
def test_zero_area_equation_uses_signed_residual_without_changing_its_zero_set(scale):
    construction = [
        {"name": "A", "expr": "Point(0,0)"},
        {"name": "B", "expr": "Point(1,0)"},
        {"name": "C", "expr": "Point(0,x)"},
    ]
    with mp.workdps(180), runtime_session(None):
        ev = evaluator([f"{scale}*Area(A,B,C)"], construction=construction, answer="7")
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf("1e-100"),))
        assert result.verified
        # A finite-difference update need not land on bitwise zero. The
        # strengthened roundoff floor must cover its remaining coordinate error.
        assert abs(result.values[0]) <= result.coordinate_uncertainty[0]
        forbidden = evaluator([f"{scale}*Area(A,B,C)"], construction=construction, guards=["x>0"])
        assert not verify_final_candidate(evaluator=forbidden, values=(mp.mpf("1e-100"),)).verified
        bad = evaluator([f"{scale}*Area(A,B,C)", "x-1"], construction=construction)
        assert not verify_final_candidate(evaluator=bad, values=(mp.mpf(1),)).verified


@pytest.mark.parametrize(
    "identifier,coordinates,expected",
    [
        ("AIME-2013-II-08", ("5+sqrt(267)",), "5 + sqrt(267)"),
        ("AIME-2015-I-06", ("pi/9", "7*pi/45"), "58"),
        ("AIME-2022-I-08", ("12",), "-3*sqrt(3) + 3*sqrt(39)"),
        ("HMMT-2014-FEB-GEO-08", ("82/73",), "600/73"),
        ("HMMT-2016-FEB-GEO-04", ("5/13",), "7*sqrt(3)/3"),
        ("HMMT-2019-FEB-GEO-08", ("-9/7", "12/7"), "6/7"),
        (
            "JMO-2019-PRE-10",
            ("-11.1944292220400814283418313388311210079872582189727825319341885",),
            "-1/2 + sqrt(33)/6",
        ),
    ],
)
def test_natural_valid_witness_survives_complete_exact_assembly(identifier, coordinates, expected):
    import sympy as sp

    path = Path(__file__).resolve().parents[1] / "benchmarks/dsl" / (identifier + ".json")
    problem = GeometryProblem.model_validate_json(path.read_text())
    ev = build_ir_evaluator(load_problem_bundle(problem.engine_document()))
    with mp.workdps(180), runtime_session(None), high_precision_mode():
        point = tuple(mp.mpf(str(sp.N(sp.sympify(x), 190))) for x in coordinates)
        value = ev.evaluate_answer_hp(point, precision=180).answer_hp
        candidate = RefinedCandidate(point, mp.mpf("1e-170"), value, "stalled", ())
        result = assemble_exact_results(refined_candidates=(candidate,), evaluator=ev)
    assert len(result.answer_values) == 1, result.rejection_tags
    assert sp.simplify(sp.sympify(result.answer_values[0]) - sp.sympify(expected)) == 0
    with mp.workdps(600):
        root = mp.mpf(str(sp.N(sp.sympify(expected), 590)))
        accepted = result.accepted_candidates[0]
        assert abs(accepted.answer_hp - root) <= accepted.answer_uncertainty


def test_discovery_precision_does_not_override_final_error_bound():
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer

    with mp.workdps(350):
        result = identify_answer(
            answer_hp=mp.sqrt(2) + mp.mpf("1e-110"),
            tier="strict",
            input_precision_dps=350,
            answer_uncertainty=mp.mpf("1e-120"),
        )
        assert result.selected_exact_value != "sqrt(2)"
        result = identify_answer(
            answer_hp=mp.sqrt(2) + mp.mpf("1e-100"),
            tier="strict",
            input_precision_dps=350,
            answer_uncertainty=mp.mpf("1e-99"),
        )
        assert result.selected_exact_value == "sqrt(2)"


def test_irrational_guard_limits_constrain_search_without_changing_exact_guards():
    import math

    import sympy as sp

    from geosolver.problem.domain_bounds import mathematical_bounds, search_bounds

    ev = evaluator(["sin(x)-12*pi/180"], guards=["x>0", "Not(x>=pi/4)"])
    domain = mathematical_bounds(ev.bundle.spec)["x"]
    assert domain.upper == sp.pi / 4 and not domain.upper_closed
    lo, hi = search_bounds(ev.bundle.spec)[0]
    assert lo == 0 and math.pi / 4 <= hi < math.pi / 4 + 1e-15
    ev = evaluator(["x*x-2"], guards=["x/(-sqrt(2))>-1", "x>0"])
    assert mathematical_bounds(ev.bundle.spec)["x"].upper == sp.sqrt(2)


def test_aime_2015_search_box_does_not_discard_pi_bounds():
    import math

    from geosolver.problem.domain_bounds import search_bounds

    path = Path(__file__).resolve().parents[1] / "benchmarks/dsl/AIME-2015-I-06.json"
    problem = GeometryProblem.model_validate_json(path.read_text())
    ev = build_ir_evaluator(load_problem_bundle(problem.engine_document()))
    bounds = search_bounds(ev.bundle.spec)
    assert bounds[0][0] == bounds[1][0] == 0
    assert abs(bounds[0][1] - math.pi / 4) < 1e-15
    assert abs(bounds[1][1] - math.pi / 5) < 1e-15
    from geosolver.engine.standard.refinement.mpmath_refiner import _convert_problem_bounds

    hp_bounds = _convert_problem_bounds(ev.bundle)
    with mp.workdps(500):
        assert abs(hp_bounds[0][1] - mp.pi / 4) < mp.mpf("1e-490")
        assert abs(hp_bounds[1][1] - mp.pi / 5) < mp.mpf("1e-490")


def test_public_solve_carries_irrational_bounds_through_refinement():
    from geosolver import solve

    problem = GeometryProblem(
        id="irrational-bound-pipeline",
        variables=["x"],
        constructions=[],
        conditions=[
            {"left": "x", "operator": "=", "right": "pi/6"},
            {"left": "x", "operator": ">", "right": 0},
            {"left": "x", "operator": "<", "right": "pi/4"},
        ],
        target="6*x/pi",
    )
    result = solve(problem)
    assert result.status == "solved", result.error
    assert result.answers[0].value.minimal_polynomial == ["1", "-1"]
