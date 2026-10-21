"""Scale chart contracts and numerical regressions."""

import re
from fractions import Fraction

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.positive_scale_chart import positive_scale_chart
from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from geosolver.geometry.entities import Point
from geosolver.geometry.operations.basic import AreConcyclic, OnLine
from geosolver.problem.adapter import to_engine_document
from tests.helpers.capabilities import requires_cpu_timer


def family(names=("a", "b", "c")):
    definitions = (
        ("A", "Point(a,0)"),
        ("B", "Point(b,b)"),
        ("C", "Point(c,2*c)"),
        ("D", "Point(a,a)"),
        ("L", "Line(Point(0,0),Point(1,1))"),
        ("M", "Line(Point(0,0),Point(1,2))"),
        ("G", "Circumcircle(A,D,C)"),
        ("E", "Intersect(G,L,exclude=D)"),
        ("F", "Intersect(Line(A,E),M)"),
    )
    equations = (("Collinear(A,B,C)", "0"), ("Distance(A,B)", "2*Distance(B,C)"))
    guards = ("AssumeGt(a,0)", "AssumeGt(Dot(Vector(A,E),Vector(A,F)),0)")
    answer = "Distance(A,E)/Distance(E,F)"
    rename = dict(zip(("a", "b", "c"), names, strict=True))

    def change(source):
        return re.sub(r"\b(a|b|c)\b", lambda m: rename[m[0]], source)

    return (
        names,
        tuple((n, change(e)) for n, e in definitions),
        tuple((change(a), change(b)) for a, b in equations),
        tuple(map(change, guards)),
        change(answer),
    )


@requires_cpu_timer
@pytest.mark.parametrize("names", [("a", "b", "c"), ("u", "v", "w")])
@pytest.mark.parametrize("scale", [1, 3, 11])
def test_origin_reference_lines_and_excluded_circle_contact_have_all_scale_orbits(names, scale):
    variables, definitions, equalities, guards, answer = family(names)
    # Positive changes of equation units must not affect the proof or branches.
    equalities = tuple((f"{scale}*({a})", f"{scale}*({b})") for a, b in equalities)
    assert positive_scale_chart(variables, definitions, equalities, guards, answer) == names[0]
    payload = {
        "variables": variables,
        "construction": definitions,
        "constraints": [a for a, _ in equalities] + [names[0]],
        "targets": [b for _, b in equalities] + ["1"],
        "guards": guards,
    }
    data = discover_polynomial_branches(payload)
    assert data is not None and len(data["points"]) == 2
    problem = {
        "id": "scaled-intersection-family",
        "variables": list(variables),
        "constructions": [{"name": n, "expression": e} for n, e in definitions],
        "conditions": [{"left": a, "operator": "=", "right": b} for a, b in equalities]
        + [
            {"left": names[0], "operator": ">", "right": "0"},
            {"left": "Dot(Vector(A,E),Vector(A,F))", "operator": ">", "right": "0"},
        ],
        "target": answer,
    }
    evaluator = build_ir_evaluator(
        load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    )
    with mp.workdps(180):
        answers = set()
        for point in data["points"]:
            values = tuple(mp.mpf(x) * scale for x in point)
            result = verify_final_candidate(evaluator=evaluator, values=values)
            assert result.verified
            answers.add(mp.nstr(result.answer_hp, 60))
        assert answers == {mp.nstr(mp.mpf(7), 60), mp.nstr(mp.mpf(35) / 11, 60)}


@pytest.mark.parametrize(
    "change",
    [
        "length_target",
        "nonzero_bound",
        "fixed_center",
        "integer",
        "angle_variable",
        "mixed_coordinates",
        "no_positive_variable",
        "moving_selector",
    ],
)
def test_scale_chart_declines_unproved_or_noninvariant_models(change):
    variables, definitions, equalities, guards, answer = family()
    if change == "length_target":
        answer = "Distance(A,E)"
    elif change == "nonzero_bound":
        guards += ("AssumeLt(a,5)",)
    elif change == "fixed_center":
        definitions += (("bad", "Circle(Point(1,0),a)"),)
    elif change == "integer":
        equalities += (("IsInteger(a)", "0"),)
    elif change == "angle_variable":
        definitions += (("bad", "Point(cos(a),sin(a))"),)
    elif change == "mixed_coordinates":
        definitions += (("bad", "Point(a,a*a)"),)
    elif change == "no_positive_variable":
        guards = guards[1:]
    elif change == "moving_selector":
        definitions = tuple(
            (n, "Intersect(G,L,exclude=Point(1,1))") if n == "E" else (n, e) for n, e in definitions
        )
    assert positive_scale_chart(variables, definitions, equalities, guards, answer) is None


@pytest.mark.parametrize("coefficient", ["0.5", "1", "1.5"])
@pytest.mark.parametrize("renamed", [False, True])
def test_positive_circle_ratio_family_retains_all_proper_shape_branches(
    coefficient, renamed, monkeypatch
):
    from contextlib import nullcontext

    from geosolver.engine.standard.search import algebraic_branches

    # This checks the exact branch implication, independently of machine load
    # and the optional production work allowance. CPU and wall deadline
    # behavior is exercised separately in test_algebraic_work_telemetry.py.
    monkeypatch.setattr(algebraic_branches, "_bounded_symbolic_work", lambda _: nullcontext(True))
    names = ("u", "v", "s", "t", "q") if renamed else ("r", "R", "x", "y", "b")
    r, bigr, x, y, b = names
    definitions = (
        ("O", "Point(0,0)"),
        ("P", f"Point({coefficient}*{r},0)"),
        ("A", f"Point({x},{y})"),
        ("B", f"Point({b},0)"),
        ("G", f"Circle(O,{r})"),
        ("H", f"Circle(P,{bigr})"),
    )
    equalities = (
        ("Distance(O,A)", r),
        ("Distance(P,A)", bigr),
        ("Distance(P,B)", bigr),
        ("Distance(A,B)", r),
    )
    guards = (
        f"AssumeGt({r},0)",
        f"AssumeGt({bigr},0)",
        f"AssumeGt({y},0)",
        "AssumeNe(Distance(B,O),0)",
    )
    answer = f"{r}/{bigr}"
    assert positive_scale_chart(names, definitions, equalities, guards, answer) == r
    data = discover_polynomial_branches(
        {
            "variables": names,
            "construction": definitions,
            "constraints": [a for a, _ in equalities] + [r],
            "targets": [b for _, b in equalities] + ["1"],
            "guards": guards,
        }
    )
    assert data is not None
    problem = {
        "id": "homogeneous-circle-ratio-family",
        "variables": list(names),
        "constructions": [{"name": n, "expression": e} for n, e in definitions],
        "conditions": [{"left": a, "operator": "=", "right": b} for a, b in equalities]
        + [
            {"left": r, "operator": ">", "right": "0"},
            {"left": bigr, "operator": ">", "right": "0"},
            {"left": y, "operator": ">", "right": "0"},
            {"left": "Distance(B,O)", "operator": "!=", "right": "0"},
        ],
        "target": answer,
    }
    evaluator = build_ir_evaluator(
        load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    )
    with mp.workdps(180):
        actual = []
        for point in data["points"]:
            result = verify_final_candidate(
                evaluator=evaluator, values=tuple(mp.mpf(x) for x in point)
            )
            if result.verified:
                actual.append(result.answer_hp)
        h = mp.mpf(coefficient)
        expected = []
        for sign in (-1, 1):
            ratio = (mp.sqrt(h * h + 4) + sign * h) / 2
            # A=(b/2,+sqrt(1-b*b/4)); strict Ay>0 excludes b=2.
            b_coordinate = h + sign / ratio
            if abs(b_coordinate) < 2:
                expected.append(ratio)
        expected.sort()
        assert len(actual) == len(expected)
        assert all(
            abs(a - b) < mp.mpf("1e-150") for a, b in zip(sorted(actual), expected, strict=True)
        )


@pytest.mark.parametrize("change", ["tiny_bound", "tiny_fixed_point", "near_one_exponent"])
def test_exact_decimal_tokens_cannot_turn_a_noninvariant_model_into_a_scale_chart(change):
    variables, definitions, equalities, guards, answer = family()
    if change == "tiny_bound":
        guards += ("AssumeLt(a,1e-400)",)
    elif change == "tiny_fixed_point":
        definitions += (("bad", "Line(Point(1e-400,0),Point(a,0))"),)
    else:
        definitions += (("bad", "Point(a,a**1.00000000000000000000001)"),)
    assert positive_scale_chart(variables, definitions, equalities, guards, answer) is None


@pytest.mark.parametrize("has_chart", [False, True])
def test_optional_chart_keeps_every_ordinary_candidate_and_runs_backend_once(
    monkeypatch, has_chart
):
    import importlib

    from geosolver.engine.standard.contracts.candidate_record import (
        FloatCandidate,
        SearchBatchResult,
    )
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.search import finite_guard_search, scale_chart
    from geosolver.engine.standard.search.nomad_config import NomadConfig

    module = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    original = FloatCandidate((1.0,), 0, 0, True, EvaluationStatus.OK, 0, 0, 42)
    proposal = FloatCandidate((1.0,), 0, 0, True, EvaluationStatus.OK, -1, 0, 910000)
    baseline = SearchBatchResult(
        candidates=(original,),
        all_records=(original,),
        evaluation_count=1,
        failure_ratio=0,
        evaluation_failure_count=0,
    )
    chart = (
        SearchBatchResult(
            candidates=(proposal,),
            all_records=(proposal,),
            evaluation_count=1,
            failure_ratio=0,
            evaluation_failure_count=0,
        )
        if has_chart
        else None
    )
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return baseline

    monkeypatch.setattr(module, "_run_search_baseline", backend)
    monkeypatch.setattr(finite_guard_search, "search_finite_guards", lambda **kwargs: None)
    monkeypatch.setattr(scale_chart, "search_positive_scale_chart", lambda **kwargs: chart)
    result = module.run_search(
        bundle=None,
        evaluator=None,
        bounds=[(0.0, 2.0)],
        initial_probe_result=None,
        config=NomadConfig(max_bb_eval=1),
    )
    assert len(calls) == 1
    assert result.candidates[-1] is original
    assert result.all_records[-1] is original
    assert len(result.candidates) == (2 if has_chart else 1)


def test_scale_variable_is_exactly_substituted_without_mutating_the_original_bundle(monkeypatch):
    from geosolver.engine.standard.search import scale_chart

    variables, definitions, equalities, _guards, answer = family()
    problem = {
        "id": "chart-alias-family",
        "variables": list(variables),
        "constructions": [{"name": n, "expression": e} for n, e in definitions],
        "conditions": [{"left": a, "operator": "=", "right": b} for a, b in equalities]
        + [{"left": "a", "operator": ">", "right": "0"}],
        "target": answer,
    }
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    original_constraints = tuple(bundle.spec.constraints)
    original_definitions = tuple((x.name, x.expr) for x in bundle.spec.construction)
    calls = []

    def worker(operation, payload, **kwargs):
        calls.append((operation, payload))
        return {
            "points": [["-2", "-0.5"], ["0.6666666666666666666666666666666666666667", "0.5"]],
            "method": "test",
        }

    monkeypatch.setattr(scale_chart, "request", worker)
    result = scale_chart.search_positive_scale_chart(
        bundle=bundle, evaluator=build_ir_evaluator(bundle)
    )
    assert result is not None and len(result.candidates) == 2
    assert calls[0][1]["variables"] == ["b", "c"]
    assert calls[0][1]["construction"][-1] == ("a", "1")
    assert tuple(calls[0][1]["constraints"]) == original_constraints
    assert tuple(bundle.spec.constraints) == original_constraints
    assert tuple((x.name, x.expr) for x in bundle.spec.construction) == original_definitions
    assert all(c.initial_point_decimal[0] == "1" for c in result.candidates)


POINTS = (("O", "Point(0,0)"), ("A", "Point(x,0)"), ("B", "Point(0,x)"))


def chart(definitions=POINTS, equations=(), answer="x/x"):
    return positive_scale_chart(("x",), definitions, equations, ("AssumeGt(x,0)",), answer)


def test_three_point_on_line_is_quadratic_not_linear():
    # OnLine(O,A,B)=x^2. x^2=x selects x=1; scaling by two breaks it.
    assert OnLine(Point(0, 0), Point(1, 0), Point(0, 1)) == 1
    assert OnLine(Point(0, 0), Point(2, 0), Point(0, 2)) == 4
    assert chart(equations=(("OnLine(O,A,B)", "x"),)) is None


def test_concyclic_residual_is_distance_not_a_degree_four_determinant():
    definitions = POINTS + (("D", "Point(x/2,0)"),)
    value = AreConcyclic(Point(0, 0), Point(1, 0), Point(0, 1), Point(Fraction(1, 2), 0))
    scaled = AreConcyclic(Point(0, 0), Point(2, 0), Point(0, 2), Point(1, 0))
    assert scaled == 2 * value
    assert chart(definitions, (("AreConcyclic(O,A,B,D)", "-x**4"),)) is None


@pytest.mark.parametrize("selector", ["Point(1,0)", "Point(0,x)", "3", "x/x"])
def test_contact_selector_domain_must_be_proved_scale_equivariant(selector):
    definitions = POINTS + (("T", f"IncircleContactPoint(A,B,O,{selector})"),)
    # A fixed vertex selector matches only x=1. Conservative proof supports
    # only the discrete scalar selectors 0/1/2, never arbitrary geometric data.
    assert chart(definitions) is None


@pytest.mark.parametrize("selector", ["0", "1", "2", "1.0000000000000000000000000000000000000001"])
def test_contact_selector_uses_exact_discrete_scalar_values(selector):
    definitions = POINTS + (("T", f"IncircleContactPoint(A,B,O,{selector})"),)
    assert chart(definitions) == ("x" if selector in {"0", "1", "2"} else None)


@pytest.mark.parametrize(
    "expression,power",
    [
        ("Area(O,A,B)", 2),
        ("Collinear(O,A,B)", 2),
        ("OnLine(O,A,B)", 2),
        ("OnLine(B,Line(O,A))", 1),
        ("OnSegment(O,A,B)", 1),
        ("AreConcyclic(O,A,B,Point(x/2,0))", 1),
        ("OnCircle(A,Circle(O,x))", 1),
        ("IsTangent(Line(O,A),Circle(B,x))", 1),
        ("Dot(Vector(O,A),Vector(O,B))", 2),
    ],
)
def test_supported_geometric_residuals_have_their_implemented_degree(expression, power):
    assert chart(answer=f"({expression})/(x**{power})") == "x"


@pytest.mark.parametrize("expression", ["Angle(A,O,B)", "Perimeter(O,A,B)", "Area(Circle(O,x))"])
def test_unimplemented_typed_proofs_decline_instead_of_guessing(expression):
    assert chart(answer=f"({expression})/x") is None


@pytest.mark.parametrize(
    "definition",
    [
        "Point(x,1e-400)",
        "Circle(Point(x,0),1e-400)",
        "Line(Point(1e-400,0),Point(x,x))",
        "Point(x,x**1.0000000000000000000000000000000000000001)",
    ],
)
def test_extreme_nonzero_literals_are_never_polymorphic_zero(definition):
    assert chart(POINTS + (("bad", definition),)) is None


@pytest.mark.parametrize(
    "source",
    [
        "0/(x-1)",
        "0*sqrt(1-x)",
        "0*Distance(Point(x,0),Point(1,0))",
    ],
)
def test_zero_prefactors_never_erase_non_equivariant_domains(source):
    assert chart(answer=f"({source})+x/x") is None
