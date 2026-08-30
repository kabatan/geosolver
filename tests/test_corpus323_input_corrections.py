"""Source-based input repairs; these are not optimizer success-rate tests."""

from __future__ import annotations

import copy
import hashlib
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
REPAIR = ROOT / "benchmarks/repairs/corpus323-inputs-v1"
WITNESSES = json.loads((REPAIR / "witnesses.json").read_text())


def rows(path):
    return {row["id"]: row for row in map(json.loads, path.read_text().splitlines())}


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def evaluator(dsl):
    return build_ir_evaluator(
        load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    )


def point(dsl, identifier):
    assignments = WITNESSES[identifier]["assignments"]
    return tuple(mp.mpf(str(sp.N(sp.sympify(assignments[name]), 610))) for name in dsl["variables"])


def test_all_six_repairs_preserve_identity_and_record_exact_before_after_hashes():
    current = rows(ROOT / "benchmarks/cases.jsonl")
    before = rows(REPAIR / "before.jsonl")
    ledger = rows(REPAIR / "ledger.jsonl")
    assert len(current) == 323
    assert len(ledger) == 6
    assert set(before) == set(ledger) == set(WITNESSES)
    assert sum(entry["kind"] == "dsl" for entry in ledger.values()) == 5
    for identifier, entry in ledger.items():
        old, new = before[identifier], current[identifier]
        assert digest(old) == entry["before_sha256"]
        assert digest(new) == entry["after_sha256"]
        assert digest(old["dsl"]) == entry["dsl_before_sha256"]
        assert digest(new["dsl"]) == entry["dsl_after_sha256"]
        assert new["repair"]["dsl_after_sha256"] == digest(new["dsl"])
        assert old["answer"] == entry["reference_before"]
        assert (
            new["answer"] == entry["reference_after"] == WITNESSES[identifier]["expected_answers"]
        )
        assert entry["evidence"] and entry["reference_from_solver"] is False
        assert old["migration"] == new["migration"]
        assert old["dedupe_key"] == new["dedupe_key"]
        assert old["history_partition"] == new["history_partition"] == "development_touched"
        assert old["outcome_seen"] == new["outcome_seen"] is True
        path = ROOT / "benchmarks" / new["dsl_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["dsl_file_after_sha256"]
        assert json.loads(path.read_text()) == new["dsl"]
        assert new["authoring_status"] == "runnable"
        assert new["truth_status"] == "verified"


def test_only_the_diagnosed_mathematical_fields_change():
    before = rows(REPAIR / "before.jsonl")
    expected = {key: copy.deepcopy(row["dsl"]) for key, row in before.items()}
    expected["AIME-2018-II-12"]["conditions"][6]["operator"] = ">"
    expected["AIME-2021-I-13"]["constructions"][9]["expression"] = "Intersect(L, omega, n=1)"
    expected["HMMT-2022-FEB-GEO-05"]["target"] = "Distance(B, D) ** 2 + Distance(C, D) ** 2"
    for condition in expected["JMO-2013-PRE-08"]["conditions"][:4]:
        condition["right"] = condition["right"].replace("r + ", "r - ", 1)
    expected["JMO-2015-PRE-11"]["conditions"][2]["left"] = "Area(Ap, Bp, C)"
    current = rows(ROOT / "benchmarks/cases.jsonl")
    for identifier, dsl in expected.items():
        assert current[identifier]["dsl"] == dsl
    assert current["AIME-2020-I-15"]["answer"] == ["3*sqrt(55)"]
    ledger = rows(REPAIR / "ledger.jsonl")["AIME-2020-I-15"]
    assert ledger["dsl_file_before_sha256"] == ledger["dsl_file_after_sha256"]


@pytest.mark.parametrize("identifier", WITNESSES)
def test_independent_configuration_passes_all_conditions_and_exact_assembly(identifier):
    dsl = json.loads((ROOT / "benchmarks/dsl" / f"{identifier}.json").read_text())
    ev = evaluator(dsl)
    deadline = time.monotonic() + 20
    with mp.workdps(600), high_precision_mode(), runtime_session(deadline):
        values = point(dsl, identifier)
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
            refined_candidates=(candidate,),
            evaluator=ev,
            deadline_monotonic=deadline,
        )
        assert len(result.accepted_candidates) == 1, result.rejection_tags
        assert len(result.answer_values) == 1
        expected = sp.sympify(WITNESSES[identifier]["expected_answers"][0])
        assert sp.simplify(sp.sympify(result.answer_values[0]) - expected) == 0


def test_intersection_label_choice_does_not_remove_geometric_solutions():
    """Only P/Q labels change; their two incidence conditions and angle are symmetric."""
    identifier = "AIME-2021-I-13"
    dsl = json.loads((ROOT / "benchmarks/dsl" / f"{identifier}.json").read_text())
    for selection in (1, 2):
        dsl["constructions"][9]["expression"] = f"Intersect(L, omega, n={selection})"
        ev = evaluator(dsl)
        with mp.workdps(600), high_precision_mode():
            values = point(dsl, identifier)
            residual = ev.evaluate_hp_residual(values, precision=550)
            assert residual.is_finite and residual.residual_norm_hp < mp.mpf("1e-500")
            assert ev.evaluate_hp_hard_feasibility(values, precision=550).hard_feasible
            assert ev.evaluate_answer_hp(values, precision=550).answer_hp == 672


@pytest.mark.parametrize("identifier", ["AIME-2018-II-12", "JMO-2013-PRE-08", "JMO-2015-PRE-11"])
def test_previous_wrong_conditions_exclude_the_independent_configuration(identifier):
    old = rows(REPAIR / "before.jsonl")[identifier]["dsl"]
    ev = evaluator(old)
    with mp.workdps(600), high_precision_mode():
        values = point(old, identifier)
        residual = ev.evaluate_hp_residual(values, precision=550)
        hard = ev.evaluate_hp_hard_feasibility(values, precision=550)
        assert not hard.hard_feasible or residual.residual_norm_hp > mp.mpf("1e-5")


def test_previous_exponent_target_is_not_the_requested_sum_of_squares():
    identifier = "HMMT-2022-FEB-GEO-05"
    old = rows(REPAIR / "before.jsonl")[identifier]["dsl"]
    ev = evaluator(old)
    with mp.workdps(600), high_precision_mode():
        value = ev.evaluate_answer_hp(point(old, identifier), precision=550).answer_hp
        assert abs(value - mp.mpf(361) / 4) > 1


def test_correct_area_is_not_a_root_of_the_old_reference_polynomial():
    # Old reference was 5 times a root of 16*x^4-328*x^2+945.
    value = 3 * sp.sqrt(55) / 5
    assert sp.simplify(16 * value**4 - 328 * value**2 + 945) != 0
