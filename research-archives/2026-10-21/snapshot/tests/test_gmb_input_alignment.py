"""Input-source checks and synthetic geometry only; no natural-case optimization."""

from __future__ import annotations

import copy
import importlib
import itertools
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    alignment = importlib.import_module("benchmarks.gmb_comparison.alignment")
    checker = importlib.import_module("benchmarks.gmb_comparison.checker")
    prepare = importlib.import_module("benchmarks.gmb_comparison.prepare")
    sources = importlib.import_module("benchmarks.gmb_comparison.sources")
finally:
    sys.path.pop(0)

ROOT = sources.HERE
ADJUSTMENTS = json.loads((ROOT / "input-adjustments.json").read_text(encoding="utf-8"))["variants"]


def data(points):
    return {"points": points, "lines": {}, "circles": {}, "choices": {}}


def official_row(case_id):
    if not sources.DEFAULT_UPSTREAM.is_dir():
        pytest.skip("Pinned GMB checkout is not installed")
    manifest = prepare.read_json(ROOT / "source-manifest.json")
    entry = next(item for item in manifest["inputs"] if item["case_id"] == case_id)
    row = prepare.inspect_case(
        ROOT,
        entry,
        manifest["statements"][str(entry["year"])],
        sources.DEFAULT_UPSTREAM,
        manifest["supplementary_statements"],
    )
    return entry, row


def test_declared_repair_cannot_change_existing_commands_or_add_goals():
    original = "(param A point) (eval (= 1 1))"
    addition = "(assert (> 2 1))"
    selected = f"(param A point) {addition} (eval (= 1 1))"
    assert alignment.additions_only(original, selected, [addition])
    assert not alignment.additions_only(
        original, selected.replace("param A", "param B"), [addition]
    )
    assert not alignment.additions_only(original, selected.replace("= 1 1", "= 1 2"), [addition])
    assert not alignment.additions_only(original, selected + "(assert (< 2 3))", [addition])
    assert not alignment.additions_only(original, selected, ["(eval (= 2 2))"])


@pytest.mark.parametrize("case_id", list(ADJUSTMENTS))
def test_selected_inputs_are_reviewed_additive_repairs_and_keep_official_history(case_id):
    entry, row = official_row(case_id)
    assert set(row["issues"]) == alignment.SOURCE_OMISSION_ISSUES
    previous = copy.deepcopy(row)
    alignment.select_comparison_input(
        ROOT, entry, sources.DEFAULT_UPSTREAM, row, ADJUSTMENTS[case_id]
    )
    assert row["issues"] == []
    assert row["independently_reviewed"]
    assert row["original_assumptions_covered"]
    assert row["comparison_input"]["origin"] == alignment.PROFILE
    assert row["official_pairing"]["issues"] == previous["issues"]
    assert row["official_pairing"]["source_differences"] == previous["source_differences"]
    assert not row["official_pairing"]["original_assumptions_covered"]


def test_valid_alignment_cannot_waive_an_unrelated_problem_error():
    case_id = "IMO_2000_P1"
    entry, row = official_row(case_id)
    row["issues"].append("invalid_dsl")
    alignment.select_comparison_input(
        ROOT, entry, sources.DEFAULT_UPSTREAM, row, ADJUSTMENTS[case_id]
    )
    assert row["issues"] == ["invalid_dsl"]


@pytest.mark.parametrize("tamper", ["input", "review", "scope", "case_hash", "malformed"])
def test_changed_or_unreviewed_alignment_is_not_approved(tmp_path, tamper):
    case_id = "IMO_2000_P1"
    entry, row = official_row(case_id)
    adjustment = copy.deepcopy(ADJUSTMENTS[case_id])
    for key in ("comparison_relative_path", "review_relative_path"):
        target = tmp_path / adjustment[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / adjustment[key]).read_bytes())
    if tamper == "input":
        path = tmp_path / adjustment["comparison_relative_path"]
        path.write_text(path.read_text() + "\n(assert (> 4 3))\n", encoding="utf-8")
    elif tamper == "review":
        path = tmp_path / adjustment["review_relative_path"]
        content = json.loads(path.read_text())
        content["conclusion_not_added"] = False
        path.write_text(json.dumps(content), encoding="utf-8")
    elif tamper == "scope":
        adjustment["resolved_source_difference_ids"] = ["unrelated"]
    elif tamper == "case_hash":
        row["case_sha256"] = "changed-after-review"
    else:
        (tmp_path / adjustment["comparison_relative_path"]).write_text("(invalid", encoding="utf-8")
    alignment.select_comparison_input(tmp_path, entry, sources.DEFAULT_UPSTREAM, row, adjustment)
    assert row["issues"]
    assert not row["independently_reviewed"]
    assert not row["original_assumptions_covered"]


def test_comparison_paths_cannot_escape_the_preparation_directory(tmp_path):
    with pytest.raises(ValueError):
        alignment.local_path(tmp_path, "../other-input.smt2")
    with pytest.raises(ValueError):
        alignment.local_path(tmp_path, str(tmp_path / "absolute.smt2"))


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("n_height,expected", [("3", True), ("0.5", False), ("1", False)])
def test_added_tangent_distance_condition_with_synthetic_coordinates(mirror, n_height, expected):
    source = "\n".join(
        [f"(param {name} point)" for name in ("A", "B", "M", "N")]
        + ADJUSTMENTS["IMO_2000_P1"]["added_assertions"]
    )
    points = {"A": [0, 0], "B": [2, 0], "M": [1, "1"], "N": [1, n_height]}
    if mirror:
        points = {name: [x, str(-Decimal(y))] for name, (x, y) in points.items()}
    assert checker.check_configuration(source, data(points))["valid"] is expected


@pytest.mark.parametrize("mirror", [False, True])
def test_added_circle_order_matches_all_label_permutations_and_rejects_duplicates(mirror):
    # Known counterclockwise points on the unit circle; this is not an IMO configuration.
    points = [("1", "0"), ("0.6", "0.8"), ("-0.6", "0.8"), ("-1", "0"), ("0", "-1")]
    if mirror:
        points = [(x, str(-Decimal(y))) for x, y in points]
    names = ("A", "B", "C", "K", "Q")
    source = "\n".join(
        ["(param (A B C) triangle)", "(param K point)", "(param Q point)"]
        + ADJUSTMENTS["IMO_2015_P3"]["added_assertions"]
    )
    rotations = {
        tuple((start + direction * i) % 5 for i in range(5))
        for start in range(5)
        for direction in (-1, 1)
    }
    for permutation in itertools.permutations(range(5)):
        witness = data({name: points[i] for name, i in zip(names, permutation, strict=True)})
        assert checker.check_configuration(source, witness)["valid"] == (permutation in rotations)
    for first, second in itertools.combinations(names, 2):
        witness = data(dict(zip(names, points, strict=True)))
        witness["points"][second] = witness["points"][first]
        assert not checker.check_configuration(source, witness)["valid"]


def test_all_36_are_ready_under_the_explicit_profile_without_unlocking_execution():
    if not sources.DEFAULT_UPSTREAM.is_dir():
        pytest.skip("Pinned GMB checkout is not installed")
    report = prepare.preflight()
    assert report["global_issues"] == []
    assert report["input_ready_count"] == 36
    assert report["official_input_count"] == 34
    assert report["original_aligned_input_count"] == 2
    assert report["all_inputs_ready"]
    assert not report["execution_unlocked"]
