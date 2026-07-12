import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "aggregate_t0.py"
SPEC = importlib.util.spec_from_file_location("aggregate_t0", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _attempt(variant, case, start_index):
    target_index = min(start_index, int(case["target_count"]))
    return {
        "assessor_qualified": True,
        "assessor_gold_matched": True,
        "assessor_target_ambiguous": False,
        "assessor_matched_target_id": f"{case['instance_id']}-target-{target_index}",
        "reported_accepted": True,
        "observed_evaluations": 600,
        "reported_evaluations": 600,
        "evaluation_count_mismatch": False,
        "exception": None,
        "budget_exhausted": False,
        "endpoint": [float(start_index)],
        "instance_id": case["instance_id"],
        "start": [float(start_index)],
        "start_index": start_index,
        "variant": variant,
    }


def _write_shards(root):
    paths = []
    for case_index, case in enumerate(MODULE._expected_cases(), start=1):
        attempts = [
            _attempt(variant, case, start_index)
            for variant in MODULE.VARIANTS
            for start_index in range(1, 9)
        ]
        suffix = int(case["target_count"]) * 600
        terminals = [
            {
                "variant": variant,
                "attempt_count": 8,
                "callback_work": 4_800,
                "suffix_stable_work": suffix,
                "right_censored_suffix_stable_work": suffix,
            }
            for variant in MODULE.VARIANTS
        ]
        document = {
            "schema": "geotarget.local-correction-campaign/v1",
            "case_count": 9,
            "case_index": case_index,
            "revision": {"git_head": "0" * 40, "git_dirty": False},
            "variant_manifest": [
                {"name": variant, "configuration": {}} for variant in MODULE.VARIANTS
            ],
            "problem_manifest": [
                {
                    "instance_id": case["instance_id"],
                    "family_id": case["family_id"],
                    "replay_checksum": case["replay_checksum"],
                    "targets": int(case["target_count"]),
                }
            ],
            "attempts": attempts,
            "terminals": terminals,
        }
        path = root / f"case-{case_index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)
    return paths


class AggregateUnitTests(unittest.TestCase):
    def test_suffix_work_is_suffix_stable_and_unsafe_is_sticky(self):
        good_a = {
            "assessor_qualified": True,
            "assessor_gold_matched": True,
            "assessor_target_ambiguous": False,
            "assessor_matched_target_id": "a",
            "observed_evaluations": 100,
        }
        good_b = {**good_a, "assessor_matched_target_id": "b", "observed_evaluations": 200}
        duplicate = {**good_a, "observed_evaluations": 50}
        self.assertEqual(MODULE._suffix_work([good_a, good_b, duplicate], 2), 300)
        unsafe = {
            **duplicate,
            "assessor_gold_matched": False,
            "assessor_matched_target_id": None,
        }
        self.assertIsNone(MODULE._suffix_work([good_a, good_b, unsafe], 2))

    def test_safety_and_activity_require_real_endpoint_difference(self):
        safe = {
            "assessor_qualified": True,
            "assessor_gold_matched": True,
            "assessor_target_ambiguous": False,
            "assessor_matched_target_id": "a",
            "endpoint": [0.0],
        }
        same = dict(safe)
        changed = {**safe, "endpoint": [1.0e-13]}
        self.assertFalse(MODULE._unsafe(safe))
        self.assertTrue(MODULE._same_safe_target(safe, changed))
        self.assertFalse(MODULE._endpoint_changed(safe, same))
        self.assertTrue(MODULE._endpoint_changed(safe, changed))

    def test_reported_acceptance_rejects_nonqualified_invalid_endpoint(self):
        invalid = {
            "reported_accepted": True,
            "assessor_qualified": False,
            "assessor_gold_matched": False,
            "assessor_target_ambiguous": False,
        }
        self.assertTrue(MODULE._reported_unsafe(invalid))
        invalid["reported_accepted"] = False
        self.assertFalse(MODULE._reported_unsafe(invalid))

    def test_complete_nine_shard_fixture_recomputes_metrics_and_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(Path(directory))
            result = MODULE.aggregate(paths)
        self.assertFalse(any(result["accounting"].values()))
        self.assertEqual(
            result["variant_metrics"][MODULE.CONTROL]["assessor_target_recall"], 1.0
        )
        self.assertEqual(result["reported_unsafe_by_variant"][MODULE.CONTROL], 0)
        self.assertFalse(
            result["candidate_gates"]["E1-FD2-CPQR3"]["gates"]
            ["three_unrelated_active_structures"]
        )

    def test_manifest_and_first_crossing_stop_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(Path(directory))
            document = json.loads(paths[0].read_text(encoding="utf-8"))
            document["problem_manifest"][0]["replay_checksum"] = "f" * 64
            paths[0].write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                MODULE.aggregate(paths)

            paths = _write_shards(Path(directory))
            document = json.loads(paths[0].read_text(encoding="utf-8"))
            extra = dict(document["attempts"][7])
            extra["start_index"] = 9
            extra["start"] = [9.0]
            extra["endpoint"] = [9.0]
            document["attempts"].insert(8, extra)
            terminal = next(
                row for row in document["terminals"] if row["variant"] == MODULE.CONTROL
            )
            terminal["attempt_count"] = 9
            terminal["callback_work"] = 5_400
            paths[0].write_text(json.dumps(document), encoding="utf-8")
            result = MODULE.aggregate(paths)
        self.assertEqual(result["accounting"]["stream_stop_violations"], 1)


if __name__ == "__main__":
    unittest.main()
