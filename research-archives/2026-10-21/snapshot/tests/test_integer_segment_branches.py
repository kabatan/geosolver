"""Translated lattice trapezoids retain every independently enumerated slope."""

import math
import re
from fractions import Fraction

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.discrete.lattice_segments import (
    _integer_line,
    integer_segment_branches,
    scan_integer_segments,
)
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.problem.adapter import to_engine_document


def make_problem(vector, translation, representation):
    a, b = vector
    h, k = translation
    variables = ("t", "u", "v", "s") if representation else ("x", "y", "z", "w")
    x, y, z, w = variables
    conditions = [{"left": f"IsInteger({name})", "operator": "=", "right": 0} for name in variables]
    conditions += [
        {"predicate": "ConvexPolygon([P,Q,R,S])"},
        {"left": "Parallel(L,N)", "operator": "=", "right": 0},
        {"left": "Distance(P,S)", "operator": "=", "right": "Distance(Q,R)"},
    ]
    for left, right in [("L", "M"), ("L", "O"), ("N", "M"), ("N", "O"), ("M", "O")]:
        conditions.append({"left": f"Parallel({left},{right})", "operator": "!=", "right": 0})
    for left, right in [("P", "Q"), ("Q", "R"), ("R", "S")]:
        for coordinate in ("x", "y"):
            conditions.append(
                {"left": f"{left}.{coordinate}-{right}.{coordinate}", "operator": "!=", "right": 0}
            )
    if representation:
        conditions = list(reversed(conditions))
        for c in conditions:
            if c.get("operator") == "=" and c["right"] == 0:
                c["left"] = "-7*(" + c["left"] + ")"
        conditions.append({"left": "0", "operator": "=", "right": 0})
    result = {
        "id": "lattice-family",
        "variables": list(variables),
        "constructions": [
            {"name": "P", "expression": f"Point({h},{k})"},
            {"name": "S", "expression": f"Point({h + a},{k + b})"},
            {"name": "Q", "expression": f"Point({x},{y})"},
            {"name": "R", "expression": f"Point({z},{w})"},
            {"name": "L", "expression": "Line(P,Q)"},
            {"name": "M", "expression": "Line(Q,R)"},
            {"name": "N", "expression": "Line(R,S)"},
            {"name": "O", "expression": "Line(S,P)"},
        ],
        "conditions": conditions,
        "target": "(-7*Slope(Line(R,S))+0)/-7" if representation else "Slope(L)",
    }
    if representation:
        # Inline all distance and parallel operands, swap their orders, and
        # rename every geometry symbol independently of the free variables.
        for condition in result["conditions"]:
            if condition.get("left") == "Distance(P,S)":
                condition["left"] = f"Distance(Point({z},{w}),Point({x},{y}))"
                condition["right"] = f"Distance(Point({h + a},{k + b}),Point({h},{k}))"
            if condition.get("left") == "-7*(Parallel(L,N))":
                condition["left"] = "-7*(Parallel(Line(R,S),Line(Q,P)))"
        mapping = dict(
            zip(
                ("P", "Q", "R", "S", "L", "M", "N", "O"),
                ("E", "F", "G", "H", "U", "V", "W", "X"),
                strict=True,
            )
        )

        def rename(source):
            return re.sub(r"\b(?:P|Q|R|S|L|M|N|O)\b", lambda m: mapping[m.group()], source)

        for construction in result["constructions"]:
            construction["name"] = mapping[construction["name"]]
            construction["expression"] = rename(construction["expression"])
        for condition in result["conditions"]:
            for key in ("left", "right", "predicate"):
                if isinstance(condition.get(key), str):
                    condition[key] = rename(condition[key])
        result["target"] = rename(result["target"])
    return result


@pytest.mark.parametrize("vector", [(1, 7), (2, 9), (3, 8), (5, 11)])
@pytest.mark.parametrize("representation", [0, 1])
def test_integer_unit_witnesses_are_sound_under_translation_and_equation_units(
    vector, representation
):
    problem = make_problem(vector, (-17, 23) if representation else (3, -2), representation)
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    result = scan_integer_segments(
        bundle=bundle, evaluator=evaluator, config=NomadConfig(max_bb_eval=1000)
    )
    diagnostics = result.search_diagnostics["integer_segment_displacements"]
    assert diagnostics["all_displacements_covered"] == (
        diagnostics["admissible_count"] + diagnostics["excluded_displacement_count"]
        == diagnostics["displacement_count"]
    )
    actual = set()
    for candidate in result.candidates:
        verification = verify_final_candidate(
            evaluator=evaluator, values=tuple(mp.mpf(x) for x in candidate.x_float)
        )
        assert verification.verified
        actual.add(Fraction(str(verification.answer_hp)).limit_denominator(10000))
    # Independently exhaust all possible integer edge vectors; reject parallel,
    # vertical and horizontal sides as required by the generated construction.
    a, b = vector
    squared = a * a + b * b
    expected = set()
    radius = math.isqrt(squared)
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if dx * dx + dy * dy != squared or dx * dy == 0 or dx * b == dy * a:
                continue
            if a == dx or b == dy:
                continue
            expected.add(Fraction(b - dy, a - dx))
    assert actual <= expected
    if diagnostics["all_displacements_covered"]:
        assert actual == expected


@pytest.mark.parametrize(
    "origin,direction",
    [
        ((Fraction(1, 2), Fraction(0)), (Fraction(1), Fraction(0))),
        ((Fraction(0), Fraction(1, 2)), (Fraction(0), Fraction(1))),
        ((Fraction(1, 2), Fraction(0)), (Fraction(0), Fraction(1))),
    ],
)
def test_integer_line_distinguishes_inconsistent_rational_offsets(origin, direction):
    line = _integer_line(origin, direction)
    if direction[0] == 0 and origin[0].denominator != 1:
        assert line is None
    else:
        point, step = line
        assert all(isinstance(x, int) for x in point + step)


def test_noninvariant_target_does_not_skip_global_search():
    problem = make_problem((1, 7), (3, -2), 0)
    problem["target"] = "Distance(P,Q)"
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    assert integer_segment_branches(bundle) is None


def test_uncovered_parallelogram_family_keeps_baseline_candidates(monkeypatch):
    import importlib
    from dataclasses import replace
    from types import SimpleNamespace

    from geosolver.engine.standard.contracts.candidate_record import (
        FloatCandidate,
        SearchBatchResult,
    )
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
    from geosolver.engine.standard.search.discrete import lattice_segments

    module = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    problem = make_problem((1, 7), (3, -2), 0)
    # Allow BC parallel AD. Then displacement BC=AD is a parallelogram
    # family whose AB slope is unrestricted by the finite displacement.
    problem["conditions"] = [c for c in problem["conditions"] if c.get("left") != "Parallel(M,O)"]
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    point = (4.0, 15.0, 5.0, 22.0)  # parallelogram with AB slope 17
    assert verify_final_candidate(
        evaluator=evaluator, values=tuple(mp.mpf(x) for x in point)
    ).verified
    candidate = FloatCandidate(
        point, 0, 0, True, EvaluationStatus.OK, 0, 0, 123, hard_feasible=True
    )
    baseline = SearchBatchResult(
        candidates=(candidate,),
        all_records=(candidate,),
        guard_feasible_ledger=(candidate,),
        evaluation_count=1,
        failure_ratio=0,
    )
    calls = {"discrete": 0, "baseline": 0}
    real_scan = lattice_segments.scan_integer_segments

    def scan(**kwargs):
        calls["discrete"] += 1
        return real_scan(**kwargs)

    def backend(**kwargs):
        calls["baseline"] += 1
        return baseline

    monkeypatch.setattr(lattice_segments, "scan_integer_segments", scan)
    monkeypatch.setattr(
        module, "_build_search_backend", lambda **kwargs: SimpleNamespace(run_search=backend)
    )
    config = NomadConfig(max_bb_eval=1000)
    config = replace(config, seed_values=(0,))
    result = module._run_search_baseline(
        bundle=bundle,
        evaluator=evaluator,
        bounds=[(-100.0, 100.0)] * 4,
        initial_probe_result=InitialProbeResult((candidate,), {}),
        config=config,
    )
    assert candidate in result.candidates
    assert len(result.candidates) > 1
    assert calls == {"discrete": 1, "baseline": 1}
    assert not result.search_diagnostics["integer_segment_displacements"][
        "all_displacements_covered"
    ]
