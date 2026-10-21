"""Integer search contracts and numerical regressions."""

import importlib
import math
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.orchestration.assemble_exact_results import ExactAssemblyResult
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.zero_test_source import zero_test_call
from geosolver.engine.standard.refinement.mpmath_refiner import (
    IntegerConstraintClosure,
    _exact_answer_from_integer_closures,
    _extract_isinteger_inner_expression,
)
from geosolver.engine.standard.search.discrete.square_difference import (
    _square_root_points,
    finite_integer_square_roots,
)
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.geometry.mp.mp_number_constraints import mp_is_prime
from geosolver.problem.adapter import to_engine_document


def _bundle(answer_expr: str) -> SimpleNamespace:
    return SimpleNamespace(
        var_names=("u", "v"),
        spec=SimpleNamespace(answer_expr=answer_expr),
    )


def _closures() -> tuple[IntegerConstraintClosure, ...]:
    return (
        IntegerConstraintClosure(
            constraint_index=0,
            inner_expression="u",
            target_integer=mp.mpf(11),
        ),
        IntegerConstraintClosure(
            constraint_index=1,
            inner_expression="v",
            target_integer=mp.mpf(10),
        ),
    )


def test_integer_closure_supplies_exact_arithmetic_answer() -> None:
    answer = _exact_answer_from_integer_closures(
        bundle=_bundle("u + v"),
        closures=_closures(),
    )

    assert answer == 21


def test_integer_closure_keeps_rational_answer_at_high_precision() -> None:
    answer = _exact_answer_from_integer_closures(
        bundle=_bundle("u / 3"),
        closures=_closures(),
    )

    with mp.workdps(100):
        assert abs(answer - mp.mpf(11) / 3) < mp.mpf("1e-90")


def test_integer_closure_does_not_hint_geometry_expression() -> None:
    answer = _exact_answer_from_integer_closures(
        bundle=_bundle("Distance(Point(u, v), Point(0, 0))"),
        closures=_closures(),
    )

    assert answer is None


def test_prime_constraints_use_integer_projection_and_unbounded_exact_test() -> None:
    assert _extract_isinteger_inner_expression("IsPrime(n)") == "n"
    with mp.workdps(180):
        assert mp_is_prime(mp.mpf(1009)) == 0
        assert mp_is_prime(mp.mpf(1009) + mp.mpf("1e-80")) != 0
        assert mp_is_prime(mp.mpf(1001)) != 0


def bundle(problem):
    return load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))


@pytest.mark.parametrize("offsets", [(3, 1), (8, 5), (17, 4), (15, 6)])
@pytest.mark.parametrize("representation", [0, 1])
def test_integer_square_difference_finds_outlying_integer_lengths(offsets, representation):
    a, b = offsets
    variable = "t" if representation else "x"
    conditions = [
        {"left": f"IsInteger(sqrt({variable}**2+{a * a}))", "operator": "=", "right": 0},
        {"left": f"IsInteger(sqrt({variable}**2+{b * b}))", "operator": "=", "right": 0},
    ]
    if representation:
        conditions = [
            {"left": "-7*(" + c["left"] + ")", "operator": "=", "right": 0}
            for c in reversed(conditions)
        ]
        conditions.append({"left": "0", "operator": "=", "right": 0})
    problem = {
        "id": "general-square-pair",
        "variables": [variable],
        "constructions": [],
        "conditions": conditions,
        "target": variable,
    }
    roots, difference = finite_integer_square_roots(bundle(problem))
    assert abs(difference) == a * a - b * b
    # Enumerate a separately derived finite integer length range. m-n >= 1
    # implies m+n <= |N|, hence m <= (|N|+1)/2.
    expected = set()
    for m in range((a * a - b * b + 1) // 2 + 1):
        square = m * m - a * a
        if square < 0:
            continue
        n2 = square + b * b
        if math.isqrt(n2) ** 2 == n2:
            expected.update((-math.sqrt(square), math.sqrt(square)))
    assert {round(x[0], 10) for x in roots} == {round(x, 10) for x in expected}


def test_equal_integer_squares_do_not_claim_finite_enumeration():
    problem = {
        "id": "equal-squares",
        "variables": ["x"],
        "constructions": [],
        "conditions": [
            {"left": "IsInteger(x)", "operator": "=", "right": 0},
            {"left": "IsInteger(-x)", "operator": "=", "right": 0},
        ],
        "target": "x",
    }
    assert finite_integer_square_roots(bundle(problem)) is None


@pytest.mark.parametrize(
    "source", ["0*IsInteger(x)", "x*IsInteger(x)", "IsInteger(x)+1", "IsInteger(x)/x"]
)
def test_zero_wrappers_do_not_drop_additional_root_sets(source):
    assert zero_test_call(source) is None


@pytest.mark.parametrize("translation,offsets", [(10**100, (4, 1)), (10**400, (3, 1))])
def test_unrepresentable_distinct_integer_square_seeds_fall_back(translation, offsets):
    a, b = offsets
    shifted = f"(x-({translation}))"
    problem = {
        "id": "large-translation-family",
        "variables": ["x"],
        "constructions": [],
        "conditions": [
            {"left": f"IsInteger(sqrt({shifted}**2+{a * a}))", "operator": "=", "right": 0},
            {"left": f"IsInteger(sqrt({shifted}**2+{b * b}))", "operator": "=", "right": 0},
        ],
        "target": "x",
    }
    assert finite_integer_square_roots(bundle(problem)) is None


pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")


search = importlib.import_module("geosolver.engine.standard.orchestration.run_search")


def proposal(index, backend, attempt=0):
    return FloatCandidate(
        (float(index),),
        0,
        0,
        True,
        EvaluationStatus.OK,
        0,
        index,
        candidate_id=index,
        origin_backend=backend,
        origin_attempt=attempt,
        originating_branch_box=((str(index - 0.25), str(index + 0.25)),),
    )


def accepted(origin, coordinate=None):
    return RefinedCandidate(
        (mp.mpf(origin.x_float[0] if coordinate is None else coordinate),),
        mp.mpf(0),
        mp.mpf(7),
        "target_reached",
        (),
        source=origin,
        candidate_id=origin.candidate_id,
        hard_feasible=True,
        revision=2,
        coordinate_uncertainty=(mp.mpf("1e-60"),),
    )


def outcome(attempt, proposals, verified):
    values = tuple("7" for _ in verified)
    assembly = ExactAssemblyResult(
        verified,
        verified,
        values,
        tuple(SimpleNamespace(candidate=c) for c in verified),
        values,
        0,
        (),
        tuple({"candidate_uid": c.candidate_uid, "verified": True} for c in verified),
    )
    stage = pipeline._CompletedPipelineStageState(
        initial_probe_result=None,
        search_result=SearchBatchResult(proposals, len(proposals), 0, all_records=proposals),
        refinement_result=RefinementBatchResult(verified, len(verified), len(verified)),
        exact_assembly_result=assembly,
        rescue_search_summary={},
        integer_fallback_summary={},
    )
    return pipeline._OrderedSearchAttemptOutcome(attempt, stage)


@pytest.mark.parametrize("backend", ["integer_square_difference"])
@pytest.mark.parametrize("verification", ["missing", "drifted", "complete"])
def test_integer_roots_only_skip_fallback_after_every_origin_is_independently_verified(
    monkeypatch, backend, verification
):
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    fallback = pipeline._OrderedSearchAttemptDescriptor("hybrid_fallback", "fallback", None, None)
    a, b = proposal(1, backend), proposal(2, backend)
    verified = (accepted(a),)
    if verification != "missing":
        verified += (accepted(b, 1 if verification == "drifted" else 2),)
    first = outcome(primary, (a, b), verified)
    c = proposal(3, "scipy", attempt=1)
    second = outcome(fallback, (c,), (accepted(c),))
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["attempt"])
        return first if kwargs["attempt"] is primary else second

    monkeypatch.setattr(pipeline, "_execute_ordered_search_attempt", execute)
    result = pipeline._run_ordered_search_attempts(
        ordered_attempts=(primary, fallback),
        bundle=None,
        evaluator=None,
        bounds=[],
        refiner=None,
        runtime_budget=SimpleNamespace(remaining_sec=lambda: 100),
    )
    assert calls == ([primary] if verification == "complete" else [primary, fallback])
    if verification != "complete":
        combined = result.selected_outcome.completed_stage_state.exact_assembly_result
        assert combined.accepted_candidates == verified + (accepted(c),)
        assert len(combined.verification_records) == len(verified) + 1


def batch(candidates, diagnostics=None):
    return SearchBatchResult(
        tuple(candidates),
        len(candidates),
        0,
        all_records=tuple(candidates),
        guard_feasible_ledger=tuple(candidates),
        search_diagnostics=diagnostics or {},
    )


def disable_other_proposals(monkeypatch):
    from geosolver.engine.standard.search import finite_guard_search, scale_chart

    monkeypatch.setattr(finite_guard_search, "search_finite_guards", lambda **_: None)
    monkeypatch.setattr(scale_chart, "search_positive_scale_chart", lambda **_: None)


@pytest.mark.parametrize("complete", [False, True])
def test_partial_float_filtering_of_finite_roots_preserves_ordinary_backend(monkeypatch, complete):
    from geosolver.engine.standard.search.discrete import square_difference

    a = proposal(1, "integer_square_difference")
    b = proposal(2, "ordinary")
    discrete = batch((a,), {"integer_square_difference": {"all_finite_seeds_admissible": complete}})
    ordinary = batch((b,))
    calls = []
    monkeypatch.setattr(square_difference, "scan_integer_square_branches", lambda **_: discrete)
    monkeypatch.setattr(
        search,
        "_build_search_backend",
        lambda **_: SimpleNamespace(run_search=lambda **kw: calls.append(kw) or ordinary),
    )
    disable_other_proposals(monkeypatch)
    result = search.run_search(
        bundle=None,
        evaluator=None,
        bounds=[(-10, 10)],
        initial_probe_result=InitialProbeResult((a,), {}),
        config=replace(NomadConfig(max_bb_eval=1), seed_values=(0,)),
    )
    assert len(calls) == (0 if complete else 1)
    assert result.candidates == ((a,) if complete else (a, b))


@pytest.mark.parametrize("dimensions", [1, 4])
def test_numeric_completion_cannot_reenter_integer_early_return(monkeypatch, dimensions):
    from geosolver.engine.standard.search.discrete import square_difference

    def forbidden(**kwargs):
        raise AssertionError("integer enumeration reentered numeric completion")

    monkeypatch.setattr(square_difference, "scan_integer_square_branches", forbidden)
    disable_other_proposals(monkeypatch)
    calls = []
    original = replace(proposal(1, "ordinary"), x_float=(1.0,) * dimensions)
    ordinary = batch((original,))
    monkeypatch.setattr(
        search,
        "_build_search_backend",
        lambda **_: SimpleNamespace(run_search=lambda **kw: calls.append(kw) or ordinary),
    )
    result = search.run_search(
        bundle=None,
        evaluator=None,
        bounds=[(-10, 10)] * dimensions,
        initial_probe_result=InitialProbeResult((original,), {}),
        config=replace(NomadConfig(max_bb_eval=1), seed_values=(0,)),
        allow_integer_shortcuts=False,
    )
    assert calls and result.candidates == (original,)


def test_float_rejected_square_root_remains_a_mathematical_completion_obligation():
    attempt = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    a, rejected = proposal(1, "integer_square_difference"), proposal(2, "integer_square_difference")
    first = outcome(attempt, (a,), (accepted(a),))
    stage = first.completed_stage_state
    stage = replace(stage, search_result=replace(stage.search_result, all_records=(a, rejected)))
    assert pipeline._algebraic_provenance_incomplete(stage)


def test_quadratic_seed_formula_keeps_representable_small_root_after_cancellation():
    points = _square_root_points((Fraction(4), Fraction(10**100), Fraction(1)), 0)
    assert points is not None and len(points) == 2
    assert all(point != 0 for point in points)
    assert points[0] * points[1] == pytest.approx(4)


def test_identically_zero_root_polynomial_is_not_a_finite_empty_set():
    assert _square_root_points((Fraction(9),), 9) is None
    assert _square_root_points((Fraction(9),), 4) == ()


@pytest.mark.parametrize(
    "polynomial",
    [
        (Fraction(1), Fraction(10**400)),
        (Fraction(1, 10**200), Fraction(10**200), Fraction(1)),
    ],
)
def test_nonzero_root_float_underflow_declines_finite_enumeration(polynomial):
    assert _square_root_points(polynomial, 0) is None


def test_rational_root_boxes_bind_distinct_irrational_roots_exactly():
    from geosolver.engine.standard.search.discrete.square_difference import _root_boxes

    roots = {-(2**0.5): 2, 2**0.5: 2}
    boxes = _root_boxes((Fraction(0), Fraction(0), Fraction(1)), roots)
    assert boxes is not None and len(boxes) == 2
    intervals = [(Fraction(box[0][0]), Fraction(box[0][1])) for box in boxes]
    assert intervals[0][1] < intervals[1][0]
    for lower, upper in intervals:
        assert (lower * lower - 2) * (upper * upper - 2) <= 0
    assert _root_boxes((Fraction(0), Fraction(0), Fraction(1)), {0.0: 2}) is None
