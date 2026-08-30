"""Corpus authoring regressions, not optimizer success tests."""

from __future__ import annotations

import json
from collections import Counter

import pytest
import sympy as sp
from mpmath import mp

from benchmarks.repairs.corpus97.audit26_mathematics import (
    hmmt_2013_angle_obstruction,
    hmmt_2013_published_configuration,
)
from benchmarks.repairs.corpus97.evidence import ledger_rows
from benchmarks.repairs.corpus97.independent_checks import (
    hmmt_2011_collinear_branches,
    hmmt_2022_rectangle_union,
    jmo_2008_quad,
    jmo_2010_triangle,
)
from benchmarks.repairs.corpus97.records import (
    BEFORE,
    CASES,
    HERE,
    digest,
    removed_rows,
    repaired_rows,
    validate,
)
from benchmarks.repairs.corpus97.witnesses import BRANCH_WITNESSES, WITNESSES, check_witness

ROWS = repaired_rows()
HISTORICAL_ROWS = repaired_rows(include_removed=True)
FIXTURES = [
    (key, row["dsl"], WITNESSES.get(key, {}))
    for key, row in ROWS.items()
    if key in WITNESSES or not row["dsl"]["variables"]
]
FIXTURES += [
    (key, HISTORICAL_ROWS[key]["dsl"], point)
    for key, points in BRANCH_WITNESSES.items()
    for point in points
]


def test_every_original_record_is_repaired_or_explicitly_archived():
    before = [json.loads(line) for line in BEFORE.read_text().splitlines()]
    assert Counter(r["authoring_status"] for r in before) == {
        "runnable": 79,
        "reference_only": 17,
        "migration_blocked": 1,
    }
    removed = removed_rows()
    removed_from_original = {key: row for key, row in removed.items() if key in HISTORICAL_ROWS}
    assert set(removed_from_original) == {
        "HMMT-2013-FEB-GEO-09",
        "HMMT-2011-regular-hexagon",
        "HMMT-2011-square",
        "HMMT-2011-collinear-circumcircle",
    }
    assert len(ROWS) == 93
    assert set(ROWS).isdisjoint(removed)
    assert set(ROWS) | set(removed_from_original) == {r["id"] for r in before}
    assert Counter(row["truth_status"] for row in ROWS.values()) == {
        "verified": 93,
    }
    validate(ROWS)
    current = {r["id"]: r for r in map(json.loads, CASES.read_text().splitlines())}
    for old in before:
        if old["id"] in removed:
            assert old["id"] not in current
            assert not (CASES.parent / removed[old["id"]]["dsl_path"]).exists()
            continue
        row = ROWS[old["id"]]
        assert row == current[old["id"]]
        assert row["authoring_status"] == "runnable"
        assert row["truth_status"] == "verified"
        assert row["answer"]
        assert all(sp.sympify(value).is_real is True for value in row["answer"])
        assert row["repair"]["before_sha256"] == digest(old)
        assert row["migration"] == old["migration"]
        assert row["dedupe_key"] == old["dedupe_key"]
        assert json.loads((CASES.parent / row["dsl_path"]).read_text()) == row["dsl"]
    historical = repaired_rows(include_removed=True)
    assert historical == ROWS | removed_from_original
    ledger = ledger_rows(before, historical)
    assert ledger == list(map(json.loads, (HERE / "repair-ledger.jsonl").read_text().splitlines()))
    assert all(not row["reference_from_solver"] and row["evidence"] for row in ledger)


@pytest.mark.parametrize("identifier,dsl,assignments", FIXTURES, ids=[r[0] for r in FIXTURES])
def test_independently_derived_positive_configuration(identifier, dsl, assignments):
    residual, feasible, answer, references = check_witness(identifier, dsl, assignments)
    with mp.workdps(120):
        assert residual.is_finite and residual.residual_norm_hp < mp.mpf("1e-80")
        assert feasible.hard_feasible, feasible.failure_tags
        assert min(abs(answer.answer_hp - value) for value in references) < mp.mpf("1e-80")


def test_two_collinear_branches_not_filtered_to_official_single_answer():
    assert hmmt_2011_collinear_branches() == [7, sp.Rational(35, 11)]
    for identifier in BRANCH_WITNESSES:
        assert HISTORICAL_ROWS[identifier]["answer"] == ["7", "35/11"]
    assert ROWS["HMMT-2011-FEB-ALGGEO-18"]["answer"] == ["7", "35/11"]


def test_hmmt_2013_source_obstruction_preserves_removed_record_for_audit():
    proof = hmmt_2013_angle_obstruction()
    assert proof["bd_over_ad"] == sp.sqrt(5) / 3
    assert (proof["pb"], proof["pd"], proof["bd_squared"]) == (5, 7, 39)
    assert proof["cosine_dba"] ** 2 == sp.Rational(1, 10)
    assert proof["cosine_dbp"] ** 2 == sp.Rational(3, 52)
    assert proof["cosine_squared_gap"] == sp.Rational(11, 260)
    assert len(hmmt_2013_published_configuration()) == 2
    assert "HMMT-2013-FEB-GEO-09" not in ROWS
    row = removed_rows()["HMMT-2013-FEB-GEO-09"]
    assert row["truth_status"] == "quarantined"
    assert row["answer"] == ["sqrt(39)"]  # Retained publication, not a verified reference.
    assert row["repair"]["dsl_after_sha256"] == (
        "e7e6730e68e0ee2db70bdf96d169d4e8f9aa0273d53e63fae5de153b272deafc"
    )
    assert {
        "left": "Angle(B,C,D)+Angle(D,E,A)",
        "operator": "=",
        "right": "5*pi/3",
    } in row["dsl"]["conditions"]


def test_rectangle_union_against_full_exact_inclusion_exclusion():
    assert hmmt_2022_rectangle_union() == 30


def test_independent_convexity_and_interior_branch_checks():
    assert jmo_2008_quad() == [2 + 4 * sp.sqrt(2)]
    assert jmo_2010_triangle() == [3 + 7 * sp.sqrt(3) / 2]


def test_original_broken_encodings_fail_positive_witnesses():
    before = {r["id"]: r for r in map(json.loads, BEFORE.read_text().splitlines())}
    for identifier in ["JMO-2017-PRE-04", "HMMT-2020-FEB-GEO-06"]:
        residual, feasible, answer, references = check_witness(
            identifier, before[identifier]["dsl"], WITNESSES[identifier]
        )
        assert (
            not feasible.hard_feasible
            or residual.residual_norm_hp > mp.mpf("1e-20")
            or min(abs(answer.answer_hp - value) for value in references) > mp.mpf("1e-20")
        )
