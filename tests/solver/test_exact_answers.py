"""Exact answers contracts and numerical regressions."""

import time
from dataclasses import replace

import pytest
from mpmath import mp

from geosolver import GeometryProblem, solve
from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.exact import assemble_exact_answers as _public_assemble_exact_answers
from geosolver.exact import describe_exact
from geosolver.exact.descriptors import assemble_exact_answers as _descriptor_assemble_exact_answers
from geosolver.runtime.deadline import runtime_session


def test_exact_root_is_not_nsimplified_to_a_nearby_rational():
    with mp.workdps(150):
        value = mp.findroot(lambda x: x**8 - 10**7 * x + 1, mp.mpf("1e-7"))
        result = identify_answer(answer_hp=value, tier="strict", input_precision_dps=120)
        assert result.exact_status == "identified"
        assert result.selected_exact_value != "1/10000000"


def test_close_exact_roots_remain_distinct():
    answers, warnings = _descriptor_assemble_exact_answers(
        ["1-sqrt(2)/10**130", "1+sqrt(2)/10**130"]
    )
    assert not warnings
    assert len(answers) == 2
    assert {answer.value.real_root_index for answer in answers} == {0, 1}


def test_small_algebraic_scale_is_exactly_reconstructed():
    with mp.workdps(150):
        result = identify_answer(
            answer_hp=mp.sqrt(2) / 10**10, tier="strict", input_precision_dps=120
        )
        assert result.exact_status == "identified"


def test_closed_expression_is_not_rounded_to_a_simple_neighbour():
    result = solve(
        GeometryProblem(
            id="offset", variables=[], constructions=[], conditions=[], target="sqrt(2)+1e-110"
        )
    )
    assert result.status == "solved"
    assert result.answers[0].value.minimal_polynomial != ["1", "0", "-2"]
    assert "closed_scalar_expression" in str(result.diagnostics)


def test_variable_offset_is_not_reconstructed_as_sqrt_two():
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constraints": ["x-sqrt(2)-1e-110"],
                "answer": "x",
                "guards": ["x>0"],
            }
        )
    )
    with mp.workdps(180):
        candidate = RefinedCandidate((mp.sqrt(2),), mp.mpf("1e-110"), mp.sqrt(2), "stalled", ())
        result = assemble_exact_results(refined_candidates=(candidate,), evaluator=evaluator)
    assert "sqrt(2)" not in result.answer_values


@pytest.mark.parametrize("power", [-100, 100])
def test_large_and_small_algebraic_values(power):
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer

    with mp.workdps(350):
        result = identify_answer(
            answer_hp=mp.sqrt(2) * mp.power(10, power), tier="strict", input_precision_dps=250
        )
    assert result.exact_status == "identified" and result.descriptor is not None


def test_radian_angle_is_affine_pi() -> None:
    answer = describe_exact("pi/2")

    assert answer.kind == "affine_pi"
    assert answer.pi_coefficient.minimal_polynomial == ["2", "-1"]
    assert answer.constant.minimal_polynomial == ["1", "0"]


def test_degree_conversion_is_algebraic() -> None:
    answer = describe_exact("90")

    assert answer.kind == "algebraic"
    assert answer.minimal_polynomial == ["1", "-90"]


def test_affine_pi_accepts_real_algebraic_coefficients() -> None:
    answer = describe_exact("sqrt(2) * pi + sqrt(3)")

    assert answer.kind == "affine_pi"
    assert answer.pi_coefficient.minimal_polynomial == ["1", "0", "-2"]
    assert answer.constant.minimal_polynomial == ["1", "0", "-3"]


def test_zero_distance_retains_precision_for_exact_algebraic_answer():
    from geosolver import GeometryProblem, SolveOptions, solve

    # Answer stability at 250 digits is insufficient for the later domain
    # boundary/uncertainty check, even though x+y already looks unchanged.
    problem = GeometryProblem(
        id="zero-distance-precision",
        variables=["x", "y"],
        constructions=[
            {"name": "P", "expression": "Point(x,y)"},
            {"name": "Q", "expression": "Point(2,sqrt(2))"},
        ],
        conditions=[
            {"left": "Distance(P,Q)", "operator": "=", "right": 0},
            {"left": "x", "operator": ">", "right": 0},
            {"left": "y", "operator": ">", "right": 0},
        ],
        target="x+y",
    )
    result = solve(problem, SolveOptions(time_limit_seconds=180, cores=1, seed=0))
    assert result.status == "solved"
    assert len(result.answers) == 1
    answer = result.answers[0]
    assert answer.kind == "algebraic"
    assert answer.minimal_polynomial == ["1", "-4", "2"]
    assert answer.real_root_index == 1


def test_pslq_does_not_repeat_the_unscaled_trial(monkeypatch):
    from geosolver.exact import polynomial_search

    calls = []

    def search_polynomial(value, degree, precision, **kwargs):
        calls.append((value, degree))
        return None

    monkeypatch.setattr(polynomial_search, "_find_polynomial_pslq", search_polynomial)
    monkeypatch.setattr(polynomial_search, "scale_candidates_for_value", lambda value: [1, 10])
    assert polynomial_search.find_minimal_polynomial(mp.mpf(7), max_degree=3) is None
    assert len(calls) == 6
    assert sum(value == 7 for value, degree in calls) == 3


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


def test_descriptor_reuse_rechecks_the_new_answer_and_rejects_ambiguity(monkeypatch):
    import sympy as sp

    from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
    from geosolver.exact.descriptors import describe_exact

    with mp.workdps(120):
        prior = ExactIdentificationResult(
            "identified",
            "fixture",
            100,
            (1, -1),
            1,
            "1",
            mp.mpf(0),
            None,
            describe_exact(1),
            discovery_precision_dps=60,
        )
        result = identify_answer(
            answer_hp=1 + mp.mpf("1e-90"),
            tier="strict",
            input_precision_dps=100,
            answer_uncertainty=mp.mpf("1e-80"),
            reusable_results=(prior,),
        )
        assert result.identification_method == "verified_descriptor_reuse"
        assert 0 < result.verification_residual < mp.mpf("1e-80")
        assert result.descriptor.canonical_key() == prior.descriptor.canonical_key()
        other_value = 1 + sp.Rational(1, 10**70)
        other = replace(
            prior, selected_exact_value=str(other_value), descriptor=describe_exact(other_value)
        )
        calls = []

        def propose(**kwargs):
            calls.append(kwargs)
            return replace(prior, selected_exact_value=None, descriptor=None)

        monkeypatch.setattr(
            "geosolver.engine.standard.exact_assembly.identify_answer._identify_answer_proposal",
            propose,
        )
        for value, uncertainty, bank in (
            (mp.mpf(1), mp.mpf("1e-60"), (prior, other)),
            (mp.mpf(2), mp.mpf("1e-80"), (prior,)),
        ):
            result = identify_answer(
                answer_hp=value,
                tier="strict",
                input_precision_dps=100,
                answer_uncertainty=uncertainty,
                reusable_results=bank,
            )
            assert result.identification_method != "verified_descriptor_reuse"
        assert len(calls) == 2


def test_exactification_precedes_deduplication() -> None:
    close_distinct = f"1 + 1/{10**30}"
    answers, warnings = _public_assemble_exact_answers(["1", close_distinct, "sqrt(2)", "2**(1/2)"])

    assert not warnings
    assert len(answers) == 3
    assert len({answer.canonical_key() for answer in answers}) == 3
