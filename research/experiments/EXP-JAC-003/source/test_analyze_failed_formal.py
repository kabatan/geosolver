from __future__ import annotations

import importlib.util
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().with_name("analyze_failed_formal.py")
SPEC = importlib.util.spec_from_file_location("analyze_failed_formal", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def safety_document(values: list[int | float | bool]) -> dict:
    entries = [[0, index, value] for index, value in enumerate(values)]
    matrix = {"entries": entries, "shape": [1, len(entries)]}
    return {
        "cases": [
            {
                "starts": [
                    {"colored": copy.deepcopy(matrix), "dense": copy.deepcopy(matrix)}
                ]
            }
        ],
        "fallback_controls": [],
        "incomplete_pattern_controls": [],
    }


class FailedFormalForensicsTests(unittest.TestCase):
    def test_normalization_is_deep_and_exactly_bounded(self) -> None:
        original = safety_document([-1, 0, 1, 0.5])
        normalized, report = MODULE.normalize_matrix_integer_tokens(original)
        self.assertEqual(report["observed_integer_values"], [-1, 0, 1])
        self.assertEqual(report["normalization_count"], 6)
        self.assertIs(
            type(original["cases"][0]["starts"][0]["dense"]["entries"][0][2]), int
        )
        self.assertIs(
            type(normalized["cases"][0]["starts"][0]["dense"]["entries"][0][2]), float
        )

    def test_other_integer_matrix_value_fails_closed(self) -> None:
        with self.assertRaisesRegex(MODULE.ForensicError, "outside"):
            MODULE.normalize_matrix_integer_tokens(safety_document([2]))

    def test_boolean_is_not_normalized_as_an_integer(self) -> None:
        original = safety_document([True, 0])
        normalized, report = MODULE.normalize_matrix_integer_tokens(original)
        self.assertEqual(report["observed_integer_values"], [0])
        self.assertIs(
            type(normalized["cases"][0]["starts"][0]["dense"]["entries"][0][2]),
            bool,
        )

    def test_host_output_is_only_category_name_aggregate(self) -> None:
        host = {
            "contention_events": [
                {"category": "host_process", "name": "tool", "pid": 12},
                {"category": "host_process", "name": "tool", "pid": 13},
                {"category": "process_start", "name": "other", "pid": 14},
                {"category": "aggregate_cpu", "name": None},
            ],
            "host_contention_event_count": 4,
        }
        self.assertEqual(
            MODULE.aggregate_host_categories(host),
            [
                {"category": "aggregate_cpu", "count": 1, "name": "<none>"},
                {"category": "host_process", "count": 2, "name": "tool"},
                {"category": "process_start", "count": 1, "name": "other"},
            ],
        )

    def test_partial_inventory_refuses_segment_trace_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "segments").mkdir()
            (root / "segments" / "segment-0.json").write_text("not json")
            with self.assertRaisesRegex(MODULE.ForensicError, "must not read"):
                MODULE.partial_inventory(root)

    def test_claim_excludes_efficacy_and_individual_values(self) -> None:
        analysis = {
            "safety_assessment": {
                "aggregate_counts": {"failure": 0},
                "passed": True,
                "representation_normalization": {
                    "normalization_count": 3,
                    "observed_integer_values": [-1, 0, 1],
                },
            }
        }
        claim = MODULE.build_claim_boundary(analysis)
        self.assertIn("no ABBA", claim)
        self.assertIn("The frozen assessor read its safety", claim)
        self.assertIn("reference matrices and statuses", claim)
        self.assertIn("No segment trace or K0 control outcome was opened", claim)
        self.assertIn("No scalar target Gold", claim)
        self.assertNotIn("opaque_case_id", claim)

    def test_write_once_refuses_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "result.json"
            path.write_text(json.dumps({"old": True}))
            with self.assertRaises(FileExistsError):
                MODULE.write_once(path, b"{}")


if __name__ == "__main__":
    unittest.main()
