"""Seed scheduling and repeated-study aggregation; no IMO solver runs in tests."""

from __future__ import annotations

import copy
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    replication = importlib.import_module("benchmarks.gmb.replication")
finally:
    sys.path.pop(0)


@pytest.mark.parametrize("seeds", [[], [0], [1, 1], [-1], [True], [2**32]])
def test_repeated_or_invalid_seeds_are_rejected(seeds):
    with pytest.raises(ValueError):
        replication.check_seeds(seeds, [0])


def test_new_seeds_are_allowed():
    replication.check_seeds([1, 2], [0])


def conditions():
    return dict.fromkeys(replication.SAME_CONDITIONS) | {
        "seeds": [0],
        "identity_files": {"worker.py": "hash"},
        "runtime_identity": {"cpu": [4], "tensorflow": "2.7.4"},
    }


def test_measurement_code_and_options_must_match():
    baseline = conditions()
    repeated = copy.deepcopy(baseline)
    repeated["seeds"] = [1, 2]
    repeated["identity_files"]["replication.py"] = "new-driver"
    replication.check_same_conditions(baseline, repeated)
    repeated["options"] = {"eps": 0.1}
    with pytest.raises(ValueError, match="options"):
        replication.check_same_conditions(baseline, repeated)
    repeated["options"] = baseline["options"]
    repeated["identity_files"]["worker.py"] = "different"
    with pytest.raises(ValueError, match="implementation changed"):
        replication.check_same_conditions(baseline, repeated)


def example_rows():
    return [
        {
            "case_id": case_id,
            "seed": seed,
            "availability": "public_input",
            "outcome": "model_returned" if success else "no_model",
            "all_goals_passed": goals,
            "wall_seconds": 3.0,
            "cpu_seconds": 2.5,
            "peak_rss_bytes": 100,
        }
        for case_id, seed, success, goals in [
            ("a", 0, True, True),
            ("b", 0, True, False),
            ("a", 1, True, True),
            ("b", 1, False, None),
        ]
    ]


def test_macro_and_pooled_goal_rates_are_distinct():
    result, cases = replication.statistics_from_rows(example_rows())
    assert result["macro_model_rate"] == 0.75
    assert result["macro_goal_rate"] == 0.75
    assert result["pooled_goal_rate"] == pytest.approx(2 / 3)
    assert result["cases_succeeding_in_any_seed"] == 2
    assert result["cases_succeeding_in_every_seed"] == 1
    assert result["model_returned_count_histogram"] == {"1": 1, "2": 1}
    assert cases[1]["seed1_outcome"] == "no_model"


def test_incomplete_and_duplicate_matrices_are_rejected():
    rows = example_rows()
    with pytest.raises(ValueError, match="incomplete"):
        replication.statistics_from_rows(rows[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        replication.statistics_from_rows(rows + [rows[0]])


def test_unsupported_is_not_counted_as_a_failed_execution():
    rows = example_rows() + [
        {
            "case_id": "missing",
            "seed": seed,
            "availability": "unsupported",
            "outcome": "unsupported",
        }
        for seed in [0, 1]
    ]
    result, _ = replication.statistics_from_rows(rows)
    assert result["unique_cases_including_unsupported"] == 3
    assert result["unique_executable_cases"] == 2
    assert result["executed_runs"] == 4
    assert result["pooled_model_rate"] == 0.75


def test_timeout_is_not_success_even_if_partial_goal_diagnostics_exist():
    rows = example_rows()
    rows[2]["outcome"] = "timeout"
    result, _ = replication.statistics_from_rows(rows)
    assert result["per_seed"][1]["model_returned"] == 0
    assert result["per_seed"][1]["goal_rate"] is None
    assert result["macro_goal_rate"] is None
    assert result["pooled_model_rate"] == 0.5


def test_different_aggregate_cannot_overwrite_existing_file(tmp_path):
    path = tmp_path / "summary.json"
    replication.write_unchanged(path, "original\n")
    replication.write_unchanged(path, "original\n")
    with pytest.raises(RuntimeError, match="overwrite"):
        replication.write_unchanged(path, "different\n")
    assert path.read_text() == "original\n"
