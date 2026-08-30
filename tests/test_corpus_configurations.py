"""Check independent configurations against the current corpus and solver."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.deadline import runtime_session

ROOT = Path(__file__).resolve().parents[1]
WITNESSES = json.loads((ROOT / "tests/fixtures/independent-configurations.json").read_text())[
    "witnesses"
]
EVALUATION = [row for row in WITNESSES if "evaluation" in row["checks"]]
EXACT_ASSEMBLY = [row for row in WITNESSES if "exact_assembly" in row["checks"]]


def _dsl(identifier):
    return json.loads((ROOT / "benchmarks/dsl" / f"{identifier}.json").read_text())


def _evaluator(dsl):
    return build_ir_evaluator(
        load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    )


def _point(dsl, assignments, precision):
    return tuple(
        mp.mpf(str(sp.N(sp.sympify(assignments[name]), precision + 10)))
        for name in dsl["variables"]
    )


def test_configurations_match_current_variables_and_reference_answers():
    rows = {
        row["id"]: row
        for row in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())
    }
    for witness in WITNESSES:
        row = rows[witness["id"]]
        reference = row["answer"]
        if not isinstance(reference, list):
            reference = [str(reference)]
        assert witness["expected_answers"] == reference
        assert set(witness["assignments"]) == set(row["dsl"]["variables"])


@pytest.mark.parametrize("witness", EVALUATION, ids=[row["id"] for row in EVALUATION])
def test_independent_configuration_satisfies_conditions_and_target(witness):
    dsl = _dsl(witness["id"])
    with mp.workdps(120), high_precision_mode():
        point = _point(dsl, witness["assignments"], 120)
        ev = _evaluator(dsl)
        residual = ev.evaluate_hp_residual(point, precision=100)
        feasibility = ev.evaluate_hp_hard_feasibility(point, precision=100)
        answer = ev.evaluate_answer_hp(point, precision=100)
        references = [mp.mpf(str(sp.N(value, 120))) for value in witness["expected_answers"]]
        assert residual.is_finite and residual.residual_norm_hp < mp.mpf("1e-80")
        assert feasibility.hard_feasible, feasibility.failure_tags
        assert min(abs(answer.answer_hp - value) for value in references) < mp.mpf("1e-80")


@pytest.mark.parametrize("witness", EXACT_ASSEMBLY, ids=[row["id"] for row in EXACT_ASSEMBLY])
def test_independent_configuration_passes_exact_assembly(witness):
    dsl = _dsl(witness["id"])
    ev = _evaluator(dsl)
    deadline = time.monotonic() + 20
    with mp.workdps(600), high_precision_mode(), runtime_session(deadline):
        values = _point(dsl, witness["assignments"], 600)
        residual = ev.evaluate_hp_residual(values, precision=550)
        hard = ev.evaluate_hp_hard_feasibility(values, precision=550)
        answer = ev.evaluate_answer_hp(values, precision=550)
        assert residual.is_finite and residual.residual_norm_hp < mp.mpf("1e-500")
        assert hard.hard_feasible, hard.failure_tags
        candidate = RefinedCandidate(
            values,
            residual.residual_norm_hp,
            answer.answer_hp,
            "direct_evaluation",
            (),
            candidate_id=0,
            coordinate_precision_dps=600,
            answer_precision_dps=600,
        )
        result = assemble_exact_results(
            refined_candidates=(candidate,), evaluator=ev, deadline_monotonic=deadline
        )
        assert len(result.accepted_candidates) == 1, result.rejection_tags
        assert len(result.answer_values) == 1
        expected = sp.sympify(witness["expected_answers"][0])
        assert sp.simplify(sp.sympify(result.answer_values[0]) - expected) == 0


def test_intersection_label_choice_preserves_geometric_solutions():
    """P/Q incidence and angle conditions are symmetric in this configuration."""
    identifier = "AIME-2021-I-13"
    witness = next(row for row in EXACT_ASSEMBLY if row["id"] == identifier)
    dsl = _dsl(identifier)
    for selection in (1, 2):
        dsl["constructions"][9]["expression"] = f"Intersect(L, omega, n={selection})"
        ev = _evaluator(dsl)
        with mp.workdps(600), high_precision_mode():
            values = _point(dsl, witness["assignments"], 600)
            residual = ev.evaluate_hp_residual(values, precision=550)
            assert residual.is_finite and residual.residual_norm_hp < mp.mpf("1e-500")
            assert ev.evaluate_hp_hard_feasibility(values, precision=550).hard_feasible
            assert ev.evaluate_answer_hp(values, precision=550).answer_hp == 672
