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

T2_MODULE_PATH = Path(__file__).parents[1] / "aggregate_t2.py"
T2_SPEC = importlib.util.spec_from_file_location("aggregate_t2", T2_MODULE_PATH)
T2_MODULE = importlib.util.module_from_spec(T2_SPEC)
assert T2_SPEC.loader is not None
sys.modules[T2_SPEC.name] = T2_MODULE
T2_SPEC.loader.exec_module(T2_MODULE)


def _attempt(variant, case, start_index):
    target_index = min(start_index, int(case["targets"]))
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


def _snapshots(variant, case):
    rows = []
    target_count = int(case["targets"])
    for start_index, threshold in zip((1, 2, 4, 8), MODULE.CALLBACK_THRESHOLDS):
        targets = min(start_index, target_count)
        rows.append(
            {
                "assessor_qualified": start_index,
                "assessor_safe_full": targets == target_count,
                "assessor_target_recall": targets / target_count,
                "assessor_targets_found": targets,
                "assessor_unsafe": 0,
                "callback_threshold": threshold,
                "crossing_callback_work": threshold,
                "crossing_start_index": start_index,
                "family_id": case["family_id"],
                "instance_id": case["instance_id"],
                "variant": variant,
            }
        )
    return rows


def _write_shards(root, cases=None, *, suite=None):
    cases = MODULE._expected_cases() if cases is None else cases
    paths = []
    for case_index, case in enumerate(cases, start=1):
        attempts = [
            _attempt(variant, case, start_index)
            for variant in MODULE.VARIANTS
            for start_index in range(1, 9)
        ]
        suffix = int(case["targets"]) * 600
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
            "case_count": len(cases),
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
                    "targets": int(case["targets"]),
                    **(
                        {"saved_starts_checksum": case["saved_starts_checksum"]}
                        if "saved_starts_checksum" in case
                        else {}
                    ),
                }
            ],
            "attempts": attempts,
            "terminals": terminals,
            "threshold_snapshots": [
                row for variant in MODULE.VARIANTS for row in _snapshots(variant, case)
            ],
        }
        if suite is not None:
            document["suite"] = suite
        path = root / f"case-{case_index}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)
    return paths


def _activate_both_candidates(paths, family_count=3):
    activated = set()
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        family = document["problem_manifest"][0]["family_id"]
        if family in activated or len(activated) >= family_count:
            continue
        activated.add(family)
        for attempt in document["attempts"]:
            if (
                attempt["variant"] in MODULE.CANDIDATE_SHADOW
                and attempt["start_index"] == 1
            ):
                attempt["endpoint"] = [100.0 + len(activated)]
        path.write_text(json.dumps(document), encoding="utf-8")
    return activated


class AggregateUnitTests(unittest.TestCase):
    def test_suffix_work_is_suffix_stable_and_unsafe_is_sticky(self):
        good_a = {
            "assessor_qualified": True,
            "assessor_gold_matched": True,
            "assessor_target_ambiguous": False,
            "assessor_matched_target_id": "a",
            "observed_evaluations": 100,
        }
        good_b = {
            **good_a,
            "assessor_matched_target_id": "b",
            "observed_evaluations": 200,
        }
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
        self.assertEqual(
            result["variant_metrics"][MODULE.CONTROL]["mean_family_safe_full_rate"],
            1.0,
        )
        for family in result["family_metrics"][MODULE.CONTROL].values():
            self.assertEqual(family["safe_full_cases"], family["case_count"])
            self.assertEqual(family["safe_full_rate"], 1.0)
        self.assertFalse(
            result["candidate_gates"]["E1-FD2-CPQR3"]["gates"][
                "three_unrelated_active_structures"
            ]
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

    def test_threshold_snapshot_must_be_the_true_first_crossing(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(Path(directory))
            document = json.loads(paths[0].read_text(encoding="utf-8"))
            document["threshold_snapshots"][0]["crossing_start_index"] = 2
            paths[0].write_text(json.dumps(document), encoding="utf-8")
            result = MODULE.aggregate(paths)
        self.assertEqual(result["accounting"]["threshold_snapshot_mismatches"], 1)


class AggregateT2Tests(unittest.TestCase):
    def test_committed_manifest_materializes_exact_48_case_contract(self):
        cases = T2_MODULE.expected_cases()
        self.assertEqual(len(cases), 48)
        self.assertEqual(sum(case["targets"] for case in cases), 88)
        self.assertEqual(len({case["instance_id"] for case in cases}), 48)
        self.assertTrue(all("saved_starts_checksum" in case for case in cases))

    def test_complete_48_shard_fixture_recomputes_family_equal_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(
                Path(directory), T2_MODULE.expected_cases(), suite=T2_MODULE.T2_SUITE
            )
            result = T2_MODULE.aggregate(paths)
        self.assertFalse(any(result["accounting"].values()))
        self.assertEqual(result["suite"], "t2")
        self.assertEqual(
            result["variant_metrics"][MODULE.CONTROL]["assessor_target_count"], 88
        )
        self.assertEqual(
            result["variant_metrics"][MODULE.CONTROL]["mean_family_safe_full_rate"],
            1.0,
        )
        families = result["family_metrics"][MODULE.CONTROL]
        self.assertEqual(len(families), 8)
        for family in families.values():
            self.assertEqual(family["case_count"], 6)
            self.assertEqual(family["safe_full_cases"], 6)
            self.assertEqual(family["safe_full_rate"], 1.0)

    def test_t2_rejects_missing_duplicate_and_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(
                Path(directory), T2_MODULE.expected_cases(), suite=T2_MODULE.T2_SUITE
            )
            with self.assertRaisesRegex(ValueError, "expected 48 shard paths"):
                T2_MODULE.aggregate(paths[:-1])
            with self.assertRaisesRegex(ValueError, "case indices must be exactly"):
                T2_MODULE.aggregate([paths[0], *paths[:-1]])

            document = json.loads(paths[0].read_text(encoding="utf-8"))
            document["problem_manifest"][0].pop("saved_starts_checksum")
            paths[0].write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                T2_MODULE.aggregate(paths)

            paths = _write_shards(
                Path(directory), T2_MODULE.expected_cases(), suite=T2_MODULE.T2_SUITE
            )
            document = json.loads(paths[0].read_text(encoding="utf-8"))
            document["problem_manifest"][0]["saved_starts_checksum"] = "f" * 64
            paths[0].write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                T2_MODULE.aggregate(paths)

    def test_both_pass_and_exact_tie_selects_cpqr_finalist(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(
                Path(directory), T2_MODULE.expected_cases(), suite=T2_MODULE.T2_SUITE
            )
            self.assertEqual(len(_activate_both_candidates(paths)), 3)
            result = T2_MODULE.aggregate(paths)
        self.assertTrue(result["t2_candidate_gates"]["E1-FD2-CPQR3"]["passes_t2"])
        self.assertTrue(result["t2_candidate_gates"]["E2-FD2-SVD3"]["passes_t2"])
        self.assertEqual(result["selected_finalist"], "E1-FD2-CPQR3")
        self.assertEqual(
            result["variant_metrics"]["E1-FD2-CPQR3"]["mean_family_safe_full_rate"],
            result["variant_metrics"]["E2-FD2-SVD3"]["mean_family_safe_full_rate"],
        )
        self.assertEqual(
            result["t2_candidate_gates"]["E1-FD2-CPQR3"]["active_family_count"],
            3,
        )

    def test_t2_first_crossing_and_index_manifest_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_shards(
                Path(directory), T2_MODULE.expected_cases(), suite=T2_MODULE.T2_SUITE
            )
            document = json.loads(paths[0].read_text(encoding="utf-8"))
            document["threshold_snapshots"][0]["crossing_callback_work"] = 601
            paths[0].write_text(json.dumps(document), encoding="utf-8")
            result = T2_MODULE.aggregate(paths)
            self.assertEqual(result["accounting"]["threshold_snapshot_mismatches"], 1)

            paths = _write_shards(
                Path(directory), T2_MODULE.expected_cases(), suite=T2_MODULE.T2_SUITE
            )
            first = json.loads(paths[0].read_text(encoding="utf-8"))
            second = json.loads(paths[1].read_text(encoding="utf-8"))
            first["problem_manifest"] = second["problem_manifest"]
            paths[0].write_text(json.dumps(first), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                T2_MODULE.aggregate(paths)


if __name__ == "__main__":
    unittest.main()
