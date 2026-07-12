"""Focused tests for the shared local T0 wave driver and raw scorer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / "run_t0_wave.py"
SPEC = importlib.util.spec_from_file_location("local_t0_wave", PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load T0 wave module")
WAVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WAVE)


def attempt(index: int, target=None, *, qualified=False, gold=False, ambiguous=False):
    return {
        "start_index": index,
        "evaluations": 10,
        "assessor_qualified": qualified,
        "assessor_gold_matched": gold,
        "assessor_target_ambiguous": ambiguous,
        "assessor_matched_target_id": target,
    }


class WaveTests(unittest.TestCase):
    def test_common_assessor_suffix_work(self):
        sequence = [attempt(1, "a", qualified=True, gold=True)] + [
            attempt(index) for index in range(2, 9)
        ]
        self.assertTrue(WAVE.assessor_snapshot(sequence, 1)["safe_full"])
        self.assertEqual(WAVE.suffix_stable_work(sequence, 1), 10)
        sequence[-1].update(
            assessor_qualified=True,
            assessor_gold_matched=False,
            assessor_matched_target_id=None,
        )
        self.assertIsNone(WAVE.suffix_stable_work(sequence, 1))

    def test_path_a_and_path_b(self):
        control = {
            "targets": 5,
            "safe_full": 3,
            "work": 1000,
            "stratum_targets": {key: 1 for key in WAVE.STRATA},
        }
        improved = {**control, "targets": 6, "work": 1100}
        improved["stratum_targets"] = dict(control["stratum_targets"])
        improved["stratum_targets"][WAVE.STRATA[0]] = 2
        gate = WAVE._gate(control, improved, guard_safe=True, recoveries=1,
                          violations=0, integrity=0, truth_audit="pass",
                          mechanism_tests="pass")
        self.assertTrue(gate["path_a"])
        self.assertTrue(gate["passed"])
        efficient = {**control, "work": 800}
        gate = WAVE._gate(control, efficient, guard_safe=True, recoveries=1,
                          violations=0, integrity=0, truth_audit="pass",
                          mechanism_tests="pass")
        self.assertTrue(gate["path_b"])
        self.assertTrue(gate["passed"])

    def test_safety_and_audit_are_mandatory(self):
        control = {
            "targets": 5,
            "safe_full": 3,
            "work": 1000,
            "stratum_targets": {key: 1 for key in WAVE.STRATA},
        }
        candidate = {**control, "work": 700}
        self.assertFalse(WAVE._gate(control, candidate, guard_safe=True, recoveries=1,
                                    violations=1, integrity=0, truth_audit="pass",
                                    mechanism_tests="pass")["passed"])
        self.assertFalse(WAVE._gate(control, candidate, guard_safe=True, recoveries=1,
                                    violations=0, integrity=0, truth_audit="pending",
                                    mechanism_tests="pass")["passed"])

    def test_driver_contract(self):
        self.assertEqual(WAVE.SHARDS, 6)
        self.assertEqual(WAVE.MAX_JOBS, 12)
        self.assertEqual(set(WAVE.CONFIGS), {"008", "009"})
        command = WAVE._command("julia", "008", 5, Path("out.json"), 11)
        self.assertIn("--shard-index=5", command)
        self.assertIn("--shard-count=6", command)


if __name__ == "__main__":
    unittest.main()
